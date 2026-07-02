"""self_repair — evolutionary self-repair under two hard gates: NEVER REGRESS, NEVER touch a solid invariant.

self_diagnosis tells the engine WHERE it was weak. This module lets it try to FIX it, alive, without ever
going backwards. A repair is accepted ONLY if, re-measured after it is applied:
  (1) EVERY protected invariant still holds — the solid things that make the library work today are untouchable;
  (2) the health metric did NOT regress (re-measured, not assumed — «valutare se davvero non è regredita»).
If either fails, the change is ROLLED BACK and the attempt is recorded as a diagnostic point (a failure is
information). An accepted, strictly-improving repair is logged on the monotone FrontierLedger, so the engine's
health can only move forward across self-repairs.

The protected invariants are the explicit «cose solide che non si possono toccare»: the four entrypoints exist,
the engine never claims PROVED on an open conjecture, the frontier rejects regressions, a deterministic distance
exists, the parity barrier still fires. They are checkable predicates, re-run as the external resolver.

Deterministic, pure-Python. The repair PROPOSAL (the actual fix) is supplied by the caller/LLM — the spark is
external; the rigor (the two gates) is the machine's.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from .self_diagnosis import DiagnosticLog, DiagnosticMemory, DiagnosisReport, self_diagnose


# ── protected invariants: the solid, untouchable behaviors (each is a cheap, deterministic predicate) ──
@dataclass
class ProtectedInvariant:
    name: str
    check: Callable[[], Tuple[bool, str]]    # () -> (ok, detail)
    why: str


def _inv_four_entrypoints() -> Tuple[bool, str]:
    import OUTLIER_MCB as gsl
    missing = [n for n in ("creative", "judge", "invent", "green_star") if not callable(getattr(gsl, n, None))]
    return (not missing, "all four entrypoints present" if not missing else f"missing: {missing}")


def _inv_never_proves_open_conjecture() -> Tuple[bool, str]:
    from .math_discovery import LEMMA_STATES, LEMMA_CERTIFIED
    from .certificates import FORMAL_CERTIFICATES
    # (1) no BARE 'PROVED' status — that would name proving a PARENT conjecture. Every proof status must be a
    #     SPECIFIC external prover's LEMMA certificate (LEAN_CHECKED, ISABELLE_CHECKED, X_PROVED, NUMERIC_VERIFIED).
    bare = [s for s in LEMMA_STATES if s == "PROVED" or s.endswith("_CONJECTURE")]
    # (2) every certified LEMMA status is a REGISTERED external FORMAL certificate (certificates.py) — never a
    #     self-judged label. Adding a certified status thus requires adding it to the curated external registry.
    all_external = all(s in FORMAL_CERTIFICATES for s in LEMMA_CERTIFIED)
    ok = not bare and all_external and len(LEMMA_CERTIFIED) >= 3
    return (ok, "lemma vocabulary certifies only via external provers — never a bare parent PROVED"
            if ok else f"open-conjecture honesty broken: {LEMMA_CERTIFIED} (bare={bare}, all_external={all_external})")


def _inv_frontier_rejects_regression() -> Tuple[bool, str]:
    from .frontier_ledger import FrontierLedger, ACCEPTED, REGRESSION_REJECTED, UNCERTIFIED_REJECTED
    led = FrontierLedger()
    cert = {"status": "NUMERIC_VERIFIED"}
    a = led.claim("p", "m", 10, "increase", cert).outcome == ACCEPTED
    b = led.claim("p", "m", 5, "increase", cert).outcome == REGRESSION_REJECTED          # worse → rejected
    c = led.claim("p", "m", 99, "increase", {"status": "EMPIRICALLY_SUPPORTED"}).outcome == UNCERTIFIED_REJECTED
    ok = a and b and c
    return (ok, "frontier accepts certified improvements, rejects regressions + uncertified"
            if ok else "frontier monotonicity/certification broken")


def _inv_deterministic_distance() -> Tuple[bool, str]:
    from .embeddings import semantic_distance, LexicalEmbedder
    d1 = semantic_distance("alpha beta gamma", "alpha beta delta")
    d2 = semantic_distance("alpha beta gamma", "alpha beta delta")
    ok = (d1 == d2) and LexicalEmbedder().distance("same words", "same words") == 0.0
    return (ok, "a deterministic distance exists (lexical fallback)" if ok else "distance non-deterministic")


def _inv_parity_barrier_lives() -> Tuple[bool, str]:
    import OUTLIER_MCB as gsl
    from .barriers import barrier_membership, DEAD_BY_BARRIER
    v = barrier_membership("a classical Selberg sieve for twin primes at gap 2", gsl.get_pack("number_theory"))
    ok = v is not None and v.status == DEAD_BY_BARRIER
    return (ok, "the parity barrier still kills the dead sieve route" if ok else "parity barrier no longer fires")


def _inv_agnostic_certificates() -> Tuple[bool, str]:
    """The engine is AGNOSTIC: a non-math external certificate (a reproducible simulation, a wet-lab
    reproduction) must advance a frontier exactly like a math proof, while mere sampling stays rejected."""
    from .frontier_ledger import FrontierLedger, ACCEPTED, UNCERTIFIED_REJECTED
    sim = FrontierLedger().claim("physics", "eff", 0.4, "increase", {"status": "SIMULATION_VERIFIED"}).outcome == ACCEPTED
    exp = FrontierLedger().claim("biology", "x", 1, "increase", {"status": "EXPERIMENT_REPRODUCED"}).outcome == ACCEPTED
    sampling = FrontierLedger().claim("ml", "acc", 0.9, "increase", {"status": "EMPIRICALLY_SUPPORTED"}).outcome == UNCERTIFIED_REJECTED
    ok = sim and exp and sampling
    return (ok, "non-math external certificates advance the frontier; sampling is rejected (agnostic + honest)"
            if ok else "agnostic-certificate handling broken")


def _inv_fitness_requires_external_verification() -> Tuple[bool, str]:
    """The self-improvement fitness must NEVER reward self-judged novelty: a proposal that breaks a box but is
    NOT externally certified contributes 0; the same proposal with an external certificate contributes. This
    locks the anti-circularity the engine designed for itself (the anti-circularity break: an external resolver must certify, not a self score)."""
    from .verified_novelty import Proposal, verified_novelty_fitness
    unverified = verified_novelty_fitness([Proposal("p", breaks_box=True, certificate=None)])
    verified = verified_novelty_fitness([Proposal("p", breaks_box=True, certificate={"status": "NUMERIC_VERIFIED"})])
    ok = (unverified == 0.0) and (verified > 0.0)
    return (ok, "verified-novelty fitness rewards ONLY externally-certified novelty (never self-judgment)"
            if ok else "the self-improvement fitness can be gamed by self-judged novelty — circularity reintroduced")


def _inv_pareto_no_regression() -> Tuple[bool, str]:
    """Multi-metric self-improvement must NEVER trade one skill for another: the Pareto gate rejects any change
    that regresses ANY performance dimension, and accepts only a strict all-round improvement."""
    from .verified_novelty import pareto_improves
    base = {"a": 0.5, "b": 0.5}
    regress = pareto_improves(base, {"a": 0.9, "b": 0.4})    # one up, one DOWN → must be rejected
    improve = pareto_improves(base, {"a": 0.6, "b": 0.5})    # one up, none down → must be accepted
    neutral = pareto_improves(base, {"a": 0.5, "b": 0.5})    # nothing improves → must be rejected
    ok = (not regress) and improve and (not neutral)
    return (ok, "the Pareto gate rejects any per-dimension regression (improve all-round, never trade a skill)"
            if ok else "the multi-metric gate could accept a regression — a skill could be traded away")


def _inv_invented_physics_scored_externally() -> Tuple[bool, str]:
    """Point 1 honesty gate: an INVENTED universe's worth is settled by an EXTERNAL emergence metric that rewards
    STRUCTURE, never mere change or disorder. A trivial (frozen) universe and an i.i.d.-noise universe must BOTH
    score ~0 while a structured one scores materially higher, and every invented physics is deterministic and
    bounded. Blocks self-inflation: the engine cannot score a static or chaotic 'universe' as emergent."""
    from .physics_inventor import coherence_controls_pass
    ok = coherence_controls_pass()
    return (ok, "invented physics is scored only by external emergence (structure beats trivial+noise controls)"
            if ok else "the emergence metric could be gamed by a static or chaotic universe — Point-1 honesty broken")


def _inv_symbol_is_grounded() -> Tuple[bool, str]:
    """Point 2 honesty gate: an endogenous concept MEANS something only if it maps to a real, non-trivial,
    recurring pattern actually observed in a log. A ghost symbol must fail verification and give no compression
    gain, and grounding a non-recurring pattern must be refused — so the conceptual_compression dimension can
    never be inflated by empty self-coined symbols."""
    from .semantic_grounding import grounding_controls_pass
    ok = grounding_controls_pass()
    return (ok, "endogenous symbols compress only when grounded in real recurring structure (no empty concepts)"
            if ok else "conceptual compression could be inflated by an ungrounded symbol — Point-2 honesty broken")


def _inv_language_is_sound() -> Tuple[bool, str]:
    """Point 3 honesty gate: an invented formal language must actually COMPUTE — its interpreter must run test
    programs and match precomputed expected outputs — AND give a real expressive gain (> 1) while a mere rename
    of the baseline scores exactly 1. Blocks inventing a language that looks expressive but miscomputes or that
    inflates expressive_power without a genuine gain."""
    from .language_inventor import soundness_controls_pass
    ok = soundness_controls_pass()
    return (ok, "invented languages are sound (the interpreter computes) and expressive_power gates a real gain"
            if ok else "an invented language could miscompute or fake a gain — Point-3 honesty broken")


def _inv_aesthetics_are_objective() -> Tuple[bool, str]:
    """Point 4 honesty gate: aesthetic scores must be OBJECTIVE functions of the artifact's structure — not a
    taste the engine can assert. Deterministic; a more verbose formula is never scored more simple; a symmetric
    form scores higher symmetry than an asymmetric one; a canonical beautiful formula beats a clumsy equivalent."""
    from .aesthetics import aesthetics_objectivity_pass
    ok = aesthetics_objectivity_pass()
    return (ok, "aesthetic metrics are objective AST functions (symmetry/simplicity/surprise), never self-declared"
            if ok else "aesthetics could be asserted at will rather than measured — Point-4 honesty broken")


def _inv_elegance_never_buys_a_regression() -> Tuple[bool, str]:
    """Point 4, the crucial one: adding elegance as a Pareto dimension must NOT loosen the gate. A change that
    improves elegance but REGRESSES a hard metric is still rejected; only a no-regression change is accepted.
    This locks the correction to the plan — beauty never buys a performance regression (never-regress holds)."""
    from .verified_novelty import pareto_improves
    base = {"accuracy": 0.8, "elegance": 0.3}
    beauty_at_a_cost = pareto_improves(base, {"accuracy": 0.7, "elegance": 0.9})   # prettier but WORSE → reject
    pure_beauty_gain = pareto_improves(base, {"accuracy": 0.8, "elegance": 0.5})   # same acc, more elegant → accept
    ok = (not beauty_at_a_cost) and pure_beauty_gain
    return (ok, "elegance is a Pareto dimension under the strict gate — beauty never buys a regression"
            if ok else "aesthetics could be traded for a performance regression — never-regress broken")


INVARIANT_REGISTRY: Dict[str, ProtectedInvariant] = {
    "four_entrypoints": ProtectedInvariant(
        "four_entrypoints", _inv_four_entrypoints, "creative/judge/invent/green_star are the public contract"),
    "never_proves_open_conjecture": ProtectedInvariant(
        "never_proves_open_conjecture", _inv_never_proves_open_conjecture,
        "the non-negotiable honesty: never PROVED on an open conjecture"),
    "frontier_rejects_regression": ProtectedInvariant(
        "frontier_rejects_regression", _inv_frontier_rejects_regression, "never regress is enforced, not assumed"),
    "deterministic_distance": ProtectedInvariant(
        "deterministic_distance", _inv_deterministic_distance, "default behavior is deterministic, zero-dep"),
    "parity_barrier_lives": ProtectedInvariant(
        "parity_barrier_lives", _inv_parity_barrier_lives, "known no-go routes stay refused"),
    "agnostic_certificates": ProtectedInvariant(
        "agnostic_certificates", _inv_agnostic_certificates,
        "the engine works for ALL domains: any field's external certificate can advance the frontier"),
    "fitness_requires_external_verification": ProtectedInvariant(
        "fitness_requires_external_verification", _inv_fitness_requires_external_verification,
        "self-improvement is driven by VERIFIED novelty only — never by a self-judged score (anti-circularity)"),
    "pareto_no_regression": ProtectedInvariant(
        "pareto_no_regression", _inv_pareto_no_regression,
        "multi-metric self-improvement raises every dimension and trades none away (Pareto gate)"),
    "invented_physics_scored_externally": ProtectedInvariant(
        "invented_physics_scored_externally", _inv_invented_physics_scored_externally,
        "inventing new universes is scored by an external structure metric, never self-judged (Point 1)"),
    "symbol_is_grounded": ProtectedInvariant(
        "symbol_is_grounded", _inv_symbol_is_grounded,
        "an endogenous concept must abstract a real recurring pattern — no empty symbols inflate compression (Point 2)"),
    "language_is_sound": ProtectedInvariant(
        "language_is_sound", _inv_language_is_sound,
        "an invented formal language must actually compute (sound interpreter) and gain real expressiveness (Point 3)"),
    "aesthetics_are_objective": ProtectedInvariant(
        "aesthetics_are_objective", _inv_aesthetics_are_objective,
        "beauty is measured on formal AST structure (symmetry/simplicity/surprise), never self-declared (Point 4)"),
    "elegance_never_buys_a_regression": ProtectedInvariant(
        "elegance_never_buys_a_regression", _inv_elegance_never_buys_a_regression,
        "elegance is a Pareto dimension under the strict no-regression gate — beauty never buys a regression (Point 4)"),
}


@dataclass
class InvariantReport:
    passed: List[str] = field(default_factory=list)
    failed: List[Tuple[str, str]] = field(default_factory=list)   # (name, detail)

    @property
    def ok(self) -> bool:
        return not self.failed

    @property
    def passed_names(self):
        return set(self.passed)

    @property
    def failed_names(self):
        return {n for n, _ in self.failed}

    @property
    def n_passed(self) -> int:
        return len(self.passed)

    @property
    def n_total(self) -> int:
        return len(self.passed) + len(self.failed)

    def markdown(self) -> str:
        L = [f"## Protected invariants — {self.n_passed}/{self.n_total} hold" + ("" if self.ok else " ⚠ BROKEN")]
        L += [f"  ✓ {n}" for n in self.passed]
        L += [f"  ✗ {n} — {d}" for n, d in self.failed]
        return "\n".join(L)


def verify_invariants(invariants: Optional[List[ProtectedInvariant]] = None) -> InvariantReport:
    """Re-run every protected invariant (the external resolver for a self-repair). Deterministic, order-stable."""
    invs = invariants if invariants is not None else [INVARIANT_REGISTRY[k] for k in sorted(INVARIANT_REGISTRY)]
    report = InvariantReport()
    for inv in invs:
        try:
            ok, detail = inv.check()
        except Exception as exc:                       # an invariant that crashes is a FAILED invariant, not a crash
            ok, detail = False, f"check raised: {exc}"
        (report.passed.append(inv.name) if ok else report.failed.append((inv.name, detail)))
    return report


def library_health(invariants: Optional[List[ProtectedInvariant]] = None) -> float:
    """Default health metric: the fraction of protected invariants that hold, in [0,1]. A simple, deterministic,
    externally-checkable signal a repair must not regress."""
    # ERGONOMICS (#15): a caller may reach for library_health('.') expecting a repo argument. There is none —
    # the metric is over protected invariants — so coerce any non-list (a path string, etc.) to the default
    # set instead of crashing with an opaque AttributeError deep inside verify_invariants.
    if invariants is not None and not isinstance(invariants, list):
        invariants = None
    r = verify_invariants(invariants)
    return round(r.n_passed / r.n_total, 4) if r.n_total else 1.0


# ── the evolutionary repair loop ──
@dataclass
class RepairProposal:
    name: str
    apply: Callable[[], None]
    rollback: Callable[[], None]
    rationale: str = ""


@dataclass
class RepairResult:
    proposal: str
    accepted: bool
    reason: str
    before: float
    after: float
    regressed: bool = False
    broken_invariants: List[str] = field(default_factory=list)
    rolled_back: bool = False
    advanced_frontier: bool = False

    def markdown(self) -> str:
        verb = "ACCEPTED" if self.accepted else "REJECTED (rolled back)"
        return (f"## Self-repair «{self.proposal}» — {verb}\n"
                f"- health {self.before} → {self.after} · {self.reason}"
                + (f"\n- broken invariants: {self.broken_invariants}" if self.broken_invariants else "")
                + (f"\n- frontier advanced (monotone, never regresses)" if self.advanced_frontier else ""))


def evolutionary_self_repair(proposal: RepairProposal, measure: Optional[Callable[[], float]] = None,
                             direction: str = "increase", invariants: Optional[List[ProtectedInvariant]] = None,
                             ledger=None, memory: Optional[DiagnosticMemory] = None,
                             problem: str = "library", metric: str = "health") -> RepairResult:
    """Try `proposal`, keep it ONLY if every protected invariant still holds AND the metric did not regress
    (re-measured). Otherwise roll back and record the failed attempt. An accepted strict improvement is logged
    on the monotone frontier. The two gates are non-negotiable: never regress, never break a solid invariant."""
    measure = measure or (lambda: library_health(invariants))

    base_inv = verify_invariants(invariants)
    before = measure()

    proposal.apply()
    after_inv = verify_invariants(invariants)
    after = measure()

    newly_broken = sorted(base_inv.passed_names & after_inv.failed_names)
    regressed = (after < before) if direction == "increase" else (after > before)

    def _log_failure(reason: str) -> None:
        if memory is None:
            return
        log = DiagnosticLog(task=f"self_repair:{proposal.name}")
        if newly_broken:
            log.blocked("self_repair", f"would break protected invariant(s): {newly_broken}",
                        detail=proposal.rationale)
        if regressed:
            log.failed("self_repair", "regressed the health metric", detail=reason, metric=metric, value=after)
        if not newly_broken and not regressed:
            log.weak("self_repair", reason, metric=metric, value=after)
        log.mark_completed(False)
        memory.record(log)

    # GATE 1 — a solid invariant must never break;  GATE 2 — never regress
    if not after_inv.ok or regressed:
        proposal.rollback()
        reason = ("a protected invariant broke" if not after_inv.ok else "") + \
                 (" and " if (not after_inv.ok and regressed) else "") + \
                 ("the metric regressed" if regressed else "")
        _log_failure(reason or "rejected")
        # confirm the rollback truly restored the invariants (never leave the library worse than we found it)
        restored = verify_invariants(invariants)
        return RepairResult(proposal=proposal.name, accepted=False,
                            reason=reason + ("; rollback restored invariants" if restored.ok else
                                             "; WARNING rollback did not fully restore"),
                            before=before, after=after, regressed=regressed,
                            broken_invariants=sorted(after_inv.failed_names), rolled_back=True)

    # ACCEPT — invariants all hold and no regression. Record a strict improvement on the monotone frontier.
    improved = (after > before) if direction == "increase" else (after < before)
    advanced = False
    if improved:
        from .frontier_ledger import FrontierLedger
        ledger = ledger if ledger is not None else FrontierLedger()
        cert = {"status": "INVARIANTS_VERIFIED",
                "detail": f"{after_inv.n_passed}/{after_inv.n_total} invariants hold after repair"}
        advanced = ledger.claim(problem, metric, after, direction, cert, note=proposal.name).accepted
    if memory is not None:
        log = DiagnosticLog(task=f"self_repair:{proposal.name}")
        log.ok("self_repair", f"accepted: health {before} → {after}", metric=metric, value=after)
        log.mark_completed(True)
        memory.record(log)
    return RepairResult(proposal=proposal.name, accepted=True,
                        reason=("strict improvement, invariants intact" if improved else
                                "no regression and invariants intact (neutral change kept)"),
                        before=before, after=after, advanced_frontier=advanced)


# ── the repair INTERVIEW: the LLM queries the library for WHAT/HOW to fix + the constraints, BEFORE proposing ──
@dataclass
class RepairBrief:
    """What the library tells an LLM when it is asked 'how should I repair you?'. The LLM reads this, decides if
    the diagnosis is right, and proposes a RepairProposal — but the two gates (never regress, never break a
    protected invariant) are enforced regardless by evolutionary_self_repair. The spark is the LLM's; the
    constraints are the machine's."""
    bottleneck: str
    weak_spots: List[str]
    levers: List[str]                 # WHAT to try (candidate fixes, from the diagnosis)
    must_hold: List[str]              # the CONSTRAINTS: protected invariants the repair may never break
    current_health: float
    acceptance_rule: str
    healthy: bool = False

    def to_dict(self) -> Dict:
        return {"bottleneck": self.bottleneck, "weak_spots": self.weak_spots, "levers": self.levers,
                "must_hold": self.must_hold, "current_health": self.current_health,
                "acceptance_rule": self.acceptance_rule, "healthy": self.healthy}

    def markdown(self) -> str:
        if self.healthy:
            return "## Repair brief — nothing to repair (no weak spots; all invariants hold)"
        L = [f"## Repair brief — interview the library before patching",
             f"- **bottleneck (fix here first):** {self.bottleneck or '—'}",
             "- **what to try (levers):**"] + [f"    → {lv}" for lv in self.levers[:6]]
        L += ["- **constraints you MUST respect (non-negotiable):**"] + [f"    ⛔ {m}" for m in self.must_hold]
        L += [f"- **current health:** {self.current_health}",
              f"- **acceptance rule:** {self.acceptance_rule}"]
        return "\n".join(L)


def repair_brief(source, invariants: Optional[List[ProtectedInvariant]] = None) -> RepairBrief:
    """The INTERVIEW step: given a diagnostic memory / log / DiagnosisReport, return the structured feedback an
    LLM needs to decide WHAT and HOW to repair — the bottleneck, the candidate levers, and the hard CONSTRAINTS
    (the protected invariants it may never break, plus never-regress). The LLM then proposes a RepairProposal and
    may judge the diagnosis right or wrong; the gates in evolutionary_self_repair enforce the constraints anyway."""
    diag = source if isinstance(source, DiagnosisReport) else self_diagnose(source)
    invs = invariants if invariants is not None else [INVARIANT_REGISTRY[k] for k in sorted(INVARIANT_REGISTRY)]
    must_hold = [f"{inv.name} — {inv.why}" for inv in invs]
    levers = []
    if diag.next_lever:
        levers.append(diag.next_lever)
    if diag.dominant_failure:
        levers.append(f"address the dominant failure: {diag.dominant_failure}")
    for w in diag.weak_spots[:4]:
        levers.append(f"in phase '{w.phase}' (severity {w.severity}): {', '.join(w.examples[:2])}")
    return RepairBrief(
        bottleneck=diag.bottleneck_phase,
        weak_spots=[w.phase for w in diag.weak_spots],
        levers=levers,
        must_hold=must_hold,
        current_health=library_health(invariants),
        acceptance_rule=("a proposed fix is KEPT only if EVERY constraint above still holds AND the health metric "
                         "does not regress (re-measured); otherwise it is rolled back and the failure is logged."),
        healthy=diag.healthy)
