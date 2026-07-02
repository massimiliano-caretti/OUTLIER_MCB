"""test_demo — the zero-config, offline, batteries-included tour runs end-to-end with no setup. Deterministic.
"""
import OUTLIER_MCB as gsl


def test_demo_runs_offline_end_to_end():
    out = gsl.demo()
    assert isinstance(out, str) and "zero-config offline demo" in out
    # it exercises the distinctive parts: a verdict, an offline prior-art scope, and the claim gate
    assert "verdict:" in out
    assert "OFFLINE_CORPUS_CHECKED" in out
    assert "honest rewrite:" in out


def test_demo_accepts_a_custom_prompt_and_idea():
    out = gsl.demo(prompt="invent a better cache", idea="key the cache by request cost, not by recency")
    assert "OUTLIER_MCB" in out and "verdict:" in out
