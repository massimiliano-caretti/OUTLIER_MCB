"""frontier_search — the «toward-the-objective» loop that never regresses.

Closes the cycle over the hard-problem pieces:
  1. take lateral sub-lemmas (breaking the pack's assumptions, F1) — and DISCARD routes a barrier proves dead (F2);
  2. settle each survivor with an EXTERNAL resolver (F4) — a counterexample kills the false ones;
  3. record certified, strictly-improving winners on the monotone frontier (F3 — so it can only move forward);
  4. turn every FAILED lemma into the next assumption to break (a failure is information, never discarded).

Returns a report: the current certified frontier, the residual distance to the objective, and the next levers.
The parent problem stays **CONJECTURE** forever — the loop advances PARTIAL certified results, it never claims
the open conjecture is proved. That honesty is the engine of progress here, not a brake.

Deterministic: no randomness; the frontier is settled only by external certificates, so re-running with the
sub-lemmas in any order reaches the SAME frontier and never a worse one.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from .math_discovery import Conjecture, settle_lemma, LemmaCertificate
from .frontier_ledger import FrontierLedger
from .barriers import barrier_membership, DEAD_BY_BARRIER


@dataclass
class LemmaCandidate:
    """A lateral sub-lemma to attack (MATH instance): a decidable statement plus the frontier advance it would
    certify. Settled by `settle_lemma` (z3 / Lean / exhaustive numeric)."""
    name: str
    lemma: Conjecture
    metric: str
    value: float
    direction: str                       # 'decrease' | 'increase'
    predicate: Optional[Callable] = None
    breaks_assumption: str = ""          # which pack assumption it breaks (for the failure→next-lever loop)


@dataclass
class ResultCandidate:
    """A DOMAIN-AGNOSTIC partial result to attack in ANY field (physics / biology / chemistry / engineering / ML
    / software / medicine): a metric advance plus the candidate's OWN external resolver `settle()`. `settle()`
    returns a certificate-like object with `.status` and `.certified` (see certificates.Certificate) — e.g. a
    reproducible simulation (SIMULATION_VERIFIED), a wet-lab reproduction (EXPERIMENT_REPRODUCED), a held-out
    eval (DATASET_EVAL_PASSED), a benchmark (BENCHMARK_MEASURED), or a green repo test (REPO_TEST_GREEN). The
    loop is blind to the domain; only the resolver knows it."""
    name: str
    metric: str
    value: float
    direction: str                       # 'decrease' | 'increase'
    settle: Callable[[], object]         # () -> a certificate (.status / .certified / .counterexample)
    breaks_assumption: str = ""


def _settle_candidate(candidate, resolver, backend):
    """Settle one candidate by its EXTERNAL resolver, domain-blind. Priority: an explicit global `resolver`
    (candidate -> certificate), then the candidate's own `settle()` (ResultCandidate), then the math default
    `settle_lemma` (LemmaCandidate). Returns a certificate-like with `.status`, `.certified`, `.counterexample`."""
    if resolver is not None:
        return resolver(candidate)
    settle = getattr(candidate, "settle", None)
    if callable(settle):
        return settle()
    return settle_lemma(candidate.lemma, predicate=getattr(candidate, "predicate", None), backend=backend)


@dataclass
class FrontierSearchReport:
    problem: str
    ledger: FrontierLedger
    advanced: List[dict] = field(default_factory=list)        # certified, accepted advances
    killed: List[dict] = field(default_factory=list)          # refuted / undecided → became next levers
    dead_routes: List[dict] = field(default_factory=list)     # barrier-killed routes (never attempted)
    next_levers: List[str] = field(default_factory=list)      # the next assumptions to break (failures reused)
    objective_metric: str = ""
    objective_value: Optional[float] = None
    parent_status: str = "CONJECTURE"                         # INVARIANT: the parent is NEVER 'PROVED'

    def best(self) -> Optional[float]:
        return self.ledger.best(self.problem, self.objective_metric) if self.objective_metric else None

    def residual(self) -> Optional[float]:
        """Distance from the current certified frontier to the objective (None if no objective/frontier yet)."""
        if self.objective_value is None or self.best() is None:
            return None
        return round(abs(self.best() - self.objective_value), 6)

    def markdown(self) -> str:
        L = [f"## Frontier search — «{self.problem}»  (parent stays **{self.parent_status}** — never proved)"]
        if self.objective_metric and self.best() is not None:
            L.append(f"- frontier: {self.objective_metric} = {self.best()}"
                     + (f" · objective {self.objective_value} · residual {self.residual()}"
                        if self.objective_value is not None else ""))
        L.append(f"- advanced (certified): {len(self.advanced)} · killed/undecided: {len(self.killed)} · "
                 f"dead routes skipped: {len(self.dead_routes)}")
        for a in self.advanced:
            L.append(f"  ✓ {a['name']}: {a['metric']}={a['value']} (certified {a['status']})")
        if self.next_levers:
            L.append("- next levers (failures reused, never discarded):")
            L.extend(f"    → {lev}" for lev in self.next_levers[:8])
        return "\n".join(L)


def propose_sublemmas(pack, k: int = 4) -> List[LemmaCandidate]:
    """Generative side (statement-only stubs): turn the pack's breakable assumptions into sub-lemma STUBS. They
    carry no predicate, so they settle to UNKNOWN_TIMEOUT and become next levers — demonstrating that a lemma we
    cannot yet settle is kept as the next assumption to break, never thrown away. Plug real predicates to settle."""
    from .kernel import graph_of, _ranked_breakable
    ranked = _ranked_breakable(pack, graph_of(pack))[:k]
    out = []
    for name in ranked:
        a = pack.by_name().get(name)
        if a is None:
            continue
        out.append(LemmaCandidate(
            name=f"sublemma[break {name}]",
            lemma=Conjecture(statement=f"a decidable consequence of assuming '{name}' is false: {a.if_false}"),
            metric="open", value=0.0, direction="increase", predicate=None, breaks_assumption=name))
    return out


def frontier_search(problem: str, candidates: List, objective_metric: str = "",
                    objective_value: Optional[float] = None, ledger: Optional[FrontierLedger] = None,
                    pack=None, backend=None, log=None, resolver=None) -> FrontierSearchReport:
    """Run one pass of the toward-objective loop over `candidates`. Reuses the FrontierLedger so the frontier is
    monotone BY CONSTRUCTION across calls. Never asserts the parent conjecture — only advances partial results.

    Pass `log` (a self_diagnosis.DiagnosticLog) to drop diagnostic POINTS as the loop proceeds — so a run that
    does not reach the objective leaves a post-mortem (dead routes, killed lemmas, the residual bottleneck) the
    engine can later self-diagnose and try to repair. Logging is opt-in: no `log` ⇒ identical behaviour."""
    ledger = ledger or FrontierLedger()
    report = FrontierSearchReport(problem=problem, ledger=ledger,
                                  objective_metric=objective_metric or (candidates[0].metric if candidates else ""),
                                  objective_value=objective_value)
    for c in candidates:
        # 2-: discard a route a barrier proves dead (F2) — never even attempt it
        if pack is not None:
            bv = barrier_membership(f"{c.name} {c.lemma.statement}", pack)
            if bv is not None and bv.status == DEAD_BY_BARRIER:
                report.dead_routes.append({"name": c.name, "barrier": bv.barrier})
                report.next_levers.append(f"{c.name}: DEAD_BY_BARRIER «{bv.barrier}» → take an exit: {bv.exits[0]}")
                if log is not None:
                    log.blocked("barrier", f"{c.name}: DEAD_BY_BARRIER «{bv.barrier}»", detail=bv.exits[0])
                continue
        # 3: settle externally (F4) — domain-agnostic: math lemma, simulation, experiment, eval, benchmark, test
        cert = _settle_candidate(c, resolver, backend)
        if cert.certified:
            r = ledger.claim(problem, c.metric, c.value, c.direction, cert, note=c.name)
            if r.accepted:
                report.advanced.append({"name": c.name, "metric": c.metric, "value": c.value, "status": cert.status})
                if log is not None:
                    log.ok("settlement", f"{c.name} advanced {c.metric}={c.value}", metric=c.metric, value=c.value)
            else:
                # certified but not an improvement → still information for the next move
                report.next_levers.append(f"{c.name}: certified ({cert.status}) but {r.outcome} — pick a stronger lemma")
                if log is not None:
                    log.weak("settlement", f"{c.name}: certified but {r.outcome}", metric=c.metric, value=c.value)
        else:
            # 4: a failed lemma becomes the next assumption to break (information, never discarded)
            report.killed.append({"name": c.name, "status": cert.status, "counterexample": cert.counterexample})
            lever = f"{c.name} failed ({cert.status})"
            if cert.counterexample is not None:
                lever += f"; counterexample {cert.counterexample} → break a further assumption"
            elif c.breaks_assumption:
                lever += f" → break beyond '{c.breaks_assumption}'"
            report.next_levers.append(lever)
            if log is not None:
                log.failed("settlement", f"{c.name} not settled ({cert.status})", detail=str(cert.counterexample or ""))
    # post-mortem: did the loop reach the objective? a non-zero residual is the bottleneck worth recording.
    if log is not None:
        residual = report.residual()
        reached = (residual is not None and residual == 0)
        if not report.advanced:
            log.bottleneck("frontier", "no certified advance this pass", metric=report.objective_metric)
        if residual is not None and not reached:
            log.bottleneck("frontier", f"objective not reached (residual {residual})",
                           metric=report.objective_metric, value=report.best())
        log.mark_completed(bool(reached))
    return report
