"""atp_backend — first-order Automated Theorem Provers (Vampire, E) via TPTP (G4).

ATPs have a different strength from SMT: quantifiers and relational axioms where SMT arithmetic heuristics struggle.
They round out the level-A portfolio. Same contract as z3_backend: (status, counterexample|None, detail),
.backend_name ∈ {'vampire','e'}. Opt-in: needs the `vampire` / `eprover` (or `E`) binary; absent ⇒
TOOL_UNAVAILABLE (never a crash). The claim is compiled to a TPTP TFF conjecture (typed arithmetic) via the shared
compiler; the prover reports a proof of the goal (a refutation of its negation). Deterministic.
"""
from __future__ import annotations

from ._solver_common import which, run_tool, ast_to_tptp

_BINARIES = {"vampire": ["vampire"], "e": ["eprover", "E"]}


def atp_backend(prover: str = "vampire", timeout_ms: int = 5000):
    """OPT-IN first-order ATP backend. `prover` ∈ {'vampire','e'}. Returns `prove(conj)` with .backend_name=prover."""
    prover = prover.lower()
    if prover not in _BINARIES:
        raise ValueError("prover must be 'vampire' or 'e'")
    timeout_s = max(0.1, timeout_ms / 1000.0)

    def prove(conj):
        try:
            tptp = ast_to_tptp(conj.claim_expr, conj.lhs, conj.rhs, conj.hypotheses, conj.variables, conj.domain)
        except Exception as exc:
            return "TOOL_LIMIT_UNKNOWN", None, f"could not compile the claim to TPTP: {exc}"
        binary = next((which(b) for b in _BINARIES[prover] if which(b)), None)
        if binary is None:
            names = " / ".join(_BINARIES[prover])
            return "TOOL_UNAVAILABLE", None, (f"{prover} not installed ({names} not on PATH). TPTP was generated "
                                              f"(see detail).\n{tptp}")
        if prover == "vampire":
            argv = [binary, "--mode", "casc", "--time_limit", str(int(timeout_s)), "--input_syntax", "tptp"]
        else:  # E
            argv = [binary, "--auto", "--tptp3-format", f"--cpu-limit={int(timeout_s)}"]
        code, out, err, timed_out = run_tool(argv, stdin_text=tptp, timeout_s=timeout_s + 2)
        text = (out + "\n" + err)
        if timed_out:
            return "TOOL_LIMIT_UNKNOWN", None, f"{prover} timed out after {timeout_s}s"
        # SZS status is the machine-readable verdict shared by Vampire and E
        if "SZS status Theorem" in text or "Refutation found" in text or "Proof found" in text:
            return "FORMALLY_PROVED", None, f"{prover}: SZS status Theorem (negation refuted) → proved."
        if "SZS status CounterSatisfiable" in text or "SZS status Satisfiable" in text:
            return "FORMALLY_DISPROVED", None, f"{prover}: SZS status CounterSatisfiable → the goal is not valid."
        return "TOOL_LIMIT_UNKNOWN", None, f"{prover} did not decide (SZS status GaveUp/Unknown/Timeout)."

    prove.backend_name = prover
    return prove
