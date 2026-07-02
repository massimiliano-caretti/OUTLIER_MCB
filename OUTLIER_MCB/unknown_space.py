"""unknown_space — push generation toward what has NOT been explored, not the average of the seen.

To invent, the engine must look where it has not: assumptions not yet broken, axes with no attempt, domains
not yet transferred from, clusters of failure to avoid, and a novelty frontier of diverse-but-valid ideas.
This reads a pack + an EvolutionMemory and reports those regions, with WHY each is worth attacking — reusing
the assumption graph and the evolutionary record rather than guessing.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional


def explored_assumptions(memory, problem: Optional[str] = None) -> set:
    recs = memory.by_problem(problem) if problem else memory.all()
    return {a for r in recs for a in r.broken_assumptions}


def unexplored_assumptions(pack, memory, problem: Optional[str] = None) -> List[str]:
    """Breakable assumptions of `pack` that the memory has NOT yet broken — the obvious frontier."""
    done = explored_assumptions(memory, problem)
    return [a.name for a in pack.assumptions if pack.dimension_of.get(a.name) and a.name not in done]


def unexplored_axes(pack, memory, problem: Optional[str] = None) -> List[str]:
    """Axes of `pack` with NO broken assumption yet — whole dimensions left untouched."""
    done = explored_assumptions(memory, problem)
    touched = {pack.dimension_of[a] for a in done if a in pack.dimension_of}
    return sorted(set(pack.axes) - touched)


def failure_clusters(memory, problem: Optional[str] = None) -> Dict[str, int]:
    """How many times each broken assumption FAILED — a cluster to avoid re-attacking the same way."""
    recs = memory.by_problem(problem) if problem else memory.all()
    out: Dict[str, int] = {}
    for r in recs:
        if not r.correctness_passed:
            for a in r.broken_assumptions:
                out[a] = out.get(a, 0) + 1
    return out


def novelty_frontier(memory, k: int = 5, problem: Optional[str] = None, embedder=None) -> List:
    """The frontier of DIVERSE, VALID candidates: verified records, greedily spread by semantic distance —
    not the single best, but the varied edge to push outward from."""
    from .embeddings import semantic_distance
    recs = [r for r in (memory.by_problem(problem) if problem else memory.all()) if r.correctness_passed]
    recs.sort(key=lambda r: -r.score)
    frontier: List = []
    for r in recs:
        if len(frontier) >= k:
            break
        txt = f"{r.candidate_name} {r.claim}"
        if all(semantic_distance(txt, f"{c.candidate_name} {c.claim}", embedder=embedder) > 0.15 for c in frontier):
            frontier.append(r)
    return frontier


@dataclass
class UnknownRegion:
    unexplored_assumptions: List[str] = field(default_factory=list)
    unexplored_axes: List[str] = field(default_factory=list)
    saturated_assumptions: List[str] = field(default_factory=list)   # failed repeatedly — avoid re-attacking the same way
    why: str = ""


def suggest_unknown_region(problem: str, memory, pack) -> UnknownRegion:
    """The next region worth attacking: assumptions/axes not yet broken, minus those that already failed
    repeatedly (attack THOSE with a different mechanism, not the same one)."""
    clusters = failure_clusters(memory, problem)
    saturated = sorted([a for a, n in clusters.items() if n >= 2])
    unexp = unexplored_assumptions(pack, memory, problem)
    axes = unexplored_axes(pack, memory, problem)
    why = (f"{len(unexp)} assumption(s) and {len(axes)} axis/axes are untouched; "
           f"{len(saturated)} assumption(s) failed repeatedly — re-attack those only with a NEW mechanism.")
    return UnknownRegion(unexplored_assumptions=unexp, unexplored_axes=axes, saturated_assumptions=saturated, why=why)


def recommend_next_mutations(memory, pack, problem: Optional[str] = None) -> List[Dict]:
    """Concrete next moves with a reason: explore each unexplored assumption; for repeatedly-failed ones,
    change the MECHANISM rather than retry the same break."""
    region = suggest_unknown_region(problem or "", memory, pack)
    out = [{"operator": "mutate_assumption", "target": a, "why": "assumption not yet broken — opens a new axis"}
           for a in region.unexplored_assumptions[:4]]
    out += [{"operator": "mutate_mechanism", "target": a, "why": "this break failed before — change the mechanism, not the name"}
            for a in region.saturated_assumptions[:3]]
    if not region.unexplored_assumptions:
        out.append({"operator": "recombine_distant", "target": "cross-domain",
                    "why": "all known axes explored — invent an emergent mechanism via a distant blend"})
    return out
