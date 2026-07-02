"""generators — the plural, disciplined idea generator.

The original generator could make one move: negate one pre-registered assumption, one axis at a time.
Applying the engine to itself surfaced a family of operators, grouped by what they do:

  breaking      break a hidden assumption        (recombine / invert / scale / transport / abduce)
  nonbreaking   create without breaking          (unify / instrument / reframe / dissolve)
  discovery     reach past the registry          (anomaly_to_assumption / self_spark)

`generate_candidates` runs the operators as a pool. The generator got richer; the falsifier did not get
weaker — every Candidate still owes its death to a world-test (see its `discipline` field).
"""
from __future__ import annotations
from typing import List

from .base import Candidate, breakable
from .breaking import (recombine_assumptions, invert_assumption, scale_break, transport_break,
                       what_would_have_to_be_true)
from .nonbreaking import unify, instrument, reframe, dissolve  # dissolve is pooled; the rest are by-hand
from .discovery import anomaly_to_assumption, self_spark
from .blending import conceptual_blend, blend_emergence, blend_domains

__all__ = [
    "Candidate", "breakable", "generate", "generate_candidates",
    "recombine_assumptions", "invert_assumption", "scale_break", "transport_break",
    "what_would_have_to_be_true", "unify", "instrument", "reframe", "dissolve",
    "anomaly_to_assumption", "self_spark",
    "conceptual_blend", "blend_emergence", "blend_domains",
]


def generate_candidates(pack, prompt: str = "", k_recombine: int = 2, scale_factor: int = 1000,
                        transport_from=None, abduce_target: str = "") -> List[Candidate]:
    """Run the generative operators on `pack` and return the pooled, un-certified candidates.

    Grouped by family for readability; the one declared HEURISTIC is the regime probe (we scale only the
    highest-priority break, to add one regime candidate rather than N of noise — tune via scale_factor).
    Divergence first; falsification stays mandatory downstream.
    """
    pool: List[Candidate] = []
    bk = breakable(pack)

    # breaking operators
    pool.extend(recombine_assumptions(pack, k=k_recombine))
    for assumption in bk:
        inv = invert_assumption(pack, assumption.name)
        if inv is not None:
            pool.append(inv)
    if bk:                                            # HEURISTIC: one regime probe, on the top-priority break
        top = max(bk, key=lambda a: pack.axes.get(pack.dimension_of[a.name], {}).get("priority", 1))
        scaled = scale_break(pack, top.name, factor=scale_factor)
        if scaled is not None:
            pool.append(scaled)

    # dissolve — "creativity by deletion" (remove a stage so the problem dissolves). Nominally a nonbreaking
    # operator, but it carries real box-distance: capability_value ablation measured it KEEPS (+0.034 VNS),
    # whereas its sibling nonbreaking ops (instrument/reframe/unify) are HARMFUL/DECORATIVE here and are
    # therefore left as by-hand building blocks, deliberately OUT of the scored divergent pool.
    for assumption in bk:
        dis = dissolve(pack, assumption.name)
        if dis is not None:
            pool.append(dis)

    # other generative moves (only when their input is supplied)
    if transport_from is not None:
        transported = transport_break(transport_from, pack)
        if transported is not None:
            pool.append(transported)
    if abduce_target:
        pool.append(what_would_have_to_be_true(pack, abduce_target))

    # synthesis from genuine contradictions.
    # Lazy import on purpose: dialectic imports generators.Candidate, so a top-level import here would be
    # a real generators↔dialectic cycle (it only "works" by relying on import order). This is not a smell.
    from ..dialectic import all_syntheses
    pool.extend(all_syntheses(pack))
    return pool


def generate(prompt: str, pack=None, **kwargs) -> List[Candidate]:
    """Select the domain pack for `prompt` (unless given) and run the plural generator."""
    if pack is None:
        from ..pack import select_pack
        pack, _ = select_pack(prompt)
    return generate_candidates(pack, prompt, **kwargs)
