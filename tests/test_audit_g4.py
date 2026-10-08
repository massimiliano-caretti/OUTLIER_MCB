"""Regression tests for the G4 audit (math discovery / solver backends / oracle miner / evaluators).

Each test pins a CONFIRMED defect: a false certificate, a malformed counterexample, an unsafe eval, a crash on
degenerate data, a hang, or a dishonest metric. Optional tools (z3, sympy) are skipped when absent.
"""
import importlib
import random
import time

import pytest

import OUTLIER_MCB.math_discovery as md
import OUTLIER_MCB.oracle_miner as om
from OUTLIER_MCB.math_discovery import Conjecture, settle_lemma

cvc5_mod = importlib.import_module("OUTLIER_MCB.cvc5_backend")
pari_mod = importlib.import_module("OUTLIER_MCB.pari_backend")
solver_common = importlib.import_module("OUTLIER_MCB._solver_common")
conj_search = importlib.import_module("OUTLIER_MCB.conjecture_search")


def _has(mod):
    try:
        importlib.import_module(mod)
        return True
    except ImportError:
        return False


# ── math_discovery ────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.skipif(not _has("z3"), reason="z3 not installed")
def test_z3_non_boolean_claim_is_unknown_not_a_crash():
    st, ce, detail = md.z3_backend()(Conjecture("s", claim_expr="x + 1", variables={"x": (0, 1)}))
    assert st == "TOOL_LIMIT_UNKNOWN" and ce is None


@pytest.mark.skipif(not _has("z3"), reason="z3 not installed")
def test_z3_eval_rejects_attribute_escape():
    evil = Conjecture("s", claim_expr="().__class__.__mro__[1].__subclasses__() == 0", variables={"x": (0, 1)})
    st, ce, detail = md.z3_backend()(evil)
    assert st == "TOOL_LIMIT_UNKNOWN" and "could not parse" in detail
    ok = Conjecture("s", claim_expr="Implies(x > 0, Abs(x) == x)", variables={"x": (0, 1)})
    assert md.z3_backend()(ok)[0] == "FORMALLY_PROVED"


def test_real_domain_lemma_is_not_certified_by_integer_points_only():
    # x**2 >= x holds at the integers 0 and 1 but FAILS at 1/2: it must not be NUMERIC_VERIFIED over the reals.
    cert = settle_lemma(Conjecture("x^2 >= x", claim_expr="x**2 >= x", variables={"x": (0, 1)}))
    assert cert.status == "NUMERIC_REFUTED" and not cert.certified
    assert cert.counterexample is not None
    # the same claim over the INTEGERS is genuinely verified
    assert settle_lemma(Conjecture("x^2 >= x", claim_expr="x**2 >= x", variables={"x": (0, 1)},
                                   domain="int")).status == "NUMERIC_VERIFIED"
    # a true real claim still passes, with an honest caveat
    good = settle_lemma(Conjecture("x^2 >= 0", claim_expr="x*x >= 0", variables={"x": (-4, 4)}))
    assert good.status == "NUMERIC_VERIFIED" and "not a proof over the reals" in good.detail


@pytest.mark.skipif(not _has("sympy"), reason="sympy not installed")
def test_float_roundoff_is_not_a_counterexample_to_a_true_identity():
    r = md.investigate_conjecture(Conjecture("t", lhs="sqrt(x**2+2*x+1)", rhs="x+1",
                                             variables={"x": (1e9, 1e10)}))
    assert r.status != "COUNTEREXAMPLE_FOUND"


@pytest.mark.skipif(not _has("sympy"), reason="sympy not installed")
def test_undeclared_symbol_is_not_reported_as_a_counterexample():
    r = md.investigate_conjecture(Conjecture("t", lhs="sqrt(y**2)", rhs="y", variables={"x": (1, 2)}))
    assert r.status != "COUNTEREXAMPLE_FOUND"


# ── oracle_miner ──────────────────────────────────────────────────────────────────────────────────────────
def test_asymptotic_and_ratio_do_not_overflow_on_superexponential_growth():
    f = lambda n: 2 ** (n ** 3)          # noqa: E731
    om.guess_asymptotic(f)               # used to raise OverflowError in math.exp
    sparks = om.mine_invariants(f, n_terms=20)
    assert sparks.growth_ratio is None   # the ratio exceeds float range → no finite spark, no crash


def test_polynomial_recurrence_does_not_hang_on_huge_entries():
    t0 = time.time()
    assert om.guess_polynomial_recurrence(lambda n: 2 ** (n ** 3), max_order=4, n_terms=40) is None
    assert time.time() - t0 < 30         # was > 300 s (exact Fraction elimination on 2^64000-sized entries)


def test_modular_rank_prefilter_keeps_real_nullspaces():
    from fractions import Fraction as F
    rows = [[F(1), F(2), F(3)], [F(2), F(4), F(6)], [F(1), F(0), F(1)], [F(3), F(2), F(5)]]
    vec = om._nullspace_vec(rows)
    assert vec is not None and all(sum(a * b for a, b in zip(r, vec)) == 0 for r in rows)
    assert om._nullspace_vec([[F(1), F(0)], [F(0), F(1)], [F(1), F(1)]]) is None
    # Somos-4 is still discovered (the pre-filter only rejects provably trivial nullspaces)
    s = [1, 1, 1, 1]
    for n in range(4, 40):
        s.append((s[n - 1] * s[n - 3] + s[n - 2] ** 2) // s[n - 4])
    assert om.guess_polynomial_recurrence(s, max_order=4, n_terms=40) is not None


# ── solver backends ───────────────────────────────────────────────────────────────────────────────────────
def test_cvc5_model_parser_handles_negative_and_rational_values():
    out = ("sat\n(\n(define-fun x () Real (- 1.0))\n(define-fun y () Real (/ 1 2))\n"
           "(define-fun z () Int 7)\n(define-fun w () Real (- (/ 3 4)))\n)")
    assert cvc5_mod._parse_model(out, ["x", "y", "z", "w"]) == {"x": "-1", "y": "1/2", "z": "7", "w": "-3/4"}


def test_pari_counterexample_print_separates_variables():
    script = pari_mod._gp_script([("x", 0, 2), ("y", 0, 2)], "(x < y)", [])
    assert '"x=", x, ", ", "y=", y' in script


def test_pari_refuses_real_domain_claims(monkeypatch):
    monkeypatch.setattr(pari_mod, "which", lambda name: "/usr/bin/gp")
    monkeypatch.setattr(pari_mod, "run_tool", lambda *a, **k: (0, "ALL_HOLD\n", "", False))
    real = Conjecture("x^2 >= x", claim_expr="x^2 >= x", variables={"x": (0, 1)})
    st, _ce, _d = pari_mod.pari_backend()(real)
    assert st != "FORMALLY_PROVED"
    integer = Conjecture("x^2 >= x", claim_expr="x**2 >= x", variables={"x": (0, 1)}, domain="int")
    assert pari_mod.pari_backend()(integer)[0] == "FORMALLY_PROVED"


def test_gp_compiler_blocks_shell_and_io_functions():
    for evil in ("system(Str(Strchr(108)))", "extern(1)", "readstr(1)", "write(1, 2)"):
        with pytest.raises(ValueError):
            solver_common.compile_expr_gp(evil)
    assert solver_common.compile_expr_gp("isprime(n)") == "isprime(n)"


def test_symmetry_conjecture_swaps_whole_identifiers_only():
    a = conj_search.mine_conjectures_from_formula("abs(a-b)", {"a": (0, 1), "b": (0, 1)})[0]
    assert a.claim_expr == "(abs(a-b)) == (abs(b-a))"
    b = conj_search.mine_conjectures_from_formula("x1*x2 + x10", {"x1": (0, 1), "x10": (0, 1), "x2": (0, 1)})[0]
    assert b.claim_expr == "(x1*x2 + x10) == (x10*x2 + x1)"


# ── evaluators / economy / discovery ──────────────────────────────────────────────────────────────────────
def test_hidden_evaluator_without_hidden_cases_requires_public_pass():
    from OUTLIER_MCB.evaluators import HiddenEvaluator
    assert HiddenEvaluator(lambda c, case: False, public_cases=[1, 2, 3]).evaluate("c").passed is False
    assert HiddenEvaluator(lambda c, case: True, public_cases=[1, 2, 3]).evaluate("c").passed is True


def test_verification_economy_charges_for_non_confirming_proxies():
    from OUTLIER_MCB.verification_economy import VerificationEconomy
    ve = VerificationEconomy(real=lambda c: c < 5, real_cost=1.0).add_proxy(lambda c: c < 5, cost=0.6, name="p")
    ve.calibrate(list(range(10)))
    out = ve.cost_saving(list(range(10)))
    # 5 cheap confirms at 0.6 + 5 escalations at (0.6 proxy + 1.0 real) = 11.0 > baseline 10.0 → a LOSS
    assert out["economy_cost"] == pytest.approx(11.0) and out["saving"] < 0


def test_least_squares_is_scale_invariant():
    from OUTLIER_MCB.evaluators import least_squares, Term
    rng = random.Random(0)
    X = [[rng.uniform(1, 2) * 1e-6, rng.uniform(1, 2) * 1e-6] for _ in range(50)]
    y = [3.0e6 * r[0] for r in X]
    terms = [Term("1", lambda r: 1.0), Term("x0", lambda r: r[0]), Term("x1", lambda r: r[1])]
    f = least_squares(X, y, terms)
    assert f.coeffs[1] == pytest.approx(3.0e6, rel=1e-4)
    assert max(abs(f.predict(r) - v) for r, v in zip(X, y)) < 1e-6


def test_certify_reduction_survives_a_transform_that_fails_on_the_control():
    from OUTLIER_MCB.autonomous_discovery import certify_reduction

    def transform(b):
        if b[0] > b[-1]:
            raise ValueError("only increasing inputs")
        return [2 * x for x in b]
    a = [2 * i for i in range(1, 11)]
    res = certify_reduction(a, list(range(1, 11)), transform)
    assert res.state == "REDUCTION_ESTABLISHED"
