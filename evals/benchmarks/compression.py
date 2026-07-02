"""compression — the EXTERNAL benchmark for Point 2 (endogenous semantic grounding). It settles the
`conceptual_compression` Pareto dimension: take a log, let the engine ground symbols for its recurring
patterns, and measure the Minimum-Description-Length compression ratio the symbols achieve. The negative
controls (an ungrounded symbol; a log with no repetition) must yield ratio ≤ 1, so the dimension can never be
inflated by empty concepts.
"""
from __future__ import annotations
from typing import List

from OUTLIER_MCB.semantic_grounding import (SymbolRegistry, find_recurring_patterns, ground_new_symbol,
                                               conceptual_compression, EndogenousSymbol, verify_grounding)


def _diagnostic_log() -> List[str]:
    """A realistic self-diagnostic log: a recurring failure motif (retry storm) plus incidental events."""
    motif = ["settle", "timeout", "retry"]
    return motif * 10 + ["ok", "ok"] + motif * 6 + ["diverge"] + motif * 4


def conceptual_compression_score(log=None, top_k: int = 3) -> float:
    """Ground the top recurring patterns of `log` into symbols and return the MDL compression ratio (the Pareto
    dimension value). Deterministic. ≥ 1 always; > 1 iff real recurring structure was named."""
    log = log if log is not None else _diagnostic_log()
    reg = SymbolRegistry()
    grounded: List[EndogenousSymbol] = []
    for pat, _support in find_recurring_patterns(log)[:top_k]:
        sym = ground_new_symbol(pat, log, reg)
        if sym is not None:
            grounded.append(sym)
    return conceptual_compression(log, grounded)


# ── negative controls ────────────────────────────────────────────────────────────────────────────────
def ungrounded_symbol_gives_no_gain() -> bool:
    """A symbol whose pattern never occurs must NOT compress the log (ratio ≤ 1) and must fail verification."""
    log = _diagnostic_log()
    ghost = EndogenousSymbol("_GHOST", ("never", "seen", "here"), support=99)   # a lied-about support
    return (not verify_grounding(ghost, log)) and conceptual_compression(log, [ghost]) <= 1.0


def no_repetition_gives_no_gain() -> bool:
    """A log with no recurring pattern yields no grounded symbols → ratio 1.0 (nothing to compress)."""
    log = [f"e{i}" for i in range(40)]                       # all distinct → no repetition
    return conceptual_compression_score(log) <= 1.0


def controls_pass() -> bool:
    return ungrounded_symbol_gives_no_gain() and no_repetition_gives_no_gain()
