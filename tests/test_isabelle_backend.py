"""G1 — Isabelle/HOL + Sledgehammer. Theory generation tested without the binary; the checked-proof path skips."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import OUTLIER_MCB as g
from OUTLIER_MCB._solver_common import which


def test_theory_generation_is_well_formed_without_the_binary():
    conj = g.Conjecture("AM-GM", claim_expr="x**2 + y**2 >= 2*x*y", variables={"x": (-9, 9), "y": (-9, 9)})
    thy = g.emit_isabelle_theory(conj)
    assert thy.startswith("theory Scratch") and "imports Complex_Main" in thy and thy.rstrip().endswith("end")
    assert "lemma goal:" in thy and 'fixes x y :: "real"' in thy
    assert "x^2 + y^2 >= 2*x*y" in thy                              # ** → ^, claim present
    with_hyp = g.emit_isabelle_theory(g.Conjecture("h", claim_expr="x > 0", variables={"x": (0, 9)}, hypotheses=["x >= 1"]))
    assert 'assumes "x >= 1"' in with_hyp


def test_isabelle_absent_is_tool_unavailable():
    conj = g.Conjecture("AM-GM", claim_expr="x**2 + y**2 >= 2*x*y", variables={"x": (-5, 5), "y": (-5, 5)})
    st, ce, detail = g.isabelle_backend()(conj)
    if which("isabelle") is None:
        assert st == "TOOL_UNAVAILABLE" and "theory Scratch" in detail   # graceful, theory in detail
    else:
        assert st in ("FORMALLY_PROVED", "TOOL_LIMIT_UNKNOWN")           # never a false proof


def test_isabelle_false_claim_not_proved():
    if which("isabelle") is None:
        pytest.skip("isabelle not installed")
    false_conj = g.Conjecture("false", claim_expr="x*x < 0", variables={"x": (-5, 5)})
    st, ce, detail = g.isabelle_backend()(false_conj)
    assert st != "FORMALLY_PROVED"                                  # negative control
