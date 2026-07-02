"""packs/physics — a NON-math domain pack, to demonstrate the engine is agnostic across fields.

The hidden assumptions of the STANDARD way to model a physical/engineered system: treat it as closed, linear,
near-equilibrium, mean-field, with the relevant conserved quantities fixed. A genuinely new approach must break
one of THEM — and an idea that reduces to a closed-system over-unity claim is killed by the thermodynamics
barrier (barriers.py), exactly as a sieve-for-gap-2 is killed in number theory. Verdicts are HEURISTIC priors,
not validated truth; nothing here proves any physics — it organizes WHICH assumption a partial result breaks,
so the SAME falsification spine (now settled by a reproducible SIMULATION / EXPERIMENT, not z3) can attack it.
"""
from __future__ import annotations
from ..core import Assumption
from ..pack import DomainPack, register_pack

A = [
    Assumption(
        "system_is_closed",
        "The system is treated as CLOSED — no exchange of energy/matter with its environment.",
        "A closed system has clean conservation laws and is the easiest to analyze.",
        "Treating it as OPEN (a reservoir, a gradient, an external drive) unlocks behavior a closed model forbids "
        "(work from a temperature gradient, dissipative structures).",
        ["closed_system_energy_balance", "equilibrium_thermodynamics"],
        "build/simulate an OPEN-system instance that achieves what the closed model declares impossible, and show "
        "the closed baseline cannot."),
    Assumption(
        "response_is_linear",
        "The system's response is LINEAR in the input (superposition holds).",
        "Linear models are tractable and accurate near a fixed point.",
        "Nonlinearity (bifurcations, solitons, chaos) produces effects no linear model can represent.",
        ["linear_response"],
        "a regime where a nonlinear effect dominates and the linear prediction provably fails."),
    Assumption(
        "at_equilibrium",
        "The system is at or near EQUILIBRIUM (or steady state).",
        "Equilibrium gives stationary, well-defined macroscopic quantities.",
        "Far-from-equilibrium driving sustains structure/transport an equilibrium model cannot (Prigogine).",
        ["equilibrium_thermodynamics"],
        "a driven, far-from-equilibrium construction whose measured behavior the equilibrium model cannot match."),
    Assumption(
        "mean_field_independent",
        "Components interact only through a MEAN FIELD — correlations/fluctuations are negligible.",
        "The mean-field average makes the many-body problem solvable.",
        "Strong correlations/fluctuations (criticality, entanglement, turbulence) change the result qualitatively.",
        ["mean_field"],
        "a regime where measured correlations dominate and the mean-field prediction provably breaks."),
    Assumption(
        "conserved_quantities_fixed",
        "The relevant CONSERVED quantities (energy, momentum, charge) are fixed and fully accounted for.",
        "Conservation laws are bedrock and rarely questioned in a model.",
        "A hidden flux or an unmodeled symmetry/break can change what is actually conserved in the regime studied.",
        ["closed_system_energy_balance"],
        "a construction where an unmodeled conserved/【broken】 quantity changes the outcome the standard model predicts."),
]

_axes = {
    "STRUCTURE":     {"priority": 3, "verdict": "HEURISTIC: opening the system (closed→open / equilibrium→driven) is the deepest break — most 'impossible' results live there."},
    "REGIME":        {"priority": 3, "verdict": "HEURISTIC: leaving equilibrium / linearity (the regime) is where qualitatively new physics appears."},
    "REPRESENTATION":{"priority": 2, "verdict": "HEURISTIC: a linear representation hides nonlinear effects; changing it can reveal new signal."},
    "MEASURE":       {"priority": 2, "verdict": "HEURISTIC: what you treat as negligible (correlations/fluctuations) decides whether mean-field holds."},
    "HYPOTHESIS":    {"priority": 2, "verdict": "HEURISTIC: which conservation laws you assume fixed bounds what the model can predict."},
}
_dim = {
    "system_is_closed": "STRUCTURE",
    "at_equilibrium": "REGIME",
    "response_is_linear": "REPRESENTATION",
    "mean_field_independent": "MEASURE",
    "conserved_quantities_fixed": "HYPOTHESIS",
}
_edges = [
    ("system_is_closed", "blocks", "conserved_quantities_fixed",
     "a closed-system assumption hard-codes which quantities are conserved"),
    ("at_equilibrium", "if_false_requires", "drive_protocol",
     "leaving equilibrium needs an explicit driving/forcing protocol"),
    ("response_is_linear", "if_false_requires", "nonlinear_regime",
     "a nonlinear effect needs a regime where it dominates"),
]

PACK = DomainPack(
    name="physics",
    keywords=[
        # English — deliberately PHYSICS-SPECIFIC (no generic 'system'/'energy'/'force' that would mis-route)
        "physics", "thermodynamic", "thermodynamics", "entropy", "perpetual motion", "perpetuum mobile",
        "over-unity", "carnot", "conservation of energy", "second law of thermodynamics", "statistical mechanics",
        "far-from-equilibrium", "far from equilibrium", "nonlinear dynamics", "mean-field",
        # Italian
        "fisica", "termodinamica", "termodinamico", "entropia", "moto perpetuo", "conservazione dell'energia",
        "meccanica statistica", "fuori equilibrio", "dinamica nonlineare",
    ],
    box_name="the standard closed-system, linear, near-equilibrium, mean-field model of a physical system",
    assumptions=A,
    relations=_edges,
    dimension_of=_dim,
    box_assumptions={"system_is_closed", "response_is_linear", "at_equilibrium"},
    axes=_axes,
    known_families=["closed_system_energy_balance", "linear_response", "equilibrium_thermodynamics", "mean_field"],
    info_kinds={
        "drive_protocol": "an explicit forcing/driving protocol → reaches far-from-equilibrium behavior.",
        "nonlinear_regime": "a regime where a nonlinear term dominates → escapes the linear model.",
        "correlation_data": "measured correlations/fluctuations → tells when mean-field fails.",
        "open_boundary": "an energy/matter reservoir or gradient → legitimately exceeds a closed-system bound.",
    },
    failure_memory={},
    world_factory=None,
)
register_pack(PACK)
