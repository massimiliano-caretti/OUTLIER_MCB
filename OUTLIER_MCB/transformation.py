"""transformation — transformational creativity: the engine GROWS its own conceptual space.

Boden's three kinds of creativity: combinatorial (recombine / blend ✓), exploratory (search within a
pack's axes ✓), and TRANSFORMATIONAL — changing the space itself so previously-impossible ideas become
possible. green_star.novel_axis pairs two abstract primitives (ungrounded); anomaly_to_assumption mines a
new assumption but leaves it INERT (no axis). This module supplies the missing move: take an anomaly (a
residual the box calls noise, or a cross-domain blend) and PROMOTE it to a genuinely new, breakable AXIS,
producing an EXPANDED DomainPack the engine can then explore — a degree of freedom the domain did not have.

Honest, anti-rigor-theater gate (the `meta` pack forbids decorative machinery): a proposed axis only counts
as TRANSFORMATIONAL if it is far (pluggable semantic distance) from every existing axis. If it merely
rephrases a dimension the pack already has, it is `DECORATIVE_AXIS` and rejected — a renamed axis is not a
new space. The registry is never mutated; the expanded pack is a copy.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from .embeddings import semantic_distance

TRANSFORMATION_STATES = ("TRANSFORMATIONAL", "DECORATIVE_AXIS", "INERT")


@dataclass
class TransformationResult:
    new_axis: str
    assumption_name: str
    status: str                   # TRANSFORMATIONAL | DECORATIVE_AXIS | INERT
    distance_to_existing: float   # min semantic distance of the new axis to every existing axis [0,1]
    expanded_pack: object = None  # a COPY of the pack with the new axis (None unless TRANSFORMATIONAL)
    why: str = ""

    def markdown(self) -> str:
        L = [f"### Transformation — {self.status}: new axis `{self.new_axis}`",
             f"- distance to existing axes: {self.distance_to_existing} (1 = a genuinely new dimension)",
             f"- {self.why}"]
        if self.status == "DECORATIVE_AXIS":
            L.append("- rejected: this 'new axis' collapses to a dimension the pack already has — a renamed "
                     "axis is not a new space.")
        elif self.status == "TRANSFORMATIONAL":
            L.append(f"- the engine can now explore the EXPANDED space (pack '{self.expanded_pack.name}' "
                     f"with axis '{self.new_axis}') — ideas impossible before are now reachable.")
        return "\n".join(L)


def _expand(pack, assumption, new_axis: str, priority: int, why: str):
    """Return a COPY of `pack` with the new breakable axis + assumption added. Never mutates the registry.
    The new axis sits OUTSIDE box_assumptions — it is a fresh degree of freedom, not part of the default box."""
    import copy
    p = copy.copy(pack)
    p.assumptions = list(pack.assumptions) + [assumption]
    p.dimension_of = {**pack.dimension_of, assumption.name: new_axis}
    p.axes = {**pack.axes, new_axis: {"priority": priority, "verdict": f"[invented axis] {why}"}}
    p.box_assumptions = set(pack.box_assumptions)
    p.__dict__.pop("_graph_cache", None)                 # force the cached graph to rebuild for the new shape
    return p


def transform_space(pack, anomaly: str, new_axis: str, priority: int = 2, embedder=None,
                    decorative_threshold: float = 0.4) -> TransformationResult:
    """Promote `anomaly` to a new breakable axis `new_axis`, if it is genuinely a new dimension. Returns a
    TransformationResult; on TRANSFORMATIONAL it carries an EXPANDED pack (a copy) the engine can explore."""
    from .generators import anomaly_to_assumption
    asm, _meta = anomaly_to_assumption(pack, anomaly, axis=new_axis)
    if not (asm.falsifier or "").strip():
        return TransformationResult(new_axis=new_axis, assumption_name=asm.name, status="INERT",
                                    distance_to_existing=0.0,
                                    why="the mined assumption has no falsifier — it cannot generate a candidate.")
    # measure the RAW anomaly against existing dimensions (not the boilerplate-wrapped assumption, whose
    # template text would dilute the overlap and let a paraphrase masquerade as a new axis).
    existing = [a.if_false for a in pack.assumptions] or [""]
    dist = round(min(semantic_distance(anomaly, e, embedder=embedder) for e in existing), 3)
    if dist < decorative_threshold:
        return TransformationResult(new_axis=new_axis, assumption_name=asm.name, status="DECORATIVE_AXIS",
                                    distance_to_existing=dist,
                                    why=f"too close (distance {dist}) to an existing assumption — a rebrand of a "
                                        f"dimension '{pack.name}' already has, not a new space.")
    expanded = _expand(pack, asm, new_axis, priority, why=f"mined from the anomaly: {anomaly[:60]}")
    return TransformationResult(new_axis=new_axis, assumption_name=asm.name, status="TRANSFORMATIONAL",
                                distance_to_existing=dist, expanded_pack=expanded,
                                why=f"the anomaly is far (distance {dist}) from every existing axis → a new "
                                    f"degree of freedom; '{pack.name}' has been expanded with axis '{new_axis}'.")


def propose_transformation(pack, foreign_pack=None, embedder=None) -> TransformationResult:
    """Auto-propose a transformation by mining an anomaly from a CROSS-DOMAIN blend: the emergent claim of
    blending `pack` with a distant domain is exactly a degree of freedom neither domain modelled. Names the
    new axis after the foreign domain's top axis. Falls back to a generic frontier anomaly with no foreign
    pack. Composes transformational creativity with conceptual blending."""
    from .generators import conceptual_blend
    from .pack import list_packs, get_pack
    from .generators.base import breakable
    if foreign_pack is None:
        others = [get_pack(n) for n in list_packs() if n not in (pack.name, "generic")]
        foreign_pack = next((p for p in others if breakable(p)), None)
    if foreign_pack is not None:
        blend = conceptual_blend(pack, foreign_pack)
        if blend is not None:
            foreign_axis = (foreign_pack.dimension_of.get(blend.assumptions[1].split("@")[0]) or "NOVEL")
            new_axis = f"{foreign_axis}_IN_{pack.name.upper()}"
            return transform_space(pack, anomaly=blend.negation, new_axis=new_axis, embedder=embedder)
    return transform_space(pack, anomaly="a residual the box discards as noise is itself structured signal",
                           new_axis="RESIDUAL_STRUCTURE", embedder=embedder)
