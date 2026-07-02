"""test_offline_corpus — the bundled, deterministic prior-art corpus raises the no-network default from
LOCAL_ONLY (compared only to a pack's own families) to OFFLINE_CORPUS_CHECKED: renames of famous methods are
caught with no API key, while a genuinely off-corpus idea honestly finds nothing. Deterministic and offline.
"""
import OUTLIER_MCB as gsl
from OUTLIER_MCB.known_methods import OfflineCorpusProvider


def test_scope_is_offline_corpus_checked():
    r = gsl.novelty_audit("some idea", OfflineCorpusProvider())
    assert r.novelty_scope == "OFFLINE_CORPUS_CHECKED"                # a real, bounded check — not LOCAL_ONLY
    assert "OFFLINE_CORPUS_CHECKED" in gsl.NOVELTY_SCOPES


def test_catches_a_rename_of_a_famous_method_offline():
    p = OfflineCorpusProvider()
    # a rate limiter described in words that share the token-bucket vocabulary → caught with no network
    r = gsl.novelty_audit("rate limiting by consuming tokens refilled over time with a burst allowance", p)
    assert r.status in ("RENAMED", "COLLAGE")
    # a quality-diversity illumination → MAP-Elites, caught offline
    r2 = gsl.novelty_audit("a quality-diversity illumination over a behaviour map of solutions", p)
    assert r2.status in ("RENAMED", "COLLAGE")


def test_direct_mention_of_a_method_is_a_hit():
    p = OfflineCorpusProvider()
    hits = [h.title for h in p.search("this is basically MAP-Elites with a twist")]
    assert "MAP-Elites" in hits                                       # a direct name mention is an unambiguous hit


def test_off_corpus_idea_finds_nothing_but_stays_honest():
    p = OfflineCorpusProvider()
    r = gsl.novelty_audit("a zorptastic quuxify blorp wibble resembling nothing on record", p)
    assert r.status == "NO_PRIOR_ART_FOUND"
    assert r.novelty_scope == "OFFLINE_CORPUS_CHECKED"               # honest: bounded offline check, not proof


def test_corpus_entries_are_cited():
    for m in gsl.KNOWN_METHODS:
        assert m.reference and m.name and m.summary                 # every entry documents a real, cited method
    assert len(gsl.KNOWN_METHODS) >= 30 and "DeepSets" in gsl.known_method_names()
