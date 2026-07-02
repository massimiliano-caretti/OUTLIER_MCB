"""aesthetics — the EXTERNAL benchmark for Point 4 (non-homeostatic intrinsic motivation). It settles the
`elegance` Pareto dimension by checking the aesthetic metrics on CANONICAL examples: a beautiful, terse formula
must score higher overall elegance than a clumsy-but-equivalent one, a symmetric form must score higher symmetry
than an asymmetric one, and a small formula higher simplicity than a verbose one. The metrics are objective AST
functions (a protected invariant locks that), so 'beauty' is measured, never asserted.
"""
from __future__ import annotations
from typing import List, Tuple

from OUTLIER_MCB.aesthetics import elegance_score, measure_symmetry, measure_simplicity

# (beautiful, clumsy-but-equivalent) pairs — the beautiful one must win on elegance
_PAIRS: List[Tuple[str, str]] = [
    ("m*c**2", "m*c*c + 0*m + m - m"),
    ("a + b", "a + b + 0*a + 0*b"),
    ("x*y", "x*y*1 + 0 + x - x"),
]
_CORPUS = ["a+b", "a*b", "x-y", "p/q"]


def canonical_beauty_ranked_above_clumsy() -> bool:
    return all(elegance_score(nice, _CORPUS)["elegance"] > elegance_score(ugly, _CORPUS)["elegance"]
               for nice, ugly in _PAIRS)


def elegance_dimension_score(artifact: str = "m*c**2") -> float:
    """The Pareto-dimension value for a given artifact: its scalar elegance in [0,1]."""
    return elegance_score(artifact, _CORPUS)["elegance"]


# ── controls: the metrics must behave objectively, not arbitrarily ──────────────────────────────────────
def symmetry_control() -> bool:
    return measure_symmetry("a + b") == 1.0 and measure_symmetry("a - b") == 0.0


def simplicity_control() -> bool:
    return measure_simplicity("m*c**2") > measure_simplicity("m*c*c + 0*m + m - m")


def controls_pass() -> bool:
    return canonical_beauty_ranked_above_clumsy() and symmetry_control() and simplicity_control()
