"""solver_regression — the anti-regression guard for the prover portfolio (G7). «Never regress» becomes a test.

A FIXED regression set of lemmas with KNOWN outcomes. The eval FAILS if:
  (a) the portfolio closes FEWER of the decidable lemmas than the baseline (a capability regression);
  (b) any lemma is FORMALLY_PROVED without a real EXTERNAL certificate behind it (a false proof);
  (c) an OPEN conjecture (infinite domain) is ever certified PROVED (overclaim).
Deterministic; uses only z3 (always-present here) + the zero-dep exhaustive numeric path, so it runs everywhere.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List

from OUTLIER_MCB.math_discovery import Conjecture, settle_lemma, z3_backend, LEMMA_CERTIFIED
from OUTLIER_MCB.solver_portfolio import portfolio_backend
from OUTLIER_MCB.certificates import is_external_certificate

# (id, conjecture, predicate|None, expected ∈ {CLOSE, REFUTE, OPEN})
REGRESSION_SET = [
    ("amgm", Conjecture("AM-GM", claim_expr="x**2 + y**2 >= 2*x*y", variables={"x": (-9, 9), "y": (-9, 9)}), None, "CLOSE"),
    ("sq_nonneg", Conjecture("x^2 >= 0", claim_expr="x*x >= 0", variables={"x": (-9, 9)}), None, "CLOSE"),
    ("false_sq_neg", Conjecture("x^2 < 0", claim_expr="x*x < 0", variables={"x": (-9, 9)}), None, "REFUTE"),
    ("finite_sq_ge_n", Conjecture("n^2 >= n on [1,50]", variables={"n": (1, 50)}, domain="int"),
     (lambda n: n * n >= n), "CLOSE"),   # exhaustively TRUE over a finite box → NUMERIC_VERIFIED (zero-dep)
    ("twin_infinite", Conjecture("twin primes are infinite", claim_expr="isprime(n) && isprime(n + 2)",
                                 variables={"n": (float("-inf"), float("inf"))}, domain="int"), None, "OPEN"),
]

BASELINE_CLOSED = 3   # amgm + sq_nonneg (z3) + finite_primes (exhaustive) — the floor the portfolio must never drop below


@dataclass
class RegressionReport:
    closed: int = 0
    refuted: int = 0
    open_uncertified: int = 0
    rows: List[Dict] = field(default_factory=list)
    violations: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations and self.closed >= BASELINE_CLOSED

    def markdown(self) -> str:
        L = [f"## Solver anti-regression — closed {self.closed} (baseline {BASELINE_CLOSED}), refuted {self.refuted}, "
             f"open-uncertified {self.open_uncertified}", f"- ok: **{self.ok}**  · violations: {self.violations or 'none'}"]
        for r in self.rows:
            L.append(f"  - {r['id']:16} expected {r['expected']:7} → {r['status']:16} "
                     f"(via {r['method']}, certified={r['certified']})")
        return "\n".join(L)


def run_regression(backend=None) -> RegressionReport:
    """Settle every lemma in the regression set with the portfolio (z3 present; others opt-in). Flag any violation
    of the three anti-regression rules. Deterministic."""
    backend = backend if backend is not None else portfolio_backend()
    rep = RegressionReport()
    for lid, conj, pred, expected in REGRESSION_SET:
        cert = settle_lemma(conj, predicate=pred, backend=backend)
        certified = cert.certified
        rep.rows.append({"id": lid, "expected": expected, "status": cert.status,
                         "method": cert.method, "certified": certified})
        # (b) a certified status must be backed by a REAL external certificate
        if certified and not is_external_certificate({"status": cert.status}):
            rep.violations.append(f"{lid}: certified status {cert.status} is not an external certificate")
        if expected == "CLOSE":
            if cert.status in LEMMA_CERTIFIED and cert.status not in ("Z3_REFUTED", "NUMERIC_REFUTED"):
                rep.closed += 1
            else:
                rep.violations.append(f"{lid}: expected to CLOSE but got {cert.status}")
        elif expected == "REFUTE":
            if cert.status in ("Z3_REFUTED", "NUMERIC_REFUTED"):
                rep.refuted += 1
            else:
                rep.violations.append(f"{lid}: expected to REFUTE but got {cert.status}")
        elif expected == "OPEN":
            # (c) an OPEN conjecture must NEVER be certified as proved
            if certified:
                rep.violations.append(f"{lid}: an OPEN conjecture was certified {cert.status} — OVERCLAIM")
            else:
                rep.open_uncertified += 1
    return rep


if __name__ == "__main__":   # pragma: no cover
    print(run_regression().markdown())
