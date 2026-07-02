"""problem_generator — POET-style: generate NEW problems / harder environments / adversarial worlds.

Human creativity often CHANGES THE PROBLEM rather than answering the given one ('a rate limiter where the
cost is energy, not request count'). This co-evolves challenges with solutions: it reframes the objective
using the domain's own information kinds, builds an adversarial world where a rare-but-extreme case breaks
the baseline, and scales the regime to a harder environment. Each generated problem ships with a FALSIFIER —
the world where the current box must fail — so a new problem is itself a stepping stone, not a slogan.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class GeneratedProblem:
    statement: str
    kind: str                        # variant | adversarial | harder
    parent_problem: str = ""
    new_measure: str = ""            # the information kind / axis the reframing introduces
    falsifier: str = ""              # the world where the current box must fail
    metadata: dict = field(default_factory=dict)

    def markdown(self) -> str:
        return f"- **[{self.kind}]** {self.statement}\n    - falsifier: {self.falsifier}"


class ProblemGenerator:
    """Generate problems for a domain (`pack`). The reframings come from the pack's `info_kinds` (the new
    observables that could move the ceiling) and `box_assumptions` (what the box holds fixed)."""
    def __init__(self, pack):
        self.pack = pack

    def generate_problem_variants(self, problem: str, n: int = 3) -> List[GeneratedProblem]:
        """Swap the MEASURE/objective: each variant re-poses the problem around a different new-information
        kind the domain could acquire — 'the same problem, measured by X instead of the default'."""
        out: List[GeneratedProblem] = []
        for kind, why in list(self.pack.info_kinds.items())[:n]:
            out.append(GeneratedProblem(
                statement=f"{problem} — but measured by «{kind}» ({why}) instead of the box's default proxy",
                kind="variant", parent_problem=problem, new_measure=kind,
                falsifier=f"a case where the box's default proxy and «{kind}» DISAGREE; the box must fail there."))
        if not out:
            out.append(GeneratedProblem(statement=f"{problem} — reframed around a new observable the box ignores",
                                        kind="variant", parent_problem=problem,
                                        falsifier="a case the box's measure cannot see."))
        return out

    def generate_adversarial_world(self, problem: str) -> GeneratedProblem:
        """A world built to BREAK the box: a rare-but-extreme input that the default solution mishandles,
        derived from a box assumption's failure mode."""
        box = [a for a in self.pack.assumptions if a.name in self.pack.box_assumptions]
        a = box[0] if box else (self.pack.assumptions[0] if self.pack.assumptions else None)
        fail = a.if_false if a else "the box's hidden assumption is violated"
        return GeneratedProblem(
            statement=f"{problem} — in an ADVERSARIAL world where {fail}",
            kind="adversarial", parent_problem=problem,
            falsifier=f"construct the rare-but-extreme instance where «{fail}»; the box solution must fail it "
                      f"while a broken-assumption idea survives.",
            metadata={"from_assumption": a.name if a else ""})

    def generate_harder_environment(self, problem: str, factor: int = 1000) -> GeneratedProblem:
        """Scale the regime: a true-at-small-scale solution may break at {factor}× (more instances / less
        supervision / more extreme cost)."""
        return GeneratedProblem(
            statement=f"{problem} — at {factor}× (more instances, less supervision, more extreme cost)",
            kind="harder", parent_problem=problem,
            falsifier=f"show a CROSSOVER: the box solution holds below a threshold scale and FAILS beyond it.")

    def transfer_solution_between_worlds(self, solution: str, target_world: str) -> str:
        """A note on porting a solution to a generated world — it loses all novelty credit and must be
        re-falsified in the new world (no free transfer)."""
        return (f"port «{solution}» into «{target_world}»: it enters with ZERO credit and must pass the new "
                f"world's falsifier; if it does not survive there, the transfer fails.")
