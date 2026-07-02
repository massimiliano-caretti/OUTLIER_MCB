"""solution_type_lattice — when one FORM of answer is impossible, PIVOT to the next (T4). Breaks OBJECTIVE.

A discoverer does not give up when a closed form does not exist — it changes what counts as "solved". This lattice
orders the forms of a real solution from the most explicit to the most structural; each is a LEGITIMATE discovery.
When a form is excluded (e.g. the sequence is non-holonomic, so no closed form / P-recurrence), the engine pivots
the objective to the next form instead of collapsing to CONJECTURE.

Pure-Python, deterministic. The lattice is the creative break of the OBJECTIVE axis — «what counts as an answer».
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional

# most explicit → most structural. Each is a real, celebrated discovery — not a consolation prize.
SOLUTION_FORMS: List[str] = [
    "CLOSED_FORM",             # a(n) = explicit formula
    "LINEAR_RECURRENCE",       # constant-coefficient (C-finite)
    "HOLONOMIC_RECURRENCE",    # polynomial-coefficient (P-recursive)
    "GENERATING_FUNCTION",     # an algebraic/differential equation for Σ a(n) x^n
    "ASYMPTOTIC_WITH_BAND",    # a(n) ~ f(n) with a certified error band
    "ALGORITHM",               # a correct method + complexity (compute a(n) without a formula)
    "BIJECTION",               # a structural equivalence to a counted set
    "CONDITIONAL_THEOREM",     # "solved IF <hypothesis>" — a real conditional result
]
_RANK = {f: i for i, f in enumerate(SOLUTION_FORMS)}

_DESCRIBE = {
    "CLOSED_FORM": "an explicit formula for a(n)",
    "NONLINEAR_RECURRENCE": "a non-linear (polynomial / Somos-like) generative recurrence",
    "STRUCTURAL_INVARIANT": "a structural invariant (a certified law the sequence obeys, not a generative solution)",
    "MULTIPLICATIVE": "a multiplicative (number-theoretic) structure, a(m·n)=a(m)·a(n) — set by values on prime powers",
    "K_AUTOMATIC": "a k-automatic structure — a finite automaton on the base-k digits of n generates a(n)",
    "LINEAR_RECURRENCE": "a constant-coefficient linear recurrence (C-finite)",
    "HOLONOMIC_RECURRENCE": "a polynomial-coefficient recurrence (P-recursive / holonomic)",
    "GENERATING_FUNCTION": "an algebraic or differential equation for the generating function",
    "ASYMPTOTIC_WITH_BAND": "an asymptotic law a(n) ~ f(n) with a certified error band",
    "ALGORITHM": "a correct algorithm + complexity that computes a(n)",
    "BIJECTION": "a bijection to a set whose count is known",
    "CONDITIONAL_THEOREM": "a conditional result: solved IF a stated hypothesis holds",
}


@dataclass
class Pivot:
    from_form: str
    to_form: Optional[str]
    reason: str

    @property
    def pivoted(self) -> bool:
        return self.to_form is not None


def describe(form: str) -> str:
    return _DESCRIBE.get(form, form)


def is_terminal(form: str) -> bool:
    """The last form in the lattice — there is nothing weaker to pivot to (but it is still a real discovery)."""
    return _RANK.get(form, -1) == len(SOLUTION_FORMS) - 1


def next_form(form: str) -> Optional[str]:
    i = _RANK.get(form)
    if i is None or i + 1 >= len(SOLUTION_FORMS):
        return None
    return SOLUTION_FORMS[i + 1]


def pivot(form: str, reason: str = "the current form is not attainable") -> Pivot:
    """PIVOT the objective from `form` to the next, weaker-but-still-real form. This is the creative move that keeps
    a discoverer going where a refuter would stop at CONJECTURE."""
    nf = next_form(form)
    return Pivot(from_form=form, to_form=nf, reason=reason if nf else "reached the most structural form; no weaker form remains")


def form_for_recurrence(order: int, degree: int) -> str:
    """The solution FORM a mined recurrence realises: a P-recurrence with constant coefficients is C-finite."""
    return "LINEAR_RECURRENCE" if degree == 0 else "HOLONOMIC_RECURRENCE"
