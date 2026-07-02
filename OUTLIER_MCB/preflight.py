"""preflight — the single entry point for a VS Code assistant facing "invent something new".

    from OUTLIER_MCB import preflight_creative_request
    pf = preflight_creative_request(user_prompt)     # auto-selects the domain pack
    print(pf["instructions"])                         # short, ready to steer the assistant

This is a THIN agnostic wrapper. It selects the matching DomainPack (or the generic fallback +
elicitation flag), then delegates to the domain-blind kernel. Every domain is just one pack; a
rate-limiter or a theorem select their own packs and get DIFFERENT answers. Pass `pack=` to force one.
"""
from __future__ import annotations
from typing import Dict, Optional, Union
from . import kernel
from .pack import route_pack, get_pack, DomainPack
from .types import PreflightResult


def preflight_creative_request(prompt: str,
                               repo_context: Optional[Union[str, object]] = None,
                               failure_memory: Optional[Dict] = None,
                               pack: Optional[DomainPack] = None,
                               repo_path: Optional[str] = None) -> PreflightResult:
    """Route to a pack (with full decision evidence), then run the kernel.

    Grounding is STRUCTURED: pass a `RepoContext` as `repo_context`, or a `repo_path` to probe one — it
    flows through routing and the guard as data, not as text concatenated to the prompt (a bare string
    `repo_context` is still accepted for backward compatibility). An explicit `pack` is caller intent:
    it is always honoured and never triggers elicitation.
    """
    # ── structured grounding: a RepoContext (or a probed repo_path) — never text in the prompt ──
    repo = None
    if repo_path is not None:
        from .grounding import probe
        repo = probe(repo_path)
    if repo_context is not None and hasattr(repo_context, "grounded"):   # a RepoContext was passed
        repo = repo_context
        repo_context = None
    problem = (prompt or "") + (("\n" + repo_context) if isinstance(repo_context, str) and repo_context else "")

    # ── evidence-based routing; an explicit pack always wins ──
    decision = route_pack(problem, repo=repo, pack=pack)
    the_pack = pack if pack is not None else get_pack(decision.selected_pack)

    signals = (failure_memory or {}).get("signals") if isinstance(failure_memory, dict) else None
    result = kernel.preflight(problem, the_pack, signals=signals)

    confident = decision.used_explicit_pack or (
        decision.selected_pack != "generic" and decision.confidence >= 1 and not decision.ambiguous)
    result["domain_guard"] = {
        "ok": confident,
        "pack": decision.selected_pack,
        "used_explicit_pack": decision.used_explicit_pack,
        "repo_language_boost": decision.repo_language_boost,
        "confidence": decision.confidence, "margin": decision.margin, "ambiguous": decision.ambiguous,
        "scores": decision.scores, "source": decision.source, "reason": decision.reason,
        "message": decision.reason,
    }
    # FIX D: if the request is in a family closed by a REPRESENTATION THEOREM (e.g. a "new permutation-invariant
    # pooling" is governed by DeepSets universality), surface the theorem and route to the admissible exits only.
    try:
        from .theorems import theorem_brief
        tb = theorem_brief(problem, the_pack)
        if tb is not None:
            result["theorem_brief"] = tb
            result["instructions"] = "[OUTLIER_MCB theorem] " + tb["brief"] + "\n" + result["instructions"]
    except Exception:
        pass

    # elicitation ONLY when the engine itself is unsure — never when the caller named a pack.
    if not decision.used_explicit_pack and not confident:
        result["elicitation_required"] = True
        result["instructions"] = ("[OUTLIER_MCB guard] " + decision.reason + "\n" + result["instructions"])
        # #9: don't just refuse — INDUCE a provisional pack from the problem (+ repo) so the engine has a
        # falsifiable conceptual space to work with instead of only the generic one. Provisional, never authoritative.
        try:
            from .pack_induction import infer_domain_pack, validate_inferred_pack
            induced = infer_domain_pack(problem, repo=repo if isinstance(repo, dict) else None)
            if not validate_inferred_pack(induced):          # only attach a pack that is actually usable
                result["inferred_pack"] = induced
                result["inferred_pack_assumptions"] = [a.name for a in induced.assumptions]
                result["inferred_pack_note"] = ("PROVISIONAL pack induced from the problem (first-principles axes "
                                                "with concrete falsifiers) — use it or elicit a better one; never authoritative.")
        except Exception:
            pass
    return result


# convenience alias
preflight = preflight_creative_request


def creative(prompt: str, pack: Optional[DomainPack] = None, k: int = 3, provider=None,
             diagram: bool = False) -> str:
    """THE one-call entrypoint for a coding assistant. One prompt in → one ready-to-follow brief out.

        import OUTLIER_MCB as gsl
        print(gsl.creative("invent a new caching architecture"))

    It selects (or asks you to elicit) the domain pack, prints the rules to obey while answering, and
    diverges into K branches in tension. Everything else in the library is for going deeper by hand.
    `diagram=True` appends a Mermaid view of the assumption graph (opt-in; off by default so the standard
    brief is unchanged).
    """
    pf = preflight_creative_request(prompt, pack=pack)
    # real-time research: if the domain is unknown but the caller supplied a research provider, SOURCE the
    # domain from the web (provisional, cited) instead of refusing — the engine still falsifies.
    if pf.get("elicitation_required") and provider is not None:
        from .research import auto_elicit, ResearchError
        try:
            built, meta = auto_elicit(prompt, provider)
            header = ("[OUTLIER_MCB sourced an unknown domain from the web — " + meta["warning"] + "\n"
                      " sources: " + "; ".join(s.get("url", s.get("title", "")) for s in meta["sources"][:5])
                      + f"  · pack_quality={meta['quality']}]\n")
            return header + creative(prompt, pack=built, k=k)
        except ResearchError:
            pass            # no usable sources → fall through to the honest elicitation scaffold below
    out = [pf["instructions"]]
    if pf.get("elicitation_required"):
        from .elicit import elicit_pack
        e = elicit_pack(prompt)
        if e.get("request"):
            out.append("\n[no known domain] Two honest paths — do NOT fake a domain answer:")
            out.append("  (a) ELICIT examples and build a pack:")
            for i, q in enumerate(e["request"]["questions"], 1):
                out.append(f"      {i}. {q}")
            out.append("      then: pack = gsl.pack_from_spec(filled_spec); gsl.creative(prompt, pack=pack).")
            out.append("  (b) GREEN-STAR (no examples at all): gsl.green_star(prompt) — generate pure")
            out.append("      first-principles structure and extrapolate beyond every known example.")
    else:
        from . import kernel
        from .pack import get_pack
        p = pack or get_pack(pf["pack"])
        out.append("\n[divergence] Branches in tension — choose ONE assumption to break, then falsify it:")
        for b in kernel.branch_on_assumptions(prompt, p, k=k):
            out.append(f"  [{b['stance']:11s}] break '{b['assumption']}' on axis {b['axis']} → {b['negation']}")
        # plural generator: composed/inverted/regime ideas the single-break divergence cannot reach
        from .generators import recombine_assumptions, invert_assumption, scale_break, breakable
        extra = recombine_assumptions(p, k=2, max_candidates=2)
        bk = breakable(p)
        if bk:
            inv = invert_assumption(p, bk[0].name)
            sc = scale_break(p, bk[0].name)
            extra += [c for c in (inv, sc) if c]
        if extra:
            out.append("\n[generate] Composed / inverted / regime candidates (still must die on a world-test):")
            for c in extra:
                out.append(f"  • [{c.operator}] {c.name}: {c.negation[:110]}")
                out.append(f"      ↳ survives only if: {c.discipline[:110]}")
        if diagram:
            out.append("\n[diagram] AssumptionGraph (Mermaid — box=red, breakable=green, ★=central):")
            out.append("```mermaid\n" + kernel.graph_of(p).mermaid() + "\n```")
    return "\n".join(out)
