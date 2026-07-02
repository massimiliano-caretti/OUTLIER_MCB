"""test_ngram_embedder — a stronger, in-box, deterministic offline distance than plain token-Jaccard: it closes
much of the paraphrase gap (morphology, hyphenation, partial words) with no model and no network. Deterministic.
"""
import OUTLIER_MCB as gsl
from OUTLIER_MCB.embeddings import LexicalEmbedder, NgramEmbedder


def test_identical_strings_are_zero_distance():
    ng = NgramEmbedder()
    assert ng.distance("same words here", "same words here") == 0.0


def test_closes_the_paraphrase_gap_vs_pure_lexical():
    lex, ng = LexicalEmbedder(), NgramEmbedder()
    a, b = "permutation invariant pooling", "permutation-invariance pooled readout"
    assert ng.distance(a, b) < lex.distance(a, b)          # morphology/hyphenation align → nearer than Jaccard


def test_unrelated_stays_far():
    ng = NgramEmbedder()
    assert ng.distance("token bucket rate limiter", "photosynthesis in tropical plants") > 0.8


def test_is_deterministic():
    ng = NgramEmbedder()
    assert ng.distance("a b c", "a b d") == ng.distance("a b c", "a b d")


def test_can_be_set_as_the_default_offline_embedder():
    try:
        gsl.set_default_embedder(NgramEmbedder())
        # semantic_distance now uses the stronger offline embedder
        d = gsl.semantic_distance("token bucket rate limiter", "rate limiting with token buckets")
        assert 0.0 <= d <= 1.0
    finally:
        gsl.reset_default_embedder()
