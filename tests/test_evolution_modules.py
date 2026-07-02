"""test_evolution_modules — the 4 modules: evolution_ops (#6), prompt_sampler (#5), unknown_space (#9),
self_evolve (#10). Deterministic, offline, no file writes.
"""
import OUTLIER_MCB as m
from OUTLIER_MCB.generators import Candidate, invert_assumption


def _numeric():
    return m.get_pack("numeric")


def _parent():
    return invert_assumption(_numeric(), "law_is_separable")


# ── #6 evolution operators ────────────────────────────────────────────────────────────────────────────
def test_operators_track_provenance_and_change_content():
    pack = _numeric()
    par = _parent()
    r = m.mutate_assumption(pack, par, parent_id="p0")
    assert r and r.parent_ids == ["p0"] and r.candidate.assumptions != par.assumptions   # a different axis
    mech = m.mutate_mechanism(pack, par, parent_id="p0")
    assert mech and mech.candidate.operator != par.operator                              # different mechanism, not name
    assert mech.rationale and mech.expected_change and mech.risk


def test_recombine_distant_uses_two_domains():
    r = m.recombine_distant(_numeric(), None, parent_ids=["a", "b"])
    assert r and r.mutation_operator == "recombine_distant"
    assert {x.split("@")[1] for x in r.candidate.assumptions} == {"numeric", "causal"} or len(r.candidate.assumptions) == 2


def test_novelty_push_picks_farthest_from_box():
    from OUTLIER_MCB.invent import box_distance
    pack = _numeric()
    r = m.novelty_push(pack, _parent(), parent_id="p0")
    plain = invert_assumption(pack, "law_is_smooth")
    assert r and box_distance(r.candidate, pack) >= box_distance(plain, pack)


# ── #5 prompt sampler ─────────────────────────────────────────────────────────────────────────────────
def test_prompt_contains_objective_unexplored_failures_and_rules():
    mem = m.EvolutionMemory()
    mem.add(m.EvolutionRecord(id="f1", problem="P", candidate_name="failed_x",
                              broken_assumptions=["law_is_separable"], correctness_passed=False))
    ps = m.PromptSampler(_numeric(), memory=mem, evaluator_objective="held-out residual on the data")
    prompt = ps.sample("P", strategy="explore_unknown_axis", prior_art_warnings=["resembles a known GAM"])
    assert "held-out residual on the data" in prompt                 # evaluator objective
    assert "law_is_smooth" in prompt                                 # an unexplored assumption is offered
    assert "failed_x" in prompt                                      # recent failure surfaced
    assert "collage" in prompt.lower() and "rename" in prompt.lower()  # forbids rebrand/collage
    assert "falsif" in prompt.lower()                                # requires a falsifier


# ── #9 unknown space ──────────────────────────────────────────────────────────────────────────────────
def test_unexplored_detected_and_saturated_handled():
    pack = _numeric()
    mem = m.EvolutionMemory()
    # law_is_separable explored & failed twice ⇒ saturated; others unexplored
    for i in range(2):
        mem.add(m.EvolutionRecord(id=f"r{i}", problem="P", candidate_name=f"c{i}",
                                  broken_assumptions=["law_is_separable"], correctness_passed=False))
    unexp = m.unexplored_assumptions(pack, mem, "P")
    assert "law_is_smooth" in unexp and "law_is_separable" not in unexp
    region = m.suggest_unknown_region("P", mem, pack)
    assert "law_is_separable" in region.saturated_assumptions and region.why
    recs = m.recommend_next_mutations(mem, pack, "P")
    assert any(x["operator"] == "mutate_mechanism" and x["target"] == "law_is_separable" for x in recs)  # change mechanism, not retry
    assert all(x.get("why") for x in recs)


def test_novelty_frontier_prefers_diverse_valid():
    mem = m.EvolutionMemory()
    mem.add(m.EvolutionRecord(id="a", problem="P", candidate_name="interaction coupling term", claim="x",
                              correctness_passed=True, score=0.9))
    mem.add(m.EvolutionRecord(id="b", problem="P", candidate_name="interaction coupling term", claim="x",
                              correctness_passed=True, score=0.8))   # near-duplicate of a
    mem.add(m.EvolutionRecord(id="c", problem="P", candidate_name="latent confounder adjustment idea", claim="z",
                              correctness_passed=True, score=0.7))
    front = m.novelty_frontier(mem, k=5, problem="P")
    ids = {r.id for r in front}
    assert "a" in ids and "c" in ids and "b" not in ids             # diverse kept, near-duplicate dropped


# ── #10 self evolve (dry-run, safe) ───────────────────────────────────────────────────────────────────
def test_self_evolve_dry_run_records_nothing_applied():
    res = m.self_evolve("OUTLIER_MCB/scoring.py", budget=4, dry_run=True)
    assert res.dry_run is True and res.applied == []                # nothing applied
    assert res.memory.all() and all(not r.verified for r in res.memory.all())  # unverified hypotheses only
    assert all(r.score <= 0.25 for r in res.memory.all())          # correctness-gated (not a win)
    d = res.to_dict()
    assert "DRY-RUN" in d["statement"] and d["best"]["lineage"]


def test_invalid_patch_is_rejected():
    ok, errs = m.validate_improvement_patch(
        "--- a/../../etc/passwd\n+++ b/../../etc/passwd\n@@ -1 +1 @@\n-x\n+y\n", repo_root=".")
    assert ok is False and errs                                     # path traversal refused before any apply


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
