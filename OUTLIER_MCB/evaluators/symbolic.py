"""evaluators.symbolic — settle a Candidate by the DATA, not by self-judgment.

The numeric twin of creative_search.code_evaluator (which settles by the repo). A Candidate proposes
breaking an assumption about the FORM of a law (separable / smooth / polynomial / raw-variables). The
broken assumption EXPANDS the hypothesis class — the basis of candidate terms a regressor may use. A
pure-Python, linear-in-parameters symbolic regressor fits a formula in that class; the formula is then
FALSIFIED two ways, mirroring the kernel's death-gate:

  • held-out residual — the formula must predict an unseen split (not just memorize the train split);
  • negative control — each feature column is independently shuffled, destroying the multivariate
    structure while preserving every marginal. The fit MUST collapse on this control; if it does not,
    the "law" was leakage, not signal (death-gate clause (c): "controls do not collapse").

The engine chooses the inductive bias (which assumption to break); the DATA settle the formula. No
fabrication: a candidate whose controls do not collapse is graded down, never silently accepted. The
default backend is zero-dependency and deterministic so the whole loop runs offline; inject a real
backend (PySR / gplearn) by passing `backend=` to reach laws the linear basis cannot express.

Usage — the existing FunSearch + QD machinery does the rest:

    import OUTLIER_MCB as gsl
    ev = gsl.symbolic_evaluator((X_tr, y_tr, X_ho, y_ho))
    res = gsl.creative_search("discover a law for <phenomenon>", evaluator=ev,
                              pack=gsl.get_pack("numeric"), budget=60)
    print(res.markdown())
"""
from __future__ import annotations
import math
import random
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Tuple

Row = Sequence[float]
Dataset = Tuple[Sequence[Row], Sequence[float], Sequence[Row], Sequence[float]]

_EPS = 1e-9


@dataclass
class Term:
    """One basis function: a human-readable label and the scalar it computes from a row."""
    label: str
    fn: Callable[[Row], float]


@dataclass
class Formula:
    """A fitted linear-in-parameters expression: Σ coeff·term."""
    terms: List[Term]
    coeffs: List[float]

    def predict(self, row: Row) -> float:
        return sum(c * t.fn(row) for c, t in zip(self.coeffs, self.terms))

    def text(self, tol: float = 1e-4) -> str:
        parts = [f"{c:.3g}·{t.label}" for c, t in zip(self.coeffs, self.terms) if abs(c) > tol]
        return " + ".join(parts).replace("·1", "").replace("+ -", "- ") if parts else "0"


# ── generic primitive basis builders, keyed by CAPABILITY token (never by an assumption name) ───────
# The engine stays domain-blind: it knows only how to BUILD a primitive family for a capability token.
# WHICH capability a broken assumption requires is the pack's knowledge, declared in its relations
# (`assumption --if_false_requires--> <capability>`); the evaluator reads it from the pack, it does not
# hard-code it. Callers can extend or replace these builders via `builders=`.
def _interaction_terms(n):
    out = []
    for i in range(n):
        out.append(Term(f"x{i}^2", lambda r, i=i: r[i] * r[i]))
        for j in range(i + 1, n):
            out.append(Term(f"x{i}*x{j}", lambda r, i=i, j=j: r[i] * r[j]))
    return out


def _threshold_structure(n):
    out = []
    for i in range(n):
        out.append(Term(f"relu(x{i})", lambda r, i=i: r[i] if r[i] > 0 else 0.0))
        out.append(Term(f"relu(-x{i})", lambda r, i=i: -r[i] if r[i] < 0 else 0.0))
    return out


def _transcendental_basis(n):
    out = []
    for i in range(n):
        out.append(Term(f"sin(x{i})", lambda r, i=i: math.sin(r[i])))
        out.append(Term(f"cos(x{i})", lambda r, i=i: math.cos(r[i])))
    return out


def _dimensionless_groups(n):
    out = []
    for i in range(n):
        for j in range(n):
            if i != j:
                out.append(Term(f"x{i}/(1+|x{j}|)", lambda r, i=i, j=j: r[i] / (1.0 + abs(r[j]))))
    return out


DEFAULT_BUILDERS: Dict[str, Callable[[int], List[Term]]] = {
    "interaction_terms": _interaction_terms,
    "threshold_structure": _threshold_structure,
    "transcendental_basis": _transcendental_basis,
    "dimensionless_groups": _dimensionless_groups,
}

# a robust fallback when no pack is supplied: generic English hints in the candidate's negation text.
# These are plain words, not pack tokens, so the engine stays domain-blind.
_TEXT_HINTS = {
    "interaction_terms": ("interact", "coupl", "separab", "product"),
    "threshold_structure": ("threshold", "kink", "piecewise", "heaviside", "relu", "transition"),
    "transcendental_basis": ("sin", "cos", "exp", "log", "periodic", "trig", "transcend"),
    "dimensionless_groups": ("dimensionless", "ratio"),
}


# ── basis construction (the broken assumption decides the hypothesis class) ─────────────────────────
def expansions_for(candidate, pack=None, text_hints=None) -> List[str]:
    """The capability tokens a candidate unlocks. PRIMARY source: the PACK's relations — for each
    assumption the candidate breaks, the `if_false_requires` edge names the capability its break needs
    (so the engine never hard-codes assumption→capability). FALLBACK (only when the pack resolved
    nothing, e.g. no pack or a free-text idea): generic keywords in the negation text (`text_hints`
    overrides the default symbolic-regression hints, e.g. for the causal evaluator).

    The text is a fallback, never additive: once the pack has spoken for this candidate, its declared
    relations are authoritative — a hint word that merely appears in an assumption's prose does not
    silently bolt on an unrelated capability."""
    out: List[str] = []
    broken = set(getattr(candidate, "assumptions", []) or [])
    for edge in getattr(pack, "relations", []) or []:
        src, rel, dst = edge[0], edge[1], edge[2]
        if rel == "if_false_requires" and src in broken:
            out.append(dst)
    if not out:                         # fallback: only when the pack resolved no capability
        text = (getattr(candidate, "negation", "") or "").lower()
        for token, words in (text_hints if text_hints is not None else _TEXT_HINTS).items():
            if any(w in text for w in words):
                out.append(token)
    seen, uniq = set(), []
    for e in out:                       # preserve order, dedup
        if e not in seen:
            seen.add(e); uniq.append(e)
    return uniq


def basis_from_candidate(candidate, n_features: int, pack=None, builders=None) -> List[Term]:
    """Build the term basis for a candidate: ALWAYS the box (constant + linear, the additive-smooth
    baseline), PLUS only the primitive families unlocked by the capabilities its broken assumptions
    require. A candidate that breaks nothing gets the box alone — and therefore cannot fit a
    coupled/transcendental law, which is exactly why it should score INSIDE_THE_BOX."""
    builders = builders if builders is not None else DEFAULT_BUILDERS
    terms: List[Term] = [Term("1", lambda r: 1.0)]
    for i in range(n_features):
        terms.append(Term(f"x{i}", lambda r, i=i: r[i]))
    for token in expansions_for(candidate, pack):
        build = builders.get(token)
        if build is not None:
            terms.extend(build(n_features))
    return terms


# ── the default backend: pure-Python linear least squares (ridge-stabilized normal equations) ───────
def _solve(ata: List[List[float]], aty: List[float]) -> List[float]:
    """Gaussian elimination with partial pivoting on the (already symmetric) normal-equation system."""
    n = len(aty)
    m = [row[:] + [aty[i]] for i, row in enumerate(ata)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[piv][col]) < _EPS:
            continue
        m[col], m[piv] = m[piv], m[col]
        pivot = m[col][col]
        for r in range(n):
            if r != col and abs(m[r][col]) > _EPS:
                f = m[r][col] / pivot
                for c in range(col, n + 1):
                    m[r][c] -= f * m[col][c]
    return [m[i][n] / m[i][i] if abs(m[i][i]) > _EPS else 0.0 for i in range(n)]


def least_squares(X: Sequence[Row], y: Sequence[float], terms: List[Term], ridge: float = 1e-8) -> Formula:
    """Fit Σ coeff·term to y by ridge-stabilized least squares — deterministic, no dependencies."""
    k = len(terms)
    feats = [[t.fn(row) for t in terms] for row in X]
    ata = [[sum(feats[s][i] * feats[s][j] for s in range(len(X))) + (ridge if i == j else 0.0)
            for j in range(k)] for i in range(k)]
    aty = [sum(feats[s][i] * y[s] for s in range(len(X))) for i in range(k)]
    return Formula(terms=terms, coeffs=_solve(ata, aty))


# ── falsification metrics ───────────────────────────────────────────────────────────────────────────
def _nrmse(formula: Formula, X: Sequence[Row], y: Sequence[float]) -> float:
    if not y:
        return float("inf")
    mse = sum((formula.predict(X[s]) - y[s]) ** 2 for s in range(len(y))) / len(y)
    mean = sum(y) / len(y)
    denom = math.sqrt(sum((v - mean) ** 2 for v in y) / len(y))
    return math.sqrt(mse) / (denom + _EPS)


def _shuffled_columns(X: Sequence[Row], seed: int) -> List[List[float]]:
    """Independently permute each feature column across rows — kills the multivariate (joint) structure
    while preserving every marginal. The NEGATIVE CONTROL: a real law collapses here; leakage does not."""
    if not X:
        return []
    n_feat = len(X[0])
    cols = [[X[r][c] for r in range(len(X))] for c in range(n_feat)]
    rng = random.Random(seed)
    for c in cols:
        rng.shuffle(c)
    return [[cols[c][r] for c in range(n_feat)] for r in range(len(X))]


# ── the external evaluator ──────────────────────────────────────────────────────────────────────────
def symbolic_evaluator(dataset: Dataset, pack=None, backend: Optional[Callable] = None,
                       builders=None, collapse_ratio: float = 2.0, seed: int = 0) -> Callable[[object], Dict]:
    """An EXTERNAL evaluator (Candidate -> {"score", **evidence}) that settles a candidate on the DATA.

    `dataset` = (X_train, y_train, X_holdout, y_holdout), X as rows of floats. The candidate's broken
    assumption selects the basis — resolved through `pack`'s relations (so the engine never hard-codes
    assumption→basis); the backend fits a formula in it; the score in [0,1] rewards a low held-out
    residual ONLY when the negative control collapses (controls_collapse). A candidate whose control
    does not collapse keeps just a fraction of its score — never a free pass.

    `pack` lets a broken assumption be mapped to the capability its break requires (falls back to text
    hints if omitted). `backend(X, y, candidate, n_features) -> Formula` overrides the default
    least-squares fitter (wire PySR/gplearn here). `builders` extends the primitive families. Returns a
    dict so `creative_search` records the formula and residuals as evidence."""
    X_tr, y_tr, X_ho, y_ho = dataset
    n_features = len(X_tr[0]) if X_tr else 0

    def _fit(candidate) -> Formula:
        if backend is not None:
            return backend(X_tr, y_tr, candidate, n_features)
        return least_squares(X_tr, y_tr, basis_from_candidate(candidate, n_features, pack=pack, builders=builders))

    def _ev(candidate) -> Dict:
        formula = _fit(candidate)
        nrmse_ho = _nrmse(formula, X_ho, y_ho)
        nrmse_ctrl = _nrmse(formula, _shuffled_columns(X_ho, seed), y_ho)
        controls_collapse = nrmse_ctrl > collapse_ratio * max(nrmse_ho, _EPS)
        fit_quality = max(0.0, 1.0 - nrmse_ho)
        score = fit_quality * (1.0 if controls_collapse else 0.3)
        return {"score": round(score, 4), "formula": formula.text(),
                "nrmse_holdout": round(nrmse_ho, 4), "nrmse_control": round(nrmse_ctrl, 4),
                "controls_collapse": controls_collapse, "n_terms": len(formula.terms)}

    return _ev
