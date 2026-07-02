"""physics_inventor — invent whole new consistent 'physics' (law-sets), not just discover our universe's laws.

The frontier move (Point 1): stop assuming the universe is GIVEN. A Physics here is a discrete dynamical law
over a lattice of cells — a self-contained toy universe. propose_new_physics() invents one; run_simulation()
evolves it; measure_emergence() asks — with an EXTERNAL, non-self-judged metric — whether that universe grows
structure. The library's own creative() flagged the box (closed / equilibrium / linear) and the exit: a driven
lattice rule far from a trivial fixed point.

Emergence is measured HONESTLY, not by raw entropy (which rewards CHAOS). A trajectory is interesting when it
is STRUCTURED and STATE-RICH — neither frozen, nor random, nor a trivial cycle: it must (a) actually move, (b)
compress better than EQUAL-SHAPE NOISE (real correlation, not disorder), and (c) visit many distinct states
(so a period-2 blinker does not qualify). So emergence = structure × activity × state-diversity, which is ~0
for a static universe, ~0 for a chaotic one, and ~0 for a trivial oscillator. The negative controls (a trivial
and a noise universe, in evals/benchmarks/physics_emergence.py) must both score ~0 while a structured one does
not — that is the enforced honesty gate (coherence_controls_pass), checked by a protected invariant.

Deterministic (seeded), zero-dependency (zlib from the stdlib). This module INVENTS and SIMULATES; the external
Pareto metric + its control live in evals/benchmarks/physics_emergence.py, and the coherence gate is a protected
invariant in self_repair.py.
"""
from __future__ import annotations
import random
import zlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

State = Tuple[int, ...]


@dataclass
class Law:
    """One update rule of the toy universe: a local neighborhood pattern → the cell's next value."""
    neighborhood: Tuple[int, ...]
    next_value: int


@dataclass
class Physics:
    """A self-contained toy universe: k cell-states, a neighborhood radius, and a total local update law."""
    k: int
    radius: int
    rule: Dict[Tuple[int, ...], int]
    constants: Dict[str, float] = field(default_factory=dict)
    name: str = "physics"

    def step(self, state: State) -> State:
        n = len(state)
        r = self.radius
        out = []
        for i in range(n):
            nb = tuple(state[(i + d) % n] for d in range(-r, r + 1))   # periodic boundary → bounded by construction
            out.append(self.rule.get(nb, 0) % self.k)
        return tuple(out)

    def laws(self) -> List[Law]:
        return [Law(neighborhood=nb, next_value=v) for nb, v in sorted(self.rule.items())]

    def is_deterministic(self) -> bool:
        """The same state must always map to the same successor — a universe cannot be settled if it is random."""
        return self.step(self._probe()) == self.step(self._probe())

    def _probe(self) -> State:
        return tuple((i % self.k) for i in range(2 * self.radius + 3))


def propose_new_physics(complexity: int = 1, seed: int = 0, k: int = 2, radius: int = 1) -> Physics:
    """Invent a new toy universe: a random TOTAL local rule over all k^(2·radius+1) neighborhoods. `complexity`
    scales the alphabet k (richer state space). Seeded ⇒ deterministic and reproducible (never random at runtime)."""
    k = max(2, k + max(0, complexity - 1))
    rng = random.Random(seed)
    span = 2 * radius + 1
    rule: Dict[Tuple[int, ...], int] = {}

    def _all(prefix: Tuple[int, ...]):
        if len(prefix) == span:
            rule[prefix] = rng.randrange(k)
            return
        for v in range(k):
            _all(prefix + (v,))

    _all(())
    return Physics(k=k, radius=radius, rule=rule, name=f"physics[c{complexity},s{seed}]")


def elementary_physics(rule_number: int) -> Physics:
    """A named 2-state, radius-1 elementary cellular automaton (Wolfram numbering) — for reproducible tests:
    rule 90 (Sierpinski, structured), rule 30 (chaotic), rule 0 (dies to a static universe)."""
    rule: Dict[Tuple[int, ...], int] = {}
    for idx in range(8):
        nb = tuple((idx >> (2 - j)) & 1 for j in range(3))   # (left, center, right)
        rule[nb] = (rule_number >> idx) & 1
    return Physics(k=2, radius=1, rule=rule, name=f"ECA[{rule_number}]")


def run_simulation(physics: Physics, steps: int = 40, width: int = 41, seed: int = 1,
                   init: Optional[State] = None) -> List[State]:
    """Evolve the universe for `steps` from a seeded initial state. Returns the full trajectory (bounded by
    construction: periodic boundary + mod-k values, so it can never blow up to NaN/inf)."""
    if init is None:
        rng = random.Random(seed)
        init = tuple(rng.randrange(physics.k) for _ in range(width))
    traj = [tuple(init)]
    for _ in range(steps):
        traj.append(physics.step(traj[-1]))
    return traj


def _flatten(traj: List[State]) -> bytes:
    return bytes(v % 256 for row in traj for v in row)


def _csize(b: bytes) -> int:
    return len(zlib.compress(b, 9)) if b else 1


def _activity(trajectory: List[State]) -> float:
    """Fraction of (cell, timestep) transitions that actually change — 0 for a frozen universe, high for a
    lively one. This is what stops a beautifully-compressible STATIC universe from scoring."""
    if len(trajectory) < 2:
        return 0.0
    total = changes = 0
    for a, b in zip(trajectory, trajectory[1:]):
        for x, y in zip(a, b):
            total += 1
            changes += (x != y)
    return (changes / total) if total else 0.0


def _noise_bytes(trajectory: List[State], k: int, seed: int = 13) -> bytes:
    """An i.i.d.-random trajectory of the SAME shape and alphabet — the max-entropy baseline. Comparing against
    THIS (not against the raw size) is what lets the metric tell STRUCTURE from mere disorder: binary data always
    zlib-packs ~8×, so only 'compresses better than equal-shape noise' is real structure."""
    rng = random.Random(seed)
    n = sum(len(row) for row in trajectory)
    return bytes(rng.randrange(max(2, k)) % 256 for _ in range(n))


def measure_emergence(trajectory: List[State], k: Optional[int] = None) -> float:
    """[0,1] external interest of a trajectory: STRUCTURE × ACTIVITY × STATE-DIVERSITY — the honest anti-entropy,
    anti-triviality metric.
      • activity   — does the universe MOVE? 0 for a frozen/period-1 universe.
      • structure  — does it compress BETTER THAN EQUAL-SHAPE NOISE (1 − c(traj)/c(noise))? >0 only with real
                     correlation; ~0 for a chaotic universe (incompressible, like the noise).
      • diversity  — how many DISTINCT states does it visit, relative to the trajectory length? This is the
                     anti-triviality guard: a period-2 oscillator (a 'blinker') is maximally active AND
                     compressible but visits only 2 states → low diversity → low emergence.
    So a static universe scores 0 (activity), a chaotic one ~0 (structure), a trivial oscillator ~0 (diversity),
    and only a STRUCTURED, state-rich universe peaks. Unlike raw entropy / Lempel-Ziv, disorder is not rewarded;
    unlike plain structure×activity, a trivial cycle is not rewarded either."""
    if len(trajectory) < 3:
        return 0.0
    activity = _activity(trajectory)
    if activity == 0.0:
        return 0.0
    distinct = len(set(trajectory))
    diversity = min(1.0, (distinct - 1) / max(1, 0.5 * len(trajectory)))   # a 2-state blinker → ~0; rich → 1
    kk = k if k is not None else (max((max(row) for row in trajectory), default=1) + 1)
    raw = _flatten(trajectory)
    structure = max(0.0, 1.0 - _csize(raw) / max(1, _csize(_noise_bytes(trajectory, kk))))
    return round(structure * activity * diversity, 4)


def emergence_of(physics: Physics, steps: int = 40, width: int = 41, seed: int = 1) -> float:
    """Convenience: simulate a physics and score its emergence in one call (the external benchmark's core)."""
    return measure_emergence(run_simulation(physics, steps=steps, width=width, seed=seed))


def _single_seed_init(width: int) -> State:
    s = [0] * width
    s[width // 2] = 1
    return tuple(s)


def coherence_controls_pass(margin: float = 0.05) -> bool:
    """The honesty gate for the physics dimension (used by a protected invariant). TRUE iff:
      • a STRUCTURED universe (rule 90 from a single seed → Sierpinski) scores materially above BOTH
      • a TRIVIAL universe (identity, rule 204) AND an i.i.d.-NOISE universe — so the metric rewards structure,
        not mere change or disorder; AND
      • the invented physics is DETERMINISTIC and BOUNDED (mod-k + periodic boundary can never blow up).
    If any clause fails, emergence could be inflated by a static or chaotic universe → the dimension is not honest."""
    seed61 = _single_seed_init(61)
    structured = measure_emergence(run_simulation(elementary_physics(90), steps=30, width=61, init=seed61), k=2)
    trivial = measure_emergence(run_simulation(elementary_physics(204), steps=30, width=61, init=seed61), k=2)
    rng = random.Random(1)
    noise = measure_emergence([tuple(rng.randrange(2) for _ in range(61)) for _ in range(31)], k=2)
    deterministic = elementary_physics(90).is_deterministic() and propose_new_physics(1, seed=0).is_deterministic()
    return bool(structured >= trivial + margin and structured >= noise + margin and deterministic)
