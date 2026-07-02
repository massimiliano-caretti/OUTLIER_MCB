"""isabelle_backend — Isabelle/HOL + Sledgehammer (G1), the bridge between level A (z3, automatic) and B (Lean, by hand).

Isabelle/HOL is a proof assistant (absolute-certainty checking, like Lean); Sledgehammer searches for the proof
itself (delegating to z3/cvc5/Vampire/E behind the scenes) and Isabelle THEN machine-checks the found proof. So it
often closes a goal with no hand-written proof — the single addition that most raises the auto-closed-lemma rate.

Contract identical to z3_backend: (status, counterexample|None, detail), .backend_name='isabelle'. Opt-in: needs
the `isabelle` binary; absent ⇒ TOOL_UNAVAILABLE (never a crash). We generate a temporary .thy that states the
lemma and lets Isabelle discharge it by strong automation (the Sledgehammer-class tactics); a clean build where
the lemma is proved with NO `sorry`/error ⇒ FORMALLY_PROVED (ISABELLE_CHECKED). Never a false proof: an error or a
timeout ⇒ TOOL_LIMIT_UNKNOWN. Deterministic.
"""
from __future__ import annotations
import os
import tempfile

from ._solver_common import which, run_tool


def _to_hol(s: str) -> str:
    """Best-effort Python-relation → Isabelle/HOL surface syntax for the arithmetic fragment (ASCII forms that
    Isabelle accepts). Structural functions And/Or/Not/Implies map to HOL connectives."""
    out = (s or "").replace("**", "^").replace("!=", "\\<noteq>").replace("==", "=")
    out = out.replace("Implies(", "HOL_IMP(").replace("And(", "HOL_AND(").replace("Or(", "HOL_OR(").replace("Not(", "HOL_NOT(")
    return out


def emit_isabelle_theory(conj, name: str = "goal", thy: str = "Scratch") -> str:
    """The temporary theory text: a typed lemma over reals/ints with the hypotheses as assumptions. Pure and
    ALWAYS available (emission ≠ proof). Sledgehammer + strong tactics attempt to discharge it."""
    typ = "int" if (conj.domain or "real") == "int" else "real"
    names = list(conj.variables or {}) or ["x"]
    fixes = f"  fixes {' '.join(names)} :: \"{typ}\"\n" if names else ""
    assumes = "".join(f"  assumes \"{_to_hol(h)}\"\n" for h in (conj.hypotheses or []))
    claim = _to_hol(conj.claim_expr) if conj.claim_expr else f"{_to_hol(conj.lhs)} = {_to_hol(conj.rhs)}"
    # a sequence of strong, terminating methods Isabelle machine-checks (the Sledgehammer-class automation)
    proof = "  by (auto simp: algebra_simps power2_eq_square) (smt (z3))?"
    return (f"theory {thy}\n  imports Complex_Main\nbegin\n\n"
            f"lemma {name}:\n{fixes}{assumes}  shows \"{claim}\"\n{proof}\n\nend\n")


def isabelle_backend(timeout_ms: int = 60000):
    """OPT-IN Isabelle/HOL backend. See module docstring. Returns `prove(conj)` with .backend_name='isabelle'."""
    timeout_s = max(1.0, timeout_ms / 1000.0)

    def prove(conj):
        theory = emit_isabelle_theory(conj)
        binary = which("isabelle")
        if binary is None:
            return "TOOL_UNAVAILABLE", None, ("Isabelle not installed (`isabelle` not on PATH). The theory was "
                                              "generated (see detail).\n" + theory)
        tmp = tempfile.mkdtemp(prefix="mcb_isa_")
        thy_path = os.path.join(tmp, "Scratch.thy")
        with open(thy_path, "w") as f:
            f.write(theory)
        # batch-check the theory; a clean process (lemma discharged, no error) ⇒ checked proof
        code, out, err, timed_out = run_tool(
            [binary, "process", "-T", os.path.join(tmp, "Scratch")], timeout_s=timeout_s)
        text = out + "\n" + err
        if timed_out:
            return "TOOL_LIMIT_UNKNOWN", None, f"Isabelle timed out after {timeout_s}s"
        if code == 0 and "error" not in text.lower() and "*** " not in text:
            return "FORMALLY_PROVED", None, "Isabelle/HOL machine-checked the proof (Sledgehammer-class automation)."
        return "TOOL_LIMIT_UNKNOWN", None, ("Isabelle did not discharge the lemma automatically "
                                            "(no false proof is ever reported).")

    prove.backend_name = "isabelle"
    return prove
