"""test_first_principles_reviewer — proposal #2: critique beyond the pack's known families.

The pack-bound reviewer.attack() is silent on an axis the pack does not model. first_principles_attack()
reads the claim's own logic and raises a falsifiable objection there anyway — and judge() can attach it
opt-in WITHOUT changing the standard verdict (non-regression).
"""
import OUTLIER_MCB as gsl


def test_performance_claim_raises_unmodeled_cost():
    crit = gsl.first_principles_attack("a faster cache that reduces latency for every request")
    dims = crit.dimensions()
    assert "UNMODELED_COST" in dims                       # the hidden axis a 'faster' claim pays on
    assert "COUNTEREXAMPLE" in dims                       # 'every request' is a universal
    cost = next(o for o in crit.objections if o.dimension == "UNMODELED_COST")
    assert "latency" in cost.world_test or "memory" in cost.world_test or "$" in cost.world_test


def test_robustness_claim_raises_perturbation():
    crit = gsl.first_principles_attack("a provably robust parser that is always correct")
    assert "PERTURBATION" in crit.dimensions()


def test_negation_floor_is_always_present():
    # even a claim that triggers no lens still gets one concrete way to die.
    crit = gsl.first_principles_attack("a widget")
    assert "NEGATION" in crit.dimensions()
    assert crit.objections[-1].dimension == "NEGATION"


def test_goes_beyond_the_pack_axes():
    # the whole point: it raises a dimension the pack does not model.
    pack = gsl.get_pack("numeric")
    crit = gsl.first_principles_attack("a better, faster method that outperforms the baseline")
    beyond = set(crit.dimensions()) - set(pack.axes)
    assert beyond                                         # at least one objection axis the pack lacks


# ── judge integration: opt-in, non-regressive ──────────────────────────────────────────────────────
def test_judge_default_is_unchanged():
    j = gsl.judge("measure rate by request cost instead of time window", prompt="a rate limiter")
    assert j.first_principles is None
    assert "First-principles reviewer" not in j.markdown()


def test_judge_opt_in_attaches_critique():
    j = gsl.judge("a faster limiter that always blocks abuse", prompt="a rate limiter", first_principles=True)
    assert j.first_principles is not None
    assert "First-principles reviewer" in j.markdown()
    assert "NEGATION" in j.first_principles.dimensions()


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
