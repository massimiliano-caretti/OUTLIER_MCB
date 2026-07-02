"""Agnostic tests for guess_polynomial_recurrence — the non-linear (Somos-like) mining capability.
Domain-agnostic: operates on any integer oracle. Positive control = Somos-4; negative control = primes."""
from OUTLIER_MCB import oracle_miner as om


def _somos4(n_terms):
    s = [1, 1, 1, 1]
    for n in range(4, n_terms):
        s.append((s[n - 1] * s[n - 3] + s[n - 2] ** 2) // s[n - 4])
    return s


def test_finds_somos4_nonlinear_law():
    # POSITIVE CONTROL: the quadratic Somos-4 law must be discovered exactly.
    rec = om.guess_polynomial_recurrence(_somos4(40), max_order=4, max_total_degree=2, max_n_degree=0, n_terms=40)
    assert rec is not None
    assert rec.order == 4 and rec.total_degree == 2
    assert rec.verified_on > 0                      # held-out verified, not fitted-only


def test_negative_control_primes_no_false_law():
    # NEGATIVE CONTROL: primes admit no low-complexity non-linear law → no hallucinated relation.
    primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79, 83, 89, 97]
    rec = om.guess_polynomial_recurrence(primes, max_order=3, max_total_degree=2, max_n_degree=1, n_terms=25)
    assert rec is None


def test_shuffle_control_breaks_the_law():
    # NEGATIVE CONTROL (perturbation): a corrupted Somos sequence must NOT satisfy the law.
    s = _somos4(40)
    s[20] += 1                                       # break one term
    rec = om.guess_polynomial_recurrence(s, max_order=4, max_total_degree=2, max_n_degree=0, n_terms=40)
    assert rec is None or rec.verified_on == 0 or not (rec.order == 4)


def _catalan(n_terms):
    from math import comb
    return [comb(2 * n, n) // (n + 1) for n in range(1, n_terms + 1)]


def test_finds_catalan_algebraic_gf():
    # POSITIVE CONTROL: the Catalan GF is algebraic — the guesser must find a degree-2 equation.
    r = om.guess_algebraic_gf(_catalan(20), max_gf_degree=2, max_x_degree=2, n_terms=20)
    assert r is not None
    assert r.gf_degree == 2 and r.verified_on > 0


def test_negative_control_primes_no_algebraic_gf():
    primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71]
    assert om.guess_algebraic_gf(primes, n_terms=20) is None
