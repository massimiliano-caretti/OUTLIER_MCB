"""metrics — measure the VALUE of a pool of ideas, not just that the code runs.

`health()` measures yield and wiring (does the engine produce / is it used). These metrics measure
whether the ideas are actually GOOD: falsifiable, specific, distinct, grounded — the external value the
eval harness scores. They operate on a pool of `Candidate`s (optionally with a real `RepoContext`), need
NO external LLM, and combine into a single Verified Novelty Score so a mode can be compared to a baseline.

Honest scope: these score STRUCTURE (is the idea falsifiable, distinct, grounded?), not human-judged
usefulness — that still needs a person or a stronger model. They make the engine's claims FALSIFIABLE.

Collaborators: generators.Candidate; repo_world.compile_world_test (for grounding-based metrics).
"""
from __future__ import annotations
from typing import Dict, List, Optional


def _key(c):
    return (c.name, c.operator, tuple(c.breaks), tuple(c.assumptions), c.negation)


def broken_assumption_rate(cands: List) -> float:
    """Fraction of candidates that actually break ≥1 axis (vs sit in the box)."""
    return round(sum(1 for c in cands if c.breaks) / len(cands), 3) if cands else 0.0


def falsifiability_score(cands: List) -> float:
    """Fraction that carry a non-empty discipline — a stated way the idea could die."""
    return round(sum(1 for c in cands if (c.discipline or "").strip()) / len(cands), 3) if cands else 0.0


def unique_frontier_ratio(cands: List) -> float:
    """Distinct ideas / total — 1.0 means no duplicate bets."""
    return round(len({_key(c) for c in cands}) / len(cands), 3) if cands else 0.0


def rebranding_risk_rate(cands: List) -> float:
    """Fraction at risk of being a lexical re-skin: it breaks NO axis AND produces no new output — a
    rename, not a difference. (A genuine operator break — invert/scale/recombine/dialectic — is NOT
    rebranding; an earlier version wrongly penalized every break that needed no new data.)"""
    new_output_ops = ("unify", "instrument", "reframe")
    risky = sum(1 for c in cands if not c.breaks and c.operator not in new_output_ops)
    return round(risky / len(cands), 3) if cands else 0.0


_GENERATIVE_OPERATORS = 6   # recombine · invert · scale · transport · abduce · dialectic (the plural generator)


def operator_diversity(cands: List) -> float:
    """How many DISTINCT mechanisms the pool uses (a one-move engine is worse than a plural one).
    Rewards the plural generator and makes each operator earn its keep under ablation."""
    return round(min(1.0, len({c.operator for c in cands}) / _GENERATIVE_OPERATORS), 3) if cands else 0.0


def _checks(cands: List, repo):
    from .repo_world import compile_world_test
    return [compile_world_test(c.negation, (c.breaks[0] if c.breaks else ""), repo=repo) for c in cands]


def artifact_specificity(cands: List, repo=None) -> float:
    """Fraction whose compiled world-test is a FULL artifact contract (not a bare command)."""
    if not cands:
        return 0.0
    return round(sum(1 for ch in _checks(cands, repo) if ch.is_full_contract) / len(cands), 3)


def auto_verifiability_rate(cands: List, repo=None) -> float:
    """Fraction the engine could settle by RUNNING a grounded, full-contract check (AUTO, not HUMAN)."""
    from .verifier import verifiability_class
    if not cands:
        return 0.0
    return round(sum(1 for ch in _checks(cands, repo) if verifiability_class(ch) == "AUTO") / len(cands), 3)


def verified_novelty_score(cands: List, repo=None) -> float:
    """One falsifiable number in [0,1]: distinct AND breaking AND falsifiable AND not-rebranding, lifted
    by grounding. A naive pool (duplicates, no falsifiers, ungrounded) scores low; a deduped, grounded,
    disciplined frontier scores high."""
    if not cands:
        return 0.0
    base = (broken_assumption_rate(cands) * unique_frontier_ratio(cands)
            * falsifiability_score(cands) * (1.0 - rebranding_risk_rate(cands)))
    grounding = 0.5 + 0.5 * auto_verifiability_rate(cands, repo)     # grounding lifts, never below half
    diversity = 0.6 + 0.4 * operator_diversity(cands)               # a plural pool beats a one-move pool
    return round(base * grounding * diversity, 3)


def score_pool(cands: List, repo=None) -> Dict[str, float]:
    """All metrics for a pool of candidates — the row an eval writes per (task, mode)."""
    return {
        "n": len(cands),
        "broken_assumption_rate": broken_assumption_rate(cands),
        "falsifiability_score": falsifiability_score(cands),
        "unique_frontier_ratio": unique_frontier_ratio(cands),
        "rebranding_risk_rate": rebranding_risk_rate(cands),
        "operator_diversity": operator_diversity(cands),
        "artifact_specificity": artifact_specificity(cands, repo),
        "auto_verifiability_rate": auto_verifiability_rate(cands, repo),
        "verified_novelty_score": verified_novelty_score(cands, repo),
    }


# ── discovery confidence (Step 5): a CONSERVATIVE composite that cannot be high on a weak link ──────────
def discovery_confidence(structure: float = 0.0, prior_art_distance: float = 0.0,
                         semantic_novelty: float = 0.0, materialization: float = 0.0,
                         verification: float = 0.0, novelty_scope: str = "LOCAL_ONLY") -> Dict:
    """A single, deliberately PESSIMISTIC discovery score in [0,1] — it separates 'tidy / different / useful
    / verified / actually promising'. The rule is honesty by hard caps, not a flattering weighted average:

      • no successful ONLINE prior-art search → global novelty cannot be trusted → capped at 0.5;
      • not materialized (no executed test/patch/data) → capped at 0.5;
      • not externally verified → capped at 0.6.

    So a paraphrase (high semantic_novelty, no prior-art scope, no verification) stays LOW, and only an idea
    that is novel-on-checked-sources AND materialized AND verified can approach 1.0. Returns the number, the
    caps that fired, and the components — never a bare figure."""
    comp = {"structure": round(float(structure), 3), "prior_art_distance": round(float(prior_art_distance), 3),
            "semantic_novelty": round(float(semantic_novelty), 3),
            "materialization": round(float(materialization), 3), "verification": round(float(verification), 3)}
    base = (0.25 * comp["structure"] + 0.20 * comp["prior_art_distance"] + 0.15 * comp["semantic_novelty"]
            + 0.20 * comp["materialization"] + 0.20 * comp["verification"])
    conf = base
    caps: List[str] = []
    if novelty_scope != "ONLINE_PRIOR_ART_CHECKED":
        conf = min(conf, 0.5); caps.append(f"novelty_scope={novelty_scope}: no confirmed online prior-art search")
    if comp["materialization"] < 0.5:
        conf = min(conf, 0.5); caps.append("not materialized: no executed test/patch/data")
    if comp["verification"] <= 0.0:
        conf = min(conf, 0.6); caps.append("not externally verified")
    return {"discovery_confidence": round(max(0.0, conf), 3), "caps_applied": caps,
            "novelty_scope": novelty_scope, "components": comp}
