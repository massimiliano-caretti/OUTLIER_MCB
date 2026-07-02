"""goal_setter — the INTRINSIC goal-setter: read the QD map, then ask for a world-test that fills a gap.

Literature: the open-endedness line — Lehman & Stanley's Novelty Search, the POET co-evolution of agents
and environments (Wang et al. 2019), and intrinsically-motivated goal exploration. The shared idea: a
system that keeps improving does not chase one fixed objective; it INVENTS its own next goal from where it
is currently weak or unexplored. Here the QD map (qd.QDArchive) is the record of where we are strong, and
its empty cells are where we are blind — so the next goal is "find a falsifiable idea that lands in an empty
region", which keeps the search expanding instead of polishing one corner.

This module does not call any model. It builds the PROMPT that a coding assistant (e.g. Claude in the
editor) answers, turning the map's gaps into a concrete, executable world-test request.

Collaborators: qd.QDArchive (the map of what exists and what is missing), pack (the axes/box vocabulary).
"""
from __future__ import annotations


def propose_goal(archive, pack) -> str:
    """Construct a goal-setting prompt from the current QD map. It states (1) where we already have strong,
    diverse solutions, (2) the unexplored / weak regions of the map, and (3) the ask: a NEW executable
    world-test that forces a solution into one of those empty regions. `archive` is a qd.QDArchive.

    The returned string is meant to be handed to an LLM; the model's reply (a world-test SPEC) becomes the
    next thing the engine tries to fill — the open-ended loop."""
    filled = archive.filled_descriptors() if archive is not None else []
    empty = archive.empty_regions() if archive is not None else []
    box = getattr(pack, "box_name", "the domain")
    axes = ", ".join(pack.axes.keys()) if pack is not None else "the domain's axes"

    lines = ["[OUTLIER_MCB intrinsic goal-setter — read the map, then set the next goal]",
             f"Domain box: {box}.  Breakable axes: {axes}.",
             "",
             "We already have high-quality, DIVERSE solutions for these structural kinds of idea:"]
    if filled:
        for d in filled[:8]:
            lines.append(f"  • {d['abstraction'] or 'mixed'} / {d['complexity']}-complexity, breaking "
                         f"{d['breaks'] or ['—']} → «{d['candidate']}» (quality {d['quality']})")
    else:
        lines.append("  • (the map is empty — any first falsifiable idea expands it)")

    lines += ["",
              "We have NO good idea yet for these unexplored regions of the map:"]
    if empty:
        for d in empty[:6]:
            lines.append(f"  • a {d['abstraction']}-level, {d['complexity']}-complexity idea that breaks "
                         f"{d['breaks']}")
    else:
        lines.append("  • (the map is saturated for the current behavior dimensions)")

    target = empty[0] if empty else None
    ask_region = (f"a {target['abstraction']}-level idea that breaks {target['breaks']}"
                  if target else "any region the map has not yet filled")
    lines += ["",
              "GOAL — propose a NEW, executable world-test that FORCES us to find a solution for "
              f"{ask_region}.",
              "Requirements for the world-test (it must be able to DIE):",
              "  1. specific & measurable: name the artifact, the metric, and the pass/fail threshold;",
              "  2. red-first: state what the current code/box fails or lacks TODAY (the baseline);",
              "  3. a negative control: the perturbation that must make the test FAIL, proving it tests the",
              "     broken axis and not noise;",
              "  4. it must require an idea that lands in the target region above — not a re-skin of an idea",
              "     we already have on the map.",
              "Return only the world-test SPEC."]
    return "\n".join(lines)
