"""physics_emergence — the EXTERNAL benchmark for Point 1 (invent new physics). It is the world that settles the
`physics_invention` Pareto dimension: it simulates an invented law-set and scores the emergent structure of the
trajectory with measure_emergence — a metric the engine cannot talk its way past. Includes the negative controls
(a trivial/identity universe and an i.i.d.-noise universe must both score ~0), so the dimension can never be
inflated by a universe that is static or merely disordered.
"""
from __future__ import annotations
import random
from typing import Dict, List

from OUTLIER_MCB.physics_inventor import (Physics, propose_new_physics, elementary_physics,
                                             run_simulation, measure_emergence)

STEPS = 30
WIDTH = 61


def _single_seed(width: int = WIDTH):
    s = [0] * width
    s[width // 2] = 1
    return tuple(s)


def emergence_score(physics: Physics, single_seed: bool = True) -> float:
    """The external interest of an invented universe: simulate it and measure emergent structure in [0,1]."""
    init = _single_seed(WIDTH) if single_seed else None
    return measure_emergence(run_simulation(physics, steps=STEPS, width=WIDTH, init=init), k=physics.k)


def best_invented_emergence(trials: int = 24, complexity: int = 1) -> Dict:
    """Search invented physics and return the BEST emergent universe found — this max is the `physics_invention`
    Pareto-dimension value. Deterministic (seeds 0..trials-1)."""
    best_score, best_seed = 0.0, -1
    for seed in range(trials):
        s = emergence_score(propose_new_physics(complexity=complexity, seed=seed))
        if s > best_score:
            best_score, best_seed = s, seed
    return {"score": round(best_score, 4), "seed": best_seed, "trials": trials, "complexity": complexity}


def physics_invention_score(trials: int = 24) -> float:
    """The single float for the multi-metric Pareto vector: the best certified emergent universe we can invent."""
    return best_invented_emergence(trials=trials)["score"]


# ── negative controls: the dimension must be UN-gameable by trivial or disordered universes ──────────────
def trivial_universe_emergence() -> float:
    """An identity law (nothing ever changes) — must score ~0 (a frozen universe is not emergent)."""
    return emergence_score(elementary_physics(204))               # rule 204 = identity


def noise_universe_emergence(seed: int = 1) -> float:
    """A max-entropy i.i.d.-noise 'universe' (no law-structure at all) — must score ~0: disorder is not emergence
    (this is exactly what a raw entropy / Lempel-Ziv metric would WRONGLY reward)."""
    rng = random.Random(seed)
    traj: List = [tuple(rng.randrange(2) for _ in range(WIDTH)) for _ in range(STEPS + 1)]
    return measure_emergence(traj, k=2)


def structured_universe_emergence() -> float:
    """A canonical STRUCTURED universe (rule 90 from a single seed → the Sierpinski triangle) — must score
    materially above the controls, proving the metric rewards structure, not change."""
    return emergence_score(elementary_physics(90))


def controls_pass(margin: float = 0.05) -> bool:
    """The benchmark is honest iff a structured universe beats BOTH controls by `margin`."""
    s = structured_universe_emergence()
    return s >= trivial_universe_emergence() + margin and s >= noise_universe_emergence() + margin
