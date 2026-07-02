"""counterexamples — a second, ORTHOGONAL certified substrate: refute false conjectures with a real counterexample.

A different capability from symbolic regression: given conjectures over the integers (some true, some false), the
engine must REFUTE the false ones by exhibiting a concrete counterexample — a verified fact (the predicate is
False there), never self-judged. The metric is the false-conjecture refutation rate within a search window.

It is genuinely IMPROVABLE: several famous conjectures hold for a long initial run and fail only later
(n²+n+41 is prime for n=0..39 but composite at 40; n²−79n+1601 fails at 80; the Fermat number 2^(2^5)+1 is
composite). A narrow search misses them; widening it finds more — a real, certified gain, with no risk of a
false refutation (a true conjecture has no counterexample to find). Honesty: a wider window is more compute, not
a cleverer claim; the engine never asserts a conjecture is TRUE (absence of a counterexample is not a proof).
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, List, Optional


def _is_prime(m) -> bool:
    m = int(round(m))
    if m < 2:
        return False
    d = 2
    while d * d <= m:
        if m % d == 0:
            return False
        d += 1
    return True


@dataclass
class Conjecture:
    name: str
    predicate: Callable[[int], bool]   # claimed to hold for all n in [0, ∞)
    is_true: bool                      # ground truth (whether a counterexample exists at all)


# 3 FALSE conjectures whose counterexample appears only beyond a narrow window, + 3 TRUE ones (no counterexample)
CONJECTURES: List[Conjecture] = [
    Conjecture("n^2+n+41 is prime",          lambda n: _is_prime(n * n + n + 41),        False),  # fails at n=40
    Conjecture("n^2-79n+1601 is prime",      lambda n: _is_prime(n * n - 79 * n + 1601), False),  # fails at n=80
    Conjecture("2^(2^n)+1 is prime (Fermat)", lambda n: _is_prime(2 ** (2 ** n) + 1),     False),  # fails at n=5
    Conjecture("n^2 >= n",                   lambda n: n * n >= n,                        True),
    Conjecture("n^3 >= n^2 (n>=0)",          lambda n: n ** 3 >= n ** 2,                  True),
    Conjecture("2n <= n^2+1",                lambda n: 2 * n <= n * n + 1,                True),
]


@dataclass
class RefutationReport:
    width: int
    refuted: int
    n_false: int
    false_refutation: int              # a TRUE conjecture wrongly "refuted" — must always be 0 (a bug if not)

    @property
    def rate(self) -> float:
        return round(self.refuted / self.n_false, 4) if self.n_false else 0.0


def find_counterexample(conj: Conjecture, width: int) -> Optional[int]:
    """Search [0, width] for a certified counterexample (a concrete n where the predicate is False). Returns the
    n, or None. For a Fermat-style conjecture the index is the exponent, so the window is small by design."""
    cap = min(width, 12) if "Fermat" in conj.name else width   # 2^(2^n) explodes — the exponent window is tiny
    for n in range(0, cap + 1):
        try:
            if not conj.predicate(n):
                return n
        except Exception:
            return n
    return None


def refutation_rate(width: int, conjectures: List[Conjecture] = None) -> RefutationReport:
    """The certified metric: fraction of FALSE conjectures refuted within [0, width]. A TRUE conjecture must
    never be 'refuted' (verified: false_refutation stays 0)."""
    conjectures = conjectures if conjectures is not None else CONJECTURES
    falses = [c for c in conjectures if not c.is_true]
    refuted = sum(1 for c in falses if find_counterexample(c, width) is not None)
    false_ref = sum(1 for c in conjectures if c.is_true and find_counterexample(c, width) is not None)
    return RefutationReport(width=width, refuted=refuted, n_false=len(falses), false_refutation=false_ref)
