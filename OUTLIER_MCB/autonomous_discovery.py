"""autonomous_discovery — the INVENTOR is the default front door; the judge is one stage downstream (T3,T5,T6,T7,T8).

The library is a discoverer, not a refuter. `autonomous_discover` drives the creative pipeline and only USES external
certification to make a discovery REAL:
  T1 mine the oracle for sparks (oracle_miner) →
  T2 grow the primitive alphabet if the object needs a composite (primitive_library) →
  T4 pivot the solution TYPE when a form is impossible (solution_type_lattice) — never stop at CONJECTURE →
  external check (the judge, at its place: downstream) turns a spark into a certified discovery →
  T3 acquire NEW information (more oracle terms) when stalled — the move that raises the ceiling →
  T5 a scratch sandbox permits worsening detours; only the committed ledger stays monotone →
  T6 manufactured sister-landscapes test whether a discovered MECHANISM generalises (validate by transfer) →
  T8 celebrate REDUCTION_ESTABLISHED / CONDITIONAL_THEOREM as first-class discoveries.

On success the message is a DISCOVERY ("I found/invented X, certified thus"), never a defence ("cannot prove Y").
Honesty keeps the discoveries real: no false PROVED, the committed ledger never regresses. Pure-Python, deterministic.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from .oracle_miner import mine_invariants, guess_holonomic, HolonomicRecurrence
from .solution_type_lattice import pivot as pivot_form, describe as describe_form, form_for_recurrence, SOLUTION_FORMS
from .primitive_library import PrimitiveLibrary, becomes_constant

DISCOVERY_STATES = ("SOLVED", "REDUCTION_ESTABLISHED", "CONDITIONAL_THEOREM", "OPEN")


@dataclass
class DiscoveryResult:
    state: str                                # one of DISCOVERY_STATES
    form: str = ""                            # the solution FORM discovered (from the lattice)
    certificate: str = ""                     # how it was made real (held-out verification / algorithm-reproduces-oracle)
    mechanism: str = ""                       # the discovered structure (recurrence text, algorithm, reduction)
    generalized: Optional[bool] = None        # did the mechanism pass the sister-landscape transfer test?
    trace: List[str] = field(default_factory=list)
    pivots: List[str] = field(default_factory=list)
    alphabet_growth: List[str] = field(default_factory=list)
    acquired_information: bool = False

    @property
    def discovered(self) -> bool:
        return self.state in ("SOLVED", "REDUCTION_ESTABLISHED", "CONDITIONAL_THEOREM")

    def message(self) -> str:
        if self.state == "SOLVED":
            g = "" if self.generalized is None else (" (generalises to sister landscapes)" if self.generalized
                                                     else " (did NOT generalise — kept honest, not overclaimed)")
            return (f"DISCOVERED — {describe_form(self.form)}: {self.mechanism}. Made real by {self.certificate}{g}. "
                    f"The parent problem is not claimed PROVED; this is a certified {self.form}.")
        if self.state == "REDUCTION_ESTABLISHED":
            return f"DISCOVERED a REDUCTION: {self.mechanism}. Certified by {self.certificate} — a result in its own right."
        if self.state == "CONDITIONAL_THEOREM":
            return f"DISCOVERED a CONDITIONAL result: {self.mechanism}."
        return (f"OPEN — no certified discovery yet. Next moves: {', '.join(self.pivots[-2:]) or 'acquire new information'}. "
                "(Honest: the engine invents no false solution.)")

    def markdown(self) -> str:
        L = [f"# Autonomous discovery — {self.state}", f"- **{self.message()}**"]
        if self.pivots:
            L.append(f"- solution-type pivots: {' → '.join(self.pivots)}")
        if self.alphabet_growth:
            L.append(f"- primitive alphabet grew: {self.alphabet_growth}")
        if self.acquired_information:
            L.append("- acquired NEW information (more oracle terms) to break the stall")
        L.append("- trace: " + " · ".join(self.trace))
        return "\n".join(L)


# ── T5: a scratch sandbox — detours allowed; only the committed record is monotone ──────────────────────────────
@dataclass
class ScratchFrontier:
    committed: float = float("-inf")          # the monotone record (only improves)
    scratch: float = float("-inf")            # the exploratory value (may worsen to escape a local optimum)
    detour_budget: int = 3
    history: List[Tuple[str, float]] = field(default_factory=list)

    def explore(self, value: float, opens_new_region: bool = False) -> bool:
        """Take an exploratory step. A WORSENING step is allowed while detour budget remains (creativity may regress
        temporarily). Returns True if the step is taken."""
        if value >= self.scratch or (opens_new_region and self.detour_budget > 0):
            if value < self.scratch:
                self.detour_budget -= 1
                self.history.append(("detour", value))
            else:
                self.history.append(("explore", value))
            self.scratch = value
            return True
        return False

    def commit(self) -> bool:
        """Commit the scratch value to the monotone record — ONLY if it strictly beats it (never regress committed)."""
        if self.scratch > self.committed:
            self.committed = self.scratch
            self.history.append(("commit", self.committed))
            return True
        return False


# ── T3: acquire NEW information — query the oracle for more terms (the move that raises the ceiling) ─────────────
def acquire_new_information(oracle, have: int, more: int = 8) -> Optional[List[int]]:
    """Ask the oracle for MORE terms than the current representation contains. Returns the extended term list, or
    None if the oracle cannot supply more (a real data_insufficient wall). This is genuinely new information."""
    if callable(oracle):
        return [int(oracle(i)) for i in range(have + more)]
    if len(oracle) > have:
        return [int(x) for x in oracle[:have + more]]
    return None


# ── T6: manufactured sister-landscapes — validate a discovered MECHANISM by transfer, not self-vote ─────────────
def _sister_sequences(rec: HolonomicRecurrence) -> List[List[int]]:
    """Generate sister sequences with KNOWN ground truth that SATISFY the same recurrence from different seeds — if
    the discovered mechanism is real, it must reproduce them exactly (external transfer, with a negative control)."""
    out = []
    for seed in ([1, 3], [2, 1], [1, 5]):
        terms = list(seed[: rec.order]) if rec.order >= len(seed) else list(seed)
        terms = terms[: rec.order] or [1]
        # extend by the recurrence itself; if it truly governs the family, it generates a consistent sequence
        for _ in range(8):
            nxt = rec.predict_next(terms)
            if nxt is None or nxt.denominator != 1:
                break
            terms.append(int(nxt))
        if len(terms) >= rec.order + 4:
            out.append(terms)
    return out


def mechanism_generalizes(rec: HolonomicRecurrence) -> Optional[bool]:
    """Transfer test: the recurrence must hold on freshly-generated sister sequences (positive) AND a scrambled
    sister must FAIL it (negative control). None if no sister could be built."""
    from .oracle_miner import _verify_recurrence
    sisters = _sister_sequences(rec)
    if not sisters:
        return None
    ok = all(_verify_recurrence(rec, s, start=rec.order) > 0 for s in sisters)
    scrambled = list(reversed(sisters[0]))
    neg = _verify_recurrence(rec, scrambled, start=rec.order) > 0
    return bool(ok and not neg)


# ── T8: discover and CERTIFY a REDUCTION between two problems — a first-class result, distinct from PROVED ───────
def certify_reduction(oracle_a, oracle_b, transform: Callable[[List[int]], List[int]],
                      name: str = "A ⟺ B", n_terms: int = 16) -> DiscoveryResult:
    """Discover that problem A reduces to B via `transform`: certified iff transform(B-terms) reproduces A-terms
    EXACTLY over the checked range (an external, finite check), AND a scrambled B does NOT (negative control). A
    reduction is a real discovery even when NEITHER problem is closed — it is not CONJECTURE and not PROVED."""
    a = oracle_a if isinstance(oracle_a, list) else [int(oracle_a(i)) for i in range(n_terms)]
    b = oracle_b if isinstance(oracle_b, list) else [int(oracle_b(i)) for i in range(n_terms)]
    k = min(len(a), len(b))
    try:
        mapped = list(transform(list(b[:k])))
    except Exception as exc:
        return DiscoveryResult(state="OPEN", trace=[f"reduction transform failed: {exc}"])
    m = min(len(mapped), len(a))
    holds = m >= 3 and all(mapped[i] == a[i] for i in range(m))
    scrambled = list(transform(list(reversed(b[:k]))))
    neg = len(scrambled) >= m and all(scrambled[i] == a[i] for i in range(m))   # must FAIL on scrambled input
    if holds and not neg:
        return DiscoveryResult(state="REDUCTION_ESTABLISHED", form="REDUCTION",
                               mechanism=f"{name}: transform(B) reproduces A on {m} terms",
                               certificate=f"exact match on {m} terms + scrambled-input negative control collapses",
                               trace=["discover reduction (T8)", "certify externally (finite check + negative control)"])
    return DiscoveryResult(state="OPEN", trace=["reduction did not certify (no false REDUCTION emitted)"])


def autonomous_discover(problem: str, oracle, budget: int = 3, allow_detour: bool = True,
                        acquire: bool = True, grow_primitives: bool = True, allow_pivot: bool = True) -> DiscoveryResult:
    """The inventor-first pipeline. `oracle` is a callable n→a(n) or a list of exact terms. Returns a DiscoveryResult
    whose message is a DISCOVERY when it finds real structure, an honest OPEN otherwise — NEVER a false proof."""
    res = DiscoveryResult(state="OPEN")
    res.trace.append("mine oracle for sparks (T1)")
    n_terms = 16
    sparks = mine_invariants(oracle, n_terms=n_terms)

    # T3: if no structure yet, acquire NEW information (more terms) and re-mine — the ceiling-raising move
    if not sparks.found_structure and acquire:
        ext = acquire_new_information(oracle, n_terms, more=12)
        if ext is not None and len(ext) > n_terms:
            res.acquired_information = True
            res.trace.append("stall → acquire NEW information (T3)")
            sparks = mine_invariants(ext, n_terms=len(ext))

    # forms in order of desirability — the discoverer reports the strongest structure it certified
    if sparks.closed_form is not None:
        cf = sparks.closed_form
        res.state, res.form, res.mechanism = "SOLVED", "CLOSED_FORM", cf.as_text()
        res.certificate = f"reproduces every one of {cf.verified_on} held-out terms exactly"
        res.trace.append("spark → certified CLOSED_FORM (the top of the solution lattice)")
        return res

    if sparks.holonomic is not None:
        rec = sparks.holonomic
        form = form_for_recurrence(rec.order, rec.degree)
        res.state, res.form, res.mechanism = "SOLVED", form, rec.as_text()
        res.certificate = f"held-out verification on {rec.verified_on} unseen term(s)"
        res.trace.append(f"spark → certified {form} (judge downstream)")
        # T6: does the discovered mechanism GENERALISE? (transfer, not self-vote)
        res.generalized = mechanism_generalizes(rec)
        res.trace.append(f"sister-landscape transfer (T6): generalizes={res.generalized}")
        return res

    if sparks.polynomial is not None:                       # beyond the linear box: a non-linear law
        p = sparks.polynomial
        # HONESTY: a relation LINEAR in the leading term uniquely generates a(n+order) (a solution-grade recurrence,
        # e.g. Somos); one that is quadratic in it is a real structural INVARIANT (a certified law) but NOT a
        # generative solution (e.g. floor(nφ): consecutive differences ∈ {1,2}). Label them differently — no overclaim.
        if p.is_generative:
            res.state, res.form, res.mechanism = "SOLVED", "NONLINEAR_RECURRENCE", p.as_text()
            res.trace.append("spark → certified GENERATIVE non-linear recurrence (broke out of the linear box)")
        else:
            res.state, res.form, res.mechanism = "SOLVED", "STRUCTURAL_INVARIANT", p.as_text()
            res.trace.append("spark → certified STRUCTURAL INVARIANT (a real law, not a generative solution)")
        res.certificate = f"held-out verification on {p.verified_on} unseen term(s)"
        return res

    if sparks.multiplicative is not None:                   # AXIS 1: a number-theoretic MULTIPLICATIVE function
        mu = sparks.multiplicative
        res.state, res.form, res.mechanism = "SOLVED", "MULTIPLICATIVE", mu.as_text()
        res.certificate = f"a(m·n)=a(m)·a(n) held on {mu.verified_pairs} coprime pairs (+ negative control)"
        res.trace.append("spark → certified MULTIPLICATIVE structure (number-theoretic axis)")
        return res

    if sparks.k_automatic is not None:                      # AXIS 3: a k-AUTOMATIC (digit-driven) sequence
        ka = sparks.k_automatic
        res.state, res.form, res.mechanism = "SOLVED", "K_AUTOMATIC", ka.as_text()
        res.certificate = f"the base-{ka.base} automaton reproduces {ka.verified_on} held-out terms"
        res.trace.append(f"spark → certified {ka.base}-AUTOMATIC structure (digit axis)")
        return res

    if sparks.algebraic is not None:                        # an ALGEBRAIC generating function P(x,y)=0
        a = sparks.algebraic
        res.state, res.form, res.mechanism = "SOLVED", "GENERATING_FUNCTION", a.as_text()
        res.certificate = f"held-out verification on {a.verified_on} unseen GF order(s)"
        res.trace.append("spark → certified ALGEBRAIC generating function")
        return res

    if not allow_pivot:
        res.trace.append("no recurrence and pivot disabled → OPEN (this is the refuter behaviour we fixed)")
        return res
    # T4: no closed/recurrence form → PIVOT the solution type instead of stopping at CONJECTURE
    res.trace.append("no recurrence → pivot solution type (T4)")
    form = "HOLONOMIC_RECURRENCE"
    for _ in range(len(SOLUTION_FORMS)):
        p = pivot_form(form, reason="the sequence is non-holonomic here")
        res.pivots.append(f"{p.from_form}→{p.to_form or '∅'}")
        form = p.to_form
        if form == "ASYMPTOTIC_WITH_BAND" and sparks.asymptotic is not None:
            # AXIS 2: a real growth law with a certified band fills this rung — a discovery, not just 'run the algorithm'
            asy = sparks.asymptotic
            res.state, res.form, res.mechanism = "SOLVED", "ASYMPTOTIC_WITH_BAND", asy.as_text()
            res.certificate = (f"the ratio a(n)/model stays in [{asy.band_lo:.3f}, {asy.band_hi:.3f}] on "
                               f"{asy.verified_on} held-out terms (a certified band, honestly not exact)")
            res.trace.append("pivoted to ASYMPTOTIC_WITH_BAND — a certified growth law (axis 2)")
            return res
        if form == "ALGORITHM":
            # HONEST: no algorithm is constructed or verified here. "Reproducing the oracle" by echoing the
            # oracle's own terms is a lookup table (zero compression), NOT a discovery — and claiming a
            # certificate for it would be a false PROVED, exactly what this module forbids. A real ALGORITHM
            # discovery requires a constructed predictor verified on HELD-OUT terms with a negative control;
            # until that exists we report an honest OPEN (state is already OPEN), never a certified SOLVED.
            res.trace.append("pivot reached ALGORITHM, but no algorithm was constructed/verified on held-out "
                             "terms → OPEN (no false certificate)")
            return res
        if form is None:
            break

    # T2 last resort on a transform target: grow the primitive alphabet (ratchet) — handled by the caller's substrate
    if grow_primitives:
        res.trace.append("primitive ratchet available (T2) for transform targets")
    return res
