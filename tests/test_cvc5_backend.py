"""G3 — cvc5 SMT backend. Compiler correctness is tested WITHOUT the binary; the proof path skips if cvc5 absent."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import OUTLIER_MCB as g
from OUTLIER_MCB._solver_common import which, ast_to_smtlib, compile_expr_smtlib


def test_smtlib_compiler_is_correct_without_the_binary():
    assert compile_expr_smtlib("x**2 + y**2 >= 2*x*y", ["x", "y"]) == "(>= (+ (* x x) (* y y)) (* (* 2 x) y))"
    assert compile_expr_smtlib("Implies(And(x>0, y>0), x+y>0)", ["x", "y"]) == "(=> (and (> x 0) (> y 0)) (> (+ x y) 0))"
    smt = ast_to_smtlib("x >= 0", "", "", ["x > 0"], {"x": (0, 9)}, "int")
    assert "(declare-const x Int)" in smt and "(assert (not (>= x 0)))" in smt and "(check-sat)" in smt


def test_unknown_variable_degrades_not_crashes():
    st, ce, detail = g.cvc5_backend()(g.Conjecture("bad", claim_expr="q > 0", variables={"x": (0, 1)}))
    # 'q' is not a declared variable → the compiler refuses → TOOL_LIMIT_UNKNOWN (never a wrong SMT term, never a crash)
    assert st in ("TOOL_LIMIT_UNKNOWN", "TOOL_UNAVAILABLE")


def test_cvc5_absent_is_tool_unavailable_or_proves():
    conj = g.Conjecture("AM-GM", claim_expr="x**2 + y**2 >= 2*x*y", variables={"x": (-5, 5), "y": (-5, 5)})
    st, ce, detail = g.cvc5_backend()(conj)
    if which("cvc5") is None:
        try:
            import cvc5  # noqa: F401
            have_pkg = True
        except ImportError:
            have_pkg = False
        if not have_pkg:
            assert st == "TOOL_UNAVAILABLE" and "cvc5" in detail    # graceful, SMT-LIB in detail
            return
    assert st in ("FORMALLY_PROVED", "TOOL_LIMIT_UNKNOWN")          # a real cvc5 must not misreport a false proof


def test_cvc5_false_claim_not_proved():
    if which("cvc5") is None:
        pytest.skip("cvc5 binary not installed")
    false_conj = g.Conjecture("false", claim_expr="x*x < 0", variables={"x": (-5, 5)})   # never true
    st, ce, detail = g.cvc5_backend()(false_conj)
    assert st != "FORMALLY_PROVED"                                  # negative control: a falsity is never 'proved'
