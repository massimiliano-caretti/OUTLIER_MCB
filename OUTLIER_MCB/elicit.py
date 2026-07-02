"""elicit — the disciplined generative bridge.

The kernel cannot invent domain knowledge (that would be hallucination). When no registered pack
matches, elicit_pack returns the generic fallback PLUS an ElicitationRequest: the exact scaffold the
assistant must fill (the human/LLM spark) to build a real DomainPack. The assistant fills it,
pack_from_spec validates it, and the kernel then falsifies — agnosticism without magic.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List
from .core import Assumption
from .pack import DomainPack, select_pack, get_pack, register_pack


SCAFFOLD_QUESTIONS = [
    "List 4–6 assumptions that EVERY known solution in this domain silently shares.",
    "For each assumption: which breakable AXIS does it sit on (e.g. representation / objective / "
    "evaluation / decomposition / interface / measure / structure)? Name 3–5 axes for this domain.",
    "Name the known solution FAMILIES a new idea must be collided against (so we can detect collage).",
    "Which NEW INFORMATION could move the ceiling (a new observable / oracle / constraint / dataset)?",
    "For one assumption, sketch the WORLD-TEST: the situation where the known family fails and the "
    "broken-assumption idea wins, plus the counterexample that would kill the idea.",
]


@dataclass
class ElicitationRequest:
    prompt: str
    reason: str
    questions: List[str] = field(default_factory=lambda: list(SCAFFOLD_QUESTIONS))
    spec_template: Dict = field(default_factory=lambda: {
        "name": "<domain>", "keywords": ["..."], "box_name": "<the domain's default solution>",
        "assumptions": [{"name": "...", "description": "...", "why_obvious": "...",
                         "if_false": "...", "assumed_by": ["..."], "falsifier": "...", "axis": "..."}],
        "axes": {"<AXIS>": {"priority": 3, "verdict": "<honest note, mark HEURISTIC if not validated>"}},
        "relations": [["src", "needs_new_data", "<info_token>", "note"]],
        "known_families": ["..."], "info_kinds": {"<info_token>": "why it helps"}})
    def as_dict(self) -> Dict:
        return {"prompt": self.prompt, "reason": self.reason, "questions": self.questions,
                "spec_template": self.spec_template}


def pack_from_spec(spec: Dict) -> DomainPack:
    """Build (and validate) a DomainPack from an elicited spec dict."""
    assumptions, dim = [], {}
    for a in spec.get("assumptions", []):
        assumptions.append(Assumption(a["name"], a.get("description", ""), a.get("why_obvious", ""),
                                      a.get("if_false", ""), a.get("assumed_by", []), a.get("falsifier", "")))
        if a.get("axis"):
            dim[a["name"]] = a["axis"]
    relations = [tuple(r) for r in spec.get("relations", [])]
    pack = DomainPack(
        name=spec.get("name", "elicited"), keywords=spec.get("keywords", []),
        box_name=spec.get("box_name", "the default solution"),
        assumptions=assumptions, relations=relations, dimension_of=dim,
        box_assumptions=set(spec.get("box_assumptions", list(dim)[:3])),
        axes=spec.get("axes", {}), known_families=spec.get("known_families", []),
        info_kinds=spec.get("info_kinds", {}), failure_memory=spec.get("failure_memory", {}),
        universal_closures=spec.get("universal_closures", []), world_factory=None)
    issues = pack.validate()
    if issues:
        from .errors import InvalidPackError
        raise InvalidPackError(f"elicited pack invalid: {issues}")
    return pack


def _gap_questions(quality: Dict) -> List[str]:
    """Turn a pack_quality report into the SPECIFIC follow-up questions that would close its gaps — so
    elicitation stops being one-shot and converges on a pack strong enough to not launder weak structure."""
    qs: List[str] = []
    for ax in quality.get("uncovered_axes", []):
        qs.append(f"Axis '{ax}' has no assumption on it — add an assumption that sits on '{ax}', or drop the axis.")
    for name in quality.get("weak_falsifiers", []):
        qs.append(f"The falsifier for '{name}' is too vague — give the concrete construction (≥4 words) where "
                  f"the known family provably fails.")
    c = quality.get("components", {})
    if c.get("assumption_count_score", 1.0) < 1.0:
        qs.append("List more hidden assumptions every known solution silently shares (aim for ≥4).")
    if c.get("known_family_score", 1.0) < 1.0:
        qs.append("Name more known solution FAMILIES to collide a new idea against (≥2).")
    if c.get("relation_density_score", 1.0) < 0.5:
        qs.append("Add typed relations among assumptions (implies / depends_on / if_false_requires / needs_new_data).")
    if c.get("info_kind_score", 1.0) < 1.0:
        qs.append("List the NEW information kinds that could move the ceiling (≥2).")
    return qs


def iterative_elicit(prompt: str, answer_provider, threshold: float = 0.6, max_rounds: int = 3) -> Dict:
    """Iterative elicitation. `answer_provider(request) -> spec` is the human/LLM filling (or improving) the
    spec; `request` carries the prompt, the questions to answer, and the spec so far. Each round we build the
    pack, score it with pack_quality, and — if it is below `threshold` (or invalid) — generate the SPECIFIC
    follow-up questions that would close its gaps, then ask again. Stops on convergence or after max_rounds.

    Returns {pack, quality, converged, rounds, history, spec}. `pack` is None only if no round produced a
    valid pack. This never fabricates content — the assistant/human still answers; the loop only insists on
    a pack strong enough that the engine's rigor is real, not apparent."""
    from .pack_quality import pack_quality
    history: List[Dict] = []
    request = {"prompt": prompt, "questions": list(SCAFFOLD_QUESTIONS),
               "spec_template": ElicitationRequest(prompt=prompt, reason="initial").spec_template, "round": 0}
    pack, spec, quality = None, None, 0.0
    for r in range(max_rounds):
        spec = answer_provider(request) or spec
        if spec is None:
            break
        try:
            pack = pack_from_spec(spec)
        except Exception as exc:                         # invalid spec → ask to fix the schema, keep looping
            history.append({"round": r, "quality": 0.0, "valid": False, "error": str(exc)})
            request = {"prompt": prompt, "round": r + 1, "spec_template": spec,
                       "questions": [f"The spec is not yet valid ({exc}). Fix it, then continue."]}
            pack, quality = None, 0.0
            continue
        q = pack_quality(pack)
        quality = q["overall"]
        history.append({"round": r, "quality": quality, "valid": True})
        if quality >= threshold:
            return {"pack": pack, "quality": quality, "converged": True, "rounds": r + 1,
                    "history": history, "spec": spec}
        gaps = _gap_questions(q) or ["Strengthen the weakest component and resubmit."]
        request = {"prompt": prompt, "round": r + 1, "spec_template": spec,
                   "current_quality": quality, "questions": gaps}
    return {"pack": pack, "quality": quality, "converged": False, "rounds": len(history),
            "history": history, "spec": spec}


def elicit_pack(prompt: str, register: bool = False) -> Dict:
    """Return a usable pack for `prompt`. If a registered domain matches, use it; otherwise return the
    generic fallback + an ElicitationRequest for the assistant to build a real pack."""
    pack, hits = select_pack(prompt)
    if hits > 0 and pack.name != "generic":
        return {"pack": pack, "confidence": hits, "source": f"registered:{pack.name}", "request": None}
    req = ElicitationRequest(prompt=prompt,
                             reason="no registered domain pack matched; the kernel must not answer from a canned "
                                    "domain. Fill the scaffold to build this domain's assumptions, then falsify.")
    return {"pack": get_pack("generic"), "confidence": 0, "source": "generic_fallback", "request": req.as_dict()}
