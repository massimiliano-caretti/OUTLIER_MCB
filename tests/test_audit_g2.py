"""test_audit_g2 — regression tests for the audit of the novelty / prior-art / metrics modules.

Every test pins a defect that was confirmed by a reproduction before it was fixed. No network: every provider
here is a deterministic fake.
"""
import math
import os
import random
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from OUTLIER_MCB.generators import Candidate  # noqa: E402
from OUTLIER_MCB.novelty import (novelty_audit, prior_art_audit, rebranding_detector,  # noqa: E402
                                 collage_detector, prior_art_distance_score)
from OUTLIER_MCB.prior_art import (CachedPriorArtProvider, CompositePriorArtProvider,  # noqa: E402
                                   CallableOnlineProvider, CrossrefProvider, OfflinePriorArtProvider,
                                   OnlinePriorArtProvider, PriorArtResult)


class _Fixed:
    def __init__(self, payload):
        self.payload = payload

    def research(self, q):
        return dict(self.payload)


# ── novelty: the graded audit must agree with the base audit on COLLAGE ─────────────────────────────────
_COLLAGE = {"matches": [{"title": "Alpha paper", "url": "u1", "summary": "adaptive bucket refill scheme"},
                        {"title": "Beta work", "url": "u2", "summary": "latency aware shaping policy"},
                        {"title": "Gamma", "url": "u3", "summary": "burst control queue drain"}]}
_COLLAGE_IDEA = "adaptive bucket refill latency aware shaping burst control"


def test_prior_art_audit_does_not_upgrade_a_collage_to_novel():
    nv = novelty_audit(_COLLAGE_IDEA, _Fixed(_COLLAGE))
    pa = prior_art_audit(_COLLAGE_IDEA, _Fixed(_COLLAGE))
    assert nv.status == "COLLAGE"
    assert pa.graded_verdict == "COLLAGE_OF_PRIOR_ART"
    assert pa.source_overlap_score >= 0.7


def test_collage_coverage_counts_sources_beyond_the_top_five():
    # 5 irrelevant-but-close titles crowd the top-5; the covering summaries sit in sources 6..8
    filler = [{"title": f"adaptive note {i}", "url": f"f{i}", "summary": ""} for i in range(5)]
    payload = {"matches": filler + _COLLAGE["matches"]}
    pa = prior_art_audit(_COLLAGE_IDEA, _Fixed(payload))
    assert pa.graded_verdict in ("COLLAGE_OF_PRIOR_ART", "RENAMED_PRIOR_ART")


def test_provider_similarity_is_clamped_and_robust():
    payload = {"matches": [{"title": "a", "url": "u", "similarity": 7.0},
                           {"title": "b", "url": "v", "similarity": "garbage"},
                           {"title": "c", "url": "w", "similarity": float("nan")}]}
    nv = novelty_audit("some idea text here", _Fixed(payload))
    assert all(0.0 <= m["similarity"] <= 1.0 for m in nv.closest_matches)
    assert 0.0 <= prior_art_distance_score(nv.closest_matches) <= 1.0


def test_detectors_tolerate_missing_similarity():
    ms = [{"title": "x", "similarity": None}, {"title": "y"}]
    assert rebranding_detector(ms) is False
    assert collage_detector("idea words", ms) is False


def test_sources_as_plain_strings_do_not_crash():
    nv = novelty_audit("an idea", _Fixed({"sources": ["just a title string"]}))
    assert nv.sources_searched == 1


# ── red team: the rebrand probe must catch a rename even when providers give no similarity ──────────────
def test_rebrand_attack_catches_a_rename_without_provider_similarity():
    from OUTLIER_MCB.red_team import rebrand_attack
    prov = OfflinePriorArtProvider([{"title": "token bucket rate limiter refill burst", "url": "x"}])
    attack = rebrand_attack(prov, claim_text="token bucket rate limiter refill burst")
    assert attack.survived(None) is False
    far = rebrand_attack(prov, claim_text="chromatic provenance routing of photosynthesis")
    assert far.survived(None) is True


def test_rebrand_attack_still_abstains_on_search_failure():
    from OUTLIER_MCB.red_team import rebrand_attack

    class Boom:
        def research(self, q):
            raise RuntimeError("down")
    assert rebrand_attack(Boom(), claim_text="x").survived(None) is True


# ── cache: a transient failure must not be pinned for the TTL; the store is bounded ────────────────────
class _Flaky(OnlinePriorArtProvider):
    name = "flaky"

    def __init__(self):
        super().__init__()
        self.calls = 0

    def _fetch(self, q):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("network down")
        return [PriorArtResult(title="t", url="u")]


def test_cache_does_not_store_a_failed_first_fetch():
    inner = _Flaky()
    c = CachedPriorArtProvider(CompositePriorArtProvider([inner]), clock=lambda: 0.0)
    assert c.research("q")["novelty_scope"] == "INCOMPLETE_ONLINE_SEARCH"
    r = c.research("q")
    assert r["novelty_scope"] == "ONLINE_PRIOR_ART_CHECKED" and r["from_cache"] is False
    assert inner.calls == 2


def test_cache_store_is_bounded():
    t = [0.0]

    def clock():
        t[0] += 1.0
        return t[0]
    c = CachedPriorArtProvider(OfflinePriorArtProvider([{"title": "x"}]), clock=clock, max_entries=3)
    for i in range(10):
        c.research(f"q{i}")
    assert len(c._store) == 3 and "q9" in c._store and "q0" not in c._store


def test_crossref_malformed_dates_do_not_fail_the_provider():
    assert CrossrefProvider._date({"published": {"date-parts": []}}) == ""
    assert CrossrefProvider._date({"published": {"date-parts": [[None]]}}) == ""
    assert CrossrefProvider._date({}) == ""
    assert CrossrefProvider._date({"published": {"date-parts": [[2020, 5]]}}) == "2020-5"


# ── embeddings ──────────────────────────────────────────────────────────────────────────────────────────
def test_short_word_texts_are_not_identical():
    from OUTLIER_MCB.embeddings import LexicalEmbedder, NgramEmbedder
    assert LexicalEmbedder().distance("GPU", "CPU") == 1.0
    assert LexicalEmbedder().distance("a b", "a b") == 0.0
    assert LexicalEmbedder().distance("", "") == 0.0
    assert NgramEmbedder().distance("GPU", "CPU") == 1.0
    assert NgramEmbedder().distance("same words here", "same words here") == 0.0


def test_callable_embedder_cache_is_bounded():
    from OUTLIER_MCB.embeddings import CallableEmbedder
    e = CallableEmbedder(lambda t: [float(len(t)), 1.0], max_cache=4)
    for i in range(20):
        e.distance(f"text {i}", "anchor")
    assert len(e._cache) <= 4


# ── frontier ledger: NaN / inf / non-numeric values ────────────────────────────────────────────────────
def test_frontier_rejects_non_finite_and_non_numeric_values():
    from OUTLIER_MCB.frontier_ledger import FrontierLedger, INVALID_CLAIM, ACCEPTED
    led = FrontierLedger()
    ev = {"status": "Z3_PROVED"}
    assert led.claim("p", "m", float("nan"), "decrease", ev).outcome == INVALID_CLAIM
    assert led.claim("p", "m", float("inf"), "decrease", ev).outcome == INVALID_CLAIM
    assert led.claim("p", "m", "abc", "decrease", ev).outcome == INVALID_CLAIM
    assert led.best("p", "m") is None
    assert led.claim("p", "m", 1.0, "decrease", ev).outcome == ACCEPTED


# ── first-principles reviewer: whole-word triggers, bilingual ───────────────────────────────────────────
def test_first_principles_triggers_are_whole_words():
    from OUTLIER_MCB.first_principles_reviewer import first_principles_attack
    assert first_principles_attack("a small cache for the reach of the teacher").dimensions() == ["NEGATION"]
    dims = first_principles_attack("a faster cache that reduces latency for every request").dimensions()
    assert "UNMODELED_COST" in dims and "COUNTEREXAMPLE" in dims


def test_first_principles_reads_italian_claims():
    from OUTLIER_MCB.first_principles_reviewer import first_principles_attack
    dims = first_principles_attack("un parser robusto che garantisce sempre risultati più veloce").dimensions()
    assert {"COUNTEREXAMPLE", "UNMODELED_COST", "PERTURBATION"} <= set(dims)


# ── claim ladder: an Italian overclaim must be gated too ────────────────────────────────────────────────
def test_claim_gate_catches_italian_overclaims():
    from OUTLIER_MCB.claim_ladder import gate_claim_language
    g = gate_claim_language("Abbiamo dimostrato un teorema inedito, una scoperta mai vista")
    assert g["allowed"] is False
    low = g["rewritten"].lower()
    assert "teorema" not in low and "dimostrato" not in low and "mai vista" not in low
    ok = gate_claim_language("un teorema dimostrato", {"falsifier": True, "symbolic_proof": True})
    assert ok["allowed"] is True


# ── metrics / interestingness: scores stay in [0,1] ─────────────────────────────────────────────────────
def test_discovery_confidence_is_bounded():
    from OUTLIER_MCB.metrics import discovery_confidence
    hi = discovery_confidence(5, 5, 5, 5, 5, "ONLINE_PRIOR_ART_CHECKED")["discovery_confidence"]
    lo = discovery_confidence(-5, -5, -5, -5, -5, "ONLINE_PRIOR_ART_CHECKED")["discovery_confidence"]
    nan = discovery_confidence(float("nan"), 0, 0, 1, 1, "ONLINE_PRIOR_ART_CHECKED")["discovery_confidence"]
    assert 0.0 <= lo <= hi <= 1.0 and 0.0 <= nan <= 1.0 and not math.isnan(nan)


def test_interestingness_nan_is_not_maximal():
    from OUTLIER_MCB.interestingness import interestingness_score
    assert interestingness_score(surprise=float("nan"))["interestingness"] == 0.0


# ── QD archive: different axes must not collide in one cell ─────────────────────────────────────────────
def _cand(name, breaks, op="invert"):
    return Candidate(name=name, operator=op, breaks=breaks, assumptions=["x"], negation=name, needs=[],
                     discipline="d")


def test_qd_without_pack_keeps_different_axes_apart():
    from OUTLIER_MCB.qd import QDArchive
    arc = QDArchive(quality_fn=lambda c: 0.5)
    assert arc.add(_cand("a", ["TIME"])) and arc.add(_cand("b", ["SPACE"]))
    assert arc.coverage() == 2
    assert sorted(d["breaks"][0] for d in arc.filled_descriptors()) == ["SPACE", "TIME"]


def test_qd_off_pack_axis_does_not_collide_with_no_break():
    from OUTLIER_MCB.pack import get_pack
    from OUTLIER_MCB.qd import QDArchive
    arc = QDArchive(pack=get_pack("coding"), quality_fn=lambda c: 0.5)
    assert arc.add(_cand("none", []))
    assert arc.add(_cand("alien", ["NOT_A_PACK_AXIS"]))
    assert arc.coverage() == 2
    assert any("NOT_A_PACK_AXIS" in d["breaks"] for d in arc.filled_descriptors())


# ── novelty archive: a member is not its own neighbour ──────────────────────────────────────────────────
def test_mean_novelty_excludes_self():
    from OUTLIER_MCB.novelty_archive import NoveltyArchive
    a = NoveltyArchive()
    a.add({"alpha", "beta"})
    a.add({"gamma", "delta"})
    assert a.mean_novelty() == 1.0
    # a half-overlapping idea is LESS sparse than the archive's members → must not be admitted
    assert a.add_if_novel({"alpha", "gamma"}) is False


# ── greenstar / lineage / reviewer: whole-word family matching ──────────────────────────────────────────
def test_extrapolation_family_match_is_whole_word():
    from OUTLIER_MCB.greenstar import extrapolation
    far = Candidate(name="a", operator="invert", breaks=["ZZZ_NEW_AXIS"], assumptions=[],
                    negation="games scheduled by madam")
    near = Candidate(name="b", operator="invert", breaks=["ZZZ_NEW_AXIS"], assumptions=[],
                     negation="use a token bucket")
    assert extrapolation(far) == 1.0
    assert extrapolation(near) == 0.6


def test_family_guess_is_whole_word():
    from OUTLIER_MCB.lineage import infer_family
    from OUTLIER_MCB.reviewer import _guess_family
    from OUTLIER_MCB.pack import DomainPack
    p = DomainPack(name="t", keywords=[], box_name="b", assumptions=[], relations=[], dimension_of={},
                   box_assumptions=set(), axes={}, known_families=["standard", "gam"], info_kinds={},
                   failure_memory={})
    assert _guess_family("a game engine", p) == "standard"
    assert infer_family("a game engine", p) == "standard"
    assert infer_family("fit a gam here", p) == "gam"


# ── box map: mermaid labels survive quotes / pipes ──────────────────────────────────────────────────────
def test_mermaid_labels_are_escaped():
    from OUTLIER_MCB.box_map import _mermaid
    out = _mermaid('the "box"', [{"assumption": 'a "q"', "dimension": "X|Y"}], [])
    for line in out.splitlines()[1:]:
        if "[" in line:
            label = line[line.index('["') + 2:line.rindex('"]')]
            assert '"' not in label
    assert "X|Y" not in out


# ── receipt: a prior-art check that FOUND the idea does not license novelty words ───────────────────────
def test_receipt_renamed_online_is_not_prior_art_checked():
    from OUTLIER_MCB.receipt import novelty_receipt
    prov = _Fixed({"matches": [{"title": "token bucket rate limiter", "url": "u", "summary": "",
                                "similarity": 0.95}], "novelty_scope": "ONLINE_PRIOR_ART_CHECKED"})
    r = novelty_receipt("a token bucket rate limiter", prior_art_provider=prov)
    assert r["prior_art"]["status"] == "RENAMED"
    assert r["evidence_used"]["prior_art_checked"] is False


# ── semantic grounding: same result, linear-ish time ────────────────────────────────────────────────────
def _reference_patterns(log, min_len=2, max_len=6, min_support=2):
    from OUTLIER_MCB.semantic_grounding import _count_nonoverlapping
    seen = {}
    n = len(log)
    for L in range(min_len, max_len + 1):
        for i in range(n - L + 1):
            pat = tuple(log[i:i + L])
            if pat not in seen:
                seen[pat] = _count_nonoverlapping(log, pat)
    good = [(p, c) for p, c in seen.items() if c >= min_support]
    return sorted(good, key=lambda pc: -(pc[1] * (len(pc[0]) - 1)))


def test_find_recurring_patterns_matches_reference_and_is_fast():
    from OUTLIER_MCB.semantic_grounding import find_recurring_patterns
    rng = random.Random(3)
    for _ in range(30):
        log = [rng.choice("abc") for _ in range(rng.randint(0, 40))]
        assert find_recurring_patterns(log) == _reference_patterns(log)
    big = [rng.choice("abcdefghij") for _ in range(3000)]
    t0 = time.time()
    find_recurring_patterns(big)
    assert time.time() - t0 < 2.0


# ── grounding: unreadable entries do not crash the probe ────────────────────────────────────────────────
def test_probe_survives_unreadable_files(tmp_path):
    from OUTLIER_MCB.grounding import probe
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "a.py").write_text("def f():\n    pass\n")
    locked = tmp_path / "locked"
    locked.mkdir()
    secret = tmp_path / "secret.py"
    secret.write_text("x = 1\n")
    os.chmod(locked, 0)
    os.chmod(secret, 0)
    try:
        ctx = probe(str(tmp_path))
        assert "python" in ctx.languages
    finally:
        os.chmod(locked, 0o755)
        os.chmod(secret, 0o644)


def test_probe_does_not_treat_latest_as_a_test(tmp_path):
    from OUTLIER_MCB.grounding import probe
    (tmp_path / "latest_notes.md").write_text("notes")
    (tmp_path / "main.go").write_text("package main")
    assert probe(str(tmp_path)).test_command is None


# ── the refuting query uses the idea's most specific words, not the alphabetically-first ones ───────────
def test_falsification_query_keeps_distinctive_terms():
    pa = prior_art_audit("an adaptive bucket with apple banana cherry date elderberry photosynthetic throttling",
                         _Fixed({"matches": []}))
    assert "photosynthetic" in pa.falsification_query and "throttling" in pa.falsification_query


def test_receipt_grants_no_novelty_wording_to_a_dead_route():
    import OUTLIER_MCB as m
    r = m.novelty_receipt("a perpetual motion machine with magnets", prompt="invent a new engine",
                          pack=m.get_pack("physics"))
    assert r["verdict"] == "DEAD_BY_BARRIER"
    assert "novel contribution (" in r["max_claim_allowed"] and "not a novel" in r["max_claim_allowed"]
    assert r["claim_as_written_allowed"] is False and m.verify_receipt(r)
