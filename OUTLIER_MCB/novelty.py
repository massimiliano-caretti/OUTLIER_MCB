"""novelty — autonomously check, against the REAL WORLD, whether an idea is genuinely new.

The library exists to push a model OUT of the known — to invent where it has no examples, guided by an
*innovation* objective, not by the average of what it already knows. So checking an idea only against a
pack's handful of known families is not enough: it must search the real world (web / GitHub / papers) and
ask "does this already exist, renamed or recombined?".

Honest by construction (the engine demanded all three when applied to this problem):
  • REAL-WORLD scope — prior art comes from a pluggable provider that searches the web, not from a pack;
  • absence is NOT proof — no match ⇒ NO_PRIOR_ART_FOUND, PROVISIONAL, with how much was searched;
  • RENAMED ≠ COLLAGE ≠ new — one close match is a rename; coverage by a union of works is a collage;
    only what no existing work covers is a candidate for genuine novelty — and even then, only *provisionally*.

The verdict points outward: NO_PRIOR_ART_FOUND explicitly says the idea must EXTRAPOLATE BEYOND the searched
world to be genuinely new (see green_star) — it never declares "novel" as proven.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List

_STOP = {"the", "a", "an", "of", "to", "is", "are", "for", "with", "and", "or", "in", "on", "by", "as",
         "new", "novel", "design", "make", "build", "system", "method", "approach", "that", "this", "via"}


def _tokens(text: str) -> set:
    return {w for w in "".join(c if c.isalnum() else " " for c in (text or "").lower()).split()
            if len(w) > 3 and w not in _STOP}


def _jaccard(a: set, b: set) -> float:
    return round(len(a & b) / len(a | b), 3) if (a or b) else 0.0


# the GRADED novelty scale (scientific honesty: never claim absolute novelty — only a defensible degree).
GRADED_VERDICTS = ("RENAMED_PRIOR_ART", "COLLAGE_OF_PRIOR_ART", "WEAKLY_NOVEL",
                   "PROVISIONALLY_NOVEL", "VERIFIED_USEFUL_NOVELTY")


@dataclass
class NoveltyVerdict:
    idea: str
    status: str                 # NO_PRIOR_ART_FOUND | RENAMED | COLLAGE  (legacy 3-way; see graded_verdict)
    confidence: float           # how sure the status is, in [0,1]
    closest_matches: List[Dict] = field(default_factory=list)   # [{title,url,similarity}]
    sources_searched: int = 0
    provisional: bool = True     # NO_PRIOR_ART_FOUND is never proof of novelty
    why: str = ""
    # ── graded audit (Impl 2): degrees of novelty, never "absolute" ──
    graded_verdict: str = ""             # one of GRADED_VERDICTS
    prior_art_distance_score: float = 0.0    # [0,1]: 1 = far from all prior art, 0 = an exact match
    source_overlap_score: float = 0.0        # [0,1]: how much of the idea is covered by the union of sources
    claim_scope: str = ""                # what the claim is bounded to (sources/domain searched)
    falsification_query: str = ""        # the concrete search that would REFUTE the novelty claim
    why_not_absolute: str = ""           # why this is never proof of absolute novelty
    what_would_falsify_this: str = ""    # what evidence would downgrade the verdict
    # ── provenance + honest scope (Step 1): WHAT was actually searched ──
    novelty_scope: str = ""              # LOCAL_ONLY | INCOMPLETE_ONLINE_SEARCH | ONLINE_PRIOR_ART_CHECKED (or "" = unscoped)
    coverage_level: str = ""             # NONE | PARTIAL | MULTI | STRONG — how thorough the online search was
    checked_sources: List[Dict] = field(default_factory=list)   # [{provider, online, count}]
    failed_sources: List[Dict] = field(default_factory=list)    # [{provider, online, error}]
    retrieved_at: str = ""

    def real_world_status(self, min_real_sources: int = 3) -> str:
        """FIX C: the HONEST prior-art status. NO_PRIOR_ART_FOUND is allowed ONLY when a real online search
        actually returned ≥ min_real_sources sources WITH URLs. A lexical/offline-only run can never yield
        NO_PRIOR_ART — it is capped at INCOMPLETE_ONLINE_SEARCH (absence of a lexical match is not evidence)."""
        url_sources = sum(1 for m in self.closest_matches if str(m.get("url", "")).strip())
        if self.novelty_scope != "ONLINE_PRIOR_ART_CHECKED" or url_sources < min_real_sources:
            return "INCOMPLETE_ONLINE_SEARCH"
        return self.scoped_verdict()

    def claims_novelty(self) -> bool:
        """The honest gate (fix B): an audit may CLAIM novelty ONLY when a successful ONLINE prior-art search
        actually ran AND the graded verdict is positive. A local-only / incomplete / unscoped search NEVER
        claims novelty — absence of an online check is not evidence of novelty. Every 'novel' label in the
        engine routes through this, so the default (no online provider) refuses the claim instead of faking it."""
        return (self.novelty_scope == "ONLINE_PRIOR_ART_CHECKED"
                and self.graded_verdict in ("PROVISIONALLY_NOVEL", "VERIFIED_USEFUL_NOVELTY"))

    def scoped_verdict(self) -> str:
        """The verdict QUALIFIED by what was searched — the only place the strong honest name appears: a
        provisional-novel verdict is `PROVISIONALLY_NOVEL_ON_CHECKED_SOURCES` ONLY under a successful online
        search; under a local-only search it is `LOCAL_ONLY_NOVELTY`. Never 'absolute novelty'."""
        if self.graded_verdict == "PROVISIONALLY_NOVEL" and self.novelty_scope == "ONLINE_PRIOR_ART_CHECKED":
            return "PROVISIONALLY_NOVEL_ON_CHECKED_SOURCES"
        if self.graded_verdict in ("WEAKLY_NOVEL", "PROVISIONALLY_NOVEL") and self.novelty_scope == "LOCAL_ONLY":
            return "LOCAL_ONLY_NOVELTY"
        if self.novelty_scope == "INCOMPLETE_ONLINE_SEARCH" and self.graded_verdict in ("WEAKLY_NOVEL", "PROVISIONALLY_NOVEL"):
            return "PRIOR_ART_INCOMPLETE"
        return self.graded_verdict

    def markdown(self) -> str:
        head = self.scoped_verdict() if self.novelty_scope else (self.graded_verdict or self.status)
        lines = [f"### Novelty audit — {head}  (confidence {self.confidence}, provisional={self.provisional})"]
        if self.novelty_scope:
            lines.append(f"- **novelty_scope: {self.novelty_scope}** · coverage: {self.coverage_level or '—'} · checked: "
                         f"{', '.join(c['provider'] for c in self.checked_sources) or 'none'} · failed: "
                         f"{', '.join(f['provider'] for f in self.failed_sources) or 'none'}"
                         + (f" · retrieved_at {self.retrieved_at}" if self.retrieved_at else ""))
        lines += [f"- prior-art distance {self.prior_art_distance_score} · source overlap {self.source_overlap_score} "
                  f"· searched {self.sources_searched} real sources",
                  f"- {self.why}"]
        if (not self.claims_novelty()) and self.graded_verdict in ("WEAKLY_NOVEL", "PROVISIONALLY_NOVEL", "VERIFIED_USEFUL_NOVELTY"):
            lines.append(f"- ⚠ novelty NOT established: no successful ONLINE prior-art search "
                         f"(scope={self.novelty_scope or 'unscoped'}) — this is NOT a novelty claim "
                         "(wire default_online_provider() to check the real world).")
        if self.why_not_absolute:
            lines.append(f"- why not absolute: {self.why_not_absolute}")
        if self.what_would_falsify_this:
            lines.append(f"- what would falsify this: {self.what_would_falsify_this}")
        for m in self.closest_matches[:5]:
            lines.append(f"- closest: {m.get('title', '')} ({m.get('similarity')}) — {m.get('url', '')}")
        return "\n".join(lines)


def novelty_audit(idea: str, provider, pack=None,
                  rename_threshold: float = 0.55, collage_coverage: float = 0.7) -> NoveltyVerdict:
    """Search the real world (via `provider`) for prior art on `idea` and classify it. The provider may
    return rich `matches` (with summaries / its own similarity) or plain `sources`; either works."""
    res = provider.research(idea) or {}
    raw = res.get("matches") or [{"title": s.get("title", ""), "url": s.get("url", ""), "summary": ""}
                                 for s in res.get("sources", [])]
    idea_tok = _tokens(idea)
    matches = []
    for m in raw:
        sim = m.get("similarity")
        if sim is None:
            sim = _jaccard(idea_tok, _tokens(f"{m.get('title', '')} {m.get('summary', '')}"))
        matches.append({"title": m.get("title", ""), "url": m.get("url", ""), "similarity": float(sim)})
    matches.sort(key=lambda x: -x["similarity"])

    top = matches[0]["similarity"] if matches else 0.0
    union = set().union(*[_tokens(f"{m.get('title', '')} {m.get('summary', '')}") for m in raw]) if raw else set()
    coverage = round(len(idea_tok & union) / len(idea_tok), 3) if idea_tok else 0.0

    if top >= rename_threshold:
        status, provisional = "RENAMED", False
        why = (f"a single existing work matches closely (“{matches[0]['title']}”, similarity {top}); "
               f"this is most likely a rename of prior art — not novel.")
    elif coverage >= collage_coverage and top >= 0.25:
        status, provisional = "COLLAGE", False
        why = (f"the idea's parts are already covered by a union of existing works (coverage {coverage}); "
               f"this is most likely a collage of prior art — a new NAME, not a new mechanism.")
    else:
        status, provisional = "NO_PRIOR_ART_FOUND", True
        why = (f"no close prior art among the {len(matches)} sources searched — PROVISIONAL novelty "
               f"(absence of evidence, not proof). To be genuinely new it must EXTRAPOLATE BEYOND this "
               f"searched world (break a further assumption; see green_star), not merely be unseen here.")
    confidence = round(top if status != "NO_PRIOR_ART_FOUND" else max(0.0, 1.0 - top), 2)
    return NoveltyVerdict(idea=idea, status=status, confidence=confidence, closest_matches=matches[:5],
                          sources_searched=len(matches), provisional=provisional, why=why,
                          # provenance flows through from a scope-aware provider (CompositePriorArtProvider);
                          # an old provider supplies none → novelty_scope stays "" and nothing is gated.
                          novelty_scope=str(res.get("novelty_scope", "")),
                          coverage_level=str(res.get("coverage_level", "")),
                          checked_sources=list(res.get("checked_sources", []) or []),
                          failed_sources=list(res.get("failed_sources", []) or []),
                          retrieved_at=str(res.get("retrieved_at", "")))


def honest_prior_art_status(idea: str, provider=None, min_real_sources: int = 3) -> Dict:
    """FIX C entrypoint: the prior-art status you may actually act on. Without a real provider — or with one
    that returned fewer than `min_real_sources` URL'd sources — the status is INCOMPLETE_ONLINE_SEARCH, never
    NO_PRIOR_ART_FOUND. Returns {status, real_sources, scope, why}."""
    if provider is None:
        return {"status": "INCOMPLETE_ONLINE_SEARCH", "real_sources": 0, "scope": "LOCAL_ONLY",
                "why": "no prior-art provider ran — only the local lexical view exists; absence of a match is not proof."}
    nv = prior_art_audit(idea, provider)
    url_sources = sum(1 for m in nv.closest_matches if str(m.get("url", "")).strip())
    status = nv.real_world_status(min_real_sources=min_real_sources)
    return {"status": status, "real_sources": url_sources, "scope": nv.novelty_scope or "LOCAL_ONLY",
            "graded_verdict": nv.graded_verdict,
            "why": ("a real online search returned enough URL'd sources" if status != "INCOMPLETE_ONLINE_SEARCH"
                    else f"only {url_sources} URL'd source(s) / scope {nv.novelty_scope or 'LOCAL_ONLY'} — "
                         "not enough for NO_PRIOR_ART; capped at INCOMPLETE_ONLINE_SEARCH.")}


def world_novelty_score(idea: str, provider) -> float:
    """A NEW, INDEPENDENT metric: how far an idea is from existing REAL work, in [0,1].
        1.0 = no close prior art among the searched sources;  0.0 = an exact existing match.

    Independent of the structural scores (box_distance, VNS, …) by construction: those measure internal
    rigor, this measures distance from the real world. An idea can be perfectly structured AND a rename —
    high structural score, low world_novelty. PROVISIONAL: absence of prior art is not proof of novelty.
    """
    nv = novelty_audit(idea, provider)
    top = nv.closest_matches[0]["similarity"] if nv.closest_matches else 0.0
    return round(max(0.0, 1.0 - top), 3)


# ── Impl 2: a STRONGER, graded prior-art audit ─────────────────────────────────────────────────────────
def prior_art_distance_score(matches: List[Dict]) -> float:
    """[0,1]: 1 − the single closest prior-art similarity. 1 = far from everything found, 0 = exact match."""
    top = max((m.get("similarity", 0.0) for m in matches), default=0.0)
    return round(max(0.0, 1.0 - float(top)), 3)


def source_overlap_score(idea: str, matches: List[Dict]) -> float:
    """[0,1]: fraction of the idea's content tokens covered by the UNION of the sources — a collage signal
    (the parts already exist, even if no single source matches)."""
    it = _tokens(idea)
    if not it:
        return 0.0
    union = set().union(*[_tokens(f"{m.get('title','')} {m.get('summary','')}") for m in matches]) if matches else set()
    return round(len(it & union) / len(it), 3)


def rebranding_detector(matches: List[Dict], threshold: float = 0.55) -> bool:
    """True when a SINGLE existing work matches closely — a likely rename of prior art."""
    return max((m.get("similarity", 0.0) for m in matches), default=0.0) >= threshold


def collage_detector(idea: str, matches: List[Dict], coverage: float = 0.7, min_top: float = 0.25) -> bool:
    """True when no single source matches but the UNION covers the idea — a likely collage of prior art."""
    top = max((m.get("similarity", 0.0) for m in matches), default=0.0)
    return source_overlap_score(idea, matches) >= coverage and top >= min_top


def prior_art_audit(idea: str, provider, pack=None, verifier_passed: bool = None) -> NoveltyVerdict:
    """The graded prior-art audit (Impl 2). Maps an idea to one of GRADED_VERDICTS — NEVER 'absolute novelty':

      RENAMED_PRIOR_ART       a single close match → a rename.
      COLLAGE_OF_PRIOR_ART    the union of sources covers it → a recombination, a new NAME not a new mechanism.
      WEAKLY_NOVEL            no close match, but moderate overlap remains → novel only at the margin.
      PROVISIONALLY_NOVEL     far from everything searched → provisional novelty (absence is NOT proof).
      VERIFIED_USEFUL_NOVELTY provisionally novel AND a real external check passed (verifier_passed=True) →
                              the only state that pairs novelty with demonstrated usefulness (computational-
                              creativity: novel + valuable + verifiable, never 'different' alone).

    Reuses `novelty_audit` for the search, then grades it and fills the honesty fields (scope, why-not-
    absolute, the falsification query that would REFUTE the claim)."""
    nv = novelty_audit(idea, provider, pack=pack)
    matches = nv.closest_matches
    dist = prior_art_distance_score(matches)
    overlap = source_overlap_score(idea, matches)
    top = matches[0]["similarity"] if matches else 0.0

    if rebranding_detector(matches):
        graded = "RENAMED_PRIOR_ART"
    elif collage_detector(idea, matches):
        graded = "COLLAGE_OF_PRIOR_ART"
    elif top >= 0.35 or overlap >= 0.45:
        graded = "WEAKLY_NOVEL"
    elif verifier_passed:
        graded = "VERIFIED_USEFUL_NOVELTY"
    else:
        graded = "PROVISIONALLY_NOVEL"

    # HONESTY GATE (Step 1): strong provisional novelty is only warranted when a real online search actually
    # ran. This fires ONLY when the provider supplied an explicit novelty_scope (the CompositePriorArtProvider);
    # an old/local provider supplies none → unchanged behaviour (no regression).
    scope = nv.novelty_scope
    if scope and scope != "ONLINE_PRIOR_ART_CHECKED" and graded in ("PROVISIONALLY_NOVEL", "VERIFIED_USEFUL_NOVELTY"):
        # WITHOUT a successful online prior-art search, neither strong-provisional NOR verified-useful novelty is
        # warranted (a passing verifier proves USEFUL, not NOVEL). Downgrade the human-facing label so it cannot
        # contradict the appended "novelty NOT established" warning. (claims_novelty() already gates programmatically.)
        was = graded
        graded = "WEAKLY_NOVEL"
        nv.why = (nv.why + f" [scope={scope}: no successful ONLINE prior-art search, so {was} is NOT warranted "
                  "— downgraded to WEAKLY_NOVEL.]")

    key_terms = sorted(_tokens(idea))[:6]
    falsification_query = (f"search for: {' '.join(key_terms)} (web / arXiv / GitHub). A single result with "
                           f"similarity ≥ 0.55 REFUTES this as RENAMED_PRIOR_ART; broad coverage by several "
                           f"results REFUTES it as COLLAGE_OF_PRIOR_ART.")
    why_not_absolute = ("absolute novelty is practically unprovable: only a finite set of sources was searched, "
                        f"with lexical (not semantic) matching. Scope here: {nv.sources_searched} sources.")
    what_would_falsify = (falsification_query + " A failed external verifier would also drop "
                          "VERIFIED_USEFUL_NOVELTY back to PROVISIONALLY_NOVEL.")
    nv.graded_verdict = graded
    nv.prior_art_distance_score = dist
    nv.source_overlap_score = overlap
    nv.claim_scope = f"{nv.sources_searched} searched sources; lexical matching; provider-bounded"
    nv.falsification_query = falsification_query
    nv.why_not_absolute = why_not_absolute
    nv.what_would_falsify_this = what_would_falsify
    return nv
