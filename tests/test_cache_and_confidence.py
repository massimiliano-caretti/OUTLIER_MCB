"""test_cache_and_confidence — Step 3 (honest prior-art cache) and Step 5 (discovery_confidence).

#3: a hit within TTL is served with its age; a stale entry whose live refresh FAILS is served but its scope
is downgraded to INCOMPLETE_ONLINE_SEARCH (no faking a fresh search). #5: discovery_confidence is capped by
hard honesty rules — a paraphrase / unmaterialized / unverified idea cannot score high.
"""
import OUTLIER_MCB as gsl
from OUTLIER_MCB.prior_art import OnlinePriorArtProvider, PriorArtResult


class _Clock:
    def __init__(self): self.t = 0.0
    def __call__(self): return self.t


class _FlakyOnline(OnlinePriorArtProvider):
    """Answers while healthy; raises once `down` is set — to exercise the stale-refresh-fails path."""
    def __init__(self):
        super().__init__()
        self.name = "flaky"
        self.down = False

    def _fetch(self, query):
        if self.down:
            raise RuntimeError("offline now")
        return [PriorArtResult(title="some prior work", url="http://w", source_type="paper")]


# ── #3: honest cache ────────────────────────────────────────────────────────────────────────────────
def test_cache_hit_within_ttl_reports_age():
    clock = _Clock()
    inner = _FlakyOnline()
    cached = gsl.CachedPriorArtProvider(inner, ttl_seconds=100, clock=clock)
    first = cached.research("q")
    assert first["from_cache"] is False
    clock.t = 50
    second = cached.research("q")
    assert second["from_cache"] is True and second["cache_age_seconds"] == 50 and second["stale"] is False


def test_stale_refresh_failure_downgrades_scope():
    clock = _Clock()
    inner = _FlakyOnline()
    cached = gsl.CachedPriorArtProvider(inner, ttl_seconds=10, clock=clock)
    cached.research("q")                                  # warm cache while healthy (scope ONLINE)
    clock.t = 1000                                        # well past TTL
    inner.down = True                                     # live refresh will now fail
    out = cached.research("q")
    assert out["from_cache"] is True and out["stale"] is True
    assert out["novelty_scope"] == "INCOMPLETE_ONLINE_SEARCH"   # cannot fake a fresh search
    assert "stale_warning" in out


# ── #5: conservative discovery_confidence ───────────────────────────────────────────────────────────
def test_paraphrase_cannot_score_high():
    # high semantic novelty but no online prior art, no materialization, no verification → capped low.
    out = gsl.discovery_confidence(structure=0.9, semantic_novelty=0.95, prior_art_distance=0.0,
                                   materialization=0.0, verification=0.0, novelty_scope="LOCAL_ONLY")
    assert out["discovery_confidence"] <= 0.5
    assert out["caps_applied"]


def test_full_evidence_can_score_high():
    out = gsl.discovery_confidence(structure=0.9, semantic_novelty=0.8, prior_art_distance=0.9,
                                   materialization=1.0, verification=1.0,
                                   novelty_scope="ONLINE_PRIOR_ART_CHECKED")
    assert out["discovery_confidence"] > 0.7
    assert out["caps_applied"] == []


def test_unmaterialized_is_capped_even_when_online_checked():
    out = gsl.discovery_confidence(structure=1.0, semantic_novelty=1.0, prior_art_distance=1.0,
                                   materialization=0.0, verification=1.0,
                                   novelty_scope="ONLINE_PRIOR_ART_CHECKED")
    assert out["discovery_confidence"] <= 0.5
    assert any("materialized" in c for c in out["caps_applied"])


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
