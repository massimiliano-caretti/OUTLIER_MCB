"""OUTLIER_MCB — shared types & the domain-agnostic negation engine.

Deliberately minimal and domain-blind: the only things every domain shares are an `Assumption`
(a hidden premise that can be made false) and a `Negation` (three increasingly radical ways to
break it). All real domain content lives in a DomainPack (see pack.py); nothing here knows about
any specific problem. Everything an idea rests on can be made false.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List


@dataclass
class Assumption:
    """A hidden premise that the known solutions of a domain silently share."""
    name: str
    description: str
    why_obvious: str
    if_false: str
    assumed_by: List[str] = field(default_factory=list)
    falsifier: str = ""
    def __repr__(self) -> str:
        return f"Assumption({self.name})"


@dataclass
class Negation:
    """One way of breaking an assumption. kind ∈ {weak, radical, green_star}."""
    assumption: str
    kind: str
    statement: str
    consequence: str
    testable_via: str


def negate(a: Assumption) -> List[Negation]:
    """Produce three negations of an assumption, increasingly radical, from the assumption itself.

    Domain-agnostic: it reads only the Assumption's own fields (no per-domain lookup table), so it
    works identically on any pack.
      weak       — the premise need not always hold (relax it on a sub-population).
      radical    — the premise is simply false (its `if_false` consequence is the truth).
      green_star — reframe WHAT the object/target is around the broken premise.
    """
    consequence = (a.if_false or f"the premise '{a.name}' does not hold").strip()
    weak = f"'{a.description.rstrip('.')}' need not always hold — it can fail on a sub-population."
    radical = consequence
    green_star = f"reframe the problem so that the real object/target is defined by: {consequence}"
    return [
        Negation(a.name, "weak", weak, f"slightly relaxes '{a.name}'", a.falsifier),
        Negation(a.name, "radical", radical, f"replaces the premise of '{a.name}'", a.falsifier),
        Negation(a.name, "green_star", green_star, "reframes WHAT the object/target is", a.falsifier),
    ]
