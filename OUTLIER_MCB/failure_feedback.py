"""failure_feedback — what died yesterday steers what is proposed today.

The kernel already ranks breaks by RARITY (`kernel._failure_count` reads `pack.failure_memory`), but nothing ever
WROTE to that memory: every built-in pack ships it empty, and an assistant drives the library through separate
`python -c` / CLI calls, so even an in-process record would vanish between `judge()` and the next `creative()`.
The brief therefore re-proposed the same worn break forever.

This module closes the loop with a small persistent store:
  • `judge(..., memory=…)` records every NEGATIVE verdict (INSIDE_THE_BOX, DEAD_BY_BARRIER, RENAMED / COLLAGE prior
    art, NEEDS_DISAMBIGUATION is not one) under the routed pack and the assumption the idea tried to break;
  • `creative(..., memory=…)` / `preflight_creative_request(..., memory=…)` load it into a COPY of the pack, so the
    kernel demotes spent breaks (one priority level per two deaths — see kernel._ranked_breakable), the
    anti-collage warning names them, and the brief lists the ideas already rejected so they are not re-proposed.
`memory` is a FailureStore, a JSON path, or None → the OUTLIER_MCB_MEMORY env var (unset ⇒ no persistence, the
library stays side-effect free by default).
"""
from __future__ import annotations
import dataclasses
import json
import os
import re
from typing import Dict, List, Optional

# verdicts that mean "this attempt is spent" (an idea that merely needs disambiguation is not a death).
NEGATIVE_VERDICTS = ("INSIDE_THE_BOX", "DEAD_BY_BARRIER", "RENAMED", "COLLAGE", "RENAMED_PRIOR_ART",
                     "COLLAGE_OF_PRIOR_ART", "MODE_ECHO", "NEAR_MODE", "NOT_SEPARATED", "LOST")
ENV_VAR = "OUTLIER_MCB_MEMORY"
MAX_PER_PACK = 500


def _slug(text: str, n: int = 60) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(text or "").lower()).strip("_")[:n] or "idea"


class FailureStore:
    """{pack_name: {key: entry}} persisted as JSON (atomic writes). An entry is
    {"status": "DEAD_<verdict>", "assumption", "axis", "idea", "reason", "count"} — the shape kernel._failure_count
    already understands, so a loaded store needs no kernel change to influence the ranking."""

    def __init__(self, path: Optional[str] = None):
        self.path = path
        self.data: Dict[str, Dict[str, Dict]] = {}
        if path and os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as fh:
                    raw = json.load(fh)
                self.data = {str(k): dict(v) for k, v in raw.items() if isinstance(v, dict)}
            except (OSError, ValueError):
                self.data = {}                       # a corrupt/unreadable store must never block a verdict

    def record(self, pack_name: str, idea: str, verdict: str, assumption: str = "", axis: str = "",
               reason: str = "") -> Optional[Dict]:
        """Record one negative verdict (others are ignored → None). The same idea under the same assumption only
        increments its count, so repetition is visible without growing the file."""
        if verdict not in NEGATIVE_VERDICTS:
            return None
        bucket = self.data.setdefault(pack_name, {})
        key = f"{assumption or 'unmapped'}::{_slug(idea)}"
        e = bucket.get(key)
        if e is None:
            e = bucket[key] = {"status": f"DEAD_{verdict}", "assumption": assumption or "", "axis": axis or "",
                               "idea": str(idea or "")[:160], "reason": str(reason or "")[:200], "count": 0}
        e["count"] = int(e.get("count", 0)) + 1
        e["status"], e["reason"] = f"DEAD_{verdict}", str(reason or e.get("reason", ""))[:200]
        if len(bucket) > MAX_PER_PACK:                 # bounded: drop the least-repeated, oldest entries first
            for k in sorted(bucket, key=lambda k: bucket[k].get("count", 0))[: len(bucket) - MAX_PER_PACK]:
                if k != key:
                    del bucket[k]
        return e

    def entries(self, pack_name: str) -> Dict[str, Dict]:
        return dict(self.data.get(pack_name, {}))

    def spent(self, pack_name: str) -> List[Dict]:
        """Per-assumption summary, most-spent first: [{assumption, deaths, verdicts}] (unmapped ideas excluded)."""
        agg: Dict[str, Dict] = {}
        for e in self.data.get(pack_name, {}).values():
            a = e.get("assumption") or ""
            if not a:
                continue
            s = agg.setdefault(a, {"assumption": a, "deaths": 0, "verdicts": set()})
            s["deaths"] += int(e.get("count", 1))
            s["verdicts"].add(str(e.get("status", ""))[5:])
        out = [dict(v, verdicts=sorted(v["verdicts"])) for v in agg.values()]
        return sorted(out, key=lambda d: (-d["deaths"], d["assumption"]))

    def rejected_ideas(self, pack_name: str, k: int = 6) -> List[str]:
        es = sorted(self.data.get(pack_name, {}).values(), key=lambda e: -int(e.get("count", 1)))
        return [e["idea"] for e in es[:k] if e.get("idea")]

    def apply(self, pack):
        """A COPY of `pack` whose failure_memory includes this store's entries (one map entry per death, so the
        kernel's per-entry count reflects repetitions). The registered pack is never mutated."""
        fm = dict(pack.failure_memory or {})
        for key, e in self.data.get(pack.name, {}).items():
            for i in range(max(1, int(e.get("count", 1)))):
                fm[f"{key}#{i}" if i else key] = e
        return dataclasses.replace(pack, failure_memory=fm) if fm != (pack.failure_memory or {}) else pack

    def save(self) -> None:
        if not self.path:
            return
        from .memory import atomic_write_json
        d = os.path.dirname(os.path.abspath(self.path))
        os.makedirs(d, exist_ok=True)
        atomic_write_json(self.path, self.data, ensure_ascii=False, indent=1)


def resolve_store(memory=None) -> Optional[FailureStore]:
    """A FailureStore from `memory` (store | path), else from the OUTLIER_MCB_MEMORY env var, else None."""
    if isinstance(memory, FailureStore):
        return memory
    if isinstance(memory, str) and memory.strip():
        return FailureStore(memory)
    env = os.environ.get(ENV_VAR, "").strip()
    return FailureStore(env) if env else None


def spent_markdown(store: Optional[FailureStore], pack_name: str) -> str:
    """The brief block: which breaks are worn and which ideas were already rejected ('' when nothing is spent)."""
    if store is None:
        return ""
    spent, ideas = store.spent(pack_name), store.rejected_ideas(pack_name)
    if not spent and not ideas:
        return ""
    lines = ["\n[memory] Already spent in this domain — do NOT re-propose; breaks below are demoted in the ranking:"]
    lines += [f"  ✗ {s['assumption']} — died {s['deaths']}× ({', '.join(s['verdicts'])})" for s in spent[:6]]
    lines += [f"  ✗ idea: «{i[:100]}»" for i in ideas]
    return "\n".join(lines)
