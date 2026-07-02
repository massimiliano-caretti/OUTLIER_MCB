"""G6 — the new external certificates are first-class: they advance the monotone frontier; nothing uncertified does.

A lemma certified by ANY external prover (Isabelle/cvc5/Vampire/E/PARI) is a THEOREM for that lemma; the parent
conjecture stays CONJECTURE (never PROVED). This pins the claim ladder invariant + the certificate registry.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import OUTLIER_MCB as g
from OUTLIER_MCB.certificates import FORMAL_CERTIFICATES, EXTERNAL_CERTIFICATES, is_external_certificate
from OUTLIER_MCB.frontier_ledger import FrontierLedger, is_certified
from OUTLIER_MCB.math_discovery import LEMMA_CERTIFIED

_NEW = ("ISABELLE_CHECKED", "CVC5_PROVED", "VAMPIRE_PROVED", "E_PROVED")


def test_new_statuses_are_registered_external_formal_certificates():
    for s in _NEW:
        assert s in FORMAL_CERTIFICATES and s in EXTERNAL_CERTIFICATES
        assert is_external_certificate({"status": s}) and is_certified({"status": s})
        assert s in LEMMA_CERTIFIED                                 # a LemmaCertificate with it is `certified`


def test_each_new_certificate_advances_the_frontier():
    for i, s in enumerate(_NEW):
        led = FrontierLedger()
        r1 = led.claim("prime gap bound H", "H", 246.0, "decrease", {"status": s})
        assert r1.accepted                                         # a valid external certificate advances the frontier
        r2 = led.claim("prime gap bound H", "H", 200.0, "decrease", {"status": s})
        assert r2.accepted and r2.value == 200.0                  # monotone improvement accepted


def test_uncertified_status_is_rejected():
    led = FrontierLedger()
    assert not led.claim("H", "H", 246.0, "decrease", {"status": "UNKNOWN_TIMEOUT"}).accepted
    assert not led.claim("H", "H", 246.0, "decrease", {"status": "EMPIRICALLY_SUPPORTED"}).accepted   # sampling ≠ proof
    assert not led.claim("H", "H", 246.0, "decrease", {"status": ""}).accepted


def test_frontier_never_regresses_even_with_new_certificates():
    led = FrontierLedger()
    assert led.claim("H", "H", 246.0, "decrease", {"status": "CVC5_PROVED"}).accepted
    worse = led.claim("H", "H", 300.0, "decrease", {"status": "ISABELLE_CHECKED"})   # a certified but WORSE bound
    assert not worse.accepted and worse.outcome == "REGRESSION_REJECTED"          # never regress, even if certified
