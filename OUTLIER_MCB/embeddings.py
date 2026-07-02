"""embeddings — a PLUGGABLE semantic-distance adapter for the creativity metrics.

The honest constraint: the core stays zero-dependency and deterministic, so the DEFAULT distance is lexical
(token-set Jaccard) — exactly the proxy the metrics used before, with all its limits (it sees shared words,
not shared meaning). But "different words, same idea" and "same words, different idea" both fool a lexical
metric, so this module lets a caller inject a REAL embedding model (sentence-transformers, an API, a local
model) without the library taking on the dependency or losing determinism by default.

    from OUTLIER_MCB.embeddings import CallableEmbedder
    emb = CallableEmbedder(lambda text: my_model.encode(text))     # your real embedder
    gsl.diverge("…", embedder=emb)                                  # this call is SEMANTIC, cosine-based

Lifting the ceiling everywhere, not call-by-call: the default is now PROCESS-WIDE RESOLVABLE. A single
`gsl.set_default_embedder(emb)` (or `OUTLIER_MCB_EMBEDDER=sentence-transformers:<model>` in the env)
upgrades EVERY `embedder=None` distance — novelty, judge, memory, frontier, blending — to real semantics,
because `semantic_distance(...)` and `default_embedder()` resolve that default. With nothing registered and
the var unset it stays lexical: deterministic, zero-dependency, the library never imports a model on its own.

The same provider pattern as research/novelty: the library defines the interface and the lexical fallback;
the network/model lives with the caller. Both embedders expose `.distance(a, b) -> float` in [0,1].
"""
from __future__ import annotations
import os
from math import sqrt
from typing import Callable, List, Optional


def _tokens(text: str):
    return {w for w in "".join(c if c.isalnum() else " " for c in str(text).lower()).split() if len(w) > 3}


class LexicalEmbedder:
    """The default, deterministic, zero-dependency distance: 1 − token-set Jaccard. Sees shared WORDS, not
    shared meaning — a paraphrase with different words reads as 'far'. Good enough as a baseline; swap in a
    CallableEmbedder for real semantics."""
    kind = "lexical"

    def distance(self, a: str, b: str) -> float:
        ta, tb = _tokens(a), _tokens(b)
        if not ta and not tb:
            return 0.0
        return round(1.0 - len(ta & tb) / len(ta | tb), 4)


def _cosine(u: List[float], v: List[float]) -> float:
    if not u or not v or len(u) != len(v):
        return 0.0
    dot = sum(x * y for x, y in zip(u, v))
    nu, nv = sqrt(sum(x * x for x in u)), sqrt(sum(y * y for y in v))
    return dot / (nu * nv) if (nu and nv) else 0.0


class CallableEmbedder:
    """Wrap a real embedding function `fn(text) -> list[float]` (sentence-transformers, an API, …). Distance
    is 1 − cosine similarity, clamped to [0,1] — so 'different words, same meaning' is correctly NEAR. The
    library never imports the model; the caller owns it (determinism/offline are the caller's choice here)."""
    kind = "semantic"

    def __init__(self, fn: Callable[[str], List[float]], cache: bool = True):
        self.fn = fn
        self._cache = {} if cache else None

    def _embed(self, text: str) -> List[float]:
        if self._cache is None:
            return list(self.fn(text))
        if text not in self._cache:
            self._cache[text] = list(self.fn(text))
        return self._cache[text]

    def distance(self, a: str, b: str) -> float:
        return round(max(0.0, min(1.0, 1.0 - _cosine(self._embed(a), self._embed(b)))), 4)


def _stem(w: str) -> str:
    """A tiny, deterministic suffix stripper — enough to align morphology (pool/pooling, invariant/invariance)
    without a stemming library. Not linguistically perfect; just better than exact-word matching."""
    for suf in ("ational", "ization", "iveness", "ing", "tion", "ment", "ness", "ely", "ed", "es", "s", "ly"):
        if len(w) > len(suf) + 2 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def _char_ngrams(text: str, n: int = 3) -> set:
    s = "".join(c if c.isalnum() else " " for c in str(text).lower())
    s = " ".join(s.split())
    return {s[i:i + n] for i in range(len(s) - n + 1)} if len(s) >= n else {s}


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b) if (a | b) else 1.0


class NgramEmbedder:
    """A stronger, still deterministic and zero-dependency offline distance than plain token-Jaccard: it blends
    (a) token-set overlap, (b) character 3-gram overlap (so hyphenation, morphology, and partial words align),
    and (c) light-stemmed token overlap (pool≈pooling, invariant≈invariance). It still sees FORM, not learned
    meaning — for true semantics wire a CallableEmbedder — but it closes much of the paraphrase gap the pure
    lexical default leaves open, with no model and no network. Identical strings → distance 0."""
    kind = "ngram"

    def __init__(self, w_token: float = 0.4, w_char: float = 0.35, w_stem: float = 0.25):
        total = w_token + w_char + w_stem
        self.w_token, self.w_char, self.w_stem = w_token / total, w_char / total, w_stem / total

    def distance(self, a: str, b: str) -> float:
        ta, tb = _tokens(a), _tokens(b)
        sa, sb = {_stem(w) for w in ta}, {_stem(w) for w in tb}
        ca, cb = _char_ngrams(a), _char_ngrams(b)
        sim = self.w_token * _jaccard(ta, tb) + self.w_char * _jaccard(ca, cb) + self.w_stem * _jaccard(sa, sb)
        return round(max(0.0, min(1.0, 1.0 - sim)), 4)


# ── the process-wide resolvable default (fix: the integration point existed but nothing used it) ──
# The lexical default is novelty-by-naming in disguise: it credits a reworded known idea as 'far' (novel)
# and cannot tell two genuinely different ideas that share words apart. Rather than force every call site to
# thread an embedder, the default is now resolvable ONCE per process — so a single `set_default_embedder(...)`
# (or the OUTLIER_MCB_EMBEDDER env var) upgrades EVERY `embedder=None` distance (novelty, judge, memory,
# frontier, blending) to real semantics. Unset/offline ⇒ lexical ⇒ identical, deterministic behaviour: the
# library still never imports a model on its own.
_DEFAULT_EMBEDDER: Optional[object] = None   # None ⇒ resolve lazily (env, else lexical)


def set_default_embedder(embedder) -> None:
    """Register the process-wide default embedder. Pass a CallableEmbedder (real model) to give the whole
    engine semantic eyes; pass None to reset to the lexical/env-resolved default. Programmatic registration
    always wins over the env var. This is the ONE switch that lifts the lexical ceiling everywhere."""
    global _DEFAULT_EMBEDDER
    _DEFAULT_EMBEDDER = embedder


def reset_default_embedder() -> None:
    """Forget any registered default (back to env-resolved, else lexical). Mainly for tests/isolation."""
    set_default_embedder(None)


_ENV_VAR = "OUTLIER_MCB_EMBEDDER"
_ENV_CACHE: dict = {}   # spec → resolved embedder (or None ⇒ lexical); built once, never reloaded per distance


def _build_from_spec(spec: str) -> Optional[object]:
    """Construct the embedder a spec asks for, or None to mean 'fall back to lexical'. Recognised:
      'lexical' (or empty)                  → None (lexical fallback, deterministic, zero-dep)
      'sentence-transformers:<model-name>'  → wrap a local sentence-transformers model (must be installed)
    A missing/broken model falls back to lexical instead of crashing — the model is the caller's dependency,
    never the library's, and never imported eagerly at module load."""
    key = spec.lower()
    if not spec or key == "lexical":
        return None
    if key.startswith("sentence-transformers:"):
        model_name = spec.split(":", 1)[1].strip() or "all-MiniLM-L6-v2"
        try:
            from sentence_transformers import SentenceTransformer   # type: ignore
            model = SentenceTransformer(model_name)
            return CallableEmbedder(lambda text: list(model.encode(str(text))))
        except Exception:
            return None                                        # honest fallback: a missing model ⇒ lexical, not a crash
    return None                                                # unknown scheme ⇒ lexical, never a silent wrong model


def _from_env() -> Optional[object]:
    """Resolve the OUTLIER_MCB_EMBEDDER env var, opt-in only and CACHED by spec — `default_embedder()` runs
    per distance, so a model is built once per spec, not reloaded on every call. Var unset ⇒ lexical (so
    determinism by default is preserved)."""
    spec = os.environ.get(_ENV_VAR, "").strip()
    if not spec or spec.lower() == "lexical":
        return None
    if spec not in _ENV_CACHE:
        _ENV_CACHE[spec] = _build_from_spec(spec)
    return _ENV_CACHE[spec]


def default_embedder():
    """The resolved default embedder: a programmatic registration if set, else the env-configured model, else
    the zero-dependency lexical fallback. Override per call by passing an explicit embedder."""
    if _DEFAULT_EMBEDDER is not None:
        return _DEFAULT_EMBEDDER
    env = _from_env()
    return env if env is not None else LexicalEmbedder()


def semantic_distance(a: str, b: str, embedder=None) -> float:
    """Distance in [0,1] between two texts. `embedder` overrides for this call; otherwise the process-wide
    default is resolved (semantic if one is registered/configured, lexical offline) — so lifting the ceiling
    is a single switch, not a rewrite of every call site."""
    return (embedder if embedder is not None else default_embedder()).distance(a, b)
