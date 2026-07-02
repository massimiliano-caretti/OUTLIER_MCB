"""test_conjecture_search — close the loop GENERATE → PROVE: generate candidate conjectures, settle each
with the external solver, and refine the disproved (Reflexion). Robust whether or not z3 is installed.
"""
import OUTLIER_MCB as m


def _has_z3():
    try:
        import z3  # noqa: F401
        return True
    except ImportError:
        return False


def test_generate_conjectures_from_templates():
    conjs = m.generate_conjectures({"x": (-5.0, 5.0)}, ["x**2", "x"], relations=[">="])
    assert conjs and all(c.claim_expr for c in conjs)
    assert any("x**2" in c.statement and ">=" in c.statement for c in conjs)


def test_mine_conjectures_from_formula():
    conjs = m.mine_conjectures_from_formula("2*x0*x1 - 3", {"x0": (-2.0, 2.0), "x1": (-2.0, 2.0)})
    stmts = " ".join(c.statement for c in conjs)
    assert "symmetric" in stmts and "non-negative" in stmts


def test_discover_proves_disproves_and_refines():
    conjs = [
        m.Conjecture("amgm", claim_expr="x**2 + y**2 >= 2*x*y", variables={"x": (-5.0, 5.0), "y": (-5.0, 5.0)}),
        m.Conjecture("x + 1/x >= 2", claim_expr="x + 1/x >= 2", variables={"x": (-9.0, 9.0)}),
    ]
    disco = m.discover_conjectures(conjs)
    if _has_z3():
        assert any(r.status == "FORMALLY_PROVED" and "amgm" in r.statement for r in disco.results)   # a real proof
        assert any(r.status == "FORMALLY_DISPROVED" and "1/x" in r.statement and not r.refined_from
                   for r in disco.results)                                                            # false over ℝ
        assert any(r.status == "FORMALLY_PROVED" and r.refined_from for r in disco.results)           # rescued by x>0
        d = disco.to_dict()
        assert d["proved"] and d["refined_proved"]
    else:
        assert all(r.status == "TOOL_UNAVAILABLE" for r in disco.results)                             # graceful, no fake proof
    assert "absolute" not in disco.markdown().lower().replace("not 'a new theorem'", "")              # never overclaims


def test_counterexample_cell_refinement_finds_non_positive_domain_splits():
    conj = m.Conjecture("x^2 >= x", claim_expr="x**2 >= x", variables={"x": (-5.0, 5.0)})

    def verifier(c):
        hyps = set(c.hypotheses)
        if "x <= 0" in hyps or "x >= 1" in hyps:
            return "FORMALLY_PROVED", None, "cell split closes the conjecture"
        return "FORMALLY_DISPROVED", {"x": "1/2"}, "middle cell is a counterexample"

    disco = m.discover_conjectures([conj], verifier=verifier)

    assert any(r.status == "FORMALLY_DISPROVED" and not r.refined_from for r in disco.results)
    assert any(r.status == "FORMALLY_PROVED" and "counterexample-cell" in r.statement
               for r in disco.results)
    assert all("x**2 >= x" in r.statement or "x^2 >= x" in r.statement for r in disco.results)


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
