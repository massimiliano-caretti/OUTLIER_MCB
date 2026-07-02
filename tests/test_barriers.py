"""F2 world-test — no-go theorems as a kill gate (the parity problem).

RED→GREEN: a classical sieve aimed at gap = 2 is DEAD_BY_BARRIER (a proven dead route), and judge() surfaces
it. Negative control: an idea that injects a parity-BREAKING input is NOT hit by the barrier. The gate never
claims the conjecture is true or false — it rules on the ROUTE only.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import OUTLIER_MCB as gsl
from OUTLIER_MCB.barriers import barrier_membership, DEAD_BY_BARRIER, NOT_BLOCKED

_NT = None


def _pack():
    global _NT
    _NT = _NT or gsl.get_pack("number_theory")
    return _NT


def test_classical_sieve_for_gap_two_is_dead_by_barrier():
    idea = "use a classical Selberg sieve with parity-respecting weights to prove infinitely many twin primes (gap 2)"
    v = barrier_membership(idea, _pack())
    assert v is not None and v.status == DEAD_BY_BARRIER
    assert v.barrier == "PARITY_PROBLEM" and v.exits


def test_judge_reports_dead_by_barrier():
    j = gsl.judge("a classical sieve-only attack to get twin primes at gap 2", pack=_pack())
    assert j.verdict == "DEAD_BY_BARRIER"
    assert j.barrier is not None and j.barrier.status == DEAD_BY_BARRIER


def test_negative_control_parity_breaking_idea_is_not_blocked():
    idea = ("attack twin primes by injecting a parity-breaking automorphic (GL(2)) input that distinguishes "
            "primes from products of two primes")
    v = barrier_membership(idea, _pack())
    assert v is None or v.status == NOT_BLOCKED        # took an admissible exit → not the dead route
    j = gsl.judge(idea, pack=_pack())
    assert j.verdict != "DEAD_BY_BARRIER"


def test_bounded_gaps_objective_is_not_blocked():
    """Maynard–Tao bounded gaps use sieves but target a FINITE bound, not gap 2 — the barrier must NOT fire."""
    idea = "a multidimensional sieve achieving a finite bounded gap H between primes"
    v = barrier_membership(idea, _pack())
    assert v is None or v.status != DEAD_BY_BARRIER


def test_barrier_is_domain_scoped():
    """The parity barrier applies to number_theory only — it must not fire on an unrelated domain's idea."""
    v = barrier_membership("a sieve for twin primes at gap 2", gsl.get_pack("coding"))
    assert v is None
