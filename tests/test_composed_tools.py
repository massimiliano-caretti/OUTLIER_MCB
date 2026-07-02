"""test_composed_tools — the five low-risk composed tools (box_map, assumption_diff, novelty_receipt,
CI gate, honesty linter). They are pure compositions of existing primitives; these tests pin their contracts
and their HONEST/CONSERVATIVE behaviour. Offline, deterministic, additive (no core path touched)."""
import pytest
import OUTLIER_MCB as m
from OUTLIER_MCB.pack import DomainPack
from OUTLIER_MCB.core import Assumption


def _mil_pack():
    return DomainPack(name="mil", assumptions=[Assumption("readout_is_mean_of_phi", "the readout is the mean", "", "")],
                      dimension_of={"readout_is_mean_of_phi": "READOUT"},
                      axes={"READOUT": {"priority": 1, "verdict": "breaking the readout changes the function class"}},
                      universal_closures=["DEEPSETS"])


def test_box_map_makes_the_box_legible():
    bm = m.box_map("invent a new permutation-invariant pooling operator")
    assert bm["box_name"] and len(bm["axes"]) >= 1
    assert any(c["name"] == "DEEPSETS" for c in bm["closures"])         # governing closure surfaced
    assert bm["closures"][0]["exits"]                                   # the only admissible exits are listed
    assert "graph" in bm["mermaid"]                                     # a diagram is emitted
    assert "# Box map" in m.box_map_markdown("invent a new pooling operator")


def test_assumption_diff_reports_two_legs_and_a_tension():
    d = m.assumption_diff("R = mean of phi(x_i) over the bag", "R = mean of phi(x_i) over the bag",
                          pack=_mil_pack(), prompt="new pooling")
    assert d["a"]["verdict"] and d["b"]["verdict"] and isinstance(d["tension"], str) and d["tension"]
    assert "# Assumption-diff" in m.assumption_diff_markdown("a", "b")


def test_novelty_receipt_is_hashed_and_tamper_evident():
    r = m.novelty_receipt("R = sum of softmax(e/T)*e, a soft-top-k readout", pack=_mil_pack(), prompt="new pooling")
    assert r["verdict"] and isinstance(r["max_claim_allowed"], str)
    assert m.verify_receipt(r) is True                                 # the content hash checks out
    tampered = dict(r); tampered["verdict"] = "MUST_BE_AUDITED"
    assert m.verify_receipt(tampered) is False                         # any edit breaks the hash


def test_receipt_is_conservative_no_escape_credit_when_inside_the_box():
    # a readout INSIDE the DeepSets closure must NOT be credited a closure-escape in its receipt
    r = m.novelty_receipt("R = mean(e) over the bag", pack=_mil_pack(), prompt="new pooling")
    assert r["verdict"] == "INSIDE_THE_BOX"
    assert r["closure_verdict"]["closure_escape_proven"] is False       # conservative: no fabricated escape


def test_ci_gate_fails_on_inside_the_box_and_on_overclaim():
    with pytest.raises(m.NoveltyRegression):
        m.assert_outside_the_box("R = mean(e) over the bag", pack=_mil_pack())
    with pytest.raises(m.ClaimOverreach):
        m.assert_claim_honest("a breakthrough, first-ever novel architecture")
    # a modest claim with no unearned strong words passes
    m.assert_claim_honest("we describe a method and evaluate it")


def test_honesty_linter_flags_overclaims_and_rewrites():
    findings = m.lint_text("This is a breakthrough.\nWe describe a method.")
    assert len(findings) == 1 and findings[0]["line"] == 1
    assert "breakthrough" in findings[0]["violations"] and findings[0]["rewritten"] != findings[0]["original"]
    assert m.lint_text("a plain factual sentence about a method") == []  # clean text → no findings
