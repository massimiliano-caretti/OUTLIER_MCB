"""test_generative_4_to_8 — improvements #4 active problem-finding, #5 online analogy API, #6 failure→mutation,
#7 divergent protocol runner, #8 real novelty frontier. Each has a behavior test AND an ablation proving it is
not decorative. Offline, deterministic (a fake provider; no network)."""
import OUTLIER_MCB as m


# ── #4 active problem-finding ───────────────────────────────────────────────────────────────────────
def test_detect_problem_fixation_and_ranking():
    stuck = m.detect_problem_fixation(["a", "a", "a", "b"])
    assert stuck["fixated"] is True and stuck["dominant_seed"] == "a"
    assert m.detect_problem_fixation(["a", "b", "c", "d"])["fixated"] is False
    ab = m.problem_active_ablation()
    assert ab["earns_keep"] is True and ab["ranking_discriminates"] and ab["fixation_fires_on_stuck"]


def test_high_leverage_questions_and_family():
    port = m.find_high_leverage_questions({"pack": m.get_pack("coding"), "prompt": "a new rate limiter"}, k=4)
    assert port.best() is not None
    assert len(m.generate_problem_family("a new rate limiter", m.get_pack("coding"), n=3)) == 3


# ── #5 online analogy API ────────────────────────────────────────────────────────────────────────────
def _mech_provider():
    return m.CallableProvider(lambda q: {"matches": [{"title": "predator-prey carrying capacity",
                                                      "summary": "population stabilizes at a dynamic equilibrium",
                                                      "url": "http://x", "source_type": "paper"}]})


def test_transfer_carries_world_test_and_prior_art_hook():
    mechs = m.discover_remote_mechanisms("an adaptive rate limiter", _mech_provider(), domains=["ecology"])
    assert mechs and mechs[0].domain == "ecology"
    tr = m.transfer_mechanism(mechs[0], "an adaptive rate limiter")
    assert tr.world_test and "refuted" in tr.world_test
    assert m.testable_analogy_claim(tr)["source_domain"] == "ecology"
    verdict = m.analogy_prior_art_audit(tr, _mech_provider())
    assert tr.prior_art is verdict and hasattr(verdict, "graded_verdict")


def test_analogy_online_ablation_distant_beats_local():
    ab = m.analogy_online_ablation(_mech_provider())
    assert ab["earns_keep"] is True and ab["distant_more_lateral"] is True


# ── #6 failure → mutation ────────────────────────────────────────────────────────────────────────────
def test_mutate_from_failure_lesson_repairs_the_mode():
    from OUTLIER_MCB.generators.base import Candidate
    bare = Candidate(name="bare", operator="proposed", breaks=["X"], assumptions=["a"],
                     negation="no falsifier", discipline="")
    mut = m.mutate_from_failure_lesson(bare, m.FailureLesson("no_world_test", "x"), m.get_pack("coding"))
    assert mut is not None and "FALSIFIER" in mut.candidate.discipline.upper()
    assert m.mutate_from_failure_lesson(bare, m.FailureLesson("clean", "ok"), m.get_pack("coding")) is None
    assert m.failure_lesson_ablation()["earns_keep"] is True


# ── #7 divergent protocol runner ─────────────────────────────────────────────────────────────────────
def test_divergent_runner_keeps_productive_drops_decorative():
    res = m.run_divergent_protocols("a new rate limiter", m.get_pack("coding"))
    assert res.candidates and "scamper" in res.kept
    assert all(str(getattr(c, "discipline", "")).strip() for c in res.candidates)   # every kept candidate falsifiable
    ab = m.protocol_ablation()
    assert ab["earns_keep"] is True and ab["real_kept"] and ab["decorative_dropped"]


# ── #8 real novelty frontier ─────────────────────────────────────────────────────────────────────────
def test_behavioral_novelty_separates_what_text_cannot():
    ab = m.frontier_ablation()
    assert ab["conceptual_identical"] is True                  # identical text → conceptual cannot tell them apart
    assert ab["behavioral_separates"] is True                  # different behavior → behavioral can
    assert ab["earns_keep"] is True


def test_frontier_score_keeps_axes_separate():
    from OUTLIER_MCB.evaluators.base import CallableEvaluator
    class _C:
        name, negation, discipline = "idea", "break the box", "t"
    ev = CallableEvaluator(lambda c: {"score": 1.0, "ok": True}, passed_key="ok")
    fs = m.frontier_score(_C(), evaluator=ev, conceptual_archive=["something else entirely"])
    assert set(fs["axes_measured"]) == {"conceptual", "behavioral"}   # no provider → prior_art axis absent
    assert fs["prior_art"] is None and 0.0 <= fs["frontier"] <= 1.0


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
