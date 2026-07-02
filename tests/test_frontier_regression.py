"""F6 world-test — «never regress» is a CI invariant (this test runs in CI via pytest).

GREEN: the current certified frontier matches/beats the committed baseline. Negative controls: a worsened
frontier and an uncertified-on-frontier artifact are both caught by the guard.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from OUTLIER_MCB.frontier_ledger import FrontierLedger
from evals.frontier_regression import (run, build_current_frontier, check_no_regression, BASELINE_PATH)


def test_current_frontier_does_not_regress_against_baseline():
    report = run(BASELINE_PATH)
    assert report.ok, report.markdown()


def test_guard_catches_a_worsened_frontier():
    baseline = FrontierLedger.load(BASELINE_PATH)
    worse = FrontierLedger()
    # a frontier that is certified but WORSE than baseline (H=99 vs 14) must be flagged
    worse.frontier.setdefault("toy_gap_problem", {})["H"] = type(baseline.frontier["toy_gap_problem"]["H"])(
        metric="H", direction="decrease", value=99.0, evidence_status="NUMERIC_VERIFIED")
    rep = check_no_regression(worse, baseline)
    assert not rep.ok and rep.regressions


def test_guard_catches_an_uncertified_frontier_record():
    baseline = FrontierLedger.load(BASELINE_PATH)
    bad = build_current_frontier()
    # tamper: stamp a non-certified status onto the frontier record → must be caught
    bad.frontier["toy_gap_problem"]["H"].evidence_status = "EMPIRICALLY_SUPPORTED"
    rep = check_no_regression(bad, baseline)
    assert not rep.ok and rep.uncertified


def test_guard_catches_a_missing_certified_result():
    baseline = FrontierLedger.load(BASELINE_PATH)
    empty = FrontierLedger()
    rep = check_no_regression(empty, baseline)
    assert not rep.ok and rep.missing
