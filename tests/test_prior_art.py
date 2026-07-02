"""test_prior_art — Step 1: real multi-source prior art + honest novelty_scope.

Deterministic & offline: an OfflinePriorArtProvider and fake online providers (one that answers, one that
fails) exercise the three scopes, the dedup, the provenance, and the honesty gate that forbids strong
provisional novelty without a successful ONLINE search — WITHOUT touching the network.
"""
import OUTLIER_MCB as gsl
from OUTLIER_MCB.prior_art import PriorArtResult, OnlinePriorArtProvider

_IDEA = "a distributed rate limiter that measures request cost instead of time windows"
_TS = "2026-06-30T00:00:00Z"


def _result(title, summary="", url="", similarity=None, source_type="paper"):
    return PriorArtResult(title=title, summary=summary, url=url, similarity=similarity,
                          source_type=source_type, retrieved_at=_TS)


class _FakeOnline(OnlinePriorArtProvider):
    def __init__(self, results=None, fail=False, name="fake_online"):
        super().__init__()
        self.name = name
        self._results = results or []
        self._fail = fail

    def _fetch(self, query):
        if self._fail:
            raise RuntimeError("network down")
        return list(self._results)


# ── scope logic ─────────────────────────────────────────────────────────────────────────────────────
def test_offline_only_is_local_scope():
    comp = gsl.CompositePriorArtProvider([gsl.OfflinePriorArtProvider([_result("unrelated thing")])],
                                         retrieved_at=_TS)
    res = comp.research(_IDEA)
    assert res["novelty_scope"] == "LOCAL_ONLY"
    assert res["retrieved_at"] == _TS


def test_successful_online_is_checked_scope():
    comp = gsl.CompositePriorArtProvider([_FakeOnline([_result("something else entirely")])], retrieved_at=_TS)
    assert comp.research(_IDEA)["novelty_scope"] == "ONLINE_PRIOR_ART_CHECKED"


def test_all_online_failing_is_incomplete_scope():
    comp = gsl.CompositePriorArtProvider([_FakeOnline(fail=True)], retrieved_at=_TS)
    res = comp.research(_IDEA)
    assert res["novelty_scope"] == "INCOMPLETE_ONLINE_SEARCH"
    assert res["failed_sources"] and res["failed_sources"][0]["provider"] == "fake_online"


def test_results_are_deduped_by_url():
    dup = _result("paper X", url="http://x")
    comp = gsl.CompositePriorArtProvider(
        [_FakeOnline([dup], name="a"), _FakeOnline([_result("paper X", url="http://x")], name="b")],
        retrieved_at=_TS)
    assert len(comp.research(_IDEA)["matches"]) == 1


# ── the honesty gate, wired through prior_art_audit ──────────────────────────────────────────────────
def test_online_no_match_is_provisional_on_checked_sources():
    comp = gsl.CompositePriorArtProvider([_FakeOnline([_result("a recipe for sourdough bread")])], retrieved_at=_TS)
    v = gsl.prior_art_audit(_IDEA, comp)
    assert v.graded_verdict == "PROVISIONALLY_NOVEL"
    assert v.novelty_scope == "ONLINE_PRIOR_ART_CHECKED"
    assert v.scoped_verdict() == "PROVISIONALLY_NOVEL_ON_CHECKED_SOURCES"
    assert v.checked_sources and v.retrieved_at == _TS


def test_local_only_cannot_yield_strong_novelty():
    comp = gsl.CompositePriorArtProvider([gsl.OfflinePriorArtProvider([_result("sourdough bread recipe")])],
                                         retrieved_at=_TS)
    v = gsl.prior_art_audit(_IDEA, comp)
    assert v.graded_verdict == "WEAKLY_NOVEL"            # downgraded: no online search ran
    assert v.scoped_verdict() == "LOCAL_ONLY_NOVELTY"


def test_incomplete_online_is_flagged_not_novel():
    comp = gsl.CompositePriorArtProvider([_FakeOnline(fail=True)], retrieved_at=_TS)
    v = gsl.prior_art_audit(_IDEA, comp)
    assert v.graded_verdict == "WEAKLY_NOVEL"
    assert v.scoped_verdict() == "PRIOR_ART_INCOMPLETE"


def test_close_online_match_is_a_rename():
    comp = gsl.CompositePriorArtProvider([_FakeOnline([_result(_IDEA, summary=_IDEA, url="http://m")])],
                                         retrieved_at=_TS)
    v = gsl.prior_art_audit(_IDEA, comp)
    assert v.graded_verdict == "RENAMED_PRIOR_ART"
    assert v.novelty_scope == "ONLINE_PRIOR_ART_CHECKED"


def test_no_verdict_claims_absolute_novelty():
    comp = gsl.CompositePriorArtProvider([_FakeOnline([_result("x")])], retrieved_at=_TS)
    v = gsl.prior_art_audit(_IDEA, comp)
    assert "absolute" not in v.scoped_verdict().lower()          # the verdict never CLAIMS absolute novelty
    assert "absolute novelty is practically unprovable" in v.markdown().lower()  # it DISCLAIMS it, honestly


# ── the real online providers are constructible and declare themselves online (no network here) ──────
def test_real_providers_are_online_and_lazy():
    for P in (gsl.ArxivPriorArtProvider, gsl.OpenAlexProvider, gsl.GitHubPriorArtProvider):
        p = P()
        assert p.is_online is True and p.name


# ── fix B: novelty is CLAIMED only under a successful ONLINE search; LOCAL_ONLY/unscoped refuses it ───
def _far_provider(scope=None):
    def research(q):
        d = {"matches": [{"title": "a recipe for sourdough bread", "summary": "flour water salt"}]}
        if scope:
            d.update({"novelty_scope": scope, "coverage_level": "STRONG"})
        return d
    return gsl.CallableProvider(research)


def test_claims_novelty_requires_online_scope():
    # SAME graded verdict, but the honest novelty CLAIM is granted only when an online search actually ran
    local = gsl.prior_art_audit(_IDEA, _far_provider())                               # unscoped
    online = gsl.prior_art_audit(_IDEA, _far_provider("ONLINE_PRIOR_ART_CHECKED"))    # real online search
    assert local.graded_verdict == "PROVISIONALLY_NOVEL" and local.claims_novelty() is False
    assert online.graded_verdict == "PROVISIONALLY_NOVEL" and online.claims_novelty() is True
    assert "NOT a novelty claim" in local.markdown()        # the refusal is surfaced, not hidden
    assert "NOT a novelty claim" not in online.markdown()


def test_default_online_provider_builds_a_real_online_composite_offline():
    cached = gsl.default_online_provider(cache=True)
    assert isinstance(cached, gsl.CachedPriorArtProvider)
    names = [p.name for p in cached.inner.providers]
    assert names == ["arxiv", "openalex", "crossref"] and cached.inner.is_online is True
    plain = gsl.default_online_provider(cache=False, include_github=True)
    assert isinstance(plain, gsl.CompositePriorArtProvider) and "github" in [p.name for p in plain.providers]


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
