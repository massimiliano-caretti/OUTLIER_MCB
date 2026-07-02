"""F3 world-test — the monotone, externally-certified frontier (never regresses).

RED→GREEN: the bound sequence 7e7 → 600 → 246 is accepted and monotone; a worsening claim (500 → 700) is
REGRESSION_REJECTED and never written; a claim without an external certificate is UNCERTIFIED_REJECTED (no
self-judgment). Deterministic JSON round-trips.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import OUTLIER_MCB as gsl
from OUTLIER_MCB.frontier_ledger import (FrontierLedger, ACCEPTED, REGRESSION_REJECTED,
                                            UNCERTIFIED_REJECTED, DIRECTION_MISMATCH)

_CERT = {"status": "NUMERIC_VERIFIED", "detail": "exhaustive over the declared domain"}
_PROB, _METRIC = "twin_prime_gap", "H"


def test_decreasing_sequence_is_accepted_and_monotone():
    led = FrontierLedger()
    for v in (7e7, 600, 246):
        r = led.claim(_PROB, _METRIC, v, "decrease", _CERT)
        assert r.accepted and r.outcome == ACCEPTED
    assert led.best(_PROB, _METRIC) == 246


def test_regression_is_rejected_and_frontier_protected():
    led = FrontierLedger()
    assert led.claim(_PROB, _METRIC, 500, "decrease", _CERT).accepted
    r = led.claim(_PROB, _METRIC, 700, "decrease", _CERT)          # worse → must be rejected
    assert not r.accepted and r.outcome == REGRESSION_REJECTED
    assert led.best(_PROB, _METRIC) == 500                          # frontier untouched


def test_equal_value_does_not_advance():
    led = FrontierLedger()
    led.claim(_PROB, _METRIC, 246, "decrease", _CERT)
    r = led.claim(_PROB, _METRIC, 246, "decrease", _CERT)          # not STRICTLY better
    assert not r.accepted and r.outcome == REGRESSION_REJECTED


def test_uncertified_claim_is_rejected_no_self_judgment():
    led = FrontierLedger()
    r = led.claim(_PROB, _METRIC, 100, "decrease", {"status": "EMPIRICALLY_SUPPORTED"})  # sampling ≠ certificate
    assert not r.accepted and r.outcome == UNCERTIFIED_REJECTED
    r2 = led.claim(_PROB, _METRIC, 100, "decrease", None)                                # no evidence at all
    assert not r2.accepted and r2.outcome == UNCERTIFIED_REJECTED
    assert led.best(_PROB, _METRIC) is None


def test_increase_direction_and_mismatch():
    led = FrontierLedger()
    assert led.claim("p", "score", 10, "increase", _CERT).accepted
    assert led.claim("p", "score", 12, "increase", _CERT).accepted
    assert led.best("p", "score") == 12
    assert led.claim("p", "score", 11, "increase", _CERT).outcome == REGRESSION_REJECTED
    assert led.claim("p", "score", 99, "decrease", _CERT).outcome == DIRECTION_MISMATCH


def test_deterministic_round_trip():
    led = FrontierLedger()
    for v in (7e7, 600, 246):
        led.claim(_PROB, _METRIC, v, "decrease", _CERT)
    path = os.path.join(tempfile.mkdtemp(), "frontier.json")
    led.save(path)
    again = FrontierLedger.load(path)
    assert again.best(_PROB, _METRIC) == 246
    # the serialized form is stable (sorted keys) → reproducible
    with open(path) as f:
        first = f.read()
    again.save(path)
    with open(path) as f:
        assert f.read() == first
