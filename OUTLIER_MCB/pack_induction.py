"""pack_induction — INDUCE a DomainPack instead of hand-writing one (improvement #1).

The engine's reach has been bounded by what a human pack made thinkable. This module lets the engine build
the conceptual space itself: it reads the problem (and, when given, the repo identifiers, the data columns,
the real prior art, and past failures) and proposes falsifiable assumptions, breakable axes, known families,
info-kinds — a PROVISIONAL pack the falsification spine then attacks exactly as it would a written one.

Honest by construction:
  • every induced assumption carries a CONCRETE falsifier (validate_inferred_pack REJECTS one without it);
  • the assumptions come from domain-GENERAL schemas instantiated on the problem's OWN words — never from a
    hard-coded per-domain table (the agnosticism guard stays green: no pack token lives here);
  • the pack is marked provisional/inferred; known_families are only as real as the prior art actually found.

It does not fabricate a domain — it instantiates first-principles breakable axes (representation, objective,
independence, regime, agency, granularity) on the targets it can actually extract, and pairs each with the
construction that would kill it.
"""
from __future__ import annotations
from dataclasses import replace
from typing import Dict, List, Optional

from .core import Assumption
from .pack import DomainPack

_STOP = {"the", "a", "an", "of", "to", "is", "are", "for", "with", "and", "or", "in", "on", "by", "as", "that",
         "this", "via", "new", "novel", "design", "make", "build", "system", "method", "approach", "better",
         "using", "use", "from", "into", "than", "more", "less", "best", "good", "bad", "how", "what", "why",
         "invent", "create", "find", "discover", "propose", "without", "instead", "based", "given", "between"}


def _tokens(text: str) -> List[str]:
    return [w for w in "".join(c if c.isalnum() else " " for c in (text or "").lower()).split()
            if len(w) > 3 and w not in _STOP]


def _targets(text: str, k: int = 4) -> List[str]:
    """The most salient content words (the things the domain is ABOUT), most-frequent first, order-stable."""
    counts: Dict[str, int] = {}
    first_at: Dict[str, int] = {}
    for i, w in enumerate(_tokens(text)):
        if w not in counts:
            first_at[w] = i
        counts[w] = counts.get(w, 0) + 1
    order = sorted(counts, key=lambda w: (-counts[w], first_at[w]))
    return order[:k] or ["the_target"]


# domain-GENERAL assumption schemas. Each instantiates on a target (or target pair) into a falsifiable
# assumption with a CONCRETE falsifier. These are first-principles breakable axes, not domain knowledge.
_UNARY_SCHEMAS = [
    {"axis": "REPRESENTATION", "suffix": "is_surface_proxy",
     "desc": "the solution represents «{t}» by its obvious surface proxy, not the underlying quantity",
     "why": "the proxy is the first thing measured and the cheapest to compute",
     "if_false": "the proxy and the true quantity can diverge, and the standard solution silently fails there",
     "fals": "construct an instance where the surface proxy of «{t}» diverges from the true quantity and show the standard solution degrades"},
    {"axis": "OBJECTIVE", "suffix": "is_one_metric",
     "desc": "success on «{t}» is captured by a single obvious metric",
     "why": "one number is easy to optimize and to report",
     "if_false": "optimizing that one metric can degrade the real goal (a Goodhart effect)",
     "fals": "exhibit a case where maximizing the single metric for «{t}» makes the real outcome strictly worse"},
    {"axis": "REGIME", "suffix": "regime_is_static",
     "desc": "the regime governing «{t}» is static / stationary across time and scale",
     "why": "a fixed regime makes the problem a one-shot optimization",
     "if_false": "a shift over time or scale changes the right answer and the box does not adapt",
     "fals": "show a temporal or scale shift in «{t}» under which the standard solution's choice becomes wrong"},
    {"axis": "AGENCY", "suffix": "actors_nonstrategic",
     "desc": "the actors interacting with «{t}» are non-strategic — they do not game the rule",
     "why": "assuming passive actors keeps the model simple and analyzable",
     "if_false": "a strategic actor games the rule and the intended outcome collapses",
     "fals": "introduce a strategic actor that games the «{t}» rule and show the intended outcome collapses"},
    {"axis": "GRANULARITY", "suffix": "one_global_scale",
     "desc": "«{t}» is handled at one global granularity / one scale for everyone",
     "why": "a single global setting is simplest to implement and tune",
     "if_false": "different sub-populations need different scales and one global choice fails some of them",
     "fals": "find two sub-populations of «{t}» that need different scales, where a single global choice fails one"},
]
_BINARY_SCHEMA = {
    "axis": "INDEPENDENCE", "suffix": "independent_of",
    "desc": "«{t}» and «{u}» are treated as independent",
    "why": "independence factorizes the problem and is the default modeling choice",
    "if_false": "a coupling between «{t}» and «{u}» exists that the standard solution ignores",
    "fals": "exhibit a coupling between «{t}» and «{u}» and a concrete instance the standard solution gets wrong because it ignores it",
}


def _slug(s: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in s.lower()).strip("_")


def _assumption_from_schema(schema: Dict, t: str, u: str = "") -> Assumption:
    fmt = lambda s: s.replace("{t}", t).replace("{u}", u)
    suffix = schema["suffix"] + (f"_{_slug(u)}" if u else "")
    return Assumption(name=f"{_slug(t)}_{suffix}", description=fmt(schema["desc"]),
                      why_obvious=fmt(schema["why"]), if_false=fmt(schema["if_false"]), falsifier=fmt(schema["fals"]))


def infer_domain_pack(problem: str, repo: Optional[Dict] = None, data: Optional[Dict] = None,
                      provider=None, max_assumptions: int = 6) -> DomainPack:
    """Induce a PROVISIONAL DomainPack from real evidence. `repo` may be a repo-world model (see #2) whose
    identifiers add targets; `data` may be {"columns": [...]} whose columns add targets; `provider` is a
    PriorArtProvider whose real matches seed known_families. Every assumption gets a concrete falsifier."""
    text = problem
    if isinstance(repo, dict):
        text += " " + " ".join(map(str, repo.get("identifiers", []) or repo.get("modules", []) or []))
    if isinstance(data, dict):
        text += " " + " ".join(map(str, data.get("columns", []) or []))
    targets = _targets(text)

    assumptions: List[Assumption] = []
    dimension_of: Dict[str, str] = {}
    axes: Dict[str, Dict] = {}

    def _add(a: Assumption, axis: str):
        if a.name in {x.name for x in assumptions}:
            return
        assumptions.append(a)
        dimension_of[a.name] = axis
        axes.setdefault(axis, {"priority": len(axes) + 1, "verdict": f"breaking the {axis} axis changes the answer"})

    t0 = targets[0]
    for sch in _UNARY_SCHEMAS:
        if len(assumptions) >= max_assumptions:
            break
        _add(_assumption_from_schema(sch, t0), sch["axis"])
    if len(targets) >= 2 and len(assumptions) < max_assumptions:
        _add(_assumption_from_schema(_BINARY_SCHEMA, targets[0], targets[1]), _BINARY_SCHEMA["axis"])
    # a second target broadens the space (a different REPRESENTATION lever) when room remains
    if len(targets) >= 2 and len(assumptions) < max_assumptions:
        _add(_assumption_from_schema(_UNARY_SCHEMAS[0], targets[1]), _UNARY_SCHEMAS[0]["axis"])

    known_families: List[str] = []
    if provider is not None:
        try:
            res = provider.research(problem) or {}
            for m in (res.get("matches") or res.get("sources") or [])[:6]:
                fam = _slug(str(m.get("title", "")))[:40]
                if fam and fam not in known_families:
                    known_families.append(fam)
        except Exception:
            known_families = []

    info_kinds = {f"counterexample_for_{_slug(t0)}": f"an instance that separates the proxy of «{t0}» from its truth",
                  "coupling_evidence": "data showing a coupling the box assumes away",
                  "out_of_regime_sample": "a sample from a shifted time/scale regime"}

    box_assumptions = set(list(dimension_of)[:3])
    return DomainPack(
        name=f"inferred:{_slug(t0)}", keywords=targets,
        box_name=f"the most-probable solution for «{problem.strip()[:60]}» from training memory",
        assumptions=assumptions, dimension_of=dimension_of, box_assumptions=box_assumptions,
        axes=axes, known_families=known_families, info_kinds=info_kinds,
        failure_memory={})


def expand_pack_with_discovered_assumptions(pack: DomainPack, evidence: Dict) -> DomainPack:
    """Return a COPY of `pack` extended with assumptions discovered from evidence. `evidence` may carry:
      "assumptions": [{name, description, why_obvious, if_false, falsifier, axis}]  (each MUST have a falsifier)
      "known_families": [...]   "info_kinds": {k: why}   "anomalies": ["..."]   "failures": {id: {...}}
    An anomaly becomes a falsifiable assumption ('the standard view does not explain X'); a failure is recorded
    so it is never reincarnated. Assumptions lacking a falsifier are dropped (honesty over completeness)."""
    assumptions = list(pack.assumptions)
    names = {a.name for a in assumptions}
    dim = dict(pack.dimension_of)
    axes = dict(pack.axes)
    fams = list(pack.known_families)
    info = dict(pack.info_kinds)
    fails = dict(pack.failure_memory)

    def _add(a: Assumption, axis: str):
        if a.name in names or not (a.falsifier and len(a.falsifier.split()) >= 4):
            return
        assumptions.append(a); names.add(a.name)
        if axis:
            dim[a.name] = axis
            axes.setdefault(axis, {"priority": len(axes) + 1, "verdict": f"breaking the {axis} axis changes the answer"})

    for spec in evidence.get("assumptions", []) or []:
        _add(Assumption(name=spec.get("name", ""), description=spec.get("description", ""),
                        why_obvious=spec.get("why_obvious", ""), if_false=spec.get("if_false", ""),
                        assumed_by=spec.get("assumed_by", []), falsifier=spec.get("falsifier", "")),
             spec.get("axis", ""))
    for i, anomaly in enumerate(evidence.get("anomalies", []) or []):
        _add(Assumption(name=f"unexplained_anomaly_{i}_{_slug(str(anomaly))[:24]}",
                        description=f"the standard view does not explain: {anomaly}",
                        why_obvious="the anomaly is treated as noise or an edge case",
                        if_false="the anomaly is a signal the box's assumptions cannot produce",
                        falsifier=f"reproduce «{anomaly}» under controlled conditions and show the standard model cannot generate it"),
             "ANOMALY")
    for fam in evidence.get("known_families", []) or []:
        if fam not in fams:
            fams.append(fam)
    info.update(evidence.get("info_kinds", {}) or {})
    fails.update(evidence.get("failures", {}) or {})
    return replace(pack, assumptions=assumptions, dimension_of=dim, axes=axes, known_families=fams,
                   info_kinds=info, failure_memory=fails)


def validate_inferred_pack(pack: DomainPack, min_assumptions: int = 3, min_falsifier_words: int = 4) -> List[str]:
    """Stricter than DomainPack.validate(): an INDUCED pack is only usable if it has enough assumptions and
    EVERY assumption carries a concrete falsifier. Returns [] when the pack is fit to attack with."""
    issues = list(pack.validate())
    if len(pack.assumptions) < min_assumptions:
        issues.append(f"inferred pack has {len(pack.assumptions)} assumptions (< {min_assumptions} required)")
    for a in pack.assumptions:
        if not (a.falsifier and len(a.falsifier.split()) >= min_falsifier_words):
            issues.append(f"assumption '{a.name}' has no concrete falsifier (an unfalsifiable assumption is not usable)")
    return issues


def _divergence(pack: DomainPack, problem: str) -> int:
    """A divergence proxy: how many DISTINCT breakable axes the pack's generated candidates actually cover.
    More distinct axes ⇒ the engine can leave the average answer along more independent directions."""
    from .generators import generate_candidates
    axes = set()
    try:
        for c in generate_candidates(pack, problem):
            for a in (getattr(c, "assumptions", []) or []):
                ax = pack.dimension_of.get(a)
                if ax:
                    axes.add(ax)
    except Exception:
        return 0
    return len(axes)


def pack_induction_ablation(problem: str, provider=None) -> Dict:
    """Ablation for #1: does an INDUCED pack beat the generic pack (and a decorative single-axis pack) on
    divergence? Returns the three divergence scores and whether induction earned its place."""
    from .pack import get_pack
    inferred = infer_domain_pack(problem, provider=provider)
    generic = get_pack("generic")
    # decorative control: one assumption, one axis, no falsifier — structurally a pack, creatively inert
    decorative = DomainPack(name="decorative", assumptions=[Assumption("flat", "a flat restatement", "", "", falsifier="")],
                            dimension_of={"flat": "FLAT"}, axes={"FLAT": {"priority": 1, "verdict": "—"}})
    d_inf, d_gen, d_dec = _divergence(inferred, problem), _divergence(generic, problem), _divergence(decorative, problem)
    return {"inferred_divergence": d_inf, "generic_divergence": d_gen, "decorative_divergence": d_dec,
            "induction_beats_generic": d_inf > d_gen, "induction_beats_decorative": d_inf > d_dec,
            "inferred_assumptions": len(inferred.assumptions), "inferred_axes": len(inferred.axes)}
