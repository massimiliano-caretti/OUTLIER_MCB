"""evolution_memory — a persistent, lineage-tracked population of evaluated candidates.

The AlphaEvolve-useful idea, taken honestly: to invent, the engine must ACCUMULATE attempts — successes,
failures, and their genealogy — not generate ideas and forget them. This complements the existing
DiscoveryMemory (assumption-level fertility) and the Ledger (axis×operator pricing) with a CANDIDATE-level
evolutionary record: who its parents were, which mutation produced it, what an objective evaluator scored,
how it compared to baseline/parent, and — crucially — whether it was actually VERIFIED (no evaluator ⇒ not
verified, by construction). Persistent JSONL so a population compounds across runs.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional


@dataclass
class EvolutionRecord:
    id: str
    problem: str
    candidate_name: str
    claim: str = ""
    parent_ids: List[str] = field(default_factory=list)
    generation: int = 0
    broken_assumptions: List[str] = field(default_factory=list)
    source_patch_or_program: str = ""
    evaluator_name: str = ""
    external_resolver: str = ""      # the name of the EXTERNAL resolver that settled it (repo/data/world); "" = self-judged only
    score: float = 0.0
    score_components: Dict[str, float] = field(default_factory=dict)
    correctness_passed: bool = False
    novelty_scope: str = ""
    prior_art_scoped_verdict: str = ""
    baseline_score: Optional[float] = None
    parent_score: Optional[float] = None
    improvement_over_baseline: Optional[float] = None
    improvement_over_parent: Optional[float] = None
    mutation_operator: str = ""
    created_at: str = ""
    metadata: Dict = field(default_factory=dict)

    @property
    def verified(self) -> bool:
        """A record is VERIFIED only if an evaluator actually ran AND its correctness gate passed. No
        evaluator ⇒ a hypothesis, never a verified result (the spec's hard rule)."""
        return bool(self.evaluator_name) and bool(self.correctness_passed)

    @property
    def externally_settled(self) -> bool:
        """The STRONGER gate (fix A): certified only if an EXTERNAL resolver — a repo test that flips, the
        data, a red-team, a world-test — settled it. An internal score (self-judgment) is never enough; this
        is what separates a settled discovery from a merely high-scoring one. Implies `verified`."""
        return bool(self.external_resolver) and bool(self.correctness_passed)

    @property
    def is_improvement(self) -> bool:
        """Beat baseline OR parent on the objective — not merely 'different'."""
        return bool((self.improvement_over_baseline or 0) > 0 or (self.improvement_over_parent or 0) > 0)


def _text(r: EvolutionRecord) -> str:
    return f"{r.candidate_name} {r.claim} {' '.join(r.broken_assumptions)}"


@dataclass
class EvolutionMemory:
    records: Dict[str, EvolutionRecord] = field(default_factory=dict)

    def add(self, record: EvolutionRecord) -> EvolutionRecord:
        self.records[record.id] = record
        return record

    def get(self, rid: str) -> Optional[EvolutionRecord]:
        return self.records.get(rid)

    def all(self) -> List[EvolutionRecord]:
        return list(self.records.values())

    def by_problem(self, problem: str) -> List[EvolutionRecord]:
        return [r for r in self.records.values() if r.problem == problem]

    def top_k(self, k: int = 5, problem: Optional[str] = None) -> List[EvolutionRecord]:
        pool = self.by_problem(problem) if problem else self.all()
        return sorted(pool, key=lambda r: (-r.score, r.id))[:k]

    def diverse_top_k(self, k: int = 5, problem: Optional[str] = None, embedder=None) -> List[EvolutionRecord]:
        """Quality-Diversity selection: greedily pick high-score records that are also far (semantic
        distance) from those already chosen — best of each KIND, not k copies of the same idea."""
        from .embeddings import semantic_distance
        pool = sorted(self.by_problem(problem) if problem else self.all(), key=lambda r: -r.score)
        chosen: List[EvolutionRecord] = []
        for r in pool:
            if len(chosen) >= k:
                break
            if all(semantic_distance(_text(r), _text(c), embedder=embedder) > 0.15 for c in chosen):
                chosen.append(r)
        for r in pool:                                   # backfill if diversity left fewer than k
            if len(chosen) >= k:
                break
            if r not in chosen:
                chosen.append(r)
        return chosen[:k]

    def parents(self, rid: str) -> List[EvolutionRecord]:
        r = self.get(rid)
        return [self.records[p] for p in (r.parent_ids if r else []) if p in self.records]

    def lineage(self, rid: str) -> List[EvolutionRecord]:
        """The full ancestry chain (this record first, then ancestors), de-duplicated, breadth-first."""
        out, seen, frontier = [], set(), [rid]
        while frontier:
            cur = frontier.pop(0)
            if cur in seen or cur not in self.records:
                continue
            seen.add(cur)
            out.append(self.records[cur])
            frontier.extend(self.records[cur].parent_ids)
        return out

    def dedupe_near_duplicates(self, threshold: float = 0.08, embedder=None) -> int:
        """Drop NEAR-DUPLICATES (same idea, ~same text) keeping the higher-scoring one. Genuinely different
        candidates (distance > threshold) are KEPT — diversity is not collapsed. Returns #removed."""
        from .embeddings import semantic_distance
        kept: List[EvolutionRecord] = []
        removed = 0
        for r in sorted(self.records.values(), key=lambda r: -r.score):
            dup = next((c for c in kept if semantic_distance(_text(r), _text(c), embedder=embedder) <= threshold), None)
            if dup is None:
                kept.append(r)
            else:
                removed += 1
        self.records = {r.id: r for r in kept}
        return removed

    def save_jsonl(self, path: str) -> None:
        import json
        with open(path, "w") as fh:
            for r in self.records.values():
                fh.write(json.dumps(asdict(r)) + "\n")

    @classmethod
    def load_jsonl(cls, path: str) -> "EvolutionMemory":
        import json
        import os
        mem = cls()
        if not os.path.exists(path):
            return mem
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if line:
                    mem.add(EvolutionRecord(**json.loads(line)))
        return mem

    def markdown(self) -> str:
        v = sum(r.verified for r in self.records.values())
        imp = sum(r.is_improvement for r in self.records.values())
        return (f"## Evolution memory — {len(self.records)} candidates "
                f"({v} verified, {imp} improvements over baseline/parent)")
