"""G7 — «never regress» as a CI test: the portfolio must keep closing the baseline lemmas, never certify an OPEN
conjecture, and never report a proof without a real external certificate. Deterministic (z3 + exhaustive numeric)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evals.solver_regression import run_regression, BASELINE_CLOSED, REGRESSION_SET


def test_portfolio_meets_the_no_regression_baseline():
    rep = run_regression()
    assert rep.ok, rep.markdown()
    assert rep.closed >= BASELINE_CLOSED
    assert not rep.violations


def test_open_conjecture_is_never_certified():
    rep = run_regression()
    row = next(r for r in rep.rows if r["id"] == "twin_infinite")
    assert row["certified"] is False and row["status"] == "UNKNOWN_TIMEOUT"   # the mother stays CONJECTURE


def test_repeated_runs_are_deterministic():
    a, b = run_regression(), run_regression()
    assert [(r["id"], r["status"]) for r in a.rows] == [(r["id"], r["status"]) for r in b.rows]


def test_every_certified_row_has_an_external_certificate():
    from OUTLIER_MCB.certificates import is_external_certificate
    for r in run_regression().rows:
        if r["certified"]:
            assert is_external_certificate({"status": r["status"]})    # no certified-without-external ever
