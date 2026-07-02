"""packs/math — a NON-ML, non-software domain pack (a convergence-theorem question).

Proves the kernel works on pure mathematics: the world-test is a constructed family of functions
(a counterexample/separation), emitted as a SPEC. Verdicts are HEURISTIC priors, not validated.
"""
from __future__ import annotations
from ..core import Assumption
from ..pack import DomainPack, register_pack

A = [
    Assumption("gradient_informative", "The gradient carries reliable descent information.",
               "First-order methods assume -∇f points usefully downhill.",
               "On rugged/non-smooth landscapes the gradient may be uninformative or adversarial.",
               ["gradient_descent", "sgd", "momentum", "adam"],
               "a function family where gradient methods stall but a zeroth-order/structural method converges."),
    Assumption("smoothness_required", "Convergence requires L-smoothness (Lipschitz gradient).",
               "Standard proofs need a smoothness constant.",
               "Convergence might hold under a weaker structure (relative smoothness, KL inequality).",
               ["gradient_descent", "momentum"],
               "a non-L-smooth family where a Bregman/mirror method still converges at a proven rate."),
    Assumption("static_landscape", "The loss landscape is fixed during optimization.",
               "We optimize a frozen objective.",
               "The landscape could be reshaped (homotopy, smoothing schedule) to make descent provable.",
               ["gradient_descent", "sgd"],
               "a hard landscape made provably solvable by a continuation/smoothing path the static view misses."),
    Assumption("euclidean_metric", "Distance/geometry is Euclidean.",
               "Gradient steps live in ℓ2.",
               "The right geometry may be non-Euclidean (mirror map / Riemannian) for the problem class.",
               ["gradient_descent", "adam"],
               "a simplex/positive-orthant problem where mirror descent beats any Euclidean rate."),
]
_axes = {
    "MEASURE":   {"priority": 3, "verdict": "HEURISTIC: questioning WHICH oracle/information you trust (gradient) is the deepest break."},
    "HYPOTHESIS":{"priority": 3, "verdict": "HEURISTIC: weakening the hypothesis (smoothness→relative smoothness/KL) is where new theorems live."},
    "OBJECT":    {"priority": 2, "verdict": "HEURISTIC: reshaping the object (homotopy/continuation) can convert impossible into provable."},
    "STRUCTURE": {"priority": 2, "verdict": "HEURISTIC: changing the geometry (mirror/Riemannian) often yields a strictly better rate."},
}
_dim = {"gradient_informative": "MEASURE", "smoothness_required": "HYPOTHESIS",
        "static_landscape": "OBJECT", "euclidean_metric": "STRUCTURE"}
_edges = [
    ("smoothness_required", "depends_on", "gradient_informative", "smoothness is about the gradient's regularity"),
    ("euclidean_metric", "blocks", "gradient_informative", "the wrong metric makes the gradient point the wrong way"),
    ("smoothness_required", "if_false_requires", "curvature_info", "a weaker hypothesis needs a curvature/Bregman structure"),
]

PACK = DomainPack(
    name="math",
    keywords=["theorem", "convergence", "non-convex", "nonconvex", "gradient", "optimization",
              "smoothness", "lipschitz", "proof", "bound", "rate of convergence", "lemma", "manifold"],
    box_name="first-order Euclidean descent under L-smoothness (GD/SGD/Adam)",
    assumptions=A,
    relations=_edges,
    dimension_of=_dim,
    box_assumptions={"gradient_informative", "smoothness_required", "euclidean_metric"},
    axes=_axes,
    known_families=["gradient_descent", "sgd", "momentum", "adam", "mirror_descent", "newton"],
    info_kinds={"curvature_info": "second-order / Bregman structure → enables relative-smoothness theorems.",
                "oracle_access": "a different oracle (zeroth-order, proximal) → escapes the gradient assumption.",
                "stochastic_samples": "sample structure → variance-reduction rates.",
                "geometry_assumption": "the problem's natural geometry → a mirror map with a better rate."},
    failure_memory={},
    world_factory=None,
)
register_pack(PACK)
