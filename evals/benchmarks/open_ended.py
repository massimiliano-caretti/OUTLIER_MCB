"""open_ended — a POET-like substrate: the engine MANUFACTURES its own increasing-difficulty problems.

The assumption this breaks (meta pack axis EXPLORATION): `problem_space_is_static` — that the engine only SOLVES
a fixed benchmark. A fixed set has a ceiling; real exploration generates NEW, HARDER problems and climbs them.
But — and this is the whole point of OUTLIER_MCB — a generated problem is worthless unless it can be settled
WITHOUT the engine's own opinion. So every generated problem here carries the full anti-autoreferential apparatus:

  • KNOWN ground truth   — a symbolic law fixed BY CONSTRUCTION (`sym`), not declared by the proposal;
  • external resolver    — R²>0.999 on held-out samples AND SymPy symbolic equivalence (the same external
                           settler the Feynman benchmark uses) — never a self-score;
  • a baseline           — the zero-dep base basis, which solves ONLY the difficulty-0 rung;
  • a difficulty score   — the minimal number of GROWN primitives whose union recovers it (0,1,2,…);
  • a NEGATIVE CONTROL   — scramble the target (decouple x→y): a real solver must STOP recovering it. If a
                           "problem" survives a scrambled target it is degenerate (measuring leakage, not skill).

`curriculum_progression(primitives)` — the fraction of a difficulty-ranked curriculum the current primitive set
solves (externally certified) — is the Pareto dimension. It is ORTHOGONAL to `sr_recovery`/`external_transfer`:
its rungs are unlocked by primitives those dimensions do NOT reward (triple_product, product_trig, gaussian), so
optimizing it changes which upgrades the loop keeps. It rises as the engine grows the right primitives and
SATURATES honestly (you cannot solve a difficulty-N rung without the primitive it needs). Deterministic.

Run:  python -m evals.benchmarks.open_ended
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Tuple


@dataclass(frozen=True)
class GeneratedProblem:
    """A manufactured SR problem with KNOWN ground truth and the apparatus to settle it externally."""
    id: str
    f: object                          # y = f(*x): the (hidden-from-solver) generator of the data
    nvars: int
    sym: str                           # ground truth in x0..xn — fixed by construction, for the SymPy check
    ranges: List[Tuple[float, float]]
    primitives_needed: FrozenSet[str]  # the grown primitives whose union recovers it (∅ ⇒ base solves it)

    @property
    def difficulty(self) -> int:
        return len(self.primitives_needed)


def _R(n, lo=0.5, hi=2.5):
    return [(lo, hi)] * n


# ── the seed curriculum: increasing difficulty, each rung unlocked by a SPECIFIC grown primitive (verified, not
# asserted — `curriculum_recovery_map` re-derives the requirement from real fits). The rungs are deliberately
# unlocked by the primitives that `external_transfer` does NOT reward, so the dimension is genuinely orthogonal. ──
SEED_CURRICULUM: List[GeneratedProblem] = [
    GeneratedProblem("OE.d0.product",   lambda a, b: a * b,                       2, "x0*x1",            _R(2), frozenset()),
    GeneratedProblem("OE.d1.triple",    lambda a, b, c: a * b * c,                3, "x0*x1*x2",         _R(3), frozenset({"triple_product"})),
    GeneratedProblem("OE.d1.prodtrig",  lambda a, b, c: a * b * math.sin(c),      3, "x0*x1*sin(x2)",    _R(3), frozenset({"product_trig"})),
    GeneratedProblem("OE.d1.gaussian",  lambda x: math.exp(-x * x / 2),           1, "exp(-x0**2/2)",    [(-2.0, 2.0)], frozenset({"gaussian"})),
    GeneratedProblem("OE.d2.triple_gauss", lambda a, b, c, d: a * b * c + math.exp(-d * d / 2), 4,
                     "x0*x1*x2 + exp(-x3**2/2)", [(0.5, 2.0), (0.5, 2.0), (0.5, 2.0), (-2.0, 2.0)],
                     frozenset({"triple_product", "gaussian"})),
]


def _to_feynman(p: GeneratedProblem):
    from evals.benchmarks.feynman import FeynmanEquation
    return FeynmanEquation(p.id, p.sym, p.f, p.nvars, list(p.ranges), False, p.sym)


def _constant_target(y) -> bool:
    """A (near-)constant held-out target has no variance, so R² is undefined/inflated (feynman._r2 floors the
    denominator at 1e-12). Such a 'problem' is degenerate — any constant fit scores ~1.0 and a scrambled target
    cannot collapse (reversed(constant)==constant). We refuse it as not-settleable rather than let it leak."""
    if not y:
        return True
    m = sum(y) / len(y)
    ss = sum((v - m) ** 2 for v in y)
    return ss < 1e-9 * len(y) * max(1.0, m * m)


def recover_generated(problem: GeneratedProblem, primitives, n_samples: int = 250, seed: int = 0,
                      scramble: bool = False) -> bool:
    """The EXTERNAL resolver — fit base (+ the given grown primitives) and return True iff the DATA certifies it
    (held-out R²>0.999) AND it is the exact symbolic form (SymPy). `scramble=True` is the NEGATIVE CONTROL: it
    reverses the training target (decouples x→y) so a genuine recovery must collapse."""
    from evals.benchmarks.feynman import generate_dataset, _symbolic_match, _r2
    from evals.self_improve_loop import _base_terms
    from OUTLIER_MCB.grown_basis import GROWN_PRIMITIVES
    from OUTLIER_MCB.evaluators.symbolic import least_squares
    X_tr, y_tr, X_ho, y_ho = generate_dataset(_to_feynman(problem), n=n_samples, seed=seed)
    if _constant_target(y_ho):
        return False                                      # degenerate (no variance) → not a settleable problem
    if scramble:
        y_tr = list(reversed(y_tr))                       # break the input→output mapping (negative control)
    terms = _base_terms(problem.nvars)
    for name in primitives:
        if name in GROWN_PRIMITIVES:
            terms = terms + GROWN_PRIMITIVES[name](problem.nvars)
    f = least_squares(X_tr, y_tr, terms)
    if _r2(f, X_ho, y_ho) <= 0.999:
        return False                                      # does not fit the held-out target
    if scramble:
        return True                                       # scrambled inputs STILL fit → LEAK: the negative control must FAIL so the caller's guard fires
    return _symbolic_match(f.text(), problem.sym, problem.nvars) is True


def curriculum_recovery_map(curriculum: List[GeneratedProblem] = None, n_samples: int = 250) -> Dict[str, FrozenSet[str]]:
    """Precompute ONCE, by REAL fits, the minimal primitive set each rung needs — and CERTIFY each rung's apparatus
    externally: base+needed recovers, dropping any needed primitive breaks it, the scrambled target collapses, and
    the baseline solves only the difficulty-0 rungs. Returns {rung_id: required primitive frozenset}. Raises if a
    declared rung does not behave as an externally-settleable problem (so a degenerate 'problem' cannot sneak in)."""
    curriculum = curriculum if curriculum is not None else SEED_CURRICULUM
    out: Dict[str, FrozenSet[str]] = {}
    for p in curriculum:
        need = p.primitives_needed
        if not recover_generated(p, need, n_samples):
            raise ValueError(f"{p.id}: base+{set(need) or 'base'} does not recover the known ground truth — not settleable")
        for drop in need:                                  # minimality: each declared primitive is load-bearing
            if recover_generated(p, need - {drop}, n_samples):
                raise ValueError(f"{p.id}: primitive '{drop}' is not actually required — difficulty is overstated")
        if recover_generated(p, need, n_samples, scramble=True):
            raise ValueError(f"{p.id}: scrambled-target NEGATIVE CONTROL did not collapse — the problem leaks")
        base_solves = recover_generated(p, frozenset(), n_samples)
        if base_solves != (len(need) == 0):
            raise ValueError(f"{p.id}: baseline behaviour inconsistent with declared difficulty {p.difficulty}")
        out[p.id] = need
    return out


@dataclass
class CurriculumReport:
    n_rungs: int
    solved: int
    by_difficulty: Dict[int, Tuple[int, int]] = field(default_factory=dict)   # difficulty → (solved, total)
    false_solved: int = 0              # a scrambled-target rung wrongly "solved" — must always be 0

    @property
    def progression(self) -> float:
        return round(self.solved / self.n_rungs, 4) if self.n_rungs else 0.0


def curriculum_progression(primitives, recovery_map: Dict[str, FrozenSet[str]] = None,
                           curriculum: List[GeneratedProblem] = None, n_samples: int = 250) -> float:
    """The Pareto metric: fraction of the difficulty-ranked curriculum the current primitive set solves. Uses the
    externally-certified recovery map (set membership) when provided — else recomputes it by real fits."""
    return curriculum_report(primitives, recovery_map, curriculum, n_samples).progression


def curriculum_report(primitives, recovery_map: Dict[str, FrozenSet[str]] = None,
                      curriculum: List[GeneratedProblem] = None, n_samples: int = 250) -> CurriculumReport:
    curriculum = curriculum if curriculum is not None else SEED_CURRICULUM
    cmap = recovery_map if recovery_map is not None else curriculum_recovery_map(curriculum, n_samples)
    have = set(primitives)
    by: Dict[int, Tuple[int, int]] = {}
    solved = 0
    for p in curriculum:
        ok = cmap[p.id] <= have
        solved += int(ok)
        s, t = by.get(p.difficulty, (0, 0))
        by[p.difficulty] = (s + int(ok), t + 1)
    return CurriculumReport(n_rungs=len(curriculum), solved=solved, by_difficulty=by)


def harder_problem(primitives, recovery_map: Dict[str, FrozenSet[str]] = None,
                   curriculum: List[GeneratedProblem] = None) -> Optional[GeneratedProblem]:
    """OPEN-ENDEDNESS, disciplined: return the EASIEST not-yet-solved rung — the next problem at the engine's
    frontier (just beyond current capability). None ⇒ the curriculum is exhausted (a real ceiling, not a bluff)."""
    curriculum = curriculum if curriculum is not None else SEED_CURRICULUM
    cmap = recovery_map if recovery_map is not None else curriculum_recovery_map(curriculum)
    have = set(primitives)
    unsolved = [p for p in curriculum if not (cmap[p.id] <= have)]
    return min(unsolved, key=lambda p: p.difficulty) if unsolved else None


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# UNBOUNDED open-endedness — a ratchet with no fixed ceiling (the POET move, made rigorous)
#
# The seed curriculum above SATURATES at 1.0 — a fixed list over a fixed primitive set has a ceiling. POET escapes
# this with an ever-growing problem population admitted by a MINIMAL CRITERION (novel AND solvable-at-the-frontier)
# over agents that keep improving — but POET's "solved" is the agent's own reward (autoreferential). We take POET's
# open-endedness and subordinate it to an EXTERNAL resolver: for EVERY depth k there is a generated problem (the
# k-way product) with KNOWN ground truth, and an UNBOUNDED primitive family (product_k) the engine grows on demand.
# `frontier_reach` is a RATCHET — the deepest certified depth — that is monotone (a solved depth stays solved), has
# NO built-in 1.0, and climbs as far as compute allows. The only ceiling is `reach_budget`; lift it and exploration
# continues. This is what makes the engine explore UNLIMITEDLY without ever regressing and without self-judging.
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════

def product_problem(k: int) -> GeneratedProblem:
    """A generated problem of depth k: the k-way product x0·x1·…·x_{k-1}, with KNOWN ground truth. There is one for
    EVERY k (no fixed list); base solves k≤2, deeper needs the grown product_k primitive."""
    sym = "*".join(f"x{i}" for i in range(k))

    def f(*a):
        p = 1.0
        for v in a:
            p *= v
        return p
    needed = frozenset() if k <= 2 else frozenset({f"product_{k}"})
    return GeneratedProblem(f"OE.depth.{k}", f, k, sym, _R(k, 0.7, 1.6), needed)


def solves_depth(k: int, grown_depths, n_samples: int = 300, scramble: bool = False) -> bool:
    """EXTERNAL resolver for the ratchet: can base + the grown product_j primitives (j in grown_depths) recover the
    depth-k product? R²>0.999 on held-out samples AND exact SymPy form. `scramble` is the NEGATIVE CONTROL."""
    from evals.benchmarks.feynman import generate_dataset, _symbolic_match, _r2
    from evals.self_improve_loop import _base_terms
    from OUTLIER_MCB.grown_basis import product_k_builder
    from OUTLIER_MCB.evaluators.symbolic import least_squares
    p = product_problem(k)
    X_tr, y_tr, X_ho, y_ho = generate_dataset(_to_feynman(p), n=n_samples, seed=0)
    if _constant_target(y_ho):
        return False                                      # degenerate (no variance) → not a settleable problem
    if scramble:
        y_tr = list(reversed(y_tr))
    terms = _base_terms(k)
    for j in grown_depths:
        terms = terms + product_k_builder(j)(k)
    f = least_squares(X_tr, y_tr, terms)
    if _r2(f, X_ho, y_ho) <= 0.999:
        return False                                      # does not fit the held-out target
    if scramble:
        return True                                       # scrambled inputs STILL fit → LEAK: the negative control must FAIL so the caller's guard fires
    return _symbolic_match(f.text(), p.sym, k) is True


def admit(k: int, grown_depths, n_samples: int = 300) -> bool:
    """POET's MINIMAL CRITERION, made rigorous. Admit depth k to the frontier iff it is
      • NOVEL      — k not already grown, and k > 2 (k≤2 is trivially base-solvable);
      • UNSOLVED   — base + current grown primitives cannot YET solve it (it is AT the frontier, not too easy);
      • SETTLEABLE — growing product_k makes it externally recoverable (R²+SymPy) AND the scrambled target COLLAPSES
                     (a real gain, not leakage).
    A depth that fails any clause is refused — the ratchet never counts a trivial, unsolvable, or leaky problem."""
    grown = set(grown_depths)
    if k <= 2 or k in grown:
        return False                                            # not novel
    if solves_depth(k, grown, n_samples):
        return False                                            # already solvable → not at the frontier
    if not solves_depth(k, grown | {k}, n_samples):
        return False                                            # cannot be certified even by growing the primitive
    if solves_depth(k, grown | {k}, n_samples, scramble=True):
        return False                                            # negative control did not collapse → leakage
    return True


@dataclass
class RatchetResult:
    reach_trajectory: List[int]        # certified reach after each step (monotone non-decreasing)
    grown_depths: List[int]            # the product_k primitives grown, in order
    reach_budget: int
    hit_conceptual_ceiling: bool       # True ⇒ a depth genuinely could not be certified (an HONEST ceiling)

    @property
    def final_reach(self) -> int:
        return self.reach_trajectory[-1] if self.reach_trajectory else 2

    def markdown(self) -> str:
        why = ("a depth could NOT be externally certified — an honest CONCEPTUAL ceiling"
               if self.hit_conceptual_ceiling else
               f"reach_budget={self.reach_budget} (COMPUTE) — lift it and the ratchet keeps climbing, no conceptual ceiling")
        return "\n".join([
            "## Open-ended ratchet — unlimited exploration, externally certified, never regressing",
            f"- reach: **2 → {self.final_reach}** (each depth settled by R²>0.999 + SymPy + a scrambled negative control)",
            f"- grown primitives (on demand): {['product_%d' % d for d in self.grown_depths] or '—'}",
            f"- stopped because: {why}",
            "- the metric is a RATCHET (deepest certified depth), not a saturating [0,1] score — it has no built-in ceiling.",
        ])


def frontier_reach(grown_depths) -> int:
    """The RATCHET metric: the deepest depth the engine can currently certify. Base gives 2; each grown product_k
    extends it. Monotone, unbounded — the open-endedness certificate."""
    grown = set(grown_depths)
    reach = 2
    while (reach + 1) in grown:
        reach += 1
    return reach


def open_ended_ratchet(reach_budget: int = 8, n_samples: int = 300) -> RatchetResult:
    """Unlimited exploration, disciplined. Start at reach 2 (base). Repeatedly propose depth reach+1, admit it under
    the minimal criterion, grow product_{reach+1}, advance — each depth certified externally with a negative control.
    Monotone and non-regressing. Stops at `reach_budget` (compute) or, honestly, at the first depth that cannot be
    certified (a real conceptual ceiling). Raising reach_budget resumes exploration — there is no built-in 1.0."""
    grown: List[int] = []
    reach = 2
    traj = [2]
    conceptual = False
    while reach < reach_budget:
        k = reach + 1
        if not admit(k, grown, n_samples):
            conceptual = True
            break
        grown.append(k)
        reach = frontier_reach(grown)
        traj.append(reach)
    return RatchetResult(traj, list(grown), reach_budget, conceptual)


if __name__ == "__main__":   # pragma: no cover
    print(open_ended_ratchet(reach_budget=9).markdown())
    print()
    cmap = curriculum_recovery_map()
    print("curriculum (externally certified):")
    for p in SEED_CURRICULUM:
        print(f"  {p.id:22} difficulty {p.difficulty}  needs {set(cmap[p.id]) or '∅ (base)'}")
    for prims in ([], ["triple_product"], ["triple_product", "product_trig", "gaussian"]):
        r = curriculum_report(prims, cmap)
        print(f"primitives={prims or '∅'}: progression {r.progression}  by_difficulty {r.by_difficulty}")
