"""world_tests — generate the WORLDS that settle a candidate (often you must invent the test, not the idea).

For one candidate it produces: the world where the BASELINE must fail, the counterworld where the candidate
should WIN, the minimal falsifier (the single case that would kill it), a scale shift (does it survive 1000×?),
and a negative control (a perturbation that must collapse the gain — or it was leakage). These specs feed the
HiddenEvaluator's hidden/adversarial/negative-control slots: the candidate is then settled on worlds it never
saw. Reuses the candidate's own broken assumption (its `if_false`) so the worlds are grounded, not generic.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class GeneratedWorld:
    description: str
    kind: str                        # baseline_fails | counterworld | minimal_falsifier | scale_shift | negative_control
    falsifier: str = ""

    def markdown(self) -> str:
        return f"- **[{self.kind}]** {self.description}" + (f"\n    - falsifier: {self.falsifier}" if self.falsifier else "")


def _broke(candidate) -> str:
    a = getattr(candidate, "assumptions", None)
    return (a[0] if a else getattr(candidate, "name", "the assumption"))


def _if_false(candidate, pack) -> str:
    nm = _broke(candidate)
    a = pack.by_name().get(nm) if pack else None
    return (a.if_false if a else getattr(candidate, "negation", "the box's assumption is violated"))


class WorldTestGenerator:
    """Build candidate-specific worlds. `pack` grounds the worlds in the broken assumption's failure mode."""
    def __init__(self, pack=None):
        self.pack = pack

    def generate_world_test(self, problem: str, candidate) -> GeneratedWorld:
        return GeneratedWorld(
            description=f"{problem} — the world where the BASELINE fails because {_if_false(candidate, self.pack)}",
            kind="baseline_fails",
            falsifier="if the baseline ALSO handles this world, the candidate breaks no real assumption here.")

    def generate_counterworld(self, candidate) -> GeneratedWorld:
        return GeneratedWorld(
            description=f"the world where breaking '{_broke(candidate)}' should WIN: matched to the candidate's mechanism",
            kind="counterworld",
            falsifier="if the candidate does NOT win here, its claimed mechanism is not what helps.")

    def generate_minimal_falsifier(self, candidate) -> GeneratedWorld:
        return GeneratedWorld(
            description=f"the SINGLE minimal case that would kill the candidate (the cheapest disproof of '{_broke(candidate)}')",
            kind="minimal_falsifier",
            falsifier="construct it adversarially; one failure here refutes the candidate.")

    def generate_scale_shift(self, candidate, factor: int = 1000) -> GeneratedWorld:
        return GeneratedWorld(
            description=f"the same world at {factor}× (more instances / less supervision / more extreme cost)",
            kind="scale_shift",
            falsifier="show a CROSSOVER: it must hold below a threshold scale and may break beyond it.")

    def negative_control(self, candidate) -> GeneratedWorld:
        return GeneratedWorld(
            description=f"a NEGATIVE CONTROL: shuffle/destroy the structure '{_broke(candidate)}' exploits",
            kind="negative_control",
            falsifier="the candidate's gain MUST collapse here; if it survives, the gain was leakage, not a mechanism.")

    def full_suite(self, problem: str, candidate) -> List[GeneratedWorld]:
        return [self.generate_world_test(problem, candidate), self.generate_counterworld(candidate),
                self.generate_minimal_falsifier(candidate), self.generate_scale_shift(candidate),
                self.negative_control(candidate)]
