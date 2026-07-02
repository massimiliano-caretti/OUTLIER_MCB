"""barriers — no-go theorems as a KILL gate that forces the search out of the already-dead zone.

The closure gate (closures.py) rules an idea INSIDE_THE_BOX when it reduces to a universal representation.
A BARRIER is the dual for hard open problems: a proven obstruction (a no-go theorem) that kills a whole
ROUTE of attack as already-known-dead. The point is not pessimism — it is to stop the engine from re-proposing
a route the literature proved cannot work, and to point at the ONLY admissible exits the theorem leaves open.

Flagship: the PARITY PROBLEM (Selberg). A parity-respecting sieve cannot, by itself, distinguish numbers with
an even vs odd number of prime factors — so a pure-sieve attack aimed straight at gap = 2 (twin primes) is
DEAD_BY_BARRIER. The exits the theorem itself leaves open: inject a parity-BREAKING observable, add automorphic
/ spectral input, or change the objective to a finite certified bound (Maynard–Tao's bounded gaps — which the
barrier does NOT block). This is honest by construction: it never says a conjecture is false or proved — it
says one ROUTE is closed and names the openings.

Detectors are explicit and structural (no learned magic), mirroring closures.py: lexical signals for the dead
route, and explicit ESCAPE signals that mean the idea already takes an admissible exit (the negative control).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

DEAD_BY_BARRIER, NOT_BLOCKED, UNKNOWN = "DEAD_BY_BARRIER", "NOT_BLOCKED", "UNKNOWN"


def _text_of(idea) -> str:
    if isinstance(idea, str):
        return idea
    g = lambda k: getattr(idea, k, "") if not isinstance(idea, dict) else idea.get(k, "")
    return " ".join(str(g(k)) for k in ("name", "negation", "claim", "statement", "description") if g(k))


# ── PARITY PROBLEM signals ──
# the dead route: a sieve attack aimed at the literal twin-prime endpoint (gap = 2)
_SIEVE = ("sieve", "crivello", "selberg", "gpy", "goldston", "maynard", "large sieve", "sieve-only",
          "sieve only", "sieving", "upper bound sieve", "lower bound sieve")
_TWIN_TARGET = ("twin prime", "twin primes", "primi gemelli", "gemelli", "gap 2", "gap=2", "gap = 2",
                "gap of 2", "gap of two", "differ by 2", "differ by two", "two apart", "p+2", "p + 2")
# the admissible EXITS — if present, the idea already escapes the barrier (NOT blocked: the negative control)
_PARITY_ESCAPES = ("parity-breaking", "parity breaking", "break parity", "breaks parity", "breaking parity",
                   "automorphic", "gl(2)", "gl2", "l-function", "l function", "spectral", "bilinear",
                   "exponential sum", "exponential-sum", "kloosterman", "new observable", "non-sieve observable",
                   "bounded gap", "bounded gaps", "finite bound", "gap finito", "limitato", "h finite", "h finito")


def _detect_parity(text: str) -> str:
    low = text.lower()
    if any(s in low for s in _PARITY_ESCAPES):
        return NOT_BLOCKED                               # already takes an admissible exit (parity-breaking / new objective)
    sieve = any(s in low for s in _SIEVE)
    twin = any(s in low for s in _TWIN_TARGET)
    if sieve and twin:
        return DEAD_BY_BARRIER                           # pure-sieve route aimed at gap = 2 → the parity barrier kills it
    return UNKNOWN


# ── SECOND LAW / energy-conservation signals (physics / engineering) — barriers are AGNOSTIC, not math-only ──
_THERMO_DEAD = ("perpetual motion", "perpetuum mobile", "moto perpetuo", "over-unity", "over unity", "overunity",
                "free energy", "efficiency greater than 1", "efficiency > 1", "efficiency above 100",
                "more energy out than in", "net energy from a closed", "net work from a closed",
                "net work from an isolated", "creates energy", "destroys entropy", "violates conservation of energy",
                "100% efficient closed", "self-powered", "self powered")
_THERMO_ESCAPES = ("open system", "external energy", "energy input", "power source", "from a reservoir",
                   "temperature gradient", "thermal gradient", "heat bath", "not a closed", "not closed",
                   "external source", "draws energy", "fuel", "battery", "ambient gradient", "extracts from",
                   "work from a gradient", "input power", "driven", "forcing", "pump")


def _detect_thermo(text: str) -> str:
    low = text.lower()
    if any(s in low for s in _THERMO_ESCAPES):
        return NOT_BLOCKED                               # an OPEN system / external drive — a legitimate exit
    if any(s in low for s in _THERMO_DEAD):
        return DEAD_BY_BARRIER                           # net output from a closed system → 1st/2nd law kills it
    return UNKNOWN


@dataclass
class Barrier:
    name: str
    theorem: str                      # the no-go / obstruction the barrier encodes
    citation: str
    detect: Callable                  # (text) -> DEAD_BY_BARRIER | NOT_BLOCKED | UNKNOWN
    exits: List[str] = field(default_factory=list)   # the ONLY openings the theorem leaves
    domains: List[str] = field(default_factory=list)  # pack names it applies to ([] = all)


@dataclass
class BarrierVerdict:
    barrier: str
    status: str                       # DEAD_BY_BARRIER | NOT_BLOCKED | UNKNOWN
    citation: str
    reason: str
    exits: List[str] = field(default_factory=list)

    def markdown(self) -> str:
        if self.status == DEAD_BY_BARRIER:
            return (f"- verdict: **DEAD_BY_BARRIER** «{self.barrier}» ({self.citation}) — {self.reason} "
                    f"Admissible exits: {', '.join(self.exits)}.")
        return f"- barrier «{self.barrier}»: {self.status} — {self.reason}"


BARRIER_REGISTRY: Dict[str, Barrier] = {
    "PARITY_PROBLEM": Barrier(
        name="PARITY_PROBLEM",
        theorem="a parity-respecting sieve cannot distinguish integers with an even vs odd number of prime "
                "factors, so it cannot isolate primes (gap = 2) by itself",
        citation="Selberg's parity problem; see Friedlander–Iwaniec, Opera de Cribro",
        detect=_detect_parity,
        exits=["inject a parity-BREAKING observable (automorphic / bilinear / exponential-sum input)",
               "add automorphic / spectral input (escape sieve-only)",
               "change the objective to a finite certified gap bound (Maynard–Tao bounded gaps — NOT blocked)"],
        domains=["number_theory"]),
    "THERMODYNAMICS_2ND_LAW": Barrier(
        name="THERMODYNAMICS_2ND_LAW",
        theorem="no net work/energy can be extracted from a CLOSED/isolated system over a cycle (1st law: energy "
                "conservation; 2nd law: entropy of an isolated system does not decrease) — perpetual motion is impossible",
        citation="First and Second Laws of Thermodynamics (Carnot / Clausius / Kelvin)",
        detect=_detect_thermo,
        exits=["make the system OPEN — draw from an external reservoir / energy source",
               "exploit a temperature/chemical GRADIENT (a non-equilibrium drive), not a closed cycle",
               "change the objective: efficiency BELOW the Carnot bound, not above unity"],
        domains=["physics", "engineering"]),
}


def barrier_membership(idea, pack=None) -> Optional[BarrierVerdict]:
    """Check `idea` against every barrier that applies to `pack` (a barrier with empty `domains` applies to
    all). Returns the first DEAD_BY_BARRIER verdict (the route is proven dead), else a NOT_BLOCKED verdict when
    a relevant barrier explicitly saw an admissible exit, else None (no relevant barrier fired). Never asserts a
    conjecture is true or false — it rules on the ROUTE only."""
    text = _text_of(idea)
    pack_name = getattr(pack, "name", "") if pack is not None else ""
    not_blocked: Optional[BarrierVerdict] = None
    for b in BARRIER_REGISTRY.values():
        if b.domains and pack_name and pack_name not in b.domains:
            continue
        status = b.detect(text)
        if status == DEAD_BY_BARRIER:
            return BarrierVerdict(
                barrier=b.name, status=DEAD_BY_BARRIER, citation=b.citation,
                reason=(f"the idea reduces to a route the «{b.name}» barrier proves cannot work: {b.theorem}."),
                exits=b.exits)
        if status == NOT_BLOCKED and not_blocked is None:
            not_blocked = BarrierVerdict(
                barrier=b.name, status=NOT_BLOCKED, citation=b.citation,
                reason="the idea already takes an admissible exit the barrier leaves open (not the dead route).",
                exits=b.exits)
    return not_blocked
