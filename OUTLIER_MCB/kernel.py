"""kernel — the agnostic creativity engine. It knows nothing about any domain.

Everything it needs comes from a DomainPack, so the same kernel runs on a rate-limiter, a convergence
theorem, or a domain it has never seen (via an elicited pack). Public operations:

  graph_of(pack)                      build the typed assumption graph from a pack
  preflight(prompt, pack)             what NOT to propose · 3 breaks · 1 direction · death-gate · instructions
  no_solution_before_assumption(...)  gate ANY proposed solution (INSIDE_THE_BOX until justified)
  branch_on_assumptions(prompt, pack) divergence: K candidate breaks in tension across distinct axes
  novelty_score(...)                  graded concept-novelty (collage vs local vs architectural)

Collaborators: assumption_graph (the graph type), core.negate, instruction_emitter, types.PreflightResult.
"""
from __future__ import annotations
from typing import Dict, List, Optional

from .assumption_graph import AssumptionGraph
from .closures import _mentions          # whole-word family match (avoids short 'net'→'ResNet' substring)
from .core import negate
from .instruction_emitter import emit_assistant_instructions
from .types import PreflightResult

# prompt words signalling a request to exceed the current ceiling (used by the missing-info heuristic).
_CEILING = ["invent", "new ", "novel", "original", "breakthrough", "beat ", "outperform",
            "never seen", "ceiling", "limited", "more model", "another model", "no collage"]
# the fields a proposed solution must declare before it can leave INSIDE_THE_BOX.
REQUIRED_FIELDS = ("breaks_assumption", "family_that_cannot", "new_output", "new_data", "world_test")
_STANCES = ["conservative", "radical", "hybrid", "contrarian"]


# ── graph construction ──────────────────────────────────────────────────────────────────────────
def _graph_fingerprint(pack) -> tuple:
    """A cheap content fingerprint of everything graph_of reads — so the cache invalidates the moment the
    pack's structure changes (a mutation or an _extend_pack copy) and never returns a stale graph."""
    return (tuple(a.name for a in pack.assumptions),
            tuple(sorted(pack.dimension_of.items())),
            tuple(sorted(pack.box_assumptions)), len(pack.relations))


def graph_of(pack, prompt: str = "") -> AssumptionGraph:
    """Build the typed AssumptionGraph from a pack; each node carries its own box/axis/breakable flags
    so the kernel stays blind to the domain content. The result is CACHED on the pack (keyed by a content
    fingerprint), since `graph_of` is called repeatedly per pack and the graph depends only on the pack —
    a measurable saving on large packs, transparent and self-invalidating on any structural change."""
    fp = _graph_fingerprint(pack)
    cached = getattr(pack, "_graph_cache", None)
    if cached is not None and cached[0] == fp:
        return cached[1]
    nodes = {a.name: {"description": a.description, "in_box": a.name in pack.box_assumptions,
                      "dimension": pack.dimension_of.get(a.name),
                      "breakable": bool(pack.dimension_of.get(a.name)), "falsifier": a.falsifier}
             for a in pack.assumptions}
    edges = [e for e in pack.relations if e[0] in nodes]
    g = AssumptionGraph(nodes=nodes, edges=edges)
    try:
        pack._graph_cache = (fp, g)
    except Exception:
        pass                                            # a frozen/exotic pack just skips the cache
    return g


# ── shared ranking (used by both preflight and divergence) ────────────────────────────────────────
def _priority(pack, axis: str) -> int:
    return pack.axes.get(axis, {}).get("priority", 1)


def _failure_count(pack, name: str) -> int:
    """How many DEAD ideas in this pack's failure_memory touch this assumption — a 'how-exhausted' signal.
    An assumption that has already failed often is an obvious, worn break; a rarely-failed one reaches
    further. Empty failure_memory (the built-in packs) ⇒ 0 for every assumption ⇒ ranking is unchanged."""
    fm = pack.failure_memory or {}
    return sum(1 for k, v in fm.items()
               if str(v.get("status", "")).startswith("DEAD")
               and (name in k or name in str(v.get("assumption", "")) or name in str(v.get("axis", ""))))


def _ranked_breakable(pack, g: AssumptionGraph) -> List[str]:
    """Breakable assumptions, best first: higher axis priority, then RARITY (fewer past failures — the
    less-worn break maximizes novelty), then ones needing no new data, then name. The rarity term only
    re-orders within an equal axis priority and is a no-op when failure_memory is empty, so existing
    behaviour is preserved until a pack actually accumulates failures."""
    dr = g.data_requirements()
    return sorted(g.breakable(),
                  key=lambda n: (-_priority(pack, pack.dimension_of.get(n, "")),
                                 _failure_count(pack, n), 0 if dr.get(n) else 1, n))


def _distinct_axis_breaks(pack, ranked: List[str], k: int) -> List[tuple]:
    """The best break on each DISTINCT axis, up to k — so the proposed exits are genuinely different."""
    out, seen = [], set()
    for n in ranked:
        axis = pack.dimension_of.get(n, "—")
        if axis in seen:
            continue
        seen.add(axis)
        out.append((n, axis))
        if len(out) >= k:
            break
    return out


# ── preflight: the full brief for an assistant ────────────────────────────────────────────────────
def _why(pack, axis: str, data_req: List[str]) -> str:
    base = pack.axes.get(axis, {}).get("verdict", "")
    return base + (f" requires new information: {', '.join(data_req)}." if data_req else "")


def _criticality(token: str, pack, g: AssumptionGraph) -> str:
    """Grade an information need (answering 'data_insufficient is too binary'): CRITICAL if a high-priority
    breakable assumption REQUIRES it to move the ceiling; HELPFUL if a lower-priority break needs it;
    VALIDATION if no break requires it (it refines/confirms rather than unlocks)."""
    requiring = [a for a, toks in g.data_requirements().items() if token in toks]
    if not requiring:
        return "VALIDATION"
    prio = max(pack.axes.get(pack.dimension_of.get(a, ""), {}).get("priority", 1) for a in requiring)
    return "CRITICAL" if prio >= 3 else "HELPFUL"


def _missing_info(prompt: str, pack, g: AssumptionGraph, signals: Optional[Dict]) -> Dict:
    """Decide whether a breakthrough needs NEW information, which kind, and how CRITICAL each is."""
    required = sorted({t for toks in g.data_requirements().values() for t in toks})
    needed = [{"kind": k, "why": pack.info_kinds.get(k, k), "criticality": _criticality(k, pack, g)}
              for k in required]
    if not needed and pack.info_kinds:                      # fall back to the pack's headline info kinds
        needed = [{"kind": k, "why": v, "criticality": _criticality(k, pack, g)}
                  for k, v in list(pack.info_kinds.items())[:2]]
    ceiling = any(p in (prompt or "").lower() for p in _CEILING)
    flagged = bool((signals or {}).get("label_limited") or (signals or {}).get("errors_track_suspect_labels"))
    insufficient = bool(flagged or (ceiling and needed))
    reason = ("the problem is information-limited: a new combination of known mechanisms searches the SAME "
              "information and cannot exceed the box; only NEW information changes the structure."
              if insufficient else
              "current information may suffice for an engineering gain; a paradigm claim still needs the new information below.")
    critical_first = next((d["kind"] for d in needed if d["criticality"] == "CRITICAL"), None)
    return {"data_insufficient": insufficient, "reason": reason, "needed_information": needed,
            "recommended_first": critical_first or (needed[0]["kind"] if needed else None)}


def preflight(prompt: str, pack, signals: Optional[Dict] = None) -> PreflightResult:
    """The single brief: the box to avoid, three breaks on distinct axes, the recommended direction, the
    forbidden families, the death-gate, the anti-collage warning, the missing information, and ready
    instructions to paste in front of an assistant."""
    g = graph_of(pack, prompt)
    dr = g.data_requirements()
    ranked = _ranked_breakable(pack, g)

    three = [{"assumption": n, "dimension": ax, "why": _why(pack, ax, dr.get(n, []))}
             for n, ax in _distinct_axis_breaks(pack, ranked, 3)]
    for n in ranked:                                        # pad to 3 if there are fewer than 3 axes
        if len(three) >= 3:
            break
        if not any(t["assumption"] == n for t in three):
            ax = pack.dimension_of.get(n, "—")
            three.append({"assumption": n, "dimension": ax, "why": _why(pack, ax, dr.get(n, []))})
    recommended = dict(three[0], reason=three[0]["why"]) if three else {}

    dead = [k for k, v in pack.failure_memory.items() if str(v.get("status", "")).startswith("DEAD")]
    anti_collage = ("combining known mechanisms is a COLLAGE, not novelty. Novelty = a broken assumption + a "
                    "world-test where the named family provably fails."
                    + (f" In this domain these were collages and DIED: {', '.join(dead[:6])}." if dead else ""))
    result: PreflightResult = {
        "pack": pack.name,
        "box_name": pack.box_name,
        "hidden_assumptions": [{"name": n, "in_box": g.nodes[n]["in_box"], "dimension": g.nodes[n]["dimension"]}
                               for n in g.nodes],
        "central_assumptions": g.central(3),
        "three_breaks": three,
        "recommended_direction": recommended,
        "must_not_propose": sorted(set(pack.known_families)),
        "death_gate": ("an idea dies if (a) it breaks no axis, or (b) a known family matches it on its own world-test, "
                       "or (c) its controls (shuffle the broken structure) do not collapse, or (d) its claimed new "
                       "output is unfaithful or reducible to a trivial baseline."),
        "anti_collage_warning": anti_collage,
        "missing_information": _missing_info(prompt, pack, g, signals),
    }
    result["instructions"] = emit_assistant_instructions(result)
    return result


# ── gate: no solution may be proposed before it names its broken assumption ─────────────────────────
def no_solution_before_assumption(solution: str, answers: Optional[Dict] = None, pack=None) -> Dict:
    """Gate ANY proposed solution (a layer, an algorithm, a proof technique). With the required fields
    unanswered it is INSIDE_THE_BOX; once a broken assumption and a world-test are declared it becomes
    MUST_BE_AUDITED (eligible for the falsification harness — not yet certified novel)."""
    answers = answers or {}
    family = next((f for f in (pack.known_families if pack else [])
                   if _mentions(solution.lower(), [f.lower()])), "") or "unknown"
    missing = [f for f in REQUIRED_FIELDS if not str(answers.get(f, "")).strip()]
    hard = [f for f in missing if f != "new_data"]          # new_data is recommended, not required
    if hard:
        return {"solution": solution, "status": "INSIDE_THE_BOX", "family": family, "missing": missing,
                "message": f"'{solution}' cannot be proposed until you answer: {', '.join(hard)}. "
                           f"Without a named broken assumption + world-test it is a re-skin of {family}."}
    return {"solution": solution, "status": "MUST_BE_AUDITED", "family": family, "missing": missing,
            "message": f"'{solution}' declares a broken assumption and a world-test → may enter the falsification "
                       f"harness (collision audit vs {family} + controls). Not yet certified novel."}


# ── scoring: graded novelty, with synergy to rescue the live collage ────────────────────────────────
def novelty_score(breaks: List[str], reduces_to: Optional[str] = None, new_output: bool = False,
                  controls_collapse: bool = True, synergy: float = 0.0) -> Dict:
    """Concept-novelty in [0,1]: distinguishes well-phrased from genuinely-different from promising.

    `synergy` (≥0) is the margin by which a RECOMBINATION beats its best single component on the same
    world-test (full − max(parts)). It rescues the legitimate collage: an idea may reduce to a known
    family yet still be novel if the whole strictly beats every part. A dead collage has synergy 0.
    """
    synergistic = bool(reduces_to is not None and synergy and synergy > 0)
    score = 0.0
    score += 0.4 if breaks else 0.0
    # irreducible (0.3) — but ONLY when the idea actually breaks an axis: an idea that breaks nothing is trivially
    # "not reducible to a named family" and must NOT collect the irreducibility credit (else breaking-nothing
    # scores 0.4 and mislabels as LOCAL novelty). Or a live collage whose rescue is PROPORTIONAL to how much the
    # whole beats its best part (synergy in [0,1]) — capped at 0.3 so a maximally synergistic recombination can
    # match an irreducible idea but a barely-synergistic one earns little.
    if breaks and reduces_to is None:
        score += 0.3
    elif synergistic:
        score += round(0.3 * min(1.0, max(0.0, float(synergy))), 3)
    score += 0.2 if new_output else 0.0
    score += 0.1 if controls_collapse else 0.0
    if score < 0.4:
        label = "INSIDE_THE_BOX / collage (well-phrased ≠ different)"
    elif score < 0.7:
        label = ("LOCAL novelty — synergistic recombination (beats its parts)" if synergistic
                 else "LOCAL novelty (a real but bounded difference)")
    else:
        label = "ARCHITECTURAL candidate (different + verifiable + controls collapse)"
    return {"score": round(score, 2), "label": label,
            "components": {"broke_axis": bool(breaks), "not_reducible": reduces_to is None,
                           "synergistic_collage": synergistic, "new_output": new_output,
                           "controls_collapse": controls_collapse}}


# ── divergence: the generator of K breaks in tension ────────────────────────────────────────────────
def branch_on_assumptions(prompt: str, pack, k: int = 3) -> List[Dict]:
    """Produce K candidate breaks in TENSION, one per distinct axis, each tagged with a stance. Disciplined,
    not random: every branch names an assumption and the negation that breaks it; the kernel still
    falsifies them downstream."""
    g = graph_of(pack, prompt)
    dr = g.data_requirements()
    by_name = pack.by_name()
    branches = []
    for i, (n, axis) in enumerate(_distinct_axis_breaks(pack, _ranked_breakable(pack, g), k)):
        a = by_name.get(n)
        negation = negate(a)[1].statement if a else f"negate '{n}'"   # radical negation = the if_false
        branches.append({"stance": _STANCES[i % len(_STANCES)], "assumption": n, "axis": axis,
                         "negation": negation, "needs": dr.get(n, []),
                         "axis_verdict": pack.axes.get(axis, {}).get("verdict", "")})
    return branches
