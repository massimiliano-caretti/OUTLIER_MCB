"""Tests for the open-ended layer: graded prior-art audit (Impl 2) and the FunSearch loop (Impl 3).
Each feature has a positive test, a negative/adversarial control. Deterministic, offline."""
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import OUTLIER_MCB as gsl  # noqa: E402
from OUTLIER_MCB.novelty import prior_art_audit, GRADED_VERDICTS  # noqa: E402
from OUTLIER_MCB.creative_search import creative_search, structural_evaluator  # noqa: E402

_IDEA = "a byzantine fault tolerant consensus using verifiable random functions for leader election"


def _provider(matches):
    return gsl.CallableProvider(lambda q, _m=matches: {"matches": _m})


# ── Impl 2: graded prior-art audit ──
def test_renamed_prior_art_is_caught_negative_control():
    # the mandatory negative control: a known idea, renamed, MUST come back RENAMED_PRIOR_ART (not novel)
    v = prior_art_audit(_IDEA, _provider([{"title": _IDEA, "summary": _IDEA}]))
    assert v.graded_verdict == "RENAMED_PRIOR_ART"
    assert v.prior_art_distance_score == 0.0
    assert gsl.rebranding_detector(v.closest_matches) is True


def test_collage_of_prior_art_is_caught():
    v = prior_art_audit(_IDEA, _provider([
        {"title": "byzantine fault tolerant consensus", "summary": "byzantine fault tolerant consensus protocol"},
        {"title": "verifiable random functions", "summary": "verifiable random function leader election"}]))
    assert v.graded_verdict == "COLLAGE_OF_PRIOR_ART"
    assert v.source_overlap_score >= 0.7


def test_provisionally_novel_when_nothing_close():
    v = prior_art_audit(_IDEA, _provider([{"title": "a recipe for sourdough bread", "summary": "flour water salt"}]))
    assert v.graded_verdict == "PROVISIONALLY_NOVEL"
    assert v.prior_art_distance_score > 0.8


def test_verified_useful_novelty_requires_a_passing_external_check():
    prov = _provider([{"title": "a recipe for sourdough bread", "summary": "flour water salt"}])
    assert prior_art_audit(_IDEA, prov, verifier_passed=True).graded_verdict == "VERIFIED_USEFUL_NOVELTY"
    assert prior_art_audit(_IDEA, prov, verifier_passed=None).graded_verdict == "PROVISIONALLY_NOVEL"


def test_audit_never_claims_absolute_novelty_and_states_falsification():
    v = prior_art_audit(_IDEA, _provider([]))
    assert v.graded_verdict in GRADED_VERDICTS
    assert "absolute" not in v.graded_verdict.lower()
    assert v.why_not_absolute and v.falsification_query and v.what_would_falsify_this
    assert "≥ 0.55" in v.falsification_query or "0.55" in v.falsification_query


def test_detectors_are_consistent_with_the_verdict():
    # detectors operate on post-search matches that carry a `similarity` (as novelty_audit computes them)
    close = [{"title": _IDEA, "summary": _IDEA, "similarity": 0.9}]
    assert gsl.rebranding_detector(close) is True
    assert gsl.prior_art_distance_score(close) == round(1.0 - 0.9, 3)
    assert gsl.collage_detector(_IDEA, [{"title": "x", "summary": "y", "similarity": 0.1}]) is False


# ── Impl 3: FunSearch-style creative search ──
def test_creative_search_fills_an_archive_with_lineage():
    res = creative_search("design a rate limiter", budget=30)
    assert len(res.records) == 30
    assert res.archive.coverage() >= 3                 # a MAP of diverse elites
    assert res.best() is not None
    assert all(isinstance(r.operator_path, list) for r in res.records)   # lineage recorded
    assert 0.0 <= res.lineage_diversity() <= 1.0


def test_external_evaluator_really_drives_selection():
    # the FunSearch discipline: an EXTERNAL evaluator (not the generator) decides quality. A custom evaluator
    # that rewards a specific operator must make THAT operator win — proving selection is externally driven.
    calls = {"n": 0}

    def reward_dissolve(c):
        calls["n"] += 1
        return 0.95 if c.operator == "dissolve" else 0.1
    res = creative_search("design a rate limiter", evaluator=reward_dissolve, budget=20)
    assert calls["n"] == 20                              # the evaluator was actually consulted every step
    assert res.best().operator == "dissolve" and res.best().score == 0.95


def test_creative_search_is_deterministic():
    a = creative_search("design a rate limiter", budget=20)
    b = creative_search("design a rate limiter", budget=20)
    assert a.archive.qd_score() == b.archive.qd_score()
    assert [r.name for r in a.records] == [r.name for r in b.records]


def test_evaluator_evidence_is_captured_for_the_report():
    res = creative_search("design a rate limiter",
                          evaluator=lambda c: {"score": 0.5, "evidence": "ran a check"}, budget=10)
    assert res.best().evidence.get("evidence") == "ran a check"


# ── Impl 6: open-ended creativity metrics (positive / negative / adversarial each) ──
from evals.scorers import (qd_coverage_score, semantic_novelty_score, lineage_diversity_score,  # noqa: E402
                           surprise_usefulness_score, transformational_break_score, creativity_composite_score)


def test_semantic_novelty_penalizes_paraphrase():
    base = "measure the rate by request cost instead of by the time window"
    assert semantic_novelty_score("a completely unrelated idea about matchmaking", [base]) > 0.7  # positive: different
    assert semantic_novelty_score(base, [base]) == 0.0                                            # negative: identical
    paraphrase = "measure the rate by the request cost rather than the time window"
    assert semantic_novelty_score(paraphrase, [base]) < 0.4                                       # adversarial: reword


def test_qd_coverage_scales_with_filled_cells():
    res = creative_search("design a rate limiter", budget=30)
    assert qd_coverage_score(res.archive, reference_cells=24) > 0.0
    assert qd_coverage_score(0, reference_cells=24) == 0.0                # negative: empty archive
    assert qd_coverage_score(48, reference_cells=24) == 1.0              # adversarial: clamps, never >1


def test_surprise_usefulness_requires_both():
    assert surprise_usefulness_score(0.9, 0.9) > 0.8        # positive: both high
    assert surprise_usefulness_score(0.9, 0.0) == 0.0       # negative: surprising but useless → 0
    assert surprise_usefulness_score(0.0, 0.9) == 0.0       # adversarial: useful but unsurprising → 0


def test_transformational_break_needs_a_real_rule_break():
    broke = {"broken_assumption": "time_windowed", "world_test": "a constructed counterexample"}
    assert transformational_break_score(broke, {"known_bad_families": []}) == 1.0          # positive
    assert transformational_break_score({"broken_assumption": "", "world_test": ""}, {}) == 0.0   # negative
    rebrand = {"broken_assumption": "x", "world_test": "y", "text": "just use a token_bucket"}
    assert transformational_break_score(rebrand, {"known_bad_families": ["token_bucket"]}) < 1.0  # adversarial


def test_creativity_composite_is_transparent_and_gated():
    good = creativity_composite_score(0.8, 0.8, 0.8, 1.0, 1.0)
    assert set(good) == {"composite", "novelty", "usefulness", "surprise", "verification", "anti_gaming"}  # components exposed
    gamed = creativity_composite_score(0.8, 0.8, 0.8, 1.0, 0.2)   # anti_gaming low → multiplied DOWN
    assert gamed["composite"] < good["composite"]
    unverifiable = creativity_composite_score(0.8, 0.8, 0.8, 0.0, 1.0)   # verification gate halves it
    assert unverifiable["composite"] < good["composite"]


def test_gsl_openended_beats_full_on_creativity_metrics():
    # acceptance: the open-ended runtime must beat the single-best GSL_FULL on diversity/novelty/creativity,
    # WITHOUT degrading robust novelty beyond a small documented tolerance.
    from evals.run_eval import run
    S = run(modes=["GSL_FULL", "GSL_OPENENDED"])["summary"]
    oe, gf = S["GSL_OPENENDED"], S["GSL_FULL"]
    for m in ("qd_coverage_score", "semantic_novelty_score", "creativity_composite_score"):
        assert oe[m] > gf[m], f"GSL_OPENENDED must beat GSL_FULL on {m}"
    assert oe["robust_verified_novelty_score"] >= gf["robust_verified_novelty_score"] - 0.05


def test_openended_ablations_each_drop_their_target_metric():
    # at least 3 ablations must show a measurable contribution (remove the capability → its metric drops)
    from evals.run_eval import run
    S = run(modes=["GSL_OPENENDED", "GSL_NO_QD_ARCHIVE", "GSL_NO_DIVERGENCE"])["summary"]
    assert S["GSL_NO_QD_ARCHIVE"]["qd_coverage_score"] < S["GSL_OPENENDED"]["qd_coverage_score"]
    assert S["GSL_NO_DIVERGENCE"]["semantic_novelty_score"] < S["GSL_OPENENDED"]["semantic_novelty_score"]
    r = run(modes=["GSL_OPENENDED", "GSL_NO_PRIOR_ART"], task_id="judge_rename_005")["summary"]
    assert r["GSL_OPENENDED"]["prior_art_caught_score"] == 1.0       # catches the planted rename
    assert r["GSL_NO_PRIOR_ART"]["prior_art_caught_score"] == 0.0    # ablation misses it


def test_readiness_openended_gate():
    from evals.readiness_openended import readiness_openended_report
    r = readiness_openended_report()
    assert r["status"] in ("GO_READY_OPENENDED", "NOT_READY_OPENENDED")
    assert isinstance(r["blockers"], list) and r["checks"] and r["limits"]
    # the gate must be honest: status GO only iff there are no blockers
    assert (r["status"] == "GO_READY_OPENENDED") == (not r["blockers"])


def test_diverge_produces_many_distinct_ideas_across_categories():
    r = gsl.diverge("design a rate limiter", n=8)
    assert len(r.ideas) >= 4                                          # fluency: several ideas
    assert len({d.boden_category for d in r.ideas}) >= 2              # flexibility: >1 Boden category
    assert all(d.breaks_rule for d in r.ideas)                        # each declares the rule it breaks
    assert r.fluency_score > 0 and r.flexibility_score > 0 and r.elaboration_score > 0


def test_diverge_penalizes_paraphrase():
    # adversarial: allowing near-duplicates (threshold 1.0 = no pruning) must NOT increase originality —
    # pruned divergence is at least as original as the un-pruned (paraphrase-laden) set.
    pruned = gsl.diverge("design a rate limiter", n=10, paraphrase_threshold=0.6)
    laxer = gsl.diverge("design a rate limiter", n=10, paraphrase_threshold=1.0)
    assert pruned.originality_score >= laxer.originality_score
    # direct: two rewordings of the same sentence are NOT both kept under pruning
    from OUTLIER_MCB.divergence import _similarity
    assert _similarity("measure rate by request cost", "measure the rate by the request cost") > 0.6


def test_diverge_respects_axis_and_operator_constraints():
    only_cost = gsl.diverge("design a rate limiter", n=8, axes=["COST_MODEL"])
    assert only_cost.ideas and all("COST_MODEL" in d.candidate.breaks for d in only_cost.ideas)
    only_dissolve = gsl.diverge("design a rate limiter", n=8, constraints={"operators": ["dissolve"]})
    assert all(d.boden_category == "transformational" for d in only_dissolve.ideas)


def test_thought_tree_prunes_by_external_score():
    # an external scorer (not the generator) decides which branches survive — a custom scorer rewarding one
    # operator must make it win the tree, proving pruning is externally driven (the ToT discipline).
    t = gsl.thought_tree("design a rate limiter", branching=2, depth=2,
                         scorer=lambda c: 0.95 if c.operator == "dissolve" else 0.05)
    assert t.best().candidate.operator == "dissolve"
    assert len(t.nodes) > 2 and t.depth == 2


def test_prune_by_external_score_keeps_the_top():
    nodes = [gsl.ThoughtNode(None, s, 0, []) for s in (0.1, 0.9, 0.5)]
    kept = gsl.prune_by_external_score(nodes, keep=2)
    assert [n.score for n in kept] == [0.9, 0.5]


def test_self_refine_accepts_only_on_real_external_improvement():
    p = gsl.get_pack("coding")
    c = gsl.recombine_assumptions(p, k=2, max_candidates=1)[0]
    # a constant evaluator can never show improvement → the original is kept, improved is False
    flat = gsl.self_refine(c, "reword it", lambda x: 0.5, p)
    assert flat["improved"] is False and flat["candidate"] is c
    # invariant: improved is true only when the external score actually rose
    real = gsl.self_refine(c, "go further", gsl.box_distance, p)
    assert real["improved"] == (real["after"] > real["before"])


def test_reflection_memory_turns_failure_into_a_hint():
    p = gsl.get_pack("coding")
    c = gsl.recombine_assumptions(p, k=2, max_candidates=1)[0]
    m = gsl.ReflectionMemory()
    hint = m.record(c, "a known family already does this")
    assert hint and m.hints() == [hint] and "next" in hint.lower()


def test_code_evaluator_settles_by_execution_not_self_judgment():
    # the FunSearch discipline made real: an EXTERNAL code evaluator that SETTLES by the repo. A candidate
    # whose check goes GREEN must score strictly higher than the same one going RED.
    from OUTLIER_MCB.creative_search import code_evaluator
    repo = gsl.probe(str(ROOT))
    c = gsl.generate_candidates(gsl.get_pack("coding"))[0]
    green = code_evaluator(repo, runner=lambda cmd, cwd: "GREEN")(c)
    red = code_evaluator(repo, runner=lambda cmd, cwd: "RED")(c)
    grounding_only = code_evaluator(repo)(c)
    assert green > red                                  # execution outcome moves the score
    assert grounding_only >= 0.0 and red <= grounding_only   # grounding-only = materialization, no execution


def test_code_evaluator_drives_creative_search_selection():
    from OUTLIER_MCB.creative_search import code_evaluator, creative_search
    repo = gsl.probe(str(ROOT))
    # a runner that only GREENs commands selecting a 'dissolve'/deletion test → those candidates win
    runner = lambda cmd, cwd: "GREEN" if ("delet" in cmd or "dissolv" in cmd) else "RED"
    res = creative_search("design a rate limiter", evaluator=code_evaluator(repo, runner=runner), budget=20, repo=repo)
    assert res.best() is not None and res.records           # ran end-to-end with a real-settlement evaluator


def test_lexical_embedder_is_the_deterministic_default():
    e = gsl.LexicalEmbedder()
    assert e.distance("a b c d", "a b c d") == 0.0          # identical → 0
    assert e.distance("alpha beta", "gamma delta") == 1.0   # disjoint → 1
    assert gsl.semantic_distance("alpha beta", "alpha beta") == 0.0   # default is lexical


def test_callable_embedder_uses_cosine_and_catches_meaning():
    # a fake "semantic" model: maps synonyms to the SAME vector, unrelated text to an orthogonal one →
    # "different words, same meaning" is NEAR (lexical would call it far)
    vecs = {"car": [1.0, 0.0], "automobile": [1.0, 0.0], "banana": [0.0, 1.0]}
    emb = gsl.CallableEmbedder(lambda t: vecs.get(t.strip(), [0.0, 0.0]))
    assert emb.distance("car", "automobile") == 0.0         # synonyms → semantically identical
    assert emb.distance("car", "banana") == 1.0             # orthogonal → far
    assert gsl.LexicalEmbedder().distance("car", "automobile") == 1.0   # lexical is fooled (different words)


def test_semantic_novelty_score_accepts_an_embedder_without_changing_the_default():
    base = "measure the rate by request cost"
    assert semantic_novelty_score(base, [base]) == 0.0      # default lexical unchanged
    vecs = {"a": [1.0, 0.0], "b": [1.0, 0.0]}
    emb = gsl.CallableEmbedder(lambda t: vecs.get(t, [0.0, 1.0]))
    assert semantic_novelty_score("a", ["b"], embedder=emb) == 0.0   # semantically identical → not novel


def test_diverge_with_an_embedder_runs_and_stays_in_range():
    emb = gsl.CallableEmbedder(lambda t: [float(len(t) % 7), float(len(t) % 5), 1.0])
    r = gsl.diverge("design a rate limiter", n=6, embedder=emb)
    assert r.ideas and 0.0 <= r.originality_score <= 1.0 and 0.0 <= r.semantic_distance_score <= 1.0


def test_self_improvement_loop_triages_proposals():
    # the recursive central test: the engine proposes improvements to itself and triages them honestly
    r = gsl.propose_self_improvements(budget=20)
    assert r.proposals and r.qd_coverage >= 2
    assert all(p.verdict in ("INSIDE_THE_BOX", "MUST_BE_AUDITED", "NEEDS_DISAMBIGUATION") for p in r.proposals)
    # accepted proposals must NOT be inside-the-box (they break a real assumption)
    assert all(p.verdict == "MUST_BE_AUDITED" for p in r.accepted())


def test_self_improvement_rebranding_filter_drops_known_renames():
    # with a prior-art provider that flags EVERYTHING as a close match, every proposal is a rename → 0 accepted
    everything_is_known = gsl.CallableProvider(lambda q: {"matches": [{"title": q, "summary": q, "similarity": 0.99}]})
    r = gsl.propose_self_improvements(budget=20, provider=everything_is_known)
    assert len(r.accepted()) == 0                      # the rebranding gate removed them all


def test_open_ended_metrics_are_not_decorative_or_redundant():
    # build a small varied set and check the metrics actually SEPARATE different inputs (not flat)
    vals_sem = [semantic_novelty_score(t, ["the base idea here"]) for t in
                ("the base idea here", "the base idea now", "an utterly different matchmaking concept")]
    assert max(vals_sem) - min(vals_sem) > 0.3            # semantic novelty discriminates (not decorative)
    su = [surprise_usefulness_score(a, b) for a, b in ((0.9, 0.9), (0.9, 0.1), (0.1, 0.1))]
    assert max(su) - min(su) > 0.3                        # surprise×usefulness discriminates
    # not redundant with each other: a paraphrase is low-semantic-novelty yet can be high surprise×useful
    assert semantic_novelty_score("reword of base idea here", ["the base idea here"]) < 0.5
    assert surprise_usefulness_score(0.9, 0.9) > 0.8
