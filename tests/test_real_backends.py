"""test_real_backends — P2: optional PySR / DoWhy adapters, with ZERO hard dependency.

The factories always return a callable; the heavy library is imported lazily inside it. If the library is
present, the backend fits for real; if absent, it raises a CLEAR ImportError — never a silent or fake
result. Either way `import OUTLIER_MCB` must not require PySR/DoWhy.
"""
import random

import pytest

import OUTLIER_MCB as gsl
from OUTLIER_MCB.generators import Candidate


def _interaction_data(n=120, seed=7):
    rng = random.Random(seed)
    X = [[rng.uniform(-2, 2), rng.uniform(-2, 2), rng.uniform(-2, 2)] for _ in range(n)]
    y = [2.0 * r[0] * r[1] - 3.0 for r in X]
    cut = int(0.66 * n)
    return X[:cut], y[:cut], X[cut:], y[cut:]


def _confounded(n=300, seed=11):
    rng = random.Random(seed)
    Z = [rng.gauss(0, 1) for _ in range(n)]
    A = [Z[i] + 0.5 * rng.gauss(0, 1) for i in range(n)]
    B = [Z[i] + 0.5 * rng.gauss(0, 1) for i in range(n)]
    return {"A": A, "B": B, "Z": Z}


def _candidate():
    return Candidate(name="brk", operator="invert", breaks=["FORM"], assumptions=["law_is_separable"],
                     negation="break separability with an interaction term")


def test_factories_return_callables_without_importing_deps():
    assert callable(gsl.pysr_backend())
    assert callable(gsl.dowhy_backend())


def test_pysr_backend_runs_or_raises_clearly():
    pack = gsl.get_pack("numeric")
    X_tr, y_tr, _, _ = _interaction_data()
    backend = gsl.pysr_backend(pack=pack)
    try:
        import pysr, numpy  # noqa: F401
    except ImportError:
        with pytest.raises(ImportError, match="pysr"):
            backend(X_tr, y_tr, _candidate(), 3)
        return
    # if PySR IS installed, the symbolic evaluator must run end-to-end through the real backend.
    ev = gsl.symbolic_evaluator(_interaction_data(), pack=pack, backend=backend)
    out = ev(_candidate())
    assert "score" in out and "formula" in out


def test_dowhy_backend_runs_or_raises_clearly():
    pack = gsl.get_pack("causal")
    backend = gsl.dowhy_backend()
    try:
        import dowhy, pandas  # noqa: F401
    except ImportError:
        # causal_evaluator estimates eagerly (truth/naive) at construction → the clear error fires here.
        with pytest.raises(ImportError, match="dowhy"):
            gsl.causal_evaluator(_confounded(), "A", "B", ["Z"], pack=pack, backend=backend)
        return
    ev = gsl.causal_evaluator(_confounded(), "A", "B", ["Z"], pack=pack, backend=backend)
    out = ev(_candidate())
    assert "score" in out and "effect" in out


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
