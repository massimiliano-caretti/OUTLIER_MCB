"""cascade — assumption DYNAMICS: breaking one assumption forces or frees others (a chain reaction).

Every other operator treats a break as a static, isolated act. But assumptions are coupled: the typed
graph already records which depends on which, which blocks which, which collapses to a family. `cascade`
reads those edges and computes the chain reaction of a single break — what DESTABILIZES (assumptions
that depended on it), what is FREED (assumptions it was blocking), what COLLAPSES (families that rested
on it), and the new information the whole cascade requires. The most creative seed is the one whose
single break unlocks the largest cascade — a lever, not a pebble. This is generation by dynamics, a move
no standard idea engine makes.

Collaborators: kernel.graph_of (the typed AssumptionGraph and its edges).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List


@dataclass
class Cascade:
    seed: str                                       # the assumption broken
    forced: List[str] = field(default_factory=list)     # assumptions that DESTABILIZE (they depended on the seed)
    freed: List[str] = field(default_factory=list)      # assumptions the seed was BLOCKING — now breakable
    collapses: List[str] = field(default_factory=list)  # families/structures that rested on the seed
    requires: List[str] = field(default_factory=list)   # new information the cascade needs
    @property
    def reach(self) -> int:
        """The size of the chain reaction — how much a single break unlocks."""
        return len(set(self.forced) | set(self.freed) | set(self.collapses))
    def markdown(self) -> str:
        return "\n".join([
            f"### Cascade from breaking `{self.seed}`  (reach {self.reach})",
            f"- **forced (depended on it, now destabilized):** {', '.join(self.forced) or '—'}",
            f"- **freed (it was blocking them, now breakable):** {', '.join(self.freed) or '—'}",
            f"- **collapses (rested on it):** {', '.join(self.collapses) or '—'}",
            f"- **the cascade requires:** {', '.join(self.requires) or 'nothing new'}",
        ])


def cascade(pack, seed: str, depth: int = 2) -> Cascade:
    """Compute the chain reaction of breaking `seed`, propagating `forced` up to `depth` levels."""
    from . import kernel
    g = kernel.graph_of(pack)
    forced, freed, collapses, requires = [], [], [], []
    frontier, seen = [seed], {seed}
    for _ in range(max(1, depth)):
        nxt = []
        for node in frontier:
            for s, r, d, _ in g.in_edges(node, "depends_on"):       # X depends_on node ⇒ breaking node destabilizes X
                if s not in seen:
                    forced.append(s); seen.add(s); nxt.append(s)
            for s, r, d, _ in g.in_edges(node, "implies"):          # X implies node ⇒ X also shaken
                if s not in seen:
                    forced.append(s); seen.add(s); nxt.append(s)
            for s, r, d, _ in g.out_edges(node, "blocks"):          # node blocks Z ⇒ breaking node frees Z
                if d not in freed:
                    freed.append(d)
            for s, r, d, _ in g.out_edges(node, "collapses_to"):
                if d not in collapses:
                    collapses.append(d)
            for rel in ("needs_new_data", "if_false_requires"):
                for s, r, d, _ in g.out_edges(node, rel):
                    if d not in requires:
                        requires.append(d)
        frontier = nxt
        if not frontier:
            break
    return Cascade(seed=seed, forced=forced, freed=freed, collapses=collapses, requires=requires)


def biggest_lever(pack, depth: int = 2) -> Cascade:
    """The single break with the largest cascade — the assumption whose negation unlocks the most."""
    breakable = [a.name for a in pack.assumptions if pack.dimension_of.get(a.name)]
    cascades = [cascade(pack, n, depth) for n in breakable]
    return max(cascades, key=lambda c: c.reach) if cascades else Cascade(seed="—")
