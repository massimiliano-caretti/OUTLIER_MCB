"""test_math_discovery — Step 7: honest conjecture → counterexample → empirical → proof.

A false identity is killed by a counterexample; a true identity is EMPIRICALLY_SUPPORTED by sampling and
FORMALLY_PROVED by SymPy when available (TOOL_UNAVAILABLE otherwise). Never 'theorem' without a proof.
"""
import OUTLIER_MCB as gsl


def test_false_identity_is_killed_by_a_counterexample():
    conj = gsl.Conjecture("x**2 == x for all x", variables={"x": (-5.0, 5.0)})
    res = gsl.investigate_conjecture(conj, predicate=lambda x: abs(x * x - x) < 1e-9, use_sympy=False)
    assert res.status == "COUNTEREXAMPLE_FOUND"
    assert res.counterexample is not None


def test_true_identity_is_empirically_supported_without_sympy():
    conj = gsl.Conjecture("(x+1)**2 == x**2+2x+1", variables={"x": (-5.0, 5.0)})
    res = gsl.investigate_conjecture(
        conj, predicate=lambda x: abs((x + 1) ** 2 - (x ** 2 + 2 * x + 1)) < 1e-9, use_sympy=False)
    assert res.status == "EMPIRICALLY_SUPPORTED"
    assert res.samples_passed == res.samples_total
    assert "not a proof" in res.note.lower()              # honesty: evidence is not proof


def test_no_predicate_is_a_sketch():
    res = gsl.investigate_conjecture(gsl.Conjecture("some deep claim"), use_sympy=False)
    assert res.status == "SKETCH"


def test_vacuous_hypotheses_do_not_license_a_formal_proof():
    conj = gsl.Conjecture("vacuous implication", claim_expr="x > x",
                          hypotheses=["x > 0", "x < 0"], variables={"x": (-1.0, 1.0)})

    def fake_backend(c):
        return "FORMALLY_PROVED", None, "a solver would prove this vacuously"

    res = gsl.investigate_conjecture(conj, backend=fake_backend, use_sympy=False)

    assert res.status == "VACUOUS_DOMAIN"
    assert "no witness" in res.note.lower()


def test_settle_lemma_numeric_fallback_respects_hypotheses():
    good = gsl.Conjecture("x >= 1 implies x > 0", claim_expr="x > 0",
                          hypotheses=["x >= 1"], variables={"x": (-2, 2)}, domain="int")
    cert = gsl.settle_lemma(good)
    assert cert.status == "NUMERIC_VERIFIED"

    bad = gsl.Conjecture("x >= 1 implies x > 1", claim_expr="x > 1",
                         hypotheses=["x >= 1"], variables={"x": (-2, 2)}, domain="int")
    refuted = gsl.settle_lemma(bad)
    assert refuted.status == "NUMERIC_REFUTED"
    assert refuted.counterexample == {"x": 1}

    vacuous = gsl.Conjecture("empty integer domain", claim_expr="x > x",
                             hypotheses=["x > 1", "x < 0"], variables={"x": (-2, 2)}, domain="int")
    empty = gsl.settle_lemma(vacuous)
    assert empty.status == "UNKNOWN_TIMEOUT"
    assert "no witness" in empty.detail.lower()


def test_sympy_path_proves_or_reports_tool_unavailable():
    conj = gsl.Conjecture("(x+1)**2 == x**2+2*x+1", lhs="(x+1)**2", rhs="x**2+2*x+1",
                          variables={"x": (-5.0, 5.0)})
    res = gsl.investigate_conjecture(conj, use_sympy=True)
    try:
        import sympy  # noqa: F401
        assert res.status == "FORMALLY_PROVED"            # a CAS confirmed the identity
        assert res.proof.status == "FORMALLY_PROVED"
    except ImportError:
        # no SymPy: the formal path is honest about being unavailable, and nothing crashes.
        assert res.proof is not None and res.proof.status == "TOOL_UNAVAILABLE"
        assert res.status in ("SKETCH", "EMPIRICALLY_SUPPORTED")


def test_markdown_renders():
    conj = gsl.Conjecture("x == x", variables={"x": (-1.0, 1.0)})
    md = gsl.investigate_conjecture(conj, predicate=lambda x: True, use_sympy=False).markdown()
    assert "Math discovery" in md


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
