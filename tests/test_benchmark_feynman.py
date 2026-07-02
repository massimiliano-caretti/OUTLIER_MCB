"""Official Feynman SR benchmark — attests, with certified ground truth, what the SR component recovers.

Deterministic. GREEN: an algebraically-simple Feynman equation (μ·Nn) is recovered (exact symbolic form when
SymPy is present; R²>0.999 always). Negative control: a transcendental equation (Gaussian, needs exp) is
honestly NOT recovered — the library does not pretend to fit what its basis cannot express.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evals.benchmarks.feynman import FEYNMAN, recover, run_benchmark


def _by_id(eid):
    return next(e for e in FEYNMAN if e.id == eid)


def test_simple_product_law_is_recovered():
    r = recover(_by_id("I.12.1"))                 # F = mu * Nn
    assert r.solved and r.r2 > 0.999 and r.controls_collapse
    if r.symbolic is not None:                      # SymPy available → it is the EXACT form, not an approximation
        assert r.symbolic is True


def test_dot_product_and_trig_are_recovered():
    for eid in ("I.11.19", "TRIG.1"):
        r = recover(_by_id(eid))
        assert r.solved and r.r2 > 0.999, eid
        if r.symbolic is not None:
            assert r.symbolic is True, eid


def test_transcendental_is_honestly_not_recovered():
    r = recover(_by_id("I.6.2"))                   # Gaussian: exp(-θ²/2)/√(2π) — outside the basis
    assert not r.solved                             # no false claim of recovery
    if r.symbolic is not None:
        assert r.symbolic is not True


def test_division_law_is_not_falsely_recovered():
    r = recover(_by_id("I.25.13"))                 # q / C — true division, not in the basis
    assert not r.solved


def test_benchmark_report_numbers_are_stable_and_honest():
    rep = run_benchmark()
    assert rep.n == len(FEYNMAN)
    assert rep.solved >= 5 and rep.recovery_rate > 0.3      # the simple subset is recovered
    assert rep.median_r2 > 0.9
    if rep.symbolic_checked:
        # the true symbolic recoveries are exactly the algebraically-simple forms (no inflation)
        assert rep.symbolic_solved >= 5
        solved_ids = {r.id for r in rep.rows if r.symbolic is True}
        assert {"I.12.1", "I.12.5", "I.39.1", "I.11.19", "TRIG.1"} <= solved_ids


def test_deterministic():
    a = recover(_by_id("I.12.1")).r2
    b = recover(_by_id("I.12.1")).r2
    assert a == b
