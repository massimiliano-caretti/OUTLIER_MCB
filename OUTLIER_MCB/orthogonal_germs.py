"""orthogonal_germs -- grow a new latent basis, then keep it only if the world pays for it.

This is the stronger version of "leave the box": not just searching an unexplored point inside a fixed
conceptual space, but proposing a new basis direction that is nearly orthogonal to the known box. The gate is
deliberately anti-autoreferential: a germ earns credit only through an external reducibility test with a
structure-destroying control. Novel wording alone is not enough.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence

from .generators import Candidate


def _tokens(text: str) -> set:
    import re
    return {w for w in re.findall(r"[a-zA-Z_]\w+", str(text).lower()) if len(w) > 2}


def _jaccard(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    return len(ta & tb) / len(ta | tb) if (ta or tb) else 0.0


def known_box_surface(pack) -> List[str]:
    """Textual surface of the current box: assumptions, axes, known families and the box name."""
    out = [getattr(pack, "box_name", "")]
    out += list(getattr(pack, "known_families", []) or [])
    out += list(getattr(pack, "axes", {}).keys())
    for a in getattr(pack, "assumptions", []) or []:
        out += [getattr(a, "name", ""), getattr(a, "description", ""), getattr(a, "why_obvious", "")]
    return [x for x in out if x]


def lexical_orthogonality(text: str, pack, extra_known: Optional[Sequence[str]] = None) -> float:
    """A deterministic in-box proxy for distance from the known basis.

    It is intentionally modest: lexical orthogonality can only say "this does not look like the current box".
    The external reducibility gate below decides whether the direction is useful or just noise.
    """
    known = known_box_surface(pack) + list(extra_known or [])
    if not known:
        return 1.0
    max_sim = max(_jaccard(text, k) for k in known)
    return round(max(0.0, min(1.0, 1.0 - max_sim)), 3)


# Lexical signals that a request is about *how the problem is represented* (the axis the germ breaks).
_REP_AXIS_KEYS = ("represent", "encod", "measure", "basis", "coordinate", "embedding",
                  "manifold", "feature", "latent", "metric")


def orthogonal_germ_relevant(pack, prompt: str = "") -> bool:
    """Ask the library whether a new-basis (orthogonal germ) move is on-topic for this request.

    The germ breaks the REPRESENTATION axis, so it is relevant exactly when the request is about *how the
    problem is represented*. We do not hand-code that decision: we reuse judge's own assumption ranking to
    ask the pack which axis the prompt is about, and inject the germ only when that axis is representational
    (or the prompt/box explicitly names a representation move). This keeps the capability reachable on the
    requests that need it, without firing on every unrelated one.
    """
    low = str(prompt).lower()
    if any(k in low for k in _REP_AXIS_KEYS):
        return True
    # a pack whose very box is about representation always wants the move
    if any(k in str(getattr(pack, "box_name", "")).lower() for k in _REP_AXIS_KEYS):
        return True
    if not low.strip():
        return False
    from .judge import _rank_assumptions
    ranked = _rank_assumptions(prompt, pack)
    if ranked and ranked[0][1] > 0:                       # only trust a real (non-zero) lexical overlap
        top = ranked[0][0]
        axis = (getattr(pack, "dimension_of", {}) or {}).get(top, "")
        return any(k in f"{top} {axis}".lower() for k in _REP_AXIS_KEYS)
    return False


def _representation_assumption(pack):
    """Find the representation axis if the pack has one; otherwise use the highest-priority breakable axis."""
    assumptions = list(getattr(pack, "assumptions", []) or [])
    dim = getattr(pack, "dimension_of", {}) or {}
    for a in assumptions:
        axis = dim.get(a.name, "")
        blob = f"{a.name} {axis} {getattr(a, 'description', '')}".lower()
        if "representation" in blob or "encoding" in blob or "measure" in blob:
            return a, axis
    breakable = [(a, dim.get(a.name, "")) for a in assumptions if dim.get(a.name)]
    if not breakable:
        return None, ""
    return max(breakable, key=lambda x: getattr(pack, "axes", {}).get(x[1], {}).get("priority", 0))


def propose_orthogonal_germ(pack, prompt: str = "", extra_known: Optional[Sequence[str]] = None) -> Candidate:
    """Return a Candidate that makes the latent basis itself the object of invention.

    The candidate is still only a proposal. It must later pass `evaluate_orthogonal_germ` or an equivalent
    external world-test before any strong claim is allowed.
    """
    asm, axis = _representation_assumption(pack)
    if asm is None:
        axis = "REPRESENTATION"
        assumption = "basis_is_fixed"
        base = "the current representation is fixed"
    else:
        assumption = asm.name
        base = getattr(asm, "description", asm.name)
    basis = "orthogonal_latent_basis"
    text = (f"Create a new basis direction '{basis}' outside the known box for: {prompt}. "
            f"Make false: {base}. Accept it only if a fixed solver improves under the new encoding and a "
            "misaligned-control encoding collapses the gain.")
    ortho = lexical_orthogonality(text, pack, extra_known=extra_known)
    return Candidate(
        name="orthogonal_latent_germ",
        operator="orthogonal_germ",
        breaks=[axis or "REPRESENTATION"],
        assumptions=[assumption],
        negation=text,
        needs=["new_basis_coordinate", "external_reducibility_test"],
        discipline=("Must pass a REDUCIBILITY test against a fixed external solver, and the negative control "
                    "with the same transform structure-destroyed must fail to preserve the gain."),
        emergence=ortho,
    )


@dataclass
class OrthogonalLatentGerm:
    """An executable germ: a new coordinate system plus the evidence required to admit it."""
    name: str
    encode: Callable
    description: str = ""
    candidate: Optional[Candidate] = None


@dataclass
class OrthogonalGermVerdict:
    germ: str
    orthogonality: float
    baseline_accuracy: float
    accuracy: float
    control_accuracy: float
    reducibility: float
    control_gap: float
    external_yield: float
    accepted: bool
    status: str
    why: str = ""

    def markdown(self) -> str:
        return (f"- `{self.germ}` -- **{self.status}**: orthogonality {self.orthogonality}, "
                f"accuracy {self.accuracy} vs baseline {self.baseline_accuracy}, control {self.control_accuracy}, "
                f"yield {self.external_yield}. {self.why}")


def evaluate_orthogonal_germ(germ: OrthogonalLatentGerm, solver: Callable, instances: Sequence, labels: Sequence,
                             *, pack=None, known_basis: Optional[Sequence[str]] = None,
                             margin: float = 0.15, orthogonality_floor: float = 0.35) -> OrthogonalGermVerdict:
    """Score a germ with an external task, not the engine's own taste.

    A germ is accepted only when:
      1. it is sufficiently far from the known basis;
      2. it improves a fixed solver over the raw encoding by `margin`;
      3. a structure-destroying control does not preserve the gain.
    """
    from .representation import Representation, representation_reducibility

    rep = Representation(name=germ.name, encode=germ.encode, note=germ.description)
    rv = representation_reducibility(rep, solver, instances, labels, margin=margin)
    if pack is not None:
        basis_text = germ.description or germ.name
        if germ.candidate is not None:
            basis_text += " " + germ.candidate.negation
        ortho = lexical_orthogonality(basis_text, pack, extra_known=known_basis)
    else:
        ortho = 1.0
    external_yield = round(max(0.0, rv.reducibility) * max(0.0, rv.control_gap) * ortho, 4)
    if ortho < orthogonality_floor:
        status, accepted, why = "IN_BOX_BASIS", False, "the proposed basis is too close to the known box."
    elif rv.accepted:
        status, accepted, why = "ORTHOGONAL_REDUCES", True, (
            "the new basis improves a fixed external solver and the misaligned control collapses the gain.")
    elif rv.status == "DECORATIVE":
        status, accepted, why = "DECORATIVE", False, "the control preserves the gain, so this is relabelling."
    else:
        status, accepted, why = "NO_EXTERNAL_GAIN", False, "the new basis does not reduce the external task."
    return OrthogonalGermVerdict(
        germ=germ.name,
        orthogonality=ortho,
        baseline_accuracy=rv.baseline_accuracy,
        accuracy=rv.accuracy,
        control_accuracy=rv.control_accuracy,
        reducibility=rv.reducibility,
        control_gap=rv.control_gap,
        external_yield=external_yield,
        accepted=accepted,
        status=status,
        why=why,
    )


def orthogonal_germ_instruction(pack) -> str:
    """Prompt fragment for LLM/agent loops: make the new-basis move explicit and falsifiable."""
    cand = propose_orthogonal_germ(pack)
    return (f"ORTHOGONAL LATENT GERM: include a candidate that breaks `{cand.assumptions[0]}` by inventing a "
            "new basis coordinate. It must name the fixed-solver baseline, the new encoding, and the negative "
            "control where the encoding is misaligned and the gain collapses.")
