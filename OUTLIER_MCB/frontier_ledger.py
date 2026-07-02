"""frontier_ledger — the monotone, externally-certified frontier: «always toward the objective, never back».

An open problem is attacked by a sequence of PARTIAL certified results — e.g. the bound H on prime gaps:
7·10⁷ → 600 → 246. This ledger makes that monotone by construction:

  • a claim is accepted ONLY if (a) it carries a VALID EXTERNAL CERTIFICATE (z3 / Lean / exhaustive numeric —
    never the engine's own score: no self-judgment), AND (b) it STRICTLY improves the frontier in the declared
    direction;
  • a claim that would worsen the frontier is REGRESSION_REJECTED and never written;
  • an uncertified claim is UNCERTIFIED_REJECTED.

So the stored frontier can only move toward the objective. Persistence is deterministic (sorted JSON) so the
frontier is inspectable and reproducible. It records partial PROGRESS; it never asserts the parent conjecture
is proved — that honesty is the engine, not the brake.
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .certificates import EXTERNAL_CERTIFICATES, is_external_certificate as _is_external

# the statuses that count as an external certificate — DOMAIN-AGNOSTIC (math proof, physics simulation, wet-lab
# reproduction, ML dataset eval, benchmark, green repo test, or the protected-invariant suite). Single source of
# truth in certificates.py. Anything else — UNKNOWN_TIMEOUT, a refutation, mere sampling, a missing status — is
# NOT a certificate. The engine's own score never qualifies.
CERTIFIED_STATUSES = EXTERNAL_CERTIFICATES
DIRECTIONS = ("decrease", "increase")

# claim outcomes
ACCEPTED = "ACCEPTED"
REGRESSION_REJECTED = "REGRESSION_REJECTED"
UNCERTIFIED_REJECTED = "UNCERTIFIED_REJECTED"
DIRECTION_MISMATCH = "DIRECTION_MISMATCH"
INVALID_CLAIM = "INVALID_CLAIM"


def _evidence_status(evidence) -> str:
    if evidence is None:
        return ""
    if isinstance(evidence, dict):
        return str(evidence.get("status", ""))
    return str(getattr(evidence, "status", ""))


def is_certified(evidence) -> bool:
    """True iff `evidence` carries an EXTERNAL-resolver status in CERTIFIED_STATUSES (any domain). The engine's
    own score never qualifies — only a real external resolver (proof / simulation / reproduction / eval / test)."""
    return _is_external(evidence)


def _strictly_improves(direction: str, new: float, current: Optional[float]) -> bool:
    if current is None:
        return True                                  # first certified value establishes the frontier
    return new < current if direction == "decrease" else new > current


@dataclass
class FrontierClaim:
    problem: str
    metric: str
    value: float
    direction: str
    evidence_status: str
    accepted: bool
    outcome: str
    reason: str
    note: str = ""


@dataclass
class ClaimResult:
    outcome: str                     # ACCEPTED | REGRESSION_REJECTED | UNCERTIFIED_REJECTED | DIRECTION_MISMATCH | INVALID_CLAIM
    accepted: bool
    reason: str
    previous: Optional[float] = None
    value: Optional[float] = None

    @property
    def ok(self) -> bool:
        return self.accepted


@dataclass
class _Record:
    metric: str
    direction: str
    value: float
    evidence_status: str
    note: str = ""


@dataclass
class FrontierLedger:
    """A monotone frontier per (problem, metric). Accepted claims only ever move toward the objective."""
    # problem -> metric -> current best record
    frontier: Dict[str, Dict[str, _Record]] = field(default_factory=dict)
    history: List[FrontierClaim] = field(default_factory=list)

    def best(self, problem: str, metric: str) -> Optional[float]:
        rec = self.frontier.get(problem, {}).get(metric)
        return rec.value if rec else None

    def direction_of(self, problem: str, metric: str) -> Optional[str]:
        rec = self.frontier.get(problem, {}).get(metric)
        return rec.direction if rec else None

    def claim(self, problem: str, metric: str, value: float, direction: str, evidence,
              note: str = "") -> ClaimResult:
        """Attempt to advance the frontier. Accepts ONLY a certified, strictly-improving claim; otherwise the
        frontier is left untouched and the rejection reason is returned (and recorded in history)."""
        status = _evidence_status(evidence)
        current = self.best(problem, metric)
        prior_dir = self.direction_of(problem, metric)

        def _record(outcome: str, accepted: bool, reason: str) -> ClaimResult:
            self.history.append(FrontierClaim(problem=problem, metric=metric, value=float(value),
                                              direction=direction, evidence_status=status, accepted=accepted,
                                              outcome=outcome, reason=reason, note=note))
            return ClaimResult(outcome=outcome, accepted=accepted, reason=reason, previous=current,
                               value=float(value) if accepted else current)

        if direction not in DIRECTIONS:
            return _record(INVALID_CLAIM, False, f"direction must be one of {DIRECTIONS}, got '{direction}'")
        if prior_dir is not None and direction != prior_dir:
            return _record(DIRECTION_MISMATCH, False,
                           f"'{metric}' was declared '{prior_dir}'; a claim cannot switch to '{direction}'")
        if not is_certified(evidence):
            return _record(UNCERTIFIED_REJECTED, False,
                           f"no external certificate (status '{status or '∅'}' ∉ {CERTIFIED_STATUSES}); "
                           "the engine never self-certifies a frontier advance")
        if not _strictly_improves(direction, float(value), current):
            return _record(REGRESSION_REJECTED, False,
                           f"{value} does not strictly improve the frontier ({current}) in direction '{direction}' "
                           "— never regress")
        # ACCEPT: move the frontier toward the objective
        self.frontier.setdefault(problem, {})[metric] = _Record(metric=metric, direction=direction,
                                                                value=float(value), evidence_status=status, note=note)
        return _record(ACCEPTED, True, f"certified ({status}) and strictly improves {current} → {value}")

    # ── deterministic persistence (sorted JSON) ──
    def to_dict(self) -> Dict:
        return {
            "frontier": {p: {m: {"metric": r.metric, "direction": r.direction, "value": r.value,
                                 "evidence_status": r.evidence_status, "note": r.note}
                             for m, r in sorted(metrics.items())}
                         for p, metrics in sorted(self.frontier.items())},
            "history": [c.__dict__ for c in self.history],
        }

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, sort_keys=True, ensure_ascii=False)

    @classmethod
    def load(cls, path: str) -> "FrontierLedger":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        led = cls()
        for p, metrics in data.get("frontier", {}).items():
            for m, r in metrics.items():
                led.frontier.setdefault(p, {})[m] = _Record(metric=r["metric"], direction=r["direction"],
                                                            value=r["value"], evidence_status=r["evidence_status"],
                                                            note=r.get("note", ""))
        led.history = [FrontierClaim(**c) for c in data.get("history", [])]
        return led

    def markdown(self) -> str:
        L = ["## Frontier ledger — certified, monotone (never regresses)"]
        for p, metrics in sorted(self.frontier.items()):
            for m, r in sorted(metrics.items()):
                L.append(f"- **{p} · {m}** = {r.value} ({r.direction}, certified by {r.evidence_status})")
        rejected = [c for c in self.history if not c.accepted]
        if rejected:
            L.append(f"- rejected claims (frontier protected): {len(rejected)} "
                     f"({sum(1 for c in rejected if c.outcome == REGRESSION_REJECTED)} regressions, "
                     f"{sum(1 for c in rejected if c.outcome == UNCERTIFIED_REJECTED)} uncertified)")
        return "\n".join(L)
