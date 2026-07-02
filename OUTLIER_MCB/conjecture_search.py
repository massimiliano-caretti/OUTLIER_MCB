"""conjecture_search — close the loop GENERATE → PROVE for theorems (the engine's strongest self-flagged gap).

math_discovery CHECKS a conjecture you hand it; this GENERATES candidate conjectures from a template space
(or mines them from a data-fitted formula), pipes each to an EXTERNAL formal verifier (z3 / lean), keeps the
formally proved ones, and — Reflexion — REFINES a disproved conjecture using its guaranteed counterexample
(a false universal over ℝ often becomes a true conditional once the variables are constrained). The verdict
is the SOLVER's, never the engine's. Honest naming: a `FORMALLY_PROVED` result is a real proof in the
solver's decidable fragment — NOT 'a new theorem' unless it also clears an online prior-art check.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Dict, List, Optional, Sequence, Tuple

from .math_discovery import Conjecture, investigate_conjecture, z3_backend


@dataclass
class ConjectureResult:
    statement: str
    status: str
    counterexample: Optional[Dict] = None
    proof_detail: str = ""
    refined_from: str = ""

    def markdown(self) -> str:
        tag = {"FORMALLY_PROVED": "✅ proved", "FORMALLY_DISPROVED": "❌ disproved",
               "EMPIRICALLY_SUPPORTED": "≈ supported", "TOOL_LIMIT_UNKNOWN": "? unknown",
               "TOOL_UNAVAILABLE": "· no solver"}.get(self.status, self.status)
        s = f"- **{tag}**: {self.statement}"
        if self.counterexample:
            s += f"  (counterexample {self.counterexample})"
        if self.refined_from:
            s += f"  [refined from: {self.refined_from}]"
        return s


@dataclass
class ConjectureDiscovery:
    results: List[ConjectureResult] = field(default_factory=list)

    def proved(self) -> List[ConjectureResult]:
        return [r for r in self.results if r.status == "FORMALLY_PROVED"]

    def disproved(self) -> List[ConjectureResult]:
        return [r for r in self.results if r.status == "FORMALLY_DISPROVED"]

    def to_dict(self) -> Dict:
        return {"proved": [r.statement for r in self.proved()],
                "disproved": [r.statement for r in self.disproved()],
                "refined_proved": [r.statement for r in self.proved() if r.refined_from],
                "total": len(self.results)}

    def markdown(self) -> str:
        L = [f"## Conjecture search — {len(self.proved())} proved, {len(self.disproved())} disproved "
             f"of {len(self.results)} candidates"]
        L += [r.markdown() for r in self.results]
        L.append("\n_FORMALLY_PROVED = a real proof in the solver's decidable fragment, NOT 'a new theorem' "
                 "without an online prior-art check._")
        return "\n".join(L)


def generate_conjectures(variables: Dict[str, Tuple[float, float]], expressions: Sequence[str],
                         relations: Sequence[str] = (">=", "==")) -> List[Conjecture]:
    """Build candidate conjectures from a template space: every pair of expressions under each relation,
    plus each expression ≥ 0. A small grammar that yields many falsifiable propositions to settle."""
    exprs = list(expressions)
    out: List[Conjecture] = []
    for i, e1 in enumerate(exprs):
        for e2 in exprs[i + 1:]:
            for rel in relations:
                out.append(Conjecture(statement=f"{e1} {rel} {e2}", claim_expr=f"({e1}) {rel} ({e2})",
                                      variables=dict(variables)))
    for e in exprs:
        out.append(Conjecture(statement=f"{e} >= 0", claim_expr=f"({e}) >= 0", variables=dict(variables)))
    return out


def mine_conjectures_from_formula(formula_expr: str, variables: Dict[str, Tuple[float, float]]) -> List[Conjecture]:
    """Mine invariants ABOUT a fitted/known formula: symmetry in the first two variables, non-negativity,
    and idempotent-style checks — the 'discover a property of the law' move."""
    names = list(variables)
    out: List[Conjecture] = []
    if len(names) >= 2:
        a, b = names[0], names[1]
        swapped = formula_expr.replace(a, "§").replace(b, a).replace("§", b)
        out.append(Conjecture(statement=f"the law is symmetric in {a},{b}",
                              claim_expr=f"({formula_expr}) == ({swapped})", variables=dict(variables)))
    out.append(Conjecture(statement=f"the law is non-negative", claim_expr=f"({formula_expr}) >= 0",
                          variables=dict(variables)))
    return out


def _refine_with_positivity(conj: Conjecture) -> Conjecture:
    """Reflexion: a universal that failed over ℝ often holds once the variables are POSITIVE (a common
    domain restriction). Add `v > 0` for each variable and re-pose the (now conditional) conjecture."""
    new_hyps = list(conj.hypotheses) + [f"{v} > 0" for v in conj.variables if f"{v} > 0" not in conj.hypotheses]
    return Conjecture(statement=conj.statement + " (refined: all variables > 0)", claim_expr=conj.claim_expr,
                      hypotheses=new_hyps, variables=dict(conj.variables), domain=conj.domain)


def _parse_counterexample_number(value) -> Optional[Fraction]:
    try:
        return Fraction(str(value).strip())
    except Exception:
        return None


def _floor_frac(value: Fraction) -> int:
    return value.numerator // value.denominator


def _ceil_frac(value: Fraction) -> int:
    return -((-value.numerator) // value.denominator)


def _bound_text(var: str, op: str, bound: int) -> str:
    return f"{var} {op} {bound}"


def refine_with_counterexample_cells(conj: Conjecture, counterexample: Dict,
                                     max_refinements: int = 4) -> List[Conjecture]:
    """Split away from a solver counterexample into adjacent domain cells and re-pose the same claim.

    This is the theorem analogue of "learn from the failed experiment": if a universal dies at x=1/2,
    do not only try the generic x>0 repair; also try the neighboring cells x<=0 and x>=1. The solver still
    decides whether either cell is a theorem. These refinements are hypotheses, not claims of truth.
    """
    out: List[Conjecture] = []
    seen = set(conj.hypotheses)
    for var in conj.variables:
        if var not in counterexample:
            continue
        value = _parse_counterexample_number(counterexample[var])
        if value is None:
            continue
        lo, hi = conj.variables.get(var, (None, None))
        floor_v, ceil_v = _floor_frac(value), _ceil_frac(value)
        if floor_v == ceil_v:          # exact integer counterexample: exclude the point by adjacent cells
            candidates = [("<=", floor_v - 1), (">=", ceil_v + 1)]
        else:
            candidates = [("<=", floor_v), (">=", ceil_v)]
        for op, bound in candidates:
            if lo is not None and op == "<=" and bound < lo:
                continue
            if hi is not None and op == ">=" and bound > hi:
                continue
            hyp = _bound_text(var, op, bound)
            if hyp in seen:
                continue
            seen.add(hyp)
            hyps = list(conj.hypotheses) + [hyp]
            out.append(Conjecture(
                statement=f"{conj.statement} (counterexample-cell: {hyp})",
                claim_expr=conj.claim_expr, lhs=conj.lhs, rhs=conj.rhs,
                hypotheses=hyps, variables=dict(conj.variables), domain=conj.domain))
            if len(out) >= max_refinements:
                return out
    return out


def discover_conjectures(conjectures: Sequence[Conjecture], verifier=None, refine: bool = True) -> ConjectureDiscovery:
    """Run each candidate through the external formal verifier; keep the proved, record the disproved with
    their guaranteed counterexamples, and REFINE a disproved universal (Reflexion) into a conditional, then
    re-verify. `verifier` defaults to z3_backend() (absent ⇒ honest TOOL_UNAVAILABLE, never a fake proof)."""
    verifier = verifier if verifier is not None else z3_backend()
    disco = ConjectureDiscovery()
    for conj in conjectures:
        res = investigate_conjecture(conj, backend=verifier)
        status = ("TOOL_UNAVAILABLE" if (res.proof is not None
                                         and res.proof.status == "TOOL_UNAVAILABLE"
                                         and res.status in ("SKETCH", "EMPIRICALLY_SUPPORTED"))
                  else res.status)
        disco.results.append(ConjectureResult(
            statement=conj.statement, status=status,
            counterexample=(res.counterexample.assignment if res.counterexample else None),
            proof_detail=(res.proof.detail if res.proof else "")))
        if refine and status == "FORMALLY_DISPROVED" and res.counterexample:
            refinements = [_refine_with_positivity(conj)]
            refinements += refine_with_counterexample_cells(conj, res.counterexample.assignment)
            seen_refinements = set()
            for refined in refinements:
                key = (refined.claim_expr, tuple(refined.hypotheses), refined.statement)
                if key in seen_refinements:
                    continue
                seen_refinements.add(key)
                r2 = investigate_conjecture(refined, backend=verifier)
                status2 = ("TOOL_UNAVAILABLE" if (r2.proof is not None
                                                  and r2.proof.status == "TOOL_UNAVAILABLE"
                                                  and r2.status in ("SKETCH", "EMPIRICALLY_SUPPORTED"))
                           else r2.status)
                disco.results.append(ConjectureResult(
                    statement=refined.statement, status=status2,
                    counterexample=(r2.counterexample.assignment if r2.counterexample else None),
                    proof_detail=(r2.proof.detail if r2.proof else ""), refined_from=conj.statement))
                if status2 == "FORMALLY_PROVED":
                    continue
    return disco
