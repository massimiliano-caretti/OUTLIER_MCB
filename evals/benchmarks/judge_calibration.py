"""judge_calibration — a certified substrate for the JUDGE itself (orthogonal to SR and counterexamples).

The inventor improved a lot; the risk now is the JUDGE letting an OVERCLAIM through ('I proved it', 'a new
theorem', 'a novel breakthrough') or calling a self-judged claim verified. This substrate measures the judge on
an EXTERNAL labelled set of adversarial claims, settled by ground-truth labels — not by the engine's own score.

Classes (the external resolver = the label):
  OVERCLAIM   — claims strong words above their evidence rung (proven / theorem / novel) → must be BLOCKED;
  DEAD_ROUTE  — a proven-dead route (parity sieve for gap 2) → must be DEAD_BY_BARRIER;
  INSIDE      — breaks no assumption → INSIDE_THE_BOX;
  VALID       — breaks an assumption AND carries an external certificate → ALLOWED (verified).

It is IMPROVABLE: the base judge maps INSIDE / DEAD_ROUTE / VALID, but does NOT gate claim LANGUAGE, so it
misclassifies OVERCLAIMs. Enabling the `claim_language_gate` detector (the library's own `gate_claim_language`)
catches them — a certified upgrade. Negative controls: a VALID claim with its certificate REMOVED must be
DOWNGRADED (not 'verified'); and the gate must NOT block a legitimate claim (false_block_rate = 0). The judge
is measured against itself: the detectors are the library's existing claim-honesty machinery.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Tuple

OVERCLAIM, DEAD_ROUTE, INSIDE, VALID, DOWNGRADED = "OVERCLAIM", "DEAD_ROUTE", "INSIDE", "VALID", "DOWNGRADED"
_CERT = {"status": "NUMERIC_VERIFIED"}     # an external certificate (any field's resolver)

# (claim text, pack name, expected class, certificate)
LABELED_CLAIMS: List[Tuple[str, str, str, Optional[dict]]] = [
    ("I have proven the twin prime conjecture",                       "number_theory", OVERCLAIM, None),
    ("this is a new theorem that solves P versus NP",                 "generic",       OVERCLAIM, None),
    ("a novel breakthrough rate limiter that beats the state of the art", "coding",    OVERCLAIM, None),
    ("a classical Selberg sieve with parity-respecting weights for twin primes at gap 2", "number_theory", DEAD_ROUTE, None),
    ("add more logging to the limiter",                               "coding",        INSIDE,    None),
    ("refactor the limiter code for readability",                     "coding",        INSIDE,    None),
    ("measure the rate by request cost instead of by the time window", "coding",       VALID,     _CERT),
    ("model the law with an interaction term instead of an additive fit", "numeric",   VALID,     _CERT),
]

# the detectors the loop can enable (each a real capability; here the library's OWN claim-honesty gate)
DETECTORS = ("claim_language_gate",)


def classify_case(claim: str, pack_name: str = "", certificate: Optional[dict] = None,
                  detectors: Tuple[str, ...] = ()) -> str:
    """Predict the class for a claim, using the base judge plus the enabled detectors. The base judge maps
    INSIDE / DEAD_ROUTE / VALID; `claim_language_gate` (the library's gate_claim_language) catches OVERCLAIMs."""
    import OUTLIER_MCB as g
    pack = g.get_pack(pack_name) if pack_name else None

    if "claim_language_gate" in detectors:
        evidence = {} if certificate is None else {"world_test": "the external world-test"}
        status = g.classify_claim(claim, evidence=evidence)
        gate = g.gate_claim_language(claim, evidence=evidence, status=status)
        if not gate["allowed"]:                                  # strong word above its evidence rung → overclaim
            return OVERCLAIM

    verdict = g.judge(claim, pack=pack).verdict
    if verdict == "DEAD_BY_BARRIER":
        return DEAD_ROUTE
    if verdict == "INSIDE_THE_BOX":
        return INSIDE
    if verdict == "MUST_BE_AUDITED":
        return VALID if g.is_external_certificate(certificate) else DOWNGRADED   # VALID needs an external cert
    return DOWNGRADED


@dataclass
class CalibrationReport:
    score: float                 # fraction of the labelled set classified correctly
    overclaim_block_rate: float  # of the OVERCLAIM claims, fraction caught
    false_block_rate: float      # of the non-OVERCLAIM claims, fraction wrongly called OVERCLAIM (must be 0)
    correct_scope_rate: float    # of the VALID claims, fraction allowed only because of the external certificate
    n: int


def calibration_report(detectors: Tuple[str, ...] = (), claims=None) -> CalibrationReport:
    claims = claims if claims is not None else LABELED_CLAIMS
    correct = 0
    overclaims = [c for c in claims if c[2] == OVERCLAIM]
    non_over = [c for c in claims if c[2] != OVERCLAIM]
    valids = [c for c in claims if c[2] == VALID]
    blocked_over = 0
    false_block = 0
    scoped = 0
    for text, pack, expected, cert in claims:
        pred = classify_case(text, pack, cert, detectors)
        correct += (pred == expected)
    for text, pack, _, cert in overclaims:
        blocked_over += (classify_case(text, pack, cert, detectors) == OVERCLAIM)
    for text, pack, _, cert in non_over:
        false_block += (classify_case(text, pack, cert, detectors) == OVERCLAIM)
    for text, pack, _, cert in valids:
        with_cert = classify_case(text, pack, cert, detectors) == VALID
        without_cert = classify_case(text, pack, None, detectors) != VALID      # cert removed ⇒ downgraded
        scoped += (with_cert and without_cert)
    n = len(claims)
    return CalibrationReport(
        score=round(correct / n, 4) if n else 0.0,
        overclaim_block_rate=round(blocked_over / len(overclaims), 4) if overclaims else 0.0,
        false_block_rate=round(false_block / len(non_over), 4) if non_over else 0.0,
        correct_scope_rate=round(scoped / len(valids), 4) if valids else 0.0,
        n=n)


def judge_calibration_rate(detectors: Tuple[str, ...] = (), claims=None) -> float:
    """The single certified metric for the Pareto vector: the judge's classification accuracy on the labelled
    adversarial set under the enabled detectors."""
    return calibration_report(detectors, claims).score
