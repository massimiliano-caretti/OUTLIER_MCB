"""test_math_frontier — the math toward-objective loop composes frontier_search + sub-lemmas + solution-form
pivot, honestly (Tier-1 wiring of two orphans). Deterministic and offline.
"""
import OUTLIER_MCB as gsl


def test_math_frontier_pivots_when_nothing_certified():
    # with no real resolver, sub-lemma stubs settle to UNKNOWN → nothing advances → the objective PIVOTS
    # to the next weaker-but-real form instead of collapsing to a bare conjecture.
    pack = gsl.get_pack("math")
    res = gsl.math_frontier("prove a closed form for a(n)", pack, current_form="CLOSED_FORM")
    assert res.advanced is False
    assert res.pivot is not None and res.pivot.pivoted
    assert res.pivot.to_form == "LINEAR_RECURRENCE"          # the next real form down the lattice
    assert res.report is not None and res.report.next_levers  # failed lemmas are kept as next levers, not lost


def test_math_frontier_advances_with_a_real_resolver():
    # a resolver that certifies any candidate → the frontier advances and does NOT pivot (the strong form held).
    pack = gsl.get_pack("math")
    from OUTLIER_MCB.certificates import Certificate
    from OUTLIER_MCB.frontier_search import propose_sublemmas

    def resolver(candidate):
        return Certificate(status="Z3_PROVED", detail="stub resolver")     # status in EXTERNAL_CERTIFICATES

    cands = propose_sublemmas(pack, k=2)
    for c in cands:
        c.value = 1.0                                        # a real improvement to record on the ledger
    res = gsl.math_frontier("prove a bound", pack, resolver=resolver, candidates=cands, current_form="CLOSED_FORM")
    assert res.advanced is True and res.pivot is None        # certified advance → no pivot needed


def test_math_frontier_markdown_is_honest():
    pack = gsl.get_pack("math")
    md = gsl.math_frontier("prove a closed form", pack).markdown()
    assert "Math frontier" in md and "pivot the objective" in md.lower() or "conjecture" in md.lower()
