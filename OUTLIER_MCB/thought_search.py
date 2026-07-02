"""thought_search — Tree-of-Thoughts search + Self-Refine + Reflexion, pruned by an EXTERNAL score.

Literature: Tree of Thoughts (Yao et al. 2023) — explore a tree of partial solutions; Self-Refine (Madaan
et al. 2023) — improve a candidate with feedback; Reflexion (Shinn et al. 2023) — turn failures into verbal
memory that steers the next attempt. The one non-negotiable discipline here, and the reason this is NOT just
a wrapper: PRUNING MUST USE AN EXTERNAL SCORE (a scorer, a test, a prior-art audit, or a human-required
flag) — never the model's own "this looks good". Self-judgment is exactly the loop OUTLIER_MCB refuses.

It composes the existing inverted-objective pieces (invent.novelty_search beam, push_further, reflect) into
an explicit tree with externally-scored pruning and a reusable ReflectionMemory. Deterministic.

Collaborators: invent.push_further (the Self-Refine successor), generators (expansion), creative_search
.structural_evaluator (the default EXTERNAL scorer), invent.reflect (the Reflexion seed).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from .generators import Candidate, generate_candidates, breakable, invert_assumption, dissolve, scale_break
from .invent import push_further


@dataclass
class ThoughtNode:
    candidate: Candidate
    score: float
    depth: int
    path: List[str] = field(default_factory=list)     # operator path from the root


@dataclass
class ThoughtTree:
    problem: str
    nodes: List[ThoughtNode] = field(default_factory=list)
    depth: int = 0
    branching: int = 0
    def best(self) -> Optional[ThoughtNode]:
        return max(self.nodes, key=lambda n: n.score) if self.nodes else None
    def frontier(self, k: int = 5) -> List[ThoughtNode]:
        return sorted(self.nodes, key=lambda n: -n.score)[:k]
    def markdown(self) -> str:
        b = self.best()
        L = [f"## thought_search — «{self.problem}»  (depth {self.depth}, branching {self.branching}, "
             f"{len(self.nodes)} nodes)"]
        if b:
            L.append(f"- best (external score {round(b.score, 3)}): {'→'.join(b.path)} → «{b.candidate.name}»")
        return "\n".join(L)


def prune_by_external_score(scored: List[ThoughtNode], keep: int) -> List[ThoughtNode]:
    """Keep the top-`keep` nodes by their EXTERNAL score. The scores were assigned by a scorer/test/audit,
    NOT by the generator judging itself — that is the whole point (no self-fooling pruning)."""
    return sorted(scored, key=lambda n: -n.score)[:max(1, keep)]


def _children(parent: Candidate, pack) -> List[Candidate]:
    names = parent.assumptions or [a.name for a in breakable(pack)]
    out = []
    for nm in names[:3]:
        for fn in (lambda n: invert_assumption(pack, n), lambda n: dissolve(pack, n),
                   lambda n: scale_break(pack, n, factor=1000)):
            c = fn(nm)
            if c is not None:
                out.append(c)
    return out


def thought_tree(problem: str, branching: int = 3, depth: int = 2, scorer: Optional[Callable] = None,
                 pack=None, repo=None) -> ThoughtTree:
    """Tree-of-Thoughts with externally-scored pruning. Each level expands the surviving nodes, scores the
    children with the EXTERNAL `scorer(candidate) -> float`, and keeps the top-`branching`. Returns the tree."""
    if pack is None:
        from .pack import select_pack
        pack, _ = select_pack(problem)
    if scorer is None:
        from .creative_search import structural_evaluator
        scorer = structural_evaluator(pack, repo)

    roots = generate_candidates(pack, problem)[:branching]
    frontier = [ThoughtNode(c, float(scorer(c)), 0, [c.operator]) for c in roots]
    frontier = prune_by_external_score(frontier, branching)
    all_nodes = list(frontier)
    for d in range(1, depth + 1):
        scored_children: List[ThoughtNode] = []
        for node in frontier:
            for ch in _children(node.candidate, pack):
                scored_children.append(ThoughtNode(ch, float(scorer(ch)), d, node.path + [ch.operator]))
        if not scored_children:
            break
        frontier = prune_by_external_score(scored_children, branching)   # EXTERNAL pruning, not self-judgment
        all_nodes.extend(frontier)
    return ThoughtTree(problem=problem, nodes=all_nodes, depth=depth, branching=branching)


def self_refine(candidate: Candidate, critique: str, evaluator: Callable, pack) -> Dict:
    """Self-Refine, disciplined: produce a refined successor (push it FARTHER from the box) and ACCEPT it
    only if the EXTERNAL `evaluator` score improves. A refinement that does not measurably improve is
    rejected — the critique is recorded, but 'it reads better' never counts. Returns the accepted candidate
    and the before/after scores."""
    before = float(evaluator(candidate))
    successor = push_further(candidate, pack)
    after = float(evaluator(successor))
    improved = bool(after > before and successor.name != candidate.name)   # a REAL external gain, not just a re-word
    return {"candidate": (successor if improved else candidate), "before": round(before, 3),
            "after": round(after, 3), "improved": improved, "critique": critique}


@dataclass
class ReflectionMemory:
    """Reflexion as a reusable memory: a LOST attempt becomes a verbal mutation HINT that steers the next
    generation (failure → frontier, not a silent retry). `record` stores a failure; `hints` returns the
    accumulated guidance; `seed_assumption` mines a new assumption to break from a failure (via invent.reflect)."""
    failures: List[Dict] = field(default_factory=list)

    def record(self, candidate: Candidate, reason: str) -> str:
        axis = candidate.breaks[0] if candidate.breaks else ""
        hint = (f"the move on '{axis or candidate.operator}' lost because: {reason}; "
                f"next, break a DIFFERENT axis or push the broken one further.")
        self.failures.append({"candidate": candidate.name, "axis": axis, "reason": reason, "hint": hint})
        return hint

    def hints(self) -> List[str]:
        return [f["hint"] for f in self.failures]

    def seed_assumption(self, lost_bet, pack):
        """Mine a NEW assumption to break out of a lost bet (Reflexion → next frontier)."""
        from .invent import reflect
        return reflect(lost_bet, pack)
