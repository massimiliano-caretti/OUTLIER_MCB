"""test_pack_induction — #1 DomainPack self-induction. The engine induces a falsifiable conceptual space
from a problem (and optional repo/data/prior-art) instead of depending on a hand-written pack. Offline,
deterministic. Includes the ablation that proves induction is not decorative."""
import dataclasses
import OUTLIER_MCB as m


_PROBLEM = "design a fairer matchmaking system for an online multiplayer game where skill and latency interact"


def test_infers_at_least_three_falsifiable_assumptions_with_no_pack():
    pack = m.infer_domain_pack(_PROBLEM)
    assert len(pack.assumptions) >= 3
    assert all(a.falsifier and len(a.falsifier.split()) >= 4 for a in pack.assumptions)  # every one falsifiable
    assert len(pack.axes) >= 3                                  # multiple independent breakable axes
    assert m.validate_inferred_pack(pack) == []                # fit to attack with


def test_rejects_an_assumption_without_a_falsifier():
    pack = m.infer_domain_pack(_PROBLEM)
    broken = dataclasses.replace(pack, assumptions=pack.assumptions +
                                 [m.Assumption("no_falsifier", "a claim with no test", "", "", falsifier="")])
    issues = m.validate_inferred_pack(broken)
    assert any("no_falsifier" in i for i in issues)            # an unfalsifiable assumption is not usable


def test_induction_beats_generic_and_a_decorative_pack_on_divergence():
    ab = m.pack_induction_ablation(_PROBLEM)
    assert ab["induction_beats_generic"] is True               # more independent break-directions than generic
    assert ab["induction_beats_decorative"] is True            # and far more than a 1-axis decorative pack
    assert ab["inferred_divergence"] > ab["decorative_divergence"]


def test_prior_art_provider_seeds_known_families():
    prov = m.CallableProvider(lambda q: {"matches": [{"title": "Elo rating system", "url": "u"},
                                                     {"title": "TrueSkill ranking", "url": "u2"}]})
    pack = m.infer_domain_pack(_PROBLEM, provider=prov)
    assert pack.known_families and any("elo" in f for f in pack.known_families)


def test_expand_with_discovered_assumptions_requires_falsifiers():
    pack = m.infer_domain_pack(_PROBLEM)
    n0 = len(pack.assumptions)
    evidence = {"assumptions": [
        {"name": "queue_time_is_free", "description": "queue time has no cost", "why_obvious": "ignored",
         "if_false": "long queues drive players away", "falsifier": "show players leave when queue time crosses a threshold", "axis": "COST"},
        {"name": "no_falsifier_here", "description": "x", "falsifier": ""}],   # dropped: no falsifier
        "anomalies": ["high-skill players report unfair losses against low-latency opponents"],
        "known_families": ["glicko"]}
    grown = m.expand_pack_with_discovered_assumptions(pack, evidence)
    names = {a.name for a in grown.assumptions}
    assert "queue_time_is_free" in names and "no_falsifier_here" not in names   # falsifier required
    assert any(n.startswith("unexplained_anomaly") for n in names)              # anomaly → falsifiable assumption
    assert "glicko" in grown.known_families and len(grown.assumptions) > n0


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
