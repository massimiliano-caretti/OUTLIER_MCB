"""evolution_ops — controlled mutation & recombination operators for evolving candidates.

These wrap the existing generative operators (generators.*) into the AlphaEvolve-useful shape: each returns
a NEW candidate WITH its provenance — parent_ids, the operator name, a rationale, the expected functional
change, and a risk. The point is invention by iteration: change the mechanism (not the wording), recombine
distant parents, add a falsifier, simplify/generalize, push away from prior art. Functional content must
change — a rename is not a mutation.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional

from .generators import (invert_assumption, scale_break, dissolve, conceptual_blend, transport_break,
                         what_would_have_to_be_true, breakable, Candidate)


@dataclass
class MutationResult:
    candidate: Candidate
    parent_ids: List[str] = field(default_factory=list)
    mutation_operator: str = ""
    rationale: str = ""
    expected_change: str = ""
    risk: str = "low"


def _names(parent) -> List[str]:
    return list(getattr(parent, "assumptions", []) or [])


def _foreign(pack):
    from .pack import list_packs, get_pack
    return next((get_pack(n) for n in list_packs() if n not in (pack.name, "generic") and breakable(get_pack(n))), None)


def _r(child, pid, op, rationale, change, risk):
    return None if child is None else MutationResult(child, [pid] if pid else [], op, rationale, change, risk)


def mutate_assumption(pack, parent, parent_id: str = "") -> Optional[MutationResult]:
    """Break a DIFFERENT assumption than the parent's — move to an unexplored axis."""
    cur = set(_names(parent))
    nxt = next((a.name for a in breakable(pack) if a.name not in cur), None)
    return _r(invert_assumption(pack, nxt) if nxt else None, parent_id, "mutate_assumption",
              f"break '{nxt}' instead of the parent's axis", "explores a different hidden assumption", "low")


def mutate_mechanism(pack, parent, parent_id: str = "") -> Optional[MutationResult]:
    """Same assumption, DIFFERENT mechanism (scale/dissolve vs invert) — changes functional behaviour, not the name."""
    nm = (_names(parent) or [a.name for a in breakable(pack)])[0]
    child = scale_break(pack, nm, factor=1000) or dissolve(pack, nm)
    return _r(child, parent_id, "mutate_mechanism", f"change HOW '{nm}' is broken (regime/deletion, not wording)",
              "different functional mechanism on the same axis", "medium")


def mutate_objective(pack, parent, target: str = "a stronger, verifiable objective", parent_id: str = "") -> Optional[MutationResult]:
    """Abduce backward from a DESIRED capability — change the objective/constraint, not the surface idea."""
    return _r(what_would_have_to_be_true(pack, target), parent_id, "mutate_objective",
              f"backward-chain from «{target}» to the assumptions that must be false", "redefines the metric/constraint", "medium")


def add_falsifier(pack, parent, parent_id: str = "") -> Optional[MutationResult]:
    """Strengthen a candidate by attaching an explicit falsifier / negative control to its discipline."""
    if parent is None:
        return None
    child = Candidate(name=f"{getattr(parent, 'name', 'cand')}+falsifier", operator=getattr(parent, "operator", "proposed"),
                      breaks=list(getattr(parent, "breaks", []) or []), assumptions=_names(parent),
                      negation=getattr(parent, "negation", ""), needs=list(getattr(parent, "needs", []) or []),
                      discipline=(getattr(parent, "discipline", "") + " | ADDED FALSIFIER: design a negative control "
                                  "that MUST fail (shuffle the broken structure); if it does not collapse, the gain is leakage."))
    return MutationResult(child, [parent_id] if parent_id else [], "add_falsifier",
                          "make the candidate falsifiable with an explicit negative control",
                          "no new mechanism — raises verifiability", "low")


def simplify_candidate(pack, parent, parent_id: str = "") -> Optional[MutationResult]:
    """Reduce complexity (delete a stage) while keeping a break — parsimony without losing the mechanism."""
    nm = (_names(parent) or [a.name for a in breakable(pack)])[0]
    return _r(dissolve(pack, nm), parent_id, "simplify_candidate", f"dissolve the stage around '{nm}'",
              "fewer moving parts, same broken axis", "low")


def generalize_candidate(pack, parent, parent_id: str = "") -> Optional[MutationResult]:
    """Broaden the regime the candidate claims — generalize while staying falsifiable."""
    nm = (_names(parent) or [a.name for a in breakable(pack)])[0]
    return _r(scale_break(pack, nm, factor=1000), parent_id, "generalize_candidate",
              f"push '{nm}' to a 1000× regime", "wider domain of validity (must show a crossover)", "medium")


def recombine_distant(pack, parent_a, parent_b=None, parent_ids: Optional[List[str]] = None) -> Optional[MutationResult]:
    """Blend the pack with a DISTANT domain — emergent structure neither parent has (uses two parents)."""
    fp = _foreign(pack)
    child = conceptual_blend(pack, fp) if fp else None
    return None if child is None else MutationResult(child, list(parent_ids or []), "recombine_distant",
                                                     f"blend {pack.name} with the distant domain {fp.name}",
                                                     "emergent cross-domain mechanism", "high")


def cross_domain_transfer(pack, parent=None, parent_id: str = "") -> Optional[MutationResult]:
    """Import a break that worked in a distant domain into this one (analogy, zero novelty credit)."""
    fp = _foreign(pack)
    child = transport_break(fp, pack) if fp else None
    return _r(child, parent_id, "cross_domain_transfer", f"carry a {fp.name if fp else '—'} break into {pack.name}",
              "an analogical mechanism transferred across domains", "high")


def novelty_push(pack, parent, parent_id: str = "") -> Optional[MutationResult]:
    """Choose, among the available moves, the one FARTHEST from the box (max box_distance) — force distance
    from prior art / the archive."""
    from .invent import box_distance
    nm = (_names(parent) or [a.name for a in breakable(pack)])[0]
    fp = _foreign(pack)
    cands = [c for c in (invert_assumption(pack, nm), scale_break(pack, nm, factor=1000), dissolve(pack, nm),
                         conceptual_blend(pack, fp) if fp else None) if c is not None]
    if not cands:
        return None
    best = max(cands, key=lambda c: box_distance(c, pack))
    return MutationResult(best, [parent_id] if parent_id else [], "novelty_push",
                          "pick the move farthest from the box (max box_distance)",
                          "maximizes distance from the known", "high")


ALL_OPERATORS = [mutate_assumption, mutate_mechanism, mutate_objective, add_falsifier, simplify_candidate,
                 generalize_candidate, recombine_distant, cross_domain_transfer, novelty_push]
