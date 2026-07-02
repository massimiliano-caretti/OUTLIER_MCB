"""test_evolution — the AlphaEvolve-useful core: objective evaluators, evolution memory, invention scoring,
baseline/parent comparison, the evolve loop, a verifiable task, and an auditable report. Deterministic.
"""
import OUTLIER_MCB as m
from OUTLIER_MCB.generators import Candidate


def _cand(name="c", breaks=None, assumptions=None, neg="claim"):
    return Candidate(name=name, operator="invert", breaks=breaks or ["X"],
                     assumptions=assumptions or ["a"], negation=neg)


# ── #2 evaluators ────────────────────────────────────────────────────────────────────────────────────
def test_callable_evaluator_threshold_and_passed_key():
    ev = m.CallableEvaluator(lambda c: {"score": 0.9, "controls_collapse": True}, passed_key="controls_collapse")
    r = ev.evaluate(_cand())
    assert r.passed and r.score == 0.9 and "controls_collapse" in r.components or r.components


def test_property_evaluator_all_or_fraction():
    ok = m.PropertyEvaluator([("p1", lambda c: True), ("p2", lambda c: True)])
    assert ok.evaluate(_cand()).passed
    half = m.PropertyEvaluator([("p1", lambda c: True), ("p2", lambda c: False)])
    r = half.evaluate(_cand())
    assert not r.passed and r.score == 0.5


def test_evaluator_internal_error_is_not_masked():
    def boom(c):
        raise RuntimeError("kaboom")
    r = m.CallableEvaluator(boom).evaluate(_cand())
    assert r.passed is False and r.score == 0.0 and "kaboom" in r.error


def test_composite_hard_correctness_gate():
    good_novelty = m.CallableEvaluator(lambda c: 0.95, name="nov", is_correctness=False)
    failing_correctness = m.CallableEvaluator(lambda c: {"score": 0.0, "ok": False}, name="correct",
                                              passed_key="ok", is_correctness=True)
    comp = m.CompositeEvaluator([good_novelty, failing_correctness])
    r = comp.evaluate(_cand())
    assert r.passed is False and r.score <= 0.25          # plausible-but-unverified cannot score high


def test_novelty_evaluator_propagates_scope():
    off = m.CompositePriorArtProvider([m.OfflinePriorArtProvider([{"title": "unrelated"}])])
    r = m.NoveltyEvaluator(off).evaluate(_cand(neg="a distributed rate limiter by request cost"))
    assert r.artifacts["novelty_scope"] == "LOCAL_ONLY"


# ── #1 evolution memory ──────────────────────────────────────────────────────────────────────────────
def test_memory_persistence_topk_lineage(tmp_path):
    mem = m.EvolutionMemory()
    a = m.EvolutionRecord(id="a", problem="p", candidate_name="A", claim="alpha topology", score=0.9,
                          evaluator_name="ev", correctness_passed=True)
    b = m.EvolutionRecord(id="b", problem="p", candidate_name="B", claim="beta spectral", score=0.5,
                          parent_ids=["a"], evaluator_name="ev", correctness_passed=True)
    mem.add(a); mem.add(b)
    assert [r.id for r in mem.top_k(2)] == ["a", "b"]     # ordered by score
    assert [r.id for r in mem.lineage("b")] == ["b", "a"] # child then ancestor
    path = str(tmp_path / "evo.jsonl")
    mem.save_jsonl(path)
    assert m.EvolutionMemory.load_jsonl(path).get("b").parent_ids == ["a"]


def test_dedupe_keeps_different_drops_near_duplicate():
    mem = m.EvolutionMemory()
    mem.add(m.EvolutionRecord(id="1", problem="p", candidate_name="interaction term couples inputs", claim="x"))
    mem.add(m.EvolutionRecord(id="2", problem="p", candidate_name="interaction term couples inputs", claim="x"))
    mem.add(m.EvolutionRecord(id="3", problem="p", candidate_name="a totally different latent confounder idea", claim="z"))
    removed = mem.dedupe_near_duplicates()
    assert removed == 1 and len(mem.records) == 2          # the genuine duplicate dropped, the different kept


def test_record_without_evaluator_is_not_verified():
    assert m.EvolutionRecord(id="x", problem="p", candidate_name="c", correctness_passed=True).verified is False
    assert m.EvolutionRecord(id="y", problem="p", candidate_name="c", evaluator_name="ev",
                             correctness_passed=True).verified is True


# ── #3 invention scoring with hard caps ───────────────────────────────────────────────────────────────
def test_correct_beats_incorrect():
    good = m.invention_score({"correctness": True, "usefulness_proxy": 0.9, "improvement_over_baseline": 0.5})["score"]
    bad = m.invention_score({"correctness": False, "usefulness_proxy": 0.9, "novelty_distance": 1.0})["score"]
    assert good > bad and bad <= 0.25


def test_local_only_novelty_is_capped():
    s = m.invention_score({"correctness": True, "novelty_distance": 1.0, "novelty_scope": "LOCAL_ONLY"})
    assert s["components"]["novelty"] <= 0.55
    online = m.invention_score({"correctness": True, "novelty_distance": 1.0,
                                "novelty_scope": "ONLINE_PRIOR_ART_CHECKED", "coverage_level": "STRONG"})
    assert online["components"]["novelty"] > s["components"]["novelty"]


def test_improvement_and_useless_difference():
    improved = m.invention_score({"correctness": True, "improvement_over_parent": 0.6})["score"]
    only_diff = m.invention_score({"correctness": True, "diversity": 0.9, "improvement_over_parent": 0.0,
                                   "usefulness_proxy": 0.0})["score"]
    assert improved > only_diff


# ── #7/#8/#4/#11 the evolve loop on a verifiable task, with baseline/parent + report ──────────────────
def test_evolve_invention_on_symbolic_task():
    task = m.symbolic_invention_task()
    res = m.evolve_invention(task["problem"], task["evaluator"], budget=14, pack=task["pack"])
    assert len(res.memory.records) <= 14                  # budget respected
    assert all(r.evaluator_name for r in res.memory.all())  # every candidate evaluated (none can win unevaluated)
    best = res.best()
    assert best is not None and best.verified             # the winner is verified
    assert "law_is_separable" in best.broken_assumptions  # it found the data-true break
    assert best.improvement_over_baseline > 0             # it beats the baseline box on the objective
    # auditable report: lineage + baseline + conservative statement, no absolute claims
    d = res.to_dict()
    assert d["baseline_score"] == res.baseline_score and d["best"]["lineage"]
    md = res.markdown().lower()
    assert "baseline" in md and "lineage" in md
    stmt = res.conservative_statement().lower()
    assert "never 'absolute novelty'" in stmt              # the honest disclaimer is present
    assert "verified" in stmt or "insufficient evidence" in stmt


# ── #13 evolution eval with ablations ────────────────────────────────────────────────────────────────
def test_evolution_eval_metrics_and_ablations():
    from evals.evolution_eval import run_evolution_eval
    rep = run_evolution_eval()
    mt = rep["metrics"]
    assert mt["evaluated_candidate_rate"] == 1.0          # every candidate is evaluated (none wins unevaluated)
    assert all(0.0 <= v <= 1.0 for v in mt.values() if isinstance(v, float))
    assert mt["best_verified"] and mt["best_beats_baseline"]
    assert rep["ablation_evaluator_gate"]["gate_earns_keep"] is True   # gate blocks high-but-unverified
    assert rep["ablation_prior_art"]["false_novelty_blocked"] is True  # a rebrand is blocked


# ── #12 CLI ──────────────────────────────────────────────────────────────────────────────────────────
def test_cli_evolve_task_and_report(capsys, tmp_path):
    from OUTLIER_MCB.cli import main
    out = str(tmp_path / "evo.jsonl")
    main(["evolve-task", "--budget", "10", "--memory-out", out])
    assert "Evolution report" in capsys.readouterr().out
    main(["evolution-report", "--memory", out])
    assert "Evolution memory" in capsys.readouterr().out


def test_causal_invention_task_is_settled_in_the_loop():
    # #8: causal discovery integrated into the evolve loop — only the confounder-adjustment break is confirmed.
    task = m.causal_invention_task()
    res = m.evolve_invention(task["problem"], task["evaluator"], budget=12, pack=task["pack"])
    best = res.best()
    assert best is not None and best.verified
    assert "association_is_direct" in best.broken_assumptions   # correlation ≠ causation, settled by data


# ── fix A: only an EXTERNAL resolver may confer 'verified' (the engine never judges itself) ────────────
def test_external_resolver_certifies_internal_score_does_not():
    from OUTLIER_MCB.evaluators.base import CallableEvaluator
    # an INTERNAL score: passes its correctness gate but is NOT an external resolver
    internal = CallableEvaluator(lambda c: {"score": 0.9, "ok": True}, name="internal_score", passed_key="ok")
    res = m.evolve_invention("invent something", internal, budget=8, pack=m.get_pack("coding"))
    b = res.best()
    assert b.verified is True                          # legacy gate: an evaluator ran and passed
    assert b.externally_settled is False               # but self-judgment cannot certify
    assert res.externally_settled is False and res.settled_best() is None
    assert "NOT externally certified" in res.conservative_statement()


def test_external_resolver_path_is_certified():
    task = m.symbolic_invention_task()                 # settles by held-out DATA → an external resolver
    res = m.evolve_invention(task["problem"], task["evaluator"], budget=12, pack=task["pack"])
    b = res.best()
    assert b.externally_settled and b.external_resolver == "symbolic"
    assert res.settled_best() is not None
    assert "VERIFIED by external resolver" in res.conservative_statement()


def test_red_team_and_hidden_are_external_resolvers():
    from OUTLIER_MCB.evaluators.hidden import HiddenEvaluator
    assert HiddenEvaluator(lambda c, x: True, public_cases=[1]).settles_externally is True
    assert m.RedTeamEvaluator([]).settles_externally is True
    # a plain property/internal evaluator is NOT external by default
    assert m.PropertyEvaluator([("p", lambda c: True)]).settles_externally is False


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
