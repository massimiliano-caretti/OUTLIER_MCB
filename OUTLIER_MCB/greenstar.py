"""greenstar — creativity in the zone with NO examples: pure structure, not an average of cases.

Every other module operates on a DomainPack — assumptions someone curated from known examples. But the
real green-star zone is where there is NO pack and nothing to elicit: the idea must come from the
STRUCTURE of the problem, not from retrieval. Applying the engine to that gap flagged even "ask the
human for examples" as INSIDE_THE_BOX, and surfaced four moves, all built here:

  SUBSTRATE   generate structure from first principles when there are no examples (`synthesize_assumptions`)
  SOURCE      instantiate universal hidden-assumption templates over the problem, never retrieve them
  META        discover a NEW axis by pairing structural primitives — invent the dimension itself (`novel_axis`)
  REGIME      measure EXTRAPOLATION beyond ALL packs (the convex hull of examples), not distance within one

`green_star(prompt)` is the entrypoint: with zero examples it bootstraps a provisional structure, runs the
generators on it, and ranks by extrapolation. Everything it returns is explicitly UNFALSIFIED structure —
a world must be BUILT to test it, never assumed.

Collaborators: core.Assumption, pack.DomainPack, generators.generate_candidates, kernel (downstream falsify).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List

from .core import Assumption
from .pack import DomainPack, REGISTRY, _ensure_loaded

# The universal ASPECTS every problem has — the substrate to generate from (not domain examples).
PRIMITIVES: Dict[str, str] = {
    "INPUT": "what is given to the solver",
    "OUTPUT": "what the solver must produce",
    "OBJECTIVE": "what is being optimized",
    "OBJECT": "what the thing fundamentally is",
    "CONSTRAINT": "what bounds the feasible solutions",
    "MEASURE": "how success is judged",
    "TIME": "the temporal structure of the task",
    "AGENT": "who or what acts",
    "REPRESENTATION": "how the problem is encoded",
    "RESOURCE": "what the solution spends",
}

# The universal FORMS a hidden assumption takes: (key, default, negation, structural falsifier).
# Instantiating these over the primitives GENERATES assumptions no registry ever stated.
TEMPLATES = [
    ("fixed", "{a} is fixed/given and not ours to choose", "{a} can be CHOSEN or designed",
     "two instances identical except in {a} that the default treats the same"),
    ("uniform", "{a} is uniform across the problem", "{a} is heterogeneous and its structure decides",
     "a case where the distribution of {a}, not its average, determines the outcome"),
    ("independent", "{a} is independent of everything else", "{a} is coupled to another aspect",
     "a case where the interaction through {a} carries the signal"),
    ("observable", "{a} is fully observable", "{a} is latent and must be inferred",
     "a case where {a} is hidden yet decisive"),
    ("static", "{a} does not change during the task", "{a} evolves and the dynamics matter",
     "a case where {a} shifts over time and the static view fails"),
    ("settled", "the current {a} is the right one, never to be questioned", "a different {a} reframes the problem",
     "a re-choice of {a} that dissolves the hard part"),
]


def _offset(prompt: str, n: int) -> int:
    """A deterministic, prompt-dependent index (no randomness) so different prompts explore differently."""
    return (sum(ord(c) for c in (prompt or "x")) % n) if n else 0


def synthesize_assumptions(prompt: str = "", n_axes: int = 4, templates_per_axis: int = 1) -> List[Assumption]:
    """Generate first-principles hidden assumptions for ANY prompt, with zero examples: cross the
    structural primitives with the universal templates. This is generation, not retrieval. With
    templates_per_axis>1 it explores several framings per axis (more than a single deterministic offset)."""
    prims = list(PRIMITIVES)
    start = _offset(prompt, len(prims))
    chosen = [prims[(start + i) % len(prims)] for i in range(min(n_axes, len(prims)))]
    out: List[Assumption] = []
    for i, prim in enumerate(chosen):
        aspect = PRIMITIVES[prim]
        for t in range(max(1, templates_per_axis)):
            key, default, negation, falsifier = TEMPLATES[(start + i + t) % len(TEMPLATES)]
            out.append(Assumption(
                name=f"{prim.lower()}_is_{key}",
                description=default.format(a=aspect),
                why_obvious="it is the unexamined default structure of the problem, true of the average case.",
                if_false=negation.format(a=aspect),
                assumed_by=["the unexamined default"],
                falsifier=falsifier.format(a=aspect),
            ))
    # dedup by name (a primitive may hit the same template twice)
    seen, uniq = set(), []
    for a in out:
        if a.name not in seen:
            seen.add(a.name); uniq.append(a)
    return uniq


def synthesize_pack(prompt: str = "", n_axes: int = 4, templates_per_axis: int = 1) -> DomainPack:
    """Bootstrap a PROVISIONAL pack from first principles — no examples, no known families. In the
    green-star zone there is nothing to forbid as collage, because nothing is known yet."""
    assumptions = synthesize_assumptions(prompt, n_axes, templates_per_axis)
    dim = {a.name: a.name.split("_is_")[0].upper() for a in assumptions}
    axes = {axis: {"priority": 3 - i // 2, "verdict": f"first-principles axis '{axis}' — UNFALSIFIED structure, "
                                                      f"build a world to test it; do not assume it."}
            for i, axis in enumerate(dict.fromkeys(dim.values()))}
    return DomainPack(
        name="greenstar", keywords=[],
        box_name="the unexamined default structure of the problem (no examples — pure first principles)",
        assumptions=assumptions, relations=[], dimension_of=dim, box_assumptions=set(list(dim)[:2]),
        axes=axes, known_families=[],            # NO examples: the convex hull is empty here
        info_kinds={"a_world_built_for_it": "a constructed world (not a dataset) where the broken structure decides."},
        failure_memory={},
    )


def novel_axis(prompt: str = "") -> Dict:
    """META-creativity: pair two structural primitives into a NEW dimension of variation that no pack
    declares — invent the axis itself, then offer the assumption that breaks it."""
    prims = list(PRIMITIVES)
    i = _offset(prompt, len(prims))
    j = (i + 3) % len(prims)
    p1, p2 = prims[i], prims[j]
    axis = f"{p1}×{p2}"
    return {"axis": axis,
            "definition": f"how {PRIMITIVES[p1]} behaves as {PRIMITIVES[p2]} varies — a coupling no standard domain treats as a dimension",
            "assumption_broken": f"that {p1.lower()} and {p2.lower()} are separable",
            "falsifier": f"a case where only the joint {p1}×{p2} structure (neither alone) determines the outcome"}


def global_families() -> set:
    """The known families across ALL registered packs — the convex hull of examples a green-star idea
    must escape (not merely its own box)."""
    _ensure_loaded()
    fams: set = set()
    for name, p in REGISTRY.items():
        if name == "greenstar":
            continue
        fams |= {f.lower() for f in p.known_families}
    return fams


def _known_axes() -> set:
    _ensure_loaded()
    return {ax for name, p in REGISTRY.items() if name != "greenstar" for ax in p.axes}


def extrapolation(candidate, prompt: str = "") -> float:
    """How far BEYOND ALL examples a candidate reaches, in [0,1]. 1.0 = it breaks a dimension no pack
    declares AND references no known family — genuinely outside the global convex hull (green-star).
    Distinguishes interpolation (novel within a domain) from extrapolation (novel beyond every domain)."""
    text = (candidate.negation or "").lower()
    novel_axis = bool(candidate.breaks) and all(ax not in _known_axes() for ax in candidate.breaks)
    fams = global_families()
    no_family = not any(f in text or f.replace("_", " ") in text for f in fams)
    return round(0.6 * novel_axis + 0.4 * no_family, 2)


UNFALSIFIED_HYPOTHESIS = "UNFALSIFIED_HYPOTHESIS"   # the only status green-star may claim — never 'novel'


@dataclass
class GreenStarExploration:
    prompt: str
    novel_axis: Dict = field(default_factory=dict)
    frontier: List[Dict] = field(default_factory=list)   # [{extrapolation, candidate, status}]
    confidence: float = 0.0                              # mean extrapolation × diversity — how far beyond the hull
    confidence_label: str = "LOW"                        # LOW | MEDIUM | HIGH — it ADMITS when it is low
    diversity: float = 0.0                               # distinct structural primitives used
    note: str = ""
    def best(self):
        return self.frontier[0] if self.frontier else None
    def markdown(self) -> str:
        lines = [f"## Green-star exploration — «{self.prompt}»  (NO examples; first-principles HYPOTHESES)",
                 f"- **status:** every item below is an {UNFALSIFIED_HYPOTHESIS} — structure, not a proven idea.",
                 f"- **confidence: {self.confidence_label} ({self.confidence})** · diversity {self.diversity}"
                 + ("  ⚠ LOW: this is closer to the known hull than it claims — treat as a prompt, not a discovery."
                    if self.confidence_label == "LOW" else ""),
                 f"- **invented dimension:** {self.novel_axis.get('axis')} — {self.novel_axis.get('definition')}",
                 "", "### Frontier (most EXTRAPOLATED first)"]
        for i, f in enumerate(self.frontier, 1):
            c = f["candidate"]
            lines.append(f"{i}. **[{c.operator}] {c.name}**  (extrapolation {f['extrapolation']}, {f['status']})")
            lines.append(f"   - assume false: {c.negation[:150]}")
            lines.append(f"   - build a world where: {c.discipline[:120]}")
        if self.note:
            lines.append("\n" + self.note)
        return "\n".join(lines)


def green_star(prompt: str, n_axes: int = 5, top: int = 6, templates_per_axis: int = 2) -> GreenStarExploration:
    """The no-examples entrypoint. Bootstrap a first-principles structure (several framings per axis, not a
    single offset), generate over it, and rank by EXTRAPOLATION beyond every known example. Honest by
    construction: every item is an UNFALSIFIED_HYPOTHESIS and the confidence ADMITS when it is low."""
    from .generators import generate_candidates
    pack = synthesize_pack(prompt, n_axes, templates_per_axis)
    pool = generate_candidates(pack, prompt)
    scored = sorted(({"extrapolation": extrapolation(c, prompt), "candidate": c,
                      "status": UNFALSIFIED_HYPOTHESIS} for c in pool),
                    key=lambda x: -x["extrapolation"])[:top]
    mean_extrap = round(sum(f["extrapolation"] for f in scored) / len(scored), 2) if scored else 0.0
    diversity = round(len({c.name.split("_is_")[0] for c in (f["candidate"] for f in scored)}) /
                      max(1, len(PRIMITIVES)), 2)
    confidence = round(mean_extrap * (0.5 + 0.5 * diversity), 2)
    label = "HIGH" if confidence >= 0.6 else "MEDIUM" if confidence >= 0.35 else "LOW"
    note = ("These are FIRST-PRINCIPLES hypotheses, not retrieved ideas — there were no examples to average. "
            "Each is UNFALSIFIED: pick one, BUILD the world its falsifier describes, and let that world decide. "
            "Confidence is the engine's own honest estimate of how far it actually left the hull — when LOW, it "
            "is closer to the average than the word 'green-star' suggests.")
    return GreenStarExploration(prompt=prompt, novel_axis=novel_axis(prompt), frontier=scored,
                                confidence=confidence, confidence_label=label, diversity=diversity, note=note)
