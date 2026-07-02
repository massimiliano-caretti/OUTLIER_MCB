"""evals.scorers — deterministic metrics in [0,1] over a standardized baseline output.

Every scorer reads the standardized dict produced by baselines.py (+ the task, where the oracle needs
it) and returns a number in [0,1]. No randomness, no network, no LLM. The composite verified_novelty_score
uses the fixed weights specified for the harness.
"""
from __future__ import annotations
from typing import Dict


def _clamp(x: float) -> float:
    return round(max(0.0, min(1.0, x)), 3)


def broken_assumption_rate(out: Dict, task: Dict = None) -> float:
    return 1.0 if str(out.get("broken_assumption", "")).strip() else 0.0


def falsifiability_score(out: Dict, task: Dict = None) -> float:
    """Presence of the four things that make a claim falsifiable: a world-test, a baseline, a pass
    condition, and a failure (negative) control."""
    ac = out.get("artifact_contract", {}) or {}
    present = [
        bool(str(out.get("world_test", "")).strip()),
        bool(str(ac.get("baseline_assertion", "")).strip()),
        bool(str(ac.get("success_condition", "")).strip()),
        bool(str(out.get("negative_control", "")).strip() or str(ac.get("negative_control", "")).strip()),
    ]
    return _clamp(sum(present) / len(present))


def artifact_specificity(out: Dict, task: Dict = None) -> float:
    ac = out.get("artifact_contract", {}) or {}
    fields = ["target", "test_name", "baseline_assertion", "negative_control", "success_condition"]
    return _clamp(sum(1 for f in fields if str(ac.get(f, "")).strip()) / len(fields))


def routing_accuracy(out: Dict, task: Dict) -> float:
    pack, expected = out.get("pack", ""), task.get("expected_pack", "")
    if not pack:
        return 0.0
    if pack == expected:
        return 1.0
    if pack == "generic" and task.get("allowed_generic"):
        return 0.5                                   # an acceptable fallback the task explicitly allows
    return 0.0


def unique_frontier_ratio(out: Dict, task: Dict = None) -> float:
    return _clamp(float(out.get("score_components", {}).get("unique_frontier_ratio", 1.0)))


def rebranding_risk(out: Dict, task: Dict) -> float:
    """High when the output names a known-bad family without declaring a verifiable difference
    (a broken assumption + a world-test)."""
    text = (str(out.get("text", "")) + " " + str(out.get("broken_assumption", ""))).lower()
    names_bad = any(f.lower() in text for f in (task or {}).get("known_bad_families", []))
    differentiates = bool(str(out.get("broken_assumption", "")).strip()) and bool(str(out.get("world_test", "")).strip())
    if names_bad and not differentiates:
        return 1.0
    return 0.2 if names_bad else 0.0


def auto_verifiability(out: Dict, task: Dict = None) -> float:
    ac = out.get("artifact_contract", {}) or {}
    if ac.get("grounded") and ac.get("full_contract"):
        return 1.0
    if str(ac.get("test_name", "")).strip():
        return 0.5
    return 0.0


def usefulness_proxy(out: Dict, task: Dict = None) -> float:
    """Appropriateness, not just novelty (the creativity-literature point): an idea is useful when it is
    actionable — it names what it breaks, has a world-test, and attaches to a runnable artifact."""
    ac = out.get("artifact_contract", {}) or {}
    signals = [bool(str(out.get("broken_assumption", "")).strip()),
               bool(str(out.get("world_test", "")).strip()),
               bool(ac.get("grounded") and ac.get("full_contract"))]
    return _clamp(sum(signals) / len(signals))


# spec name alias
broken_assumption_score = broken_assumption_rate


def verified_novelty_score(out: Dict, task: Dict) -> float:
    vns = (0.18 * broken_assumption_score(out, task)
           + 0.18 * falsifiability_score(out, task)
           + 0.18 * artifact_specificity(out, task)
           + 0.14 * routing_accuracy(out, task)
           + 0.14 * auto_verifiability(out, task)
           + 0.10 * unique_frontier_ratio(out, task)
           + 0.08 * usefulness_proxy(out, task)
           - 0.20 * rebranding_risk(out, task))
    return _clamp(vns)


# ── anti-fake-rigor metrics (this round): a single VNS can be gamed; these detect it ──
_GENERIC_BA = ("unspecified", "a hidden assumption", "the box", "some ", "default", "generic")
_PLACEHOLDERS = ("todo", "...", "placeholder", "tbd", "fixme", "<", "xxx")
_ABSOLUTE = ("verified", "certified", "proven", "guaranteed")
_FILLER_VALUES = {"test", "thing", "generic", "stuff", "code", "x"}


def anti_gaming_score(out: Dict, task: Dict = None) -> float:
    """1.0 = low gaming risk, 0.0 = high. Penalizes output that looks optimized for the metric rather
    than for value: generic assumptions, world-tests with no real negative control, placeholder/filler
    artifact fields, absolute claims unbacked by AUTO, candidate inflation, and sheer verbosity."""
    text = str(out.get("text", ""))
    ba = str(out.get("broken_assumption", "")).lower()
    ac = out.get("artifact_contract", {}) or {}
    blob = " ".join(str(v) for v in ac.values()).lower()
    neg = str(out.get("negative_control", "")).strip() or str(ac.get("negative_control", "")).strip()
    pen = 0.0
    if ba and any(g in ba for g in _GENERIC_BA):
        pen += 0.20
    if str(out.get("world_test", "")).strip() and not neg:
        pen += 0.20
    if any(p in blob for p in _PLACEHOLDERS):
        pen += 0.20
    if any(str(v).strip().lower() in _FILLER_VALUES for v in ac.values()):
        pen += 0.15
    if any(w in (text + " " + blob).lower() for w in _ABSOLUTE) and out.get("verifiability") != "AUTO":
        pen += 0.25
    cc, uc = out.get("candidate_count", 1), out.get("unique_candidate_count", 1)
    if cc > 3 and uc < 0.6 * cc:
        pen += 0.15
    if len(text) > 1500:
        pen += 0.10
    return _clamp(1.0 - pen)


def calibration_honesty_score(out: Dict, task: Dict = None) -> float:
    """Does the output declare correctly what is verified vs not? Penalizes a FALSE AUTO (claims runnable
    without a full contract) and absolute claims ('verified/proven') on a non-AUTO output."""
    s = 1.0
    v = out.get("verifiability", "NONE")
    ac = out.get("artifact_contract", {}) or {}
    full = bool(ac.get("full_contract") and ac.get("grounded"))
    text = (str(out.get("text", "")) + " " + str(out.get("world_test", ""))).lower()
    if v == "AUTO" and not full:
        s -= 0.5
    if any(w in text for w in _ABSOLUTE) and v != "AUTO":
        s -= 0.4
    return _clamp(s)


def robust_verified_novelty_score(out: Dict, task: Dict) -> float:
    """VNS gated by honesty: a gamed or mis-calibrated output is multiplied DOWN, never up. (The aggregate
    ablation-contribution term is added at the run level, not here.)"""
    return _clamp(verified_novelty_score(out, task)
                  * anti_gaming_score(out, task) * calibration_honesty_score(out, task))


def materialization_score(out: Dict, task: Dict = None) -> float:
    """STRONGER than artifact_specificity: not 'are the fields filled?' but 'is this contract a real,
    selectable, currently-RED test against the repo?'. Computed against the real filesystem at baseline
    time (OUTLIER_MCB.materialize) and surfaced here. Independent of artifact_specificity by construction:
    a field-complete contract still scores low if its command runs the whole suite, its target is absent,
    or the named test already exists (nothing red to flip)."""
    return _clamp(float(out.get("score_components", {}).get("materialization_score", 0.0)))


# ── judgment accuracy: judge()'s real objective is DISCRIMINATION, which VNS (a generative metric) cannot
#    see. A human-idea task carries a ground-truth verdict; a mode that produces no verdict scores 0 here. ──
_SOFT_PAIR = {"MUST_BE_AUDITED", "NEEDS_DISAMBIGUATION"}    # both say "not in the box — needs care"


def judgment_accuracy_score(out: Dict, task: Dict) -> float:
    """1.0 when the mode classifies a human idea exactly as the ground truth; partial for a related call;
    0.0 when it produces no verdict at all (e.g. preflight, which only generates). Penalizes a mis-declared
    verifiability (HUMAN claimed AUTO) and a missed prior-art (rename) flag. Vacuously 1.0 on non-judgment
    tasks so it never distorts the generative ranking — only the task-type-aware primary score uses it
    where it applies."""
    expected = (task or {}).get("expected_verdict")
    if not expected:
        return 1.0                                    # not a judgment task → nothing to assess
    sc = out.get("score_components", {}) or {}
    got = sc.get("verdict")
    if not got:
        return 0.0                                    # this mode produced NO verdict — it cannot judge
    score = 1.0 if got == expected else (0.5 if {got, expected} <= _SOFT_PAIR else 0.0)
    exp_v = task.get("expected_verifiability")
    if exp_v and out.get("verifiability") and out.get("verifiability") != exp_v:
        score *= 0.7                                  # mis-declared what is actually verifiable
    exp_nov = task.get("expected_novelty_flag")
    if exp_nov and sc.get("novelty") != exp_nov:
        score *= 0.5                                  # failed to catch the known prior art (a rename)
    return _clamp(score)


def primary_score(out: Dict, task: Dict) -> float:
    """The task-type-aware objective (the OBJECTIVE assumption the engine told us to break): score a
    GENERATIVE task by verified novelty, a JUDGMENT task by judgment accuracy. This is what judge() must
    be measured on — not generative novelty, which structurally cannot credit a correct assessment."""
    if (task or {}).get("expected_verdict"):
        return judgment_accuracy_score(out, task)
    return verified_novelty_score(out, task)


SCORERS = {
    "broken_assumption_score": broken_assumption_score,
    "falsifiability_score": falsifiability_score,
    "artifact_specificity": artifact_specificity,
    "routing_accuracy": routing_accuracy,
    "unique_frontier_ratio": unique_frontier_ratio,
    "rebranding_risk": rebranding_risk,
    "auto_verifiability": auto_verifiability,
    "usefulness_proxy": usefulness_proxy,
    "verified_novelty_score": verified_novelty_score,
    "anti_gaming_score": anti_gaming_score,
    "calibration_honesty_score": calibration_honesty_score,
    "robust_verified_novelty_score": robust_verified_novelty_score,
    "materialization_score": materialization_score,
    "judgment_accuracy_score": judgment_accuracy_score,
}


def score_output(out: Dict, task: Dict) -> Dict[str, float]:
    return {name: fn(out, task) for name, fn in SCORERS.items()}


# ── open-ended creativity metrics (Impl 6) ──────────────────────────────────────────────────────────────
# These operate on open-ended SEARCH ARTIFACTS (a QD archive, a candidate pool, a creative_search result),
# NOT on the per-task `out` dict, so they are kept OUT of the SCORERS map above. Every one is normalized to
# [0,1] with its components exposed (no hidden composite). Computational-creativity literature: a creation
# must be NOVEL and VALUABLE and (here) VERIFIABLE — "different" alone is rejected (Boden; Ritchie).
def _toks(text: str):
    return {w for w in "".join(c if c.isalnum() else " " for c in str(text).lower()).split() if len(w) > 3}


def qd_coverage_score(archive, reference_cells: int = 24) -> float:
    """Fraction of behavioral cells the QD archive fills, vs a reference capacity. Higher ⇒ the search
    illuminated more distinct KINDS of solution (Quality-Diversity coverage)."""
    filled = archive.coverage() if hasattr(archive, "coverage") else int(archive)
    return _clamp(filled / max(1, reference_cells))


def semantic_novelty_score(text: str, prior_texts, embedder=None) -> float:
    """1 − the MAX similarity with any prior text → high only if far from everything already produced.
    Penalizes paraphrase: a reworded duplicate scores ~0, a genuinely different one ~1. Lexical by default;
    pass an embeddings.CallableEmbedder for SEMANTIC distance (different words / same meaning → still near)."""
    if not str(text).strip() or not prior_texts:
        return 1.0
    if embedder is not None:
        return _clamp(min(embedder.distance(text, p) for p in prior_texts))
    t = _toks(text)
    sims = [len(t & _toks(p)) / len(t | _toks(p)) if (t or _toks(p)) else 0.0 for p in prior_texts]
    return _clamp(1.0 - max(sims))


def lineage_diversity_score(result) -> float:
    """Fraction of DISTINCT operator-lineages in a creative_search result — low ⇒ a monoculture (everything
    a child of one pattern), high ⇒ structurally diverse lineages. Delegates to the result's own measure."""
    return _clamp(result.lineage_diversity() if hasattr(result, "lineage_diversity") else float(result))


def surprise_usefulness_score(surprise: float, usefulness: float) -> float:
    """High ONLY when an idea is BOTH surprising AND useful (geometric mean) — surprise alone is noise,
    usefulness alone is unremarkable. The computational-creativity guard against 'weird but worthless'."""
    return _clamp((max(0.0, surprise) * max(0.0, usefulness)) ** 0.5)


def transformational_break_score(out: Dict, task: Dict = None) -> float:
    """1.0 when the output breaks a RULE/assumption (changes the space), not just the style: a stated broken
    assumption + a world-test, with no rebranding. Boden's transformational (vs merely exploratory) creativity."""
    broke = bool(str(out.get("broken_assumption", "")).strip()) and bool(str(out.get("world_test", "")).strip())
    return _clamp((1.0 if broke else 0.0) * (1.0 - rebranding_risk(out, task or {})))


def creativity_composite_score(novelty: float, usefulness: float, surprise: float,
                               verification: float, anti_gaming: float) -> Dict[str, float]:
    """A TRANSPARENT creativity composite (components returned, never hidden). novelty+usefulness+surprise are
    the creativity core; verification gates them (an unverifiable 'creative' idea is discounted); anti_gaming
    multiplies the whole thing DOWN if the output looks optimized for the metric. Returns the score AND parts."""
    core = 0.40 * _clamp(usefulness) + 0.30 * _clamp(novelty) + 0.30 * _clamp(surprise)
    gated = core * (0.5 + 0.5 * _clamp(verification))      # verification gate: halve an unverifiable idea
    composite = _clamp(gated * _clamp(anti_gaming))        # honesty multiplier (never raises the score)
    return {"composite": composite, "novelty": _clamp(novelty), "usefulness": _clamp(usefulness),
            "surprise": _clamp(surprise), "verification": _clamp(verification), "anti_gaming": _clamp(anti_gaming)}


def _mean_pairwise_novelty(texts, embedder=None) -> float:
    """Mean pairwise distance within a pool — a divergence measure: a pool of paraphrases scores low, a pool
    of genuinely different ideas scores high. Lexical (token Jaccard) by default; pass an embedder for
    semantic distance."""
    items = [t for t in texts if str(t).strip()]
    if embedder is not None:
        pairs = [embedder.distance(a, b) for i, a in enumerate(items) for b in items[i + 1:]]
        return round(sum(pairs) / len(pairs), 3) if pairs else 0.0
    toks = [_toks(t) for t in items]
    pairs = [(1.0 - len(a & b) / len(a | b)) for i, a in enumerate(toks) for b in toks[i + 1:] if (a or b)]
    return round(sum(pairs) / len(pairs), 3) if pairs else 0.0


def openended_pool_metrics(candidates, pack, repo=None) -> Dict[str, float]:
    """Compute the open-ended metrics for a POOL of generated candidates (used by the GSL_OPENENDED mode and
    by GSL_FULL's frontier, so they are compared on identical math). All in [0,1]. Returns a dict to drop
    into score_components; the per-task reader scorers below surface each field."""
    import OUTLIER_MCB as gsl
    cands = list(candidates or [])
    if not cands:
        return {"qd_coverage": 0.0, "semantic_novelty": 0.0, "lineage_diversity": 0.0, "creativity_composite": 0.0}
    arc = gsl.QDArchive(pack=pack, repo=repo)
    for c in cands:
        arc.add(c)
    qd_cov = qd_coverage_score(arc, reference_cells=24)
    sem = _mean_pairwise_novelty([getattr(c, "negation", "") for c in cands])
    ops = {getattr(c, "operator", "") for c in cands}
    lineage = round(len(ops) / len(cands), 3)
    breaks = sum(1 for c in cands if getattr(c, "breaks", []))
    usefulness = round(breaks / len(cands), 3)
    verification = round(sum(1 for c in cands if getattr(c, "needs", []) or getattr(c, "breaks", [])) / len(cands), 3)
    creativity = creativity_composite_score(novelty=sem, usefulness=usefulness, surprise=lineage,
                                            verification=verification, anti_gaming=1.0)["composite"]
    return {"qd_coverage": qd_cov, "semantic_novelty": sem, "lineage_diversity": lineage,
            "creativity_composite": creativity}


# per-task reader scorers (surface the precomputed pool metrics, like materialization_score does)
def qd_coverage_metric(out: Dict, task: Dict = None) -> float:
    return _clamp(float(out.get("score_components", {}).get("qd_coverage", 0.0)))


def semantic_novelty_metric(out: Dict, task: Dict = None) -> float:
    return _clamp(float(out.get("score_components", {}).get("semantic_novelty", 0.0)))


def lineage_diversity_metric(out: Dict, task: Dict = None) -> float:
    return _clamp(float(out.get("score_components", {}).get("lineage_diversity", 0.0)))


def creativity_composite_metric(out: Dict, task: Dict = None) -> float:
    return _clamp(float(out.get("score_components", {}).get("creativity_composite", 0.0)))


def prior_art_caught_metric(out: Dict, task: Dict = None) -> float:
    """1.0 when a task that PLANTS prior art (a rename/collage) is correctly flagged by the prior-art audit;
    0.0 when the planted prior art is missed. On tasks with no planted prior art it is vacuously 1.0 so it
    never distorts them — only the GSL_NO_PRIOR_ART ablation, which skips the audit, drops here."""
    if not (task or {}).get("expected_novelty_flag"):
        return 1.0
    return 1.0 if out.get("score_components", {}).get("prior_art_verdict") == task["expected_novelty_flag"] else 0.0


def llm_call_count_score(out: Dict, task: Dict = None) -> float:
    """Normalized LLM-call count: the LLM-loop calls a model many times; heuristic modes call it zero times."""
    return _clamp(float(out.get("score_components", {}).get("llm_call_count", 0)) / 8.0)


def red_green_score(out: Dict, task: Dict = None) -> float:
    """Fraction of materialized tests that went RED-first then GREEN — real executable settlement (0 for any
    mode that materializes nothing)."""
    return _clamp(float(out.get("score_components", {}).get("red_green", 0.0)))


def anti_rebrand_score(out: Dict, task: Dict = None) -> float:
    """How well a mode's prior-art gate blocks rebrands. 0 for modes that never run a prior-art audit at all
    (they cannot claim to gate rebranding); the LLM loop runs it as a mandatory step."""
    return _clamp(float(out.get("score_components", {}).get("anti_rebrand", 0.0)))


def _component(out: Dict, key: str) -> float:
    return _clamp(float(out.get("score_components", {}).get(key, 0.0)))


def red_assertion_green_score(out: Dict, task: Dict = None) -> float:
    """Fraction of materialized tests that failed on a REAL ASSERTION (not an import/syntax/collection error)
    and then went GREEN — the only chain the loop fully rewards (§3). 0 for modes that materialize nothing."""
    return _component(out, "red_assertion_green")


def test_quality_metric(out: Dict, task: Dict = None) -> float:
    """How specific the winning test is — non-tautological, imports the target, checks a concrete value (§4).
    0 for modes that never write a test."""
    return _component(out, "test_quality")


def patch_substance_metric(out: Dict, task: Dict = None) -> float:
    """Whether the winning patch changes real source rather than cheating the test (skip/xfail/weaken) (§9).
    0 for modes that never write a patch."""
    return _component(out, "patch_substance")


def duplicate_rejection_score(out: Dict, task: Dict = None) -> float:
    """Whether the diversity gate actually rejected near-duplicate candidates (§7). 0 for modes with no gate."""
    return _component(out, "duplicate_rejection")


def repair_success_score(out: Dict, task: Dict = None) -> float:
    """Whether a bounded repair turned a broken JSON/test/impl into a passing one (§5). 0 without a repair loop."""
    return _component(out, "repair_success")


SCORERS.update({
    "qd_coverage_score": qd_coverage_metric,
    "semantic_novelty_score": semantic_novelty_metric,
    "lineage_diversity_score": lineage_diversity_metric,
    "creativity_composite_score": creativity_composite_metric,
    "prior_art_caught_score": prior_art_caught_metric,
    "llm_call_count_score": llm_call_count_score,
    "red_green_score": red_green_score,
    "anti_rebrand_score": anti_rebrand_score,
    "red_assertion_green_score": red_assertion_green_score,
    "test_quality_score": test_quality_metric,
    "patch_substance_score": patch_substance_metric,
    "duplicate_rejection_score": duplicate_rejection_score,
    "repair_success_score": repair_success_score,
})
