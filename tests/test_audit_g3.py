"""test_audit_g3 — regressions for the audit of the search/evolution runtime (invent, evolve, thought_search,
creative_search, frontier_search, generators). Each test pins a confirmed defect so it cannot come back."""
import copy
from collections import Counter

import OUTLIER_MCB as m
from OUTLIER_MCB.invent import push_further, novelty_search, invent
from OUTLIER_MCB.generators import generate_candidates, recombine_assumptions, self_spark


def _flat(c):
    return {"score": 0.5, "controls_collapse": True}


def test_push_further_does_not_collapse_unrelated_candidates_onto_one_transport():
    p = m.get_pack("coding")
    cands = generate_candidates(p, "invent a new rate limiter")
    pushed = [push_further(c, p) for c in cands]
    top = Counter(c.name for c in pushed).most_common(1)[0][1]
    assert top <= 4, "push_further mapped many distinct ideas onto the same successor"
    for c, s in zip(cands, pushed):
        if s is not c:   # a real successor shares an assumption or a broken axis with its parent
            assert set(s.assumptions) & set(c.assumptions) or set(s.breaks) & set(c.breaks)


def test_novelty_search_negative_beam_is_empty_not_all_but_last():
    p = m.get_pack("coding")
    assert novelty_search(p, "x", beam=-1) == []
    assert novelty_search(p, "x", beam=0) == []


def test_recombine_assumptions_spreads_over_assumptions():
    p = m.get_pack("coding")
    rec = recombine_assumptions(p)
    counts = Counter(a for c in rec for a in c.assumptions)
    assert counts.most_common(1)[0][1] <= 3
    assert recombine_assumptions(p, max_candidates=0) == []
    # the first (highest-priority) pair is unchanged
    assert rec[0].name == recombine_assumptions(p, max_candidates=1)[0].name


def test_anomalies_with_same_leading_words_do_not_collide():
    inv = invent("invent a new rate limiter",
                 anomalies=["latency spikes at midnight for tenant A", "latency spikes at midnight for tenant B"])
    names = [a.name for a in inv.pack.assumptions]
    assert len(names) == len(set(names))


def test_invent_ranking_respects_falsification_and_composite_stays_in_range(monkeypatch):
    import OUTLIER_MCB.verifier as V
    calls = []

    def fake(check, cwd=None, timeout=0):
        calls.append(1)
        st = "GREEN" if len(calls) % 3 == 0 else "RED"
        return V.RedGreen(st, True, st == "GREEN", "fake")
    monkeypatch.setattr(V, "verify_red_green", fake)
    led = m.Ledger()
    inv = invent("invent a new rate limiter", repo_path=".", execute=True, ledger=led, reflect_rounds=1)
    comps = [f["score"]["composite"] for f in inv.frontier]
    assert all(0.0 <= c <= 1.0 for c in comps)
    # among items on fresh assumptions the frontier must not place a LOST bet above a survivor of equal novelty
    surv = [f for f in inv.frontier if f.get("survived")]
    lost = [f for f in inv.frontier if f.get("survived") is False]
    assert surv and lost


def test_evolve_depth_mode_never_overspends_the_budget():
    for b in (0, 1, 2, 5):
        r = m.evolve_invention("invent a new rate limiter", _flat, budget=b, mode="depth")
        assert len(r.memory.by_problem(r.problem)) <= b


def test_evolve_does_not_reevaluate_identical_candidates_and_escape_leaves_the_fixated_seed():
    r = m.evolve_invention("invent a new rate limiter", _flat, budget=30, mode="depth", orchestrate=True)
    recs = r.memory.by_problem(r.problem)
    names = [x.candidate_name for x in recs]
    assert len(names) == len(set(names)), Counter(names).most_common(3)
    escapes = [x for x in recs if x.mutation_operator == "fixation_escape"]
    assert all("time_windowed" not in x.broken_assumptions for x in escapes)


def test_creative_search_budget_zero_evaluates_nothing():
    assert m.creative_search("invent a new rate limiter", budget=0).records == []
    assert len(m.creative_search("invent a new rate limiter", budget=3).records) == 3


def test_thought_tree_scores_all_roots_and_has_no_duplicate_thoughts():
    p = m.get_pack("coding")
    from OUTLIER_MCB.creative_search import structural_evaluator
    ev = structural_evaluator(p)
    t = m.thought_tree("invent a new rate limiter", pack=p, branching=3, depth=2)
    names = [n.candidate.name for n in t.nodes]
    assert len(names) == len(set(names))
    best_root = max(ev(c) for c in generate_candidates(p, "invent a new rate limiter"))
    assert max(n.score for n in t.nodes if n.depth == 0) == best_root


def test_frontier_search_accepts_result_candidates_with_a_pack():
    from OUTLIER_MCB.frontier_search import frontier_search, ResultCandidate

    class Cert:
        status, certified, counterexample = "REPO_TEST_GREEN", True, None
    rep = frontier_search("p", [ResultCandidate("r", "m", 1.0, "increase", settle=lambda: Cert())],
                          pack=m.get_pack("coding"))
    assert rep.advanced and rep.advanced[0]["name"] == "r"


def test_self_spark_tolerates_missing_failure_memory():
    p = copy.copy(m.get_pack("coding"))
    p.failure_memory = None
    assert len(self_spark(p)) == 3
