"""World-test for the broken axis NOVELTY: the DEFAULT novelty distance must stop being novelty-by-naming.

judge() (meta pack) ruled the change MUST_BE_AUDITED, breaking `novelty_is_naming`, and dictated this test:
the lexical default credits a REWORDED known idea (different words, same meaning) as 'far' (novel) and lets
a near-duplicate survive a dedup — that is novelty measured by naming. A semantic default must read the
paraphrase as NEAR and FLIP a real keep/drop decision (the engine's own ablation bar: a metric earns its
place only if it changes a keep/drop outcome). The lexical fallback must stay byte-for-byte the default when
nothing is registered (determinism / zero-dependency preserved).

The semantic stand-in here is a deterministic, dependency-free concept embedder (synonyms share dimensions):
it stands in for any real model (sentence-transformers, an API) — the wiring under test is the process-wide
default resolution, not a particular model.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import OUTLIER_MCB as gsl
from OUTLIER_MCB.embeddings import CallableEmbedder, semantic_distance, default_embedder
from OUTLIER_MCB.evolution_memory import EvolutionMemory, EvolutionRecord


# ── a deterministic, offline stand-in for a real embedder: synonyms collapse to a shared concept axis ──
_SYNONYMS = {
    "rank": "C_ORDER", "order": "C_ORDER", "sort": "C_ORDER",
    "candidates": "C_ITEM", "proposals": "C_ITEM", "ideas": "C_ITEM",
    "far": "C_DIST", "distance": "C_DIST", "distant": "C_DIST",
    "average": "C_AVG", "typical": "C_AVG", "mean": "C_AVG",
    "answer": "C_RESP", "response": "C_RESP", "reply": "C_RESP",
    "cache": "C_CACHE", "disk": "C_DISK", "faster": "C_SPEED", "reuse": "C_REUSE",
}
_CONCEPTS = sorted(set(_SYNONYMS.values()))


def _concept_vector(text):
    """Bag-of-concepts vector: map each token through the synonym table, count over a fixed concept vocab.
    Two synonymous sentences land on the SAME concepts → cosine 1 → distance 0, regardless of surface words."""
    vec = [0.0] * len(_CONCEPTS)
    for raw in "".join(c if c.isalnum() else " " for c in text.lower()).split():
        concept = _SYNONYMS.get(raw)
        if concept is not None:
            vec[_CONCEPTS.index(concept)] += 1.0
    return vec or [0.0] * len(_CONCEPTS)


# different WORDS, same MEANING — the adversarial case lexical Jaccard cannot see
_BASE = "rank candidates by how far they sit from the average answer"
_PARAPHRASE = "order proposals by their distance from the typical response"
_UNRELATED = "cache embeddings on disk for faster reuse"   # genuinely different — must stay FAR for both


def test_default_is_lexical_when_nothing_registered():
    """Determinism / zero-dependency: with no env var and no registration, the default IS lexical — existing
    behaviour is unchanged, the library never imports a model on its own."""
    gsl.reset_default_embedder()
    assert default_embedder().kind == "lexical"
    # and the lexical default mis-reads the synonym paraphrase as FAR (this is the ceiling we are lifting)
    assert semantic_distance(_BASE, _PARAPHRASE) > 0.7


def test_semantic_default_reads_paraphrase_as_near_lexical_as_far():
    """The break itself: under the lexical default the reworded idea is FAR (wrongly novel); register a
    semantic default and the SAME pair is NEAR — while a genuinely different idea stays FAR under both."""
    semantic = CallableEmbedder(_concept_vector)
    try:
        gsl.reset_default_embedder()
        lexical_para = semantic_distance(_BASE, _PARAPHRASE)
        gsl.set_default_embedder(semantic)
        semantic_para = semantic_distance(_BASE, _PARAPHRASE)        # resolves the registered default
        # the discriminating structure lives ENTIRELY on the NOVELTY axis: lexical FAR, semantic NEAR
        assert lexical_para > 0.7
        assert semantic_para < 0.2
        # negative control: a truly different idea is FAR for BOTH — semantics did not just collapse distance
        assert semantic_distance(_BASE, _UNRELATED) > 0.7
    finally:
        gsl.reset_default_embedder()


def _mem():
    m = EvolutionMemory()
    m.add(EvolutionRecord(id="base", problem="p", candidate_name="base", claim=_BASE, score=0.9))
    m.add(EvolutionRecord(id="para", problem="p", candidate_name="para", claim=_PARAPHRASE, score=0.5))
    m.add(EvolutionRecord(id="other", problem="p", candidate_name="other", claim=_UNRELATED, score=0.4))
    return m


def test_env_var_paths_are_deterministic_and_safe():
    """The opt-in env path must never crash the engine or silently load a wrong model: unset / 'lexical' /
    an unknown scheme all resolve to the deterministic lexical fallback. A model is the caller's dependency."""
    import OUTLIER_MCB.embeddings as emb
    saved = os.environ.get(emb._ENV_VAR)
    try:
        gsl.reset_default_embedder()
        for value in (None, "lexical", "LEXICAL", "totally-unknown-scheme:whatever"):
            if value is None:
                os.environ.pop(emb._ENV_VAR, None)
            else:
                os.environ[emb._ENV_VAR] = value
            assert default_embedder().kind == "lexical"
        # an unknown scheme is resolved once and CACHED (a model would not be rebuilt on every distance call)
        assert "totally-unknown-scheme:whatever" in emb._ENV_CACHE
    finally:
        if saved is None:
            os.environ.pop(emb._ENV_VAR, None)
        else:
            os.environ[emb._ENV_VAR] = saved
        gsl.reset_default_embedder()


def test_programmatic_registration_overrides_env():
    """A `set_default_embedder(...)` call always wins over the env var — the explicit choice is authoritative."""
    import OUTLIER_MCB.embeddings as emb
    saved = os.environ.get(emb._ENV_VAR)
    try:
        os.environ[emb._ENV_VAR] = "lexical"
        gsl.set_default_embedder(CallableEmbedder(_concept_vector))
        assert default_embedder().kind == "semantic"
    finally:
        if saved is None:
            os.environ.pop(emb._ENV_VAR, None)
        else:
            os.environ[emb._ENV_VAR] = saved
        gsl.reset_default_embedder()


def test_keepdrop_decision_flips_under_semantic_default():
    """The ablation bar: the metric must FLIP a real keep/drop decision, not just move a number. The same
    dedup, same threshold, same records — only the resolved default differs.
      lexical default  → the reworded near-duplicate SURVIVES (0 removed): novelty-by-naming, the bug.
      semantic default → the reworded near-duplicate is DROPPED (1 removed), the unrelated idea is KEPT."""
    semantic = CallableEmbedder(_concept_vector)
    try:
        gsl.reset_default_embedder()
        lexical_removed = _mem().dedupe_near_duplicates(threshold=0.3)   # embedder=None ⇒ default

        gsl.set_default_embedder(semantic)
        mem = _mem()
        semantic_removed = mem.dedupe_near_duplicates(threshold=0.3)

        assert lexical_removed == 0                      # lexical keeps the rebrand → ceiling
        assert semantic_removed == 1                     # semantic drops it → keep/drop decision FLIPPED
        survivors = {r.id for r in mem.all()}
        assert "other" in survivors                      # diversity preserved (genuinely different kept)
        assert "para" not in survivors                   # the lower-scoring reword is the one dropped
        assert "base" in survivors
    finally:
        gsl.reset_default_embedder()
