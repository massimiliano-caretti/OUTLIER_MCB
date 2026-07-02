"""packs/causal — a CAUSAL-INFERENCE discovery pack: the hidden assumptions of naive association.

The box here is reading correlation as causation: an observational association, taken at face value,
in a fixed direction, with all confounders assumed observed. Each assumption is a shared prior of that
box; breaking one routes the candidate to a different identification strategy (see evaluators/causal.py).
Verdicts are HEURISTIC priors, not validated.

The discipline is unchanged and is exactly the right one for causality: a claimed effect only survives
if it is ROBUST to the controls — adjusting for the observed confounders does not explain it away, and a
placebo (permuted treatment) collapses it. A claim that latent confounders may exist is `causal_sufficiency`
broken → the effect is NOT identifiable from observation alone → the evaluator reports it HUMAN, never AUTO.
"""
from __future__ import annotations
from ..core import Assumption
from ..pack import DomainPack, register_pack

A = [
    Assumption("association_is_direct",
               "An observed association between two variables reflects a direct effect.",
               "Naive analysis reads a correlation as a cause.",
               "A common cause (confounder) produces the association; the direct effect may be zero.",
               ["correlation_analysis", "naive_regression", "observational_association"],
               "a dataset where A and B correlate only through a common cause Z; adjusting for Z "
               "collapses the effect to zero, and a placebo (permuted treatment) also collapses it."),
    Assumption("direction_is_known",
               "The causal direction is the assumed one (A→B).",
               "Regressing B on A presumes A is the cause.",
               "The arrow may reverse (B→A) or be bidirectional; the direction is not identified.",
               ["regression_of_b_on_a"],
               "a dataset where the assumed direction and its reverse fit equally well, so direction "
               "needs a time order or an instrument the observational fit does not provide."),
    Assumption("causal_sufficiency",
               "All common causes are observed (no hidden confounder).",
               "Back-door adjustment and the PC algorithm assume causal sufficiency.",
               "An unobserved confounder exists; no observed adjustment set removes the bias.",
               ["pc_algorithm", "backdoor_adjustment"],
               "a dataset with a hidden confounder where every observed adjustment set leaves a residual "
               "bias — the effect is unidentifiable from observation alone (a HUMAN must run an experiment)."),
    Assumption("effect_is_homogeneous",
               "The causal effect is the same across the population.",
               "An average treatment effect assumes one number describes everyone.",
               "The effect is modified by a subgroup variable and averages can hide it.",
               ["average_treatment_effect"],
               "a dataset where the effect is positive in one subgroup and negative in another, "
               "averaging to ~0, so the homogeneous estimate is misleading."),
]

_axes = {
    "CONFOUNDING":  {"priority": 3, "verdict": "HEURISTIC: separating correlation from causation (adjust for the common cause) is the deepest break."},
    "DIRECTION":    {"priority": 2, "verdict": "HEURISTIC: questioning the arrow's direction (A→B vs B→A) guards against reversed causation."},
    "LATENT":       {"priority": 3, "verdict": "HEURISTIC: admitting hidden confounders is where observational identifiability breaks — often a HUMAN experiment."},
    "MODIFICATION": {"priority": 2, "verdict": "HEURISTIC: allowing effect modification (heterogeneous effects) recovers signal an average hides."},
}
_dim = {"association_is_direct": "CONFOUNDING", "direction_is_known": "DIRECTION",
        "causal_sufficiency": "LATENT", "effect_is_homogeneous": "MODIFICATION"}
_edges = [
    ("association_is_direct", "if_false_requires", "confounder_adjustment", "separating a direct effect needs adjustment for the confounders"),
    ("direction_is_known", "if_false_requires", "temporal_order", "settling direction needs a time order or an instrument"),
    ("causal_sufficiency", "if_false_requires", "latent_variable_search", "hidden confounding needs a latent-variable search / an experiment"),
    ("effect_is_homogeneous", "if_false_requires", "subgroup_data", "effect modification needs a subgroup / moderator variable"),
]

PACK = DomainPack(
    name="causal",
    keywords=["causal inference", "confounder", "confounding", "cause and effect", "causal effect",
              "causal graph", "does x cause", "spurious correlation", "back-door", "intervention effect"],
    box_name="reading an observational correlation as a direct causal effect",
    assumptions=A,
    relations=_edges,
    dimension_of=_dim,
    box_assumptions={"association_is_direct", "direction_is_known", "causal_sufficiency"},
    axes=_axes,
    known_families=["correlation_analysis", "naive_regression", "observational_association",
                    "regression_of_b_on_a", "pc_algorithm", "backdoor_adjustment", "average_treatment_effect"],
    info_kinds={"confounder_adjustment": "the observed confounders to adjust for → separates a direct effect from a spurious one.",
                "temporal_order": "a time order / an instrument → identifies the causal direction.",
                "latent_variable_search": "a search for hidden confounders → flags non-identifiability (often a HUMAN experiment).",
                "subgroup_data": "a moderator variable → reveals effect modification an average hides."},
    failure_memory={},
    world_factory=None,
)
register_pack(PACK)
