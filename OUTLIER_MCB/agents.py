"""agents — light cognitive ROLES (from AutoGen/CrewAI, the idea only, not the heavy framework).

Human creative thought is a conversation of roles: an inventor proposes the strange, a skeptic looks for why
it is false, an analogist reaches a distant domain, a theorist formalizes, an adversary tries to destroy it.
Each role here is a thin wrapper over the engine's OWN machinery (reviewer, prior-art, analogy, first-
principles, world-test) producing STRUCTURED evidence — no LLM, deterministic, auditable. A CognitivePanel
runs them and synthesizes a conservative verdict; the panel never certifies, it surfaces the path to a verdict.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class AgentEvidence:
    role: str
    summary: str
    evidence: Dict = field(default_factory=dict)

    def markdown(self) -> str:
        return f"- **{self.role}:** {self.summary}"


def _safe(fn, role: str, default: str):
    try:
        return fn()
    except Exception as exc:
        return AgentEvidence(role=role, summary=f"{default} (unavailable: {type(exc).__name__})")


class CognitivePanel:
    """Deliberate over a free-text idea with a panel of roles. `provider` (a PriorArtProvider) lets the
    PriorArtHunter search the real world; without one it reports LOCAL_ONLY honestly."""
    ROLES = ("Skeptic", "Adversary", "PriorArtHunter", "Analogist", "Theorist", "Orthogonalist",
             "Reducer", "Experimentalist")

    def __init__(self, pack, provider=None, reputations=None):
        self.pack, self.provider = pack, provider
        self.reputations = reputations or {}

    def _skeptic(self, idea):
        from .reviewer import attack
        card = attack(idea, self.pack)
        return AgentEvidence("Skeptic", card.reviewer_rejection,
                             {"is_this_just": card.is_this_just, "max_claim": card.max_claim_allowed})

    def _adversary(self, idea):
        from .first_principles_reviewer import first_principles_attack
        crit = first_principles_attack(idea)
        return AgentEvidence("Adversary", f"{len(crit.objections)} falsifiable objections from first principles",
                             {"dimensions": crit.dimensions()})

    def _prior_art_hunter(self, idea):
        from .novelty import prior_art_audit
        from .prior_art import CompositePriorArtProvider, OfflinePriorArtProvider
        prov = self.provider or CompositePriorArtProvider([OfflinePriorArtProvider([])])
        nv = prior_art_audit(idea, prov)
        return AgentEvidence("PriorArtHunter", f"{nv.scoped_verdict()} (scope {nv.novelty_scope or 'LOCAL_ONLY'})",
                             {"novelty_scope": nv.novelty_scope or "LOCAL_ONLY", "verdict": nv.graded_verdict})

    def _analogist(self, idea):
        from .analogy import CrossDomainAnalogyEngine
        best = CrossDomainAnalogyEngine(self.pack).best_analogies(1)
        if not best:
            return AgentEvidence("Analogist", "no distant analogy available")
        a = best[0]
        return AgentEvidence("Analogist", f"transfer '{a.source_mechanism}' from {a.source_domain} (distance {a.analogy_distance})",
                             {"source_domain": a.source_domain, "distance": a.analogy_distance})

    def _theorist(self, idea):
        from .math_discovery import Conjecture, investigate_conjecture
        res = investigate_conjecture(Conjecture(idea), use_sympy=False)
        return AgentEvidence("Theorist", f"formalization status: {res.status}", {"status": res.status})

    def _orthogonalist(self, idea):
        from .orthogonal_germs import propose_orthogonal_germ
        cand = propose_orthogonal_germ(self.pack, idea)
        return AgentEvidence("Orthogonalist",
                             f"new-basis candidate breaks {', '.join(cand.breaks) or 'REPRESENTATION'} "
                             f"(orthogonality proxy {cand.emergence})",
                             {"candidate": cand.as_dict(), "discipline": cand.discipline})

    def _reducer(self, idea):
        words = [w for w in idea.split() if len(w) > 3]
        return AgentEvidence("Reducer", f"simplify to its kernel: «{' '.join(words[:8])}…»",
                             {"kernel_terms": words[:8]})

    def _experimentalist(self, idea):
        from .world_designer import design_world_test
        try:
            spec = design_world_test(idea, axis="", pack=self.pack)
            return AgentEvidence("Experimentalist", "world-test designed (the runnable falsifier)",
                                 {"spec": getattr(spec, "as_dict", lambda: {})()})
        except Exception:
            return AgentEvidence("Experimentalist", "needs a runnable world-test before it can be settled")

    def deliberate(self, idea: str) -> "PanelReport":
        builders = {"Skeptic": self._skeptic, "Adversary": self._adversary, "PriorArtHunter": self._prior_art_hunter,
                    "Analogist": self._analogist, "Theorist": self._theorist,
                    "Orthogonalist": self._orthogonalist, "Reducer": self._reducer,
                    "Experimentalist": self._experimentalist}
        evid = [_safe(lambda b=b: b(idea), role, "no evidence") for role, b in builders.items()]
        scope = next((e.evidence.get("novelty_scope") for e in evid if e.role == "PriorArtHunter"), "LOCAL_ONLY")
        from .cognitive_growth import role_vote_weight
        role_weights = {e.role: role_vote_weight(e.role, 1.0 if e.evidence else 0.25, self.reputations) for e in evid}
        synthesis = (f"panel verdict (conservative): an idea worth auditing — prior art {scope}; it must still "
                     f"pass the Experimentalist's world-test and survive the Adversary's objections. Never "
                     f"'absolute novelty' without online prior-art + a passing verifier.")
        return PanelReport(idea=idea, evidence=evid, synthesis=synthesis, role_weights=role_weights)


@dataclass
class PanelReport:
    idea: str
    evidence: List[AgentEvidence] = field(default_factory=list)
    synthesis: str = ""
    role_weights: Dict[str, float] = field(default_factory=dict)

    def by_role(self, role: str) -> Optional[AgentEvidence]:
        return next((e for e in self.evidence if e.role == role), None)

    def markdown(self) -> str:
        weights = "" if not self.role_weights else " · role weights: " + str(self.role_weights)
        return "\n".join([f"## Cognitive panel — «{self.idea}»"] + [e.markdown() for e in self.evidence]
                         + ["", f"**{self.synthesis}**{weights}"])
