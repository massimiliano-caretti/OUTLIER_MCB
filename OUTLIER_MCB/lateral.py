"""lateral — human-like lateral-thinking moves + open-ended search discipline, taken SELECTIVELY from the
competitor landscape and bent to OUTLIER_MCB's thesis (invent the non-obvious, then falsify it).

What was taken, and from where:
  • provocation (de Bono's PO)         — assert a deliberately FALSE/absurd premise and mine its kernel;
  • random_entry (Koestler bisociation)— inject a random DISTANT concept and force a connection;
  • novelty rejection sampling (ShinkaEvolve) — refuse to evaluate a candidate too similar to the archive,
                                          so the budget buys genuine difference, not minor variations;
  • novelty-first selection (Stanley & Lehman, 'abandon the objective') — sometimes pick by NOVELTY alone,
                                          ignoring fitness, to escape the deception of the objective;
  • OperatorBandit (UCB)               — allocate the next move to the operator that has been paying off.

What was deliberately NOT taken: the Darwin Gödel Machine's wholesale self-code-rewriting (it conflicts with
the anti-self-deception discipline), and benchmark-chasing. Every move here is still a STEPPING STONE — kept
only for the kernel that survives a world-test; the provocation itself is discarded.
"""
from __future__ import annotations
import math
import random as _random
from typing import List, Optional

from .generators import Candidate, breakable, conceptual_blend


# ── lateral-thinking generative moves ─────────────────────────────────────────────────────────────────
def provocation(pack, assumption_name: str = "") -> Optional[Candidate]:
    """de Bono's PROVOCATION (PO): assert the EXTREME OPPOSITE of a box assumption as a deliberately false
    premise — not to defend it, but to mine the useful kernel it suggests. A stepping stone, not a claim."""
    by = pack.by_name()
    box = [a for a in pack.assumptions if a.name in pack.box_assumptions and pack.dimension_of.get(a.name)]
    a = by.get(assumption_name) or (box[0] if box else (breakable(pack)[0] if breakable(pack) else None))
    if a is None:
        return None
    axis = pack.dimension_of.get(a.name, "")
    return Candidate(
        name=f"PO({a.name})", operator="provocation", breaks=[axis] if axis else [], assumptions=[a.name],
        negation=(f"PROVOCATION (PO — a deliberately false premise to mine, then discard): assume the ABSURD "
                  f"OPPOSITE of «{a.description.rstrip('.')}» — i.e. {a.if_false} — taken to the extreme. Do NOT "
                  f"defend it; EXTRACT the one mechanism it suggests that could actually work."),
        discipline=("a provocation is a stepping stone, not a claim: keep ONLY the kernel that survives a "
                    "world-test; the absurd premise itself is thrown away."))


def random_entry(pack, rng=None) -> Optional[Candidate]:
    """Koestler's BISOCIATION / de Bono's RANDOM ENTRY: inject a RANDOM concept from a DISTANT domain and
    force a connection. Unlike a directed blend (top break × top break), the foreign concept is chosen at
    random — the unexpected adjacency is the point. Deterministic via a seeded `rng`."""
    from .pack import list_packs, get_pack
    rng = rng or _random.Random(0)
    foreigns = [get_pack(n) for n in list_packs() if n not in (pack.name, "generic") and breakable(get_pack(n))]
    if not foreigns:
        return None
    fp = foreigns[rng.randrange(len(foreigns))]
    fb = breakable(fp)
    rand_assumption = fb[rng.randrange(len(fb))].name
    blend = conceptual_blend(pack, fp, name_b=rand_assumption)
    if blend is None:
        return None
    blend.operator = "random_entry"
    blend.name = f"random_entry({rand_assumption}@{fp.name}→{pack.name})"
    blend.discipline = ("forced connection of a RANDOM distant concept — most will be nonsense; keep only "
                        "the one whose world-test passes where neither domain's break passes alone.")
    return blend


# ── novelty rejection sampling (don't waste the budget on minor variations) ──────────────────────────
def is_novel_enough(text: str, archive_texts: List[str], threshold: float = 0.85, embedder=None) -> tuple:
    """Refuse a candidate too similar to the archive. Returns (accept, max_similarity). similarity =
    1 − semantic distance; reject when the closest archived item is more similar than `threshold`."""
    from .embeddings import semantic_distance
    if not archive_texts:
        return True, 0.0
    mx = max(1.0 - semantic_distance(text, t, embedder=embedder) for t in archive_texts)
    return (mx <= threshold), round(mx, 3)


# ── novelty-first selection: abandon the objective to escape its deception ───────────────────────────
def novelty_first(records, k: int = 3, embedder=None) -> List:
    """Select the SPARSEST records (farthest from the rest), IGNORING fitness — Stanley & Lehman's
    'search for novelty alone'. The stepping stone the objective would overlook is exactly where the
    non-obvious invention hides."""
    from .embeddings import semantic_distance
    recs = list(records)
    if len(recs) <= k:
        return recs
    texts = [f"{getattr(r, 'candidate_name', '')} {getattr(r, 'claim', '')}" for r in recs]

    def sparseness(i: int) -> float:
        ds = [semantic_distance(texts[i], texts[j], embedder=embedder) for j in range(len(recs)) if j != i]
        return sum(ds) / len(ds) if ds else 1.0
    order = sorted(range(len(recs)), key=lambda i: -sparseness(i))
    return [recs[i] for i in order[:k]]


# ── UCB bandit over operators (allocate moves to what pays off) ──────────────────────────────────────
class OperatorBandit:
    """UCB1 over a set of operator names: balance exploiting the operator with the best mean reward and
    exploring the under-tried ones. `record(op, reward∈[0,1])`; `select()` returns the next operator."""
    def __init__(self, operators: List[str], c: float = 1.4):
        self.ops = list(operators)
        self.c = c
        self.n = {o: 0 for o in self.ops}
        self.total_reward = {o: 0.0 for o in self.ops}
        self.t = 0

    def record(self, op: str, reward: float) -> None:
        if op not in self.n:
            self.ops.append(op); self.n[op] = 0; self.total_reward[op] = 0.0
        self.n[op] += 1
        self.total_reward[op] += max(0.0, min(1.0, float(reward)))
        self.t += 1

    def mean(self, op: str) -> float:
        return round(self.total_reward[op] / self.n[op], 3) if self.n[op] else 0.0

    def select(self) -> str:
        untried = [o for o in self.ops if self.n[o] == 0]
        if untried:
            return untried[0]
        return max(self.ops, key=lambda o: self.mean(o) + self.c * math.sqrt(math.log(self.t) / self.n[o]))
