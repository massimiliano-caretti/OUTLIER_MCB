"""expressiveness — the EXTERNAL benchmark for Point 3 (invent a new formal language). It settles the
`expressive_power` Pareto dimension: on a problem family that is verbose in a baseline mini-DSL, the engine
invents a richer language (a new primitive abstracted from recurring sub-solutions) and we measure how much
more compactly it expresses the same solutions. Controls: a rename of the baseline scores 1 (no gain), and a
language that cannot solve a solvable problem scores 0. Soundness (the interpreter really computes) is a
protected invariant.
"""
from __future__ import annotations
from typing import List, Tuple

from OUTLIER_MCB.language_inventor import (FormalLanguage, integer_baseline, invent_new_language,
                                              expressive_power, shortest_program, is_sound)


def _affine_family() -> List[List[Tuple]]:
    """2·(x+k), k=1..3 — lengths 2,3,4 in the baseline; a macro for the common tail shortens them."""
    return [[(x, 2 * (x + k)) for x in range(4)] for k in (1, 2, 3)]


def expressive_power_score() -> float:
    """The Pareto-dimension value: expressive gain of the invented language over the baseline on the family."""
    base = integer_baseline()
    fam = _affine_family()
    return expressive_power(invent_new_language(base, fam), base, fam)


# ── negative controls ────────────────────────────────────────────────────────────────────────────────
def rename_gives_no_gain() -> bool:
    """A language identical to the baseline (a rename) expresses nothing more compactly → power == 1."""
    base = integer_baseline()
    return expressive_power(base, base, _affine_family()) == 1.0


def unsolvable_language_scores_zero() -> bool:
    """A crippled language missing a needed primitive cannot solve a baseline-solvable problem → power 0."""
    crippled = FormalLanguage(name="crippled", primitives={"inc": lambda x: x + 1})   # no 'double'
    base = integer_baseline()
    fam = _affine_family()
    # the baseline solves these (needs double); the crippled language cannot → 0
    return expressive_power(crippled, base, fam) == 0.0


def controls_pass() -> bool:
    return rename_gives_no_gain() and unsolvable_language_scores_zero()
