"""health — make each capability EARN its keep, by measurement (not by description).

The standing critique: a sprawling library risks "innovation theatre" — capabilities that exist but
never change a result. Applying the engine to this view forbade the three easy answers (a descriptive
list, auto-deletion, static-only evidence) and demanded REAL measurement. So `health()`:

  • operator_yield  — DYNAMIC: actually calls every generative operator and counts the candidates it
                      produces on the built-in packs. An operator that yields 0 everywhere is INERT.
  • wiring          — STATIC: which public symbols are referenced somewhere other than their own module
                      and the __init__ re-export. Those referenced only via __init__ are BY_HAND_ONLY
                      (reachable building blocks, not orchestrated).
  • report only     — it never deletes anything. It surfaces what does not earn its keep; the HUMAN
                      decides. Deleting tested code unilaterally is the mistake to avoid.

Collaborators: the generator operators (measured), the package source (scanned for wiring).
"""
from __future__ import annotations
import ast
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List


def operator_yield(pack=None) -> Dict[str, int]:
    """Call every generative operator and count the candidates it yields (summed over the built-in packs
    unless one is given). The real, dynamic 'does it generate?' measurement."""
    from .pack import get_pack, list_packs
    from .generators import (recombine_assumptions, invert_assumption, scale_break, transport_break,
                             what_would_have_to_be_true, unify, instrument, reframe, dissolve, breakable)
    from .dialectic import all_syntheses
    packs = [pack] if pack is not None else [get_pack(n) for n in list_packs() if n != "generic"]
    counts: Counter = Counter()
    for p in packs:
        names = [a.name for a in breakable(p)]
        counts["recombine"] += len(recombine_assumptions(p, k=2))
        counts["invert"] += sum(1 for n in names if invert_assumption(p, n))
        counts["scale"] += sum(1 for n in names if scale_break(p, n))
        counts["dissolve"] += sum(1 for n in names if dissolve(p, n))
        counts["reframe"] += sum(1 for n in names if reframe(p, n))
        counts["instrument"] += sum(1 for n in names if instrument(p, n))
        counts["unify"] += (1 if len(names) >= 2 and unify(p, names[0], names[1]) else 0)
        counts["abduce"] += (1 if what_would_have_to_be_true(p, "a goal") else 0)
        counts["dialectic"] += len(all_syntheses(p))
        other = next((get_pack(n) for n in list_packs() if n not in (p.name, "generic")), None)
        counts["transport"] += (1 if other is not None and transport_break(other, p) else 0)
    return dict(counts)


def _public_symbols() -> List[str]:
    import OUTLIER_MCB as gsl
    return list(getattr(gsl, "__all__", [])) + list(getattr(gsl, "__toolbox__", []))


def wiring() -> Dict[str, bool]:
    """For each public symbol: is it actually CALLED anywhere in the package (its own module counts —
    intra-module orchestration is real), beyond its definition and the __init__ re-export? True ⇒ it
    earns its keep; False ⇒ reachable only by hand (a building block referenced only via __init__)."""
    pkg = Path(__file__).parent
    sources = {f.relative_to(pkg).as_posix(): f.read_text(errors="ignore")
               for f in pkg.rglob("*.py") if "__pycache__" not in str(f) and f.name != "__init__.py"}
    out = {}
    for sym in _public_symbols():
        # HONESTY FIX (#9): count WHOLE-WORD occurrences, not substrings — otherwise a short symbol name (e.g.
        # `health`) is reported 'wired' merely because it is a substring of a longer one (`library_health`).
        use = re.compile(r"\b" + re.escape(sym) + r"\b")
        dfn = re.compile(r"\b(?:def|class)\s+" + re.escape(sym) + r"\b")
        total = sum(len(use.findall(src)) for src in sources.values())
        defs = sum(len(dfn.findall(src)) for src in sources.values())
        out[sym] = (total - defs) >= 1
    return out


@dataclass
class CapabilityReport:
    operator_yield: Dict[str, int] = field(default_factory=dict)
    inert_operators: List[str] = field(default_factory=list)      # generators that produce nothing
    by_hand_only: List[str] = field(default_factory=list)         # reachable but not orchestrated
    earns_keep: int = 0
    total_public: int = 0
    def markdown(self) -> str:
        ys = ", ".join(f"{k}={v}" for k, v in sorted(self.operator_yield.items()))
        return "\n".join([
            "### Capability health (measured, not described)",
            f"- **operator yield (candidates produced):** {ys}",
            f"- **INERT operators (produce nothing):** {', '.join(self.inert_operators) or 'none'}",
            f"- **reachable but NOT orchestrated (building blocks):** {', '.join(self.by_hand_only) or 'none'}",
            f"- **earns-its-keep:** {self.earns_keep}/{self.total_public} public symbols are wired into the flow.",
            "- This is a REPORT. It deletes nothing — the human decides what to consolidate.",
        ])


def capability_value(pack=None) -> Dict:
    """ABLATION on the value metric (the concrete answer to 'innovation theatre'): for each generative
    operator, measure the pool's Verified Novelty Score WITH vs WITHOUT its candidates.

      KEEPS      removing it LOWERS VNS  → it earns its keep
      DECORATIVE removing it changes nothing → it produces, but adds no value
      HARMFUL    removing it RAISES VNS  → it drags the pool down

    Reports only — it deletes nothing. This is the measured reply to 'a capability must earn its keep'.
    """
    from .pack import get_pack, list_packs
    from .generators import generate_candidates
    from .metrics import verified_novelty_score
    packs = [pack] if pack is not None else [get_pack(n) for n in list_packs() if n != "generic"]
    pools = [generate_candidates(p) for p in packs]

    def mean_vns(drop_op=None) -> float:
        scores = [verified_novelty_score([c for c in pool if c.operator != drop_op]) for pool in pools if pool]
        return sum(scores) / len(scores) if scores else 0.0

    full = mean_vns()
    ops = sorted({c.operator for pool in pools for c in pool})
    verdicts = {}
    for op in ops:
        delta = round(full - mean_vns(op), 4)
        verdicts[op] = ("KEEPS" if delta > 1e-6 else "HARMFUL" if delta < -1e-6 else "DECORATIVE")
    return {"full_vns": round(full, 3), "verdicts": verdicts,
            "decorative": sorted(o for o, v in verdicts.items() if v == "DECORATIVE"),
            "harmful": sorted(o for o, v in verdicts.items() if v == "HARMFUL")}


def health() -> CapabilityReport:
    """Measure which capabilities earn their keep. Reports; never deletes."""
    yields = operator_yield()
    wired = wiring()
    inert = sorted(op for op, n in yields.items() if n == 0)
    by_hand = sorted(sym for sym, used in wired.items() if not used)
    return CapabilityReport(operator_yield=yields, inert_operators=inert, by_hand_only=by_hand,
                            earns_keep=sum(1 for v in wired.values() if v), total_public=len(wired))
