"""test_claim_ladder — #9 the rigor ladder. A strong word is locked to a rung: 'theorem'/'proved' need a
symbolic proof, 'discovered'/'never seen'/'novel' need a prior-art check. The gate rewrites an over-reaching
sentence into the strongest HONEST one. Brilliant without lying. Offline, deterministic."""
import OUTLIER_MCB as m
from OUTLIER_MCB.claim_ladder import classify_claim, gate_claim_language, claim_ladder_ablation, LADDER


def test_classify_places_claim_on_the_right_rung():
    assert classify_claim("x", {}).rung == "IDEA_ONLY"
    assert classify_claim("x", {"falsifier": "a test"}).rung == "FALSIFIABLE_CLAIM"
    assert classify_claim("x", {"symbolic_proof": True}).rung == "SYMBOLICALLY_PROVED"
    full = classify_claim("x", {"formal_verification": True, "prior_art_checked": True})
    assert full.rung == "FORMALLY_VERIFIED" and full.prior_art_checked and "PRIOR_ART_CHECKED" in full.achieved


def test_gate_blocks_unlicensed_strong_words_and_rewrites_them():
    g = gate_claim_language("We proved a novel theorem", {"falsifier": True})
    assert g["allowed"] is False
    assert {v["word"] for v in g["violations"]} >= {"theorem", "proved", "novel"}
    low = g["rewritten"].lower()
    assert "theorem" not in low and "proved" not in low      # rewritten into honest hedges


def test_gate_allows_strong_words_once_evidence_reaches_the_rung():
    g = gate_claim_language("We proved the theorem", {"symbolic_proof": True})
    assert g["allowed"] is True and g["rewritten"] == "We proved the theorem"
    # 'discovered' needs BOTH support and a prior-art check
    assert gate_claim_language("we discovered X", {"empirical_support": True})["allowed"] is False
    assert gate_claim_language("we discovered X", {"empirical_support": True, "prior_art_checked": True})["allowed"] is True


def test_claim_ladder_ablation_is_about_evidence_not_censorship():
    ab = claim_ladder_ablation()
    assert ab["gate_is_about_evidence"] is True               # blocks under weak evidence, licenses under full
    assert ab["gated_blocks"] and ab["licensed_with_full_evidence"]


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
