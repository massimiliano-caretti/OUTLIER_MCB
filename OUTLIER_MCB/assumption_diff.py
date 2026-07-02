"""assumption_diff — compare two candidate ideas by WHICH hidden assumption each breaks and on which axis,
then name the tension. Similarity tools tell you how alike two ideas look; none tells you how they DIVERGE
structurally. Pure composition of judge(): deterministic, offline, opt-in. A pack sharpens it (it populates the
broken assumption + closure); without a pack it degrades honestly to a verdict-level comparison.
"""
from __future__ import annotations
from typing import Dict, Optional

from .judge import judge


def _axis_of(pack, assumption: Optional[str]) -> Optional[str]:
    if pack is None or not assumption:
        return None
    dim = getattr(pack, "dimension_of", None) or {}
    return dim.get(assumption)


def _leg(idea: str, prompt: Optional[str], pack) -> Dict:
    j = judge(idea, prompt=prompt, pack=pack) if pack is not None else judge(idea, prompt=prompt)
    closure = j.closure if isinstance(getattr(j, "closure", None), dict) else None
    return {
        "idea": idea,
        "verdict": j.verdict,
        "broken_assumption": getattr(j, "broken_assumption", None),
        "axis": _axis_of(pack, getattr(j, "broken_assumption", None)),
        "inside_closure": (closure or {}).get("inside_closure"),
    }


def assumption_diff(idea_a: str, idea_b: str, pack=None, prompt: Optional[str] = None) -> Dict:
    """Diff two ideas structurally. Returns each idea's verdict + broken assumption + axis + any closure it is
    inside, and a `tension` summary: whether they break the SAME axis (variations of one move), DIFFERENT axes
    (genuinely divergent), or one is INSIDE_THE_BOX while the other escapes (only one is a real move)."""
    a, b = _leg(idea_a, prompt, pack), _leg(idea_b, prompt, pack)
    va, vb = a["verdict"], b["verdict"]
    inside = "INSIDE_THE_BOX"
    if va == inside and vb == inside:
        tension = "both INSIDE_THE_BOX — neither breaks an axis; neither is an answer."
    elif (va == inside) != (vb == inside):
        esc = "B" if va == inside else "A"
        tension = f"only idea {esc} escapes the box; the other reduces to it — not a real alternative."
    elif a["axis"] and b["axis"]:
        tension = (f"different axes ({a['axis']} vs {b['axis']}) — genuinely divergent directions."
                   if a["axis"] != b["axis"] else
                   f"same axis ({a['axis']}) — variations of ONE move, not a real portfolio.")
    elif a["broken_assumption"] and b["broken_assumption"]:
        tension = ("different broken assumptions — divergent." if a["broken_assumption"] != b["broken_assumption"]
                   else "same broken assumption — variations of one move.")
    else:
        tension = "both audited but axes undetermined without a pack — pass pack= to sharpen the diff."
    return {"a": a, "b": b, "tension": tension, "pack_used": pack is not None}


def _leg_md(x: Dict, tag: str) -> str:
    parts = [f"- **{tag}** [{x['verdict']}] — breaks `{x['broken_assumption']}`"]
    if x["axis"]:
        parts.append(f" on axis {x['axis']}")
    if x["inside_closure"]:
        parts.append(f"; inside «{x['inside_closure']}»")
    return "".join(parts)


def assumption_diff_markdown(idea_a: str, idea_b: str, pack=None, prompt: Optional[str] = None) -> str:
    d = assumption_diff(idea_a, idea_b, pack, prompt)
    return "\n".join(["# Assumption-diff", _leg_md(d["a"], "A"), _leg_md(d["b"], "B"),
                      "", f"**Tension:** {d['tension']}"])
