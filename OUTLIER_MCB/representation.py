"""representation — invent the REPRESENTATION that makes a hard problem easy, disciplined by a control (T2.4).

The deepest creative move, and the one no system makes: a genius does not only search within a fixed encoding,
they invent the NOTATION that makes the hard problem trivial — Feynman diagrams, Leibniz's dx, place-value.
transformation.transform_space grows a new AXIS inside a pack; this goes further: it re-encodes the problem's
OBJECTS and asks whether a fixed solver, helpless on the raw encoding, SUCCEEDS on the invented one.

The honesty gate is a CONTROL, so this can never be re-encoding theatre. A representation is accepted only if:
  (i)  a fixed `solver` scores materially higher under it than under the identity encoding (a real reducibility
       gain), AND
  (ii) a STRUCTURE-DESTROYING control (the same transform, misaligned from the instances) does NOT give the
       gain — proving it is the representation's STRUCTURE that helps, not merely 'applying some transform'.
An idea that lifts accuracy but whose control lifts it just as much is DECORATIVE (a relabelling), not a new
notation. Deterministic, zero-dependency; the solver and instances are the external world that settles it.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence


@dataclass
class Representation:
    """A re-encoding of a problem's objects. `encode(instance) -> encoded` is what the solver actually sees."""
    name: str
    encode: Callable
    note: str = ""


@dataclass
class ReducibilityVerdict:
    representation: str
    baseline_accuracy: float          # solver accuracy on the RAW (identity) encoding
    accuracy: float                   # solver accuracy under this representation
    control_accuracy: float           # solver accuracy under the structure-destroying control
    accepted: bool
    status: str                       # REDUCES | DECORATIVE | NO_GAIN
    why: str = ""

    @property
    def reducibility(self) -> float:
        return round(self.accuracy - self.baseline_accuracy, 4)

    @property
    def control_gap(self) -> float:
        return round(self.accuracy - self.control_accuracy, 4)

    def markdown(self) -> str:
        return (f"- `{self.representation}` — **{self.status}**: accuracy {self.accuracy} vs baseline "
                f"{self.baseline_accuracy} (reducibility {self.reducibility}); control {self.control_accuracy} "
                f"(gap {self.control_gap}). {self.why}")


def _accuracy(solver: Callable, encode: Callable, instances: Sequence, labels: Sequence) -> float:
    n = len(instances)
    if not n:
        return 0.0
    return round(sum(1 for x, y in zip(instances, labels) if bool(solver(encode(x))) == bool(y)) / n, 4)


def _control_accuracy(solver: Callable, encode: Callable, instances: Sequence, labels: Sequence) -> float:
    """The structure-destroying control: keep the SAME encodings but MISALIGN them from the instances (a
    deterministic cyclic shift). If the representation's power came from real structure, misaligning it must
    collapse the gain; if the accuracy holds anyway, the 'gain' was an artefact, not the representation."""
    n = len(instances)
    if n < 2:
        return 0.0
    encs = [encode(x) for x in instances]
    shifted = encs[1:] + encs[:1]
    return round(sum(1 for e, y in zip(shifted, labels) if bool(solver(e)) == bool(y)) / n, 4)


def representation_reducibility(representation: Representation, solver: Callable, instances: Sequence,
                                labels: Sequence, margin: float = 0.15) -> ReducibilityVerdict:
    """Does `representation` make the problem easier for `solver` — for real? Compares accuracy under it to the
    identity baseline and to a structure-destroying control. REDUCES only if it beats BOTH by `margin`."""
    baseline = _accuracy(solver, lambda x: x, instances, labels)
    acc = _accuracy(solver, representation.encode, instances, labels)
    ctrl = _control_accuracy(solver, representation.encode, instances, labels)
    reduces = acc >= baseline + margin
    beats_control = acc >= ctrl + margin
    if reduces and beats_control:
        status, accepted, why = "REDUCES", True, ("a fixed solver, weak on the raw encoding, succeeds under this "
                                                  "representation — and the control collapses, so its STRUCTURE is "
                                                  "what helps.")
    elif reduces and not beats_control:
        status, accepted, why = "DECORATIVE", False, ("lifts accuracy, but the structure-destroying control lifts "
                                                      "it just as much — a relabelling, not a new notation.")
    else:
        status, accepted, why = "NO_GAIN", False, "no material reducibility gain over the raw encoding."
    return ReducibilityVerdict(representation=representation.name, baseline_accuracy=baseline, accuracy=acc,
                               control_accuracy=ctrl, accepted=accepted, status=status, why=why)


def invent_representation(candidates: List[Representation], solver: Callable, instances: Sequence,
                          labels: Sequence, margin: float = 0.15) -> List[ReducibilityVerdict]:
    """Try each candidate representation and keep those that REDUCE the problem (pass the control), most-reducing
    first. The returned verdicts carry the full evidence — a representation is presented as a new notation only
    when the world (solver + control) certifies it, never on looking clever."""
    verdicts = [representation_reducibility(r, solver, instances, labels, margin=margin) for r in candidates]
    return sorted(verdicts, key=lambda v: (-int(v.accepted), -v.reducibility))
