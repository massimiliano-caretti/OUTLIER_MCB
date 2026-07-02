"""test_problem_finding — the engine proposes WHICH problems are worth attacking (the creative spark).

worth is a falsifiable priority built from cascade leverage, information-frontier, non-saturation and
centrality; saturated axes are penalized; cross-domain blends surface problems neither domain poses.
Deterministic.
"""
import OUTLIER_MCB as gsl
from OUTLIER_MCB.core import Assumption


def test_finds_ranked_problems_in_a_domain():
    port = gsl.find_problems(pack=gsl.get_pack("numeric"), blend_with=[])
    assert port.problems
    worths = [p.worth for p in port.problems]
    assert worths == sorted(worths, reverse=True)            # ranked best-first
    for p in port.problems:
        assert 0.0 <= p.worth <= 1.0 and p.question and p.why_worth and p.settles


def test_saturated_axis_is_penalized():
    base = gsl.DomainPack(
        name="pf_probe", keywords=["pf probe"], box_name="box",
        assumptions=[Assumption("a1", "A.", "obv.", "not A here.", ["fam"], "kill A with a real construction"),
                     Assumption("a2", "B.", "obv.", "not B here.", ["fam"], "kill B with a real construction")],
        relations=[("a1", "if_false_requires", "info1", "n"), ("a2", "if_false_requires", "info1", "n")],
        dimension_of={"a1": "X", "a2": "Y"},
        axes={"X": {"priority": 3, "verdict": "v"}, "Y": {"priority": 3, "verdict": "v"}},
        box_assumptions={"a1", "a2"}, known_families=["fam"], info_kinds={"info1": "why"},
        failure_memory={"dead": {"status": "DEAD_COLLAPSED", "axis": "Y"}}, world_factory=None)
    port = gsl.find_problems(pack=base, blend_with=[])
    worth = {p.seed: p.worth for p in port.problems}
    assert worth["a1"] > worth["a2"]                         # a2 sits on the saturated axis Y → lower worth


def test_cross_domain_blend_problems_appear():
    port = gsl.find_problems(pack=gsl.get_pack("numeric"), blend_with=["causal"])
    blends = [p for p in port.problems if p.domain.startswith("blend:")]
    # a blend may or may not top the ranking, but with a distant domain it should be among the candidates
    full = gsl.find_problems(pack=gsl.get_pack("numeric"), blend_with=["causal"], k=99)
    assert any(p.domain == "blend:numeric⊕causal" for p in full.problems)
    assert all(0.0 <= p.worth <= 1.0 for p in full.problems)


def test_deterministic():
    a = [p.seed for p in gsl.find_problems(pack=gsl.get_pack("numeric"), blend_with=["causal"], k=99).problems]
    b = [p.seed for p in gsl.find_problems(pack=gsl.get_pack("numeric"), blend_with=["causal"], k=99).problems]
    assert a == b


def test_markdown_renders():
    assert "Problem-finding" in gsl.find_problems(pack=gsl.get_pack("numeric"), blend_with=[]).markdown()


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
