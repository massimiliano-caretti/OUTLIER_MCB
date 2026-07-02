"""test_affect — intrinsic motivation as FUNCTIONAL signals (not emotion labels): curiosity + surprise-joy.

Curiosity biases problem-finding toward the unexplored; discovery_reward is high ONLY for surprising AND
confirmed results; the inventor accumulates 'satisfaction' from genuine discovery. Deterministic.
"""
import OUTLIER_MCB as gsl


# ── the signals ───────────────────────────────────────────────────────────────────────────────────────
def test_curiosity_decays_with_attempts():
    m = gsl.DiscoveryMemory()
    assert gsl.curiosity_score("law_is_smooth", "numeric", m) == 1.0     # never tried → pure unknown
    for _ in range(5):
        m.record("law_is_smooth", "REGULARITY", "numeric", confirmed=True)
    assert gsl.curiosity_score("law_is_smooth", "numeric", m) == 0.0     # well explored → no curiosity left


def test_reward_is_high_only_for_surprising_and_confirmed():
    # expected low (prior 0.1), confirmed → big surprise → big reward (joy of an unexpected truth)
    surprise = gsl.bayesian_surprise(expected=0.1, observed=1.0)
    assert gsl.discovery_reward(surprise, confirmed=True) > 0.7
    # expected high (prior 0.9), confirmed → no surprise → little reward (a boring confirmation)
    dull = gsl.bayesian_surprise(0.9, 1.0)
    assert gsl.discovery_reward(dull, confirmed=True) < 0.2
    # surprising but REFUTED → little reward (a surprising falsehood teaches little here)
    assert gsl.discovery_reward(0.9, confirmed=False) < 0.2


# ── curiosity wired into problem-finding ───────────────────────────────────────────────────────────────
def test_curiosity_reweights_problem_finding():
    pack = gsl.get_pack("numeric")
    m = gsl.DiscoveryMemory()
    for _ in range(5):                                       # make law_is_smooth heavily-explored (low curiosity)
        m.record("law_is_smooth", "REGULARITY", "numeric", confirmed=True)
    base = {p.seed: p.worth for p in gsl.find_problems(pack=pack, blend_with=[], memory=m).problems}
    curious = {p.seed: p.worth for p in gsl.find_problems(pack=pack, blend_with=[], memory=m, curiosity=0.8).problems}
    # under curiosity the well-explored assumption loses worth relative to the no-curiosity ranking
    assert curious["law_is_smooth"] < base["law_is_smooth"]
    assert any("curiosity" in p.components for p in
               gsl.find_problems(pack=pack, blend_with=[], curiosity=0.5).problems)


def test_no_curiosity_is_unchanged():
    pack = gsl.get_pack("numeric")
    a = {p.seed: p.worth for p in gsl.find_problems(pack=pack, blend_with=[]).problems}
    b = {p.seed: p.worth for p in gsl.find_problems(pack=pack, blend_with=[], curiosity=0.0).problems}
    assert a == b                                            # default off → identical (no regression)


# ── the inventor accumulates satisfaction from real discovery ─────────────────────────────────────────
def test_inventor_reports_satisfaction():
    run = gsl.autonomous_inventor(pack=gsl.get_pack("numeric"), blend_with=["causal"], accept=0.0)
    assert hasattr(run, "total_satisfaction")
    assert run.total_satisfaction >= 0.0
    for s in run.steps:
        assert 0.0 <= s.reward <= 1.0 and 0.0 <= s.surprise <= 1.0


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
