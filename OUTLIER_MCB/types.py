"""types — explicit schemas for the engine's stable dict outputs.

Answering the review: `preflight` returns a dict with a fixed, stable set of keys. A bare `Dict` hides
that schema from the IDE and the type-checker. These TypedDicts make the shape explicit and statically
checkable WITHOUT changing the runtime value — `preflight` still returns an ordinary dict, so every
existing `pf["pack"]` access keeps working. We type the shape; we do not abandon it.
"""
from __future__ import annotations
from typing import Dict, List, Optional, TypedDict


class HiddenAssumption(TypedDict):
    name: str
    in_box: bool
    dimension: Optional[str]


class BreakOption(TypedDict):
    assumption: str
    dimension: str
    why: str


class NeededInfo(TypedDict):
    kind: str
    why: str


class MissingInfo(TypedDict):
    data_insufficient: bool
    reason: str
    needed_information: List[NeededInfo]
    recommended_first: Optional[str]


class PreflightResult(TypedDict, total=False):
    """The dict returned by kernel.preflight / preflight_creative_request.

    The first block of keys is always present; `domain_guard` / `elicitation_required` are added by the
    preflight_creative_request wrapper, hence total=False.
    """
    pack: str
    box_name: str
    hidden_assumptions: List[HiddenAssumption]
    central_assumptions: List[str]
    three_breaks: List[BreakOption]
    recommended_direction: BreakOption
    must_not_propose: List[str]
    death_gate: str
    anti_collage_warning: str
    missing_information: MissingInfo
    instructions: str
    # added by the agnostic wrapper:
    domain_guard: Dict[str, object]
    elicitation_required: bool
