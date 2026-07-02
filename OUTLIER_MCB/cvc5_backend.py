"""cvc5_backend — a SECOND SMT solver (cvc5) in portfolio with z3 (G3).

Different theories and heuristics than z3, so it decides some lemmas z3 leaves 'unknown' (and vice versa) — the
cheapest useful parallelism. Same contract as z3_backend: (status, counterexample|None, detail), .backend_name.
Opt-in: needs the `cvc5` python package OR the `cvc5` binary; absent ⇒ TOOL_UNAVAILABLE (never a crash, no forced
import). Same ¬claim strategy as z3 (∀x.P ⟺ UNSAT(¬P)) via the shared SMT-LIB compiler, so the two agree by
construction. Deterministic.
"""
from __future__ import annotations
import re

from ._solver_common import which, run_tool, ast_to_smtlib


def _parse_model(text: str, names):
    """Best-effort counterexample from an SMT-LIB (get-model): `(define-fun x () Real 3)` → {'x': '3'}."""
    ce = {}
    for n in names:
        m = re.search(r"\(define-fun\s+" + re.escape(n) + r"\s*\(\)\s*\w+\s+([^\)]+)\)", text)
        if m:
            ce[n] = m.group(1).strip()
    return ce or None


def cvc5_backend(timeout_ms: int = 5000):
    """OPT-IN cvc5 SMT backend. See module docstring. Returns a `prove(conj)` callable with .backend_name='cvc5'."""
    timeout_s = max(0.1, timeout_ms / 1000.0)

    def prove(conj):
        names = list(conj.variables or {})
        try:
            smt = ast_to_smtlib(conj.claim_expr, conj.lhs, conj.rhs, conj.hypotheses, conj.variables, conj.domain)
        except Exception as exc:
            return "TOOL_LIMIT_UNKNOWN", None, f"could not compile the claim to SMT-LIB: {exc}"
        binary = which("cvc5")
        if binary is None:
            # no binary — try the python package as a fallback runner over the same SMT-LIB
            try:
                import cvc5  # noqa: F401
            except ImportError:
                return "TOOL_UNAVAILABLE", None, ("cvc5 not installed: `pip install cvc5` or put the `cvc5` binary "
                                                  "on PATH. SMT-LIB was generated (see detail).\n" + smt)
            return _prove_via_pkg(smt, names, timeout_s)
        code, out, err, timed_out = run_tool(
            [binary, "--lang", "smt2", "--produce-models"], stdin_text=smt, timeout_s=timeout_s)
        if timed_out:
            return "TOOL_LIMIT_UNKNOWN", None, f"cvc5 timed out after {timeout_s}s"
        low = (out or "").lower()
        if low.startswith("unsat") or "\nunsat" in low:
            return "FORMALLY_PROVED", None, "cvc5: the negation is unsatisfiable under the hypotheses → proved."
        if low.startswith("sat") or "\nsat" in low:
            return "FORMALLY_DISPROVED", _parse_model(out, names), "cvc5 found a guaranteed counterexample."
        return "TOOL_LIMIT_UNKNOWN", None, f"cvc5 returned 'unknown'/unparsed (stdout: {out[:120]!r}, err: {err[:120]!r})"

    prove.backend_name = "cvc5"
    return prove


def _prove_via_pkg(smt: str, names, timeout_s: float):
    """Run the same SMT-LIB through the cvc5 python package (when the binary is absent)."""
    try:
        import cvc5
        from cvc5 import Kind  # noqa: F401
    except Exception as exc:  # pragma: no cover — exercised only where the package is installed
        return "TOOL_UNAVAILABLE", None, f"cvc5 python package present but unusable: {exc}"
    try:  # pragma: no cover — requires the package at runtime
        slv = cvc5.Solver()
        slv.setOption("produce-models", "true")
        slv.setLogic("ALL")
        cmds = slv.parse(smt) if hasattr(slv, "parse") else None  # newer API
        del cmds
        res = slv.checkSat()
        if res.isUnsat():
            return "FORMALLY_PROVED", None, "cvc5 (python): the negation is unsatisfiable → proved."
        if res.isSat():
            ce = {n: str(slv.getValue(slv.getVariable(n))) for n in names} if hasattr(slv, "getVariable") else None
            return "FORMALLY_DISPROVED", ce, "cvc5 (python): guaranteed counterexample."
        return "TOOL_LIMIT_UNKNOWN", None, "cvc5 (python) returned unknown."
    except Exception as exc:  # pragma: no cover
        return "TOOL_LIMIT_UNKNOWN", None, f"cvc5 python API error: {exc}"
