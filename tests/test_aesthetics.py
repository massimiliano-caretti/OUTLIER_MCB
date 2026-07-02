"""test_aesthetics — Point 4: intrinsic motivation toward BEAUTY, measured objectively on the artifact's AST.
Beauty is measured (symmetry/simplicity/surprise), never asserted; elegance enters as a strict Pareto dimension
that never buys a performance regression. Deterministic and offline.
"""
import OUTLIER_MCB as gsl
from OUTLIER_MCB.aesthetics import (measure_symmetry, measure_simplicity, elegance_score,
                                       aesthetics_objectivity_pass)


def test_symmetry_is_real():
    assert measure_symmetry("a + b") == 1.0        # symmetric under swapping a,b
    assert measure_symmetry("a - b") == 0.0        # not symmetric
    assert 0.0 < measure_symmetry("a*b + c") < 1.0 # partially symmetric


def test_simplicity_rewards_terseness():
    assert measure_simplicity("m*c**2") > measure_simplicity("m*c*c + 0*m + m - m")


def test_beauty_beats_clumsy_equivalent():
    corpus = ["a+b", "a*b", "x-y"]
    assert elegance_score("m*c**2", corpus)["elegance"] > elegance_score("m*c*c + 0*m + m - m", corpus)["elegance"]


def test_scores_are_deterministic():
    assert elegance_score("a*b + c") == elegance_score("a*b + c")     # pure function, no hidden state


def test_aesthetics_objectivity_is_a_protected_invariant():
    from OUTLIER_MCB.self_repair import verify_invariants, INVARIANT_REGISTRY
    assert "aesthetics_are_objective" in INVARIANT_REGISTRY
    rep = verify_invariants()
    assert rep.ok and "aesthetics_are_objective" in rep.passed_names


# ── the crucial correction: elegance is a Pareto dimension, it does NOT loosen the no-regression gate ──
def test_elegance_never_buys_a_regression():
    base = {"accuracy": 0.8, "elegance": 0.3}
    assert not gsl.pareto_improves(base, {"accuracy": 0.7, "elegance": 0.9})   # prettier but worse → rejected
    assert gsl.pareto_improves(base, {"accuracy": 0.8, "elegance": 0.5})       # same acc, more elegant → accepted
    from OUTLIER_MCB.self_repair import verify_invariants
    assert "elegance_never_buys_a_regression" in verify_invariants().passed_names


def test_elegance_dimension_benchmark():
    from evals.benchmarks.aesthetics import elegance_dimension_score, controls_pass
    assert controls_pass() is True
    assert 0.0 <= elegance_dimension_score() <= 1.0
