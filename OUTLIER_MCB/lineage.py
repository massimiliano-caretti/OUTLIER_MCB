"""lineage — every new idea must declare which DEAD ideas it descends from (domain-agnostic).

Stops reincarnation: if an idea reduces to the same family as a buried one (in the pack's
failure_memory), it must state what it ACTUALLY breaks in addition, or inherit the death.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class Lineage:
    idea: str
    inferred_family: str
    dead_ancestors: List[str]
    repeated_risk: Optional[str]
    must_explain: str
    inherits_death: bool
    def markdown(self) -> str:
        L = [f"### Idea lineage — {self.idea}",
             f"- **Inferred family:** {self.inferred_family}",
             f"- **Dead ancestors in this family:** {', '.join(self.dead_ancestors) or '—'}",
             f"- **Repeated risk:** {self.repeated_risk or '—'}",
             f"- **Inherits death unless:** {self.must_explain}",
             f"- **Verdict:** {'INHERITS DEATH (no new break declared)' if self.inherits_death else 'may proceed IF it declares the extra break'}"]
        return "\n".join(L)


def infer_family(idea_text: str, pack, family_guess: str = "") -> str:
    if family_guess:
        return family_guess
    t = (idea_text or "").lower()
    for f in pack.known_families:
        if f.lower() in t or f.lower().replace("_", " ") in t:
            return f
    return pack.known_families[0] if pack.known_families else "the standard approach"


def declare_lineage(idea: str, pack, family_guess: str = "", breaks: Optional[List[str]] = None,
                    idea_text: str = "") -> Lineage:
    """Place an idea in its family and check whether it reincarnates a dead one (per the pack's memory)."""
    breaks = breaks or []
    fam = infer_family(idea_text or idea, pack, family_guess)
    # dead ideas in this pack that reduced to the same family
    ancestors = sorted({k for k, v in pack.failure_memory.items()
                        if str(v.get("status", "")).startswith("DEAD")
                        and (fam.lower() in str(v.get("reduces_to", "")).lower() or fam == k)})
    risk = (f"reduces to '{fam}' — shares the family of dead idea '{ancestors[0]}'" if ancestors else None)
    inherits = bool(ancestors and not breaks)
    axes = ", ".join(pack.axes) or "the domain's axes"
    must = (f"declare a broken axis ({axes}) its ancestor did NOT break, and a world-test where that family "
            f"sits at the baseline while the idea wins.")
    return Lineage(idea, fam, ancestors, risk, must, inherits)
