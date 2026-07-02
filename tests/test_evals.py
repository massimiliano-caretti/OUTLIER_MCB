"""Tests for the eval harness — deterministic, offline, no LLM. Run: python -m pytest -q."""
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest                                  # noqa: E402
from evals.baselines import MODES             # noqa: E402
from evals.scorers import SCORERS, score_output  # noqa: E402
from evals.run_eval import run, load_tasks    # noqa: E402

REQUIRED_TASK_FIELDS = ("id", "domain", "prompt", "expected_pack", "known_bad_families",
                        "must_have", "success_oracle")
STD_FIELDS = ("mode", "task_id", "text", "pack", "broken_assumption", "world_test", "negative_control",
              "artifact_contract", "candidate_count", "unique_candidate_count", "verifiability", "score_components")


def test_tasks_jsonl_is_valid_and_complete():
    tasks = load_tasks()
    assert 10 <= len(tasks) <= 45
    for t in tasks:
        for f in REQUIRED_TASK_FIELDS:
            assert f in t, f"task {t.get('id')} missing {f}"


@pytest.mark.parametrize("mode", list(MODES))
def test_every_baseline_returns_standardized_output(mode):
    task = load_tasks()[0]
    out = MODES[mode](task, str(ROOT))
    assert all(f in out for f in STD_FIELDS)
    assert out["mode"] == mode and out["task_id"] == task["id"]


def test_every_scorer_returns_a_unit_interval_value():
    tasks = load_tasks()
    for task in tasks:
        for mode in MODES:
            out = MODES[mode](task, str(ROOT))
            for name, value in score_output(out, task).items():
                assert 0.0 <= value <= 1.0, f"{name} out of [0,1] for {mode}/{task['id']}: {value}"


def test_run_eval_produces_all_modes():
    result = run()
    assert set(result["summary"]) == set(MODES)
    assert result["n_tasks"] == len(load_tasks())


def test_gsl_full_beats_base_prompt_on_mean_vns():
    result = run()
    full = result["summary"]["GSL_FULL"]["verified_novelty_score"]
    base = result["summary"]["BASE_PROMPT"]["verified_novelty_score"]
    assert full > base, f"GSL_FULL ({full}) must beat BASE_PROMPT ({base}) on the included dataset"


def test_gsl_beats_base_on_falsifiability():
    s = run()["summary"]
    assert max(s["GSL_PREFLIGHT"]["falsifiability_score"], s["GSL_FULL"]["falsifiability_score"]) \
        > s["BASE_PROMPT"]["falsifiability_score"]


def test_every_baseline_declares_a_verifiability_class():
    task = load_tasks()[0]
    for mode in MODES:
        assert MODES[mode](task, str(ROOT))["verifiability"] in ("AUTO", "HUMAN", "NONE")


def test_gsl_artifact_specificity_at_least_base():
    s = run()["summary"]
    assert max(s["GSL_PREFLIGHT"]["artifact_specificity"], s["GSL_FULL"]["artifact_specificity"]) \
        >= s["BASE_PROMPT"]["artifact_specificity"]


def test_eval_is_deterministic():
    assert run()["summary"] == run()["summary"]      # same tasks + code → identical numbers


# ── anti-fake-rigor metrics (this round) ─────────────────────────────────────────────────────────────
from evals.scorers import (anti_gaming_score, calibration_honesty_score,  # noqa: E402
                           robust_verified_novelty_score, verified_novelty_score)
from evals.baselines import ABLATION_MODES                                # noqa: E402


def test_anti_gaming_penalizes_placeholders_and_inflated_claims():
    gamed = {"text": "this is verified and proven", "broken_assumption": "some unspecified assumption",
             "world_test": "a world-test", "negative_control": "",
             "artifact_contract": {"target": "TODO", "test_name": "test", "baseline_assertion": "...",
                                   "negative_control": "thing", "success_condition": "generic"},
             "verifiability": "HUMAN", "candidate_count": 10, "unique_candidate_count": 2}
    honest = {"text": "measure the rate by cost", "broken_assumption": "time_windowed",
              "world_test": "a world where cost decides", "negative_control": "shuffle the cost structure",
              "artifact_contract": {"target": "tests/test_x.py", "test_name": "test_cost_rate",
                                    "baseline_assertion": "red today", "negative_control": "shuffle cost → fails",
                                    "success_condition": "green", "grounded": True, "full_contract": True},
              "verifiability": "AUTO", "candidate_count": 5, "unique_candidate_count": 5}
    assert anti_gaming_score(gamed) < 0.5 < anti_gaming_score(honest)


def test_calibration_penalizes_false_auto_and_unbacked_certainty():
    false_auto = {"verifiability": "AUTO", "artifact_contract": {}, "text": "", "world_test": ""}
    proven_human = {"verifiability": "HUMAN", "artifact_contract": {}, "text": "this is proven and certified", "world_test": ""}
    assert calibration_honesty_score(false_auto) < 1.0 and calibration_honesty_score(proven_human) < 1.0


def test_all_ablation_baselines_run():
    s = run()["summary"]
    assert all(m in s for m in ABLATION_MODES)


def test_gsl_full_beats_at_least_two_ablations():
    r = run()
    assert r["full_beats_n_ablations"] >= 2


def test_robust_vns_stays_in_unit_interval():
    for row in run()["rows"]:
        assert 0.0 <= row["robust_verified_novelty_score"] <= 1.0


def test_run_eval_reports_the_new_metrics():
    s = run()["summary"]["GSL_FULL"]
    assert {"robust_verified_novelty_score", "anti_gaming_score", "calibration_honesty_score"} <= set(s)


def test_negative_control_task_is_not_auto():
    from evals.baselines import gsl_full
    nc = next(t for t in load_tasks() if t["id"] == "negative_control_001")
    out = gsl_full(nc, str(ROOT))
    assert out["verifiability"] != "AUTO"            # a purely conceptual claim must admit HUMAN, not AUTO


def test_metric_invariance_cosmetic_bloat_does_not_raise_the_score():
    # the green_star move: renaming/padding content without substance must NOT improve the robust score
    base = {"text": "measure the rate by cost", "broken_assumption": "time_windowed",
            "world_test": "a world where cost decides", "negative_control": "shuffle the cost structure",
            "artifact_contract": {"target": "t.py", "test_name": "test_x", "baseline_assertion": "red",
                                  "negative_control": "shuffle", "success_condition": "green",
                                  "grounded": True, "full_contract": True},
            "verifiability": "AUTO", "candidate_count": 3, "unique_candidate_count": 3}
    task = {"expected_pack": "coding", "allowed_generic": False, "known_bad_families": []}
    bloated = dict(base, text=base["text"] + " " + ("filler " * 400))   # cosmetic verbosity, no new substance
    assert robust_verified_novelty_score(bloated, task) <= robust_verified_novelty_score(base, task)


# ── meta-evaluation: is the eval ITSELF trustworthy? (this round) ────────────────────────────────────
from evals.diagnostics import (diagnostics_report, discriminative_power, decorative_metrics,  # noqa: E402
                               metric_redundancy, per_task_win_rate, effect_size, metric_monotonicity,
                               adversarial_gap, eval_informativeness, negative_control_pass_rate)


def _rows():
    return run()["rows"]


def test_diagnostics_can_detect_a_decorative_metric():
    # the meta-metric must catch a metric with the same value for every mode (zero discriminative power).
    # We inject a synthetic flat metric to prove the detector works, WITHOUT asserting any real metric is
    # decorative — calibration is no longer flat now that the OVERCLAIM control exercises it (see below).
    rows = [dict(r, _flat=0.5) for r in _rows()]
    from evals.diagnostics import discriminative_power
    assert discriminative_power(rows, "_flat") < 0.03                # a constant metric IS flagged decorative
    assert discriminative_power(rows, "verified_novelty_score") > 0.05   # VNS genuinely separates modes


def test_calibration_is_no_longer_decorative():
    # P2 fixed: the OVERCLAIM_PROMPT control (a dishonest mode) makes calibration_honesty_score vary across
    # modes, so it now carries real discriminative power and is NOT flagged decorative.
    rows = _rows()
    assert discriminative_power(rows, "calibration_honesty_score") > 0.03
    assert "calibration_honesty_score" not in decorative_metrics(rows)


def test_vns_and_robust_vns_are_no_longer_redundant():
    # P3 fixed: with the adversarial/dishonest tasks+mode, the honesty gates pull RVNS away from VNS, so the
    # pair is no longer near-identical (pearson < 0.97) and is NOT flagged redundant.
    pairs = metric_redundancy(_rows())
    names = {(a, b) for a, b, _ in pairs}
    assert ("verified_novelty_score", "robust_verified_novelty_score") not in names


def test_win_rate_and_effect_size_back_the_mean():
    rows = _rows()
    assert per_task_win_rate(rows, "GSL_FULL", "BASE_PROMPT") >= 0.75   # not carried by a few tasks
    assert effect_size(rows, "GSL_FULL", "BASE_PROMPT") > 0.8           # a real separation, not noise


def test_metric_is_monotonic_under_degradation():
    assert metric_monotonicity() is True               # removing the world-test must lower the score


def test_adversarial_gap_is_caught():
    assert adversarial_gap() > 0.3      # a gamed output's naive VNS is far above its robust score (honesty gates bite)


def test_negative_control_is_never_auto_in_aggregate():
    assert negative_control_pass_rate(_rows()) >= 1.0


def test_eval_is_informative_across_tasks():
    assert eval_informativeness(_rows()) > 0.05        # tasks differ — the eval carries information


def test_diagnostics_report_is_self_consistent():
    d = diagnostics_report(_rows())
    assert isinstance(d["trustworthy"], bool) and "win_rate_full_vs_base" in d["metrics"]


def test_overall_trust_score_aggregates_health_and_zeroes_on_hard_failures():
    # a single transparent acceptance signal in [0,1]; a decorative CORE metric (a hard failure) must halve it
    from evals.diagnostics import overall_trust_score
    d = diagnostics_report(_rows())
    assert 0.0 <= d["overall_trust_score"] <= 1.0 and d["overall_trust_score"] == d["metrics"]["overall_trust_score"]
    healthy = overall_trust_score([], [], 1.0, 1.0, 1.0, True, 0.2)
    hard_fail = overall_trust_score(["verified_novelty_score"], [], 1.0, 1.0, 1.0, True, 0.2)
    assert healthy > hard_fail                      # a decorative core metric is penalized, never hidden


def test_judge_earns_its_keep_on_the_primary_objective():
    # P1 fixed: scored on the TASK-TYPE-AWARE objective (judgment accuracy on human-idea tasks, not generative
    # novelty), judge() adds measurable value — GSL_FULL now beats GSL_NO_JUDGE, the finding that started this.
    r = run()
    assert r["judge_contribution"] > 0.0
    assert r["primary_summary"]["GSL_FULL"] > r["primary_summary"]["GSL_NO_JUDGE"]
    assert r["full_beats_n_ablations"] >= 3          # GSL_FULL now beats most/all ablations on the objective


def test_judgment_accuracy_rewards_the_correct_verdict_only():
    from evals.scorers import judgment_accuracy_score
    task = {"expected_verdict": "INSIDE_THE_BOX"}
    right = {"score_components": {"verdict": "INSIDE_THE_BOX"}}
    wrong = {"score_components": {"verdict": "MUST_BE_AUDITED"}}
    none = {"score_components": {}}                  # a mode that produces no verdict (e.g. preflight)
    assert judgment_accuracy_score(right, task) == 1.0
    assert judgment_accuracy_score(wrong, task) == 0.0
    assert judgment_accuracy_score(none, task) == 0.0
    assert judgment_accuracy_score(right, {}) == 1.0    # vacuous on a non-judgment task (never distorts ranking)


def test_judge_classifies_every_adversarial_task_correctly():
    # the five human-idea task types the contributor asked for: inside-box, audit, inflated, disambiguation, rename
    from evals.baselines import gsl_full
    from evals.scorers import judgment_accuracy_score
    for t in load_tasks():
        if t.get("expected_verdict"):
            out = gsl_full(t, str(ROOT))
            assert judgment_accuracy_score(out, t) >= 0.7, f"judge mis-handled {t['id']}"


def test_materialization_is_independent_of_artifact_specificity():
    # P4: a field-complete contract (artifact_specificity = 1.0) can still be poorly materialized — its
    # command runs the whole suite, or its target/test do not really exist red-first. The two must diverge.
    import OUTLIER_MCB as gsl
    from evals.scorers import artifact_specificity
    field_complete = {"artifact_contract": {"target": "does/not/exist.py", "test_name": "test_x",
                                            "baseline_assertion": "red", "negative_control": "shuffle",
                                            "success_condition": "green"}}
    assert artifact_specificity(field_complete) == 1.0                       # all fields present
    ev = gsl.materialization_evidence(field_complete["artifact_contract"], str(ROOT))
    assert ev["target_exists"] is False                                      # but the target is not real
    assert gsl.materialization_score(field_complete["artifact_contract"], str(ROOT)) < 1.0


def test_overclaim_control_is_punished_by_the_honesty_gates():
    # the dishonest baseline must look worse than honest ones EXACTLY where honesty is measured
    s = run()["summary"]
    assert s["OVERCLAIM_PROMPT"]["calibration_honesty_score"] < s["GSL_PREFLIGHT"]["calibration_honesty_score"]
    assert s["OVERCLAIM_PROMPT"]["robust_verified_novelty_score"] < s["OVERCLAIM_PROMPT"]["verified_novelty_score"]


def test_llm_benchmark_plumbing_runs_offline_and_refuses_without_a_model():
    # P5 scaffold: the model-in-the-loop harness must run end-to-end with a fake model (prompt→judge→score)
    # AND refuse to fabricate a result when no model is supplied.
    from evals.llm_benchmark import run_llm_benchmark, FakeLLM, ARMS
    r = run_llm_benchmark(FakeLLM(), tasks=load_tasks()[:3])
    assert set(r["summary"]) == set(ARMS)
    for arm in ARMS:
        assert 0.0 <= r["summary"][arm]["primary_score"] <= 1.0
    with pytest.raises(ValueError):
        run_llm_benchmark(None)


def test_assistant_in_the_loop_scoring_credits_a_falsifiable_answer():
    # no API: the model-in-the-loop scorer must be TEXT-AWARE — an answer that states a world-test, a
    # baseline and a negative control scores MORE falsifiable than a bare one. Uses canned strings as a
    # stand-in for two real model answers (the real workflow pastes the editor's answers in the same shape).
    from evals.llm_benchmark import score_completions
    tid = "coding_rate_limiter_001"
    bare = "Use a per-tenant token bucket. It is the standard approach."
    falsifiable = ("Break tenant_independent: a coupled max-min limiter over active tenants. World-test: "
                   "construct a 2-tenant workload where one is idle; it must beat the per-tenant baseline. "
                   "Negative control: shuffle the coupling and the gain must collapse to the baseline.")
    res = score_completions({tid: {"llm_only": bare, "llm_greenstar": falsifiable}})
    assert res["summary"]["llm_greenstar"]["falsifiability_score"] > res["summary"]["llm_only"]["falsifiability_score"]


def test_readiness_includes_the_anti_fake_rigor_checks():
    import OUTLIER_MCB as gsl
    checks = gsl.readiness_report()["checks"]
    for name in ("robust_vns_full_gt_base", "anti_gaming_full_ge_checklist", "calibration_honesty_ge_min",
                 "full_beats_two_ablations", "artifact_drop_when_no_artifact", "readiness_declares_limits"):
        assert name in checks
