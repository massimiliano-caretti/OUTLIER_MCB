"""packs/generic — the universal fallback when no domain pack matches.

It does NOT pretend to know the domain. It carries only the four DOMAIN-INDEPENDENT axes on which
almost any solution can be broken, and the generic assumptions that hide in every problem statement.
When this pack is selected, the guard should fire and `elicit_pack` should ask the assistant to BUILD
a real domain pack (the spark) before the kernel proceeds. This is how agnosticism stays honest:
the kernel never invents domain content, it requests it.
"""
from __future__ import annotations
from ..core import Assumption
from ..pack import DomainPack, register_pack

A = [
    Assumption("representation_is_fixed", "The representation of the input is the obvious one.",
               "We inherit the representation the problem ships with.",
               "A different representation can make the hard part trivial (or reveal new signal).",
               ["the standard approach"],
               "two inputs identical under the default representation but different under a richer one."),
    Assumption("objective_is_given", "The objective/metric is the one stated.",
               "The stated metric feels like the goal.",
               "Optimizing a different (proxy or reframed) objective can dominate on what actually matters.",
               ["the standard approach"],
               "a case where the stated metric and the true goal diverge."),
    Assumption("evaluation_is_fixed", "Success is judged the way it is currently judged.",
               "The current evaluation is taken as ground truth.",
               "The evaluation itself may be the thing to redesign (new test, new oracle).",
               ["the standard approach"],
               "a solution that 'wins' the current evaluation yet fails the real need."),
    Assumption("decomposition_is_natural", "The natural decomposition of the problem is the right one.",
               "We split the problem the way textbooks do.",
               "A different decomposition (or none) can expose a shortcut.",
               ["the standard approach"],
               "a re-decomposition that removes an entire stage."),
]
_axes = {
    "REPRESENTATION": {"priority": 3, "verdict": "what is measured/encoded — usually the highest-leverage break."},
    "OBJECTIVE":      {"priority": 3, "verdict": "what is optimized — reframing the goal beats optimizing harder."},
    "EVALUATION":     {"priority": 2, "verdict": "how success is judged — sometimes the real innovation."},
    "DECOMPOSITION":  {"priority": 2, "verdict": "how the problem is split — a better cut can delete a stage."},
}
_dim = {"representation_is_fixed": "REPRESENTATION", "objective_is_given": "OBJECTIVE",
        "evaluation_is_fixed": "EVALUATION", "decomposition_is_natural": "DECOMPOSITION"}

PACK = DomainPack(
    name="generic",
    keywords=[],   # never selected by keyword; only as explicit fallback
    box_name="the most-probable solution from training memory (the average answer)",
    assumptions=A,
    relations=[],
    dimension_of=_dim,
    box_assumptions=set(_dim),
    axes=_axes,
    known_families=["the standard / most-cited approach"],
    info_kinds={"new_observable": "a quantity not currently measured.",
                "new_oracle": "a different source of truth/feedback.",
                "new_constraint": "a constraint that reshapes the feasible set."},
    failure_memory={},
    world_factory=None,
)
register_pack(PACK)
