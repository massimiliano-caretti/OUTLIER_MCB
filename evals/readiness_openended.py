"""evals.readiness_openended — the GO_READY_OPENENDED gate.

A separate, stricter gate than OUTLIER_MCB.readiness: it certifies the OPEN-ENDED engine, not just the
structural one. It can declare GO_READY_OPENENDED only when every check below passes — otherwise it returns
NOT_READY_OPENENDED with the concrete blockers. Honest by construction: it runs the real eval and reads the
real numbers; it never hard-codes a pass.

    python -m evals.readiness_openended
"""
from __future__ import annotations
from typing import Dict

TOLERANCE = 0.05   # documented: GSL_OPENENDED's robust_vns may sit at most this far below GSL_FULL's


def readiness_openended_report() -> Dict:
    from evals.run_eval import run
    from evals.baselines import OPENENDED_ABLATIONS
    from evals.diagnostics import diagnostics_report
    import OUTLIER_MCB as gsl

    full = run()                      # all modes, all tasks
    S = full["summary"]
    oe, gf = S["GSL_OPENENDED"], S["GSL_FULL"]

    new_metrics = ["qd_coverage_score", "semantic_novelty_score", "creativity_composite_score"]
    beats = {m: (oe[m] > gf[m]) for m in new_metrics}

    # ablations: each must drop the metric it targets, vs GSL_OPENENDED
    drops = {
        "GSL_NO_QD_ARCHIVE": S["GSL_NO_QD_ARCHIVE"]["qd_coverage_score"] < oe["qd_coverage_score"],
        "GSL_NO_DIVERGENCE": S["GSL_NO_DIVERGENCE"]["semantic_novelty_score"] < oe["semantic_novelty_score"],
        "GSL_NO_PRIOR_ART": S["GSL_NO_PRIOR_ART"]["prior_art_caught_score"] < oe["prior_art_caught_score"],
    }
    ablations_with_value = sum(1 for v in drops.values() if v)

    d = diagnostics_report(full["rows"])
    # prior-art audit catches a planted rename (negative control), via the library directly (deterministic)
    renamed = gsl.prior_art_audit("a known idea", gsl.CallableProvider(
        lambda q: {"matches": [{"title": "a known idea", "summary": "a known idea exactly"}]})).graded_verdict

    # LLM-in-the-loop acceptance: the loop mode (fake LLM, real materialization) beats GSL_FULL on executable
    # evidence GSL_FULL cannot produce (LLM calls, RED→GREEN, materialization, coverage, anti-rebrand).
    ll = S.get("GSL_LLM_LOOP_FAKE", {})
    llm_metrics = ["materialization_score", "llm_call_count_score", "red_green_score", "qd_coverage_score", "anti_rebrand_score"]
    llm_beats = bool(ll) and all(ll.get(m, 0) > gf.get(m, 0) for m in llm_metrics)

    checks = {
        "llm_loop_beats_full_on_executable_evidence": llm_beats,
        "openended_beats_full_on_qd_coverage": beats["qd_coverage_score"],
        "openended_beats_full_on_semantic_novelty": beats["semantic_novelty_score"],
        "openended_beats_full_on_creativity_composite": beats["creativity_composite_score"],
        "robust_vns_not_degraded_beyond_tolerance": oe["robust_verified_novelty_score"] >= gf["robust_verified_novelty_score"] - TOLERANCE,
        "at_least_3_ablations_show_value": ablations_with_value >= 3,
        "no_decorative_core_metrics": not d["metrics"]["decorative_metrics"],
        "eval_trustworthy": d["trustworthy"],
        "prior_art_catches_rename": renamed == "RENAMED_PRIOR_ART",
        "no_absolute_novelty_claim": all("absolute" not in v.lower() for v in gsl.GRADED_VERDICTS),
    }
    blockers = [k for k, v in checks.items() if not v]
    status = "GO_READY_OPENENDED" if not blockers else "NOT_READY_OPENENDED"
    return {"status": status, "checks": checks, "blockers": blockers,
            "evidence": {"openended": {m: oe[m] for m in new_metrics + ["robust_verified_novelty_score"]},
                         "full": {m: gf[m] for m in new_metrics + ["robust_verified_novelty_score"]},
                         "ablation_drops": drops, "ablations_with_value": ablations_with_value,
                         "tolerance": TOLERANCE},
            "limits": ["the DEFAULT distance is a lexical proxy; inject an embeddings.CallableEmbedder for real semantic distance",
                       "creative_search uses a structural default evaluator unless a code/test evaluator is wired",
                       "GSL_LLM_LOOP_FAKE uses a deterministic FAKE LLM (real materialization run once); a real "
                       "provider's quality is only as good as the model you wire in",
                       "the dataset is small; absolute scores are not human-judged value"]}


def main():
    import json
    r = readiness_openended_report()
    print(f"=== {r['status']} ===")
    for k, v in r["checks"].items():
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")
    if r["blockers"]:
        print("\nblockers:", r["blockers"])
    print("\nevidence:", json.dumps(r["evidence"], indent=2))


if __name__ == "__main__":
    main()
