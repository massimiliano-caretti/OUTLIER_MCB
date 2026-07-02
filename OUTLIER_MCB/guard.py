"""guard — refuse the domain-canned answer; route with a confidence MARGIN, not a bare keyword count.

The failure mode to prevent: silently picking a pack on a weak keyword overlap, so an ambiguous or
mis-routed prompt gets a confident-but-wrong answer. The guard fires (→ elicitation) when no pack
clearly matches: either nothing scores, or the top two packs are too close to call. Pass a real
`RepoContext` (grounding.probe) to ground the routing in the project's actual language.
"""
from __future__ import annotations
from typing import Dict, Optional

from .pack import select_pack, pack_scores, DomainPack


def domain_confidence(prompt: str, pack: DomainPack) -> int:
    """How many of a pack's keywords the prompt contains (a quick, repo-blind confidence proxy)."""
    return sum(1 for k in pack.keywords if k in (prompt or "").lower())


def guard_response(prompt: str, min_hits: int = 1, margin: int = 1, repo=None) -> Dict:
    """Decide whether a registered pack may answer, or whether elicitation is required.

    Fires (ok=False) when: no pack scores ≥ min_hits, OR the lead of the top pack over the runner-up is
    smaller than `margin` (an ambiguous route). `repo` (grounding.RepoContext) grounds the score."""
    scores = pack_scores(prompt, repo)
    top = scores[0] if scores else (None, 0)
    second = scores[1][1] if len(scores) > 1 else 0
    pack, hits = select_pack(prompt, repo)

    if pack is None or pack.name == "generic" or hits < min_hits:
        return {"ok": False, "pack": (pack.name if pack else None), "confidence": hits, "margin": top[1] - second,
                "message": ("no registered domain pack matches this prompt. Do NOT answer from a canned domain — "
                            "call elicit_pack(prompt) to BUILD the domain's assumptions first, then falsify.")}
    if top[1] - second < margin:
        return {"ok": False, "pack": pack.name, "confidence": hits, "margin": top[1] - second,
                "message": (f"routing is AMBIGUOUS: '{top[0]}' and '{scores[1][0]}' score nearly the same "
                            f"({top[1]} vs {second}). Do not guess — confirm the domain or call elicit_pack(prompt).")}
    return {"ok": True, "pack": pack.name, "confidence": hits, "margin": top[1] - second,
            "message": f"pack '{pack.name}' matches (score={hits}, margin={top[1] - second}); kernel may proceed."}
