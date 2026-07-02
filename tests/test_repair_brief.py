"""The repair INTERVIEW — the LLM queries the library for WHAT/HOW to fix + the constraints, before patching.

The patch is the LLM's, but it must first interview the library (repair_brief): the bottleneck, candidate
levers, and the hard constraints (protected invariants + never-regress). The LLM then proposes; the gate in
evolutionary_self_repair enforces the very constraints the brief listed.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import OUTLIER_MCB as gsl
from OUTLIER_MCB.self_diagnosis import DiagnosticMemory, diagnostic_run
from OUTLIER_MCB.self_repair import (repair_brief, evolutionary_self_repair, RepairProposal,
                                        ProtectedInvariant, INVARIANT_REGISTRY)


def _memory_with_bottleneck():
    mem = DiagnosticMemory()
    with diagnostic_run("task", memory=mem) as log:
        log.ok("generation", "ok")
        log.bottleneck("settlement", "solver timed out")
        log.failed("settlement", "no external certificate")
        log.mark_completed(False)
    return mem


def test_brief_tells_what_to_fix_and_the_constraints():
    brief = repair_brief(_memory_with_bottleneck())
    assert not brief.healthy
    assert brief.bottleneck == "settlement"
    assert brief.levers                                           # WHAT to try
    # the CONSTRAINTS are the real protected invariants — the LLM is told what it may never break
    assert any("never_proves_open_conjecture" in m for m in brief.must_hold)
    assert any("agnostic_certificates" in m for m in brief.must_hold)
    assert len(brief.must_hold) == len(INVARIANT_REGISTRY)
    assert "does not regress" in brief.acceptance_rule
    assert isinstance(brief.to_dict(), dict)


def test_healthy_memory_yields_nothing_to_repair():
    mem = DiagnosticMemory()
    with diagnostic_run("clean", memory=mem) as log:
        log.ok("gen", "ok"); log.mark_completed(True)
    assert repair_brief(mem).healthy


def test_constraints_in_the_brief_are_actually_enforced():
    """An LLM that respects the brief's constraints gets its fix kept; one that violates a constraint is blocked
    by the SAME gate — proving the interview's constraints are real, not advisory."""
    h = {"flag": True, "metric": 0.5}
    invs = [ProtectedInvariant("flag_true", lambda: (h["flag"], "must stay True"), "a solid behavior")]
    brief = repair_brief(_memory_with_bottleneck(), invariants=invs)
    assert any("flag_true" in m for m in brief.must_hold)         # the brief lists the constraint

    # LLM proposal A: respects the constraint, improves the metric → accepted
    good = RepairProposal("respects-constraints", apply=lambda: h.__setitem__("metric", 0.9),
                          rollback=lambda: h.__setitem__("metric", 0.5))
    assert evolutionary_self_repair(good, measure=lambda: h["metric"], invariants=invs).accepted

    # LLM proposal B: violates the listed constraint → rejected + rolled back by the gate
    def bad_apply():
        h["flag"] = False
        h["metric"] = 0.99
    bad = RepairProposal("violates-constraint", apply=bad_apply,
                         rollback=lambda: (h.__setitem__("flag", True), h.__setitem__("metric", 0.9)))
    res = evolutionary_self_repair(bad, measure=lambda: h["metric"], invariants=invs)
    assert not res.accepted and "flag_true" in res.broken_invariants and h["flag"] is True
