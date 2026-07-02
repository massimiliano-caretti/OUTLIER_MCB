"""evaluator_synthesis — invent the way an idea is VERIFIED, not just the idea (improvement #3).

A creative system is bounded by the evaluators it has. This module ASSEMBLES a settling evaluator from the
materials a claim brings with it — a behavior check, public cases, an oracle, a baseline the claim says must
fail, a perturbation that a real mechanism must not survive — into a HiddenEvaluator with public cases,
HELD-OUT hidden cases, and NEGATIVE CONTROLS. It does not hallucinate a checker from prose: with no check or
no cases it refuses (honesty over coverage). It then proves the synthesized evaluator earns its structure —
quality requires the baseline to FAIL and the oracle to PASS, and an ablation shows the hidden/control
structure catches a cheat a public-only evaluator waves through.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from .errors import OUTLIER_MCBError
from .evaluators.hidden import HiddenEvaluator
from .evaluators.base import BaseEvaluator, EvaluationResult


class EvaluatorSynthesisError(OUTLIER_MCBError):
    """Not enough material to synthesize a real evaluator — the engine will not fake one from prose."""


class SynthesizedEvaluator(BaseEvaluator):
    """A drop-in BaseEvaluator wrapping a HiddenEvaluator built by synthesis, plus the provenance of each part
    (where the public/hidden/negative-control cases came from). An external resolver, like the one it wraps."""
    is_correctness = True
    settles_externally = True

    def __init__(self, hidden: HiddenEvaluator, sources: Dict[str, str], claim: str = "", name: str = "synthesized"):
        self.hidden, self.sources, self.claim, self.name = hidden, sources, claim, name

    def _run(self, candidate, workspace=None) -> EvaluationResult:
        return self.hidden._run(candidate, workspace)


def synthesize_evaluator(candidate, context: Dict, name: str = "synthesized") -> SynthesizedEvaluator:
    """Build a settling evaluator for `candidate` from `context`:
        check(solution, case) -> bool        REQUIRED — does a solution handle one case
        public_cases / cases : [...]          REQUIRED — at least one
        hidden_cases : [...]                  optional — else auto-held-out from public (half)
        negative_controls : [...]             optional — else derived via perturb(case) if given
        perturb(case) -> case                 optional — a break a REAL mechanism must NOT survive
        adversarial_cases : [...]             optional
    Refuses (raises) without a check or any cases — there is nothing real to test."""
    check = context.get("check")
    public = list(context.get("public_cases") or context.get("cases") or [])
    if not callable(check) or not public:
        raise EvaluatorSynthesisError("need a callable `check` and at least one case to synthesize an evaluator")

    sources: Dict[str, str] = {"check": "context.check", "public_cases": "context"}
    hidden = list(context.get("hidden_cases") or [])
    if not hidden and len(public) >= 2:
        cut = len(public) // 2
        public, hidden = public[:cut] or public, public[cut:]
        sources["hidden_cases"] = "auto-held-out from public (the candidate never sees these)"
    elif hidden:
        sources["hidden_cases"] = "context"

    controls = list(context.get("negative_controls") or [])
    if not controls and callable(context.get("perturb")):
        controls = [context["perturb"](c) for c in (context.get("cases") or public + hidden)]
        sources["negative_controls"] = "derived via context.perturb (a real mechanism must FAIL these)"
    elif controls:
        sources["negative_controls"] = "context"

    adversarial = list(context.get("adversarial_cases") or [])
    he = HiddenEvaluator(check, public_cases=public, hidden_cases=hidden, adversarial_cases=adversarial,
                         negative_controls=controls, name=name)
    claim = (candidate if isinstance(candidate, str)
             else getattr(candidate, "negation", "") or getattr(candidate, "name", ""))
    return SynthesizedEvaluator(he, sources=sources, claim=str(claim), name=name)


def validate_evaluator(evaluator) -> List[str]:
    """An evaluator is only trustworthy if it can be CHEATED-tested: it must hold public cases, HIDDEN cases,
    and NEGATIVE CONTROLS. Returns the missing pieces ([] = a complete anti-cheating evaluator)."""
    he = getattr(evaluator, "hidden", evaluator)
    issues: List[str] = []
    if not getattr(he, "public_cases", None):
        issues.append("no public cases — nothing is tested")
    if not getattr(he, "hidden_cases", None):
        issues.append("no hidden cases — cannot tell discovery from optimizing the visible")
    if not getattr(he, "negative_controls", None):
        issues.append("no negative controls — cannot detect leakage")
    return issues


def evaluator_quality_score(evaluator, context: Dict) -> Dict:
    """Score the synthesized evaluator in [0,1]: structural completeness PLUS the two behavioral musts —
    the baseline the claim says fails must FAIL, and the oracle/known-good (if any) must PASS."""
    structure = max(0.0, 1.0 - len(validate_evaluator(evaluator)) / 3.0)
    baseline = context.get("baseline")
    oracle = context.get("oracle")
    claim_baseline_fails = bool(context.get("claim_baseline_fails", True))
    baseline_fails = None
    if baseline is not None and claim_baseline_fails:
        baseline_fails = not evaluator.evaluate(baseline).passed
    oracle_passes = None
    if oracle is not None:
        oracle_passes = evaluator.evaluate(oracle).passed
    behav = [v for v in (baseline_fails, oracle_passes) if v is not None]
    behavioral = (sum(1.0 for v in behav if v) / len(behav)) if behav else 0.0
    score = round(0.5 * structure + 0.5 * behavioral, 4) if behav else round(0.5 * structure, 4)
    return {"score": score, "components": {"structure": round(structure, 3), "behavioral": round(behavioral, 3),
            "baseline_fails": baseline_fails, "oracle_passes": oracle_passes},
            "usable": structure >= 1.0 and (not behav or behavioral >= 0.5)}


def evaluator_ablation(synthesized, context: Dict) -> Dict:
    """Ablation for #3: does the hidden/control structure actually catch a cheat? Compare the synthesized
    evaluator against a PUBLIC-ONLY one on a `leaky_candidate` (passes public, fails hidden or passes a
    negative control) and an `honest_candidate`. The synthesized evaluator must reject the cheat the naive
    one accepts. Needs both candidates in context; otherwise reports insufficient material."""
    he = getattr(synthesized, "hidden", synthesized)
    leaky = context.get("leaky_candidate")
    honest = context.get("honest_candidate")
    if leaky is None or honest is None:
        return {"ran": False, "reason": "provide context.leaky_candidate and context.honest_candidate"}
    check = he.check
    naive = HiddenEvaluator(check, public_cases=he.public_cases, name="public_only")  # no hidden, no controls
    syn_leaky = synthesized.evaluate(leaky).passed
    syn_honest = synthesized.evaluate(honest).passed
    naive_leaky = naive.evaluate(leaky).passed
    naive_honest = naive.evaluate(honest).passed
    catches_cheat = (naive_leaky and not syn_leaky)            # naive waves it through, synthesized rejects it
    return {"ran": True, "naive_accepts_cheat": naive_leaky, "synthesized_rejects_cheat": not syn_leaky,
            "both_accept_honest": syn_honest and naive_honest, "structure_earns_its_place": catches_cheat,
            "synth_verdicts": {"leaky": syn_leaky, "honest": syn_honest},
            "naive_verdicts": {"leaky": naive_leaky, "honest": naive_honest}}
