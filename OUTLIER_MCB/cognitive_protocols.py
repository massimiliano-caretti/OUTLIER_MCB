"""cognitive_protocols — explicit human-creativity protocols, turned into falsifiable candidate generators.

This module adds the part that was still too implicit: psychological creativity techniques are not used as
decorative prompt words, but as structured operators that generate candidates with a declared cognitive
move and a falsifier. Implemented protocols:

  * SCAMPER: substitute, combine, adapt, modify, put-to-other-use, eliminate, reverse.
  * Geneplore: generate preinventive forms, then explore/interpret them under constraints.
  * Functional-fixedness breaking: remove or repurpose the known function/family.
  * Remote association: force a bridge among distant cues/domains.

Every output remains only a hypothesis. It receives zero proof credit until prior-art and objective
evaluators settle it.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .generators import Candidate, breakable, conceptual_blend, what_would_have_to_be_true


@dataclass
class CognitiveMove:
    protocol: str
    move: str
    candidate: Candidate
    cognitive_effect: str = ""
    rationale: str = ""

    def markdown(self) -> str:
        return (f"- **{self.protocol}/{self.move}:** {self.candidate.name}\n"
                f"  - effect: {self.cognitive_effect}\n"
                f"  - rationale: {self.rationale}\n"
                f"  - falsifier: {self.candidate.discipline}")


@dataclass
class CognitiveProtocolResult:
    problem: str
    moves: List[CognitiveMove] = field(default_factory=list)
    scores: Dict[str, float] = field(default_factory=dict)

    @property
    def candidates(self) -> List[Candidate]:
        return [m.candidate for m in self.moves]

    def markdown(self) -> str:
        L = [f"## cognitive protocols — «{self.problem}»",
             "- scores: " + " · ".join(f"{k}={v}" for k, v in self.scores.items())]
        L += [m.markdown() for m in self.moves]
        return "\n".join(L)


def _first_assumption(pack):
    bs = breakable(pack)
    return bs[0] if bs else (pack.assumptions[0] if pack.assumptions else None)


def _axis(pack, assumption) -> str:
    return pack.dimension_of.get(getattr(assumption, "name", ""), "")


def _candidate(name: str, operator: str, axis: str, assumption: str, negation: str, discipline: str,
               needs: Optional[List[str]] = None) -> Candidate:
    return Candidate(name=name[:72], operator=operator, breaks=[axis] if axis else [],
                     assumptions=[assumption] if assumption else [], negation=negation,
                     needs=needs or [], discipline=discipline)


def scamper(problem: str, pack) -> List[CognitiveMove]:
    """SCAMPER as seven concrete candidate generators, not a vague checklist."""
    a = _first_assumption(pack)
    if a is None:
        return []
    axis, an = _axis(pack, a), a.name
    info = next(iter(pack.info_kinds), "a new observable")
    family = pack.known_families[0] if pack.known_families else "the default family"
    specs = [
        ("substitute", f"replace the box's proxy with «{info}»", [info],
         "the new observable must predict a held-out case the old proxy misses"),
        ("combine", f"combine the broken assumption «{an}» with a distant mechanism instead of using {family}", [],
         "the combined mechanism must beat each component alone"),
        ("adapt", f"adapt a mechanism from a domain where «{a.if_false}» is normal", [],
         "the transfer must survive the target domain's world-test"),
        ("modify", f"exaggerate «{an}» until the default scale breaks", [],
         "show a crossover where the box works below scale and fails above it"),
        ("put_to_other_use", f"use the failure signal of {family} as the new control variable", [],
         "the former failure signal must become predictive, not merely descriptive"),
        ("eliminate", f"remove {family}'s central operation and solve by the residual structure", [],
         "if the removed operation is restored and performance is unchanged, the idea was decorative"),
        ("reverse", f"reverse the causal/order direction assumed by «{an}»", [],
         "a counterworld with the original direction must fail this candidate"),
    ]
    out = []
    for move, neg, needs, falsifier in specs:
        c = _candidate(f"SCAMPER:{move}:{an}", f"scamper_{move}", axis, an,
                       f"{problem}: {neg}.", falsifier, needs=needs)
        out.append(CognitiveMove("SCAMPER", move, c,
                                 cognitive_effect="forces a different operation on the same hidden assumption",
                                 rationale=f"SCAMPER move '{move}' prevents a same-mechanism paraphrase."))
    return out


def functional_fixedness_breaker(problem: str, pack) -> List[CognitiveMove]:
    """Break the default use/function of known families, inspired by functional fixedness experiments."""
    a = _first_assumption(pack)
    if a is None:
        return []
    axis, an = _axis(pack, a), a.name
    fams = pack.known_families[:3] or ["the standard solution"]
    out = []
    for fam in fams:
        c = _candidate(f"fixedness_break:{fam}", "functional_fixedness_break", axis, an,
                       f"{problem}: forbid «{fam}» from doing its normal job; repurpose its failure mode as the signal.",
                       "must beat the baseline while the normal use of the family is explicitly disabled",
                       needs=["ablation_without_standard_function"])
        out.append(CognitiveMove("Fixedness", "repurpose_function", c,
                                 cognitive_effect="blocks the obvious affordance so a nonstandard use can emerge",
                                 rationale=f"Known family «{fam}» is treated as a source of fixation, not a solution."))
    return out


def remote_association(problem: str, pack, cues: Optional[List[str]] = None) -> List[CognitiveMove]:
    """Force a Mednick-style remote association among distant cues/domains and the target problem."""
    cues = list(cues or ["ecology:feedback equilibrium", "economics:price signal", "biology:immune memory"])
    a = _first_assumption(pack)
    if a is None:
        return []
    axis, an = _axis(pack, a), a.name
    out = []
    for i in range(0, len(cues), 3):
        triad = cues[i:i + 3]
        if len(triad) < 2:
            continue
        bridge = " + ".join(triad)
        c = _candidate(f"remote_association:{i//3}", "remote_association", axis, an,
                       f"{problem}: invent the common mechanism linking {bridge}; transfer that mechanism to break «{an}».",
                       "the bridge is valid only if it predicts a test case neither cue/domain predicts alone",
                       needs=["distant_mechanism_evidence", "bridge_negative_control"])
        out.append(CognitiveMove("RemoteAssociation", "triadic_bridge", c,
                                 cognitive_effect="increases associative distance beyond near-domain analogies",
                                 rationale=f"Forced bridge among remote cues: {bridge}."))
    return out


def geneplore(problem: str, pack) -> List[CognitiveMove]:
    """Geneplore: generate preinventive forms, then explore them as constrained candidate interpretations."""
    from .lateral import provocation, random_entry
    forms = [provocation(pack), random_entry(pack), what_would_have_to_be_true(pack, problem)]
    try:
        from .pack import list_packs, get_pack
        foreign = next((get_pack(n) for n in list_packs() if n not in (pack.name, "generic")), None)
        forms.append(conceptual_blend(pack, foreign) if foreign else None)
    except Exception:
        pass
    out = []
    for idx, c in enumerate(f for f in forms if f is not None):
        c.name = f"geneplore:{idx}:{c.name}"[:72]
        c.operator = "geneplore_" + c.operator
        c.discipline = (c.discipline + " | GENEPLORE EXPLORATION: reinterpret this preinventive form under "
                        "a concrete constraint; discard it if no falsifiable mechanism emerges.").strip()
        out.append(CognitiveMove("Geneplore", "preinventive_form", c,
                                 cognitive_effect="separates generation of odd forms from later disciplined interpretation",
                                 rationale="A strange form is allowed only as a stepping stone toward a tested mechanism."))
    return out


def _dedupe(moves: List[CognitiveMove]) -> List[CognitiveMove]:
    seen, out = set(), []
    for m in moves:
        key = (m.candidate.operator, " ".join(m.candidate.assumptions), m.candidate.negation.lower())
        if key not in seen:
            seen.add(key)
            out.append(m)
    return out


def cognitive_extremes(problem: str, pack=None, cues: Optional[List[str]] = None) -> CognitiveProtocolResult:
    """Run the full deterministic cognitive protocol battery and score its divergent pressure."""
    if pack is None:
        from .pack import select_pack
        pack, _ = select_pack(problem)
    moves = _dedupe(scamper(problem, pack) + functional_fixedness_breaker(problem, pack)
                    + remote_association(problem, pack, cues=cues) + geneplore(problem, pack))
    protocols = {m.protocol for m in moves}
    axes = {b for m in moves for b in m.candidate.breaks}
    assumptions = {a for m in moves for a in m.candidate.assumptions}
    high_transform = sum(1 for m in moves if m.protocol in ("RemoteAssociation", "Geneplore", "Fixedness"))
    falsifiable = sum(1 for m in moves if m.candidate.discipline)
    scores = {
        "fluency": round(min(1.0, len(moves) / 12.0), 3),
        "protocol_flexibility": round(min(1.0, len(protocols) / 4.0), 3),
        "axis_coverage": round(min(1.0, len(axes) / max(1, len(getattr(pack, "axes", {}) or {"x": 1}))), 3),
        "assumption_coverage": round(min(1.0, len(assumptions) / max(1, len(breakable(pack)) or 1)), 3),
        "transformational_pressure": round(high_transform / max(1, len(moves)), 3),
        "falsifiability": round(falsifiable / max(1, len(moves)), 3),
    }
    return CognitiveProtocolResult(problem=problem, moves=moves, scores=scores)

