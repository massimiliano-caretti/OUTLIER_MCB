"""closures — the closure-membership gate (FIX A): an idea that lives inside a UNIVERSAL representation
closure is INSIDE_THE_BOX no matter how far it looks from any single member.

The MIL failure: a readout "≠ the simple mean" looked like an EXIT, but ρ(Σ φ(x_i)) is the whole DeepSets
closure — universal for permutation-invariant set functions (Zaheer 2017). Distance from the *mean* is not
distance from the *closure*. This module encodes the closures as theorems with explicit STRUCTURAL detectors,
so the engine can rule INSIDE_THE_BOX on membership, not on superficial difference.

Detectors are deliberately structural and explicit (no learned magic): a readout that is a function of
per-instance sums/means (sum, mean, power-mean/GeM, softmax-weighted sum, log-sum-exp, CVaR, …) with a
PER-INSTANCE encoder φ is INSIDE DeepSets; a readout whose φ is conditioned on the WHOLE set (inter-instance
interactions) is OUTSIDE DeepSets (it is the strictly larger Set-Transformer closure).
"""
from __future__ import annotations
from dataclasses import dataclass, field
import re
from typing import Callable, Dict, List, Optional

INSIDE, OUTSIDE, UNKNOWN = "INSIDE", "OUTSIDE", "UNKNOWN"


def _mentions(low: str, signals) -> bool:
    """Whole-token membership: a signal matches only when NOT flanked by alphanumerics — so 'sum' matches 'a sum'
    / 'p-mean' but NOT 'assume', and 'mean' does not match 'meaningful'. Fixes substring false positives that
    mislabelled genuinely-novel readouts as INSIDE the closure. (Multi-word / hyphenated signals still match.)"""
    return any(re.search(r"(?<![a-z0-9])" + re.escape(sig) + r"(?![a-z0-9])", low) for sig in signals)

# φ conditioned on the whole bag → structurally OUTSIDE the per-instance DeepSets closure.
_BAG_CONDITIONED = (
    "conditioned on the whole set", "conditioned on the bag", "conditioned on the entire set",
    "set-context", "set context", "whole-bag context", "whole bag context", "bag-conditioned",
    "depends on other instances", "depends on the other instances", "inter-instance", "interinstance",
    "pairwise interaction", "pairwise interactions", "self-attention encoder", "attention encoder over the bag",
    "instances attend to each other", "instances attend to one another", "each instance feature depends on",
    "phi(x_i, s)", "φ(x_i, s)", "phi conditioned", "φ conditioned", "context of the set", "set-level context",
)
# FIX (#1): an explicit PER-INSTANCE encoder is the defining feature of DeepSets (φ(x_i), not φ(x_i, S)). If
# the text says the encoder is per-instance, a name-dropped interaction phrase does NOT make it a Set-
# Transformer — the encoder, not a casual mention, decides membership.
_PER_INSTANCE = (
    "per-instance", "per instance", "each instance independently", "instance-wise", "instancewise",
    "pointwise encoder", "point-wise encoder", "per-point encoder", "per point encoder", "phi(x_i)", "φ(x_i)",
)
# a permutation-invariant aggregation of per-instance features → INSIDE the DeepSets closure.
_AGGREGATION = (
    "mean", "average", "sum", "σ", "pool", "pooling", "softmax", "logsumexp", "log-sum-exp", "log sum exp",
    "power-mean", "power mean", "p-mean", "gem", "generalized mean", "cvar", "weighted sum", "attention-weighted",
    "attention weighted", "soft-top-k", "soft top-k", "soft topk", "top-k", "quantile", "moment", "logmeanexp",
)
_GENERALIZED_MEAN = (
    "power-mean", "power mean", "p-mean", "gem", "generalized mean", "quasi-arithmetic", "quasi arithmetic",
    "f-mean", "kolmogorov", "nagumo", "holder mean", "hölder mean",
)


def _readout_text(candidate) -> str:
    if isinstance(candidate, str):
        return candidate
    g = lambda k: getattr(candidate, k, "") if not isinstance(candidate, dict) else candidate.get(k, "")
    return " ".join(str(g(k)) for k in ("name", "negation", "claim", "readout", "discipline", "description") if g(k))


def _bag_conditioned(low: str) -> bool:
    """φ genuinely conditioned on the whole set, AND not explicitly declared per-instance. A false OUTSIDE
    fabricates a novelty escape, so the encoder — not a casual 'interaction' mention — must decide (#1/#2)."""
    return any(sig in low for sig in _BAG_CONDITIONED) and not any(sig in low for sig in _PER_INSTANCE)


def _detect_deepsets(text: str) -> str:
    low = text.lower()
    if _bag_conditioned(low):                            # φ sees the whole set (no per-instance encoder)
        return OUTSIDE                                   # → strictly larger Set-Transformer closure, not DeepSets
    if _mentions(low, _AGGREGATION):                     # whole-token: 'sum' must not fire on 'assume'
        return INSIDE                                    # a function of per-instance sums/means → ρ(Σφ)
    return UNKNOWN


def _detect_quasi_arithmetic(text: str) -> str:
    low = text.lower()
    if _mentions(low, _GENERALIZED_MEAN):
        return INSIDE                                    # f⁻¹(mean f(·)): idempotent + symmetric + monotone
    # whole-token 'mean'/'average' (not 'meaningful'). Exclude only genuine non-idempotent aggregates
    # (softmax/ratio/weighted). A bare '/' was too aggressive: it suppressed a plain mean on any stray slash
    # (e.g. a citation "eq. a/b") — and harmonic/geometric means, written with '/', ARE quasi-arithmetic anyway.
    if _mentions(low, ("mean", "average")) and not any(x in low for x in ("softmax", "ratio", "weighted")):
        return INSIDE                                    # a plain mean is the canonical quasi-arithmetic mean
    return UNKNOWN


def _detect_set_transformer(text: str) -> str:
    low = text.lower()
    if _bag_conditioned(low):                            # φ conditioned on the set (and not per-instance)
        return INSIDE                                    # is exactly this closure — coherent with _detect_deepsets
    return UNKNOWN


# ── CONVOLUTION closure (a DIFFERENT domain than sets): a bounded LINEAR TRANSLATION-EQUIVARIANT map on a
#    homogeneous grid is a convolution. So a "new linear shift-equivariant layer" is INSIDE — a reinvention,
#    however novel its surface — and the ONLY exits are to break linearity or break translation-equivariance. ──
_CONV_NAME = (                                           # named as a convolution (up to kernel flip) → INSIDE
    "convolution", "convolutional", "cross-correlation", "cross correlation", "depthwise conv",
    "dilated convolution", "atrous convolution", "circular convolution", "fft convolution", "1x1 convolution",
    "separable convolution", "toeplitz operator", "weight-shared filter", "weight-sharing filter",
)
_CONV_LINEQUIV = (                                        # linear + translation/shift-equivariant ⇒ (theorem) a conv
    "translation-equivariant", "translation equivariant", "shift-equivariant", "shift equivariant",
    "translation-invariant filter", "shift-invariant linear",
)
_CONV_ESCAPE = (                                          # breaks linearity OR translation-equivariance ⇒ OUTSIDE
    "nonlinear", "non-linear", "position-dependent", "position dependent", "position-conditioned",
    "coordinate channel", "coord channel", "coordconv", "absolute position", "input-dependent kernel",
    "input dependent kernel", "data-dependent kernel", "data dependent kernel", "dynamic convolution",
    "dynamic kernel", "adaptive kernel", "deformable", "content-based", "self-attention", "self attention",
    "attention", "learned offsets", "per-position kernel", "spatially-varying kernel", "spatially varying kernel",
)


def _detect_convolution(text: str) -> str:
    low = text.lower()
    if any(sig in low for sig in _CONV_ESCAPE):          # a sanctioned exit is taken (nonlinear / not equivariant)
        return OUTSIDE
    if _mentions(low, _CONV_NAME):                        # named convolution (whole-token: 'conv' not in 'convex')
        return INSIDE
    if "linear" in low and any(sig in low for sig in _CONV_LINEQUIV):
        return INSIDE                                    # theorem: a linear translation-equivariant map IS a conv
    return UNKNOWN


@dataclass
class UniversalClosure:
    name: str
    theorem: str                     # the representation theorem that makes the family a CLOSURE
    citation: str
    detect: Callable                 # (text) -> INSIDE | OUTSIDE | UNKNOWN  (explicit structural heuristic)
    exits: List[str] = field(default_factory=list)   # the ONLY openings the theorem leaves


CLOSURE_REGISTRY: Dict[str, UniversalClosure] = {
    "DEEPSETS": UniversalClosure(
        name="DEEPSETS",
        theorem="any permutation-invariant set function = ρ(Σ_i φ(x_i)) with a per-instance encoder φ",
        citation="Zaheer et al. 2017 (Deep Sets); Qi et al. 2017 (PointNet)",
        detect=_detect_deepsets,
        exits=["condition φ on the whole set (leave per-instance encoding)", "break permutation invariance",
               "change the object/readout target", "acquire a NEW observable / new information"]),
    "QUASI_ARITHMETIC": UniversalClosure(
        name="QUASI_ARITHMETIC",
        theorem="a continuous, symmetric, monotone, IDEMPOTENT aggregate is a quasi-arithmetic mean f⁻¹(mean f(·))",
        citation="Kolmogorov 1930 / Nagumo 1930 / Aczél",
        detect=_detect_quasi_arithmetic,
        exits=["drop idempotence (allow a non-mean aggregate)", "drop symmetry", "drop monotonicity",
               "change the object/readout target"]),
    "SET_TRANSFORMER": UniversalClosure(
        name="SET_TRANSFORMER",
        theorem="readouts whose per-instance features are conditioned on the whole set (inter-instance attention)",
        citation="Lee et al. 2019 (Set Transformer)",
        detect=_detect_set_transformer,
        exits=["change the object/readout target", "acquire a NEW observable / new information"]),
    "CONVOLUTION": UniversalClosure(
        name="CONVOLUTION",
        theorem="a bounded LINEAR TRANSLATION-EQUIVARIANT map on a homogeneous grid IS a convolution (a weight-"
                "shared, shift-invariant filter); equivalently, equivariance to a group ⇔ a group convolution",
        citation="Kondor & Trivedi 2018; Cohen & Welling 2016 (Group-equivariant CNNs); classical (Toeplitz)",
        detect=_detect_convolution,
        exits=["drop linearity (a nonlinear translation-equivariant map)",
               "break translation-equivariance (condition on absolute position / input-dependent kernel)",
               "change the group or domain (equivariance to a larger group)",
               "acquire a NEW observable / new information"]),
}


def reduces_to_closure(candidate, closure) -> str:
    """INSIDE / OUTSIDE / UNKNOWN — does the candidate's readout reduce to this universal closure?
    `closure` may be a UniversalClosure or a name in CLOSURE_REGISTRY."""
    if isinstance(closure, str):
        closure = CLOSURE_REGISTRY.get(closure.upper())
        if closure is None:
            return UNKNOWN
    return closure.detect(_readout_text(candidate))


def closure_membership(candidate, pack) -> Dict:
    """Check a candidate against EVERY universal closure the pack declares (FIX A hard rule). If it is INSIDE
    any declared closure → INSIDE_THE_BOX, regardless of how different it looks from a single member."""
    declared = list(getattr(pack, "universal_closures", []) or [])
    inside_of, outside_of, unknown_of = [], [], []
    for name in declared:
        v = reduces_to_closure(candidate, name)
        (inside_of if v == INSIDE else outside_of if v == OUTSIDE else unknown_of).append(name)
    if inside_of:
        return {"verdict": "INSIDE_THE_BOX", "inside_closure": inside_of[0], "inside_closures": inside_of,
                "reason": (f"reduces to the universal closure «{inside_of[0]}» "
                           f"({CLOSURE_REGISTRY[inside_of[0]].theorem}) — INSIDE the box however much it differs "
                           "from any single member; distance from one member is not distance from the closure."),
                "exits": CLOSURE_REGISTRY[inside_of[0]].exits}
    if declared and not unknown_of:          # proven OUTSIDE every declared closure
        return {"verdict": "OUTSIDE_DECLARED_CLOSURES", "inside_closure": None, "inside_closures": [],
                "reason": f"OUTSIDE every declared closure ({', '.join(declared)}) — a real closure-escape.",
                "exits": []}
    return {"verdict": "UNKNOWN", "inside_closure": None, "inside_closures": [],
            "reason": "membership undetermined by the structural detectors (declare more structure or prove it).",
            "exits": []}


def closure_escape_proven(candidate, pack) -> bool:
    """True only if the candidate is structurally OUTSIDE EVERY universal closure the pack declares (and the
    pack declares at least one). This is requirement (i) of the honest novelty ladder (FIX B)."""
    declared = list(getattr(pack, "universal_closures", []) or [])
    if not declared:
        return False
    return all(reduces_to_closure(candidate, name) == OUTSIDE for name in declared)


# the honest ladder for ARCHITECTURAL novelty (FIX B). ALIVE_OWN_WORLD is NOT novelty.
ARCHITECTURE_LADDER = ("INSIDE_THE_BOX", "NOT_YET_NOVEL", "ALIVE_OWN_WORLD",
                       "ALIVE_LOCAL_NOVELTY", "ALIVE_ARCHITECTURAL")


def architectural_novelty(candidate, pack, evidence: Optional[Dict] = None) -> Dict:
    """FIX B: place an architecture on the honest ladder. To be presentable as novel it needs, in AND:
      (i)   a proven closure-escape (OUTSIDE every declared universal closure),
      (ii)  a transfer-test passed on a world the candidate did NOT design,
      (iii) a real prior-art check.
    Without (i) the result is NOT_YET_NOVEL and its markdown makes NO affirmative novelty/innovation claim —
    it shows 'NOT YET NOVEL — closure-escape mancante'. ALIVE_OWN_WORLD never licenses 'novel'/'innovative'."""
    e = evidence or {}
    membership = closure_membership(candidate, pack)
    if membership["verdict"] == "INSIDE_THE_BOX":
        return {"state": "INSIDE_THE_BOX", "can_say_novel": False, "closure_escape": False,
                "reason": membership["reason"], "inside_closure": membership["inside_closure"],
                "markdown": (f"- verdict: **INSIDE_THE_BOX** — {membership['reason']} Admissible exits: "
                             f"{', '.join(membership['exits'])}.")}
    escape = e["closure_escape"] if "closure_escape" in e else closure_escape_proven(candidate, pack)
    transfer = bool(e.get("transfer_test_passed"))
    prior_art = bool(e.get("prior_art_checked"))
    can_say_novel = bool(escape and prior_art)
    if not escape:
        state = "NOT_YET_NOVEL"
        md = ("- verdict: **NOT YET NOVEL — closure-escape mancante**. Prove the idea is OUTSIDE every declared "
              "universal closure and run a REAL prior-art search before any such claim. Admissible exits: "
              + ", ".join(CLOSURE_REGISTRY[c].exits[0] for c in (getattr(pack, "universal_closures", []) or []) if c in CLOSURE_REGISTRY) + ".")
    elif can_say_novel and transfer:
        state, md = "ALIVE_ARCHITECTURAL", "- verdict: **ALIVE_ARCHITECTURAL** — closure-escape proven, transfer-test passed, prior-art checked."
    elif can_say_novel:
        state, md = "ALIVE_LOCAL_NOVELTY", "- verdict: **ALIVE_LOCAL_NOVELTY** — closure-escape + prior-art checked; transfer-test still pending."
    else:
        state = "ALIVE_OWN_WORLD"
        md = ("- verdict: **ALIVE_OWN_WORLD** — wins only on its own arena; closure-escape not yet paired with a "
              "real prior-art check, so this is NOT presentable as new. Run the prior-art search + a transfer-test.")
    return {"state": state, "can_say_novel": can_say_novel, "closure_escape": bool(escape),
            "transfer_test_passed": transfer, "prior_art_checked": prior_art, "markdown": md,
            "reason": ("closure-escape missing" if not escape else "escaped the declared closures")}
