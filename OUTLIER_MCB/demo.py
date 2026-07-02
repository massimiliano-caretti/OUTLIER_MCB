"""demo — a zero-configuration, offline, end-to-end tour of the library, so a first-time user sees it WORK with
no setup: no LLM, no network, no API key, no domain pack to write. It runs the honest pipeline on a bundled
example and returns a readable report — addressing the "needs significant configuration to be useful" concern by
giving a batteries-included default that already exercises the distinctive parts (assumption-breaking, the claim
ladder, and an offline prior-art check against a curated corpus).
"""
from __future__ import annotations
from typing import Optional


def demo(prompt: str = "invent a better rate limiter for a distributed API gateway",
         idea: str = "measure the rate by request cost instead of by a fixed time window") -> str:
    """Run the full offline pipeline on one prompt+idea and render an honest report. Deterministic; needs
    nothing wired. Steps: (1) the creative brief (which assumption to break), (2) judge the free-text idea,
    (3) check it against the in-box prior-art corpus (OFFLINE_CORPUS_CHECKED), (4) the claim-honesty gate."""
    from .preflight import creative
    from .judge import judge
    from .novelty import novelty_audit
    from .known_methods import OfflineCorpusProvider
    from .claim_ladder import gate_claim_language

    lines = ["# OUTLIER_MCB — zero-config offline demo",
             "(no LLM, no network, no API key, no custom pack — just the deterministic default tier)", ""]

    lines.append("## 1) Creative brief — which hidden assumption to break")
    brief = creative(prompt)
    lines.append(brief.strip().splitlines()[0] if brief.strip() else "(no brief)")
    lines.append("")

    lines.append("## 2) Discipline a free-text idea (judge)")
    j = judge(idea, prompt=prompt)
    lines.append(f"- verdict: **{j.verdict}** · breaks: {j.broken_assumption or '—'} · verifiability: {j.verifiability}")
    lines.append(f"- next step: {j.next_step}")
    lines.append("")

    lines.append("## 3) Offline prior-art check (curated corpus, no network)")
    nv = novelty_audit(idea, OfflineCorpusProvider())
    lines.append(f"- novelty_scope: **{nv.novelty_scope}** · status: {nv.status}")
    lines.append("")

    lines.append("## 4) Claim-honesty gate")
    claim = f"a novel, verified rate limiter that is a breakthrough"
    g = gate_claim_language(claim)
    lines.append(f"- as written: «{claim}»")
    lines.append(f"- honest rewrite: «{g['rewritten']}»")
    lines.append("")
    lines.append("This is the FLOOR (deterministic, honest). Wire an LLM for content, an online provider for "
                 "prior art, and a repo/prover/data for settlement to raise each tier — see capabilities_markdown().")
    return "\n".join(lines)
