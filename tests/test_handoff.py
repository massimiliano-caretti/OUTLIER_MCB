"""test_handoff — the AgentHandoffContract. The acceptance gate must reject on SUBSTANCE (not field presence),
apply ONLY to creative handoffs, and carry the route context. Offline, deterministic, additive (no core path).
"""
import OUTLIER_MCB as m

_SHARP = ("an agent handoff is invalid unless its acceptance gate rejects the subagent output when it fails to "
          "prove a broken assumption and a world-test (substance checked by judge, not field presence)")


def test_contract_carries_route_context_and_required_fields():
    c = m.handoff_contract("make disciplined creativity non-optional across agent handoffs", creative=True)
    assert c["creative"] is True and c["acceptance"] == "substance"
    assert "route_snapshot" in c and c["route_snapshot"]["prompt"]        # condition 1: context travels
    for f in ("idea", "broken_assumption", "world_test", "claim"):
        assert f in c["must_report"]


def test_gate_rejects_bureaucratic_output_on_substance():
    # every field filled, but the idea is INSIDE_THE_BOX and the claim over-reaches → rejected on SUBSTANCE
    c = m.handoff_contract("invent a new pooling", creative=True)
    r = m.accept_handoff({"idea": "R = mean(e) over the bag", "broken_assumption": "we say so",
                          "world_test": "we say so", "claim": "a breakthrough novel first"}, c)
    assert r["accepted"] is False
    assert any("INSIDE_THE_BOX" in x for x in r["reasons"]) and any("over-claim" in x for x in r["reasons"])


def test_gate_rejects_missing_fields():
    c = m.handoff_contract("invent a new pooling", creative=True)
    r = m.accept_handoff({"idea": _SHARP, "broken_assumption": "x"}, c)   # missing world_test + claim
    assert r["accepted"] is False and any("missing required field" in x for x in r["reasons"])


def test_gate_accepts_substantive_output_and_attaches_verifiable_receipt():
    c = m.handoff_contract("make disciplined creativity non-optional across agent handoffs", creative=True)
    good = {"idea": _SHARP, "broken_assumption": "subagent_success = task_completion",
            "world_test": "feed a filled-but-average output; the gate must reject it",
            "claim": "a candidate protocol worth auditing"}     # claim calibrated to evidence (no unearned words)
    r = m.accept_handoff(good, c)
    assert r["accepted"] is True and r["receipt"] is not None
    assert m.verify_receipt(r["receipt"]) is True


def test_non_creative_handoff_bypasses_the_gate():
    # a routine sub-task must NOT be forced through the novelty bar (anti-bureaucracy scoping)
    c = m.handoff_contract("reformat this JSON file", creative=False)
    r = m.accept_handoff({}, c)
    assert r["accepted"] is True and r["skipped"] is True


def test_gate_rejects_garbage_substance_fields_even_with_a_valid_idea():
    # THE DANGEROUS BYPASS: a genuinely out-of-box idea but placeholder broken_assumption + world_test.
    # substance is on the FIELDS, not just the idea — this must be rejected.
    c = m.handoff_contract("make disciplined creativity non-optional across agent handoffs", creative=True)
    r = m.accept_handoff({"idea": _SHARP, "broken_assumption": "x", "world_test": "x",
                          "claim": "a candidate protocol worth auditing"}, c)
    assert r["accepted"] is False
    assert any("broken_assumption" in x for x in r["reasons"])
    assert any("world_test" in x for x in r["reasons"])


def test_world_test_validator_requires_a_kill_condition():
    assert m.validate_world_test("x") is False
    assert m.validate_world_test("we say there is a test") is False        # no falsification condition
    assert m.validate_world_test("baseline LRU; the policy is rejected if its hit-rate is no better than LRU") is True


def test_broken_assumption_validator_rejects_placeholders():
    idea = "the subagent output is invalid unless it proves a broken assumption"
    assert m.validate_broken_assumption("x", idea) is False
    assert m.validate_broken_assumption("we say so", idea) is False        # only stop-words
    assert m.validate_broken_assumption("subagent_success = task_completion", idea) is True


def test_forced_creative_flag_when_override_conflicts_with_router():
    # parent forces creative on a request the router would not activate → recorded transparently
    c = m.handoff_contract("reformat this JSON file", creative=True)
    assert c["creative"] is True and c["route_snapshot"]["forced_creative"] is True
    # default (creative=None) derives from the router, so no forced flag
    c2 = m.handoff_contract("reformat this JSON file")
    assert c2["route_snapshot"]["forced_creative"] is False
