"""evaluators.hidden — the anti-cheating evaluator: a candidate must pass HIDDEN cases, survive ADVERSARIAL
ones, and NOT pass the negative controls (which would be leakage). The single most important hardening.

If a candidate passes the PUBLIC cases but fails the HIDDEN ones, it optimized the visible, it did not
discover. If it passes the task but ALSO passes a negative control (a perturbation that should break any
real mechanism), the gain is LEAKAGE, not a mechanism. If it only improves on easy cases, it is not an
invention. This evaluator encodes those rules as a hard gate (is_correctness=True) so the evolve loop
cannot reward a conceptual shortcut.
"""
from __future__ import annotations
from typing import Callable, List, Optional, Sequence

from .base import BaseEvaluator, EvaluationResult


class HiddenEvaluator(BaseEvaluator):
    """`check(candidate, case) -> bool` decides whether the candidate handles one case. The candidate is
    settled on cases it NEVER saw (hidden), attacked (adversarial), and tested against negative controls it
    must FAIL. A correctness gate by default."""
    name = "hidden"
    is_correctness = True
    settles_externally = True           # settles on held-out / adversarial / control cases — a real resolver

    def __init__(self, check: Callable, public_cases: Sequence, hidden_cases: Sequence = (),
                 adversarial_cases: Sequence = (), negative_controls: Sequence = (),
                 hidden_threshold: float = 1.0, adversarial_threshold: float = 0.5,
                 leakage_threshold: float = 0.0, name: str = "hidden"):
        self.check, self.name = check, name
        self.public_cases, self.hidden_cases = list(public_cases), list(hidden_cases)
        self.adversarial_cases, self.negative_controls = list(adversarial_cases), list(negative_controls)
        self.hidden_threshold, self.adversarial_threshold, self.leakage_threshold = (
            hidden_threshold, adversarial_threshold, leakage_threshold)

    def _frac(self, candidate, cases) -> Optional[float]:
        if not cases:
            return None
        return round(sum(1 for c in cases if self.check(candidate, c)) / len(cases), 3)

    def _run(self, candidate, workspace=None) -> EvaluationResult:
        pub = self._frac(candidate, self.public_cases)
        hid = self._frac(candidate, self.hidden_cases)
        adv = self._frac(candidate, self.adversarial_cases)
        neg = self._frac(candidate, self.negative_controls)

        hidden_basis = hid if hid is not None else (pub if pub is not None else 0.0)
        adv_basis = adv if adv is not None else 1.0
        leakage = (neg is not None and neg > self.leakage_threshold)
        hidden_ok = (hid is None) or (hid >= self.hidden_threshold)
        adv_ok = (adv is None) or (adv >= self.adversarial_threshold)
        passed = bool(hidden_ok and adv_ok and not leakage)

        score = round(hidden_basis * (1.0 - (neg or 0.0)) * (0.5 + 0.5 * adv_basis), 4)
        notes = []
        if not hidden_ok:
            notes.append("passes public but FAILS hidden — optimized the visible, not a discovery")
        if leakage:
            notes.append("passes a NEGATIVE CONTROL — leakage, not a mechanism")
        if not adv_ok:
            notes.append("does not survive the adversarial cases")
        return EvaluationResult(
            passed=passed, score=score,
            components={"public": pub or 0.0, "hidden": hidden_basis, "adversarial": adv_basis,
                        "negative_control": neg or 0.0, "leakage_detected": 1.0 if leakage else 0.0},
            error="; ".join(notes) if (not passed) else "",
            artifacts={"verdict": "real mechanism" if passed else "shortcut/leakage/overfit"})
