"""G4 — Vampire/E ATP backend (TPTP). TPTP compilation tested without the binary; proof path skips if absent."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import OUTLIER_MCB as g
from OUTLIER_MCB._solver_common import which, ast_to_tptp


def test_tptp_compiler_is_correct_without_the_binary():
    t = ast_to_tptp("x**2 + y**2 >= 2*x*y", "", "", [], {"x": (-9, 9), "y": (-9, 9)}, "real")
    assert t.startswith("tff(goal, conjecture, ! [V_X:$real,V_Y:$real]:")
    assert "$greatereq($sum($product(V_X,V_X),$product(V_Y,V_Y)),$product($product(2,V_X),V_Y))" in t
    ti = ast_to_tptp("x >= 0", "", "", ["x > 0"], {"x": (0, 9)}, "int")
    assert ":$int" in ti and "=>" in ti                            # hypothesis becomes the antecedent


def test_atp_prover_name_validation():
    with pytest.raises(ValueError):
        g.atp_backend("not_a_prover")


@pytest.mark.parametrize("prover,binaries", [("vampire", ["vampire"]), ("e", ["eprover", "E"])])
def test_atp_absent_is_tool_unavailable_or_proves(prover, binaries):
    conj = g.Conjecture("AM-GM", claim_expr="x**2 + y**2 >= 2*x*y", variables={"x": (-5, 5), "y": (-5, 5)})
    st, ce, detail = g.atp_backend(prover)(conj)
    if not any(which(b) for b in binaries):
        assert st == "TOOL_UNAVAILABLE" and "tff(goal" in detail    # graceful, TPTP in detail
    else:
        assert st in ("FORMALLY_PROVED", "TOOL_LIMIT_UNKNOWN")


def test_atp_false_claim_not_proved():
    if not any(which(b) for b in ("vampire", "eprover", "E")):
        pytest.skip("no ATP binary installed")
    false_conj = g.Conjecture("false", claim_expr="x*x < 0", variables={"x": (-5, 5)})
    st, ce, detail = g.atp_backend("vampire" if which("vampire") else "e")(false_conj)
    assert st != "FORMALLY_PROVED"                                  # negative control
