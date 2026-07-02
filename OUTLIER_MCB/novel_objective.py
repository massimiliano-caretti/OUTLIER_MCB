"""novel_objective -- make novelty the objective without letting it self-certify.

The broken assumption is that the objective is already fixed: invention is not
just "score the candidate on the task"; it is "move the verified frontier". This
evaluator wraps a real resolver, measures novelty on independent axes, and then
applies hard honesty caps:

* no external resolver passed -> hypothesis only;
* no negative-control evidence -> useful, but not a frontier win;
* no successful online prior-art check -> no strong novelty language.

It is intentionally an evaluator, not a generator. The generator may be wild;
this objective decides what survives.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .evaluators.base import BaseEvaluator, CallableEvaluator, EvaluationResult


def _clamp(x) -> float:
    return max(0.0, min(1.0, float(x or 0.0)))


def _cand_text(candidate) -> str:
    if isinstance(candidate, str):
        return candidate
    get = (lambda k: getattr(candidate, k, "") if not isinstance(candidate, dict) else candidate.get(k, ""))
    return " ".join(str(get(k)) for k in ("name", "negation", "claim", "discipline") if get(k))


def _behavior_signature_from_result(result: EvaluationResult):
    comps = tuple(sorted((k, round(float(v), 1)) for k, v in (result.components or {}).items()))
    return (bool(result.passed), comps)


def _sig_distance(a, b) -> float:
    passed_diff = 0.5 if a[0] != b[0] else 0.0
    ka, kb = dict(a[1]), dict(b[1])
    keys = set(ka) | set(kb)
    comp_diff = (sum(abs(ka.get(k, 0.0) - kb.get(k, 0.0)) for k in keys) / max(1, len(keys))) if keys else 0.0
    return round(min(1.0, passed_diff + 0.5 * comp_diff), 3)


def _behavioral_novelty_from_result(result: EvaluationResult, archive: Optional[List] = None) -> float:
    sig = _behavior_signature_from_result(result)
    if not archive:
        return 1.0
    return round(min(_sig_distance(sig, prior) for prior in archive), 3)


def _control_evidence(result: EvaluationResult) -> Dict:
    """Read negative-control evidence from common evaluator fields.

    `controls_collapse=True` is the strongest existing convention in this repo.
    If an evaluator does not expose any such field, the objective still scores
    the candidate but caps it, because the gain may be leakage.
    """
    merged = {}
    merged.update(result.components or {})
    merged.update(result.artifacts or {})
    keys = ("controls_collapse", "negative_control_collapse", "negative_control_collapses")
    present = [k for k in keys if k in merged]
    if present:
        ok = all(bool(merged[k]) for k in present)
        return {"present": True, "passed": ok, "keys": present}
    return {"present": False, "passed": False, "keys": []}


def _break_depth(candidate) -> float:
    breaks = set(getattr(candidate, "breaks", []) or ([] if isinstance(candidate, str) else []))
    assumptions = set(getattr(candidate, "assumptions", []) or ([] if isinstance(candidate, str) else []))
    return round(min(1.0, (len(breaks) + 0.5 * len(assumptions)) / 3.0), 3)


@dataclass
class NoveltyObjectiveWeights:
    correctness: float = 0.35
    frontier: float = 0.35
    break_depth: float = 0.15
    base_quality: float = 0.15

    def score(self, factors: Dict[str, float]) -> float:
        return round(_clamp(
            self.correctness * factors["correctness"]
            + self.frontier * factors["frontier"]
            + self.break_depth * factors["break_depth"]
            + self.base_quality * factors["base_quality"]
        ), 4)


@dataclass
class NoveltyObjectiveEvaluator(BaseEvaluator):
    """A frontier-seeking objective that is still settled by an external resolver.

    `correctness_evaluator` is the world/data/repo/prover gate. `provider` is a
    prior-art provider. Archives make the objective recursive: each run can feed
    seen texts and behavior signatures back into the next evaluation so novelty
    is measured against what the system has already tried.
    """
    correctness_evaluator: Optional[BaseEvaluator] = None
    provider: object = None
    conceptual_archive: List[str] = field(default_factory=list)
    behavioral_archive: List = field(default_factory=list)
    weights: NoveltyObjectiveWeights = field(default_factory=NoveltyObjectiveWeights)
    threshold: float = 0.5
    name: str = "novelty_objective"
    is_correctness: bool = True
    settles_externally: bool = False

    def __post_init__(self):
        self.settles_externally = bool(getattr(self.correctness_evaluator, "settles_externally", False))

    def _run(self, candidate, workspace=None) -> EvaluationResult:
        from .claim_ladder import gate_claim_language
        from .frontier import conceptual_novelty
        from .novelty import prior_art_audit

        if self.correctness_evaluator is None:
            base = EvaluationResult(passed=False, score=0.0, error="no external correctness evaluator")
        else:
            base = self.correctness_evaluator.evaluate(candidate, workspace=workspace)

        external_ok = bool(self.settles_externally and base.passed)
        controls = _control_evidence(base)
        controls_ok = bool(controls["present"] and controls["passed"])
        text = _cand_text(candidate)

        conceptual = conceptual_novelty(candidate, self.conceptual_archive)
        behavioral = _behavioral_novelty_from_result(base, self.behavioral_archive)
        prior_art = None
        scoped_verdict = ""
        novelty_scope = "LOCAL_ONLY"
        prior_art_checked = False
        if self.provider is not None:
            audit = prior_art_audit(text, self.provider, verifier_passed=external_ok)
            prior_art = audit.prior_art_distance_score
            scoped_verdict = audit.scoped_verdict()
            novelty_scope = audit.novelty_scope or "LOCAL_ONLY"
            prior_art_checked = novelty_scope == "ONLINE_PRIOR_ART_CHECKED"

        measured = [conceptual, behavioral] + ([] if prior_art is None else [prior_art])
        # HONESTY FIX (#6, twin): frontier is the WEAKEST measured axis (a gate), not their mean — a real-world
        # prior-art collision must pull the frontier down, not be averaged away by high text-distance. (The cap
        # cascade below is an independent guard; this keeps the frontier factor itself honest too.)
        frontier = round(min(measured), 4) if measured else 0.0
        factors = {
            "correctness": 1.0 if base.passed else 0.0,
            "base_quality": _clamp(base.score),
            "frontier": frontier,
            "break_depth": _break_depth(candidate),
        }
        score = self.weights.score(factors)
        caps = []
        if not base.passed:
            score = min(score, 0.25)
            caps.append("correctness_failed -> score capped at 0.25")
        if not external_ok:
            score = min(score, 0.35)
            caps.append("external_resolver_missing -> frontier claim capped at 0.35")
        if not controls_ok:
            score = min(score, 0.55)
            caps.append("negative_control_missing_or_failed -> score capped at 0.55")
        if self.provider is None or novelty_scope != "ONLINE_PRIOR_ART_CHECKED":
            score = min(score, 0.72)
            caps.append(f"online_prior_art_missing -> novelty language refused (scope={novelty_scope})")
        if scoped_verdict in ("RENAMED_PRIOR_ART", "COLLAGE_OF_PRIOR_ART"):
            score = min(score, 0.4)
            caps.append(f"prior_art_collision -> score capped at 0.4 ({scoped_verdict})")

        raw_claim = f"candidate {getattr(candidate, 'name', text[:40])} is a verified novel discovery."
        gate = gate_claim_language(raw_claim, {
            "falsifier": True,
            "empirical_support": base.passed,
            "external_settlement": external_ok,
            "formal_verification": external_ok,
            "prior_art_checked": prior_art_checked,
        })
        comps = {
            "base_score": round(_clamp(base.score), 3),
            "conceptual_novelty": conceptual,
            "behavioral_novelty": behavioral,
            "frontier": frontier,
            "break_depth": factors["break_depth"],
            "external_settlement": 1.0 if external_ok else 0.0,
            "negative_control": 1.0 if controls_ok else 0.0,
        }
        if prior_art is not None:
            comps["prior_art_novelty"] = prior_art
        artifacts = {
            "base_error": base.error,
            "base_artifacts": base.artifacts,
            "novelty_scope": novelty_scope,
            "prior_art_scoped_verdict": scoped_verdict,
            "caps": caps,
            "claim_gate": gate,
            "behavior_signature": _behavior_signature_from_result(base),
            "control_evidence": controls,
        }
        passed = bool(base.passed and external_ok and controls_ok and score >= self.threshold)
        return EvaluationResult(passed=passed, score=round(score, 4), components=comps, artifacts=artifacts)


def novelty_objective(evaluator=None, provider=None, conceptual_archive: Optional[List[str]] = None,
                      behavioral_archive: Optional[List] = None, weights: Optional[NoveltyObjectiveWeights] = None,
                      threshold: float = 0.5, name: str = "novelty_objective") -> NoveltyObjectiveEvaluator:
    """Factory for a novelty-seeking objective.

    `evaluator` may be a BaseEvaluator or a callable returning a score/evidence
    dict. Plain callables are treated as non-external unless the caller wraps
    them in `CallableEvaluator(..., settles_externally=True)`.
    """
    base = evaluator
    if base is not None and not isinstance(base, BaseEvaluator):
        base = CallableEvaluator(base, name="objective", passed_key="controls_collapse")
    return NoveltyObjectiveEvaluator(
        correctness_evaluator=base,
        provider=provider,
        conceptual_archive=list(conceptual_archive or []),
        behavioral_archive=list(behavioral_archive or []),
        weights=weights or NoveltyObjectiveWeights(),
        threshold=threshold,
        name=name,
    )


def recursive_novelty_search(problem: str, evaluator=None, provider=None, pack=None, budget: int = 24, **kwargs):
    """Run evolve_invention with novelty as the objective and orchestration on.

    This is the "keep pushing the frontier" convenience path. It still returns
    an EvolveResult, so all normal honesty statements and prior-art caps remain
    in force.
    """
    from .evolve import evolve_invention

    ev = novelty_objective(evaluator=evaluator, provider=provider)
    return evolve_invention(problem, ev, pack=pack, prior_art_provider=provider, budget=budget,
                            orchestrate=True, **kwargs)
