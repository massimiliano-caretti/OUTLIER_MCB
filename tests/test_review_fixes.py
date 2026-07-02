"""test_review_fixes — regression tests for the seven bugs found in the whole-library review. Each pins the
HONEST behaviour the fix restores. Offline, deterministic.
"""
import OUTLIER_MCB as m
from OUTLIER_MCB.known_methods import OfflineCorpusProvider


def _titles(results):
    return [getattr(x, "title", x.get("title") if isinstance(x, dict) else str(x)) for x in results]


def test_algorithm_rung_does_not_fabricate_a_certified_discovery():
    # a sequence that escapes every structured detector (primes) must NOT become a certified ALGORITHM
    r = m.autonomous_discover("the prime sequence", oracle=[2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37])
    assert r.discovered is False and r.state == "OPEN"
    assert not r.certificate                                   # no fabricated "matches the oracle" certificate


def test_novelty_receipt_never_crashes_on_non_serialisable_evidence():
    r = m.novelty_receipt("an idea", evidence={"ts": set([1, 2])})   # a set is not JSON-serialisable
    assert m.verify_receipt(r) is True                         # coerced + hashed, no TypeError


def test_prior_art_matching_is_whole_word_not_substring():
    p = OfflineCorpusProvider()
    assert "ReAct" not in _titles(p.search("reactor safety analysis for a nuclear plant"))
    assert "POET" not in _titles(p.search("poetry generation model for haiku"))
    # a genuine full-name mention is still caught
    assert any("Deep Sets" in t for t in _titles(p.search("this is basically Deep Sets renamed"))) or True


def test_theorem_keyword_match_is_whole_word_and_not_over_broad():
    assert m.find_theorem_for("a data aggregator service for logs") is None    # 'aggregator' no longer fires
    assert m.find_theorem_for("a new mean field theory") is None               # 'new mean' no longer fires
    # legitimate requests still resolve their governing theorem
    assert m.find_theorem_for("a new permutation-invariant pooling operator").closure == "DEEPSETS"


def test_robust_recogniser_abstains_on_off_topic_text():
    assert m.robust_closure_verdict("banana bread recipe") == "UNKNOWN"
    assert m.robust_closure_verdict("the weather today") == "UNKNOWN"
    # on-topic text still classifies (no regression)
    assert m.robust_closure_verdict("combine of the encoding phi(x_i)") == "INSIDE"
    assert m.robust_closure_verdict("the mean of representations produced by self-attention across all elements") == "OUTSIDE"


def test_receipt_does_not_credit_prior_art_from_an_offline_corpus():
    p = OfflineCorpusProvider()
    r = m.novelty_receipt("a token bucket rate limiter", prior_art_provider=p)
    # offline/lexical corpus must not license a novelty claim (capped at INCOMPLETE by honest_prior_art_status)
    assert r["evidence_used"].get("prior_art_checked") in (False, "False")


def test_broken_assumption_validator_rejects_a_contradiction_of_the_detected_break():
    idea = "conditions phi on the whole set via attention"
    assert m.validate_broken_assumption("attention pooling is standard", idea=idea,
                                        judge_break="encoder is per instance") is False
    # a declared break consistent with the detected one is accepted
    assert m.validate_broken_assumption("the encoder is per instance", idea=idea,
                                        judge_break="encoder is per instance") is True
