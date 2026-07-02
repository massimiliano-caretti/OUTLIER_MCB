"""generators.breaking — operators that create by BREAKING a hidden assumption.

  recombine_assumptions        break two assumptions on distinct axes at once (TRIZ-style contradiction)
  invert_assumption            swap the roles an assumption fixes (given ↔ target)
  scale_break                  push the regime ("what at Nx?") until a small-scale-true assumption fails
  transport_break              carry a break that survived in one domain into another, as an analogy
  what_would_have_to_be_true   backward-chain from a desired capability to the assumptions that must be false

Each returns a Candidate whose `discipline` names the world-test it must still survive.
"""
from __future__ import annotations
from itertools import combinations
from typing import List, Optional

from .base import Candidate, breakable, data_req, radical_negation, axes_by_priority


def recombine_assumptions(pack, k: int = 2, max_candidates: int = 6) -> List[Candidate]:
    """Break k assumptions on DISTINCT axes at once — the fertile regime: designs that are sterile as a
    single break but decisive as a pair."""
    req = data_req(pack)
    priority = lambda a: pack.axes.get(pack.dimension_of[a.name], {}).get("priority", 1)
    out: List[Candidate] = []
    for combo in combinations(sorted(breakable(pack), key=lambda a: -priority(a)), k):
        axes = [pack.dimension_of[a.name] for a in combo]
        if len(set(axes)) != k:                      # require distinct axes
            continue
        out.append(Candidate(
            name="×".join(a.name for a in combo),
            operator="recombine", breaks=sorted(set(axes)), assumptions=[a.name for a in combo],
            negation=" AND ".join(radical_negation(a) for a in combo),
            needs=sorted({t for a in combo for t in req.get(a.name, [])}),
            discipline=("parsimony: it must beat the ABLATION of EACH single break on the same world-test "
                        "(synergy>0); if either break alone matches it, it collapses to that single break."),
        ))
        if len(out) >= max_candidates:
            break
    return out


def invert_assumption(pack, name: str) -> Optional[Candidate]:
    """Swap what the assumption treats as given with what it treats as the target (lateral reversal)."""
    a = pack.by_name().get(name)
    if a is None or not pack.dimension_of.get(name):
        return None
    return Candidate(
        name=f"inv({name})", operator="invert", breaks=[pack.dimension_of[name]], assumptions=[name],
        negation=(f"INVERT: treat what '{name}' fixes as the variable to optimize, and what it optimizes "
                  f"as a constraint — '{a.description.rstrip('.')}' becomes the unknown, not the given."),
        discipline=("symmetric world-test: rebuild the world with the roles swapped; if the inverted idea "
                    "does NOT collapse when the original symmetry is restored, the gain was leakage."),
    )


def scale_break(pack, name: str, factor: int = 1000) -> Optional[Candidate]:
    """Push the regime: a true-at-small-scale assumption can become false past a threshold."""
    a = pack.by_name().get(name)
    if a is None or not pack.dimension_of.get(name):
        return None
    return Candidate(
        name=f"scale({name},{factor}x)", operator="scale", breaks=[pack.dimension_of[name]], assumptions=[name],
        negation=(f"REGIME: at {factor}× (more instances / less supervision / more extreme cost), does "
                  f"'{a.description.rstrip('.')}' still hold? Likely not: {a.if_false}"),
        discipline=("must show a CROSSOVER: it wins only BEYOND a threshold scale and ties/loses below it. "
                    "If it wins at every scale, it is ordinary engineering, not a regime shift."),
    )


def transport_break(src_pack, dst_pack, assumption_name: str = "") -> Optional[Candidate]:
    """Map a break from src_pack onto dst_pack's axes by priority rank — a disciplined analogy. The
    transported idea enters dst with ZERO novelty credit and must pass dst's own collision audit."""
    candidates = breakable(src_pack)
    if not candidates:
        return None
    a = src_pack.by_name().get(assumption_name) or max(
        candidates, key=lambda x: src_pack.axes.get(src_pack.dimension_of[x.name], {}).get("priority", 1))
    src_rank, dst_rank = axes_by_priority(src_pack), axes_by_priority(dst_pack)
    if not dst_rank:
        return None
    src_axis = src_pack.dimension_of[a.name]
    dst_axis = dst_rank[min(src_rank.index(src_axis) if src_axis in src_rank else 0, len(dst_rank) - 1)]
    dst_families = ", ".join(sorted(set(dst_pack.known_families))) or "the destination family"
    return Candidate(
        name=f"transport({a.name}@{src_pack.name}→{dst_pack.name}:{dst_axis})",
        operator="transport", breaks=[dst_axis], assumptions=[a.name],
        negation=(f"by analogy to {src_pack.name} (where breaking '{a.name}' is decisive): on the '{dst_axis}' "
                  f"axis of {dst_pack.name}, assume false → {a.if_false}"),
        needs=sorted(dst_pack.info_kinds)[:1],
        discipline=(f"analogy GENERATES, it does not certify: it enters with zero novelty credit and must beat "
                    f"a {dst_families} baseline on a {dst_pack.name} world-test; if the analogy doesn't transfer, it dies."),
    )


def what_would_have_to_be_true(pack, target: str) -> Candidate:
    """Goal-directed (abductive) generation: given a desired capability, which assumptions MUST be false,
    and what would each break require? The opposite of blind forward enumeration."""
    req = data_req(pack)
    bk = breakable(pack)
    chain = "; ".join(f"'{a.name}' false ⇒ {a.if_false}" for a in bk)
    return Candidate(
        name=f"abduce({target[:32]})", operator="abduce",
        breaks=sorted({pack.dimension_of[a.name] for a in bk}), assumptions=[a.name for a in bk],
        negation=f"to make possible «{target}», these assumptions must be false → {chain}",
        needs=sorted({t for a in bk for t in req.get(a.name, [])}),
        discipline=("each link inherits its own falsifier; the chain is valid ONLY if every world-test passes. "
                    "A single surviving link is not the capability — it is one necessary condition."),
    )
