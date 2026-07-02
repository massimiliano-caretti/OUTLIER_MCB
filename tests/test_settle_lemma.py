"""F4 world-test — external settlement of a partial LEMMA (never the parent conjecture).

RED→GREEN: a true decidable lemma → NUMERIC_VERIFIED certificate, and a FrontierLedger advance is accepted;
a false lemma → NUMERIC_REFUTED with a counterexample, and the frontier does NOT move (the certificate is not
'certified'). Zero-dep (exhaustive numeric), deterministic. The mapping from an opt-in prover backend is also
checked with a fake backend (no z3 needed).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import OUTLIER_MCB as gsl
from OUTLIER_MCB.math_discovery import Conjecture, settle_lemma


def test_true_lemma_is_numerically_verified_and_advances_frontier():
    lemma = Conjecture(statement="n^2 >= n for integers 1..50", variables={"n": (1, 50)}, domain="int")
    cert = settle_lemma(lemma, predicate=lambda n: n * n >= n)
    assert cert.status == "NUMERIC_VERIFIED" and cert.certified

    led = gsl.FrontierLedger()
    r = led.claim("toy_problem", "bound", 50, "increase", cert)     # an external certificate → accepted
    assert r.accepted and led.best("toy_problem", "bound") == 50


def test_false_lemma_is_refuted_and_frontier_unchanged():
    lemma = Conjecture(statement="n^2 < 100 for integers 1..50", variables={"n": (1, 50)}, domain="int")
    cert = settle_lemma(lemma, predicate=lambda n: n * n < 100)
    assert cert.status == "NUMERIC_REFUTED" and not cert.certified
    assert cert.counterexample is not None and cert.counterexample["n"] >= 10

    led = gsl.FrontierLedger()
    r = led.claim("toy_problem", "bound", 999, "increase", cert)    # not certified → rejected
    assert not r.accepted and led.best("toy_problem", "bound") is None


def test_no_decidable_path_is_unknown_timeout():
    lemma = Conjecture(statement="undecidable here", variables={}, domain="int")
    cert = settle_lemma(lemma, predicate=None)
    assert cert.status == "UNKNOWN_TIMEOUT" and not cert.certified


def test_domain_too_large_is_not_falsely_certified():
    lemma = Conjecture(statement="huge box", variables={"a": (1, 10**4), "b": (1, 10**4)}, domain="int")
    cert = settle_lemma(lemma, predicate=lambda a, b: True)         # 10^8 points → cannot settle exhaustively
    assert cert.status == "UNKNOWN_TIMEOUT" and not cert.certified


def test_backend_mapping_with_a_fake_prover():
    def proved_backend(conj):
        return "FORMALLY_PROVED", None, "fake prover accepted it"
    proved_backend.backend_name = "z3"
    assert settle_lemma(Conjecture(statement="x"), backend=proved_backend).status == "Z3_PROVED"

    def disproved_backend(conj):
        return "FORMALLY_DISPROVED", {"x": "3"}, "fake counterexample"
    disproved_backend.backend_name = "z3"
    cert = settle_lemma(Conjecture(statement="x"), backend=disproved_backend)
    assert cert.status == "Z3_REFUTED" and cert.counterexample == {"x": "3"}

    def lean_proved(conj):
        return "FORMALLY_PROVED", None, "lean checked"
    lean_proved.backend_name = "lean"
    assert settle_lemma(Conjecture(statement="x"), backend=lean_proved).status == "LEAN_CHECKED"


def test_settle_lemma_never_says_proved_on_a_parent_conjecture():
    """Honesty invariant: no BARE 'PROVED' label (that would name proving a parent conjecture), and every certified
    LEMMA status is a REGISTERED external formal certificate — never a self-judged one. The certificate set may grow
    with new external provers (cvc5/Isabelle/Vampire/E), but each must be an external resolver, lemma-level only."""
    from OUTLIER_MCB.certificates import FORMAL_CERTIFICATES
    assert "PROVED" not in gsl.LEMMA_STATES                      # no bare parent-PROVED
    assert all(s in FORMAL_CERTIFICATES for s in gsl.LEMMA_CERTIFIED)   # every certified status is external + registered
    assert {"LEAN_CHECKED", "Z3_PROVED", "NUMERIC_VERIFIED"} <= set(gsl.LEMMA_CERTIFIED)   # the originals remain
