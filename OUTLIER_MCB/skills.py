"""skills — Voyager-style skill library: accumulate REUSABLE creative MOVES and compose them.

Human creativity does not restart from zero — it accrues mental tools ('use a minimal counterexample',
'transfer a mechanism from physics to software', 'replace a continuous metric with a discrete constraint')
and recombines them. A Skill names such a move, records WHEN it works and its success rate, can be RETRIEVED
for a new problem, and COMPOSED with another into a new skill. Persistent (JSONL) so the toolkit compounds.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional


@dataclass
class Skill:
    name: str
    move: str                        # the operator / mechanism (e.g. 'invert@MEASURE', 'transport_from_distant')
    when_to_use: str = ""            # the cue that signals this skill applies
    attempts: int = 0
    successes: int = 0
    source_problems: List[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        return round(self.successes / self.attempts, 3) if self.attempts else 0.5   # untried ⇒ neutral

    def markdown(self) -> str:
        return f"- **{self.name}** ({self.move}) · success {self.success_rate} ({self.successes}/{self.attempts}) — {self.when_to_use}"


def _tokens(text: str) -> set:
    return {w for w in "".join(c if c.isalnum() else " " for c in (text or "").lower()).split() if len(w) > 3}


# a small seed toolkit of domain-blind creative moves (the engine starts with a vocabulary, then grows it).
SEED_SKILLS = [
    ("minimal_counterexample", "search_counterexample", "a universal/robustness claim — find the single case that breaks it"),
    ("distant_mechanism_transfer", "transport_from_distant", "stuck inside one domain — import a mechanism from a far domain"),
    ("break_temporal_assumption", "invert@time", "the problem assumes a fixed/static order — make time a variable"),
    ("find_latent_variable", "abduce_latent", "a surface proxy is being optimized — look for the hidden causal variable"),
    ("continuous_to_discrete", "reframe@measure", "a continuous metric — replace it with a discrete constraint"),
    ("provoke_then_mine", "provocation", "the obvious answers are exhausted — assert an absurd premise and mine the kernel"),
]


@dataclass
class SkillLibrary:
    skills: Dict[str, Skill] = field(default_factory=dict)

    @classmethod
    def with_seed(cls) -> "SkillLibrary":
        lib = cls()
        for name, move, cue in SEED_SKILLS:
            lib.add(Skill(name=name, move=move, when_to_use=cue))
        return lib

    def add(self, skill: Skill) -> Skill:
        self.skills[skill.name] = skill
        return skill

    def retrieve_skills(self, problem: str, k: int = 3) -> List[Skill]:
        """The skills most relevant to `problem` (cue overlap), best-first by relevance then success rate."""
        pt = _tokens(problem)
        scored = [(len(pt & _tokens(s.when_to_use + " " + s.name)), s.success_rate, s) for s in self.skills.values()]
        return [s for _o, _r, s in sorted(scored, key=lambda t: (-t[0], -t[1]))[:k]]

    def record_outcome(self, name: str, success: bool, problem: str = "") -> None:
        s = self.skills.get(name)
        if s is None:
            return
        s.attempts += 1
        s.successes += int(success)
        if problem and problem not in s.source_problems:
            s.source_problems.append(problem)

    def compose_skills(self, name_a: str, name_b: str) -> Optional[Skill]:
        """Compose two skills into a NEW reusable move — recombination at the level of TOOLS, not ideas."""
        a, b = self.skills.get(name_a), self.skills.get(name_b)
        if a is None or b is None:
            return None
        composed = Skill(name=f"{a.name}+{b.name}", move=f"{a.move} ∘ {b.move}",
                         when_to_use=f"when both apply: {a.when_to_use}; AND {b.when_to_use}")
        return self.add(composed)

    def save_jsonl(self, path: str) -> None:
        import json
        with open(path, "w") as fh:
            for s in self.skills.values():
                fh.write(json.dumps(asdict(s)) + "\n")

    @classmethod
    def load_jsonl(cls, path: str) -> "SkillLibrary":
        import json
        import os
        lib = cls()
        if os.path.exists(path):
            with open(path) as fh:
                for line in fh:
                    if line.strip():
                        lib.add(Skill(**json.loads(line)))
        return lib

    def markdown(self) -> str:
        L = [f"## Skill library — {len(self.skills)} reusable creative moves"]
        L += [s.markdown() for s in sorted(self.skills.values(), key=lambda s: -s.success_rate)]
        return "\n".join(L)
