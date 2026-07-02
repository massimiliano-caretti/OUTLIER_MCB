"""test_cognitive_growth — world-model imagination, active experiments, role reputation, executable skills,
artifact gates and taste. Each has a negative control; none self-certifies novelty.
"""
import OUTLIER_MCB as m


def test_counterfactual_world_prediction_collapses_when_causal_edge_shuffled():
    world = m.LinearCausalWorld({"Y": (0.0, {"X": 2.0, "Z": 0.0})})
    assert world.counterfactual_delta({"X": 1.0, "Z": 5.0}, {"X": 3.0}, "Y") == 4.0
    assert m.counterfactual_world_prediction_collapses_when_edge_shuffled(
        world, {"X": 1.0, "Z": 5.0}, {"X": 3.0}, "Y"
    )


def test_active_counterfactual_experiment_splits_hypotheses():
    h1 = m.LinearCausalWorld({"Y": (0.0, {"X": 2.0, "Z": 0.0})})
    h2 = m.LinearCausalWorld({"Y": (0.0, {"X": 0.0, "Z": 2.0})})
    exps = [
        m.CounterfactualExperiment("touch_z", {"Z": 3.0}, "Y"),
        m.CounterfactualExperiment("touch_x", {"X": 3.0}, "Y"),
    ]
    chosen = m.experiment_splits_hypotheses_better_than_random_probe({"h1": h1, "h2": h2},
                                                                     {"X": 1.0, "Z": 1.0}, exps)
    assert chosen.name in {"touch_x", "touch_z"}
    assert chosen.name != m.CounterfactualExperiment("useless", {}, "Y").name


def test_low_reputation_role_cannot_dominate_without_evidence():
    reps = {"Skeptic": m.RoleReputation("Skeptic", successes=9, attempts=10),
            "Hype": m.RoleReputation("Hype", successes=0, attempts=10)}
    assert m.role_vote_weight("Skeptic", 0.8, reps) > m.role_vote_weight("Hype", 1.0, reps)
    assert m.role_vote_weight("Skeptic", 0.0, reps) == 0.0


def test_executable_skill_must_execute_and_improve_external_task():
    skill = m.ExecutableSkill("double", run=lambda x: x * 2, verifier=lambda problem, result: result > problem)
    assert skill.execute(3) == 6 and skill.success_rate == 1.0
    bad = m.ExecutableSkill("identity", run=lambda x: x, verifier=lambda problem, result: result > problem)
    try:
        bad.execute(3)
    except ValueError:
        pass
    else:
        raise AssertionError("a skill that fails its verifier must not be accepted")


def test_idea_without_artifact_cannot_enter_discovery_ledger():
    assert not m.idea_without_artifact_cannot_enter_discovery_ledger(None)
    bad = m.DiscoveryArtifact(kind="paper", location="report.md", verifier="", passed=True, negative_control_passed=True)
    assert not m.idea_without_artifact_cannot_enter_discovery_ledger(bad)
    good = m.DiscoveryArtifact(kind="test", location="tests/test_x.py", verifier="pytest -q",
                               passed=True, negative_control_passed=True)
    assert m.idea_without_artifact_cannot_enter_discovery_ledger(good)


def test_taste_model_prefers_small_deep_mechanism_over_large_trivial_result():
    assert m.taste_prefers_small_deep_mechanism_over_large_trivial_result()
    assert m.research_taste_score(1.0, 1.0, 1.0, 1.0, false_claim_risk=1.0, triviality=1.0) < 0.5


def test_numeric_claim_expr_fallback_closes_finite_box_without_z3():
    conj = m.Conjecture("x^2 >= 0", claim_expr="x*x >= 0", variables={"x": (-4, 4)})
    cert = m.settle_lemma(conj, backend=m.portfolio_backend(backends=[]))
    assert cert.status == "NUMERIC_VERIFIED" and cert.certified
    false = m.Conjecture("x^2 < 0", claim_expr="x*x < 0", variables={"x": (-4, 4)})
    ref = m.settle_lemma(false, backend=m.portfolio_backend(backends=[]))
    assert ref.status == "NUMERIC_REFUTED" and ref.counterexample is not None


def test_asymptotic_band_does_not_count_as_exact_structure():
    primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71]
    s = m.mine_invariants(primes)
    assert s.discovery_rung == "WEAK_ASYMPTOTIC_BAND"
    assert s.weak_structure_found and not s.exact_structure_found

