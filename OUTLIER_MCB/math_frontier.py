"""math_frontier — the math discoverer's toward-objective loop, composed and honest (wires two orphans).

frontier_search maintains a CERTIFIED, monotone frontier of sub-results and turns every failed lemma into the
next lever; solution_type_lattice.pivot degrades the OBJECTIVE to the next weaker-but-still-real form when the
strong one is not attained. Both sat unwired. This entry composes them into one honest flow:

    propose_sublemmas(pack) → frontier_search(problem, candidates, resolver) → if nothing certified at the
    current solution FORM, pivot to the next form (never collapse to a bare CONJECTURE).

Honest by construction: a sub-lemma with no predicate settles to UNKNOWN and is KEPT as a next lever (never a
claim); the parent conjecture is never asserted. With a real `resolver` (z3/lean/data/benchmark) the frontier
actually advances; without one, the value is the frontier of levers plus the pivoted weaker form to aim at.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class MathFrontierResult:
    problem: str
    report: object                 # a FrontierSearchReport (the monotone certified frontier + next levers)
    current_form: str
    pivot: object = None           # a solution_type_lattice.Pivot when the strong form was not attained
    note: str = ""

    @property
    def advanced(self) -> bool:
        return bool(getattr(self.report, "advanced", []))

    def markdown(self) -> str:
        L = [f"## Math frontier — «{self.problem}» (target form: {self.current_form})"]
        L.append(self.report.markdown() if hasattr(self.report, "markdown") else "")
        if self.pivot is not None and self.pivot.pivoted:
            from .solution_type_lattice import describe
            L.append(f"- **pivot the objective:** {self.current_form} → **{self.pivot.to_form}** "
                     f"({describe(self.pivot.to_form)}) — {self.pivot.reason}")
        elif self.pivot is not None:
            L.append(f"- {self.pivot.reason}")
        L.append(f"- {self.note}")
        return "\n".join(L)


def math_frontier(problem: str, pack, resolver=None, backend=None, candidates: Optional[List] = None,
                  current_form: str = "CLOSED_FORM", k: int = 4, ledger=None,
                  log=None) -> MathFrontierResult:
    """Run one honest toward-objective pass for a math problem. `candidates` defaults to sub-lemma stubs mined
    from `pack` (propose_sublemmas). Pass a real `resolver`/`backend` to actually certify advances; otherwise
    the frontier records the levers and the loop pivots the objective to the next weaker real form."""
    from .frontier_search import propose_sublemmas, frontier_search
    from .solution_type_lattice import pivot as pivot_solution_type   # the public 'pivot the objective' move
    cands = candidates if candidates is not None else propose_sublemmas(pack, k=k)
    report = frontier_search(problem, cands, pack=pack, resolver=resolver, backend=backend, ledger=ledger, log=log)
    piv = None
    if not report.advanced:
        piv = pivot_solution_type(current_form, reason="no sub-lemma certified at this form on this pass")
    note = ("advanced the certified frontier — the parent stays a conjecture until fully settled." if report.advanced
            else "nothing certified at the strong form → pivot to a weaker real form and keep the levers "
                 "(a discoverer degrades the objective; it does not collapse to a bare conjecture).")
    return MathFrontierResult(problem=problem, report=report, current_form=current_form, pivot=piv, note=note)
