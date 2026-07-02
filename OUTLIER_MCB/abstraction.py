"""abstraction — DreamCoder-style: when several candidates share a structure, EXTRACT it as a reusable
CONCEPT and add it to a growing concept library.

This is how a system builds a NEW conceptual language rather than just more ideas: three different
candidates that all 'replace a surface proxy with a hidden causal variable' become the named concept
`latent_cost_reframing`, reusable in a new domain. It reuses the engine's compression view (MDL: explain
more with less) to score a concept's worth — an abstraction only earns its place if it COMPRESSES the
population (covers several members) — never a relabel of a single idea.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Concept:
    name: str
    pattern: str                     # the shared structure (the common broken-assumption / mechanism)
    members: List[str] = field(default_factory=list)   # ids of the candidates it abstracts
    domains: List[str] = field(default_factory=list)
    reuse_hint: str = ""
    level: str = "assumption_set"    # assumption_set (exact shared break) | mechanism (cross-cutting lever/axis)

    @property
    def support(self) -> int:
        return len(self.members)

    def markdown(self) -> str:
        tag = "" if self.level == "assumption_set" else f" [{self.level}]"
        return f"- **{self.name}**{tag} (support {self.support}): {self.pattern} — reuse: {self.reuse_hint}"


@dataclass
class ConceptLibrary:
    concepts: Dict[str, Concept] = field(default_factory=dict)

    def add(self, concept: Concept) -> Concept:
        self.concepts[concept.name] = concept
        return concept

    def all(self) -> List[Concept]:
        return sorted(self.concepts.values(), key=lambda c: -c.support)

    def reuse_concept_in_new_domain(self, name: str, pack) -> str:
        """Apply a learned concept to a new domain: suggest breaking the analogous assumption there."""
        c = self.concepts.get(name)
        if c is None:
            return ""
        axis = next(iter(pack.axes), "—")
        return (f"reuse «{c.name}» in {pack.name}: apply the pattern «{c.pattern}» to {pack.name}'s '{axis}' "
                f"axis — break the assumption there that plays the same role, then falsify.")

    def markdown(self) -> str:
        L = [f"## Concept library — {len(self.concepts)} reusable concepts"]
        L += [c.markdown() for c in self.all()]
        return "\n".join(L)


def _records(memory_or_records):
    return memory_or_records.all() if hasattr(memory_or_records, "all") else list(memory_or_records)


def mine_abstractions(memory_or_records, min_support: int = 2) -> ConceptLibrary:
    """Cluster candidates by the SET of assumptions they break; any structure shared by ≥ min_support
    candidates becomes a Concept. The abstraction must COMPRESS (cover several members), never relabel one."""
    recs = _records(memory_or_records)
    clusters: Dict[frozenset, List] = {}
    for r in recs:
        key = frozenset(getattr(r, "broken_assumptions", []) or [])
        if key:
            clusters.setdefault(key, []).append(r)
    lib = ConceptLibrary()
    for key, members in clusters.items():
        if len(members) >= min_support:
            name = "concept_" + "_".join(sorted(key))[:40]
            pattern = "candidates that jointly break {" + ", ".join(sorted(key)) + "}"
            domains = sorted({getattr(m, "problem", "") for m in members})
            lib.add(Concept(name=name, pattern=pattern, members=[getattr(m, "id", "?") for m in members],
                            domains=domains, reuse_hint="apply this joint break to a new domain's analogous axes"))
    return lib


def compress_candidates_to_concepts(memory_or_records, min_support: int = 2) -> ConceptLibrary:
    """Alias that emphasizes the MDL view: turn a population into the fewest concepts that cover it."""
    return mine_abstractions(memory_or_records, min_support=min_support)


def mine_mechanism_abstractions(memory_or_records, pack=None, min_support: int = 2) -> ConceptLibrary:
    """A DEEPER miner (#7): mine_abstractions clusters by the EXACT set of broken assumptions and so misses
    the structure shared *across* different combinations. This one finds the cross-cutting MECHANISM:

      • a recurring LEVER — one assumption reused inside several candidates whose full break-sets DIFFER
        (the same move, recombined — the mark of a real reusable mechanism, not one repeated idea); and
      • a recurring AXIS — different assumptions that all act on the same pack dimension (operate on the
        REPRESENTATION axis, whatever the specific lever), discovered via pack.dimension_of.

    The result sits one level above mine_abstractions: it names the mechanism, not the particular idea.
    """
    recs = _records(memory_or_records)
    dim_of = getattr(pack, "dimension_of", {}) or {}

    by_lever: Dict[str, List] = {}
    by_axis: Dict[str, List] = {}
    for r in recs:
        broken = list(getattr(r, "broken_assumptions", []) or [])
        for a in broken:
            by_lever.setdefault(a, []).append(r)
            axis = dim_of.get(a)
            if axis:
                by_axis.setdefault(axis, []).append(r)

    lib = ConceptLibrary()
    # a recurring lever is a mechanism only if it shows up in DIFFERENT full break-sets (cross-cutting reuse)
    for lever, members in by_lever.items():
        distinct_sets = {frozenset(getattr(m, "broken_assumptions", []) or []) for m in members}
        if len(members) >= min_support and len(distinct_sets) >= 2:
            lib.add(Concept(
                name="mechanism_" + lever, level="mechanism",
                pattern=f"the recurring lever «{lever}» reused across different assumption combinations",
                members=[getattr(m, "id", "?") for m in members],
                domains=sorted({getattr(m, "problem", "") for m in members}),
                reuse_hint=f"carry «{lever}» into a new domain as a standalone move, then recombine + falsify"))
    # a recurring axis is a mechanism only if several DIFFERENT levers act on the same dimension
    for axis, members in by_axis.items():
        levers = {a for m in members for a in (getattr(m, "broken_assumptions", []) or []) if dim_of.get(a) == axis}
        if len(members) >= min_support and len(levers) >= 2:
            lib.add(Concept(
                name="axis_" + axis, level="mechanism",
                pattern=f"operate on the «{axis}» dimension (different levers, same axis)",
                members=[getattr(m, "id", "?") for m in members],
                domains=sorted({getattr(m, "problem", "") for m in members}),
                reuse_hint=f"in a new domain, attack its «{axis}» analogue with any available lever, then falsify"))
    return lib
