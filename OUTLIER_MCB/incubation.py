"""incubation — the delayed-insight step: let dead ends and distant wins RECONNECT offline (Tier-2, T2.3).

A human genius does not solve only in the moment. A private world-model accumulates over years, and during
'rest' distant elements connect on their own — the shower-thought, Poincaré stepping onto the omnibus. Today
LLMs are amnesiac between sessions and this engine, while it PERSISTS outcomes (DiscoveryMemory: which
assumptions proved fertile or barren, per domain), never lets those cross-session traces INCUBATE: it consults
them only to deprioritise dead ends. The missing move is generative — during an offline pass, connect the
FERTILE breaks that live in DIFFERENT domains/axes into fresh cross-domain conjectures no single session would
surface, and REVIVE a barren assumption under a DIFFERENT axis (a dead end can be alive under a new lens).

incubate() returns ranked IncubatedConnection conjectures (by a surprise = semantic-distance × combined
fertility) and revive_barren() returns dead ends worth reopening on a new axis. Both are CONJECTURES to break
next — settled later by falsification, never asserted here — so incubation widens the search honestly. Feed the
results back as the next assumptions to break (they compose with invent()'s reflexion loop and pack extension).

Deterministic, zero-dependency beyond the pluggable embedder. Composes DiscoveryMemory (the store) with the
existing semantic_distance — it adds the incubation POLICY, not a new memory or a new operator.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional

from .embeddings import semantic_distance


@dataclass
class IncubatedConnection:
    """A fresh cross-domain conjecture formed by connecting two distant FERTILE breaks during incubation."""
    left: str                    # a fertile assumption (domain/axis A)
    right: str                   # a fertile assumption (domain/axis B), distant from `left`
    left_domain: str
    right_domain: str
    axis_hint: str               # the invented axis the connection would live on
    surprise: float              # semantic distance × combined fertility, in [0,1] — higher = less obvious
    conjecture: str              # the assumption to try breaking next (still must be falsified)

    def markdown(self) -> str:
        return (f"- **incubated** (surprise {self.surprise}) on axis `{self.axis_hint}`: {self.conjecture}\n"
                f"    - from «{self.left}» ({self.left_domain}) × «{self.right}» ({self.right_domain})")


@dataclass
class RevivedDeadEnd:
    """A previously-barren assumption worth reopening under a DIFFERENT axis — the ledger's reopen rule applied
    across sessions: an axis killed under one lens is cheap again under another."""
    assumption: str
    old_axis: str
    new_axis: str
    domain: str
    why: str

    def markdown(self) -> str:
        return (f"- **revive** «{self.assumption}» ({self.domain}): dead on axis `{self.old_axis}` → retry on "
                f"`{self.new_axis}` — {self.why}")


def incubate(memory, k: int = 5, min_attempts: int = 1, min_distance: float = 0.4,
             embedder=None) -> List[IncubatedConnection]:
    """Offline recombination of accumulated FERTILE breaks across domains/axes into fresh conjectures, ranked by
    surprise (distance × combined fertility). Only DISTANT pairs (semantic distance ≥ min_distance) are kept —
    connecting two near-identical wins is a rephrase, not an insight. Returns the top-k, most-surprising first."""
    fertile = memory.fertile(min_attempts=min_attempts)
    out: List[IncubatedConnection] = []
    seen = set()
    for i, a in enumerate(fertile):
        for b in fertile[i + 1:]:
            if a.assumption == b.assumption:
                continue
            key = tuple(sorted((a.assumption, b.assumption)))
            if key in seen:
                continue
            seen.add(key)
            dist = semantic_distance(a.assumption, b.assumption, embedder=embedder)
            if dist < min_distance:
                continue                                  # too close → a rephrase, not a genuine connection
            surprise = round(dist * ((a.prior + b.prior) / 2.0), 4)
            axis_hint = (f"{a.axis}+{b.axis}" if a.axis and b.axis and a.axis != b.axis
                         else (a.axis or b.axis or "CROSS_DOMAIN"))
            conj = (f"the fertile break «{a.assumption}» and «{b.assumption}» share a transferable mechanism "
                    f"across {a.domain or 'a domain'} and {b.domain or 'another'} — break their common cause.")
            out.append(IncubatedConnection(left=a.assumption, right=b.assumption,
                                           left_domain=a.domain, right_domain=b.domain,
                                           axis_hint=axis_hint, surprise=surprise, conjecture=conj))
    out.sort(key=lambda c: -c.surprise)
    return out[:k]


def revive_barren(memory, new_axes: Optional[List[str]] = None, min_attempts: int = 1) -> List[RevivedDeadEnd]:
    """Reopen barren (refuted) assumptions under a DIFFERENT axis than the one they died on — a dead end can be
    alive under a new lens (the reopen rule, across sessions). `new_axes` supplies candidate lenses; without it,
    the fertile axes seen elsewhere in memory are borrowed (transfer a lens that has paid off somewhere else)."""
    barren = memory.barren(min_attempts=min_attempts)
    if new_axes is None:
        new_axes = sorted({o.axis for o in memory.fertile(min_attempts=1) if o.axis})
    out: List[RevivedDeadEnd] = []
    for o in barren:
        lens = next((ax for ax in new_axes if ax and ax != o.axis), None)
        if lens is None:
            continue
        out.append(RevivedDeadEnd(assumption=o.assumption, old_axis=o.axis, new_axis=lens, domain=o.domain,
                                  why=f"barren on '{o.axis}', but '{lens}' has paid off elsewhere — a new lens "
                                      f"reopens it (settle by a real world-test, do not assume it revives)."))
    return out
