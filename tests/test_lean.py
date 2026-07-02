"""test_lean — emit a FORMAL Lean statement for a conjecture (and let Lean check it if installed).

Emission is pure, zero-dependency and ALWAYS available — it is a formal SKETCH (`sorry`), NOT a proof.
Only a Lean-checked, sorry-free proof is FORMALLY_PROVED; without Lean the backend is TOOL_UNAVAILABLE
and never crashes. Robust whether or not Lean is installed.
"""
import shutil

import OUTLIER_MCB as gsl


def test_lean_emit_translates_to_lean_syntax():
    conj = gsl.Conjecture("AM-GM", claim_expr="x**2 + y**2 >= 2*x*y", variables={"x": (-5.0, 5.0), "y": (-5.0, 5.0)})
    src = gsl.lean_emit(conj)
    assert "import Mathlib" in src and "theorem conjecture" in src
    assert "(x y : ℝ)" in src
    assert "x^2 + y^2 ≥ 2*x*y" in src                     # ** → ^, >= → ≥
    assert ":= sorry" in src                              # emission is a SKETCH, not a proof


def test_lean_emit_identity_and_hypotheses_and_int():
    ident = gsl.lean_emit(gsl.Conjecture("id", lhs="(x+1)**2", rhs="x**2+2*x+1", variables={"x": (-3.0, 3.0)}))
    assert "(x+1)^2 = x^2+2*x+1" in ident
    hyp = gsl.lean_emit(gsl.Conjecture("pos", claim_expr="x + 1/x >= 2", hypotheses=["x > 0"],
                                       variables={"x": (0.1, 9.0)}))
    assert "(h0 : x > 0)" in hyp
    intc = gsl.lean_emit(gsl.Conjecture("ints", claim_expr="x + y == y + x", domain="int",
                                        variables={"x": (-3.0, 3.0), "y": (-3.0, 3.0)}))
    assert "(x y : ℤ)" in intc and "x + y = y + x" in intc


def test_lean_backend_is_callable_and_honest():
    conj = gsl.Conjecture("AM-GM", claim_expr="x**2 + y**2 >= 2*x*y", variables={"x": (-5.0, 5.0), "y": (-5.0, 5.0)})
    res = gsl.investigate_conjecture(conj, backend=gsl.lean_backend())
    assert res.proof is not None and res.proof.method == "lean"
    if shutil.which("lean") is None:
        assert res.status == "SKETCH" and res.proof.status == "TOOL_UNAVAILABLE"
        assert "import Mathlib" in res.proof.detail        # the emitted statement is still handed back
    else:
        assert res.status in ("FORMALLY_PROVED", "LEAN_EMITTED")


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
