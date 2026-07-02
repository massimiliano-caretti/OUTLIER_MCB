"""generators.nonbreaking — operators that create WITHOUT breaking anything.

Creation is not only negation. These break no axis (`breaks == []`); their value is the NEW PREDICTION
they make possible, so a world-test certifies them by `new_output`, not by removing an assumption.

  unify       claim two objects are one underlying thing (Maxwell: light = electromagnetism)
  instrument  add a new observable that makes a discarded structure measurable (the telescope move)
  reframe     restate the object so a previously-undecidable question becomes decidable
  dissolve    delete a stage/assumption so the problem dissolves (creativity as negative information)
"""
from __future__ import annotations
from typing import Optional

from .base import Candidate


def unify(pack, name_a: str, name_b: str) -> Optional[Candidate]:
    """Claim two assumptions/objects are the SAME underlying thing and derive what follows."""
    a, b = pack.by_name().get(name_a), pack.by_name().get(name_b)
    if a is None or b is None:
        return None
    return Candidate(
        name=f"unify({name_a},{name_b})", operator="unify", breaks=[], assumptions=[name_a, name_b],
        negation=(f"'{a.description.rstrip('.')}' and '{b.description.rstrip('.')}' are two faces of ONE "
                  f"object; treat them as identical and derive what follows."),
        discipline=("must yield a prediction TRUE under the unified view that NEITHER assumption implies "
                    "alone; if it makes no new prediction, it is renaming → INSIDE_THE_BOX."),
    )


def instrument(pack, name: str, observable: str = "") -> Optional[Candidate]:
    """Propose a NEW observable that makes a discarded axis directly measurable."""
    a = pack.by_name().get(name)
    if a is None:
        return None
    axis = pack.dimension_of.get(name)
    obs = observable or f"a quantity that resolves the '{axis or name}' structure the box cannot see"
    return Candidate(
        name=f"instrument({name})", operator="instrument", breaks=[], assumptions=[name],
        negation=(f"introduce a new observable — {obs} — so that what '{name}' assumes away becomes "
                  f"directly measurable."),
        needs=[obs],
        discipline=("the observable must add a REAL degree of freedom (two instances identical under current "
                    "measurements but different under it) AND be shuffle-invariant; else it relabels old data."),
    )


def reframe(pack, name: str) -> Optional[Candidate]:
    """Restate the object so a previously-undecidable question becomes decidable (e.g. a least-action vs
    a force-by-force description of the same physics)."""
    a = pack.by_name().get(name)
    if a is None:
        return None
    return Candidate(
        name=f"reframe({name})", operator="reframe", breaks=[], assumptions=[name],
        negation=(f"re-describe the problem so that '{a.description.rstrip('.')}' is no longer the natural "
                  f"frame — change WHAT is being asked, not the data."),
        discipline=("must make a NEW question decidable, or a new prediction follow; the SAME empirical content "
                    "merely reframed is cosmetic → INSIDE_THE_BOX."),
    )


def dissolve(pack, name: str) -> Optional[Candidate]:
    """Creativity by DELETION: the strongest move can be removing a stage so the problem dissolves."""
    a = pack.by_name().get(name)
    if a is None or not pack.dimension_of.get(name):
        return None
    return Candidate(
        name=f"dissolve({name})", operator="dissolve", breaks=[pack.dimension_of[name]], assumptions=[name],
        negation=(f"DELETE: remove '{a.description.rstrip('.')}' and the machinery it justifies entirely — "
                  f"does the problem still need solving, or does it dissolve? {a.if_false}"),
        discipline=("well-posedness test: after deletion the problem must remain solvable AND become simpler. "
                    "If removing it breaks correctness it was load-bearing (keep it); if nothing breaks, the "
                    "stage was box-padding and its deletion IS the innovation."),
    )
