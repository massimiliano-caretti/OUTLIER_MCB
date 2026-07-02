"""test_hardening — harder verification (HiddenEvaluator), better experiments (WorldTestGenerator,
ActiveExperimentSelector), and interestingness. The decisive 'don't self-deceive' batch. Deterministic.
"""
import OUTLIER_MCB as m
from OUTLIER_MCB.generators import Candidate


def _check(cand, case):
    return case in cand["handles"]


# ── #1 HiddenEvaluator (anti-cheating) ────────────────────────────────────────────────────────────────
def test_real_mechanism_passes_hidden_and_fails_negative_control():
    ev = m.HiddenEvaluator(_check, public_cases=[1, 2], hidden_cases=[3, 4], adversarial_cases=[5],
                           negative_controls=[9])
    real = ev.evaluate({"handles": {1, 2, 3, 4, 5}})              # solves hidden+adversarial, fails the control
    assert real.passed is True and real.components["leakage_detected"] == 0.0


def test_overfit_passes_public_but_fails_hidden():
    ev = m.HiddenEvaluator(_check, public_cases=[1, 2], hidden_cases=[3, 4], negative_controls=[9])
    overfit = ev.evaluate({"handles": {1, 2}})                   # only the visible cases
    assert overfit.passed is False and "hidden" in overfit.error


def test_leakage_is_caught_by_negative_control():
    ev = m.HiddenEvaluator(_check, public_cases=[1, 2], hidden_cases=[3, 4], negative_controls=[9])
    leaky = ev.evaluate({"handles": {1, 2, 3, 4, 9}})            # also "solves" the control ⇒ leakage
    assert leaky.passed is False and leaky.components["leakage_detected"] == 1.0


# ── #6 interestingness (new is not enough) ────────────────────────────────────────────────────────────
def test_interestingness_rewards_useful_generative_not_arbitrary():
    good = m.interestingness_score(surprise=0.9, opens_new_question=0.8, mechanism_transfer_distance=0.8,
                                   falsifiability=0.9, usefulness=0.9, arbitrariness=0.0)["interestingness"]
    arbitrary = m.interestingness_score(surprise=0.2, mechanism_transfer_distance=0.9, usefulness=0.0,
                                        falsifiability=0.0, arbitrariness=0.9)["interestingness"]
    assert good > 0.7 and arbitrary < 0.2                        # novel-but-arbitrary scores low


# ── #5 active experiment selection ────────────────────────────────────────────────────────────────────
def test_next_best_experiment_maximizes_information_gain():
    splitting = m.Experiment("discriminating", predicts={"h1": True, "h2": False})     # 50/50 → max info
    agreeing = m.Experiment("useless", predicts={"h1": True, "h2": True})              # all agree → 0
    assert m.expected_information_gain(splitting) == 1.0 and m.expected_information_gain(agreeing) == 0.0
    assert m.next_best_experiment([agreeing, splitting]).name == "discriminating"


# ── #2 world-test generator ───────────────────────────────────────────────────────────────────────────
def test_world_test_generator_full_suite():
    cand = Candidate(name="c", operator="invert", breaks=["FORM"], assumptions=["law_is_separable"],
                     negation="interaction term")
    suite = m.WorldTestGenerator(m.get_pack("numeric")).full_suite("discover the law", cand)
    kinds = {w.kind for w in suite}
    assert kinds == {"baseline_fails", "counterworld", "minimal_falsifier", "scale_shift", "negative_control"}
    neg = next(w for w in suite if w.kind == "negative_control")
    assert "leakage" in neg.falsifier                            # the control catches leakage


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
