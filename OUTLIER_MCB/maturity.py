"""maturity — separate COHERENCE from VALUE, and PROPOSING from CERTIFYING.

Surfaced by applying the engine to its own residual box. Three honesty fixes the bare survive/die
ladder lacked:

  survival_equals_value  → survival certifies coherence, not reach. We score reach (severe, independent
                           predictions) and fecundity (new questions opened) as SEPARATE axes.
  testable_now_or_dead   → a bold idea with no executable world-test today is SUSPENDED_BOLD, not killed;
                           we record what would make it testable (the Eddington field).
  engine_builds_own_arena→ winning on the world you designed proves little; we distinguish WON_ON_OWN_WORLD
                           from WON_ON_FOREIGN_WORLD (a transfer test on another idea's arena).

This is the discipline that keeps the richer generator (the generators package) from drifting into rigor
theater: generation became plural, so certification must become finer — not weaker.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# the enriched ladder (coherence is necessary, never sufficient)
STATUSES = [
    "INSIDE_THE_BOX",            # breaks no axis
    "DEAD_COLLAGE",             # reducible to a known family, no synergy
    "INDETERMINATE",            # the deciding metric crosses the threshold band — this run cannot decide
    "SUSPENDED_BOLD",           # breaks an axis, but no executable world-test exists yet (suspend, don't bury)
    "ALIVE_OWN_WORLD",          # wins only on the arena it designed (provisional — circularity not excluded)
    "ALIVE_LOCAL_NOVELTY",      # wins + a verifiable new output, bounded reach
    "ALIVE_TRANSFERS",          # wins ALSO on a foreign world → captures something general
    "ALIVE_ARCHITECTURAL",      # transfers + high reach
]


@dataclass
class Maturity:
    status: str
    coherence: float            # did it survive the tests it faced? [0,1]
    reach: int                  # # of severe, independent predictions it implies
    fecundity: int              # # of new falsifiable questions it opens
    note: str = ""
    what_would_make_it_testable: str = ""
    open_questions: List[str] = field(default_factory=list)
    def markdown(self) -> str:
        L = [f"### Maturity — {self.status}",
             f"- **coherence (survived what it faced):** {self.coherence:.2f}",
             f"- **reach (severe independent predictions):** {self.reach}",
             f"- **fecundity (new questions opened):** {self.fecundity}"]
        if self.note:
            L.append(f"- **note:** {self.note}")
        if self.what_would_make_it_testable:
            L.append(f"- **what would make it testable:** {self.what_would_make_it_testable}")
        if self.open_questions:
            L.append("- **open questions:** " + "; ".join(self.open_questions))
        return "\n".join(L)


def assess(breaks: List[str],
           has_executable_world_test: bool,
           coherence: float = 0.0,
           reduces_to: Optional[str] = None,
           synergy: float = 0.0,
           controls_collapse: bool = True,
           new_output: bool = False,
           won_on_foreign_world: Optional[bool] = None,
           reach: int = 0,
           open_questions: Optional[List[str]] = None,
           what_would_make_it_testable: str = "") -> Maturity:
    """Place a candidate on the enriched ladder. `coherence` is the survive-score (e.g. novelty_score's
    value); the rest separate what survival alone cannot tell you."""
    oq = open_questions or []
    fecundity = len(oq)
    base = Maturity("", round(coherence, 2), reach, fecundity,
                    what_would_make_it_testable=what_would_make_it_testable, open_questions=oq)

    # 1. no axis broken → in the box (a non-breaking unify/instrument still 'breaks []' but earns its
    #    place through new_output; only an idea with neither a break NOR a new output is in the box)
    if not breaks and not new_output:
        base.status = "INSIDE_THE_BOX"; base.note = "breaks no axis and makes no new prediction."
        return base

    # 2. reducible with no synergy → dead collage
    if reduces_to is not None and not (synergy and synergy > 0):
        base.status = "DEAD_COLLAGE"; base.note = f"reduces to '{reduces_to}' and does not beat its parts."
        return base

    # 3. controls did not collapse → leakage, not the broken axis (kept as INDETERMINATE if unsure)
    if not controls_collapse:
        base.status = "INDETERMINATE"; base.note = "controls did not collapse — likely leakage; this run cannot certify."
        return base

    # 4. bold but no executable world-test today → suspend, do not kill
    if not has_executable_world_test:
        base.status = "SUSPENDED_BOLD"
        base.note = "breaks an axis but cannot be falsified yet; not killed, suspended."
        if not base.what_would_make_it_testable:
            base.what_would_make_it_testable = "name the observation / instrument / dataset that would decide it."
        return base

    # 5. it has an executable world-test and survives — but WHERE did it win?
    if won_on_foreign_world is None:
        base.status = "ALIVE_OWN_WORLD"
        base.note = "wins on its own arena; run the transfer test on another idea's world before claiming generality."
    elif won_on_foreign_world:
        base.status = "ALIVE_ARCHITECTURAL" if (reach >= 2 and new_output) else "ALIVE_TRANSFERS"
        base.note = "wins also on a world built for a different idea → not an artifact of its own complement."
    else:
        base.status = "ALIVE_LOCAL_NOVELTY" if new_output else "ALIVE_OWN_WORLD"
        base.note = "wins on its own world but not on the foreign one → real but bounded; do not claim a paradigm."
    return base
