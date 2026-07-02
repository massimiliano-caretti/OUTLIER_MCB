"""closure_recognition — a more robust, still deterministic and zero-dependency recogniser of universal-closure
membership, generalising beyond the exact-keyword detectors in closures.py.

Motivation. The structural detectors in closures.py are high-precision but key on specific words, so a diverse
paraphrase ("combine the pointwise embeddings") is missed. This module lifts recall WITHOUT a learned model by
combining three deterministic signals over three CONCEPTS — aggregation, per-instance encoding, set-conditioned
encoding — each backed by a curated stem lexicon (so morphology generalises: combine/combining/combined), and a
prototype fallback: when the lexicon is undecided, classify by nearest ANCHOR phrase using the library's own
NgramEmbedder (character n-gram + stemmed distance). It is opt-in and backward-compatible: closures.py is
unchanged; callers who want the broader recogniser use robust_closure_verdict / RobustCloseureRecognizer.

Honesty: this is still a lexical/character recogniser, not a semantic model. It raises recall over diverse
phrasings but cannot cover an open vocabulary; with a real embedder wired via set_default_embedder the anchor
fallback becomes semantic. We evaluate it held-out (unseen synonyms) rather than assuming it generalises.
"""
from __future__ import annotations
import re
from typing import Optional

from .embeddings import _stem, NgramEmbedder

INSIDE, OUTSIDE, UNKNOWN = "INSIDE", "OUTSIDE", "UNKNOWN"

# ── concept stem lexicons (curated once, morphology handled by stemming; NOT tuned to any benchmark) ──
_AGG_STEMS = {  # permutation-invariant aggregation
    "sum", "add", "total", "accumul", "aggreg", "combin", "merg", "fus", "averag", "mean", "pool",
    "reduc", "gather", "collect", "softmax", "logsumexp", "max", "min", "prod", "moment", "gem",
    "powermean", "quantil", "cvar", "mix",
}
_PERINST_STEMS = {  # encoder depends only on the single element
    "perinstance", "peritem", "perelement", "perpoint", "pointwis", "elementwis", "independ",
    "isolat", "individual", "separat", "eachelement", "eachitem", "phixi",
}
_SETCOND_MARK = (  # multi-word markers that the encoder is conditioned on the WHOLE set (substring, robust)
    "attention", "attend", "interact", "pairwise", "self-attention", "whole set", "entire set",
    "across all elements", "across the set", "other instances", "one another", "each other",
    "set-level", "set context", "set-context", "cross-element", "cross element", "globally", "global context",
    "exchange information", "communicate", "conditioned on the set", "conditioned on the whole",
    "phi(x_i, s)", "induced set", "context of all", "context from all", "sees the entire", "sees the whole",
)


def _norm_tokens(text: str):
    return {_stem(w) for w in re.split(r"[^a-z0-9]+", (text or "").lower()) if len(w) > 1}


def _has_agg(text: str) -> bool:
    toks = _norm_tokens(text)
    return any(any(t.startswith(s) or s.startswith(t) for s in _AGG_STEMS) for t in toks) \
        or any(k in text.lower() for k in ("pool", "sum", "mean", "average", "aggregate"))


def _has_perinstance(text: str) -> bool:
    low = text.lower().replace("-", "").replace(" ", "")
    return any(m in low for m in _PERINST_STEMS) or "per-instance" in text.lower() or "per instance" in text.lower()


def _has_setcond(text: str) -> bool:
    low = text.lower()
    return any(m in low for m in _SETCOND_MARK)


class RobustClosureRecognizer:
    """Broader DeepSets membership recogniser. INSIDE = an aggregation of per-instance encodings (encoder NOT
    conditioned on the set). OUTSIDE = the encoder is set-conditioned. Falls back to nearest-anchor when the
    lexicon is undecided, using a pluggable distance (NgramEmbedder by default)."""

    _ANCHORS_INSIDE = [
        "sum of per-instance features", "average of pointwise embeddings", "max-pool of per-item encodings",
        "log-sum-exp of independently encoded elements", "power-mean of the per-instance representations",
        "combine the individually encoded items", "aggregate features computed for each element alone",
    ]
    _ANCHORS_OUTSIDE = [
        "self-attention across all elements then pool", "encoder conditioned on the whole set",
        "elements attend to one another before aggregation", "pairwise interactions between elements then sum",
        "induced set-attention block over the bag", "representations informed by set-level context",
    ]

    def __init__(self, embedder=None):
        self.embedder = embedder or NgramEmbedder()

    # off-topic text sits far from EVERY anchor (measured min-distance ≈0.97+) with a near-zero margin, whereas
    # on-topic text is ≈0.57–0.71 away with a ≥0.2 margin. So abstain (UNKNOWN) when no anchor is actually close
    # OR the two sides are too close to call — otherwise the fallback fabricates a verdict (a false escape) for
    # unrelated input like "banana bread recipe".
    _ANCHOR_FLOOR = 0.90
    _ANCHOR_MARGIN = 0.05

    def _nearest(self, text: str) -> str:
        di = min(self.embedder.distance(text, a) for a in self._ANCHORS_INSIDE)
        do = min(self.embedder.distance(text, a) for a in self._ANCHORS_OUTSIDE)
        if min(di, do) > self._ANCHOR_FLOOR or abs(di - do) < self._ANCHOR_MARGIN:
            return UNKNOWN
        return INSIDE if di < do else OUTSIDE

    def verdict(self, text: str) -> str:
        agg, per, setc = _has_agg(text), _has_perinstance(text), _has_setcond(text)
        # a set-conditioned encoder is OUTSIDE unless explicitly declared per-instance
        if setc and not per:
            return OUTSIDE
        # an aggregation of per-instance (or not-set-conditioned) encodings is INSIDE
        if agg and (per or not setc):
            return INSIDE
        # undecided by the lexicon → prototype fallback (deterministic)
        return self._nearest(text)


def robust_closure_verdict(text: str, closure: str = "DEEPSETS", embedder=None) -> str:
    """Robust DeepSets closure membership (INSIDE / OUTSIDE / UNKNOWN), generalising over diverse phrasings.
    `closure` is accepted for interface parity; the recogniser currently targets the DeepSets/Set-Transformer
    axis (per-instance vs set-conditioned encoder)."""
    return RobustClosureRecognizer(embedder=embedder).verdict(text)


_SEMANTIC_SYSTEM = (
    "You are a precise classifier of neural set-function architectures. The Deep Sets closure is the class of "
    "permutation-invariant functions written as rho(sum_i phi(x_i)) with a PER-INSTANCE encoder phi (phi sees "
    "only one element). A readout is INSIDE Deep Sets if it is any permutation-invariant aggregation "
    "(sum/mean/max/log-sum-exp/power-mean/softmax-weighted, etc.) of per-instance encodings. A readout is "
    "OUTSIDE if the encoder is conditioned on the WHOLE set (e.g. self-attention across elements, pairwise "
    "interactions, elements exchanging information). Answer with exactly one word: INSIDE or OUTSIDE."
)


def semantic_closure_verdict(text: str, llm, closure: str = "DEEPSETS") -> str:
    """Fully semantic DeepSets closure membership via a wired LLM (the library's LLMProvider interface): the
    encoder-vs-set-conditioning judgment is made by the model, so ANY phrasing is handled — the natural
    endpoint of the fast (keyword) -> deterministic (robust) -> semantic (LLM) coverage/cost trade-off. The
    library never bundles a model; the caller supplies `llm` (e.g. a CallableLLMProvider over a local model or
    an API). Returns INSIDE / OUTSIDE / UNKNOWN (UNKNOWN if the model does not answer clearly)."""
    prompt = f"Readout: \"{text}\"\nIs it INSIDE or OUTSIDE the Deep Sets closure? One word."
    try:
        out = llm.complete(prompt, system=_SEMANTIC_SYSTEM, temperature=0.0, n=1)
        resp = (out[0] if isinstance(out, (list, tuple)) else str(out)).upper()
    except Exception:
        return UNKNOWN
    has_in, has_out = "INSIDE" in resp, "OUTSIDE" in resp
    if has_in and not has_out:
        return INSIDE
    if has_out and not has_in:
        return OUTSIDE
    return UNKNOWN


def combined_closure_verdict(text: str, llm, closure: str = "DEEPSETS", embedder=None) -> str:
    """Falsification-CONSERVATIVE combination of the deterministic (robust) and semantic (LLM) tiers.

    The criterion's guiding asymmetry is that the dangerous error is a FALSE ESCAPE (certifying as novel
    something that in fact reduces to the closure); denying a real escape is only conservative. The two tiers
    have *complementary* adversarial failure modes: escape-dressed language can fool the LLM into a false
    OUTSIDE, while the deterministic tier keys on explicit per-instance markers and resists that attack (it
    instead errs conservatively, over-calling INSIDE). We therefore make INSIDE dominant: if EITHER tier sees
    a reduction to the closure, the novelty claim is vetoed. An escape is asserted only when no tier detects a
    reduction. This drives adversarial false-novelty toward zero at the cost of more (safe) conservative
    denials — a deliberate trade, not a free lunch; use the semantic tier alone when clean-set accuracy matters
    more than adversarial safety. Returns INSIDE / OUTSIDE / UNKNOWN."""
    r = robust_closure_verdict(text, closure, embedder)
    s = semantic_closure_verdict(text, llm, closure)
    if r == INSIDE or s == INSIDE:
        return INSIDE      # a reduction seen by any tier vetoes novelty (conservative)
    if r == OUTSIDE or s == OUTSIDE:
        return OUTSIDE     # no tier saw a reduction, at least one asserts the escape
    return UNKNOWN
