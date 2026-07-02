"""test_creative_dimensions — the four creativity dimensions (Points 1-4) are measured externally and protected
by the SAME strict Pareto gate as the hard dimensions: the loop can raise 'invent new universes / meaning /
languages / beauty' but never by regressing any dimension. Deterministic and offline.
"""
import OUTLIER_MCB as gsl
from evals.multi_metric_loop import creative_dimensions, _NEXT_DIMENSIONS


def test_creative_dimensions_are_real_and_registered():
    dims = creative_dimensions()
    assert set(dims) == {"physics_invention", "conceptual_compression", "expressive_power", "elegance"}
    for name, v in dims.items():
        assert 0.0 <= v <= 1.0
        assert name in _NEXT_DIMENSIONS                 # registered as a certified dimension of the loop
    # each measures a real capability (> 0), not a placeholder
    assert dims["physics_invention"] > 0 and dims["conceptual_compression"] > 0
    assert dims["expressive_power"] > 0 and dims["elegance"] > 0


def test_creative_dimensions_are_pareto_gated_with_the_hard_ones():
    # a full profile: hard dimensions + the four creativity dimensions
    base = {"sr_recovery": 0.6, "counterexample": 0.6, **creative_dimensions()}
    # improving a creativity dim while REGRESSING a hard one → rejected (never trade a skill for creativity)
    worse = dict(base); worse["elegance"] = min(1.0, worse["elegance"] + 0.2); worse["sr_recovery"] = 0.5
    assert not gsl.pareto_improves(base, worse)
    # improving a creativity dim with NO regression anywhere → accepted (genuine all-round gain)
    better = dict(base); better["physics_invention"] = min(1.0, better["physics_invention"] + 0.1)
    assert gsl.pareto_improves(base, better)


def test_creativity_never_regresses_a_creativity_dimension_either():
    base = creative_dimensions()
    regress_one = dict(base)
    # pick any creativity dim and regress it while bumping another → the Pareto gate must reject
    regress_one["expressive_power"] = max(0.0, regress_one["expressive_power"] - 0.1)
    regress_one["elegance"] = min(1.0, regress_one["elegance"] + 0.2)
    assert not gsl.pareto_improves(base, regress_one)
