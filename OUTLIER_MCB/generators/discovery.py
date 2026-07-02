"""generators.discovery — operators that reach PAST the pre-registered assumptions.

  anomaly_to_assumption  mine "what refused to collapse / stayed unexplained" into a NEW provisional
                         assumption the registry did not contain (the engine discovers, not just retrieves)
  self_spark             let the engine propose WHICH assumption to break, then still falsify it
                         (the spark stops being only-human; the rigor stays)
"""
from __future__ import annotations
from typing import Dict, List, Tuple

from ..core import Assumption
from .base import breakable, data_req


def anomaly_to_assumption(pack, anomaly: str, axis: str = "") -> Tuple[Assumption, Dict]:
    """Turn an unexplained residual into a NEW, provisional assumption. It is INERT (cannot generate a
    candidate) until it is given an axis AND a falsifier — the same gate every other assumption obeys.
    Returns (assumption, meta) where meta carries the provisional flag and the gate."""
    slug = "anomaly_" + "_".join(anomaly.lower().split()[:4])
    assumption = Assumption(
        name=slug,
        description=f"[provisional, mined from an anomaly] {anomaly}",
        why_obvious="it was treated as noise/leakage and discarded, never as signal.",
        if_false=f"the residual '{anomaly}' is itself a structured, modellable signal — a hidden assumption is being violated.",
        assumed_by=["the current box (which calls it noise)"],
        falsifier=("reproduce the anomaly on a clean construction and show it does NOT vanish under the "
                   "controls; if it vanishes, it was leakage after all."),
    )
    meta = {"provisional": True, "axis": axis if axis in pack.axes else None,
            "gate": "assign an axis + a falsifier before it may generate a candidate (REQUIRED_FIELDS)."}
    return assumption, meta


def self_spark(pack, prompt: str = "", n: int = 3) -> List[Dict]:
    """Let the engine propose which assumptions to break, ranked by novelty potential (axis priority ·
    needs-new-data · not-yet-exhausted), then route them through the SAME falsifier."""
    req = data_req(pack)
    dead_axes = {pack.dimension_of.get(k) for k, v in pack.failure_memory.items()
                 if str(v.get("status", "")).startswith("DEAD")}

    def potential(a) -> Tuple[int, str]:
        axis = pack.dimension_of[a.name]
        score = pack.axes.get(axis, {}).get("priority", 1)
        score += 1 if req.get(a.name) else 0          # a break that needs new data reaches further
        score += 1 if axis not in dead_axes else 0    # prefer an axis not already exhausted
        return score, a.name

    ranked = sorted(breakable(pack), key=potential, reverse=True)[:n]
    return [{"assumption": a.name, "axis": pack.dimension_of[a.name],
             "why": f"engine-proposed spark (potential {potential(a)[0]}): {a.if_false}",
             "needs": req.get(a.name, []),
             "still_must_falsify": "the human did NOT choose this; it must still win a world-test where the box fails."}
            for a in ranked]
