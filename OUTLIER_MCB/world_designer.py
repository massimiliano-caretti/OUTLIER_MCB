"""world_designer — design a falsifiable world-test SPEC from a broken axis (domain-agnostic).

Given the axis a candidate breaks, it emits a SPEC stating which family must FAIL, which candidate
must WIN, which controls must collapse, which leakage to avoid, and which metric decides. For a
domain with an executable `world_factory` on the pack it names the builder; otherwise it emits the
construction recipe as a SPEC (a property test / constructed counterexample) for the assistant to run.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class WorldTestSpec:
    dimension: str
    existing_builder: Optional[str]
    family_must_fail: str
    candidate_must_win: str
    construction: str
    controls_must_collapse: List[str]
    leakage_to_avoid: str
    deciding_metric: str
    note: str = ""
    def as_dict(self) -> Dict: return self.__dict__
    def markdown(self) -> str:
        L = [f"### World-test SPEC — axis {self.dimension}"]
        L += [f"- **Existing builder:** {self.existing_builder or 'NONE (construct per the recipe below)'}",
              f"- **Family that MUST fail:** {self.family_must_fail}",
              f"- **Candidate that MUST win:** {self.candidate_must_win}",
              f"- **Construction:** {self.construction}",
              f"- **Controls that must collapse:** {', '.join(self.controls_must_collapse)}",
              f"- **Leakage to avoid:** {self.leakage_to_avoid}",
              f"- **Deciding metric:** {self.deciding_metric}"]
        if self.note:
            L.append(f"- **Note:** {self.note}")
        return "\n".join(L)


def design_world_test(axis: str, pack) -> WorldTestSpec:
    """Emit a falsifiable world-test SPEC for `axis` in the domain described by `pack`."""
    if not axis or axis not in pack.axes:
        return WorldTestSpec(axis or "—", None,
                             "—", "—",
                             "no breakable axis → no separating world exists; the idea is INSIDE THE BOX.",
                             [], "—", "—",
                             f"Break one of the domain's axes first ({', '.join(pack.axes) or '—'}).")
    families = ", ".join(sorted(set(pack.known_families))) or "the known family"
    has_factory = bool(getattr(pack, "world_factory", None))
    builder = (pack.world_factory.__name__ if has_factory and hasattr(pack.world_factory, "__name__") else None)
    note = ("the pack provides an executable world_factory that realizes this SPEC."
            if has_factory else
            "no executable builder for this domain — construct per the recipe (a property test / constructed "
            "counterexample), keeping the box's variables matched across the contrast.")
    construction = (f"Build instances where the discriminative structure lives ENTIRELY on the '{axis}' axis: "
                    f"everything the box [{pack.box_name}] can see is matched across classes, so only the broken "
                    f"axis distinguishes them.")
    controls = [f"shuffle the '{axis}' structure → the gain collapses to chance",
                f"a box-only baseline ({families}) → chance / ties the baseline"]
    return WorldTestSpec(
        dimension=axis,
        existing_builder=builder,
        family_must_fail=f"every member of the box [{families}] (must sit at the baseline by construction)",
        candidate_must_win=f"the mechanism that uses the '{axis}' structure the box discards",
        construction=construction,
        controls_must_collapse=controls,
        leakage_to_avoid=f"the '{axis}' structure must be the ONLY discriminator; use group-disjoint splits so nothing leaks.",
        deciding_metric=f"the gap (with '{axis}' structure − without); it must vanish under the shuffle control.",
        note=note,
    )
