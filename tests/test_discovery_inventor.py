"""The library as an INVENTOR-first discoverer (T1–T8): world-tests RED→GREEN with negative controls.

The message on success is a DISCOVERY, never a defence; honesty (no false PROVED, committed monotone) keeps the
discoveries real. Deterministic, zero-dep.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import OUTLIER_MCB as g


def _catalan(n):
    from math import comb
    return comb(2 * n, n) // (n + 1)


CATALAN = [_catalan(i) for i in range(18)]
PRIMES = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71]


# ── T1: the oracle INSPIRES (mines structure), and does not hallucinate on a non-holonomic sequence ──
def test_oracle_miner_rediscovers_catalan_recurrence():
    s = g.mine_invariants(CATALAN)
    assert s.holonomic is not None and s.holonomic.order == 1 and s.holonomic.verified_on >= 1   # verified on held-out


def test_oracle_miner_does_not_hallucinate_on_primes():
    s = g.mine_invariants(PRIMES)
    # NEGATIVE CONTROL: no false EXACT structure on a non-holonomic sequence (a banded asymptotic law may exist —
    # that is a real, honestly-approximate growth axis, not a hallucinated exact recurrence).
    assert s.holonomic is None and s.polynomial is None and s.closed_form is None and s.algebraic is None
    assert s.multiplicative is None and s.k_automatic is None
    assert not s.exact_structure_found and s.weak_structure_found
    assert s.discovery_rung == "WEAK_ASYMPTOTIC_BAND"


# ── T2: the primitive alphabet is a RATCHET — unreachable at depth 1, reachable at 2, then depth 1 after abstraction ──
def test_primitive_alphabet_grows_to_solve_what_base_cannot():
    squares = tuple(i * i for i in range(10))
    lib = g.PrimitiveLibrary()
    assert lib.search(squares, g.becomes_constant, max_depth=1) is None       # base alphabet cannot
    sol = lib.search(squares, g.becomes_constant, max_depth=2)
    assert sol is not None and sol.depth == 2                                  # a composite solves it
    lib.abstract(sol)
    assert lib.abstractions and lib.search(squares, g.becomes_constant, max_depth=1) is not None   # alphabet grew


# ── T4: PIVOT the solution type instead of stopping at CONJECTURE ──
def test_non_holonomic_pivots_instead_of_stopping():
    r = g.autonomous_discover("n-th prime", PRIMES)
    # pivoted to a real non-closed-form discovery (an asymptotic band if one fits, else the reproducing algorithm)
    assert r.state == "SOLVED" and r.form in ("ASYMPTOTIC_WITH_BAND", "ALGORITHM")
    assert r.pivots and "DISCOVERED" in r.message()               # the message is a discovery, not a defence
    # NEGATIVE CONTROL: with the creative pivot OFF it degrades to OPEN (the old refuter behaviour)
    r_off = g.autonomous_discover("n-th prime", PRIMES, allow_pivot=False)
    assert r_off.state == "OPEN"


def test_holonomic_is_solved_as_a_discovery_not_a_defence():
    r = g.autonomous_discover("Catalan", CATALAN)
    assert r.state == "SOLVED" and r.form == "HOLONOMIC_RECURRENCE"
    assert r.message().startswith("DISCOVERED") and "not claimed PROVED" in r.message()   # honest + celebratory


# ── T5: scratch sandbox allows a worsening detour; the committed record stays monotone ──
def test_scratch_detour_allows_worsening_but_committed_is_monotone():
    sf = g.ScratchFrontier(detour_budget=2)
    assert sf.explore(0.5) and sf.commit() and sf.committed == 0.5
    assert sf.explore(0.3, opens_new_region=True)                 # a WORSENING detour is allowed in the sandbox
    assert sf.scratch == 0.3 and sf.committed == 0.5              # committed did NOT regress
    assert sf.explore(0.9) and sf.commit() and sf.committed == 0.9   # the detour reached a better region → committed
    # NEGATIVE CONTROL: a worsening step with no detour budget and no new region is refused
    sf2 = g.ScratchFrontier(detour_budget=0)
    sf2.explore(0.5)
    assert not sf2.explore(0.2)


# ── T6: a discovered MECHANISM is validated by TRANSFER to sister landscapes, not self-vote ──
def test_mechanism_must_generalize_to_sister_landscapes():
    r = g.autonomous_discover("Catalan", CATALAN)
    assert r.generalized is True                                  # the recurrence reproduces fresh sister sequences


# ── T3: acquire NEW information unblocks a stall (more terms reveal the structure) ──
def test_acquire_new_information_extends_the_oracle():
    ext = g.acquire_new_information(_catalan, have=8, more=6)
    assert ext is not None and len(ext) == 14 and ext[:8] == CATALAN[:8]
    assert g.acquire_new_information([1, 2, 3], have=3) is None   # a finite oracle that cannot supply more


# ── T8: discover and CERTIFY a REDUCTION — a first-class result, distinct from PROVED and CONJECTURE ──
def test_reduction_is_discovered_and_certified_with_negative_control():
    # B(n) = Catalan; A(n) = 2*Catalan(n). The reduction A = 2·B is real and finitely checkable.
    A = [2 * c for c in CATALAN]
    red = g.certify_reduction(A, CATALAN, transform=(lambda b: [2 * x for x in b]), name="A = 2·B")
    assert red.state == "REDUCTION_ESTABLISHED" and "negative control" in red.certificate
    # NEGATIVE CONTROL: a WRONG transform does not certify a false reduction
    bad = g.certify_reduction(A, CATALAN, transform=(lambda b: [3 * x for x in b]))
    assert bad.state == "OPEN"


# ── extended representation spaces: the DEFAULT pipeline (not only a hand-tuned call) must reach them ──
def _somos4(n):
    s = [1, 1, 1, 1]
    for i in range(4, n):
        s.append((s[i - 1] * s[i - 3] + s[i - 2] ** 2) // s[i - 4])
    return s


def test_pipeline_discovers_somos_nonlinear_by_default():
    # the FIX: mine_invariants / autonomous_discover must find the non-linear Somos law with DEFAULT params,
    # not only a hand-tuned guess_polynomial_recurrence call.
    s = _somos4(40)
    assert g.mine_invariants(s).polynomial is not None
    r = g.autonomous_discover("Somos-4", s)
    assert r.state == "SOLVED" and r.form == "NONLINEAR_RECURRENCE" and "a(n+2)^2" in r.mechanism


def test_pipeline_discovers_polynomial_closed_form():
    cubic = [i ** 3 - 2 * i + 5 for i in range(16)]
    cf = g.mine_invariants(cubic).closed_form
    assert cf is not None and cf.degree == 3
    r = g.autonomous_discover("cubic", cubic)
    assert r.state == "SOLVED" and r.form == "CLOSED_FORM" and "n^3" in r.mechanism


def test_closed_form_negative_controls():
    # a non-polynomial sequence must yield NO false closed form (Catalan is holonomic, primes are neither)
    assert g.guess_polynomial_closed_form(CATALAN) is None
    assert g.guess_polynomial_closed_form(PRIMES) is None
    assert g.mine_invariants(CATALAN).holonomic is not None   # Catalan still solved (holonomic), not a fake closed form


def test_nonlinear_and_algebraic_do_not_hallucinate():
    # structureless / perturbed inputs must yield NO non-linear or algebraic law (negative controls)
    weird = [3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5, 8, 9, 7, 9, 3, 2, 3, 8, 4, 6, 2, 6, 4]
    assert g.guess_polynomial_recurrence(weird, max_order=4) is None
    assert g.guess_algebraic_gf(weird) is None
    s = _somos4(40)
    s[9] += 1                                                 # perturb one term → the law must break
    assert g.guess_polynomial_recurrence(s, max_order=4, n_terms=40) is None


# ── complementary axes (multiplicative / k-automatic / asymptotic) — orthogonal structure classes ──
def _phi(n):
    r, p, nn = n, 2, n
    while p * p <= nn:
        if nn % p == 0:
            while nn % p == 0:
                nn //= p
            r -= r // p
        p += 1
    if nn > 1:
        r -= r // nn
    return r


_PHI = [_phi(i) for i in range(1, 50)]
_THUE = [bin(i).count("1") % 2 for i in range(64)]
_PRIMES40 = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79, 83, 89, 97,
             101, 103, 107, 109, 113, 127, 131, 137, 139, 149, 151, 157, 163, 167, 173]


def test_axis1_multiplicative_structure_discovered():
    mu = g.mine_invariants(_PHI).multiplicative
    assert mu is not None                                     # Euler φ is multiplicative
    r = g.autonomous_discover("Euler phi", _PHI)
    assert r.state == "SOLVED" and r.form == "MULTIPLICATIVE"
    # NEGATIVE CONTROLS: primes and Fibonacci are NOT multiplicative
    assert g.mine_invariants(_PRIMES40).multiplicative is None
    assert g.mine_invariants([1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377]).multiplicative is None


def test_axis3_k_automatic_discovered_and_no_degenerate_law():
    ka = g.mine_invariants(_THUE).k_automatic
    assert ka is not None and ka.base == 2                    # Thue-Morse is 2-automatic
    assert ka.maps[0] == {0: 0, 1: 1} and ka.maps[1] == {0: 1, 1: 0}   # a(2n)=a(n), a(2n+1)=1-a(n)
    assert g.mine_invariants(_THUE).polynomial is None        # HONESTY: the trivial a(n)^2=a(n) is suppressed now
    assert g.mine_invariants(_PRIMES40).k_automatic is None   # NEGATIVE CONTROL


def test_axis2_asymptotic_band_fills_the_lattice_slot():
    asy = g.mine_invariants(_PRIMES40).asymptotic
    assert asy is not None and asy.band_lo <= asy.band_hi
    r = g.autonomous_discover("primes", _PRIMES40)
    assert r.state == "SOLVED" and r.form == "ASYMPTOTIC_WITH_BAND"   # a real growth law, not just 'run the algorithm'
    # NEGATIVE CONTROL: a bounded sequence has no growth law
    assert g.mine_invariants(_THUE).asymptotic is None


def test_new_axes_do_not_steal_exact_structure():
    # exact structure still wins over the softer axes (Catalan → holonomic, not multiplicative/asymptotic)
    r = g.mine_invariants([1, 1, 2, 5, 14, 42, 132, 429, 1430, 4862, 16796, 58786, 208012])
    assert r.holonomic is not None and r.multiplicative is None and r.asymptotic is None


# ── T7: the battery + ablation — discovery is the primary metric; every creative stage is load-bearing ──
def test_battery_discovers_and_ablation_shows_each_stage_matters():
    from evals.discovery_battery import run_ablation
    abl = run_ablation()
    assert abl["full"].ok and abl["full"].false_proved == 0
    assert abl["full"].discovered > abl["no_pivot (T4 off)"].discovered      # pivot is load-bearing
    assert abl["full"].discovered > abl["no_ratchet (T2 off)"].discovered    # the ratchet is load-bearing
