"""red_team — a dedicated adversarial evaluator that ATTACKS a candidate instead of waiting for it to pass.

HiddenEvaluator settles a candidate on cases handed to it; the red team GENERATES the cases meant to BREAK
it — boundary perturbations it must still handle, negative controls it must FAIL (passing one is leakage),
and a prior-art probe that survives only if the idea is not a renamed known one. A candidate is kept only if
it survives ALL attacks: the burden of proof is on the idea, and the engine actively tries to refute it.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, List, Sequence

from .evaluators.base import BaseEvaluator, EvaluationResult


@dataclass
class Attack:
    """One adversarial probe. `survived(candidate) -> bool` is True iff the candidate WITHSTOOD this attack
    (for a negative control, withstanding means correctly FAILING it — see negative_control_attacks)."""
    name: str
    survived: Callable
    kind: str = "robustness"        # robustness | leakage | rebrand
    note: str = ""


class RedTeamEvaluator(BaseEvaluator):
    """Runs a battery of attacks against each candidate and keeps only those that survive (by default) ALL of
    them. A hard correctness gate: a plausible idea that breaks under its own red team cannot win the loop."""
    name = "red_team"
    is_correctness = True
    settles_externally = True           # generated attacks are an external resolver: it actively tries to refute

    def __init__(self, attacks: Sequence[Attack], name: str = "red_team", survive_threshold: float = 1.0):
        self.attacks = list(attacks)
        self.name = name
        self.survive_threshold = survive_threshold

    def _run(self, candidate, workspace=None) -> EvaluationResult:
        if not self.attacks:
            return EvaluationResult(passed=False, score=0.0, components={"attacks": 0.0},
                                    error="no attacks generated — nothing was tested",
                                    artifacts={"verdict": "untested"})
        outcomes = []
        for a in self.attacks:
            try:
                ok = bool(a.survived(candidate))
            except Exception:
                ok = False                              # an attack that errors counts as a break, never a pass
            outcomes.append((a, ok))
        broke = [a for a, ok in outcomes if not ok]
        survived = len(outcomes) - len(broke)
        frac = round(survived / len(outcomes), 4)
        passed = frac >= self.survive_threshold
        comps = {"attacks": float(len(outcomes)), "survived": float(survived), "survived_fraction": frac,
                 "leakage_detected": 1.0 if any(a.kind == "leakage" for a in broke) else 0.0,
                 "rebrand_detected": 1.0 if any(a.kind == "rebrand" for a in broke) else 0.0}
        return EvaluationResult(
            passed=passed, score=frac, components=comps,
            error="" if passed else "broke under: " + ", ".join(a.name for a in broke),
            artifacts={"broken_attacks": [a.name for a in broke],
                       "verdict": "robust" if passed else "broken by red team"})


# ── attack builders (the red team generates these; you do not hand-write the cases) ────────────────────
def boundary_attacks(check: Callable, cases: Sequence, mutators: Sequence[Callable]) -> List[Attack]:
    """For each case × mutator, an attack the candidate survives iff it STILL handles the perturbed case.
    `check(candidate, case) -> bool`; `mutator(case) -> case` pushes the case to a boundary/edge."""
    out: List[Attack] = []
    for i, case in enumerate(cases):
        for j, mut in enumerate(mutators):
            adv = mut(case)
            out.append(Attack(name=f"boundary[{i}.{j}]", kind="robustness",
                              survived=lambda c, adv=adv: bool(check(c, adv)),
                              note="perturbed case the candidate must still handle"))
    return out


def negative_control_attacks(check: Callable, controls: Sequence) -> List[Attack]:
    """Controls a REAL mechanism MUST fail; the candidate survives iff it does NOT pass them. Passing a
    negative control is leakage, not a discovery — so survival is the negation of the check."""
    return [Attack(name=f"neg_control[{i}]", kind="leakage",
                   survived=lambda c, ctrl=ctrl: not bool(check(c, ctrl)),
                   note="must FAIL this — passing it is leakage")
            for i, ctrl in enumerate(controls)]


def rebrand_attack(provider, claim_text: str = "", threshold: float = 0.6) -> Attack:
    """A prior-art probe: the candidate survives iff NO existing work matches closely (it is not a renamed
    known idea). Uses any PriorArtProvider; on a search failure it abstains (survives) — absence is not proof."""
    def survived(candidate) -> bool:
        text = claim_text or getattr(candidate, "negation", "") or getattr(candidate, "name", "")
        try:
            from .novelty import rebranding_detector
            res = provider.research(text)
            matches = res.get("matches") or res.get("sources") or []
            return not rebranding_detector(matches, threshold=threshold)
        except Exception:
            return True
    return Attack(name="rebrand", kind="rebrand", survived=survived, note="prior-art probe (renamed ⇒ broken)")


def red_team_from_check(check: Callable, public_cases: Sequence, mutators: Sequence[Callable] = (),
                        negative_controls: Sequence = (), provider=None, claim_text: str = "",
                        survive_threshold: float = 1.0) -> RedTeamEvaluator:
    """Assemble a full red team from a single check: boundary perturbations of the public cases, negative
    controls it must fail, and (optionally) a prior-art rebrand probe. One call → an adversarial gate."""
    attacks: List[Attack] = []
    if mutators:
        attacks += boundary_attacks(check, public_cases, mutators)
    attacks += negative_control_attacks(check, negative_controls)
    if provider is not None:
        attacks.append(rebrand_attack(provider, claim_text=claim_text))
    return RedTeamEvaluator(attacks, survive_threshold=survive_threshold)
