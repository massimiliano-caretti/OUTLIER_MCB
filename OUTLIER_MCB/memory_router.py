"""memory_router - turn many memory stores into one creative next-move plan.

The library already has useful memories, but a discovery engine needs them as an
active control surface, not as separate archives. CreativeMemoryRouter retrieves
only the memories that should change the next generation: unknown assumptions to
attack, repeated failure modes to avoid, fertile analogies to transfer, skills to
reuse, and frontier candidates to push beyond.

This is intentionally prompt- and evaluator-friendly: it returns compact cues and
a prompt block that can be injected into any generator without claiming proof or
absolute novelty.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .prompt_sampler import STRATEGIES


@dataclass
class MemoryCue:
    source: str
    kind: str
    text: str
    weight: float = 0.0
    action: str = ""
    evidence: Dict = field(default_factory=dict)


@dataclass
class MemoryPlan:
    problem: str
    cues: List[MemoryCue] = field(default_factory=list)
    recommended_strategy: str = "explore_unknown_axis"
    prompt_block: str = ""

    def by_source(self, source: str) -> List[MemoryCue]:
        return [c for c in self.cues if c.source == source]

    def by_action(self, action: str) -> List[MemoryCue]:
        return [c for c in self.cues if c.action == action]


def _clip(text: str, n: int = 180) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "..."


def _weight(v: float) -> float:
    return round(max(0.0, min(1.0, float(v))), 3)


class CreativeMemoryRouter:
    """Unify memory retrieval around the real creative objective.

    The router is not another memory. It is the policy layer deciding what memory
    should influence the next candidate. Its bias is deliberately divergent:
    unexplored axes and distant transfers outrank repetition of high-scoring but
    saturated patterns.
    """

    def __init__(
        self,
        *,
        evolution_memory=None,
        discovery_memory=None,
        episodic_memory=None,
        analogical_memory=None,
        skill_library=None,
        lesson_memory=None,
        pack=None,
        embedder=None,
    ):
        self.evolution_memory = evolution_memory
        self.discovery_memory = discovery_memory
        self.episodic_memory = episodic_memory
        self.analogical_memory = analogical_memory
        self.skill_library = skill_library
        self.lesson_memory = lesson_memory
        self.pack = pack
        self.embedder = embedder

    def plan(self, problem: str, k: int = 12) -> MemoryPlan:
        cues = self.retrieve(problem, k=k)
        strategy = self.recommend_strategy(cues)
        return MemoryPlan(
            problem=problem,
            cues=cues,
            recommended_strategy=strategy,
            prompt_block=self.prompt_block(problem, cues),
        )

    def retrieve(self, problem: str, k: int = 12) -> List[MemoryCue]:
        cues: List[MemoryCue] = []
        self._add_unknown_space(cues, problem)
        self._add_failure_lessons(cues, problem)
        self._add_discovery_memory(cues)
        self._add_episodic_memory(cues, problem)
        self._add_analogical_memory(cues)
        self._add_skill_library(cues, problem)
        self._add_evolution_frontier(cues, problem)
        return self._dedupe(cues)[:k]

    def recommend_strategy(self, cues: List[MemoryCue]) -> str:
        actions = {c.action for c in cues}
        if "explore_unknown_axis" in actions:
            return "explore_unknown_axis"
        if "avoid_failure_mode" in actions or "change_failed_mechanism" in actions:
            return "mutate_failed_candidate"
        if "transfer_mechanism_from_distant_domain" in actions:
            return "transfer_mechanism_from_distant_domain"
        if "improve_frontier_candidate" in actions:
            return "exploit_best_parent"
        return "explore_unknown_axis"

    def prompt_block(self, problem: str, cues: Optional[List[MemoryCue]] = None, k: int = 12) -> str:
        cues = cues if cues is not None else self.retrieve(problem, k=k)
        if not cues:
            return "MEMORY ROUTER: no useful memory cues yet; prefer a new falsifiable axis."

        groups = {
            "EXPLORE": [
                c for c in cues
                if c.action in {"explore_unknown_axis", "exploit_fertile_assumption"}
            ],
            "AVOID / MUTATE": [
                c for c in cues
                if c.action in {"avoid_failure_mode", "change_failed_mechanism", "avoid_barren_assumption"}
            ],
            "TRANSFER": [
                c for c in cues
                if c.action == "transfer_mechanism_from_distant_domain"
            ],
            "REUSE SKILLS": [
                c for c in cues
                if c.action == "apply_creative_skill"
            ],
            "PUSH FRONTIER": [
                c for c in cues
                if c.action in {"reuse_confirmed_episode", "improve_frontier_candidate"}
            ],
        }

        lines = ["MEMORY ROUTER (use only if it changes the mechanism):"]
        for label, items in groups.items():
            if not items:
                continue
            rendered = "; ".join(_clip(c.text, 120) for c in items[:3])
            lines.append(f"{label}: {rendered}")
        lines.append(
            "RULE: memory is evidence, not proof; use it to leave saturated patterns and create a testable mechanism."
        )
        return "\n".join(lines)

    def _add_unknown_space(self, cues: List[MemoryCue], problem: str) -> None:
        if self.pack is None or self.evolution_memory is None:
            return
        try:
            from .unknown_space import suggest_unknown_region

            region = suggest_unknown_region(problem, self.evolution_memory, self.pack)
        except Exception:
            return
        for name in region.unexplored_assumptions[:4]:
            cues.append(MemoryCue(
                source="unknown_space",
                kind="unexplored_assumption",
                text=f"Break unexplored assumption '{name}' because it opens a less-seen axis.",
                weight=0.98,
                action="explore_unknown_axis",
                evidence={"assumption": name},
            ))
        for axis in region.unexplored_axes[:3]:
            cues.append(MemoryCue(
                source="unknown_space",
                kind="unexplored_axis",
                text=f"Attack untouched axis '{axis}' before optimizing inside explored regions.",
                weight=0.94,
                action="explore_unknown_axis",
                evidence={"axis": axis},
            ))
        for name in region.saturated_assumptions[:3]:
            cues.append(MemoryCue(
                source="unknown_space",
                kind="saturated_failure",
                text=f"'{name}' failed repeatedly; retry only with a different mechanism.",
                weight=0.9,
                action="change_failed_mechanism",
                evidence={"assumption": name},
            ))

    def _add_failure_lessons(self, cues: List[MemoryCue], problem: str) -> None:
        if self.lesson_memory is None:
            return
        for lesson in self.lesson_memory.retrieve(problem, k=5):
            cues.append(MemoryCue(
                source="lesson",
                kind=getattr(lesson, "mode", "failure"),
                text=f"{lesson.mode}: {lesson.lesson}",
                weight=0.96,
                action="avoid_failure_mode",
                evidence={"source_id": getattr(lesson, "source_id", "")},
            ))

    def _add_discovery_memory(self, cues: List[MemoryCue]) -> None:
        if self.discovery_memory is None:
            return
        for outcome in self.discovery_memory.fertile()[:4]:
            cues.append(MemoryCue(
                source="discovery",
                kind="fertile_assumption",
                text=(
                    f"{outcome.domain}:{outcome.assumption} was fertile "
                    f"({outcome.confirmed}/{outcome.attempted}); extend it, do not rename it."
                ),
                weight=_weight(0.7 + 0.25 * outcome.prior),
                action="exploit_fertile_assumption",
                evidence={"assumption": outcome.assumption, "prior": outcome.prior},
            ))
        for outcome in self.discovery_memory.barren()[:4]:
            cues.append(MemoryCue(
                source="discovery",
                kind="barren_assumption",
                text=f"{outcome.domain}:{outcome.assumption} was barren; avoid the same break.",
                weight=_weight(0.72 + 0.2 * (1.0 - outcome.prior)),
                action="avoid_barren_assumption",
                evidence={"assumption": outcome.assumption, "prior": outcome.prior},
            ))
        for item in self.discovery_memory.discovered[-3:]:
            assumption = item.get("assumption", "")
            axis = item.get("axis", "")
            cues.append(MemoryCue(
                source="discovery",
                kind="emergent_axis",
                text=f"Promoted emergent assumption '{assumption}' on axis '{axis}'; test whether it generalizes.",
                weight=0.88,
                action="explore_unknown_axis",
                evidence=dict(item),
            ))

    def _add_episodic_memory(self, cues: List[MemoryCue], problem: str) -> None:
        if self.episodic_memory is None:
            return
        for episode, sim in self.episodic_memory.recall(problem, k=4, embedder=self.embedder):
            outcome = getattr(episode, "outcome", "OPEN")
            if sim < 0.45:
                continue
            action = "reuse_confirmed_episode" if outcome == "CONFIRMED" else "avoid_failure_mode"
            cues.append(MemoryCue(
                source="episode",
                kind=outcome.lower(),
                text=(
                    f"Similar episode '{episode.assumption or episode.problem}' ended {outcome} "
                    f"(sim {sim}); {'reuse the mechanism' if outcome == 'CONFIRMED' else 'avoid repeating it'}."
                ),
                weight=_weight(0.45 + 0.45 * sim),
                action=action,
                evidence={"similarity": sim, "assumption": getattr(episode, "assumption", "")},
            ))

    def _add_analogical_memory(self, cues: List[MemoryCue]) -> None:
        if self.analogical_memory is None:
            return
        for analogy in self.analogical_memory.fertile()[:5]:
            emergence_bonus = min(0.12, 0.12 * float(getattr(analogy, "emergence", 0.0) or 0.0))
            mapping = _clip(getattr(analogy, "mapping", "") or "transfer the relation, not the vocabulary", 90)
            cues.append(MemoryCue(
                source="analogy",
                kind="fertile_transfer",
                text=(
                    f"{analogy.source_domain}->{analogy.target_domain} transfers well "
                    f"(prior {analogy.prior}); {mapping}."
                ),
                weight=_weight(0.74 + 0.14 * analogy.prior + emergence_bonus),
                action="transfer_mechanism_from_distant_domain",
                evidence={
                    "source_domain": analogy.source_domain,
                    "target_domain": analogy.target_domain,
                    "prior": analogy.prior,
                    "emergence": analogy.emergence,
                },
            ))

    def _add_skill_library(self, cues: List[MemoryCue], problem: str) -> None:
        if self.skill_library is None:
            return
        for skill in self.skill_library.retrieve_skills(problem, k=4):
            cues.append(MemoryCue(
                source="skill",
                kind="creative_move",
                text=f"Use skill '{skill.name}' via {skill.move} when it changes the mechanism.",
                weight=_weight(0.52 + 0.34 * skill.success_rate),
                action="apply_creative_skill",
                evidence={"skill": skill.name, "success_rate": skill.success_rate},
            ))

    def _add_evolution_frontier(self, cues: List[MemoryCue], problem: str) -> None:
        if self.evolution_memory is None:
            return
        try:
            records = self.evolution_memory.diverse_top_k(k=4, problem=problem, embedder=self.embedder)
        except Exception:
            records = self.evolution_memory.top_k(k=4, problem=problem)
        for record in records:
            action = "improve_frontier_candidate" if getattr(record, "correctness_passed", False) else "change_failed_mechanism"
            verb = "beat and generalize" if action == "improve_frontier_candidate" else "repair with a new mechanism"
            cues.append(MemoryCue(
                source="evolution",
                kind="frontier" if action == "improve_frontier_candidate" else "failed_parent",
                text=f"{record.candidate_name} scored {record.score}; {verb}.",
                weight=_weight(0.45 + 0.35 * float(record.score or 0.0)),
                action=action,
                evidence={"record_id": record.id, "score": record.score},
            ))

    def _dedupe(self, cues: List[MemoryCue]) -> List[MemoryCue]:
        out: Dict[str, MemoryCue] = {}
        for cue in cues:
            key = f"{cue.source}:{cue.kind}:{cue.text.lower()}"
            old = out.get(key)
            if old is None or cue.weight > old.weight:
                out[key] = cue
        ranked = sorted(out.values(), key=lambda c: (-c.weight, c.source, c.kind, c.text))
        strategy_rank = {s: i for i, s in enumerate(STRATEGIES)}
        return sorted(ranked, key=lambda c: (-c.weight, strategy_rank.get(c.action, 99), c.source))
