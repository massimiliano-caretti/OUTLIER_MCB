"""F5 world-test — the toward-objective loop advances a certified frontier and never regresses.

RED→GREEN: on a toy problem with decidable lemmas, the loop advances the frontier by ≥1 certified step,
kills a false lemma with a counterexample (turning it into a next lever), skips a barrier-dead route, and on
3 runs with different sub-lemma orderings ('seeds') reaches the SAME frontier and never a worse one. The
parent problem stays CONJECTURE — never PROVED.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import OUTLIER_MCB as gsl
from OUTLIER_MCB.math_discovery import Conjecture
from OUTLIER_MCB.frontier_search import frontier_search, LemmaCandidate

_PROBLEM = "toy_gap_problem"
_METRIC = "H"   # a bound we want to DECREASE toward the objective 10


def _candidates():
    # three certified-decreasing lemmas (true), one false lemma (gets refuted → next lever)
    true_30 = LemmaCandidate("H<=30", Conjecture(statement="bound 30", variables={"n": (1, 20)}, domain="int"),
                             _METRIC, 30, "decrease", predicate=lambda n: n >= 1)
    true_20 = LemmaCandidate("H<=20", Conjecture(statement="bound 20", variables={"n": (1, 20)}, domain="int"),
                             _METRIC, 20, "decrease", predicate=lambda n: n * n >= n)
    true_14 = LemmaCandidate("H<=14", Conjecture(statement="bound 14", variables={"n": (1, 20)}, domain="int"),
                             _METRIC, 14, "decrease", predicate=lambda n: n + 1 > n)
    false_5 = LemmaCandidate("H<=5", Conjecture(statement="bound 5", variables={"n": (1, 20)}, domain="int"),
                             _METRIC, 5, "decrease", predicate=lambda n: n * n < 100)  # false at n>=10
    return [true_30, true_20, true_14, false_5]


def test_loop_advances_a_certified_frontier_and_keeps_failures():
    rep = frontier_search(_PROBLEM, _candidates(), objective_metric=_METRIC, objective_value=10)
    assert len(rep.advanced) >= 1
    assert rep.ledger.best(_PROBLEM, _METRIC) == 14            # best true bound certified
    assert rep.parent_status == "CONJECTURE"                  # never PROVED
    assert any("H<=5" in lev for lev in rep.next_levers)      # the false lemma became a next lever
    assert rep.residual() == 4                                # |14 - 10|


def test_never_regresses_across_three_seeds():
    import itertools
    cands = _candidates()
    # three different orderings stand in for three seeds; the certified frontier must be identical and monotone
    finals = []
    for order in list(itertools.permutations(range(len(cands))))[:3]:
        rep = frontier_search(_PROBLEM, [cands[i] for i in order], objective_metric=_METRIC, objective_value=10)
        finals.append(rep.ledger.best(_PROBLEM, _METRIC))
    assert finals == [14, 14, 14]                             # order-independent, never worse


def test_shared_ledger_only_moves_forward_across_calls():
    led = gsl.FrontierLedger()
    frontier_search(_PROBLEM, _candidates(), objective_metric=_METRIC, objective_value=10, ledger=led)
    best_after_first = led.best(_PROBLEM, _METRIC)
    # a second pass offering only WORSE certified bounds must not move the frontier back
    worse = [LemmaCandidate("H<=40", Conjecture(statement="bound 40", variables={"n": (1, 5)}, domain="int"),
                            _METRIC, 40, "decrease", predicate=lambda n: True)]
    frontier_search(_PROBLEM, worse, objective_metric=_METRIC, objective_value=10, ledger=led)
    assert led.best(_PROBLEM, _METRIC) == best_after_first == 14


def test_barrier_dead_route_is_skipped():
    nt = gsl.get_pack("number_theory")
    dead = LemmaCandidate("classic sieve twin primes gap 2",
                          Conjecture(statement="classical Selberg sieve for twin primes at gap 2"),
                          "H", 2, "decrease", predicate=lambda n: True)
    rep = frontier_search("twin_primes", [dead], objective_metric="H", objective_value=2, pack=nt)
    assert len(rep.dead_routes) == 1 and not rep.advanced
    assert rep.parent_status == "CONJECTURE"
