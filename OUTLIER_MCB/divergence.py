"""divergence — a divergent-thinking engine with the four classic creativity metrics.

Literature: Guilford's divergent-thinking factors — FLUENCY (how many ideas), FLEXIBILITY (how many
different categories), ORIGINALITY (how rare/distinct), ELABORATION (how developed) — and Boden's three
kinds of creativity: COMBINATIONAL (new combinations of familiar ideas), EXPLORATORY (new points within an
existing conceptual space), TRANSFORMATIONAL (changing the space itself). Human divergent thinking is the
ability to produce many genuinely-different alternatives, not paraphrases — so this engine explicitly
penalizes near-duplicates and lexical-only variation.

It reuses OUTLIER_MCB's operators (each move already declares which assumption/axis it breaks) and maps
each to a Boden category, then keeps a paraphrase-pruned set and scores it. Pure-Python, deterministic.

Collaborators: generators (the moves), invent._mutate (variation), scoring._mean_pairwise via tokens here.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .generators import Candidate, generate_candidates, breakable, dissolve, invert_assumption, scale_break

# operator → Boden's kind of creativity
_BODEN = {"recombine": "combinational", "unify": "combinational",
          "invert": "exploratory", "scale": "exploratory", "instrument": "exploratory", "reframe": "exploratory",
          "dissolve": "transformational", "transport": "transformational", "abduce": "exploratory",
          "dialectic": "combinational", "proposed": "exploratory"}


def _toks(text: str):
    return {w for w in "".join(c if c.isalnum() else " " for c in str(text).lower()).split() if len(w) > 3}


def _similarity(a: str, b: str) -> float:
    ta, tb = _toks(a), _toks(b)
    return len(ta & tb) / len(ta | tb) if (ta or tb) else 0.0


@dataclass
class DivergentIdea:
    candidate: Candidate
    breaks_rule: str                 # the assumption/axis this idea breaks (declared, never implicit)
    boden_category: str              # combinational | exploratory | transformational
    elaboration: float               # how developed: breaks + needs + a discipline/world-test


@dataclass
class DivergenceResult:
    prompt: str
    ideas: List[DivergentIdea] = field(default_factory=list)
    fluency_score: float = 0.0       # distinct ideas produced, vs the target n
    flexibility_score: float = 0.0   # distinct Boden categories / axes covered
    originality_score: float = 0.0   # 1 − the LEAST-original pair's similarity (penalizes any near-duplicate)
    elaboration_score: float = 0.0   # mean development of the ideas
    semantic_distance_score: float = 0.0   # mean pairwise distance (overall spread)

    def markdown(self) -> str:
        L = [f"## divergence — «{self.prompt}»",
             f"- fluency {self.fluency_score} · flexibility {self.flexibility_score} · originality "
             f"{self.originality_score} · elaboration {self.elaboration_score} · spread {self.semantic_distance_score}"]
        for d in self.ideas:
            L.append(f"- [{d.boden_category}] breaks {d.breaks_rule or '—'} → «{d.candidate.name}»")
        return "\n".join(L)


def _pool(pack, prompt: str) -> List[Candidate]:
    """A wide pool: the standard generators across every axis, plus one mutation per breakable assumption,
    so all three Boden categories can appear (combinational/exploratory/transformational)."""
    pool = list(generate_candidates(pack, prompt))
    for a in breakable(pack):
        for fn in (lambda n: invert_assumption(pack, n), lambda n: dissolve(pack, n),
                   lambda n: scale_break(pack, n, factor=1000)):
            c = fn(a.name)
            if c is not None:
                pool.append(c)
    return pool


def diverge(prompt: str, n: int = 8, axes: Optional[List[str]] = None, constraints: Optional[Dict] = None,
            pack=None, paraphrase_threshold: float = 0.6, embedder=None) -> DivergenceResult:
    """Produce up to `n` GENUINELY-different ideas for `prompt`, each declaring the rule it breaks.

    `axes` restricts to ideas breaking those axes (a constraint on the search). Paraphrases are pruned: an
    idea too similar (≥ `paraphrase_threshold`) to one already chosen is dropped — divergence must be
    conceptual, not a reword. `embedder` (embeddings.CallableEmbedder) switches similarity from lexical
    (default) to SEMANTIC, so a paraphrase with different words is still pruned. Returns the ideas + scores."""
    if pack is None:
        from .pack import select_pack
        pack, _ = select_pack(prompt)
    if embedder is None:                                  # resolve the process-wide default (semantic if registered)
        from .embeddings import default_embedder
        embedder = default_embedder()
    sim = lambda a, b: 1.0 - embedder.distance(a, b)
    candidates = _pool(pack, prompt)
    if axes:
        wanted = {a.upper() for a in axes}
        candidates = [c for c in candidates if set(c.breaks) & wanted]
    if constraints and constraints.get("operators"):
        ops = set(constraints["operators"])
        candidates = [c for c in candidates if c.operator in ops]

    # greedy paraphrase pruning: keep an idea only if it is far enough from every idea already kept
    chosen: List[Candidate] = []
    for c in sorted(candidates, key=lambda c: (-len(set(c.breaks)), c.name)):
        if len(chosen) >= n:
            break
        if all(sim(c.negation, k.negation) < paraphrase_threshold for k in chosen):
            chosen.append(c)

    ideas = []
    for c in chosen:
        elab = round((bool(c.breaks) + bool(c.needs) + bool(c.discipline)) / 3.0, 3)
        ideas.append(DivergentIdea(candidate=c, breaks_rule=(c.assumptions[0] if c.assumptions else (c.breaks[0] if c.breaks else "")),
                                   boden_category=_BODEN.get(c.operator, "exploratory"), elaboration=elab))

    # ── the four divergent-thinking scores ──
    fluency = round(min(1.0, len(ideas) / max(1, n)), 3)
    cats = {d.boden_category for d in ideas} | {b for d in ideas for b in d.candidate.breaks}
    flexibility = round(min(1.0, len(cats) / max(1, (3 + len(pack.axes)))), 3)
    sims = [sim(a.candidate.negation, b.candidate.negation)
            for i, a in enumerate(ideas) for b in ideas[i + 1:]]
    originality = round(1.0 - max(sims), 3) if sims else (1.0 if ideas else 0.0)
    spread = round(sum(1.0 - s for s in sims) / len(sims), 3) if sims else (1.0 if ideas else 0.0)
    elaboration = round(sum(d.elaboration for d in ideas) / len(ideas), 3) if ideas else 0.0

    return DivergenceResult(prompt=prompt, ideas=ideas, fluency_score=fluency, flexibility_score=flexibility,
                            originality_score=originality, elaboration_score=elaboration,
                            semantic_distance_score=spread)
