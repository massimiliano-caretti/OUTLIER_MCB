"""novelty_archive — formal Novelty Search (sparseness in behavior space).

Literature: Lehman & Stanley, "Abandoning Objectives: Evolution through the Search for Novelty Alone"
(Novelty Search, 2011). The core finding: rewarding an individual for being DIFFERENT from everything seen
so far — its sparseness among prior behaviors — can out-explore an objective-driven search, because it
escapes deceptive local optima the objective gets stuck in. That is precisely the trap OUTLIER_MCB exists
to avoid: optimizing the loss function (the average answer) is the deceptive objective; novelty search is
the disciplined way out.

This formalizes the library's informal `box_distance`: instead of a fixed hand-weighted distance, novelty is
measured RELATIVE to an archive of everything already proposed — an idea is novel only if it is far from the
ideas we have already had. The behavior descriptor (BD) is a lightweight lexical embedding of the candidate's
generative statement; novelty is the mean distance to the k nearest prior BDs (sparseness).

NOTE: this is the *internal* novelty of the search (distance from our OWN prior ideas). It is distinct from
`novelty.py` (real-world prior-art search) and `novelty.world_novelty_score` (distance from the REAL world).
The two compose: novelty_search drives divergent generation; novelty.novelty_audit checks the survivor is
not merely a rename of existing work.

Pure-Python, deterministic, no embeddings library. Collaborators: generators.Candidate (the genome).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Set

_STOP = {"the", "a", "an", "of", "to", "is", "are", "be", "by", "for", "on", "in", "and", "or", "as",
         "it", "this", "that", "with", "not", "can", "could", "should", "make", "new", "use", "via",
         "could", "may", "might", "over", "into", "than", "then", "so"}


def _tokens(text: str) -> Set[str]:
    return {w for w in "".join(c if c.isalnum() else " " for c in (text or "").lower()).split()
            if len(w) > 3 and w not in _STOP}


def behavior_descriptor(candidate) -> Set[str]:
    """A lightweight, deterministic BD: the token set of the candidate's generative statement + the axes it
    breaks + the assumptions it touches. Stands in for a learned embedding without any heavy dependency."""
    parts = [getattr(candidate, "negation", ""), getattr(candidate, "name", "")]
    parts += list(getattr(candidate, "breaks", []) or [])
    parts += list(getattr(candidate, "assumptions", []) or [])
    return _tokens(" ".join(parts))


def _distance(a: Set[str], b: Set[str]) -> float:
    """Behavioral distance in [0,1]: 1 − Jaccard similarity (0 = identical behavior, 1 = disjoint)."""
    if not a and not b:
        return 0.0
    return 1.0 - len(a & b) / len(a | b)


@dataclass
class NoveltyArchive:
    """An archive of behavior descriptors of past candidates, with sparseness-based novelty (Lehman & Stanley).

    `calculate_novelty` is the sparseness ρ(x) = mean distance to the k nearest neighbors in the archive;
    `add_if_novel` admits a BD only when its novelty clears a DYNAMIC threshold (the archive's current mean
    novelty), so the bar rises as the space fills — the standard adaptive-threshold novelty-search policy.
    """
    descriptors: List[Set[str]] = field(default_factory=list)
    k: int = 10

    def calculate_novelty(self, candidate_bd: Set[str], k: int = None) -> float:
        """Sparseness: the mean behavioral distance from `candidate_bd` to its k nearest neighbors in the
        archive (in [0,1]). An empty archive returns 1.0 — nothing seen yet, so everything is maximally novel."""
        if not self.descriptors:
            return 1.0
        kk = k or self.k
        dists = sorted(_distance(candidate_bd, d) for d in self.descriptors)
        nearest = dists[:max(1, min(kk, len(dists)))]
        return round(sum(nearest) / len(nearest), 3)

    def mean_novelty(self) -> float:
        """The archive's current average sparseness — the dynamic novelty threshold for admission."""
        if len(self.descriptors) < 2:
            return 0.0
        vals = [self.calculate_novelty(d) for d in self.descriptors]
        return round(sum(vals) / len(vals), 3)

    def add_if_novel(self, candidate_bd: Set[str], threshold: float = None) -> bool:
        """Admit `candidate_bd` only if its novelty exceeds the threshold (default: the archive's current mean
        novelty — a self-adjusting bar). Always admits the first descriptor. Returns True if admitted."""
        if not self.descriptors:
            self.descriptors.append(set(candidate_bd))
            return True
        bar = self.mean_novelty() if threshold is None else threshold
        if self.calculate_novelty(candidate_bd) > bar:
            self.descriptors.append(set(candidate_bd))
            return True
        return False

    def add(self, candidate_bd: Set[str]) -> None:
        """Unconditionally record a BD (use when you want the archive to remember everything seen)."""
        self.descriptors.append(set(candidate_bd))

    def __len__(self) -> int:
        return len(self.descriptors)
