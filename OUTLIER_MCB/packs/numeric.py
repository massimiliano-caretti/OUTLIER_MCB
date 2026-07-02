"""packs/numeric — a DATA-DRIVEN discovery pack: the hidden assumptions about the FORM of a law.

This is the domain layer that turns OUTLIER_MCB into a law-discovery engine. The box here is ordinary
regression: an additive, smooth, polynomial fit over the raw measured variables. Each assumption is a
shared prior of that box about the *functional form* of the law; breaking one expands the hypothesis
class the data are fitted in (see evaluators/symbolic.py). Verdicts are HEURISTIC priors, not validated.

The discipline is unchanged: a broken assumption only GENERATES a wider search space; the formula it
yields must still die on a world-test — a low residual on a held-out split AND a negative control
(independently shuffled columns) that collapses, exactly the kernel's death-gate clause (c).
"""
from __future__ import annotations
from ..core import Assumption
from ..pack import DomainPack, register_pack

A = [
    Assumption("law_is_separable",
               "The law factorizes additively/separably over the inputs.",
               "Additive models and GAMs assume each variable contributes independently.",
               "The inputs are coupled: an irreducible interaction term carries the signal.",
               ["linear_regression", "additive_model", "GAM"],
               "a dataset where every separable model has high held-out residual but a model with an "
               "interaction term collapses it, and the gain vanishes when the columns are shuffled."),
    Assumption("law_is_smooth",
               "The law is smooth/analytic everywhere.",
               "Polynomial and spline fits assume continuity and differentiability.",
               "There is a threshold / phase transition a smooth fit cannot capture.",
               ["polynomial_fit", "spline"],
               "a dataset with a kink where every smooth fit fails on held-out but a threshold "
               "(ReLU/Heaviside) term succeeds, and the gain collapses under the controls."),
    Assumption("law_is_polynomial",
               "The law lives in the polynomial basis.",
               "Taylor expansions and polynomial regression assume a power-series form.",
               "The law needs a transcendental primitive (sin, exp, log) absent from the polynomial basis.",
               ["polynomial_fit", "taylor_expansion"],
               "a periodic/exponential dataset where any bounded-degree polynomial diverges on held-out "
               "but a trig/exp term fits and survives the controls."),
    Assumption("variables_are_raw",
               "The explanatory variables are the measured ones.",
               "Regression assumes the given features are the right coordinates.",
               "The law is simple only in dimensionless groups / a transformed frame.",
               ["linear_regression"],
               "a dataset where raw-feature regression stays complex but a regression on dimensionless "
               "ratios is simple, stable, and collapses under the controls."),
]

_axes = {
    "FORM":       {"priority": 3, "verdict": "HEURISTIC: questioning the functional form (separable→coupled) is the highest-leverage break."},
    "REGULARITY": {"priority": 3, "verdict": "HEURISTIC: weakening regularity (smooth→piecewise/threshold) finds transitions the smooth fit misses."},
    "BASIS":      {"priority": 2, "verdict": "HEURISTIC: expanding the primitive basis (polynomial→trig/exp) reaches laws the box cannot express."},
    "FRAME":      {"priority": 2, "verdict": "HEURISTIC: changing the frame (raw→dimensionless groups) can collapse a messy law to a simple one."},
}
_dim = {"law_is_separable": "FORM", "law_is_smooth": "REGULARITY",
        "law_is_polynomial": "BASIS", "variables_are_raw": "FRAME"}
_edges = [
    ("law_is_separable", "if_false_requires", "interaction_terms", "breaking separability needs an interaction term"),
    ("law_is_smooth", "if_false_requires", "threshold_structure", "a non-smooth law needs threshold structure"),
    ("law_is_polynomial", "if_false_requires", "transcendental_basis", "leaving the polynomial basis needs a transcendental primitive"),
]

PACK = DomainPack(
    name="numeric",
    # distinctive, mostly multi-word keywords so routing does not steal from coding/math/generic.
    keywords=["symbolic regression", "scientific law", "empirical law", "governing equation",
              "law from data", "formula from data", "discover a law", "conjecture", "physical law"],
    box_name="additive, smooth, polynomial regression over the raw measured variables",
    assumptions=A,
    relations=_edges,
    dimension_of=_dim,
    box_assumptions={"law_is_separable", "law_is_smooth", "law_is_polynomial"},
    axes=_axes,
    known_families=["linear_regression", "polynomial_fit", "additive_model", "GAM", "spline", "taylor_expansion"],
    info_kinds={"interaction_terms": "coupled terms x_i·x_j → expresses laws no separable model can.",
                "threshold_structure": "piecewise / Heaviside structure → captures transitions a smooth fit misses.",
                "transcendental_basis": "sin/cos/exp/log primitives → reaches laws outside the polynomial basis.",
                "dimensionless_groups": "ratios / Buckingham-π groups → a simpler law in a transformed frame."},
    failure_memory={},
    world_factory=None,
)
register_pack(PACK)
