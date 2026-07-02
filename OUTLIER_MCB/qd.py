"""qd — Quality-Diversity (MAP-Elites) over the idea space.

Literature: Mouret & Clune, "Illuminating search spaces by mapping elites" (MAP-Elites, 2015); Pugh,
Soros & Stanley, "Quality Diversity: A New Frontier for Evolutionary Computation" (2016). The idea of QD
is to stop optimizing for a SINGLE best solution and instead ILLUMINATE the search space: keep the best
solution found in EACH region of a behavioral map, so the output is a diverse atlas of high-quality
solutions rather than one peak. That is exactly OUTLIER_MCB's thesis — divergent, structured novelty
disciplined by quality — made into a data structure.

Mapping to this library:
  • the BEHAVIOR space is the structural shape of an idea (how complex, how abstract, which axes it breaks),
    NOT its objective value — two ideas in different cells are *kinds* of ideas, not better/worse ones;
  • QUALITY is the existing grounded composite (scoring.score_idea), so each cell keeps the most
    disciplined idea of its kind — diversity WITHOUT abandoning falsifiability;
  • the archive replaces "a flat list of the top-N" with a MAP of elites, so a strong-but-ordinary idea
    can no longer crowd out a weaker-but-genuinely-different one (the failure mode of plain ranking).

Pure-Python, deterministic, no heavy deps. Collaborators: generators.Candidate (the genome),
scoring.score_idea (the quality), pack.axes (the behavior dimensions).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from .generators import Candidate

# operator → architectural abstraction level (1 implementation · 2 interface · 3 architecture).
# A deletion / cross-domain transport / inversion restructures the whole design (3); a recombination or
# reframing changes an interface (2); instrumenting or scaling tweaks an implementation (1).
_ABSTRACTION = {"instrument": 1, "scale": 1, "negate": 1,
                "recombine": 2, "reframe": 2, "unify": 2, "abduce": 2, "proposed": 2,
                "invert": 3, "dissolve": 3, "transport": 3}


@dataclass
class BehaviorDescriptor:
    """The structural 'behavior' of a Candidate — its KIND, not its value — used to place it on the map.

    Dimensions (Quality-Diversity behavior characterization):
      • complexity        — a structural-complexity proxy standing in for cyclomatic complexity (which is
                            not computable on a not-yet-implemented idea): how many axes/assumptions/new
                            inputs the move entangles. PLACEHOLDER for true cyclomatic complexity once a
                            candidate is materialized into code.
      • abstraction_level — ordinal 1/2/3 (implementation / interface / architecture), from the operator.
      • axes_vector       — a multi-hot vector over the DomainPack's axes: which axes the idea breaks.
    """
    complexity: int
    abstraction_level: int
    axes_vector: Tuple[int, ...]
    axis_names: Tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def of(cls, candidate: Candidate, pack) -> "BehaviorDescriptor":
        axes = tuple(pack.axes.keys()) if pack is not None else tuple(sorted(set(candidate.breaks)))
        broken = set(candidate.breaks)
        axes_vector = tuple(1 if a in broken else 0 for a in axes)
        # structural-complexity proxy (cyclomatic-complexity placeholder): entangled axes + assumptions + new inputs
        complexity = len(set(candidate.breaks)) + len(candidate.assumptions) + len(candidate.needs)
        abstraction = _ABSTRACTION.get(candidate.operator, 2)
        return cls(complexity=complexity, abstraction_level=abstraction,
                   axes_vector=axes_vector, axis_names=axes)

    def vector(self) -> Tuple[int, ...]:
        """The full descriptor as one flat vector (complexity, abstraction, *axes_vector)."""
        return (self.complexity, self.abstraction_level) + self.axes_vector


def _complexity_bin(c: int) -> int:
    """Coarsen complexity into low/medium/high so the map has cells, not a unique key per idea."""
    return 0 if c <= 2 else (1 if c <= 4 else 2)


@dataclass
class QDArchive:
    """A MAP-Elites grid: one elite (the highest-quality idea) per behavioral cell.

    grid: {cell_key: (quality, Candidate)} where cell_key = (complexity_bin, abstraction_level, axes_signature).
    Adding a candidate computes its behavior cell and keeps it ONLY if the cell is empty or the newcomer's
    quality beats the incumbent's — the MAP-Elites elitism rule, which yields an atlas of diverse, each-best-of-kind
    ideas instead of a single optimum.
    """
    pack: object = None
    repo: object = None
    quality_fn: Optional[Callable[[Candidate], float]] = None
    grid: Dict[Tuple, Tuple[float, Candidate]] = field(default_factory=dict)
    _order: List[Tuple] = field(default_factory=list)   # insertion order of cells, for deterministic sampling
    _cursor: int = 0

    def _quality(self, candidate: Candidate) -> float:
        if self.quality_fn is not None:
            return float(self.quality_fn(candidate))
        from .scoring import score_idea
        return float(score_idea(candidate, pack=self.pack, repo=self.repo)["composite"])

    def cell_of(self, candidate: Candidate) -> Tuple:
        """The discrete behavioral cell a candidate maps to (its coordinates on the map)."""
        bd = BehaviorDescriptor.of(candidate, self.pack)
        return (_complexity_bin(bd.complexity), bd.abstraction_level, bd.axes_vector)

    def add(self, candidate: Candidate, quality: Optional[float] = None) -> bool:
        """Place a candidate on the map. Returns True if it became (or replaced) the elite of its cell.
        MAP-Elites rule: keep it iff the cell is empty OR its quality exceeds the incumbent's."""
        q = self._quality(candidate) if quality is None else float(quality)
        cell = self.cell_of(candidate)
        incumbent = self.grid.get(cell)
        if incumbent is None or q > incumbent[0]:
            if incumbent is None:
                self._order.append(cell)
            self.grid[cell] = (q, candidate)
            return True
        return False

    # ── illumination metrics ──
    def coverage(self) -> int:
        """How many distinct behavioral cells are filled (the breadth of the illumination)."""
        return len(self.grid)

    def qd_score(self) -> float:
        """The QD-score: total quality summed across all filled cells (breadth × depth in one number)."""
        return round(sum(q for q, _ in self.grid.values()), 3)

    def elites(self) -> List[Tuple[Tuple, float, Candidate]]:
        """Every elite as (cell_key, quality, candidate), best quality first."""
        return sorted(((cell, q, c) for cell, (q, c) in self.grid.items()), key=lambda t: -t[1])

    def best(self) -> Optional[Candidate]:
        el = self.elites()
        return el[0][2] if el else None

    def sample(self) -> Optional[Candidate]:
        """Pick a parent to mutate. DETERMINISTIC (round-robin over filled cells in insertion order) so the
        QD loop stays reproducible — MAP-Elites' usual uniform-random selection would break determinism."""
        if not self._order:
            return None
        cell = self._order[self._cursor % len(self._order)]
        self._cursor += 1
        return self.grid[cell][1]

    def filled_descriptors(self) -> List[Dict]:
        """Human-readable descriptors of the filled cells (for goal-setting / reporting)."""
        out = []
        for cell, (q, c) in self.grid.items():
            cbin, abstraction, axes_vec = cell
            broken = [a for a, on in zip(BehaviorDescriptor.of(c, self.pack).axis_names, axes_vec) if on]
            out.append({"cell": cell, "quality": round(q, 3), "complexity": ["low", "medium", "high"][cbin],
                        "abstraction": ["", "implementation", "interface", "architecture"][abstraction],
                        "breaks": broken, "candidate": c.name})
        return sorted(out, key=lambda d: -d["quality"])

    def empty_regions(self, max_regions: int = 6) -> List[Dict]:
        """Behavioral regions the map has NOT yet filled (or filled only weakly) — the frontier of the
        search, and the input to the intrinsic goal-setter (goal_setter.propose_goal)."""
        axes = tuple(self.pack.axes.keys()) if self.pack is not None else ()
        filled = set(self.grid)
        want = []
        for abstraction in (1, 2, 3):
            for ai, axis in enumerate(axes):
                sig = tuple(1 if i == ai else 0 for i in range(len(axes)))
                for cbin in (0, 1, 2):
                    cell = (cbin, abstraction, sig)
                    if cell not in filled:
                        want.append({"cell": cell, "complexity": ["low", "medium", "high"][cbin],
                                     "abstraction": ["", "implementation", "interface", "architecture"][abstraction],
                                     "breaks": [axis]})
        return want[:max_regions]

    def markdown(self) -> str:
        L = [f"### QD map (MAP-Elites) — coverage {self.coverage()} cells · QD-score {self.qd_score()}"]
        for d in self.filled_descriptors()[:12]:
            L.append(f"- **{d['abstraction']}/{d['complexity']}** breaks {d['breaks'] or ['—']} → "
                     f"«{d['candidate']}» (quality {d['quality']})")
        return "\n".join(L)
