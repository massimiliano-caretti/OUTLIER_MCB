"""readiness — an objective GO / NO_GO gate for a 1.0 release.

The rule: do NOT call it 1.0 because the unit tests pass. Call it 1.0 only when an EXTERNAL evaluation
shows OUTLIER_MCB beats simple baselines, the built-in packs are strong, no operator is inert, and the
packaging is real. `readiness_report()` runs those checks and returns a status with explicit blockers.

Collaborators: evals.run_eval (the external comparison), health (inert operators), pack_quality, the pyproject.
"""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path
from typing import Dict

PACK_QUALITY_MIN = 0.80
ROUTING_MIN = 0.75
CALIBRATION_MIN = 0.75


def _pyproject_ok(root: Path):
    pp = root / "pyproject.toml"
    if not pp.exists():
        return False, "pyproject.toml missing"
    t = pp.read_text()
    name = 'name = "OUTLIER_MCB"' in t
    script = 'OUTLIER_MCB = "OUTLIER_MCB.cli:main"' in t
    version = 'OUTLIER_MCB.__version__' in t
    return (name and version), f"name={name} version_attr={version} console_script={script}"


def readiness_report(run_tests: bool = False, repo_path: str = None) -> Dict:
    """Run every 1.0 gate. `run_tests=True` also runs `pytest -q` in a subprocess (CLI use; off by
    default to avoid recursion inside the test suite). Returns status + blockers + warnings + metrics."""
    import OUTLIER_MCB as gsl
    root = Path(repo_path).resolve() if repo_path else Path(gsl.__file__).resolve().parent.parent

    checks: Dict[str, Dict] = {}
    metrics: Dict = {}
    report_warnings: list = []

    def req(name, passed, detail=""):
        checks[name] = {"passed": bool(passed), "required": True, "detail": detail}

    def warn(name, passed, detail=""):
        checks[name] = {"passed": bool(passed), "required": False, "detail": detail}

    # packaging
    ok, detail = _pyproject_ok(root)
    req("pyproject_valid", ok, detail)
    req("console_script_present", 'OUTLIER_MCB = "OUTLIER_MCB.cli:main"' in (root / "pyproject.toml").read_text()
        if (root / "pyproject.toml").exists() else False)

    # public API documented
    req("public_api_documented", bool(getattr(gsl, "__all__", [])), f"{len(getattr(gsl, '__all__', []))} symbols")

    # health: no inert operator
    h = gsl.health()
    req("no_inert_operator", not getattr(h, "inert_operators", []), f"inert={getattr(h, 'inert_operators', [])}")

    # built-in pack quality
    pq = {n: gsl.pack_quality(gsl.get_pack(n))["overall"] for n in ("coding", "math")}
    metrics["pack_quality"] = pq
    req("pack_quality_builtin", all(v >= PACK_QUALITY_MIN for v in pq.values()), f">= {PACK_QUALITY_MIN}: {pq}")

    # external evaluation
    eval_ok = (root / "evals" / "tasks.jsonl").exists()
    req("eval_harness_exists", eval_ok)
    if eval_ok:
        try:
            sys.path.insert(0, str(root))
            from evals.run_eval import run as run_eval
            from evals.baselines import MODES
            res = run_eval(repo_path=str(root))
            s = res["summary"]
            req("all_baselines_run", set(s) == set(MODES), f"{sorted(s)}")
            req("all_scorers_in_range",
                all(0.0 <= v <= 1.0 for m in s.values() for v in m.values()),
                "every scorer in [0,1]")
            full, base, check = (s["GSL_FULL"], s["BASE_PROMPT"], s["CHECKLIST_PROMPT"])
            metrics["vns"] = {m: s[m]["verified_novelty_score"] for m in s}
            metrics["artifact_specificity"] = {m: s[m]["artifact_specificity"] for m in s}
            metrics["routing_accuracy_full"] = full["routing_accuracy"]
            req("gsl_full_beats_base_vns", full["verified_novelty_score"] > base["verified_novelty_score"],
                f"FULL {full['verified_novelty_score']} vs BASE {base['verified_novelty_score']}")
            req("gsl_full_not_worse_than_checklist",
                full["verified_novelty_score"] >= check["verified_novelty_score"],
                f"FULL {full['verified_novelty_score']} vs CHECKLIST {check['verified_novelty_score']}")
            req("artifact_specificity_full_gt_base",
                full["artifact_specificity"] > base["artifact_specificity"],
                f"FULL {full['artifact_specificity']} vs BASE {base['artifact_specificity']}")
            req("routing_accuracy_ge_min", full["routing_accuracy"] >= ROUTING_MIN,
                f"{full['routing_accuracy']} >= {ROUTING_MIN}")

            # ── anti-fake-rigor gates (this round) ──
            metrics["robust_vns_full"] = res["robust_vns_full"]
            metrics["ablation_contribution"] = res["ablation_contribution"]
            metrics["full_beats_n_ablations"] = res["full_beats_n_ablations"]
            req("robust_vns_full_gt_base", res["robust_vns_full"] > base["verified_novelty_score"],
                f"robust {res['robust_vns_full']} vs base {base['verified_novelty_score']}")
            req("anti_gaming_full_ge_checklist",
                full["anti_gaming_score"] >= check["anti_gaming_score"],
                f"FULL {full['anti_gaming_score']} vs CHECKLIST {check['anti_gaming_score']}")
            req("calibration_honesty_ge_min", full["calibration_honesty_score"] >= CALIBRATION_MIN,
                f"{full['calibration_honesty_score']} >= {CALIBRATION_MIN}")
            req("full_beats_two_ablations", res["full_beats_n_ablations"] >= 2,
                f"beats {res['full_beats_n_ablations']}/4")
            req("artifact_drop_when_no_artifact",
                full["artifact_specificity"] > s["GSL_NO_ARTIFACT"]["artifact_specificity"],
                f"FULL {full['artifact_specificity']} vs NO_ARTIFACT {s['GSL_NO_ARTIFACT']['artifact_specificity']}")
            report_warnings.extend(res.get("warnings", []))
            req("readiness_declares_limits", bool(res.get("warnings")), f"{len(res.get('warnings', []))} limits declared")
            # honest, non-self-congratulatory finding surfaced as a WARNING (not a blocker):
            warn("ablation_contribution_is_meaningful", res["ablation_contribution"] >= 0.02,
                 f"contribution {res['ablation_contribution']} — the full stack barely beats its best ablation "
                 f"({max(res['ablation_summary'], key=res['ablation_summary'].get) if res['ablation_summary'] else '—'}); "
                 f"that capability adds little MEASURABLE structural value on this dataset")
            if res["ablation_contribution"] < 0.02:
                report_warnings.append(
                    "ablation_contribution ≈ 0: GSL_FULL does not clearly beat its best partial (an ablation); the "
                    "marginal value of the full stack over a strong subset is NOT demonstrated by these metrics here")

            # ── META-evaluation: is the eval ITSELF trustworthy? (this round's new layer) ──
            from evals.diagnostics import diagnostics_report
            diag = diagnostics_report(res["rows"])
            metrics["diagnostics"] = diag["metrics"]
            req("eval_is_trustworthy", diag["trustworthy"],
                f"win_rate {diag['metrics']['win_rate_full_vs_base']}, effect_size "
                f"{diag['metrics']['effect_size_full_vs_base']}, adversarial_gap {diag['metrics']['adversarial_gap']}")
            for f in diag["findings"]:
                report_warnings.append("eval diagnostic: " + f)
        except Exception as exc:                       # an eval that cannot run is a blocker, not a silent pass
            req("eval_runs", False, f"{type(exc).__name__}: {exc}")

    if run_tests:
        try:
            r = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=str(root),
                               capture_output=True, text=True, timeout=600)
            req("pytest_passes", r.returncode == 0, (r.stdout + r.stderr).strip().splitlines()[-1] if r.stdout else "")
        except Exception as exc:
            req("pytest_passes", False, str(exc))
    else:
        warn("pytest_passes", True, "not run here — run `python -m pytest -q` separately")

    blockers = [n for n, c in checks.items() if c["required"] and not c["passed"]]
    warnings = [n for n, c in checks.items() if not c["required"] and not c["passed"]]
    return {"status": "GO_READY" if not blockers else "NO_GO",
            "blockers": blockers, "warnings": warnings, "limits": report_warnings,
            "checks": checks, "metrics": metrics}


def markdown(report: Dict) -> str:
    lines = [f"# Readiness — {report['status']}", ""]
    if report["blockers"]:
        lines += ["## Blockers (must fix for 1.0)"] + [f"- {b}: {report['checks'][b]['detail']}" for b in report["blockers"]] + [""]
    lines.append("## Checks")
    for name, c in report["checks"].items():
        mark = "✅" if c["passed"] else ("❌" if c["required"] else "⚠")
        lines.append(f"- {mark} {name}  {c['detail']}")
    if report.get("limits"):
        lines += ["", "## Declared limits (honest scope)"] + [f"- {x}" for x in report["limits"]]
    return "\n".join(lines)
