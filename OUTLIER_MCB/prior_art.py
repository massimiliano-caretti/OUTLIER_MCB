"""prior_art — real, multi-source prior-art search with explicit provenance and an honest novelty_scope.

The library's whole claim to honesty is "absence of a match is not proof of novelty". That claim is only
meaningful if we say WHAT was actually searched. Today novelty can be judged against a local archive, a
pack's known families, or a fake test provider — none of which is the real world. This module makes the
scope explicit:

  • PriorArtProvider      a stable interface; every result carries its source, source_type and timestamps.
  • OfflinePriorArtProvider   canned results for deterministic tests/CI (is_online=False).
  • OnlinePriorArtProvider    abstract base for live sources (arXiv / OpenAlex / GitHub …), key-free where
                              possible; any failure is captured, never silently swallowed.
  • CompositePriorArtProvider queries several providers, deduplicates with provenance, records which
                              succeeded and which FAILED, and computes the novelty_scope:
                                LOCAL_ONLY              — no online provider was configured at all;
                                INCOMPLETE_ONLINE_SEARCH — online providers were configured but ALL failed;
                                ONLINE_PRIOR_ART_CHECKED — at least one online provider actually answered.

A strong "provisionally novel" verdict is only warranted under ONLINE_PRIOR_ART_CHECKED (enforced in
novelty.prior_art_audit). No verdict ever claims "absolute novelty". Zero hard dependency: the online
providers use stdlib urllib only and degrade to a captured error offline.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .errors import OUTLIER_MCBError

NOVELTY_SCOPES = ("LOCAL_ONLY", "OFFLINE_CORPUS_CHECKED", "INCOMPLETE_ONLINE_SEARCH", "ONLINE_PRIOR_ART_CHECKED")
SOURCE_TYPES = ("github", "paper", "patent", "web", "package", "news", "docs", "local")


class PriorArtError(OUTLIER_MCBError):
    """A provider failed to answer (network, rate-limit, parse). Captured by the composite as a failed source."""


def _now() -> str:
    """An ISO-8601 UTC timestamp for live retrieval. Tests pass an explicit retrieved_at for determinism."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _wall_clock() -> float:
    """Monotonic-ish seconds for the cache TTL. Injectable in CachedPriorArtProvider for deterministic tests."""
    import time
    return time.time()


@dataclass
class PriorArtResult:
    """One prior-art hit with full provenance — so a novelty verdict can be audited, not just trusted."""
    title: str
    summary: str = ""
    url: str = ""
    source: str = ""                     # the provider that returned it (e.g. 'arxiv')
    source_type: str = "web"             # github | paper | patent | web | package | news | docs | local
    similarity: Optional[float] = None   # None ⇒ the auditor computes a lexical/semantic similarity
    published_at: str = ""
    retrieved_at: str = ""
    raw: Dict = field(default_factory=dict)

    def as_match(self) -> Dict:
        """The shape novelty.novelty_audit consumes (title/summary/url/similarity) + the provenance it keeps."""
        return {"title": self.title, "summary": self.summary, "url": self.url,
                "similarity": self.similarity, "source": self.source, "source_type": self.source_type,
                "published_at": self.published_at, "retrieved_at": self.retrieved_at}


class PriorArtProvider:
    """Stable interface. Implement `search(query) -> [PriorArtResult]`; `research` adapts it to the dict
    shape novelty_audit/prior_art_audit already accept, so a provider drops straight in."""
    name: str = "base"
    is_online: bool = False
    source_type: str = "web"

    def search(self, query: str) -> List[PriorArtResult]:
        raise NotImplementedError

    def research(self, query: str) -> Dict:
        return {"matches": [r.as_match() for r in self.search(query)]}


class OfflinePriorArtProvider(PriorArtProvider):
    """Canned results for deterministic tests/CI — NEVER a stand-in for a real search (is_online=False, so
    a composite that has only this provider reports novelty_scope=LOCAL_ONLY)."""
    name = "offline"
    is_online = False
    source_type = "local"

    def __init__(self, fixtures: List[Dict], name: str = "offline"):
        self.name = name
        self._fixtures = [r if isinstance(r, PriorArtResult) else PriorArtResult(
            title=r.get("title", ""), summary=r.get("summary", ""), url=r.get("url", ""),
            source=r.get("source", name), source_type=r.get("source_type", "local"),
            similarity=r.get("similarity"), published_at=r.get("published_at", ""),
            retrieved_at=r.get("retrieved_at", "")) for r in fixtures]

    def search(self, query: str) -> List[PriorArtResult]:
        return list(self._fixtures)


class OnlinePriorArtProvider(PriorArtProvider):
    """Abstract base for a live source. Subclasses implement `_fetch`; any exception becomes a PriorArtError
    so the composite records it as a failed source (which drives INCOMPLETE_ONLINE_SEARCH) — never a silent
    empty result that could masquerade as 'searched and found nothing'."""
    is_online = True

    def __init__(self, max_results: int = 8, timeout: int = 8):
        self.max_results, self.timeout = max_results, timeout

    def _fetch(self, query: str) -> List[PriorArtResult]:
        raise NotImplementedError

    def search(self, query: str) -> List[PriorArtResult]:
        try:
            return self._fetch(query)
        except PriorArtError:
            raise
        except Exception as exc:
            raise PriorArtError(f"{self.name} failed: {exc}") from exc


def _http_json(url: str, timeout: int, headers: Optional[Dict] = None) -> Dict:
    import json
    import urllib.request
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "OUTLIER_MCB"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _enc(params: Dict) -> str:
    import urllib.parse
    return urllib.parse.urlencode(params)


class ArxivPriorArtProvider(OnlinePriorArtProvider):
    """arXiv (key-free Atom API). source_type='paper'."""
    name = "arxiv"
    source_type = "paper"

    def _fetch(self, query: str) -> List[PriorArtResult]:
        import urllib.request
        from xml.etree import ElementTree as ET
        url = "http://export.arxiv.org/api/query?" + _enc(
            {"search_query": "all:" + query, "start": 0, "max_results": self.max_results})
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "OUTLIER_MCB"}),
                                    timeout=self.timeout) as r:
            root = ET.fromstring(r.read())
        ns = {"a": "http://www.w3.org/2005/Atom"}
        out = []
        for e in root.findall("a:entry", ns):
            out.append(PriorArtResult(
                title=(e.findtext("a:title", "", ns) or "").strip(),
                summary=(e.findtext("a:summary", "", ns) or "").strip()[:500],
                url=(e.findtext("a:id", "", ns) or "").strip(), source=self.name,
                source_type=self.source_type, published_at=(e.findtext("a:published", "", ns) or "").strip(),
                retrieved_at=_now()))
        return out


class OpenAlexProvider(OnlinePriorArtProvider):
    """OpenAlex works (key-free JSON). source_type='paper'."""
    name = "openalex"
    source_type = "paper"

    @staticmethod
    def _abstract(inv_index) -> str:
        """Reconstruct the abstract text from OpenAlex's abstract_inverted_index (word -> [positions]).
        Without this the similarity sees only the title and misses most real matches."""
        if not isinstance(inv_index, dict) or not inv_index:
            return ""
        positions = []
        for word, idxs in inv_index.items():
            for i in idxs:
                positions.append((i, word))
        return " ".join(w for _i, w in sorted(positions))[:600]

    def _fetch(self, query: str) -> List[PriorArtResult]:
        data = _http_json("https://api.openalex.org/works?" + _enc({"search": query, "per_page": self.max_results}),
                          self.timeout)
        out = []
        for w in data.get("results", [])[:self.max_results]:
            abstract = self._abstract(w.get("abstract_inverted_index"))
            out.append(PriorArtResult(
                title=w.get("display_name", ""), summary=abstract or (w.get("display_name") or ""),
                url=w.get("id", ""), source=self.name, source_type=self.source_type,
                published_at=w.get("publication_date", ""), retrieved_at=_now(),
                raw={"cited_by": w.get("cited_by_count")}))
        return out


class GitHubPriorArtProvider(OnlinePriorArtProvider):
    """GitHub repository search (key-free, rate-limited). source_type='github'."""
    name = "github"
    source_type = "github"

    def _fetch(self, query: str) -> List[PriorArtResult]:
        data = _http_json("https://api.github.com/search/repositories?" + _enc(
            {"q": query, "sort": "stars", "order": "desc", "per_page": self.max_results}),
            self.timeout, headers={"Accept": "application/vnd.github+json", "User-Agent": "OUTLIER_MCB"})
        out = []
        for it in data.get("items", [])[:self.max_results]:
            out.append(PriorArtResult(
                title=it.get("full_name", it.get("name", "")), summary=(it.get("description") or "")[:500],
                url=it.get("html_url", ""), source=self.name, source_type=self.source_type,
                published_at=it.get("updated_at", ""), retrieved_at=_now(),
                raw={"stars": it.get("stargazers_count", 0)}))
        return out


class CrossrefProvider(OnlinePriorArtProvider):
    """Crossref works (key-free JSON) — journal/conference publications across publishers. source_type='paper'."""
    name = "crossref"
    source_type = "paper"

    def _fetch(self, query: str) -> List[PriorArtResult]:
        data = _http_json("https://api.crossref.org/works?" + _enc({"query": query, "rows": self.max_results}),
                          self.timeout, headers={"User-Agent": "OUTLIER_MCB (mailto:noreply@example.com)"})
        out = []
        for it in data.get("message", {}).get("items", [])[:self.max_results]:
            title = " ".join(it.get("title", []) or [])
            out.append(PriorArtResult(
                title=title, summary=(it.get("abstract", "") or "")[:600], url=it.get("URL", ""),
                source=self.name, source_type=self.source_type,
                published_at="-".join(str(p) for p in (it.get("published", {}).get("date-parts", [[None]])[0] or [])),
                retrieved_at=_now()))
        return out


class GitHubCodeSearchProvider(OnlinePriorArtProvider):
    """GitHub CODE search (not just repositories) — finds implementations even in unnamed files. Requires a
    token (set `token=` or GITHUB_TOKEN); without one GitHub returns 401/403, captured as a failed source
    (honestly lowering the scope), never a silent empty result. source_type='github'."""
    name = "github_code"
    source_type = "github"

    def __init__(self, max_results: int = 8, timeout: int = 8, token: str = ""):
        super().__init__(max_results, timeout)
        import os
        self.token = token or os.environ.get("GITHUB_TOKEN", "")

    def _fetch(self, query: str) -> List[PriorArtResult]:
        headers = {"Accept": "application/vnd.github.text-match+json", "User-Agent": "OUTLIER_MCB"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        data = _http_json("https://api.github.com/search/code?" + _enc({"q": query, "per_page": self.max_results}),
                          self.timeout, headers=headers)
        out = []
        for it in data.get("items", [])[:self.max_results]:
            repo = it.get("repository", {}) or {}
            out.append(PriorArtResult(
                title=f"{repo.get('full_name', '')}/{it.get('path', '')}", summary=it.get("path", ""),
                url=it.get("html_url", ""), source=self.name, source_type=self.source_type, retrieved_at=_now()))
        return out


class CallableOnlineProvider(OnlinePriorArtProvider):
    """Wrap ANY search function the caller supplies — web search, patents, Hugging Face, Papers with Code,
    a package registry — as an ONLINE provider, without the library bundling a scraper. `fn(query) -> list`
    where each item is a dict (title/summary/url/source_type) or a PriorArtResult. The pluggable way to add
    breadth (web/patents/news) the stdlib providers cannot reach."""
    def __init__(self, fn, name: str = "callable_online", source_type: str = "web", max_results: int = 8, timeout: int = 8):
        super().__init__(max_results, timeout)
        self.name, self.source_type, self._fn = name, source_type, fn

    def _fetch(self, query: str) -> List[PriorArtResult]:
        items = self._fn(query) or []
        out = []
        for r in items[:self.max_results]:
            if isinstance(r, PriorArtResult):
                out.append(r)
            else:
                out.append(PriorArtResult(title=r.get("title", ""), summary=r.get("summary", ""),
                                          url=r.get("url", ""), source=self.name,
                                          source_type=r.get("source_type", self.source_type), retrieved_at=_now()))
        return out


def coverage_level_of(providers: List[PriorArtProvider], failed_names: set) -> str:
    """How THOROUGH the online search was (the 'one source answered ≠ checked the world' concern):
      NONE     — no online provider succeeded;
      PARTIAL  — exactly one online provider answered;
      MULTI    — two answered;
      STRONG   — three or more answered."""
    online = [p for p in providers if getattr(p, "is_online", False)]
    n_ok = sum(1 for p in online if p.name not in failed_names)
    if n_ok == 0:
        return "NONE"
    return {1: "PARTIAL", 2: "MULTI"}.get(n_ok, "STRONG")


def novelty_scope_of(providers: List[PriorArtProvider], failed_names: set) -> str:
    """LOCAL_ONLY if no online provider was configured; INCOMPLETE_ONLINE_SEARCH if every online provider
    failed; ONLINE_PRIOR_ART_CHECKED if at least one online provider answered."""
    online = [p for p in providers if getattr(p, "is_online", False)]
    if not online:
        return "LOCAL_ONLY"
    if all(p.name in failed_names for p in online):
        return "INCOMPLETE_ONLINE_SEARCH"
    return "ONLINE_PRIOR_ART_CHECKED"


class CachedPriorArtProvider(PriorArtProvider):
    """Wrap any provider with a TTL cache, honestly. A hit within TTL is served with its age; an expired
    entry triggers a live refresh. The honest twist: if the refresh FAILS (the inner scope comes back
    INCOMPLETE_ONLINE_SEARCH) but a stale entry exists, the stale result is served — but its novelty_scope
    is DOWNGRADED to INCOMPLETE_ONLINE_SEARCH and a warning is attached, so a stale cache can never
    masquerade as a fresh successful search (and the audit's gate then blocks strong novelty).

    `clock` is injectable for deterministic tests; `store` lets a caller persist the cache."""
    def __init__(self, inner: PriorArtProvider, ttl_seconds: float = 86400.0, clock=None, store=None):
        self.inner = inner
        self.ttl = ttl_seconds
        self.name = f"cached:{inner.name}"
        self.is_online = getattr(inner, "is_online", False)
        self._clock = clock or _wall_clock
        self._store = store if store is not None else {}

    def search(self, query: str) -> List[PriorArtResult]:
        return self.inner.search(query)

    def _normalize(self, res: Dict) -> Dict:
        """Guarantee the rich, scoped schema even when wrapping a raw provider that only returns matches —
        so no pipeline can accidentally bypass the scope by reading a thin result."""
        res = dict(res)
        res.setdefault("matches", [])
        if "novelty_scope" not in res:
            # HONESTY FIX (#7): `is_online` is only a class flag — it does not prove a search actually
            # completed. An online provider that returned matches clearly searched; but an EMPTY return with
            # no self-reported scope is indistinguishable from a silent failure, so it must NOT be laundered
            # into ONLINE_PRIOR_ART_CHECKED (the scope that unlocks strong-novelty claims). Downgrade it.
            if self.is_online:
                res["novelty_scope"] = "ONLINE_PRIOR_ART_CHECKED" if res.get("matches") else "INCOMPLETE_ONLINE_SEARCH"
            else:
                res["novelty_scope"] = "LOCAL_ONLY"
        res.setdefault("coverage_level", "PARTIAL" if self.is_online else "NONE")
        res.setdefault("checked_sources", [{"provider": getattr(self.inner, "name", "inner"),
                                            "online": self.is_online, "count": len(res["matches"])}])
        res.setdefault("failed_sources", [])
        res.setdefault("retrieved_at", _now())
        return res

    def research(self, query: str, force_refresh: bool = False) -> Dict:
        now = self._clock()
        ent = self._store.get(query)
        if ent and not force_refresh and (now - ent["cached_at"]) <= self.ttl:
            out = self._normalize(ent["result"])
            out.update(from_cache=True, cache_age_seconds=round(now - ent["cached_at"], 3), stale=False)
            return out
        try:
            fresh = self.inner.research(query)
        except Exception as exc:                          # a raw provider that raises = a failed refresh
            fresh = {"matches": [], "novelty_scope": "INCOMPLETE_ONLINE_SEARCH", "checked_sources": [],
                     "failed_sources": [{"provider": getattr(self.inner, "name", "inner"), "online": True,
                                         "error": str(exc)}], "retrieved_at": _now()}
        if fresh.get("novelty_scope") == "INCOMPLETE_ONLINE_SEARCH" and ent:
            age = round(now - ent["cached_at"], 3)
            out = self._normalize(ent["result"])
            out.update(from_cache=True, stale=True, cache_age_seconds=age,
                       novelty_scope="INCOMPLETE_ONLINE_SEARCH", coverage_level="NONE",   # cannot confirm freshness
                       stale_warning=f"served STALE cache ({age}s old); live refresh failed → scope downgraded "
                                     "to INCOMPLETE_ONLINE_SEARCH (no strong novelty from unconfirmed data).")
            return out
        self._store[query] = {"result": fresh, "cached_at": now}
        out = self._normalize(fresh)
        out.update(from_cache=False, cache_age_seconds=0.0, stale=False)
        return out


class CompositePriorArtProvider(PriorArtProvider):
    """Query several providers, dedupe with provenance, record which succeeded and which FAILED, and report
    the honest novelty_scope. A failed provider lowers the scope — it never silently vanishes."""
    name = "composite"

    def __init__(self, providers: List[PriorArtProvider], retrieved_at: Optional[str] = None):
        self.providers = list(providers)
        self.retrieved_at = retrieved_at
        self.is_online = any(getattr(p, "is_online", False) for p in self.providers)

    def search(self, query: str) -> List[PriorArtResult]:
        return self._collect(query)[0]

    def _collect(self, query: str):
        results: List[PriorArtResult] = []
        checked: List[Dict] = []
        failed: List[Dict] = []
        for p in self.providers:
            try:
                rs = p.search(query)
                results.extend(rs)
                checked.append({"provider": p.name, "online": bool(getattr(p, "is_online", False)), "count": len(rs)})
            except Exception as exc:
                failed.append({"provider": p.name, "online": bool(getattr(p, "is_online", False)), "error": str(exc)})
        seen, deduped = set(), []
        for r in results:
            key = (r.url or r.title).strip().lower()
            if key and key not in seen:
                seen.add(key)
                deduped.append(r)
        return deduped, checked, failed

    def research(self, query: str) -> Dict:
        deduped, checked, failed = self._collect(query)
        failed_names = {f["provider"] for f in failed}
        return {"matches": [r.as_match() for r in deduped],
                "novelty_scope": novelty_scope_of(self.providers, failed_names),
                "coverage_level": coverage_level_of(self.providers, failed_names),
                "checked_sources": checked, "failed_sources": failed,
                "retrieved_at": self.retrieved_at or _now()}


def default_online_provider(cache: bool = True, include_github: bool = False, ttl_seconds: float = 86400.0):
    """One-call wiring of a REAL online prior-art search (fix B): arXiv + OpenAlex + Crossref composed, so the
    default novelty path can REACH `ONLINE_PRIOR_ART_CHECKED` scope instead of staying `LOCAL_ONLY`. Key-free
    public sources; cached by default (a day). Network happens at call time — never used by the unit tests; it
    is the explicit, honest way to let the engine check the real world. `include_github=True` adds code prior art."""
    providers: List[PriorArtProvider] = [ArxivPriorArtProvider(), OpenAlexProvider(), CrossrefProvider()]
    if include_github:
        providers.append(GitHubPriorArtProvider())
    composite = CompositePriorArtProvider(providers)
    return CachedPriorArtProvider(composite, ttl_seconds=ttl_seconds) if cache else composite
