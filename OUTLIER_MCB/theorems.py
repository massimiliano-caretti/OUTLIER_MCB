"""theorems — a consultable registry of REPRESENTATION / IMPOSSIBILITY theorems (FIX D) and a novelty check
for proved statements (FIX E).

FIX D: when the request is "a new X in family F" and F has a representation theorem, the engine must surface
the theorem, mark every in-closure idea INSIDE_THE_BOX, and route generation toward the ONLY exits the
theorem leaves open — never propose 'a new aggregator' for a family the theorem already closes.

FIX E: after a FORMALLY_PROVED, a statement may NOT be called 'a new theorem' until it is checked against a
corpus of classical results. Output is FORMALLY_PROVED (CLASSICAL) or FORMALLY_PROVED (NOVELTY-PENDING-PRIOR-ART).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .closures import CLOSURE_REGISTRY, _mentions      # whole-word keyword matcher


@dataclass
class RepresentationTheorem:
    name: str
    statement: str
    citation: str
    closure: str                     # the universal closure it induces (a key in CLOSURE_REGISTRY)
    family_keywords: List[str]       # how a request is recognized as being in this family
    kind: str = "representation"     # representation | impossibility

    @property
    def exits(self) -> List[str]:
        c = CLOSURE_REGISTRY.get(self.closure)
        return c.exits if c else []


REPRESENTATION_THEOREMS: Dict[str, RepresentationTheorem] = {
    "DEEPSETS_UNIVERSALITY": RepresentationTheorem(
        name="DeepSets universality",
        statement="every permutation-invariant set function equals ρ(Σ_i φ(x_i)) for some φ, ρ",
        citation="Zaheer et al. 2017",
        closure="DEEPSETS",
        family_keywords=["permutation-invariant pool", "permutation invariant pool", "perm-invariant",
                         "perm invariant", "set pooling", "set readout", "mil readout", "mil pooling",
                         "aggregation function", "pooling operator", "bag readout",
                         "instance pooling", "multiple instance"]),
    "KOLMOGOROV_NAGUMO": RepresentationTheorem(
        name="Kolmogorov–Nagumo–Aczél",
        statement="a continuous, symmetric, monotone, idempotent aggregate is a quasi-arithmetic mean f⁻¹(mean f(·))",
        citation="Kolmogorov 1930 / Nagumo 1930 / Aczél",
        closure="QUASI_ARITHMETIC",
        family_keywords=["generalized mean", "quasi-arithmetic", "averaging operator", "idempotent aggregate",
                         "mean of means", "quasi-arithmetic mean"]),
    "CONVOLUTION_EQUIVARIANCE": RepresentationTheorem(
        name="Linear translation-equivariance ⇒ convolution",
        statement="a bounded linear translation-equivariant map on a homogeneous grid is a convolution "
                  "(and, for a general group, equivariance ⇔ a group convolution)",
        citation="Kondor & Trivedi 2018; Cohen & Welling 2016",
        closure="CONVOLUTION",
        family_keywords=["translation-equivariant", "translation equivariant", "shift-equivariant",
                         "shift equivariant", "convolutional operator", "convolutional layer", "new convolution",
                         "equivariant linear layer", "weight-shared filter"]),
}


def find_theorem_for(problem: str) -> Optional[RepresentationTheorem]:
    """The representation theorem governing the family the request is in, if any (keyword match)."""
    low = (problem or "").lower()
    for th in REPRESENTATION_THEOREMS.values():
        if _mentions(low, th.family_keywords):        # whole-word: 'aggregate' must not fire inside 'aggregator'
            return th
    return None


def theorem_brief(problem: str, pack=None) -> Optional[Dict]:
    """FIX D: if the request is in a family closed by a representation theorem, return a brief that (a) surfaces
    the theorem, (b) states that any in-closure idea is INSIDE_THE_BOX, (c) lists the ONLY admissible exits.
    Returns None when no theorem governs the request (the engine proceeds normally)."""
    th = find_theorem_for(problem)
    if th is None:
        return None
    return {
        "theorem": th.name, "statement": th.statement, "citation": th.citation, "closure": th.closure,
        "in_closure_is_inside_the_box": (f"any idea expressible as {CLOSURE_REGISTRY[th.closure].theorem} is "
                                         "INSIDE_THE_BOX — do NOT propose another aggregator in this closure."),
        "admissible_exits": th.exits,
        "brief": (f"This request is governed by «{th.name}» ({th.citation}): {th.statement}. A NEW member of "
                  f"this family does not exist — the closure is universal. Generate ONLY along the exits the "
                  f"theorem leaves open: {', '.join(th.exits)}."),
    }


# ── FIX E: a small corpus of CLASSICAL results; a proved statement matching one is NOT a new theorem ──
KNOWN_THEOREMS = (
    ("power mean inequality", ["power mean", "power-mean", "generalized mean inequality", "p-mean"]),
    ("AM-GM inequality", ["am-gm", "am gm", "arithmetic-geometric", "arithmetic geometric", "geometric mean"]),
    ("Jensen's inequality", ["jensen", "convex", "concavity of"]),
    ("Cauchy–Schwarz", ["cauchy-schwarz", "cauchy schwarz"]),
    ("Hölder's inequality", ["hölder", "holder inequality"]),
    ("Minkowski's inequality", ["minkowski"]),
    ("triangle inequality", ["triangle inequality"]),
    ("Markov / Chebyshev", ["markov inequality", "chebyshev"]),
    ("rearrangement inequality", ["rearrangement"]),
    ("monotonicity of the generalized mean", ["mean is monotone", "monotonic in p", "power-mean is increasing",
                                              "power mean is increasing", "power-mean ≥ mean", "power mean >= mean",
                                              "power-mean greater than", "geq mean", "≥ mean"]),
)


def classify_proved_theorem(statement: str, corpus=None) -> Dict:
    """FIX E: after a FORMALLY_PROVED, classify the statement as CLASSICAL (it matches a known result) or
    NOVELTY-PENDING-PRIOR-ART (no match — but absence of a match is NOT proof of novelty; a real prior-art
    search is still required before any 'new theorem' language)."""
    corpus = corpus or KNOWN_THEOREMS
    low = (statement or "").lower()
    for canonical, keys in corpus:
        if any(k in low for k in keys):
            return {"label": "FORMALLY_PROVED (CLASSICAL)", "classical": True, "matched": canonical,
                    "why": f"the statement matches the classical result «{canonical}» — not a new theorem."}
    return {"label": "FORMALLY_PROVED (NOVELTY-PENDING-PRIOR-ART)", "classical": False, "matched": None,
            "why": ("no classical match in the local corpus — but this is NOT proof of novelty; a REAL online "
                    "prior-art search must confirm it before any 'new theorem' claim (see novelty.honest_prior_art_status).")}
