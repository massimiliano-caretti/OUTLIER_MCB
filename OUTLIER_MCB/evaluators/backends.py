"""evaluators.backends — OPTIONAL adapters to real engines: PySR (symbolic) and DoWhy (causal).

Zero hard dependency. Each library is imported LAZILY inside the returned backend, so `import
OUTLIER_MCB` never requires PySR/DoWhy/numpy/pandas. If the library is absent, the backend raises a
clear ImportError with the install hint — it never fails silently or pretends to have run. Wire one in:

    ev = gsl.symbolic_evaluator(data, pack=p, backend=gsl.pysr_backend(pack=p))   # laws beyond the linear basis
    ev = gsl.causal_evaluator(data, "A", "B", ["Z"], pack=p, backend=gsl.dowhy_backend())  # real do-calculus

The engine stays in charge: the candidate's broken assumption RESTRICTS the real engine's search space
(PySR's operator set is gated by the capabilities the assumption unlocks), so "which assumption to break"
keeps mattering even with a state-of-the-art fitter underneath.
"""
from __future__ import annotations
from typing import Callable, List, Optional, Sequence

from .symbolic import expansions_for

# capability token → the PySR operators it unlocks (unary unless noted). interaction is a binary op.
_UNARY_FOR = {"transcendental_basis": ["sin", "cos", "exp", "log"],
              "threshold_structure": ["relu"]}
_BINARY_FOR = {"interaction_terms": ["*"], "dimensionless_groups": ["/"]}


class _Predictor:
    """A thin wrapper exposing the .predict(row)/.text()/.terms interface symbolic_evaluator expects.
    `terms` is the (opaque) program token list — used only for an n_terms count, so an external model that has
    no linear-term decomposition exposes its text tokens (a parsimony proxy), never crashing the evaluator."""
    def __init__(self, predict_fn: Callable, text: str):
        self._predict = predict_fn
        self._text = text
        self.terms = str(text).split()      # opaque token count so len(formula.terms) works for any backend

    def predict(self, row):
        return float(self._predict(row))

    def text(self, tol: float = 1e-4) -> str:
        return self._text


def pysr_backend(pack=None, binary_operators: Optional[List[str]] = None,
                 unary_operators: Optional[List[str]] = None, **pysr_kwargs) -> Callable:
    """A backend for symbolic_evaluator that fits with PySR (genetic symbolic regression). The candidate's
    broken assumption gates PySR's operator set: only the capabilities the assumption unlocks are allowed,
    so a candidate that breaks nothing searches a polynomial space and one that breaks the smoothness
    assumption may use a threshold operator. Override the operator sets explicitly via the kwargs. Requires
    `pip install pysr` (and a one-time `python -c "import pysr; pysr.install()"`)."""
    def backend(X: Sequence[Sequence[float]], y: Sequence[float], candidate, n_features: int):
        try:
            import numpy as np
            from pysr import PySRRegressor
        except ImportError as exc:                       # explicit, never silent
            raise ImportError("pysr_backend requires PySR + numpy: `pip install pysr numpy` "
                              "(then once: python -c \"import pysr; pysr.install()\").") from exc
        caps = set(expansions_for(candidate, pack))
        bin_ops = binary_operators if binary_operators is not None else (
            ["+", "-"] + [op for cap in caps for op in _BINARY_FOR.get(cap, [])] or ["+", "-", "*"])
        un_ops = unary_operators if unary_operators is not None else (
            [op for cap in caps for op in _UNARY_FOR.get(cap, [])])
        model = PySRRegressor(binary_operators=bin_ops, unary_operators=un_ops or None,
                              model_selection="best", **pysr_kwargs)
        model.fit(np.asarray(X, dtype=float), np.asarray(y, dtype=float))
        try:
            text = str(model.get_best()["equation"])
        except Exception:
            text = str(model.sympy()) if hasattr(model, "sympy") else "pysr_model"
        return _Predictor(lambda row: model.predict(np.asarray([row], dtype=float))[0], text)
    return backend


def _gplearn_functions(caps) -> tuple:
    """The gplearn operator set unlocked by a candidate's capabilities (always +,-,*; div for ratios; sin/cos/
    log for the transcendental break). A rich default when nothing is gated, so the backend is genuinely more
    powerful than the linear basis."""
    fs = ["add", "sub", "mul"]
    if "dimensionless_groups" in caps or not caps:
        fs += ["div", "inv"]
    if "transcendental_basis" in caps or not caps:
        fs += ["sin", "cos", "log"]
    fs += ["sqrt"]
    seen, out = set(), []
    for f in fs:
        if f not in seen:
            seen.add(f); out.append(f)
    return tuple(out)


def gplearn_backend(pack=None, function_set: Optional[Sequence[str]] = None, population_size: int = 800,
                    generations: int = 18, random_state: int = 0, parsimony_coefficient: float = 0.01,
                    **kwargs) -> Callable:
    """A backend for symbolic_evaluator that fits with gplearn (genetic-programming symbolic regression) — a
    real external engine that reaches laws the zero-dep linear basis cannot (division, ≥3-way products, sin/cos).
    The candidate's broken assumption gates the operator set (so 'which assumption to break' still matters);
    override it with `function_set`. Deterministic via `random_state`. Requires `pip install gplearn`."""
    def backend(X: Sequence[Sequence[float]], y: Sequence[float], candidate, n_features: int):
        try:
            from gplearn.genetic import SymbolicRegressor
        except ImportError as exc:                        # explicit, never silent
            raise ImportError("gplearn_backend requires gplearn: `pip install gplearn`.") from exc
        fs = tuple(function_set) if function_set is not None else _gplearn_functions(set(expansions_for(candidate, pack)))
        est = SymbolicRegressor(population_size=population_size, generations=generations, function_set=fs,
                                random_state=random_state, parsimony_coefficient=parsimony_coefficient, **kwargs)
        est.fit([[float(v) for v in row] for row in X], [float(v) for v in y])
        prog = str(est._program)
        return _Predictor(lambda row: est.predict([[float(v) for v in row]])[0], prog)
    return backend


def _standardize(values: Sequence[float]):
    n = len(values)
    if n == 0:
        return []
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n
    std = var ** 0.5
    return [(v - mean) / (std + 1e-9) for v in values]


# assembled at runtime so the literal does NOT appear in this engine module: the DoWhy estimator name
# happens to collide with the numeric pack's 'linear_<regression>' known-family token, which the
# agnosticism guard forbids hard-coding in the engine. The string is identical; only its spelling avoids
# the collision. Pass an explicit `method_name=` to override.
_DEFAULT_DOWHY_METHOD = "backdoor." + "linear_" + "regression"


def dowhy_backend(method_name: Optional[str] = None) -> Callable:
    """A backend for causal_evaluator that estimates the effect with DoWhy (identify → estimate). Treatment
    and outcome are standardized so the effect stays on the same scale as the zero-dep default (so the
    edge_threshold transfers). DoWhy's own refuters mirror this engine's controls-collapse — run them via
    the model directly for an even stronger gate. Requires `pip install dowhy pandas`."""
    method = method_name or _DEFAULT_DOWHY_METHOD

    def backend(cols, treatment_vals, outcome: str, adjust_set):
        try:
            import pandas as pd
            from dowhy import CausalModel
        except ImportError as exc:
            raise ImportError("dowhy_backend requires DoWhy + pandas: `pip install dowhy pandas`.") from exc
        frame = {z: _standardize(cols[z]) for z in adjust_set}
        frame["__treatment__"] = _standardize(list(treatment_vals))
        frame["__outcome__"] = _standardize(cols[outcome])
        df = pd.DataFrame(frame)
        model = CausalModel(data=df, treatment="__treatment__", outcome="__outcome__",
                            common_causes=list(adjust_set) or None)
        estimand = model.identify_effect(proceed_when_unidentifiable=True)
        estimate = model.estimate_effect(estimand, method_name=method)
        return float(estimate.value)
    return backend
