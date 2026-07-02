"""frontier — a REAL novelty frontier: different in the MECHANISM and the BEHAVIOR, not just the text (#8).

'Different wording' is the cheapest, emptiest novelty. This separates three independent axes:
  • conceptual_novelty — distance of the idea's TEXT/assumptions from an archive (the old, weak signal);
  • behavioral_novelty — distance of the idea's EVALUATOR RESULT (does it pass? what is its component
    signature?) from prior behaviors — two ideas with identical text but different behavior are NOT the same;
  • prior_art_novelty — distance from the real world (a prior-art provider).
frontier_score combines whichever signals are available, keeping conceptual and functional novelty distinct.
"""
from __future__ import annotations
from typing import Dict, List, Optional


def _cand_text(candidate) -> str:
    if isinstance(candidate, str):
        return candidate
    g = lambda k: getattr(candidate, k, "") if not isinstance(candidate, dict) else candidate.get(k, "")
    return " ".join(str(g(k)) for k in ("name", "negation", "claim", "discipline") if g(k))


def conceptual_novelty(candidate, archive_texts: Optional[List[str]] = None, embedder=None) -> float:
    """Distance of the candidate's TEXT from its nearest neighbor in the archive, in [0,1]. Empty archive ⇒
    1.0 (nothing to be near). This is the classic, WEAK novelty — necessary but never sufficient."""
    from .embeddings import semantic_distance
    text = _cand_text(candidate)
    if not archive_texts:
        return 1.0
    return round(min(semantic_distance(text, t, embedder=embedder) for t in archive_texts), 3)


def behavior_signature(candidate, evaluator):
    """A candidate's BEHAVIOR: whether it passes its evaluator and the rounded signature of its components.
    Two ideas with identical text but different behavior have different signatures — the point of #8."""
    r = evaluator.evaluate(candidate)
    comps = tuple(sorted((k, round(float(v), 1)) for k, v in (r.components or {}).items()))
    return (bool(r.passed), comps)


def _sig_distance(a, b) -> float:
    passed_diff = 0.5 if a[0] != b[0] else 0.0
    ka, kb = dict(a[1]), dict(b[1])
    keys = set(ka) | set(kb)
    comp_diff = (sum(abs(ka.get(k, 0.0) - kb.get(k, 0.0)) for k in keys) / max(1, len(keys))) if keys else 0.0
    return round(min(1.0, passed_diff + 0.5 * comp_diff), 3)


def behavioral_novelty(candidate, evaluator, archive: Optional[List] = None) -> float:
    """Distance of the candidate's BEHAVIOR (evaluator signature) from the nearest prior behavior, in [0,1].
    `archive` is a list of prior signatures (from behavior_signature). Empty ⇒ 1.0. This is the signal text
    cannot give: an idea that BEHAVES unlike everything seen is functionally novel even if worded the same."""
    sig = behavior_signature(candidate, evaluator)
    if not archive:
        return 1.0
    return round(min(_sig_distance(sig, prior) for prior in archive), 3)


def prior_art_novelty(candidate, provider) -> Optional[float]:
    """Distance from the REAL WORLD via a prior-art provider, in [0,1] (1 = far from everything found). None
    when no provider is given — honest: with no online search there is no prior-art novelty to claim."""
    if provider is None:
        return None
    from .novelty import world_novelty_score
    return world_novelty_score(_cand_text(candidate), provider)


def frontier_score(candidate, evaluator=None, provider=None, conceptual_archive: Optional[List[str]] = None,
                   behavioral_archive: Optional[List] = None) -> Dict:
    """Combine whatever novelty signals are available into a frontier score, keeping the axes SEPARATE so a
    text-only 'novelty' can never masquerade as functional or real-world novelty."""
    conceptual = conceptual_novelty(candidate, conceptual_archive)
    behavioral = behavioral_novelty(candidate, evaluator, behavioral_archive) if evaluator is not None else None
    prior_art = prior_art_novelty(candidate, provider)
    parts = [v for v in (conceptual, behavioral, prior_art) if v is not None]
    # HONESTY FIX (#6): the frontier is the WEAKEST available axis (a gate), NOT their mean. A mean lets a high
    # text-distance mask a real-world prior-art COLLISION (prior_art≈0) — exactly the masquerade the module says
    # it prevents. Under a min, a collision on any measured axis caps the frontier; every axis stays visible.
    combined = round(min(parts), 4) if parts else 0.0
    return {"frontier": combined, "conceptual": conceptual, "behavioral": behavioral, "prior_art": prior_art,
            "axes_measured": [n for n, v in (("conceptual", conceptual), ("behavioral", behavioral),
                                             ("prior_art", prior_art)) if v is not None]}


def sparse_unknown_regions(memory, k: int = 5, problem: Optional[str] = None):
    """The sparsest, least-explored regions of the behavior space so far — where to push next (wraps the
    unknown-space frontier over the run's memory)."""
    from .unknown_space import novelty_frontier
    return novelty_frontier(memory, k=k, problem=problem)


def frontier_ablation() -> Dict:
    """Ablation for #8: two candidates with IDENTICAL text but DIFFERENT behavior. conceptual_novelty cannot
    tell them apart; behavioral_novelty can. Proves the behavioral axis adds signal beyond text."""
    from .evaluators.base import CallableEvaluator

    class _C:
        def __init__(self, passes):
            self.name, self.negation, self.discipline = "same_text", "identical idea text", "t"
            self._passes = passes

    ev = CallableEvaluator(lambda c: {"score": 1.0 if c._passes else 0.0, "ok": c._passes}, passed_key="ok")
    a, b = _C(True), _C(False)
    archive = [behavior_signature(a, ev)]
    c_a = conceptual_novelty(a, [_cand_text(b)])
    c_b = conceptual_novelty(b, [_cand_text(a)])
    behav_a = behavioral_novelty(a, ev, archive)               # in archive → ~0
    behav_b = behavioral_novelty(b, ev, archive)               # different behavior → > 0
    return {"conceptual_identical": abs(c_a - c_b) < 1e-9 and c_a < 0.2,
            "behavioral_separates": behav_b > behav_a,
            "behavioral_a": behav_a, "behavioral_b": behav_b, "conceptual_a": c_a,
            "earns_keep": (abs(c_a - c_b) < 1e-9) and behav_b > behav_a}
