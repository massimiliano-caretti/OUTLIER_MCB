"""dialectic — synthesis of CONTRADICTION: thesis + antithesis → a new object that needs both.

`recombine` ANDs two breaks that happen to be compatible. Dialectic does the opposite: it seeks two
assumptions in genuine TENSION (one blocks the other in the typed graph) and synthesizes the OBJECT
whose existence resolves the contradiction — not a compromise between them, but a third thing that can
only exist where both are simultaneously broken. This is TRIZ contradiction-resolution as a first-class
generative move: the hardest, most original ideas live exactly where two requirements seem mutually
exclusive. No standard idea engine generates from contradiction on purpose.

Collaborators: kernel.graph_of (to find real tensions), generators.Candidate (the synthesized object).
"""
from __future__ import annotations
from typing import List, Optional

from .generators import Candidate


def tensions(pack) -> List[tuple]:
    """Pairs of assumptions in genuine tension (A blocks B) — the seeds for a synthesis."""
    from . import kernel
    g = kernel.graph_of(pack)
    return [(s, d) for s, r, d, _ in g.edges if r == "blocks" and s in g.nodes and d in g.nodes]


def dialectic(pack, name_a: str = "", name_b: str = "") -> Optional[Candidate]:
    """Synthesize the object that resolves a contradiction. With no pair given, pick the strongest tension
    in the pack. Returns a Candidate that breaks BOTH axes at once and names the third thing."""
    by = pack.by_name()
    if name_a and name_b:
        pair = (name_a, name_b)
    else:
        ts = tensions(pack)
        if not ts:
            return None
        pair = ts[0]
    a, b = by.get(pair[0]), by.get(pair[1])
    if a is None or b is None:
        return None
    axis_a, axis_b = pack.dimension_of.get(a.name, "—"), pack.dimension_of.get(b.name, "—")
    return Candidate(
        name=f"synthesis({a.name}⊕{b.name})", operator="dialectic",
        breaks=sorted({axis_a, axis_b}), assumptions=[a.name, b.name],
        negation=(f"THESIS: {a.description.rstrip('.')}; ANTITHESIS: {b.if_false}. "
                  f"SYNTHESIS: an object that exists ONLY where both are broken at once — it makes "
                  f"'{a.name}' and '{b.name}' two views of one mechanism, dissolving their conflict."),
        needs=[],
        discipline=("must be a genuine THIRD object, not a compromise: show a world where neither breaking "
                    "'{0}' alone nor breaking '{1}' alone works, but the synthesis does. If a weighted "
                    "trade-off between them matches it, it was no synthesis.".format(a.name, b.name)),
    )


def all_syntheses(pack) -> List[Candidate]:
    """Synthesize an object for every genuine tension in the pack."""
    out = []
    for s, d in tensions(pack):
        c = dialectic(pack, s, d)
        if c:
            out.append(c)
    return out
