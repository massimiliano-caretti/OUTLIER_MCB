"""generators.blending — conceptual blending: fuse TWO domains into an EMERGENT structure.

Computational-creativity gap surfaced by interrogating the engine on itself: it can recombine assumptions
WITHIN one pack (recombine_assumptions) and map a single break ACROSS packs (transport_break), but it has
no operator for the mechanism cognitive science credits with much of human invention — conceptual blending
(Fauconnier & Turner): take two input spaces, find their shared (generic) structure, and project them into
a BLEND that carries EMERGENT structure present in neither parent (e.g. evolution ⊕ search = a genetic
algorithm; annealing ⊕ optimization = simulated annealing).

This operator GENERATES such a blend; it certifies nothing. Its `discipline` names the emergence gate it
must still survive: the blend has to pass a world-test that NEITHER parent break passes alone — otherwise
it collapses back to a transport (one domain borrowing from the other) and is not a real blend. Emergence
is measured by the pluggable semantic distance between the two parent breaks (far domains → more surprising
blend; inject a real embedder for semantic, not lexical, distance).
"""
from __future__ import annotations
from typing import Optional

from ..embeddings import semantic_distance
from .base import Candidate, breakable, data_req


def blend_emergence(statement_a: str, statement_b: str, embedder=None) -> float:
    """Emergence potential in [0,1]: how far apart the two parent breaks are. 0 = the same idea (a blend
    with itself adds nothing); →1 = distant domains whose integration is most likely to yield structure
    neither had. Uses the pluggable semantic distance (lexical default; inject an embedder for real semantics)."""
    return round(semantic_distance(statement_a or "", statement_b or "", embedder=embedder), 3)


def _pick(pack, name: str = ""):
    bk = breakable(pack)
    if not bk:
        return None
    if name:
        return pack.by_name().get(name)
    return max(bk, key=lambda a: pack.axes.get(pack.dimension_of[a.name], {}).get("priority", 1))


def conceptual_blend(pack_a, pack_b, name_a: str = "", name_b: str = "", embedder=None) -> Optional[Candidate]:
    """Blend a break from `pack_a` with a break from `pack_b` into an emergent cross-domain assumption.
    Returns a Candidate (operator='blend') whose negation lives in a hybrid space that is BOTH domains at
    once, or None if either pack has no breakable assumption."""
    a = _pick(pack_a, name_a)
    b = _pick(pack_b, name_b)
    if a is None or b is None:
        return None
    axis_a = pack_a.dimension_of.get(a.name, "—")
    axis_b = pack_b.dimension_of.get(b.name, "—")
    emergence = blend_emergence(a.if_false, b.if_false, embedder=embedder)
    req = {**data_req(pack_a), **data_req(pack_b)}
    negation = (f"BLEND {pack_a.name}⊕{pack_b.name}: in a hybrid space that is at once «{pack_a.box_name}» "
                f"and «{pack_b.box_name}», break BOTH jointly — «{a.if_false}» AND «{b.if_false}» — and seek "
                f"the EMERGENT property present in neither domain alone.")
    return Candidate(
        name=f"blend({a.name}@{pack_a.name} ⊕ {b.name}@{pack_b.name})",
        operator="blend",
        breaks=sorted({axis_a, axis_b}),
        assumptions=[f"{a.name}@{pack_a.name}", f"{b.name}@{pack_b.name}"],
        negation=negation,
        needs=sorted(set(req.get(a.name, [])) | set(req.get(b.name, []))),
        emergence=emergence,
        discipline=(f"emergence gate (emergence={emergence}): the blend must pass a world-test that NEITHER "
                    f"parent break passes alone — if it reduces to '{pack_a.name}' or '{pack_b.name}' alone it "
                    f"collapses to a transport, not a blend. A blend of a domain with itself (emergence≈0) is sterile."),
    )


def blend_domains(name_a: str, name_b: str, name_a_assumption: str = "", name_b_assumption: str = "",
                  embedder=None) -> Optional[Candidate]:
    """Convenience: look up two registered packs by name and blend them."""
    from ..pack import get_pack
    return conceptual_blend(get_pack(name_a), get_pack(name_b), name_a_assumption, name_b_assumption, embedder)
