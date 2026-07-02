"""diagnostics — META-metrics: measure whether the EVAL ITSELF is trustworthy, not just the ideas.

A green eval suite and a high mean VNS can still hide fake rigor: a metric that gives everyone the same
score (decorative), two metrics that say the same thing (fake breadth), a mean carried by one task, a win
that vanishes under a tiny weight change, a metric that does not drop when the output is degraded, or a
gamed output that scores high. These functions measure exactly those failure modes — derived by applying
OUTLIER_MCB to its own eval (every one broke an explicit assumption about eval trust). Pure-Python,
deterministic, no randomness.
"""
from __future__ import annotations
from statistics import pstdev, mean
from typing import Dict, List

CORE_METRICS = ["verified_novelty_score", "robust_verified_novelty_score", "anti_gaming_score",
                "calibration_honesty_score", "artifact_specificity", "routing_accuracy",
                "falsifiability_score", "materialization_score"]


def _by_mode(rows: List[Dict], metric: str) -> Dict[str, List[float]]:
    out: Dict[str, List[float]] = {}
    for r in rows:
        out.setdefault(r["mode"], []).append(r.get(metric, 0.0))
    return out


def _pearson(xs: List[float], ys: List[float]) -> float:
    if len(xs) < 2:
        return 0.0
    mx, my = mean(xs), mean(ys)
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    den = (sum((a - mx) ** 2 for a in xs) * sum((b - my) ** 2 for b in ys)) ** 0.5
    return round(num / den, 3) if den else 0.0


# 1 — a metric that gives every mode the same value is decorative
def discriminative_power(rows: List[Dict], metric: str) -> float:
    mode_means = [mean(v) for v in _by_mode(rows, metric).values() if v]
    return round(pstdev(mode_means), 3) if len(mode_means) > 1 else 0.0


def decorative_metrics(rows: List[Dict], threshold: float = 0.03) -> List[str]:
    return [m for m in CORE_METRICS if discriminative_power(rows, m) < threshold]


# 2 — two metrics perfectly correlated add fake breadth
def metric_redundancy(rows: List[Dict], threshold: float = 0.97) -> List[tuple]:
    redundant = []
    for i, a in enumerate(CORE_METRICS):
        for b in CORE_METRICS[i + 1:]:
            xa = [r.get(a, 0.0) for r in rows]
            xb = [r.get(b, 0.0) for r in rows]
            if abs(_pearson(xa, xb)) >= threshold:
                redundant.append((a, b, _pearson(xa, xb)))
    return redundant


# 3 — a mean can be carried by a few tasks; how OFTEN does A beat B per task?
def per_task_win_rate(rows: List[Dict], a: str, b: str, metric: str = "verified_novelty_score") -> float:
    by_task = {}
    for r in rows:
        if r["mode"] in (a, b):
            by_task.setdefault(r["task"], {})[r["mode"]] = r.get(metric, 0.0)
    wins = [1 for t in by_task.values() if a in t and b in t and t[a] > t[b]]
    n = sum(1 for t in by_task.values() if a in t and b in t)
    return round(len(wins) / n, 3) if n else 0.0


# 4 — a tiny gap with high variance is noise: standardized effect size
def effect_size(rows: List[Dict], a: str, b: str, metric: str = "verified_novelty_score") -> float:
    va = [r.get(metric, 0.0) for r in rows if r["mode"] == a]
    vb = [r.get(metric, 0.0) for r in rows if r["mode"] == b]
    if not va or not vb:
        return 0.0
    pooled = ((pstdev(va) ** 2 + pstdev(vb) ** 2) / 2) ** 0.5
    return round((mean(va) - mean(vb)) / pooled, 3) if pooled else (999.0 if mean(va) > mean(vb) else 0.0)


# 5 — does GSL_FULL stay on top under perturbed VNS weightings? (fixed perturbations, deterministic)
_PERTURBED = [
    {"verified_novelty_score": 1.0},
    {"falsifiability_score": 1.0}, {"artifact_specificity": 1.0},
    {"routing_accuracy": 1.0}, {"auto_verifiability": 1.0},
]


def ranking_stability(rows: List[Dict], top: str = "GSL_FULL", against=("BASE_PROMPT", "CHECKLIST_PROMPT")) -> float:
    stable = 0
    for w in _PERTURBED:
        def score(mode):
            mm = _by_mode(rows, list(w)[0])
            return mean(mm.get(mode, [0.0]))
        if all(score(top) >= score(o) for o in against):
            stable += 1
    return round(stable / len(_PERTURBED), 3)


# 6 — degrading an output MUST lower its score, or the metric is broken
def metric_monotonicity(rows: List[Dict] = None) -> bool:
    from evals.scorers import verified_novelty_score
    task = {"expected_pack": "coding", "allowed_generic": False, "known_bad_families": []}
    full = {"broken_assumption": "time_windowed", "world_test": "a world where cost decides", "pack": "coding",
            "negative_control": "shuffle cost", "verifiability": "AUTO",
            "artifact_contract": {"target": "t.py", "test_name": "test_x", "baseline_assertion": "red",
                                  "negative_control": "shuffle", "success_condition": "green",
                                  "grounded": True, "full_contract": True},
            "candidate_count": 3, "unique_candidate_count": 3}
    degraded = dict(full, world_test="", artifact_contract={}, verifiability="HUMAN")
    return verified_novelty_score(degraded, task) < verified_novelty_score(full, task)


# 7 — a deliberately gamed output: how high can it score? (low robust score = the metric resists it)
def adversarial_gap(rows: List[Dict] = None) -> float:
    from evals.scorers import robust_verified_novelty_score, verified_novelty_score
    task = {"expected_pack": "coding", "allowed_generic": False, "known_bad_families": []}
    gamed = {"text": "this is verified and proven and certified " * 60, "pack": "coding",
             "broken_assumption": "some unspecified assumption", "world_test": "a world-test", "negative_control": "",
             "artifact_contract": {"target": "TODO", "test_name": "test", "baseline_assertion": "...",
                                   "negative_control": "thing", "success_condition": "generic"},
             "verifiability": "AUTO", "candidate_count": 12, "unique_candidate_count": 2}
    # gap = naive VNS it claims minus the robust score the honesty gates allow. Large gap = metric caught the gaming.
    return round(verified_novelty_score(gamed, task) - robust_verified_novelty_score(gamed, task), 3)


# 8 — if every task gets the same VNS the eval carries no information
def eval_informativeness(rows: List[Dict], mode: str = "GSL_FULL", metric: str = "verified_novelty_score") -> float:
    vals = [r.get(metric, 0.0) for r in rows if r["mode"] == mode]
    return round(pstdev(vals), 3) if len(vals) > 1 else 0.0


# 9 — does the engine correctly REFUSE to call conceptual claims AUTO?
def negative_control_pass_rate(rows: List[Dict], mode: str = "GSL_FULL") -> float:
    nc = [r for r in rows if r["task"].startswith("negative_control") and r["mode"] == mode]
    if not nc:
        return 1.0
    # a passed negative control means the engine did NOT inflate it (no auto_verifiability)
    return round(sum(1 for r in nc if r.get("auto_verifiability", 0.0) < 1.0) / len(nc), 3)


# 10 — aggregate: is the eval itself trustworthy enough to certify a release?
def diagnostics_report(rows: List[Dict] = None) -> Dict:
    if rows is None:
        from evals.run_eval import run
        rows = run()["rows"]
    decorative = decorative_metrics(rows)
    redundant = metric_redundancy(rows)
    win = per_task_win_rate(rows, "GSL_FULL", "BASE_PROMPT")
    eff = effect_size(rows, "GSL_FULL", "BASE_PROMPT")
    stability = ranking_stability(rows)
    info = eval_informativeness(rows)
    ncpr = negative_control_pass_rate(rows)
    mono = metric_monotonicity(rows)
    adv = adversarial_gap(rows)
    findings = []
    if decorative:
        findings.append(f"decorative metrics (no discriminative power): {decorative}")
    if redundant:
        findings.append(f"redundant metric pairs (r≥0.97): {[(a, b) for a, b, _ in redundant]}")
    if win < 0.5:
        findings.append(f"GSL_FULL wins only {win} of tasks vs BASE — the mean may be carried by a few")
    if not mono:
        findings.append("a core metric is NON-monotonic: degrading an output does not lower its score")
    trustworthy = (not decorative_in_core(decorative)) and win >= 0.5 and mono and ncpr >= 1.0 and stability >= 0.6
    trust = overall_trust_score(decorative, redundant, win, stability, ncpr, mono, info)
    return {"trustworthy": bool(trustworthy), "overall_trust_score": trust, "findings": findings,
            "metrics": {"win_rate_full_vs_base": win, "effect_size_full_vs_base": eff,
                        "ranking_stability": stability, "eval_informativeness": info,
                        "negative_control_pass_rate": ncpr, "monotonicity_ok": mono,
                        "adversarial_gap": adv, "overall_trust_score": trust,
                        "decorative_metrics": decorative,
                        "redundant_pairs": [(a, b) for a, b, _ in redundant]}}


def overall_trust_score(decorative, redundant, win, stability, ncpr, mono, info) -> float:
    """A single, TRANSPARENT aggregate of the eval's health in [0,1] — the simpler acceptance signal a
    self-improvement loop can compare before/after a patch (accept only if THIS does not drop and
    trustworthiness holds). Components exposed, never hidden; a hard-blocking failure (a decorative CORE
    metric, a non-monotonic metric, a failed negative control) halves the score so it can never look healthy."""
    hard_ok = (not decorative_in_core(decorative)) and mono and ncpr >= 1.0
    soft = (0.30 * min(1.0, win / 0.75)                       # wins broadly, not carried by a few tasks
            + 0.25 * min(1.0, stability)                      # robust under metric reweighting
            + 0.20 * (1.0 - min(1.0, len(redundant) / 3.0))   # few redundant metric pairs
            + 0.15 * (1.0 - min(1.0, len(decorative) / 3.0))  # few decorative metrics
            + 0.10 * min(1.0, info / 0.1))                    # the eval carries information across tasks
    return round(soft if hard_ok else 0.5 * soft, 3)


def decorative_in_core(decorative: List[str]) -> bool:
    """A decorative VNS or robust score is disqualifying; a decorative secondary metric is only a finding."""
    return any(m in ("verified_novelty_score", "robust_verified_novelty_score") for m in decorative)
