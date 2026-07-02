"""evals.frontier_regression — make «never regress» a TESTED invariant, not a promise.

This guard FAILS if a change to the codebase (a) lowers a previously-certified frontier result, or (b) lets an
UNCERTIFIED claim sit on the frontier. It compares the current certified frontier (rebuilt deterministically by
the toy `frontier_search` loop) against a committed baseline snapshot. Run in CI via pytest.

It is a TOY frontier (the harness's own decidable problem), not a claim about real mathematics — its only job
is to verify the engine's monotonicity machinery keeps working: partial certified progress can only move
forward, and only an external certificate may sit on the frontier.
"""
from __future__ import annotations
import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from OUTLIER_MCB.frontier_ledger import FrontierLedger, CERTIFIED_STATUSES
from OUTLIER_MCB.frontier_search import frontier_search, LemmaCandidate
from OUTLIER_MCB.math_discovery import Conjecture

BASELINE_PATH = os.path.join(os.path.dirname(__file__), "frontier_baseline.json")
_PROBLEM, _METRIC = "toy_gap_problem", "H"


def build_current_frontier() -> FrontierLedger:
    """Deterministically rebuild the toy certified frontier (the same loop the F5 test exercises)."""
    candidates = [
        LemmaCandidate("H<=30", Conjecture(statement="b30", variables={"n": (1, 20)}, domain="int"),
                       _METRIC, 30, "decrease", predicate=lambda n: n >= 1),
        LemmaCandidate("H<=20", Conjecture(statement="b20", variables={"n": (1, 20)}, domain="int"),
                       _METRIC, 20, "decrease", predicate=lambda n: n * n >= n),
        LemmaCandidate("H<=14", Conjecture(statement="b14", variables={"n": (1, 20)}, domain="int"),
                       _METRIC, 14, "decrease", predicate=lambda n: n + 1 > n),
    ]
    rep = frontier_search(_PROBLEM, candidates, objective_metric=_METRIC, objective_value=10)
    return rep.ledger


@dataclass
class RegressionReport:
    ok: bool
    regressions: List[str] = field(default_factory=list)
    uncertified: List[str] = field(default_factory=list)
    missing: List[str] = field(default_factory=list)

    def markdown(self) -> str:
        head = "## Frontier regression guard — " + ("PASS (no regression)" if self.ok else "FAIL")
        body = ([f"- REGRESSION: {r}" for r in self.regressions]
                + [f"- UNCERTIFIED on frontier: {u}" for u in self.uncertified]
                + [f"- MISSING (lost a certified result): {m}" for m in self.missing])
        return "\n".join([head] + body) if body else head


def _worse(direction: str, current: float, baseline: float) -> bool:
    return current > baseline if direction == "decrease" else current < baseline


def check_no_regression(current: FrontierLedger, baseline: FrontierLedger) -> RegressionReport:
    """A change is a regression iff a baseline (problem, metric) is now missing, worse in its direction, or
    backed by a non-certified status. Equal-or-better and still-certified ⇒ PASS."""
    regressions: List[str] = []
    uncertified: List[str] = []
    missing: List[str] = []
    # (a) every certified frontier record must stay certified — current artifact must never carry a bad status
    for problem, metrics in current.frontier.items():
        for metric, rec in metrics.items():
            if rec.evidence_status not in CERTIFIED_STATUSES:
                uncertified.append(f"{problem}/{metric}={rec.value} (status {rec.evidence_status})")
    # (b) no baseline result may be lost or worsened
    for problem, metrics in baseline.frontier.items():
        for metric, brec in metrics.items():
            crec = current.frontier.get(problem, {}).get(metric)
            if crec is None:
                missing.append(f"{problem}/{metric} (was {brec.value})")
                continue
            if _worse(brec.direction, crec.value, brec.value):
                regressions.append(f"{problem}/{metric}: {crec.value} worse than baseline {brec.value} "
                                   f"({brec.direction})")
    ok = not (regressions or uncertified or missing)
    return RegressionReport(ok=ok, regressions=regressions, uncertified=uncertified, missing=missing)


def write_baseline(path: str = BASELINE_PATH) -> None:
    build_current_frontier().save(path)


def run(path: str = BASELINE_PATH) -> RegressionReport:
    """Compare the current frontier against the committed baseline. Exits non-zero on regression (CLI use)."""
    if not os.path.exists(path):
        write_baseline(path)
    baseline = FrontierLedger.load(path)
    return check_no_regression(build_current_frontier(), baseline)


if __name__ == "__main__":   # pragma: no cover - CLI entry for CI
    import sys
    report = run()
    print(report.markdown())
    sys.exit(0 if report.ok else 1)
