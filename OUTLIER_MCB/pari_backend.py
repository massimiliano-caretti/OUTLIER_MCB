"""pari_backend — PARI/GP, the number-theory CAS (G2).

z3/Lean DECIDE and VERIFY but do not COMPUTE; number-theory problems are computational first (primes,
factorisation, L-functions). PARI/GP gives strong COMPUTATIONAL certificates on the `number_theory` pack's domain:
it EXHAUSTIVELY evaluates a claim over a FINITE integer box (forprime/isprime/…) — a real proof of THAT finite
domain, mapped to NUMERIC_VERIFIED. It is also a discovery engine (compute sequences → new sub-conjectures).

Contract identical to z3_backend: (status, counterexample|None, detail), .backend_name='pari'. Opt-in: needs the
`gp` binary; absent ⇒ TOOL_UNAVAILABLE (never a crash). CRITICAL HONESTY: a finite computation is NEVER a proof of
an infinite conjecture — an unbounded/too-large domain ⇒ TOOL_LIMIT_UNKNOWN, never FORMALLY_PROVED. Deterministic.
"""
from __future__ import annotations
import math
import re

from ._solver_common import which, run_tool, compile_expr_gp

_MAX_POINTS = 5_000_000   # a finite box larger than this is not enumerated → TOOL_LIMIT_UNKNOWN (honest: not a proof)


def _finite_int_box(variables):
    """Return [(name, lo, hi), …] for a finite integer box, or None if any range is unbounded/empty/too large."""
    box, total = [], 1
    for n, rng in (variables or {}).items():
        try:
            lo, hi = rng
        except Exception:
            return None
        if lo is None or hi is None or math.isinf(lo) or math.isinf(hi):
            return None
        lo, hi = int(math.ceil(lo)), int(math.floor(hi))
        if hi < lo:
            return None
        box.append((n, lo, hi))
        total *= (hi - lo + 1)
        if total > _MAX_POINTS:
            return None
    return box or None


def _gp_script(box, claim_gp, hyp_gps):
    """A GP program that scans the finite box, skips points failing the hypotheses, and prints the FIRST
    counterexample (`CE n=…`) or `ALL_HOLD` if the claim holds everywhere. Deterministic (lexicographic scan)."""
    guard = " && ".join(hyp_gps) if hyp_gps else "1"
    lines = ["found = 0;"]
    indent = ""
    for (n, lo, hi) in box:
        lines.append(f"{indent}for({n}={lo}, {hi},")
        indent += "  "
    assign = ", ".join(f'"{n}=", {n}' for (n, _, _) in box)
    lines.append(f'{indent}if(({guard}) && !({claim_gp}), print("CE ", {assign}); found=1; break({len(box)}))')
    for _ in box:
        indent = indent[:-2]
        lines.append(f"{indent})")
    lines.append('if(found==0, print("ALL_HOLD"))')
    return "\n".join(lines) + "\nquit\n"


def pari_backend(timeout_ms: int = 5000):
    """OPT-IN PARI/GP backend for FINITE number-theory claims. Returns `prove(conj)` with .backend_name='pari'."""
    timeout_s = max(0.1, timeout_ms / 1000.0)

    def prove(conj):
        box = _finite_int_box(conj.variables)
        if box is None:
            return "TOOL_LIMIT_UNKNOWN", None, ("PARI computes over a FINITE integer box only; this domain is "
                                               "unbounded/empty/too large — a finite computation is NOT a proof of "
                                               "an infinite conjecture, so this stays UNKNOWN (never PROVED).")
        try:
            claim_gp = compile_expr_gp(conj.claim_expr) if conj.claim_expr else \
                f"({compile_expr_gp(conj.lhs)} == {compile_expr_gp(conj.rhs)})"
            hyp_gps = [compile_expr_gp(h) for h in (conj.hypotheses or [])]
        except Exception as exc:
            return "TOOL_LIMIT_UNKNOWN", None, f"could not compile the claim to GP: {exc}"
        script = _gp_script(box, claim_gp, hyp_gps)
        binary = which("gp")
        if binary is None:
            return "TOOL_UNAVAILABLE", None, ("PARI/GP not installed (`gp` not on PATH; e.g. `apt install pari-gp`). "
                                              "The GP program was generated (see detail).\n" + script)
        code, out, err, timed_out = run_tool([binary, "-q", "--default", "parisize=64M"],
                                             stdin_text=script, timeout_s=timeout_s)
        if timed_out:
            return "TOOL_LIMIT_UNKNOWN", None, f"gp timed out after {timeout_s}s on a finite box"
        if "ALL_HOLD" in out:
            npts = 1
            for (_, lo, hi) in box:
                npts *= (hi - lo + 1)
            return "FORMALLY_PROVED", None, f"PARI/GP: the claim held over all {npts} finite point(s) — a computational proof of THIS finite domain."
        m = re.search(r"CE\s+(.*)", out)
        if m:
            ce = {}
            for part in m.group(1).split(", "):
                if "=" in part:
                    k, v = part.split("=", 1)
                    ce[k.strip()] = v.strip()
            return "FORMALLY_DISPROVED", ce or None, f"PARI/GP found a counterexample in the finite box: {m.group(1).strip()}"
        return "TOOL_LIMIT_UNKNOWN", None, f"gp produced no verdict (stdout: {out[:120]!r}, err: {err[:120]!r})"

    prove.backend_name = "pari"
    return prove
