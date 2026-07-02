"""research — source an UNKNOWN domain in real time instead of refusing, without fabricating.

When the guard fires on a domain OUTLIER_MCB has no pack for, it does not have to give up. It can BUILD
a provisional pack from real sources — but the core must stay zero-dependency and deterministic, so the
web access is a PLUGGABLE `ResearchProvider` injected by the caller (a coding assistant in VS Code already
has the web; the library does not bundle a scraper).

The honest split the engine demanded when applied to this very problem:
  • the WEB yields the KNOWN FAMILIES (the box) — the standard approaches, cited by URL;
  • the ASSUMPTIONS to break still come from FIRST PRINCIPLES (greenstar.synthesize_assumptions);
  • the result is PROVISIONAL: sources are attached, pack_quality validates it, and the engine still
    falsifies — a sourced pack is never treated as authoritative.

Providers:
  CallableProvider(fn)   wrap a function the assistant supplies (it does the web research, returns a spec)
  WebResearchProvider()  a reference, stdlib-only (urllib) provider that queries GitHub's search API
  (any object with `.research(prompt) -> dict` works)
"""
from __future__ import annotations
from typing import Callable, Dict, List, Optional

from .errors import OUTLIER_MCBError
from .pack import DomainPack, register_pack
from .pack_quality import pack_quality
from .elicit import pack_from_spec


class ResearchError(OUTLIER_MCBError):
    """A provider returned nothing usable (no sources) — the engine will not build a pack from nothing."""


def _slug(text: str) -> str:
    return ("web_" + "_".join((text or "domain").lower().split()[:4])).replace("-", "_")[:40]


def _keywords(prompt: str) -> List[str]:
    stop = {"the", "a", "an", "for", "with", "design", "new", "build", "make", "system", "that"}
    return sorted({w for w in "".join(c if c.isalnum() else " " for c in (prompt or "").lower()).split()
                   if len(w) > 3 and w not in stop})[:8]


def auto_elicit(prompt: str, provider, register: bool = True, n_axes: int = 4) -> tuple:
    """Build a PROVISIONAL DomainPack for `prompt` from a research provider's real, cited findings.

    The provider supplies the known families (the box) from the web; the assumptions to break are taken
    from the provider if it gives them, otherwise synthesized from first principles. Returns (pack, meta)
    where meta carries the sources, the pack_quality, and an explicit provisional warning. Raises
    ResearchError if the provider returns no sources — the engine never invents a domain from nothing.
    """
    res = provider.research(prompt) or {}
    sources = res.get("sources") or []
    if not sources:
        raise ResearchError("the research provider returned no cited sources; refusing to build a pack "
                            "from nothing (use elicit_pack to fill the scaffold by hand instead).")

    families = list(res.get("known_families") or [])
    keywords = list(res.get("keywords") or _keywords(prompt))

    if res.get("assumptions"):                                   # the provider researched the assumptions too
        assumptions_spec = res["assumptions"]
        axes_spec = res.get("axes") or {a.get("axis", "STRUCTURE"): {"priority": 3, "verdict": "web-sourced axis"}
                                        for a in assumptions_spec}
    else:                                                        # families from the web, assumptions from first principles
        from .greenstar import synthesize_assumptions
        syn = synthesize_assumptions(prompt, n_axes)
        assumptions_spec = [{"name": a.name, "description": a.description, "why_obvious": a.why_obvious,
                             "if_false": a.if_false, "falsifier": a.falsifier,
                             "axis": a.name.split("_is_")[0].upper()} for a in syn]
        axes_spec = {a["axis"]: {"priority": 3, "verdict": "first-principles axis over web-sourced families"}
                     for a in assumptions_spec}

    spec = {"name": res.get("name") or _slug(prompt), "keywords": keywords,
            "box_name": res.get("box_name") or "the standard, most-cited approach for this domain (web-sourced)",
            "assumptions": assumptions_spec, "axes": axes_spec, "relations": res.get("relations", []),
            "known_families": families or ["the standard / most-cited approach"],
            "info_kinds": res.get("info_kinds") or {"more_sources": "additional real references for this domain"}}
    pack = pack_from_spec(spec)
    quality = pack_quality(pack)
    if register:
        register_pack(pack)
    meta = {"provisional": True, "sources": sources, "quality": quality["overall"],
            "warning": ("PROVISIONAL pack sourced from the web — NOT authoritative. The known families are "
                        "from real references; the assumptions are first-principles. The engine still falsifies.")}
    return pack, meta


# ── providers ──────────────────────────────────────────────────────────────────────────────────────
class CallableProvider:
    """Wrap any function `fn(prompt) -> spec_dict` — e.g. the assistant does the web research and returns
    {known_families, sources, [assumptions], [box_name], ...}. This is the primary provider in VS Code."""
    def __init__(self, fn: Callable[[str], Dict]):
        self._fn = fn

    def research(self, prompt: str) -> Dict:
        return self._fn(prompt) or {}


class WebResearchProvider:
    """A reference provider: query GitHub's public search API (stdlib urllib only) for repositories matching
    the prompt, and turn their names/topics into known families + cited sources. Opt-in and network-bound;
    it degrades to an empty result on any error, so it never crashes the caller (which then falls back to
    the elicitation scaffold). Not used by the test suite."""
    def __init__(self, max_results: int = 8, timeout: int = 8):
        self.max_results, self.timeout = max_results, timeout

    def research(self, prompt: str) -> Dict:
        import json
        import urllib.parse
        import urllib.request
        q = " ".join(_keywords(prompt)) or prompt
        url = "https://api.github.com/search/repositories?" + urllib.parse.urlencode(
            {"q": q, "sort": "stars", "order": "desc", "per_page": self.max_results})
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                                       "User-Agent": "OUTLIER_MCB"})
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                data = json.loads(r.read().decode("utf-8"))
        except Exception:
            return {}
        families, sources = [], []
        for item in data.get("items", [])[:self.max_results]:
            name = item.get("name", "")
            if name:
                families.append(name.lower().replace("-", "_"))
            url_ = item.get("html_url")
            if url_:
                sources.append({"title": item.get("full_name", name), "url": url_,
                                "stars": item.get("stargazers_count", 0)})
        return {"known_families": families, "sources": sources,
                "box_name": f"the most-starred existing approaches to: {q}"}
