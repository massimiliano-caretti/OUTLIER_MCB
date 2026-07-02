"""test_proposals_remaining — proposals #6, #9, #10, #3, #8, #5.

#6 continuous synergy · #9 cached AssumptionGraph · #10 graded information boundary ·
#3 SUSPENDED_BOLD signal boost · #8 Mermaid graph in creative() · #5 iterative elicitation.
Every change is additive / opt-in; the non-regression is the full suite staying green.
"""
import copy

import OUTLIER_MCB as gsl
from OUTLIER_MCB.core import Assumption


# ── #6: continuous synergy ──────────────────────────────────────────────────────────────────────────
def test_synergy_score_is_a_normalized_margin():
    assert gsl.synergy_score(1.0, [0.4, 0.5]) == 0.5      # (1.0 - 0.5) / 1.0
    assert gsl.synergy_score(0.5, [0.5]) == 0.0           # a mere sum, no amplification
    assert gsl.synergy_score(0.5, []) == 0.0


def test_novelty_score_rescue_is_proportional():
    low = gsl.novelty_score(["A"], reduces_to="fam", synergy=0.1)
    high = gsl.novelty_score(["A"], reduces_to="fam", synergy=0.9)
    assert high["score"] > low["score"]                   # a stronger collage is rescued more
    assert low["components"]["synergistic_collage"] and high["components"]["synergistic_collage"]


# ── #9: cached AssumptionGraph ──────────────────────────────────────────────────────────────────────
def test_graph_of_is_cached_and_self_invalidating():
    pack = gsl.get_pack("numeric")
    g1 = gsl.graph_of(pack)
    assert gsl.graph_of(pack) is g1                       # cache hit: same object
    p2 = copy.copy(pack)
    p2.assumptions = list(pack.assumptions) + [Assumption("extra", "d", "w", "f", ["fam"], "kill it well now")]
    p2.dimension_of = dict(pack.dimension_of)
    g2 = gsl.graph_of(p2)
    assert g2 is not g1 and "extra" in g2.nodes           # fingerprint changed → rebuilt, not stale


# ── #10: graded information boundary ────────────────────────────────────────────────────────────────
def test_missing_information_is_graded():
    pack = gsl.get_pack("numeric")
    rep = gsl.detect_missing_information("discover a scientific law from data", pack)
    crits = {d["criticality"] for d in rep.needed_information}
    assert "CRITICAL" in crits                            # a high-priority break's data is CRITICAL
    assert rep.by_criticality("CRITICAL")
    assert rep.roadmap()[0]["criticality"] == "CRITICAL"  # roadmap orders critical-first
    assert any(d["kind"] == rep.recommended_first and d["criticality"] == "CRITICAL"
               for d in rep.needed_information)


# ── #3: SUSPENDED_BOLD signal boost ─────────────────────────────────────────────────────────────────
def test_suspended_bold_gets_a_testability_request():
    pack = gsl.get_pack("numeric")
    j = gsl.judge("an irreducible interaction term carries the signal", prompt="numeric law",
                  pack=pack, assumption="law_is_separable")
    assert j.status == "SUSPENDED_BOLD"                   # breaks an axis, no executable world-test yet
    assert j.testability_request is not None
    assert "SIGNAL-BOOST" in j.next_step
    assert "interaction_terms" in (j.dossier.maturity.what_would_make_it_testable or "")


# ── #8: Mermaid graph ───────────────────────────────────────────────────────────────────────────────
def test_mermaid_renders_the_graph():
    g = gsl.graph_of(gsl.get_pack("numeric"))
    m = g.mermaid()
    assert m.startswith("flowchart TD")
    assert "n0[" in m and "-->" in m


def test_creative_diagram_is_opt_in():
    base = gsl.creative("discover a scientific law from data")
    withd = gsl.creative("discover a scientific law from data", diagram=True)
    assert "```mermaid" not in base                       # default brief unchanged
    assert "```mermaid" in withd


# ── #5: iterative elicitation ───────────────────────────────────────────────────────────────────────
_WEAK = {
    "name": "probe", "keywords": ["probe"], "box_name": "box",
    "assumptions": [{"name": "a1", "description": "x", "why_obvious": "y", "if_false": "z",
                     "assumed_by": ["fam"], "falsifier": "no", "axis": "X"}],
    "axes": {"X": {"priority": 3, "verdict": "v"}, "Y": {"priority": 2, "verdict": "v"}},   # Y uncovered
    "known_families": ["fam"], "info_kinds": {}, "relations": [],
}
_STRONG = {
    "name": "probe", "keywords": ["probe"], "box_name": "box",
    "assumptions": [
        {"name": "a1", "description": "x", "why_obvious": "y", "if_false": "z", "assumed_by": ["fam"],
         "falsifier": "a construction where the family provably fails here", "axis": "X"},
        {"name": "a2", "description": "x", "why_obvious": "y", "if_false": "z", "assumed_by": ["fam"],
         "falsifier": "another construction where it clearly fails now", "axis": "Y"},
        {"name": "a3", "description": "x", "why_obvious": "y", "if_false": "z", "assumed_by": ["fam"],
         "falsifier": "third concrete falsifier with enough words here", "axis": "X"},
        {"name": "a4", "description": "x", "why_obvious": "y", "if_false": "z", "assumed_by": ["fam"],
         "falsifier": "fourth concrete falsifier with several words too", "axis": "Y"}],
    "axes": {"X": {"priority": 3, "verdict": "v"}, "Y": {"priority": 2, "verdict": "v"}},
    "known_families": ["fam", "fam2"], "info_kinds": {"i1": "why", "i2": "why2"},
    "relations": [["a1", "depends_on", "a2", "n"], ["a3", "implies", "a4", "n"],
                  ["a2", "blocks", "a1", "n"], ["a4", "depends_on", "a3", "n"]],
}


class _Provider:
    def __init__(self, specs):
        self.specs = specs
        self.calls = 0

    def __call__(self, request):
        spec = self.specs[min(self.calls, len(self.specs) - 1)]
        self.calls += 1
        return spec


def test_iterative_elicit_converges_when_gaps_are_closed():
    res = gsl.iterative_elicit("probe", _Provider([_WEAK, _STRONG]), threshold=0.6, max_rounds=3)
    assert res["converged"] is True
    assert res["quality"] >= 0.6
    assert res["rounds"] == 2                             # weak (below) → strong (converges)
    assert res["history"][0]["quality"] < res["history"][1]["quality"]


def test_iterative_elicit_stops_after_max_rounds_if_stuck():
    res = gsl.iterative_elicit("probe", _Provider([_WEAK]), threshold=0.6, max_rounds=3)
    assert res["converged"] is False
    assert len(res["history"]) == 3                       # tried, generated follow-ups, never reached the bar


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
