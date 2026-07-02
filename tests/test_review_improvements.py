"""test_review_improvements — the external-review fixes: coverage tiers, OpenAlex abstracts, cache
normalization, injectable online providers, the EVALUATOR_FAILED honesty guard, and the new CLI command.
All deterministic / offline.
"""
import OUTLIER_MCB as gsl
from OUTLIER_MCB.prior_art import OnlinePriorArtProvider, PriorArtResult, OpenAlexProvider


class _Online(OnlinePriorArtProvider):
    def __init__(self, name, results=None, fail=False):
        super().__init__()
        self.name = name
        self._results = results or [PriorArtResult(title=f"{name} hit", url=f"http://{name}")]
        self._fail = fail

    def _fetch(self, query):
        if self._fail:
            raise RuntimeError("down")
        return list(self._results)


# ── coverage tiers (one source answering ≠ thorough) ─────────────────────────────────────────────────
def test_coverage_levels():
    one = gsl.CompositePriorArtProvider([_Online("a")], retrieved_at="t")
    assert one.research("q")["coverage_level"] == "PARTIAL"
    two = gsl.CompositePriorArtProvider([_Online("a"), _Online("b")], retrieved_at="t")
    assert two.research("q")["coverage_level"] == "MULTI"
    three = gsl.CompositePriorArtProvider([_Online("a"), _Online("b"), _Online("c")], retrieved_at="t")
    assert three.research("q")["coverage_level"] == "STRONG"
    none = gsl.CompositePriorArtProvider([_Online("a", fail=True)], retrieved_at="t")
    assert none.research("q")["coverage_level"] == "NONE"
    # the verdict carries it through
    v = gsl.prior_art_audit("idea", two)
    assert v.coverage_level == "MULTI"


# ── OpenAlex abstract reconstruction ─────────────────────────────────────────────────────────────────
def test_openalex_abstract_reconstruction():
    inv = {"Conceptual": [0], "blending": [1], "is": [2], "creative": [3]}
    assert OpenAlexProvider._abstract(inv) == "Conceptual blending is creative"
    assert OpenAlexProvider._abstract(None) == ""


# ── cache always returns the rich scoped schema ──────────────────────────────────────────────────────
def test_cache_normalizes_raw_provider():
    raw = _Online("raw")                                  # a raw provider: research() returns only {"matches"}
    cached = gsl.CachedPriorArtProvider(raw, ttl_seconds=100, clock=lambda: 0.0)
    out = cached.research("q")
    assert "novelty_scope" in out and "coverage_level" in out and "checked_sources" in out
    assert out["novelty_scope"] == "ONLINE_PRIOR_ART_CHECKED"   # inner is online


# ── injectable online providers (breadth without bundling a scraper) ─────────────────────────────────
def test_callable_online_provider():
    p = gsl.CallableOnlineProvider(lambda q: [{"title": "web hit", "url": "http://w", "source_type": "web"}],
                                   name="websearch")
    assert p.is_online is True
    comp = gsl.CompositePriorArtProvider([p], retrieved_at="t")
    res = comp.research("q")
    assert res["novelty_scope"] == "ONLINE_PRIOR_ART_CHECKED" and res["matches"][0]["title"] == "web hit"


def test_new_providers_are_online():
    for P in (gsl.CrossrefProvider, gsl.GitHubCodeSearchProvider):
        assert P().is_online is True


# ── EVALUATOR_FAILED: a real evaluator error is NOT a discovery ──────────────────────────────────────
def test_evaluator_failure_is_marked_not_scored():
    def boom(_cand):
        raise RuntimeError("evaluator exploded")
    run = gsl.autonomous_inventor(pack=gsl.get_pack("numeric"), blend_with=[], evaluator=boom, accept=0.0)
    assert run.evaluator_failures > 0
    assert all(s.outcome != "CONFIRMED" for s in run.steps)     # a crash never looks like a discovery
    assert any(s.outcome == "EVALUATOR_FAILED" for s in run.steps)


# ── novelty_scope propagates into the LLM-loop scoring (a local/incomplete 'novel' is worth less) ────
def test_novelty_scope_propagates_into_llm_scoring():
    from OUTLIER_MCB.llm_loop import _prior_art_component
    base = {"distance": 1.0}
    online = _prior_art_component("PROVISIONALLY_NOVEL", {**base, "novelty_scope": "ONLINE_PRIOR_ART_CHECKED", "coverage_level": "STRONG"})
    local = _prior_art_component("PROVISIONALLY_NOVEL", {**base, "novelty_scope": "LOCAL_ONLY", "coverage_level": "NONE"})
    incomplete = _prior_art_component("PROVISIONALLY_NOVEL", {**base, "novelty_scope": "INCOMPLETE_ONLINE_SEARCH", "coverage_level": "NONE"})
    assert online > local > incomplete                      # novelty without a real online search is worth less
    assert _prior_art_component("RENAMED_PRIOR_ART", {**base, "novelty_scope": "ONLINE_PRIOR_ART_CHECKED"}) == 0.0


# ── CLI command exists ───────────────────────────────────────────────────────────────────────────────
def test_cli_readiness_discovery(capsys):
    from OUTLIER_MCB.cli import main
    main(["readiness-discovery"])
    assert "Discovery readiness" in capsys.readouterr().out


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
