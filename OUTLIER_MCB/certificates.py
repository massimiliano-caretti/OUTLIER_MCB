"""certificates — the DOMAIN-AGNOSTIC vocabulary of external certificates.

The engine is agnostic: it attacks innovative problems in ANY field — mathematics, physics, biology, chemistry,
mechanics, software, medicine, ML, … — so «settled by an external resolver» must NOT mean only «proved by z3 /
Lean». What counts as an external certificate depends on the domain's own gold standard:

  FORMAL    (math / logic)        — LEAN_CHECKED, Z3_PROVED, NUMERIC_VERIFIED        → a PROOF
  EMPIRICAL (physics/bio/chem/    — SIMULATION_VERIFIED, EXPERIMENT_REPRODUCED,      → a reproducible external
             eng / ML / software)   DATASET_EVAL_PASSED, BENCHMARK_MEASURED,           MEASUREMENT / reproduction
                                     REPO_TEST_GREEN                                    (honestly NOT a proof)
  META      (the engine itself)   — INVARIANTS_VERIFIED                               → the protected-invariant suite

This is the single source of truth for «is this an external certificate?», shared by the frontier ledger and the
frontier search so a physics simulation, a wet-lab reproduction, a held-out ML eval, or a green repo test can
advance a monotone certified frontier exactly like a math lemma — never the engine's own opinion of itself.

Honesty (non-negotiable, all domains): an EMPIRICAL certificate is a reproducible external measurement, NEVER a
proof — the never-regress frontier compares certified VALUES, and the resolver is responsible for the
measurement being reproducible (fixed protocol / seed). Mere sampling (e.g. EMPIRICALLY_SUPPORTED) is evidence,
NOT a certificate, and never advances a frontier.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Optional

# math / logic — a real proof. LEAN_CHECKED (proof assistant), ISABELLE_CHECKED (Isabelle/HOL + Sledgehammer),
# Z3_PROVED / CVC5_PROVED (SMT solvers), VAMPIRE_PROVED / E_PROVED (first-order ATP), NUMERIC_VERIFIED (exhaustive
# finite check — also what PARI/GP's finite computation maps to). Every one is a REAL external resolver; none is
# the engine's own judgment. A proof over a finite domain is a proof of that finite domain ONLY (never of an
# infinite parent conjecture).
FORMAL_CERTIFICATES = ("LEAN_CHECKED", "ISABELLE_CHECKED", "Z3_PROVED", "CVC5_PROVED",
                       "VAMPIRE_PROVED", "E_PROVED", "NUMERIC_VERIFIED")
# physics / biology / chemistry / engineering / ML / software — a reproducible external measurement/reproduction
EMPIRICAL_CERTIFICATES = ("SIMULATION_VERIFIED", "EXPERIMENT_REPRODUCED", "DATASET_EVAL_PASSED",
                          "BENCHMARK_MEASURED", "REPO_TEST_GREEN")
# the engine's own health — the protected-invariant suite re-checked deterministically
META_CERTIFICATES = ("INVARIANTS_VERIFIED",)

EXTERNAL_CERTIFICATES = FORMAL_CERTIFICATES + EMPIRICAL_CERTIFICATES + META_CERTIFICATES

# explicit, per-kind documentation — what external resolver each status names, and for which domains
RESOLVER_KINDS: Dict[str, str] = {
    "LEAN_CHECKED": "a Lean proof was machine-checked (math/logic) — a proof.",
    "ISABELLE_CHECKED": "Isabelle/HOL (via Sledgehammer) machine-checked the proof (math/logic) — a proof.",
    "Z3_PROVED": "the Z3 SMT solver proved the statement in a decidable theory (math/logic) — a proof.",
    "CVC5_PROVED": "the cvc5 SMT solver proved the statement in a decidable theory (math/logic) — a proof.",
    "VAMPIRE_PROVED": "the Vampire first-order ATP found a refutation of the negation (math/logic) — a proof.",
    "E_PROVED": "the E first-order ATP found a refutation of the negation (math/logic) — a proof.",
    "NUMERIC_VERIFIED": "exhaustive check over a finite domain (math/CS; also PARI/GP finite computation) — "
                        "a proof for that finite domain ONLY, never for an infinite parent conjecture.",
    "SIMULATION_VERIFIED": "a deterministic, reproducible simulation confirmed the claim "
                           "(physics / chemistry / engineering / mechanics) — measurement, NOT proof.",
    "EXPERIMENT_REPRODUCED": "a documented experimental protocol reproduced the effect "
                             "(biology / medicine / chemistry) — reproduction, NOT proof.",
    "DATASET_EVAL_PASSED": "a held-out dataset evaluation met the declared bound (ML / data science) — measurement.",
    "BENCHMARK_MEASURED": "a reproducible benchmark measured the value (engineering / CS / ML) — measurement.",
    "REPO_TEST_GREEN": "a real repository test went RED→GREEN against changed source (software) — measurement.",
    "INVARIANTS_VERIFIED": "the protected-invariant suite was re-checked deterministically (the engine itself).",
}


def kind_of(status: str) -> str:
    """Which family a certificate status belongs to: FORMAL | EMPIRICAL | META | NONE."""
    if status in FORMAL_CERTIFICATES:
        return "FORMAL"
    if status in EMPIRICAL_CERTIFICATES:
        return "EMPIRICAL"
    if status in META_CERTIFICATES:
        return "META"
    return "NONE"


def _status_of(evidence) -> str:
    if evidence is None:
        return ""
    if isinstance(evidence, str):
        return evidence
    if isinstance(evidence, dict):
        return str(evidence.get("status", ""))
    return str(getattr(evidence, "status", ""))


def is_external_certificate(evidence) -> bool:
    """True iff `evidence` (a status string, a dict with 'status', or an object with .status) is an external
    certificate in ANY supported domain. The engine's own score never qualifies; mere sampling never qualifies."""
    return _status_of(evidence) in EXTERNAL_CERTIFICATES


@dataclass
class Certificate:
    """A domain-agnostic external certificate. `status` ∈ EXTERNAL_CERTIFICATES to count as certified. `domain`
    and `resolver` record WHO settled it (a simulator, a wet-lab protocol, a benchmark, a prover, …) so the
    frontier is auditable across fields. `counterexample` carries the refutation when the resolver refuted it."""
    status: str
    detail: str = ""
    domain: str = ""
    resolver: str = ""
    counterexample: Optional[Dict] = None
    metadata: Dict = field(default_factory=dict)

    @property
    def certified(self) -> bool:
        return self.status in EXTERNAL_CERTIFICATES

    @property
    def kind(self) -> str:
        return kind_of(self.status)

    def markdown(self) -> str:
        head = f"### Certificate — {self.status} ({self.kind})"
        body = [f"- {self.detail}"] if self.detail else []
        if self.domain or self.resolver:
            body.append(f"- domain: {self.domain or '—'} · resolver: {self.resolver or '—'}")
        if self.counterexample is not None:
            body.append(f"- counterexample: {self.counterexample}")
        if self.certified and self.kind == "EMPIRICAL":
            body.append("- EMPIRICAL: a reproducible external measurement — NOT a proof.")
        return "\n".join([head] + body)
