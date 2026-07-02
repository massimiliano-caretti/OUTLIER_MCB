"""test_proposals_rank_ledger — proposals #1 (rarity-weighted break ranking) and #4 (in-loop ledger).

#1: a break that has already failed often is worn; a rarely-failed one reaches further. The rarity term
re-orders only within an equal axis priority and is a NO-OP when failure_memory is empty (so the built-in
packs are unaffected). #4: passing a ledger makes creative_search LEARN during the run (winning operators
gain weight, losing ones lose it) while NEVER altering the external evaluator's score; without a ledger the
loop is byte-for-byte unchanged (determinism guard).
"""
import random

import OUTLIER_MCB as gsl
from OUTLIER_MCB.core import Assumption


def _two_assumption_pack(failure_memory):
    return gsl.DomainPack(
        name="rank_probe", keywords=["rank probe domain"], box_name="probe box",
        assumptions=[
            Assumption("assume_a", "A.", "obvious A.", "not A.", ["fam"], "kill A."),
            Assumption("assume_b", "B.", "obvious B.", "not B.", ["fam"], "kill B."),
        ],
        relations=[], dimension_of={"assume_a": "X", "assume_b": "X"},
        box_assumptions={"assume_a", "assume_b"},
        axes={"X": {"priority": 1, "verdict": "the only axis."}},
        known_families=["fam"], info_kinds={}, failure_memory=failure_memory, world_factory=None)


# ── #1: rarity tiebreak ─────────────────────────────────────────────────────────────────────────────
def test_rarity_reorders_equal_priority_breaks():
    # assume_a has a DEAD failure on its name → it is the worn break → assume_b should rank first.
    pack = _two_assumption_pack({"dead1": {"status": "DEAD_COLLAPSED", "assumption": "assume_a"}})
    g = gsl.graph_of(pack)
    assert gsl.kernel._ranked_breakable(pack, g)[0] == "assume_b"


def test_empty_failure_memory_is_a_noop():
    # no failures → rarity is 0 for both → deterministic fallback to name order (assume_a first).
    pack = _two_assumption_pack({})
    g = gsl.graph_of(pack)
    assert gsl.kernel._ranked_breakable(pack, g) == ["assume_a", "assume_b"]
    assert gsl.kernel._failure_count(pack, "assume_a") == 0


def test_builtin_pack_ranking_unaffected():
    # the built-in packs carry empty failure_memory, so their ranking must be byte-for-byte unchanged.
    pack = gsl.get_pack("numeric")
    g = gsl.graph_of(pack)
    assert all(gsl.kernel._failure_count(pack, a.name) == 0 for a in pack.assumptions)


# ── #4: in-loop ledger ──────────────────────────────────────────────────────────────────────────────
def _interaction_data(n=120, seed=7):
    rng = random.Random(seed)
    X = [[rng.uniform(-2, 2), rng.uniform(-2, 2), rng.uniform(-2, 2)] for _ in range(n)]
    y = [2.0 * r[0] * r[1] - 3.0 for r in X]
    cut = int(0.66 * n)
    return X[:cut], y[:cut], X[cut:], y[cut:]


def test_ledger_learns_in_loop():
    pack = gsl.get_pack("numeric")
    ev = gsl.symbolic_evaluator(_interaction_data(), pack=pack)
    led = gsl.Ledger()
    res = gsl.creative_search("discover a law", evaluator=ev, pack=pack, budget=24, ledger=led)
    assert res.ledger is led
    summ = led.summary()
    assert summ["won"] > 0 and summ["lost"] > 0          # it settled bets BOTH ways during the single run
    # a winning (axis×operator) ends up weighted above an untried baseline; a losing one below it.
    weights = led.policy()
    assert any(w > 1.0 for w in weights.values()) and any(w < 1.0 for w in weights.values())
    # learning must not break discovery: the law is still found.
    assert res.best().score > 0.7


def test_no_ledger_is_deterministic_and_unchanged():
    pack = gsl.get_pack("numeric")
    ev = gsl.symbolic_evaluator(_interaction_data(), pack=pack)
    r1 = gsl.creative_search("discover a law", evaluator=ev, pack=pack, budget=20)
    r2 = gsl.creative_search("discover a law", evaluator=ev, pack=pack, budget=20)
    assert [r.name for r in r1.records] == [r.name for r in r2.records]   # unchanged, deterministic
    assert r1.ledger is None


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
