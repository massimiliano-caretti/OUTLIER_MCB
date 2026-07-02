"""solver_portfolio — run several external solvers on ONE lemma; the first VALID certificate wins (G5).

This is what makes 'in parallel' real: different solvers close different lemmas, so a portfolio maximises the
auto-closed-lemma rate. Same contract as z3_backend: (status, counterexample|None, detail), .backend_name. It
mutates .backend_name to the WINNING solver during the call, so settle_lemma maps to that solver's real
certificate (CVC5_PROVED, ISABELLE_CHECKED, …), never a generic label.

DETERMINISM (non-negotiable, rule 4): the winner is chosen by a FIXED PRIORITY ORDER, never 'whoever is fastest'
— so the same lemma yields the same certificate on every run, in any environment. Realised as a priority-ordered
sweep with early exit: a fast high-priority solver (z3) short-circuits slow ones (Isabelle), giving the speed of a
portfolio with a reproducible result. Missing tools degrade to TOOL_UNAVAILABLE, so it is always safe to list all.
"""
from __future__ import annotations
from typing import List, Optional


def default_backends(timeout_ms: int = 5000) -> List:
    """The standard portfolio in FIXED priority order: z3 → cvc5 → Vampire → E → Isabelle → PARI. Every entry is
    opt-in (absent tool ⇒ TOOL_UNAVAILABLE), so listing all is safe."""
    from .math_discovery import z3_backend
    from .cvc5_backend import cvc5_backend
    from .atp_backend import atp_backend
    from .isabelle_backend import isabelle_backend
    from .pari_backend import pari_backend
    return [z3_backend(timeout_ms), cvc5_backend(timeout_ms), atp_backend("vampire", timeout_ms),
            atp_backend("e", timeout_ms), isabelle_backend(timeout_ms), pari_backend(timeout_ms)]


def portfolio_backend(backends: Optional[List] = None, timeout_ms: int = 5000):
    """A portfolio prover. `backends` is a FIXED-priority list (default `default_backends()`); the first to return
    FORMALLY_PROVED/FORMALLY_DISPROVED wins and its name is recorded. Returns `prove(conj)` whose `.backend_name`
    is set to the winner (or 'portfolio' if none decided) and whose `.trace` lists every (solver, status)."""
    bks = backends if backends is not None else default_backends(timeout_ms)

    def prove(conj):
        trace = []
        reasons = []
        unavailable = 0
        for b in bks:                                   # FIXED priority order → deterministic winner (not fastest)
            name = getattr(b, "backend_name", "solver")
            status, ce, detail = b(conj)
            trace.append((name, status))
            if status in ("FORMALLY_PROVED", "FORMALLY_DISPROVED"):
                prove.backend_name = name               # settle_lemma reads the WINNER → correct certificate
                prove.winner = name
                prove.trace = trace
                return status, ce, f"[portfolio winner: {name}] {detail}"
            if status == "TOOL_UNAVAILABLE":
                unavailable += 1
            reasons.append(f"{name}={status}")
        prove.backend_name = "portfolio"
        prove.winner = None
        prove.trace = trace
        if unavailable == len(bks):
            return "TOOL_UNAVAILABLE", None, "no solver available in the portfolio: " + " | ".join(reasons)
        return "TOOL_LIMIT_UNKNOWN", None, "no solver in the portfolio decided: " + " | ".join(reasons)

    prove.backend_name = "portfolio"
    prove.winner = None
    prove.trace = []
    return prove
