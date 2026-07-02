"""evals.generative_eval — does the GENERATIVE upgrade earn its keep? (improvement #10)

One gate over the new creative capabilities, each measured AND ablated against a decorative control so a
feature only counts if it beats the inert version of itself:

  • pack self-induction (#1)     — an induced pack diverges more than the generic pack and far more than a
                                   one-axis decorative pack.
  • semantic repo grounding (#2) — a candidate naming real symbols is grounded; gibberish is not.
  • evaluator synthesis (#3)     — the hidden/control structure catches a cheat a public-only evaluator passes.
  • claim ladder (#9)            — a strong word is blocked under weak evidence, licensed under full evidence.

    python -m evals.generative_eval
"""
from __future__ import annotations
import os
import tempfile
from typing import Dict


def _pack_induction_score() -> Dict:
    import OUTLIER_MCB as gsl
    ab = gsl.pack_induction_ablation("design a fairer matchmaking system where skill and latency interact")
    earns = ab["induction_beats_generic"] and ab["induction_beats_decorative"]
    return {"score": 1.0 if earns else 0.0, "earns_keep": earns, **ab}


def _semantic_grounding_score() -> Dict:
    import OUTLIER_MCB as gsl
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, "pkg"))
    os.makedirs(os.path.join(d, "tests"))
    open(os.path.join(d, "pkg", "core.py"), "w").write("def rate_limit(x):\n    return x\n")
    open(os.path.join(d, "pkg", "api.py"), "w").write("from pkg.core import rate_limit\ndef serve(r):\n    return rate_limit(r)\n")
    open(os.path.join(d, "tests", "test_core.py"), "w").write("from pkg import core\ndef test_x():\n    assert core.rate_limit(1)==1\n")
    model = gsl.analyze_repo_semantics(d)
    ab = gsl.repo_grounding_ablation(model)
    earns = ab["grounding_discriminates"]
    return {"score": 1.0 if earns else 0.0, "earns_keep": earns,
            "untested_modules_found": model.modules_without_tests(), **ab}


def _evaluator_synthesis_score() -> Dict:
    from OUTLIER_MCB.evaluator_synthesis import synthesize_evaluator, evaluator_ablation, evaluator_quality_score

    class _Sol:
        def __init__(self, fn): self.fn, self.name = fn, "sol"
    ctx = {"check": lambda s, c: s.fn(c), "cases": [1, 2, 3, 4], "perturb": lambda c: -abs(c) - 1,
           "baseline": _Sol(lambda c: c < -100), "oracle": _Sol(lambda c: c > 0), "claim_baseline_fails": True,
           "leaky_candidate": _Sol(lambda c: True), "honest_candidate": _Sol(lambda c: c > 0)}
    ev = synthesize_evaluator("classify positive", ctx)
    q = evaluator_quality_score(ev, ctx)
    ab = evaluator_ablation(ev, ctx)
    earns = ab["ran"] and ab["structure_earns_its_place"] and q["usable"]
    return {"score": q["score"] if earns else 0.0, "earns_keep": earns,
            "quality": q["score"], "catches_cheat": ab.get("structure_earns_its_place")}


def _claim_ladder_score() -> Dict:
    import OUTLIER_MCB as gsl
    ab = gsl.claim_ladder_ablation()
    earns = ab["gate_is_about_evidence"]
    return {"score": 1.0 if earns else 0.0, "earns_keep": earns, **ab}


def _active_problem_score() -> Dict:
    import OUTLIER_MCB as gsl
    ab = gsl.problem_active_ablation()
    return {"score": 1.0 if ab["earns_keep"] else 0.0, "earns_keep": ab["earns_keep"], **ab}


def _online_analogy_score() -> Dict:
    import OUTLIER_MCB as gsl
    prov = gsl.CallableProvider(lambda q: {"matches": [{"title": "predator-prey carrying capacity",
                                                        "summary": "population stabilizes at equilibrium",
                                                        "url": "u", "source_type": "paper"}]})
    ab = gsl.analogy_online_ablation(prov)
    return {"score": 1.0 if ab.get("earns_keep") else 0.0, "earns_keep": bool(ab.get("earns_keep")), **ab}


def _failure_mutation_score() -> Dict:
    import OUTLIER_MCB as gsl
    ab = gsl.failure_lesson_ablation()
    return {"score": 1.0 if ab["earns_keep"] else 0.0, "earns_keep": ab["earns_keep"], **ab}


def _divergent_runner_score() -> Dict:
    import OUTLIER_MCB as gsl
    ab = gsl.protocol_ablation()
    return {"score": 1.0 if ab["earns_keep"] else 0.0, "earns_keep": ab["earns_keep"], **ab}


def _frontier_score() -> Dict:
    import OUTLIER_MCB as gsl
    ab = gsl.frontier_ablation()
    return {"score": 1.0 if ab["earns_keep"] else 0.0, "earns_keep": ab["earns_keep"], **ab}


def run_generative_eval() -> Dict:
    parts = {
        "pack_self_induction_score": _pack_induction_score(),
        "semantic_grounding_score": _semantic_grounding_score(),
        "evaluator_synthesis_score": _evaluator_synthesis_score(),
        "claim_ladder_score": _claim_ladder_score(),
        "active_problem_finding_score": _active_problem_score(),
        "online_analogy_score": _online_analogy_score(),
        "failure_mutation_score": _failure_mutation_score(),
        "divergent_runner_score": _divergent_runner_score(),
        "novelty_frontier_score": _frontier_score(),
    }
    scores = {k: v["score"] for k, v in parts.items()}
    earns = {k: v["earns_keep"] for k, v in parts.items()}
    primary = round(sum(scores.values()) / len(scores), 4)
    all_earn = all(earns.values())
    state = "GO_GENERATIVE" if all_earn and primary >= 0.75 else "NOT_READY_GENERATIVE"
    return {"state": state, "primary": primary, "scores": scores, "earns_keep": earns,
            "blockers": [k for k, ok in earns.items() if not ok], "detail": parts}


def markdown(report: Dict) -> str:
    L = [f"# Generative eval — {report['state']} (primary {report['primary']})", "",
         "## Each new capability vs its decorative control (ablation)"]
    for k, ok in report["earns_keep"].items():
        L.append(f"- {'✓' if ok else '✗'} {k}: score {report['scores'][k]} · earns its keep: {ok}")
    if report["blockers"]:
        L.append(f"\n**Blockers:** {', '.join(report['blockers'])}")
    return "\n".join(L)


if __name__ == "__main__":
    print(markdown(run_generative_eval()))
