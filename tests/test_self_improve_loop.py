"""The recursive self-improvement loop: the engine raises its own verified-novelty fitness, never regressing.

Fast subset (a few equations). GREEN: the fitness trajectory is monotone non-decreasing (never regress), ends
above where it started, and the discovered primitives are real (the grown backend recovers a law the default
basis cannot). Deterministic.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import OUTLIER_MCB as g
from evals.benchmarks.feynman import FEYNMAN
from evals.self_improve_loop import self_improve, _recovers
from OUTLIER_MCB.grown_basis import GROWN_PRIMITIVES

pytest.importorskip("sympy")    # the certified recovery uses symbolic equivalence


def _subset(*ids):
    by = {e.id: e for e in FEYNMAN}
    return [by[i] for i in ids]


def test_loop_raises_fitness_and_never_regresses():
    # a small substrate: two already-recovered simple laws + two that need the 'ratio' primitive (q/C, ω/c)
    eqs = _subset("I.12.1", "TRIG.1", "I.25.13", "I.29.4")
    res = self_improve(epochs=4, n_samples=150, equations=eqs)
    traj = [e.fitness for e in res.trajectory]
    assert traj == sorted(traj)                          # MONOTONE non-decreasing — never regress
    assert res.final_fitness > res.start_fitness          # it genuinely improved
    assert "ratio" in res.accepted_primitives             # discovered a real new capability
    assert res.start_fitness == 0.5                       # 2/4 recovered by the default basis
    assert res.final_fitness == 1.0                       # 4/4 after discovering 'ratio'


def test_deterministic():
    eqs = _subset("I.12.1", "I.25.13")
    a = [e.fitness for e in self_improve(epochs=2, n_samples=120, equations=eqs).trajectory]
    b = [e.fitness for e in self_improve(epochs=2, n_samples=120, equations=eqs).trajectory]
    assert a == b


def test_grown_primitive_recovers_what_default_cannot():
    qC = _subset("I.25.13")[0]                            # q / C — true division
    assert not _recovers(qC, None, n_samples=200)         # the default basis cannot
    assert _recovers(qC, GROWN_PRIMITIVES["ratio"], n_samples=200)   # the grown 'ratio' primitive can (certified)


def test_extended_substrate_gives_fresh_headroom():
    """The 14-law substrate plateaued at 12/14; the EXTENDED substrate's new primitives recover MORE laws —
    so verified-novelty can keep rising (the metric is not exhausted, the substrate was)."""
    from evals.benchmarks.feynman import FEYNMAN_EXTENDED
    by = {e.id: e for e in FEYNMAN_EXTENDED}
    # ratio_product recovers a law the default + earlier primitives cannot
    rp = by["I.39.22"]                                     # n·kb·T/V
    assert not _recovers(rp, None, n_samples=250)
    assert not _recovers(rp, GROWN_PRIMITIVES["ratio"], n_samples=250)
    assert _recovers(rp, GROWN_PRIMITIVES["ratio_product"], n_samples=250)
    # inverse_square recovers an inverse-square law
    isq = by["II.3.24"]                                    # P/(4π r²)
    assert not _recovers(isq, None, n_samples=250)
    assert _recovers(isq, GROWN_PRIMITIVES["inverse_square"], n_samples=250)


def test_loop_on_extended_subset_climbs_with_new_primitive():
    # two already-simple laws + two ratio_product laws → the loop must discover 'ratio_product' to climb
    from evals.benchmarks.feynman import FEYNMAN_EXTENDED
    ext = {e.id: e for e in FEYNMAN_EXTENDED}
    eqs = _subset("I.12.1", "TRIG.1") + [ext["I.39.22"], ext["I.34.8"]]
    res = self_improve(epochs=8, n_samples=200, equations=eqs)
    traj = [e.fitness for e in res.trajectory]
    assert traj == sorted(traj)                            # never regress
    assert res.final_fitness > res.start_fitness
    assert "ratio_product" in res.accepted_primitives


def test_loop_records_keylogs_and_never_regress_frontier():
    eqs = _subset("I.12.1", "I.25.13", "I.29.4")
    led = g.FrontierLedger()
    res = self_improve(epochs=3, n_samples=120, equations=eqs, ledger=led)
    assert res.memory.runs                                # per-epoch key-logs were recorded
    # a worse certified fitness can never be written back onto the monotone frontier
    assert led.claim("self_improvement", "verified_novelty", 0.0, "increase",
                     {"status": "NUMERIC_VERIFIED"}).outcome == "REGRESSION_REJECTED"
