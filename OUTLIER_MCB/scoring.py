"""scoring — a multi-factor idea score, replacing distance-alone ranking.

Distance from the box rewards strangeness. A real score also asks whether an idea is useful,
implementable, verifiable, and what it risks and costs. The composite GATES novelty by verifiability
and implementability, so an idea that is far-but-unbuildable cannot outrank a grounded, checkable one.

Collaborators: invent.box_distance (the novelty term); grounding.RepoContext (what 'implementable' means here).
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class ScoreWeights:
    """The composite weights — a HYPOTHESIS, not a truth. Configurable, and calibratable against labelled
    data (calibrate_weights). The defaults make usefulness lead; change them and the ranking changes."""
    usefulness: float = 0.35
    depth: float = 0.25
    novelty: float = 0.25
    simplicity: float = 0.15      # weight on (1 - risk)
    cost: float = 0.10            # subtracted

    def composite(self, f: Dict[str, float]) -> float:
        value = (self.usefulness * f["usefulness"] + self.depth * f["depth"]
                 + self.novelty * f["novelty"] + self.simplicity * (1.0 - f["risk"]))
        return round(max(0.0, value - self.cost * f["cost"]), 3)


def default_score_weights() -> ScoreWeights:
    """The default composite weights (a hypothesis, not a dogma — override via score_idea(weights=...))."""
    return ScoreWeights()


def synergy_score(combined: float, parts: List[float]) -> float:
    """How much a RECOMBINATION amplifies, in [0,1]: the margin by which the whole beats its best part,
    normalized on the whole. 0 ⇒ a mere sum (no amplification, a dead collage); →1 ⇒ the combination is
    decisively more than any component alone. Feed the result to kernel.novelty_score(synergy=…), which
    now rescues a live collage PROPORTIONALLY to this strength instead of with a flat bonus."""
    if not parts:
        return 0.0
    best_part = max(parts)
    gain = combined - best_part
    # HONESTY FIX (#12): a tiny ABSOLUTE amplification over near-dead parts (best=0.05, combined=0.10) must not
    # read as half-maximal synergy just because the ratio (combined-best)/combined is large. Require a real
    # absolute gain before any synergy is credited, so a dead collage is not rescued by scale-invariance.
    if combined <= 0 or gain < 0.1:
        return 0.0
    return round(max(0.0, min(1.0, gain / combined)), 3)


def score_idea(candidate, pack=None, repo=None, grounded: Optional[bool] = None,
               weights: Optional[ScoreWeights] = None, novelty_archive=None) -> Dict[str, float]:
    """Score a Candidate on grounded factors and a gated composite, each in [0,1].

      novelty          how far from the average answer (box_distance, normalized); FORMALIZED by Novelty
                       Search (sparseness vs an archive of our own prior ideas) when `novelty_archive` is given
      depth            how much it COMPRESSES the domain (MDL: explains more with less) — needs `pack`
      verifiability    can it actually be settled by a runnable check? (grounded)
      implementability does it attach to a real component of the project?
      usefulness       verifiable + implementable (it changes something checkable)
      risk             how much it touches (more axes/assumptions ⇒ more to get wrong)
      cost             how much new information it needs

    composite = (novelty + depth) gated by (verifiability, implementability) − risk − cost, so neither
    strangeness nor baroque-ness wins: a grounded, checkable, COMPRESSING difference does.

    `novelty_archive` (a novelty_archive.NoveltyArchive): when supplied, the novelty factor stops being a
    fixed hand-weighted distance and becomes RELATIVE — an idea is novel only if it is sparse (far) among the
    ideas already proposed (Lehman & Stanley 2011). This formalizes and strengthens `box_distance`.
    """
    from .invent import box_distance
    from .greenstar import extrapolation
    is_grounded = bool(grounded if grounded is not None else (repo is not None and getattr(repo, "grounded", False)))
    # one novelty number: WITHIN the domain (box_distance) blended with BEYOND all domains (extrapolation),
    # so the two metrics no longer rank an idea differently with no resolution.
    within = min(1.0, box_distance(candidate, grounded=True) / 8.0)
    beyond = extrapolation(candidate)
    novelty = round(0.7 * within + 0.3 * beyond, 2)
    if novelty_archive is not None:
        # Novelty Search: blend in the sparseness of this idea vs our OWN archive of prior ideas, so novelty
        # is measured relative to what we have already had — the formal version of box_distance.
        from .novelty_archive import behavior_descriptor
        sparseness = novelty_archive.calculate_novelty(behavior_descriptor(candidate))
        novelty = round(0.5 * within + 0.2 * beyond + 0.3 * sparseness, 2)
    depth = 0.0
    if pack is not None:
        from .compression import compression_gain
        depth = compression_gain(candidate, pack)["compression_gain"]
    verifiability = 1.0 if is_grounded else 0.3
    implementability = 0.8 if (repo is not None and candidate.breaks) else (0.5 if candidate.breaks else 0.3)
    usefulness = round(0.5 * verifiability + 0.5 * implementability, 2)
    risk = min(1.0, (len(set(candidate.breaks)) + len(candidate.assumptions)) / 5.0)
    cost = min(1.0, len(candidate.needs) / 3.0)
    factors = {"novelty": round(novelty, 2), "depth": round(depth, 2), "usefulness": usefulness,
               "implementability": round(implementability, 2), "verifiability": round(verifiability, 2),
               "risk": round(risk, 2), "cost": round(cost, 2)}
    # BETTER beats different: usefulness LEADS, novelty contributes but does NOT dominate. The weights are
    # a hypothesis (ScoreWeights) — change them and the ranking changes; calibrate them against labelled data.
    factors["composite"] = (weights or ScoreWeights()).composite(factors)
    # FIX A/D generative steering: when the domain declares UNIVERSAL CLOSURES, an idea INSIDE one cannot win
    # (it is the box), and an idea that EXITS the closure or requires NEW INFORMATION is rewarded — the only
    # real openings the representation theorem leaves. Gated on `universal_closures`, so packs without them are
    # scored identically to before (no regression).
    if pack is not None and getattr(pack, "universal_closures", None):
        from .closures import closure_membership
        verdict = closure_membership(candidate, pack)["verdict"]
        if verdict == "INSIDE_THE_BOX":
            factors["composite"] = round(factors["composite"] * 0.4, 3)   # inside a closure → cannot outrank an exit
            factors["closure_penalty"] = 1.0
        elif verdict == "OUTSIDE_DECLARED_CLOSURES":
            # a PROVEN closure-escape is the strongest admissible exit → the largest bonus.
            factors["composite"] = round(min(1.0, factors["composite"] + 0.20), 3)
            factors["closure_escape_bonus"] = 1.0
            if candidate.needs:
                factors["new_information_bonus"] = 1.0
        elif candidate.needs:
            # HONESTY FIX (#3): requiring NEW INFORMATION is an admissible exit, but here the membership is
            # UNKNOWN — the idea might still be INSIDE the box. Reward it only modestly, and never as much as a
            # PROVEN escape, so a cheap `needs` declaration cannot outrank a proven exit or a checkable idea.
            factors["composite"] = round(min(1.0, factors["composite"] + 0.08), 3)
            factors["new_information_bonus"] = 1.0
    return factors


# a small, principled grid of weightings to search during calibration (each sums to 1.0 on the + terms).
_GRID = [
    ScoreWeights(0.35, 0.25, 0.25, 0.15, 0.10),     # default: usefulness leads
    ScoreWeights(0.50, 0.20, 0.15, 0.15, 0.10),     # usefulness-heavy
    ScoreWeights(0.20, 0.20, 0.45, 0.15, 0.05),     # novelty-heavy
    ScoreWeights(0.25, 0.40, 0.20, 0.15, 0.10),     # depth-heavy
    ScoreWeights(0.30, 0.25, 0.25, 0.20, 0.15),     # simplicity/parsimony-heavy
]


def calibrate_weights(good: List, bad: List, pack=None, repo=None, grid=None) -> Dict:
    """Pick the ScoreWeights that best SEPARATE a labelled `good` set from a `bad` set — the eval feeding
    back into the scoring, so the weights stop being hand-tuned truth. Returns the best weights + the
    separation it achieves (mean good composite − mean bad composite)."""
    grid = grid or _GRID

    def mean_composite(cands, w):
        scores = [score_idea(c, pack=pack, repo=repo, weights=w)["composite"] for c in cands]
        return sum(scores) / len(scores) if scores else 0.0

    best, best_sep = grid[0], float("-inf")
    for w in grid:
        sep = mean_composite(good, w) - mean_composite(bad, w)
        if sep > best_sep:
            best, best_sep = w, sep
    return {"weights": best, "separation": round(best_sep, 3)}
