"""test_transformation — transformational creativity: the engine grows its own conceptual space.

A genuinely new dimension (far from existing axes) is TRANSFORMATIONAL and yields an EXPANDED, valid pack
the engine can explore; a rephrasing of an existing dimension is rejected as DECORATIVE_AXIS. Deterministic.
"""
import OUTLIER_MCB as gsl


def test_distant_anomaly_becomes_a_new_axis():
    pack = gsl.get_pack("numeric")
    res = gsl.transform_space(pack, anomaly="the run-to-run variance is itself a structured stochastic signal",
                              new_axis="STOCHASTICITY")
    assert res.status == "TRANSFORMATIONAL"
    exp = res.expanded_pack
    assert exp is not None and exp.validate() == []          # the expanded pack is schema-valid
    assert "STOCHASTICITY" in exp.axes
    assert exp.dimension_of[res.assumption_name] == "STOCHASTICITY"
    assert len(exp.assumptions) == len(pack.assumptions) + 1  # the space grew by one dimension
    # the original pack is untouched (registry never mutated)
    assert "STOCHASTICITY" not in gsl.get_pack("numeric").axes


def test_rephrasing_existing_dimension_is_decorative():
    pack = gsl.get_pack("numeric")
    # almost a paraphrase of law_is_separable.if_false ("The inputs are coupled: an irreducible interaction…")
    res = gsl.transform_space(pack, anomaly="the inputs are coupled by an irreducible interaction term signal",
                              new_axis="COUPLING")
    assert res.status == "DECORATIVE_AXIS"
    assert res.expanded_pack is None


def test_expanded_space_is_explorable():
    pack = gsl.get_pack("numeric")
    exp = gsl.transform_space(pack, anomaly="a latent periodic regime switches the law at unknown change-points",
                              new_axis="REGIME_SWITCHING").expanded_pack
    assert exp is not None
    # the engine can now find problems on the dimension it just invented
    port = gsl.find_problems(pack=exp, blend_with=[])
    assert any(p.axis == "REGIME_SWITCHING" for p in port.problems)


def test_propose_transformation_is_honest_and_non_crashing():
    res = gsl.propose_transformation(gsl.get_pack("numeric"))
    assert res.status in gsl.TRANSFORMATION_STATES
    assert res.new_axis


def test_deterministic_and_markdown():
    a = gsl.transform_space(gsl.get_pack("numeric"), "a structured stochastic residual signal", "STOCHASTICITY")
    b = gsl.transform_space(gsl.get_pack("numeric"), "a structured stochastic residual signal", "STOCHASTICITY")
    assert a.status == b.status and a.distance_to_existing == b.distance_to_existing
    assert "Transformation" in a.markdown()


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
