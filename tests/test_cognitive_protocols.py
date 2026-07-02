"""test_cognitive_protocols — Geneplore/SCAMPER/fixedness/remote-association as measurable creativity moves.

These tests lock the cognitive-science additions to behavior: they must generate falsifiable, diverse
candidates and feed the evolution loop only as seeds that still need objective evaluation.
"""
import OUTLIER_MCB as m


def test_scamper_generates_seven_falsifiable_moves():
    pack = m.get_pack("numeric")
    moves = m.scamper("discover a non-obvious law", pack)
    assert len(moves) == 7
    assert {x.move for x in moves} >= {"substitute", "combine", "eliminate", "reverse"}
    assert all(x.candidate.discipline for x in moves)
    assert all(x.candidate.operator.startswith("scamper_") for x in moves)


def test_functional_fixedness_breaker_blocks_known_family_use():
    pack = m.get_pack("coding")
    moves = m.functional_fixedness_breaker("invent a new rate limiter", pack)
    assert moves
    first = moves[0]
    assert first.protocol == "Fixedness"
    assert "forbid" in first.candidate.negation.lower()
    assert "disabled" in first.candidate.discipline.lower()


def test_remote_association_forces_distant_triad_and_negative_control():
    pack = m.get_pack("coding")
    moves = m.remote_association(
        "invent an adaptive limiter", pack,
        cues=["ecology:carrying capacity", "music:syncopation", "law:precedent"]
    )
    assert len(moves) == 1
    cand = moves[0].candidate
    assert cand.operator == "remote_association"
    assert "ecology" in cand.negation and "music" in cand.negation and "law" in cand.negation
    assert "bridge_negative_control" in cand.needs


def test_cognitive_extremes_has_protocol_flexibility_and_falsifiability():
    res = m.cognitive_extremes("invent a non-obvious causal discovery method", pack=m.get_pack("causal"))
    protocols = {x.protocol for x in res.moves}
    assert {"SCAMPER", "Geneplore", "Fixedness", "RemoteAssociation"} <= protocols
    assert res.scores["protocol_flexibility"] == 1.0
    assert res.scores["falsifiability"] == 1.0
    assert len({c.name for c in res.candidates}) == len(res.candidates)


def test_evolve_can_use_cognitive_protocol_seeds_without_default_regression():
    task = m.symbolic_invention_task()
    res = m.evolve_invention(task["problem"], task["evaluator"], budget=12, pack=task["pack"],
                             cognitive_protocols=True)
    ops = {r.mutation_operator for r in res.memory.all()}
    assert any(op.startswith("scamper_") or op.startswith("geneplore_") or op == "remote_association"
               for op in ops)
    assert all(r.evaluator_name for r in res.memory.all())

