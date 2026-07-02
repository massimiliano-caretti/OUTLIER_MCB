"""generators.base — the Candidate type and the shared pack helpers.

Every generative operator returns a `Candidate`: a proposed move that GENERATES an idea but certifies
nothing. Its `discipline` field names exactly how the idea must still die on a world-test. The helpers
read a DomainPack uniformly so each operator module can focus on its single move.

Collaborators: core.negate (for the radical negation); kernel.graph_of (for data requirements).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List

from ..core import negate


@dataclass
class Candidate:
    """One generated, not-yet-certified move toward an idea."""
    name: str
    operator: str                                    # recombine | invert | scale | transport | abduce | unify | …
    breaks: List[str]                                # axes broken (empty for non-breaking operators)
    assumptions: List[str]                           # assumption names involved
    negation: str                                    # the generative statement (what is now assumed false)
    needs: List[str] = field(default_factory=list)   # new information the move requires
    discipline: str = ""                             # how this candidate is STILL obliged to die
    emergence: float = 0.0                            # blend operator only: distance between the two parent breaks

    def as_dict(self) -> Dict:
        return self.__dict__

    def markdown(self) -> str:
        lines = [f"- **[{self.operator}] {self.name}**  (breaks {', '.join(self.breaks) or '—'})",
                 f"    - assumes false: {self.negation}"]
        if self.needs:
            lines.append(f"    - needs new information: {', '.join(self.needs)}")
        lines.append(f"    - still must die by: {self.discipline}")
        return "\n".join(lines)


# ── pack readers (shared by every operator) ────────────────────────────────────────────────────────
def breakable(pack) -> List:
    """The pack's assumptions that sit on a declared axis — i.e. that can be broken to leave the box."""
    return [a for a in pack.assumptions if pack.dimension_of.get(a.name)]


def data_req(pack) -> Dict[str, List[str]]:
    """Map each assumption to the new-information tokens its break requires (from the typed graph)."""
    from .. import kernel
    return kernel.graph_of(pack).data_requirements()


def radical_negation(a) -> str:
    """The assumption's `if_false` consequence — the radical (not weak, not reframing) negation."""
    return negate(a)[1].statement


def axes_by_priority(pack) -> List[str]:
    """The pack's axes, highest priority first (ties broken by name) — used to map analogies across packs."""
    return [ax for ax, _ in sorted(pack.axes.items(), key=lambda kv: (-kv[1].get("priority", 1), kv[0]))]
