"""discovery_memory — the compounding inventor advantage: remember what broke fruitfully vs fruitlessly.

The economy.Ledger prices (axis × operator) and tracks priced bets within/across runs. It does NOT carry
ASSUMPTION-level, cross-domain knowledge: which specific hidden assumptions, once broken, SURVIVED a world
-test (fertile) and which COLLAPSED under their controls (barren). A human inventor compounds exactly that
— "last time, breaking smoothness paid off in three domains; the static-landscape break never did" — and
lets it shift where they look next.

DiscoveryMemory accumulates that, persistently (JSON, like the Ledger), and FEEDS IT BACK: `as_failure_memory`
yields a pack-compatible failure_memory so the kernel's rarity ranking, cascade, and problem-finding all see
the accumulated dead ends; `prior` gives a learned fertility in [0,1] that can re-weight what to attack next.
It also records EMERGENT assumptions/axes the engine discovered (from blending/transformation) worth promoting.

Honest by construction: a prior is evidence (confirmed/attempted), never a guarantee; an untried assumption
stays neutral (0.5); nothing here claims novelty or proof.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class AssumptionOutcome:
    assumption: str
    axis: str = ""
    domain: str = ""
    confirmed: int = 0          # broke the assumption AND survived a world-test (controls collapsed)
    refuted: int = 0            # broke it but the controls did NOT collapse / it lost — a dead end
    attempted: int = 0
    last_note: str = ""

    @property
    def prior(self) -> float:
        """Learned fertility in [0,1] = confirmed / attempted. Untried ⇒ neutral 0.5 (evidence, not a guarantee)."""
        return round(self.confirmed / self.attempted, 3) if self.attempted else 0.5

    @property
    def status(self) -> str:
        if self.attempted == 0:
            return "UNTRIED"
        if self.confirmed > self.refuted and self.prior >= 0.6:
            return "CONFIRMED_FERTILE"
        if self.refuted > self.confirmed and self.prior <= 0.34:
            return "REFUTED_BARREN"
        return "MIXED"


@dataclass
class DiscoveryMemory:
    outcomes: Dict[str, AssumptionOutcome] = field(default_factory=dict)
    discovered: List[Dict] = field(default_factory=list)   # emergent assumptions/axes worth promoting

    @staticmethod
    def _key(domain: str, assumption: str) -> str:
        return f"{domain}:{assumption}"

    def record(self, assumption: str, axis: str, domain: str, confirmed: bool, note: str = "") -> AssumptionOutcome:
        """Record one settled attempt at breaking `assumption` in `domain`. `confirmed=True` ⇒ it survived a
        world-test (fertile); `False` ⇒ the controls did not collapse / it lost (a dead end)."""
        k = self._key(domain, assumption)
        o = self.outcomes.get(k) or AssumptionOutcome(assumption=assumption, axis=axis, domain=domain)
        o.attempted += 1
        if confirmed:
            o.confirmed += 1
        else:
            o.refuted += 1
        o.axis = axis or o.axis
        o.last_note = note or o.last_note
        self.outcomes[k] = o
        return o

    def prior(self, assumption: str, domain: Optional[str] = None) -> float:
        """The learned fertility of breaking `assumption` (in `domain` if given, else averaged across domains)."""
        if domain is not None:
            o = self.outcomes.get(self._key(domain, assumption))
            return o.prior if o else 0.5
        os = [o for o in self.outcomes.values() if o.assumption == assumption]
        return round(sum(o.prior for o in os) / len(os), 3) if os else 0.5

    def fertile(self, min_attempts: int = 1) -> List[AssumptionOutcome]:
        return sorted([o for o in self.outcomes.values()
                       if o.status == "CONFIRMED_FERTILE" and o.attempted >= min_attempts],
                      key=lambda o: -o.prior)

    def barren(self, min_attempts: int = 1) -> List[AssumptionOutcome]:
        return [o for o in self.outcomes.values()
                if o.status == "REFUTED_BARREN" and o.attempted >= min_attempts]

    def barren_axes(self, domain: Optional[str] = None) -> set:
        return {o.axis for o in self.barren() if (domain is None or o.domain == domain) and o.axis}

    def as_failure_memory(self, domain: Optional[str] = None) -> Dict[str, Dict]:
        """A pack-compatible failure_memory of the accumulated DEAD ends, so the kernel's rarity ranking,
        cascade, and problem-finding consult cross-session refutations (set pack.failure_memory = this)."""
        return {o.assumption: {"status": "DEAD_REFUTED", "axis": o.axis, "assumption": o.assumption}
                for o in self.barren() if domain is None or o.domain == domain}

    def promote(self, assumption: str, axis: str, domain: str, note: str = "") -> None:
        """Record an EMERGENT assumption/axis the engine discovered (e.g. via transformation/blending) worth
        adding to a pack later — the memory grows the engine's own vocabulary over time."""
        self.discovered.append({"assumption": assumption, "axis": axis, "domain": domain, "note": note})

    def save(self, path: str) -> None:
        import json
        data = {"outcomes": {k: o.__dict__ for k, o in self.outcomes.items()}, "discovered": self.discovered}
        with open(path, "w") as fh:
            json.dump(data, fh, indent=2)

    @classmethod
    def load(cls, path: str) -> "DiscoveryMemory":
        import json
        import os
        mem = cls()
        if not os.path.exists(path):
            return mem
        data = json.load(open(path))
        mem.outcomes = {k: AssumptionOutcome(**v) for k, v in data.get("outcomes", {}).items()}
        mem.discovered = list(data.get("discovered", []))
        return mem

    def markdown(self) -> str:
        f, b = self.fertile(), self.barren()
        L = [f"## Discovery memory — {len(self.outcomes)} assumptions tracked across {len({o.domain for o in self.outcomes.values()})} domain(s)"]
        if f:
            L.append("### Fertile (broke and survived):")
            L += [f"- {o.domain}:{o.assumption} (axis {o.axis}) — prior {o.prior} ({o.confirmed}/{o.attempted})" for o in f[:8]]
        if b:
            L.append("### Barren (refuted dead ends — now down-weighted everywhere):")
            L += [f"- {o.domain}:{o.assumption} (axis {o.axis}) — prior {o.prior}" for o in b[:8]]
        if self.discovered:
            L.append(f"### Discovered (emergent, worth promoting): {len(self.discovered)}")
        return "\n".join(L)
