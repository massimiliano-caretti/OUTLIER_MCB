"""instruction_emitter — turn a preflight result into SHORT instructions for an AI assistant.

The output is meant to be read by a coding assistant (in VS Code or elsewhere) right before it
answers a "invent something new" request, so it answers from method, not from the average of its
training memory. Fully domain-agnostic: every domain-specific phrase comes from the pack via the
preflight dict (box_name, breaks, families), never hard-coded.
"""
from __future__ import annotations
from typing import Dict


def emit_assistant_instructions(preflight: Dict) -> str:
    """preflight: the dict returned by kernel.preflight / preflight_creative_request."""
    box = preflight.get("box_name", "the most-probable solution from training memory")
    breaks = preflight.get("three_breaks", [])
    rec = preflight.get("recommended_direction", {})
    forbid = preflight.get("must_not_propose", [])
    L = ["[OUTLIER_MCB preflight — read before answering a 'create something new' request]",
         f"1. Do NOT propose standard solutions from memory. This problem is closed in the box: {box}.",
         "2. Any idea that stays inside that box MUST be labelled INSIDE_THE_BOX and is not an answer.",
         "3. The most promising assumptions to BREAK (with their exit axis):"]
    for b in breaks[:3]:
        L.append(f"     - {b['assumption']}  → break {b['dimension']}  ({b['why']})")
    if rec:
        L.append(f"4. Recommended direction: BREAK {rec.get('assumption')} ({rec.get('dimension')}) — {rec.get('reason')}.")
    if forbid:
        L.append(f"5. Forbidden because they are collage / known-dead: {', '.join(forbid)}.")
    L += ["6. Before proposing ANY solution, compile: which assumption it breaks · which known family can't do it ·",
          "   which new output · which new data · which world-test separates it. If you can't → INSIDE_THE_BOX.",
          "7. Then: write the theorem sketch, design the world-test, run the collision audit, and only THEN a SPEC.",
          "7b. Make the world-test RED-FIRST and RUNNABLE — state it as a concrete artifact contract:",
          "    · a NAMED test (e.g. `test_<broken_axis>_<claim>`) that is RED today;",
          "    · the file/target to touch and what the box currently FAILS or lacks (the baseline);",
          "    · the NEGATIVE CONTROL: the perturbation that must make the test FAIL (so it tests the axis, not noise);",
          "    · the exact COMMAND that runs THAT test (e.g. `pytest -k <test_name>`), not the whole suite."]
    L.append(f"8. Death-gate: {preflight.get('death_gate', '')}")
    mi = preflight.get("missing_information") or {}
    if mi.get("data_insufficient"):
        L.append(f"9. ⚠ Information-limited: {mi.get('recommended_first')} is likely required — "
                 f"a new combination of known mechanisms cannot raise the ceiling.")
    return "\n".join(L)
