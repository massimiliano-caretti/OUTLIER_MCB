"""test_readiness_discovery — Step 11: the honest discovery-readiness gate.

Without a reachable online provider the gate cannot exceed LOCAL_ONLY_READY; with one it rises. Core
honesty capabilities must hold or the state is NOT_READY_DISCOVERY.
"""
import OUTLIER_MCB as gsl
from OUTLIER_MCB.prior_art import OnlinePriorArtProvider, PriorArtResult


class _FakeOnline(OnlinePriorArtProvider):
    def __init__(self):
        super().__init__()
        self.name = "fake_online"

    def _fetch(self, query):
        return [PriorArtResult(title="some unrelated prior work", url="http://w", source_type="paper")]


def test_no_online_provider_is_local_only_ready():
    rep = gsl.readiness_discovery_report()
    assert rep["state"] == "LOCAL_ONLY_READY"             # core honesty holds, but no online search
    assert rep["checks"]["online_prior_art_reachable"]["passed"] is False
    assert all(rep["checks"][c]["passed"] for c in
               ("novelty_scope_supported", "offline_fallback_honest", "discovery_metrics_conservative",
                "math_no_overclaim", "no_absolute_verdicts"))


def test_online_provider_raises_readiness():
    rep = gsl.readiness_discovery_report(online_provider=_FakeOnline())
    # SymPy is an optional formal backend; with it present the gate reaches the experimental tier.
    assert rep["state"] in ("ONLINE_AUDIT_READY", "DISCOVERY_EXPERIMENTAL_READY")
    assert rep["checks"]["online_prior_art_reachable"]["passed"] is True


def test_failed_online_cannot_be_online_ready():
    class _Down(OnlinePriorArtProvider):
        name = "down"
        def _fetch(self, query):
            raise RuntimeError("no network")
    rep = gsl.readiness_discovery_report(online_provider=_Down())
    assert rep["state"] == "LOCAL_ONLY_READY"             # failed online search ⇒ not online-ready
    assert rep["checks"]["online_prior_art_reachable"]["passed"] is False


def test_markdown_renders():
    from OUTLIER_MCB.readiness_discovery import markdown
    assert "Discovery readiness" in markdown(gsl.readiness_discovery_report())


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
