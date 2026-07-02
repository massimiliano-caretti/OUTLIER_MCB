"""Agnostic external certificates — the frontier accepts ANY field's resolver, not only math proofs.

RED→GREEN: a physics simulation / wet-lab reproduction / ML eval / benchmark / repo test advances a monotone
frontier exactly like a math proof; mere sampling (evidence, not a certificate) is still rejected.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import OUTLIER_MCB as gsl
from OUTLIER_MCB.certificates import (is_external_certificate, EXTERNAL_CERTIFICATES, FORMAL_CERTIFICATES,
                                         EMPIRICAL_CERTIFICATES, META_CERTIFICATES, Certificate, kind_of)
from OUTLIER_MCB.frontier_ledger import FrontierLedger, ACCEPTED, UNCERTIFIED_REJECTED


def test_vocabulary_covers_formal_empirical_meta():
    assert set(EXTERNAL_CERTIFICATES) == set(FORMAL_CERTIFICATES) | set(EMPIRICAL_CERTIFICATES) | set(META_CERTIFICATES)
    assert "NUMERIC_VERIFIED" in FORMAL_CERTIFICATES
    assert {"SIMULATION_VERIFIED", "EXPERIMENT_REPRODUCED", "DATASET_EVAL_PASSED", "BENCHMARK_MEASURED",
            "REPO_TEST_GREEN"} <= set(EMPIRICAL_CERTIFICATES)


def test_is_external_certificate_and_sampling_is_not():
    assert is_external_certificate("SIMULATION_VERIFIED")
    assert is_external_certificate({"status": "EXPERIMENT_REPRODUCED"})
    assert is_external_certificate(Certificate(status="REPO_TEST_GREEN"))
    assert not is_external_certificate("EMPIRICALLY_SUPPORTED")      # sampling ≠ certificate
    assert not is_external_certificate(None) and not is_external_certificate({"status": ""})


def test_certificate_kind_and_honesty_flag():
    c = Certificate(status="SIMULATION_VERIFIED", detail="reproducible FEM run", domain="engineering")
    assert c.certified and c.kind == "EMPIRICAL"
    assert "NOT a proof" in c.markdown()
    assert kind_of("Z3_PROVED") == "FORMAL" and kind_of("INVARIANTS_VERIFIED") == "META"


def test_frontier_accepts_every_domain_certificate():
    for status in EMPIRICAL_CERTIFICATES + FORMAL_CERTIFICATES:
        led = FrontierLedger()
        r = led.claim("p", "m", 1.0, "increase", {"status": status})
        assert r.outcome == ACCEPTED, status


def test_frontier_still_rejects_sampling_and_uncertified():
    led = FrontierLedger()
    assert led.claim("p", "m", 1.0, "increase", {"status": "EMPIRICALLY_SUPPORTED"}).outcome == UNCERTIFIED_REJECTED
    assert led.claim("p", "m", 1.0, "increase", None).outcome == UNCERTIFIED_REJECTED
