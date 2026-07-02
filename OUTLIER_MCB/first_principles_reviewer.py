"""first_principles_reviewer — critique an idea from the STRUCTURE OF ITS OWN CLAIM, not from the pack.

`reviewer.attack()` can only object from a pack's `known_families`: on an axis the pack does not model —
network latency, dimensional consistency, tail cost, an unstated resource — it is silent. This module
breaks that hidden assumption ("a critique must be sourced from the known families"). It reads the claim's
LOGICAL FORM — universal quantifiers, comparatives, scale/monotonicity promises, robustness/safety
promises, novelty claims — and for each manufactures a FALSIFIABLE objection with a concrete world-test,
plus the always-present negation-of-the-claim test. Domain-blind by construction: it never consults the
pack, so it can raise the objection the pack cannot.

It GENERATES objections; it certifies nothing — each objection is a world-test the idea must still survive,
the same discipline as the rest of the engine. Pairs with reviewer.attack(): the attack card is what the
KNOWN families would say; this is what FIRST PRINCIPLES say when the families are silent.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class FalsifiableObjection:
    lens: str                # which logical form triggered it
    dimension: str           # the axis of attack it introduces (often one the pack does not model)
    objection: str           # the reviewer's line
    world_test: str          # the concrete, falsifiable test that would settle it

    def markdown(self) -> str:
        return (f"- **[{self.dimension}] {self.objection}**\n"
                f"    - falsifiable test: {self.world_test}")


@dataclass
class FirstPrinciplesCritique:
    idea: str
    objections: List[FalsifiableObjection] = field(default_factory=list)

    def dimensions(self) -> List[str]:
        return [o.dimension for o in self.objections]

    def markdown(self) -> str:
        L = [f"### First-principles reviewer — {self.idea}",
             "_objections derived from the claim's own logic, not from the pack's known families:_"]
        L += [o.markdown() for o in self.objections]
        return "\n".join(L)


# Each lens: (name, trigger words, dimension, objection, world-test). Plain-English triggers only — no
# pack token ever appears here, so the module stays domain-blind (and passes the agnosticism guard).
_LENSES = [
    ("universal_quantifier",
     ("all", "every", "each", "always", "never", "any ", "guarantee", "ensure", "ensures", "must ",
      "everyone", "100%", "no exception", "forall"),
     "COUNTEREXAMPLE",
     "A universal claim is refuted by a SINGLE counterexample.",
     "Adversarially search the input class the claim quantifies over; ONE input that violates it refutes "
     "the claim. Report the worst case and the failure rate, not the average."),
    ("comparative_performance",
     ("faster", "cheaper", "better", " more ", " less ", "lower", "higher", "reduce", "improv",
      "outperform", "efficient", "optimal", "speedup", "fewer", "scales better"),
     "UNMODELED_COST",
     "A 'better on X' claim hides the axis it pays on — the pack may not even model that axis.",
     "Measure an UNSTATED cost axis (tail latency p99, memory, $, energy, accuracy under distribution "
     "shift). If the idea wins on the stated metric but regresses on an unmodeled one, 'better' is false."),
    ("scale_monotonic",
     ("scale", "scalable", "linear", "constant time", "throughput", "unbounded", "o(", "arbitrary size",
      "any size", "grows", "indefinitely"),
     "REGIME",
     "A property true at small scale can break past a threshold.",
     "Increase the regime (N×, less supervision, adversarial load) until the property breaks; if it holds "
     "small and fails large it is not the claimed property — show the crossover, not one operating point."),
    ("robustness_safety",
     ("robust", "stable", "safe", "correct", "deterministic", "reliable", "consistent", "secure",
      "always works", "cannot fail", "provably"),
     "PERTURBATION",
     "A robustness/safety claim must survive perturbation within its own spec.",
     "Perturb inputs within the stated spec (noise, reordering, boundary and degenerate values); if the "
     "output changes, the property is not robust. Negative control: a perturbation that SHOULD change the "
     "output must — otherwise the test is inert."),
    ("novelty",
     ("novel", "new ", "first ", "unprecedented", "never seen", "breakthrough", "never-before"),
     "PRIOR_ART",
     "A novelty claim is refuted by one prior instance with the same MECHANISM.",
     "Search prior art over the full signature (mechanism, not name); a single close match downgrades the "
     "claim to a rename or a collage — absence of a match is provisional, never proof."),
]


def _triggered(text: str, words) -> bool:
    return any(w in text for w in words)


def first_principles_attack(idea: str, claim: str = "", breaks: Optional[List[str]] = None) -> FirstPrinciplesCritique:
    """Generate falsifiable objections from the claim's logical structure. `claim` defaults to `idea`.
    Always includes the negation-of-the-claim test (the falsifiability floor), so even a claim that
    triggers no lens still gets one concrete way to die."""
    text = f"{idea} {claim}".lower()
    objections: List[FalsifiableObjection] = []
    seen = set()
    for lens, words, dim, obj, test in _LENSES:
        if _triggered(text, words) and dim not in seen:
            seen.add(dim)
            objections.append(FalsifiableObjection(lens=lens, dimension=dim, objection=obj, world_test=test))
    # the falsifiability floor — present for EVERY idea: can it die at all?
    objections.append(FalsifiableObjection(
        lens="negation_of_claim", dimension="NEGATION",
        objection="Assume the claim is FALSE — what observation would we then expect?",
        world_test="State the observation expected if the claim were false, and design the experiment that "
                   "would PRODUCE it. If no such observation exists, the claim is unfalsifiable — and an "
                   "unfalsifiable claim is not an answer, however plausible."))
    return FirstPrinciplesCritique(idea=idea[:80], objections=objections)
