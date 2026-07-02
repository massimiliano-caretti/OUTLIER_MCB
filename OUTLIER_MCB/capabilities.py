"""capabilities — a single, self-describing INDEX of everything the library can do, so an LLM assistant can
drive the WHOLE engine automatically and transparently: one call returns every top-level capability with a
one-line purpose, the entry function to call, and an honest maturity note. This is the map that makes the
library orchestrable without the assistant having to memorise 600 symbols.

`capabilities()` returns structured records; `capabilities_markdown()` renders them for a prompt; the standing
routine (activation.assistant_brief) points here. Every entry names a REAL, exported callable — a test asserts
that, so the index can never drift into advertising something that isn't there.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List

MATURE = "mature"
POC = "proof-of-concept"          # honest: a real, tested mechanism, but on toy domains — not production creativity


@dataclass
class Capability:
    name: str
    category: str
    entry: str                    # the exported callable/class an assistant calls
    summary: str
    maturity: str = MATURE

    def markdown(self) -> str:
        tag = "" if self.maturity == MATURE else f"  _({self.maturity})_"
        return f"- **{self.name}** → `{self.entry}(...)` — {self.summary}{tag}"


_CAPS: List[Capability] = [
    # ── routing / the standing LLM routine ──────────────────────────────────────────────────────────────
    Capability("standing brief", "route", "assistant_brief", "the routine an LLM obeys before answering any new/novel/invent request"),
    Capability("continuous assistant route", "route", "assistant_route", "compact per-turn activation decision for LLMs that call the library continuously"),
    Capability("creative brief", "route", "creative", "break a hidden assumption, get branches-in-tension + the max claim allowed"),
    Capability("capability index", "route", "capabilities", "THIS index — discover every entry point automatically"),
    # ── generate ideas / invent ─────────────────────────────────────────────────────────────────────────
    Capability("invent runtime", "generate", "invent", "the cognitive runtime: escape the box (box_distance × survives_falsification); opt-in taste=, expand_when_stuck="),
    Capability("autonomous loop", "generate", "autonomous", "ONE composed scientific loop: incubate→invent(taste,transform)→settle(red-team,economy)→represent→disambiguate→record"),
    Capability("green-star", "generate", "green_star", "first-principles structure when no pack/examples exist"),
    # ── judge / verify / honesty ───────────────────────────────────────────────────────────────────────
    Capability("judge an idea", "verify", "judge", "INSIDE_THE_BOX vs MUST_BE_AUDITED, with theorem/world-test/maturity"),
    Capability("novelty audit", "verify", "novelty_audit", "classify against real prior art: RENAMED / COLLAGE / NO_PRIOR_ART_FOUND"),
    Capability("claim honesty gate", "verify", "gate_claim_language", "rewrite an over-reaching claim into the strongest HONEST one its evidence licenses"),
    Capability("verification economy", "verify", "VerificationEconomy", "settle more at lower cost via calibrated cheap proxies; never fabricates a pass"),
    Capability("deterministic settlement", "verify", "settle_by_materialization", "close the executive loop WITHOUT an LLM: synthesize a red-first artifact and drive it RED_ASSERTION→repair→GREEN with a binding negative control (certifies the pipeline, not the idea)"),
    Capability("earned taste", "verify", "EarnedTaste", "a learned, calibrated value over UNVERIFIED ideas from settled outcomes"),
    Capability("novelty receipt", "verify", "novelty_receipt", "a serializable, tamper-evident certificate: broken axis + world-test + closure verdict + prior-art scope + max honest claim"),
    Capability("novelty/honesty CI gate", "verify", "assert_outside_the_box", "test primitives that FAIL the build on INSIDE_THE_BOX or an over-reaching claim (see also assert_claim_honest)"),
    Capability("honesty linter", "verify", "lint_text", "scan prose/docs and rewrite scientific over-claims into the strongest honest form (lint_file for files)"),
    Capability("agent handoff contract", "verify", "handoff_contract", "hand a subagent a verifiable contract; accept_handoff GATES its output on substance (broken assumption + world-test + honest claim), only for creative handoffs"),
    # ── make the box legible / compare directions ─────────────────────────────────────────────────────────
    Capability("box map", "generate", "box_map", "make THE BOX legible: the breakable assumption axes + the closure lattice + the only admissible exits, as a diagram"),
    Capability("assumption diff", "generate", "assumption_diff", "compare two ideas by WHICH hidden assumption each breaks and on which axis; name the tension"),
    # ── discovery / math ────────────────────────────────────────────────────────────────────────────────
    Capability("explore (front door)", "discover", "explore", "route → generate → settle externally → audit → one honest report"),
    Capability("autonomous discovery", "discover", "autonomous_discover", "mine an exact oracle for certified structure; report discovery only when externally checked"),
    Capability("math frontier", "discover", "math_frontier", "certified monotone frontier of sub-lemmas + pivot the solution FORM when stuck"),
    Capability("counterexample-cell refinement", "discover", "refine_with_counterexample_cells", "repair disproved conjectures by splitting away from solver counterexamples, then re-check externally"),
    Capability("active experiments", "discover", "run_active_experiments", "ACQUIRE information: run probes, eliminate hypotheses by the world's outcome"),
    Capability("incubation", "discover", "incubate", "offline reconnection of persisted dead-ends & distant wins into fresh conjectures"),
    Capability("representation invention", "discover", "invent_representation", "a new encoding that makes a hard problem easy, gated by a control"),
    # ── the four creativity FRONTIER capabilities (Points 1-4) ─────────────────────────────────────────
    Capability("invent physics", "frontier", "propose_new_physics", "invent a toy universe (lattice law); score emergent structure externally", POC),
    Capability("endogenous meaning", "frontier", "ground_new_symbol", "coin a self-made concept for a recurring pattern; score by MDL compression", POC),
    Capability("invent a language", "frontier", "invent_new_language", "invent a compact primitive-set DSL with a sound interpreter; score by expressive power", POC),
    Capability("aesthetics", "frontier", "elegance_score", "objective AST beauty (simplicity+symmetry); surprise as a separate axis", POC),
    # ── self / health ──────────────────────────────────────────────────────────────────────────────────
    Capability("capability health", "self", "health", "measured operator yield + which symbols earn their keep"),
    Capability("protected invariants", "self", "library_health", "fraction of the 13 honesty invariants that hold (must stay 1.0)"),
]


def capabilities() -> List[Capability]:
    """Every top-level capability, as structured records — the self-describing index an LLM drives the library
    from. Each `entry` is a real exported symbol (a test asserts it)."""
    return list(_CAPS)


def capabilities_markdown() -> str:
    """The index rendered for a prompt, grouped by category — what an assistant reads to orchestrate the engine."""
    order = ["route", "generate", "verify", "discover", "frontier", "self"]
    titles = {"route": "Routing (start here)", "generate": "Generate / invent", "verify": "Judge / verify / honesty",
              "discover": "Discovery / math / experiments", "frontier": "Creativity frontier (Points 1-4, proof-of-concept)",
              "self": "Self / health"}
    lines = ["# OUTLIER_MCB — capability index (drive the whole engine from here)"]
    for cat in order:
        lines.append(f"\n## {titles[cat]}")
        lines += [c.markdown() for c in _CAPS if c.category == cat]
    lines.append("\nHonesty: every claim of novelty needs an external resolver + prior-art check; the four "
                 "frontier capabilities are proof-of-concept on toy domains, not production creativity.")
    return "\n".join(lines)
