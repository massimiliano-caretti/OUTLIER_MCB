"""theorem_sketch — turn a candidate into a FALSIFIABLE claim stub (domain-agnostic).

It does NOT prove anything. It makes explicit what WOULD have to be true: the formal object, the
negated assumption, the known class to separate from, the desired proposition, the new prediction,
the world-test, and the single counterexample that would kill it. All domain content comes from the
pack (box_name, known_families, axes); nothing is hard-coded to any problem.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class TheoremSketch:
    name: str
    formal_definition: str
    negated_assumption: str
    known_class_to_separate_from: str
    desired_proposition: str
    new_prediction: str
    world_test: str
    killer_counterexample: str
    dimension: Optional[str] = None
    honesty: str = ""
    def as_dict(self) -> Dict: return self.__dict__
    def markdown(self) -> str:
        d = self.as_dict()
        order = ["formal_definition", "negated_assumption", "known_class_to_separate_from",
                 "desired_proposition", "new_prediction", "world_test", "killer_counterexample", "honesty"]
        L = [f"### Theorem sketch — {self.name}  (axis: {self.dimension or '—'})"]
        for k in order:
            L.append(f"- **{k.replace('_', ' ')}:** {d[k]}")
        return "\n".join(L)


def sketch(name: str, breaks: List[str], pack, assumption_name: str = "", rationale: str = "") -> TheoremSketch:
    """Build a falsifiable claim stub for a candidate in the domain described by `pack`.
    `breaks` is the list of axes (pack axes) the candidate claims to break."""
    axis = (breaks[0] if breaks else pack.dimension_of.get(assumption_name)) or None
    a = pack.by_name().get(assumption_name)
    if assumption_name and a is None:
        from .errors import AssumptionNotFoundError
        raise AssumptionNotFoundError(
            f"assumption '{assumption_name}' is not in pack '{pack.name}'; "
            f"available: {sorted(pack.by_name())}")
    neg = (a.if_false if a else "the assumed premise is false on some sub-population")
    families = ", ".join(sorted(set(pack.known_families))) or "the known solution family"
    box = pack.box_name
    axis_verdict = pack.axes.get(axis or "", {}).get("verdict", "")

    if axis is None:
        honesty = "no axis broken → INSIDE_THE_BOX; not a claim candidate."
    else:
        honesty = axis_verdict or f"breaking '{axis}' is the claimed exit from the box."

    new_pred = (f"a measurable quantity that becomes predictable ONLY once '{axis}' is broken — "
                f"absent for every member of [{families}], which cannot represent it.")
    sep = f"the box [{box}] as realized by any of: {families}."
    formal = (rationale or
              f"An object/mechanism that, unlike the box [{box}], is sensitive to the axis '{axis or 'a broken assumption'}'; "
              f"defined so that breaking '{assumption_name or 'the assumption'}' changes its value.")
    prop = (f"There exists a family of instances D such that the candidate separates the target on D with margin ε>0, "
            f"while every member of [{families}] is at chance / ties the baseline on D. (To be falsified, not assumed.)")
    world_test = (f"Construct a world where the discriminative structure lives ENTIRELY on the '{axis}' axis "
                  f"(the box's variables are matched across classes): the candidate must WIN while [{families}] "
                  f"sit at the baseline. Then show the controls (shuffle the '{axis}' structure) collapse the gain to chance.")
    killer = (f"a member of [{families}] reproduces the candidate's score within a small margin on the SAME world "
              f"→ it was inside the box all along; OR the gain does NOT collapse when the '{axis}' structure is shuffled "
              f"→ it was leakage, not the broken axis.")
    return TheoremSketch(name, formal, neg, sep, prop, new_pred, world_test, killer, axis, honesty)
