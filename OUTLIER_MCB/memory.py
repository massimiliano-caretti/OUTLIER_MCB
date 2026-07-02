"""memory — two memory forms the engine asked for (judge on the `meta` pack), complementary to the others.

The engine already has: a QDArchive (within-run working memory of best-of-kind), a Ledger (axis×operator
strategy pricing), a NoveltyArchive (sparseness vs own ideas), and DiscoveryMemory (single-assumption
fertility). Interrogated about what is STILL missing, the engine flagged two — and rejected working-memory
and meta-strategy memory as already covered (honest: it does not duplicate what it has):

  • EpisodicMemory   — full past discovery EPISODES (problem · broken assumption · world-test · outcome),
    recalled by similarity. The inventor's "this reminds me of…": it stops the engine reinventing a dead
    end and lets it reuse a past confirmation (the 'novelty is naming' break — recall, not renaming).
  • AnalogicalMemory — which CROSS-DOMAIN mappings actually transferred and produced emergent value, so a
    fertile analogy can be proposed again (the 'pack knowledge in the engine' break — relational knowledge
    that lives across packs, not inside one).

Both are persistent (JSON) and honest: similarity is a lexical/semantic proxy (pluggable embedder), a prior
is evidence not proof, and nothing claims novelty.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .embeddings import semantic_distance


# ── episodic memory ─────────────────────────────────────────────────────────────────────────────────
@dataclass
class Episode:
    problem: str
    assumption: str = ""
    axis: str = ""
    domain: str = ""
    world_test: str = ""
    outcome: str = "OPEN"        # CONFIRMED | REFUTED | OPEN
    score: float = 0.0
    note: str = ""

    def _text(self) -> str:
        return f"{self.problem} {self.assumption} {self.axis} {self.domain}"


@dataclass
class EpisodicMemory:
    episodes: List[Episode] = field(default_factory=list)

    def record(self, episode: Episode) -> Episode:
        self.episodes.append(episode)
        return episode

    def recall(self, query: str, k: int = 3, embedder=None) -> List[Tuple[Episode, float]]:
        """The most SIMILAR past episodes to `query` (similarity = 1 − semantic distance), best first."""
        scored = [(e, round(1.0 - semantic_distance(query, e._text(), embedder=embedder), 3)) for e in self.episodes]
        return sorted(scored, key=lambda t: -t[1])[:k]

    def lessons(self, query: str, k: int = 3, near: float = 0.55, embedder=None) -> str:
        """A one-line lesson from near-matching past episodes: avoid reinventing a REFUTED idea, reuse a
        CONFIRMED one. Empty string if nothing close enough — silence over fabrication."""
        hits = [(e, s) for e, s in self.recall(query, k=k, embedder=embedder) if s >= near]
        if not hits:
            return ""
        parts = []
        for e, s in hits:
            verb = {"REFUTED": "was a DEAD END", "CONFIRMED": "PAID OFF", "OPEN": "is still open"}.get(e.outcome, "seen")
            parts.append(f"«{e.assumption or e.problem[:40]}» {verb} (sim {s})")
        return "recall: " + "; ".join(parts)

    def has_refuted(self, query: str, near: float = 0.8, embedder=None) -> bool:
        """True if a NEAR-IDENTICAL problem (by text similarity) was already refuted. A soft, analogical
        signal — use `refuted_seed` for the precise 'I already tried THIS exact break' check."""
        return any(s >= near and e.outcome == "REFUTED" for e, s in self.recall(query, k=3, embedder=embedder))

    def refuted_seed(self, seed: str, domain: str = "") -> bool:
        """True if breaking THIS exact assumption (`seed`) was already refuted — the precise dead-end guard.
        Identity-based, not similarity-based, so two distinct assumptions with similar templated wording are
        NOT confused for one another (the failure mode that livelocks a similarity-only skip)."""
        return any(e.outcome == "REFUTED" and e.assumption == seed and (not domain or not e.domain or e.domain == domain)
                   for e in self.episodes)

    def save(self, path: str) -> None:
        import json
        with open(path, "w") as fh:
            json.dump([e.__dict__ for e in self.episodes], fh, indent=2)

    @classmethod
    def load(cls, path: str) -> "EpisodicMemory":
        import json
        import os
        if not os.path.exists(path):
            return cls()
        return cls(episodes=[Episode(**d) for d in json.load(open(path))])

    def markdown(self) -> str:
        return f"## Episodic memory — {len(self.episodes)} episodes " \
               f"({sum(e.outcome == 'CONFIRMED' for e in self.episodes)} confirmed, " \
               f"{sum(e.outcome == 'REFUTED' for e in self.episodes)} refuted)"


# ── analogical / transfer memory ──────────────────────────────────────────────────────────────────────
@dataclass
class AnalogyOutcome:
    source_domain: str
    target_domain: str
    mapping: str = ""
    transfers: int = 0
    fails: int = 0
    attempted: int = 0
    emergence: float = 0.0

    @property
    def prior(self) -> float:
        return round(self.transfers / self.attempted, 3) if self.attempted else 0.5

    @property
    def status(self) -> str:
        if self.attempted == 0:
            return "UNTRIED"
        if self.transfers > self.fails and self.prior >= 0.6:
            return "TRANSFERS_WELL"
        if self.fails > self.transfers and self.prior <= 0.34:
            return "STERILE"
        return "MIXED"


@dataclass
class AnalogicalMemory:
    analogies: Dict[str, AnalogyOutcome] = field(default_factory=dict)

    @staticmethod
    def _key(a: str, b: str) -> str:
        return f"{a}->{b}"

    def record(self, source_domain: str, target_domain: str, transferred: bool, mapping: str = "",
               emergence: float = 0.0) -> AnalogyOutcome:
        k = self._key(source_domain, target_domain)
        o = self.analogies.get(k) or AnalogyOutcome(source_domain=source_domain, target_domain=target_domain)
        o.attempted += 1
        if transferred:
            o.transfers += 1
        else:
            o.fails += 1
        o.mapping = mapping or o.mapping
        o.emergence = max(o.emergence, emergence)
        self.analogies[k] = o
        return o

    def prior(self, source_domain: str, target_domain: str) -> float:
        o = self.analogies.get(self._key(source_domain, target_domain))
        return o.prior if o else 0.5

    def fertile(self, min_attempts: int = 1) -> List[AnalogyOutcome]:
        return sorted([o for o in self.analogies.values()
                       if o.status == "TRANSFERS_WELL" and o.attempted >= min_attempts],
                      key=lambda o: -o.prior)

    def save(self, path: str) -> None:
        import json
        with open(path, "w") as fh:
            json.dump({k: o.__dict__ for k, o in self.analogies.items()}, fh, indent=2)

    @classmethod
    def load(cls, path: str) -> "AnalogicalMemory":
        import json
        import os
        if not os.path.exists(path):
            return cls()
        return cls(analogies={k: AnalogyOutcome(**v) for k, v in json.load(open(path)).items()})

    def markdown(self) -> str:
        fert = self.fertile()
        L = [f"## Analogical memory — {len(self.analogies)} domain pairings ({len(fert)} transfer well)"]
        L += [f"- {o.source_domain}→{o.target_domain}: prior {o.prior} (emergence {o.emergence})" for o in fert[:8]]
        return "\n".join(L)
