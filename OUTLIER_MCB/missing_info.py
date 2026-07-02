"""missing_info — detect when a breakthrough is IMPOSSIBLE with the current information (agnostic).

This is the module that stops the assistant from inventing the Nth mechanism when the problem is
information-limited. It reads the pack's `info_kinds` and the assumption graph's needs_new_data edges
and reports which NEW information would actually move the ceiling. Pure wrapper over the kernel's own
missing-information logic, so it stays domain-blind.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class MissingInfoReport:
    data_insufficient: bool
    reason: str
    needed_information: List[Dict[str, str]] = field(default_factory=list)   # [{kind, why, criticality}]
    recommended_first: Optional[str] = None

    def by_criticality(self, level: str) -> List[Dict[str, str]]:
        """The information needs at a given level: CRITICAL (unlocks the ceiling) · HELPFUL (a lower-priority
        break) · VALIDATION (refines/confirms, does not unlock)."""
        return [d for d in self.needed_information if d.get("criticality", "VALIDATION") == level]

    def roadmap(self) -> List[Dict[str, str]]:
        """A partial-progress ROADMAP instead of a binary verdict: needs ordered CRITICAL → HELPFUL →
        VALIDATION, so a user knows what to gather FIRST and what merely sharpens the result."""
        order = {"CRITICAL": 0, "HELPFUL": 1, "VALIDATION": 2}
        return sorted(self.needed_information, key=lambda d: order.get(d.get("criticality", "VALIDATION"), 3))

    def markdown(self) -> str:
        L = ["### Missing-information detector",
             f"- **Data insufficient for a breakthrough?** {'YES' if self.data_insufficient else 'no'} — {self.reason}"]
        if self.needed_information:
            L.append("- **Roadmap (gather in this order):**")
            for d in self.roadmap():
                crit = d.get("criticality", "VALIDATION")
                prefix = "⭐" if d["kind"] == self.recommended_first else "  "
                L.append(f"  - {prefix}[{crit}] **{d['kind']}** — {d['why']}")
        return "\n".join(L)


def detect_missing_information(problem_text: str, pack=None, signals: Optional[Dict] = None) -> MissingInfoReport:
    """Decide whether new information is required, and which kind, for the domain described by `pack`.
    ERGONOMICS (#15): `pack` is optional — when omitted, the domain is routed from `problem_text` itself
    (falling back to the generic pack), so a caller can ask `detect_missing_information("...")` directly."""
    if pack is None:
        from .pack import select_pack
        pack, _score = select_pack(problem_text)
    from . import kernel
    g = kernel.graph_of(pack, problem_text)
    mi = kernel._missing_info(problem_text, pack, g, signals)
    return MissingInfoReport(
        data_insufficient=mi["data_insufficient"],
        reason=mi["reason"],
        needed_information=mi["needed_information"],
        recommended_first=mi["recommended_first"],
    )
