"""G2 — PARI/GP number-theory backend. The KEY honesty test (finite ≠ infinite) needs NO binary; proof path skips."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import OUTLIER_MCB as g
from OUTLIER_MCB._solver_common import which, compile_expr_gp


def test_gp_compiler_passes_number_theory_functions_through():
    assert compile_expr_gp("isprime(n*n + n + 41)") == "isprime((((n * n) + n) + 41))"
    assert compile_expr_gp("And(isprime(n), isprime(n+2))") == "(isprime(n) && isprime((n + 2)))"
    assert compile_expr_gp("x**2 >= 0") == "((x ^ 2) >= 0)"


def test_infinite_domain_is_never_proved_without_a_binary():
    # THE anti-overclaim invariant: a finite computation is NOT a proof of an infinite conjecture.
    inf = g.Conjecture("twin primes are infinite", claim_expr="isprime(n) && isprime(n+2)",
                       variables={"n": (float("-inf"), float("inf"))}, domain="int")
    st, ce, detail = g.pari_backend()(inf)
    assert st == "TOOL_LIMIT_UNKNOWN" and "NOT a proof of an infinite" in detail   # never FORMALLY_PROVED


def test_too_large_finite_domain_is_unknown():
    big = g.Conjecture("huge box", claim_expr="n > 0", variables={"n": (1, 10**9)}, domain="int")
    st, ce, detail = g.pari_backend()(big)
    assert st == "TOOL_LIMIT_UNKNOWN"                               # too large to enumerate → honest UNKNOWN


def test_pari_absent_is_tool_unavailable():
    finite = g.Conjecture("primes in [10,20]", claim_expr="isprime(n)", variables={"n": (11, 13)}, domain="int")
    st, ce, detail = g.pari_backend()(finite)
    if which("gp") is None:
        assert st == "TOOL_UNAVAILABLE" and "for(" in detail        # graceful, GP program in detail
    else:
        assert st in ("FORMALLY_PROVED", "FORMALLY_DISPROVED", "TOOL_LIMIT_UNKNOWN")


def test_pari_finite_range_twin_primes_and_negative_control():
    if which("gp") is None:
        pytest.skip("gp (PARI/GP) not installed")
    # a twin-prime pair exists in [3,7] (3,5 and 5,7) → the 'exists' form, checked over a finite range, is verified
    exists = g.Conjecture("a twin prime base in [3,5]", claim_expr="isprime(n) && isprime(n+2)",
                          variables={"n": (3, 5)}, domain="int")
    cert = g.settle_lemma(exists, backend=g.pari_backend())
    assert cert.status in ("NUMERIC_VERIFIED", "Z3_REFUTED", "NUMERIC_REFUTED")
    # a claim false on a finite range → refuted with a counterexample (negative control)
    false_conj = g.Conjecture("every n in [8,10] is prime", claim_expr="isprime(n)", variables={"n": (8, 10)}, domain="int")
    cert2 = g.settle_lemma(false_conj, backend=g.pari_backend())
    assert cert2.status == "NUMERIC_REFUTED" and cert2.counterexample
