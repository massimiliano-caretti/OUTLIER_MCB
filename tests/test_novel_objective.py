"""test_novel_objective -- novelty as an objective, with honesty caps.

World-test: the old box can score task quality, but has no single objective that
prefers frontier movement while refusing "novel/verified" language when external
settlement, controls, or online prior art are missing.

Negative control: remove controls_collapse or make the prior-art provider local;
the score and claim language must collapse.
"""
import OUTLIER_MCB as gsl
from OUTLIER_MCB.generators import Candidate
from OUTLIER_MCB.prior_art import OnlinePriorArtProvider, PriorArtResult


class _WorldEvaluator(gsl.BaseEvaluator):
    name = "world"
    is_correctness = True
    settles_externally = True

    def __init__(self, controls=True, shape=0.0):
        self.controls = controls
        self.shape = shape

    def _run(self, candidate, workspace=None):
        return gsl.EvaluationResult(
            passed=True,
            score=0.9,
            components={"controls_collapse": 1.0 if self.controls else 0.0, "shape": self.shape},
        )


class _FarOnline(OnlinePriorArtProvider):
    name = "far_online"

    def _fetch(self, query):
        return [PriorArtResult("sourdough notes", summary="flour water salt", url="https://example.test/a")]


def _candidate():
    return Candidate(
        name="orthogonal_pythagoras_frontier",
        operator="invert",
        breaks=["OBJECTIVE"],
        assumptions=["objective_is_given"],
        negation="optimize for verified frontier movement instead of task loss alone",
        discipline="controls_collapse must be present; online prior-art must bound novelty",
    )


def test_objective_break_refuses_novelty_language_without_online_prior_art():
    ev = gsl.novelty_objective(_WorldEvaluator(controls=True))
    res = ev.evaluate(_candidate())
    assert res.passed is True
    assert res.artifacts["novelty_scope"] == "LOCAL_ONLY"
    assert any("online_prior_art_missing" in c for c in res.artifacts["caps"])
    gate = res.artifacts["claim_gate"]
    assert gate["allowed"] is False
    assert "verified" in gate["rewritten"]
    assert "novel discovery" not in gate["rewritten"].lower()


def test_behavioral_frontier_separates_identical_text_when_behavior_changes():
    c = _candidate()
    same_text = f"{c.name} {c.negation} {c.discipline}"
    prior_behavior = (True, (("controls_collapse", 1.0), ("shape", 0.0)))
    provider = gsl.CompositePriorArtProvider([_FarOnline()])
    ev = gsl.novelty_objective(
        _WorldEvaluator(controls=True, shape=1.0),
        provider=provider,
        conceptual_archive=[same_text],
        behavioral_archive=[prior_behavior],
    )
    res = ev.evaluate(c)
    assert res.components["conceptual_novelty"] < 0.2
    assert res.components["behavioral_novelty"] > res.components["conceptual_novelty"]
    assert res.components["prior_art_novelty"] > 0.8
    assert res.artifacts["novelty_scope"] == "ONLINE_PRIOR_ART_CHECKED"


def test_negative_control_missing_caps_frontier_win():
    c = _candidate()
    provider = gsl.CompositePriorArtProvider([_FarOnline()])
    with_controls = gsl.novelty_objective(_WorldEvaluator(controls=True), provider=provider).evaluate(c)
    without_controls = gsl.novelty_objective(_WorldEvaluator(controls=False), provider=provider).evaluate(c)
    assert with_controls.score > without_controls.score
    assert without_controls.passed is False
    assert any("negative_control" in cap for cap in without_controls.artifacts["caps"])


def test_explore_can_use_novelty_objective_without_overclaiming():
    report = gsl.explore("invent a stranger verified rate limiter", objective="novelty", budget=3)
    assert report.mode == "invention"
    assert "PROVISIONAL" in report.statement
    assert "insufficient evidence" in report.statement
    assert report.verified is False


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
