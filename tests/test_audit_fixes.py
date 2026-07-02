"""Regression guards for the library-assisted code audit (found with the library on itself + external tools).

Each test pins a REAL defect the audit surfaced and verified, so it cannot silently come back. External resolvers
only (executed behavior), never self-judgment. See CHANGELOG "library-assisted audit".
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import OUTLIER_MCB as g


# ── F5 (HIGH): the Pareto gate must never crash and never silently accept a dropped/regressed dimension ──
def test_pareto_gate_rejects_dropped_dimension_without_crashing():
    # a dimension present in old but MISSING from new is the worst regression (a skill dropped) → reject, not KeyError
    assert g.pareto_improves({"a": 0.5, "b": 0.5}, {"a": 0.9}) is False
    # a brand-new dimension cannot by itself justify acceptance (else adding a metric games the gate)
    assert g.pareto_improves({"a": 0.5}, {"a": 0.5, "new": 0.0}) is False
    # a new dimension alongside a genuine improvement on a tracked one is fine
    assert g.pareto_improves({"a": 0.5}, {"a": 0.6, "new": 0.0}) is True
    # empty old is not an improvement
    assert g.pareto_improves({}, {"a": 1.0}) is False
    # unchanged classic behaviour
    assert g.pareto_improves({"a": 0.5, "b": 0.5}, {"a": 0.6, "b": 0.5}) is True
    assert g.pareto_improves({"a": 0.5, "b": 0.5}, {"a": 0.9, "b": 0.4}) is False


# ── F8 (HIGH): closure detectors must match WHOLE TOKENS, not substrings (no false INSIDE_THE_BOX) ──
def test_closure_detectors_use_whole_tokens_not_substrings():
    from OUTLIER_MCB import closures as c
    # substring false positives that mislabelled novel readouts as INSIDE the closure
    assert c._detect_deepsets("a routing readout; assume nothing about order") == "UNKNOWN"   # 'assume' ⊅ 'sum'
    assert c._detect_quasi_arithmetic("a meaningful readout") == "UNKNOWN"                     # 'meaningful' ⊅ 'mean'
    assert c._detect_deepsets("a consumer-facing set encoder") == "UNKNOWN"                    # 'consumer' ⊅ 'sum'
    # genuine mentions still detected (no regression)
    assert c._detect_deepsets("readout is the sum of per-instance features") == "INSIDE"
    assert c._detect_quasi_arithmetic("the mean of phi") == "INSIDE"


# ── F12 (MEDIUM-HIGH): judge() must not promote a no-break idea to MUST_BE_AUDITED via an incidental word ──
def test_judge_no_broken_assumption_is_inside_the_box():
    v = g.judge("zorptastic quuxify predict blorp", pack=g.get_pack("coding"))
    assert v.verdict == "INSIDE_THE_BOX"          # breaks nothing → inside, despite the word 'predict'
    assert getattr(v, "broken_assumption", None) is None


# ── F13 (MEDIUM): novelty_score of an idea that breaks nothing must not read as LOCAL novelty ──
def test_novelty_score_of_nothing_broken_is_inside_the_box():
    from OUTLIER_MCB.kernel import novelty_score
    r = novelty_score([])                          # breaks nothing, no synergy
    assert r["score"] < 0.4                         # was 0.4 (mislabelled LOCAL novelty) before the fix
    assert "INSIDE_THE_BOX" in r["label"] or "collage" in r["label"]


# ── F9 (MEDIUM): a passing verifier under a non-online scope must NOT print VERIFIED_USEFUL_NOVELTY ──
def test_verified_useful_novelty_downgraded_without_online_search():
    def incomplete(q):                             # verifier passes, but the online prior-art search did NOT complete
        return {"matches": [], "novelty_scope": "INCOMPLETE_ONLINE_SEARCH", "coverage_level": "PARTIAL"}

    def online(q):                                 # a real, successful online search
        return {"matches": [], "novelty_scope": "ONLINE_PRIOR_ART_CHECKED", "coverage_level": "STRONG"}

    idea = "a far-from-anything mechanism xyzzy plover"
    v_local = g.prior_art_audit(idea, g.CallableProvider(incomplete), verifier_passed=True)
    v_online = g.prior_art_audit(idea, g.CallableProvider(online), verifier_passed=True)
    # WITHOUT a completed online search the strong label is refused (useful ≠ novel); WITH it, it stands
    assert v_local.graded_verdict == "WEAKLY_NOVEL" and v_local.claims_novelty() is False
    assert v_online.graded_verdict == "VERIFIED_USEFUL_NOVELTY"


# ── F10 (HIGH): the scrambled-target negative control must be EARNED (non-vacuous), not a tautology ──
def test_open_ended_negative_control_is_earned_not_vacuous():
    from evals.benchmarks.open_ended import SEED_CURRICULUM, recover_generated, _to_feynman
    from evals.benchmarks.feynman import generate_dataset, _r2
    from evals.self_improve_loop import _base_terms
    from OUTLIER_MCB.grown_basis import GROWN_PRIMITIVES
    from OUTLIER_MCB.evaluators.symbolic import least_squares
    rung = next(p for p in SEED_CURRICULUM if p.id == "OE.d1.triple")
    # the collapse is EARNED: the scrambled fit's held-out R² is genuinely far below the 0.999 gate
    X_tr, y_tr, X_ho, y_ho = generate_dataset(_to_feynman(rung), n=250, seed=0)
    terms = _base_terms(rung.nvars) + GROWN_PRIMITIVES["triple_product"](rung.nvars)
    r2_scrambled = _r2(least_squares(X_tr, list(reversed(y_tr)), terms), X_ho, y_ho)
    assert r2_scrambled < 0.999                    # real collapse — NOT the old `scramble is False` tautology
    assert recover_generated(rung, rung.primitives_needed, 250) is True
    assert recover_generated(rung, rung.primitives_needed, 250, scramble=True) is False


# ── F11 (MEDIUM): a degenerate (constant-target) problem has no variance → must be refused, never leak ──
def test_degenerate_constant_problem_is_refused():
    from evals.benchmarks.open_ended import GeneratedProblem, recover_generated, curriculum_recovery_map
    const = GeneratedProblem("OE.const", lambda a: 5.0, 1, "5", [(-2.0, 2.0)], frozenset())
    assert recover_generated(const, frozenset(), 250) is False      # not settleable (no variance) — cannot be "recovered"
    with pytest.raises(ValueError):
        curriculum_recovery_map([const], 250)                       # refused at construction, cannot enter the curriculum
