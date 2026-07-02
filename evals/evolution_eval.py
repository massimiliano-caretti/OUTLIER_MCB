"""evolution_eval — does the evolutionary invention loop actually invent, and do its guards earn their keep?

Measures, on the verifiable symbolic task (known ground truth), whether the loop produces evaluated,
baseline-beating, honestly-scoped candidates — and ablates the two guards the spec cares about most: the
EVALUATOR gate (without it, unverified candidates look verified) and PRIOR-ART (without it, a rebrand is
not blocked). Deterministic and offline (fixtures + fake online providers; no network).
"""
from __future__ import annotations
from typing import Dict


def _mean(xs):
    xs = list(xs)
    return round(sum(1.0 if x else 0.0 for x in xs) / len(xs), 3) if xs else 0.0


def run_evolution_eval(budget: int = 14) -> Dict:
    import OUTLIER_MCB as m
    task = m.symbolic_invention_task()
    res = m.evolve_invention(task["problem"], task["evaluator"], budget=budget, pack=task["pack"])
    recs = res.memory.all()
    best = res.best()

    # core metrics
    metrics = {
        "evaluated_candidate_rate": _mean(bool(r.evaluator_name) for r in recs),
        "improvement_over_baseline_rate": _mean((r.improvement_over_baseline or 0) > 0 for r in recs),
        "verified_rate": _mean(r.verified for r in recs),
        "best_verified": bool(best and best.verified),
        "best_beats_baseline": bool(best and (best.improvement_over_baseline or 0) > 0),
        "diversity_frontier_score": round(len({tuple(sorted(r.broken_assumptions)) for r in recs}) / max(1, len(recs)), 3),
        "regression_block_rate": _mean((r.improvement_over_parent or 0) >= 0 for r in recs if r.parent_ids),
        "candidates": len(recs),
    }

    # ABLATION 1 — the evaluator gate. With it, an unverified candidate cannot score high; without it
    # (correctness forced True), unverified-but-plausible candidates inflate.
    high_unverified_gate = _mean(r.score > 0.5 and not r.verified for r in recs)
    high_unverified_nogate = _mean(
        m.invention_score({**r.score_components, "correctness": True,
                           "improvement_over_baseline": r.improvement_over_baseline,
                           "improvement_over_parent": r.improvement_over_parent})["score"] > 0.5 and not r.verified
        for r in recs)

    # ABLATION 2 — prior art blocks false novelty. A candidate that IS prior art (an exact online match)
    # is a RENAMED_PRIOR_ART and must be blocked; with NO provider it is not.
    class _Match(m.OnlinePriorArtProvider):
        name = "exact"
        def _fetch(self, q):
            return [m.PriorArtResult(title=q, summary=q, url="http://x")]   # an exact match → rename
    idea = "a distributed rate limiter measured by request cost"
    cand = m.Candidate(name=idea, operator="invert", breaks=["X"], assumptions=["a"], negation=idea)
    blocked = m.NoveltyEvaluator(m.CompositePriorArtProvider([_Match()])).evaluate(cand)
    not_checked = m.NoveltyEvaluator(m.CompositePriorArtProvider([m.OfflinePriorArtProvider([])])).evaluate(cand)
    false_novelty_blocked = (blocked.artifacts.get("graded_verdict") == "RENAMED_PRIOR_ART"
                             and blocked.score < 0.3 and not_checked.score >= blocked.score)

    return {
        "metrics": metrics,
        "ablation_evaluator_gate": {"high_unverified_with_gate": high_unverified_gate,
                                    "high_unverified_without_gate": high_unverified_nogate,
                                    "gate_earns_keep": high_unverified_nogate >= high_unverified_gate},
        "ablation_prior_art": {"false_novelty_blocked": bool(false_novelty_blocked),
                               "blocked_scope": blocked.artifacts.get("novelty_scope")},
        "statement": res.conservative_statement(),
    }


def markdown(report: Dict) -> str:
    L = ["# Evolution eval — does the loop invent, and do its guards earn their keep?", "", "## Core metrics"]
    L += [f"- {k}: {v}" for k, v in report["metrics"].items()]
    g = report["ablation_evaluator_gate"]
    L += ["", "## Ablation — evaluator gate",
          f"- high-scoring-but-UNVERIFIED with gate: {g['high_unverified_with_gate']} · without gate: "
          f"{g['high_unverified_without_gate']} → gate earns its keep: {g['gate_earns_keep']}"]
    p = report["ablation_prior_art"]
    L += ["## Ablation — prior art", f"- a rebrand is blocked as false novelty: {p['false_novelty_blocked']} "
          f"(scope {p['blocked_scope']})"]
    L += ["", f"**Statement:** {report['statement']}"]
    return "\n".join(L)


if __name__ == "__main__":
    print(markdown(run_evolution_eval()))
