"""compression — creativity as COMPRESSION (MDL): the best idea explains the most with the least.

Distance and extrapolation reward being far. But a far idea can be baroque. The deepest creativity is
the opposite: an idea that, once accepted, lets you DELETE structure — that subsumes several assumptions
or families under one principle. Following Solomonoff/Schmidhuber's view of creativity as compression,
`compression_gain` scores how much an idea would shorten the description of the domain. A unification
folds two assumptions into one; a deletion removes a stage; a recombination can explain with one
mechanism what several families did separately. The higher the compression, the deeper the idea — a
metric no standard idea engine applies.

Collaborators: generators.Candidate (the idea), kernel.graph_of (how much rests on each assumption).
"""
from __future__ import annotations
from typing import Dict


def _description_length(pack) -> int:
    """A crude description length of the domain: its assumptions plus its distinct known families."""
    return len(pack.assumptions) + len(set(pack.known_families))


def compression_gain(candidate, pack) -> Dict:
    """How much accepting `candidate` would shorten the domain's description, in [0,1].

    subsumed   = assumptions the idea folds into one principle (unify=2, dissolve=1+dependents, recombine=axes)
    explains   = known families the broken assumption underwrote (now expressed by the single principle)
    gain       = (subsumed + explains − 1) / description_length  — the fraction of the domain it absorbs
    """
    from . import kernel
    g = kernel.graph_of(pack)
    op = candidate.operator
    names = candidate.assumptions or []

    # Only FOLDING moves compress (they reduce description length). BREAKING moves (recombine/invert/
    # scale/transport/abduce/dialectic) add or relocate structure — they do not compress, by definition.
    if op == "unify":
        subsumed = len(names)                                   # two faces of one object → one
    elif op == "dissolve":
        seed = names[0] if names else ""
        dependents = len(g.in_edges(seed, "depends_on")) + len(g.out_edges(seed, "blocks"))
        subsumed = 1 + dependents                               # the stage plus what only existed for it
    elif op == "reframe":
        subsumed = 1                                            # re-expresses one object more economically
    else:
        return {"subsumed": 0, "explains": 0, "description_length": _description_length(pack),
                "compression_gain": 0.0, "principle": "no compression (a breaking move adds structure)"}

    by = pack.by_name()
    explains = len({fam for n in names for fam in (by[n].assumed_by if n in by else [])})
    dl = max(1, _description_length(pack))
    gain = round(max(0.0, (subsumed + explains - 1)) / dl, 3)
    return {"subsumed": subsumed, "explains": explains, "description_length": dl,
            "compression_gain": min(1.0, gain),
            "principle": f"one principle replaces {subsumed} assumption(s)"
                         + (f" and re-expresses {explains} known family/ies" if explains else "")}


def most_compressing(candidates, pack):
    """Pick the candidate that compresses the domain most — the deepest, not merely the farthest."""
    scored = [(compression_gain(c, pack)["compression_gain"], c) for c in candidates]
    return max(scored, key=lambda x: x[0])[1] if scored else None
