"""test_z3_backend — the optional Z3 prover: decide inequalities / hypotheses with guaranteed verdicts.

Z3 proves what SymPy's identity check cannot (inequalities, statements under hypotheses) and returns a
GUARANTEED counterexample when a claim is false. Zero hard dependency: absent ⇒ TOOL_UNAVAILABLE, never a
crash, and identities still prove via SymPy. Robust whether or not z3-solver is installed.
"""
import OUTLIER_MCB as gsl


def _has_z3():
    try:
        import z3  # noqa: F401
        return True
    except ImportError:
        return False


def test_z3_backend_is_callable():
    assert callable(gsl.z3_backend())


def test_proves_an_inequality_or_reports_unavailable():
    # AM–GM in two variables: x² + y² ≥ 2xy  (= (x−y)² ≥ 0) — true for all reals, but NOT an identity.
    conj = gsl.Conjecture("x^2 + y^2 >= 2xy for all real x,y",
                          claim_expr="x**2 + y**2 >= 2*x*y", variables={"x": (-5.0, 5.0), "y": (-5.0, 5.0)})
    res = gsl.investigate_conjecture(conj, backend=gsl.z3_backend())
    if _has_z3():
        assert res.status == "FORMALLY_PROVED" and res.proof.method == "z3"
    else:
        assert res.status == "SKETCH" and res.proof.status == "TOOL_UNAVAILABLE"


def test_disproves_with_guaranteed_counterexample_or_unavailable():
    # x² ≥ x is FALSE over the reals (e.g. x = 0.5) — sampling might miss it; Z3 must not.
    conj = gsl.Conjecture("x^2 >= x for all real x", claim_expr="x**2 >= x", variables={"x": (-5.0, 5.0)})
    res = gsl.investigate_conjecture(conj, backend=gsl.z3_backend())
    if _has_z3():
        assert res.status == "FORMALLY_DISPROVED"
        assert res.counterexample is not None and res.counterexample.assignment
    else:
        assert res.status == "SKETCH" and res.proof.status == "TOOL_UNAVAILABLE"


def test_proves_under_hypothesis_or_unavailable():
    # under x > 0: x + 1/x ≥ 2 (AM–GM). A statement with a PRECONDITION — outside SymPy's identity check.
    conj = gsl.Conjecture("x + 1/x >= 2 for x>0", claim_expr="x + 1/x >= 2",
                          hypotheses=["x > 0"], variables={"x": (0.01, 100.0)})
    res = gsl.investigate_conjecture(conj, backend=gsl.z3_backend())
    assert res.status in ("FORMALLY_PROVED", "TOOL_LIMIT_UNKNOWN", "SKETCH")  # nonlinear ⇒ may be unknown; never a crash


def test_identity_still_proved_without_z3_via_sympy():
    # with the backend present but z3 maybe absent, an identity must still come out FORMALLY_PROVED (SymPy).
    conj = gsl.Conjecture("(x+1)^2 = x^2+2x+1", lhs="(x+1)**2", rhs="x**2+2*x+1", variables={"x": (-3.0, 3.0)})
    res = gsl.investigate_conjecture(conj, backend=gsl.z3_backend())
    assert res.status == "FORMALLY_PROVED"


def test_no_backend_is_unchanged():
    # the default path (no backend) is exactly as before.
    conj = gsl.Conjecture("x*x == x", variables={"x": (-3.0, 3.0)})
    res = gsl.investigate_conjecture(conj, predicate=lambda x: abs(x * x - x) < 1e-9, use_sympy=False)
    assert res.status == "COUNTEREXAMPLE_FOUND"


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
