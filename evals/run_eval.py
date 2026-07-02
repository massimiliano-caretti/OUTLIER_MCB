"""evals.run_eval — run every baseline on the frozen tasks, score, print a repeatable table.

    python -m evals.run_eval
    python -m evals.run_eval --mode GSL_FULL
    python -m evals.run_eval --json

Deterministic: same tasks + same code → same numbers. The headline check: GSL_FULL beats BASE_PROMPT on
mean verified_novelty_score over the included dataset.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_tasks():
    return [json.loads(line) for line in (HERE / "tasks.jsonl").read_text().splitlines() if line.strip()]


def run(modes=None, repo_path: str = None, task_id: str = None) -> dict:
    from evals.baselines import MODES
    from evals.scorers import score_output
    repo_path = repo_path or str(HERE.parent)
    modes = modes or list(MODES)
    tasks = [t for t in load_tasks() if (task_id is None or t["id"] == task_id)]
    from evals.scorers import primary_score
    rows, agg = [], {m: {} for m in modes}
    for task in tasks:
        for mode in modes:
            out = MODES[mode](task, repo_path)
            scores = score_output(out, task)
            scores["primary_score"] = primary_score(out, task)   # task-type-aware objective
            rows.append({"task": task["id"], "mode": mode, **scores})
            for k, v in scores.items():
                agg[mode].setdefault(k, []).append(v)
    from evals.baselines import ABLATION_MODES
    summary = {m: {k: round(sum(v) / len(v), 3) for k, v in metrics.items()} for m, metrics in agg.items()}

    def vns(mode):
        return summary.get(mode, {}).get("verified_novelty_score", 0.0)

    def primary(mode):
        # the headline objective: judge a generative task by novelty, a judgment task by judgment accuracy.
        return summary.get(mode, {}).get("primary_score", 0.0)

    base, full = primary("BASE_PROMPT"), primary("GSL_FULL")
    full_rvns = summary.get("GSL_FULL", {}).get("robust_verified_novelty_score", 0.0)
    ablations_present = [m for m in ABLATION_MODES if m in summary]
    best_ablation = max((primary(m) for m in ablations_present), default=0.0)
    ablation_contribution = round(max(0.0, min(1.0, full - best_ablation)), 3)
    full_beats_n_ablations = sum(1 for m in ablations_present if full > primary(m))
    judge_contribution = round(primary("GSL_FULL") - primary("GSL_NO_JUDGE"), 3)
    robust_vns_full = round(min(1.0, full_rvns + 0.10 * ablation_contribution), 3)
    warnings = [
        "baselines (BASE_PROMPT/CHECKLIST) are deterministic stand-ins, NOT a real LLM — this is not a model-in-the-loop comparison",
        "scorers measure STRUCTURE (falsifiable/distinct/grounded/honest), NOT human-judged value",
    ]
    ablation_summary = {m: primary(m) for m in ablations_present}
    return {"rows": rows, "summary": summary, "n_tasks": len(tasks),
            "gsl_full_beats_base": full > base,
            "ablation_contribution": ablation_contribution, "robust_vns_full": robust_vns_full,
            "full_beats_n_ablations": full_beats_n_ablations, "ablation_summary": ablation_summary,
            "judge_contribution": judge_contribution,
            "primary_summary": {m: primary(m) for m in modes},
            "warnings": warnings}


def _table(result: dict) -> str:
    cols = [("PRIMARY", "primary_score"), ("VNS", "verified_novelty_score"),
            ("RVNS", "robust_verified_novelty_score"), ("CALIB", "calibration_honesty_score"),
            ("MATERIAL", "materialization_score"), ("JUDGE_ACC", "judgment_accuracy_score")]
    head = f"{'MODE':<24}{'TASKS':<7}" + "".join(f"{label:<11}" for label, _ in cols)
    lines = [head]
    for mode, metrics in result["summary"].items():
        row = f"{mode:<24}{result['n_tasks']:<7}" + "".join(f"{metrics.get(key, 0.0):<11.2f}" for _, key in cols)
        lines.append(row)
    lines += ["",
              f"ablation_contribution = {result.get('ablation_contribution')}  "
              f"(GSL_FULL primary − best ablation; how much the full stack adds)",
              f"judge_contribution = {result.get('judge_contribution')}  "
              f"(GSL_FULL primary − GSL_NO_JUDGE primary; >0 means judge earns its keep)",
              f"robust_vns_full = {result.get('robust_vns_full')}  ·  "
              f"GSL_FULL beats {result.get('full_beats_n_ablations')}/4 ablations on the primary objective  ·  "
              f"beats BASE: {result['gsl_full_beats_base']}",
              "warnings: " + "; ".join(result.get("warnings", []))]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="evals.run_eval")
    ap.add_argument("--mode", help="run only one mode")
    ap.add_argument("--task", help="run only one task id")
    ap.add_argument("--json", action="store_true", help="print raw JSON")
    ap.add_argument("--diagnostics", action="store_true", help="meta-evaluate the eval itself")
    args = ap.parse_args(argv)
    result = run(modes=[args.mode] if args.mode else None, task_id=args.task)
    if args.diagnostics:
        from evals.diagnostics import diagnostics_report
        diag = diagnostics_report(result["rows"])
        print(json.dumps(diag, indent=2))
        return
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(_table(result))
    out = HERE / "reports"
    out.mkdir(exist_ok=True)
    (out / "report.json").write_text(json.dumps(result, indent=2))
    (out / "report.md").write_text("```\n" + _table(result) + "\n```\n")


if __name__ == "__main__":
    main()
