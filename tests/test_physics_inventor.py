"""test_physics_inventor — Point 1: invent whole new toy 'universes', scored by an EXTERNAL emergence metric
that rewards STRUCTURE, not disorder. The controls (a frozen universe and an i.i.d.-noise universe) must both
score ~0, and the coherence invariant must hold. Deterministic and offline.
"""
import OUTLIER_MCB as gsl
from OUTLIER_MCB.physics_inventor import (propose_new_physics, elementary_physics, run_simulation,
                                             measure_emergence, coherence_controls_pass)


def _single_seed(width=61):
    s = [0] * width
    s[width // 2] = 1
    return tuple(s)


def _emergence(rule):
    return measure_emergence(run_simulation(elementary_physics(rule), steps=30, width=61, init=_single_seed()), k=2)


# ── the metric rewards STRUCTURE over both a frozen and a noise universe ───────────────────────────────
def test_emergence_rewards_structure_not_disorder():
    structured = _emergence(90)          # rule 90 from a single seed → the Sierpinski triangle
    frozen = _emergence(204)             # identity → nothing ever changes
    import random
    rng = random.Random(1)
    noise = measure_emergence([tuple(rng.randrange(2) for _ in range(61)) for _ in range(31)], k=2)
    assert structured > frozen + 0.05    # structure beats a frozen universe
    assert structured > noise + 0.05     # AND beats pure noise — disorder is NOT emergence
    assert frozen < 0.02 and noise < 0.02


def test_static_universe_scores_zero():
    # a universe whose law is 'everything becomes 0' freezes after one step → no emergence
    from OUTLIER_MCB.physics_inventor import Physics
    dead = Physics(k=2, radius=1, rule={nb: 0 for nb in [(a, b, c) for a in (0, 1) for b in (0, 1) for c in (0, 1)]})
    assert measure_emergence(run_simulation(dead, steps=20, width=41), k=2) < 0.02


# ── invented universes are deterministic and bounded (never blow up), and some are genuinely emergent ─
def test_invented_physics_is_deterministic_and_can_be_emergent():
    best = max((gsl.emergence_of(propose_new_physics(1, seed=s)) for s in range(12)))
    assert best > 0.1                    # at least one invented universe grows real structure
    p = propose_new_physics(2, seed=3)
    assert p.is_deterministic()          # same state → same successor, always (a settle-able universe)


# ── the honesty gate holds, and it is a PROTECTED INVARIANT (Point 1 cannot silently regress) ─────────
def test_physics_coherence_controls_pass():
    assert coherence_controls_pass() is True


def test_physics_invariant_is_registered_and_passes():
    from OUTLIER_MCB.self_repair import verify_invariants, INVARIANT_REGISTRY
    assert "invented_physics_scored_externally" in INVARIANT_REGISTRY
    rep = verify_invariants()
    assert rep.ok and "invented_physics_scored_externally" in rep.passed_names


# ── the external Pareto-dimension benchmark returns a real, control-passing score ─────────────────────
def test_physics_invention_dimension_benchmark():
    from evals.benchmarks.physics_emergence import physics_invention_score, controls_pass
    assert controls_pass() is True                 # structured beats trivial + noise on the benchmark
    assert 0.0 <= physics_invention_score(trials=12) <= 1.0
