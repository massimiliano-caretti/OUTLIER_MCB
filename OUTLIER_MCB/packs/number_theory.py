"""packs/number_theory — the hidden assumptions of the STANDARD attack on prime gaps.

This is the missing domain the engine diagnosed on itself (`pack_knowledge_is_in_the_engine`): the `math`
pack is only optimization (gradients/curvature), so a request about prime gaps routed to `generic` and the
engine had no hidden assumptions to break. This pack names the assumptions shared by the standard sieve
attack on bounded gaps between primes (Selberg / GPY / Maynard–Tao multidimensional sieve, large sieve), so a
new idea must break ONE of them — and, crucially, so the engine can route a parity-barrier idea to the
barrier gate (`barriers.py`) instead of re-proposing a dead route.

Verdicts are HEURISTIC priors distilled from the literature (the parity problem; Maynard–Tao), NOT validated
truth. The pack does NOT claim any conjecture is provable — it organizes WHICH assumption a partial result
breaks, which the falsification spine then attacks. Honest by construction: nothing here proves anything.
"""
from __future__ import annotations
from ..core import Assumption
from ..pack import DomainPack, register_pack

A = [
    Assumption(
        "weights_respect_parity",
        "The sieve weights respect parity — they cannot tell a number with an even vs odd count of prime factors.",
        "Every classical sieve weight is parity-respecting; it is the natural, elementary construction.",
        "A parity-BREAKING input (automorphic / bilinear-form / exponential-sum information) can separate primes "
        "from products of two primes, escaping the parity barrier the pure sieve cannot cross.",
        ["selberg_sieve", "gpy", "maynard_tao", "large_sieve"],
        "exhibit a method that, using a parity-breaking observable, certifiably does what the parity problem "
        "forbids a parity-respecting sieve (e.g. isolate primes among almost-primes) on a checkable instance."),
    Assumption(
        "attack_is_sieve_only",
        "The attack uses sieve methods alone — no input from L-functions / automorphic forms / spectral theory.",
        "Sieves are elementary and self-contained; pulling in automorphic machinery is heavier and less familiar.",
        "Coupling the sieve with automorphic / spectral / bilinear input reaches results a pure sieve cannot "
        "(the Bombieri–Vinogradov circle of ideas, Zhang's bound on gaps).",
        ["selberg_sieve", "large_sieve"],
        "a separation: a target provably out of reach for sieve-only methods, achieved once automorphic input is added."),
    Assumption(
        "bound_is_the_gap_value",
        "The objective is to drive the gap bound H straight to the literal target value (H=2 for twin primes).",
        "The conjecture asks for gap 2, so it feels natural to aim the proof directly at 2.",
        "The right objective is a MONOTONE sequence of finite, externally-certified bounds (H finite, then strictly "
        "smaller) — certified partial progress, decoupled from the unreachable endpoint.",
        ["gpy", "maynard_tao"],
        "a framework that certifies H finite and strictly improves it (7·10⁷ → 600 → 246) with each step settled "
        "externally, while never claiming H=2."),
    Assumption(
        "is_unconditional",
        "The result must be unconditional — no unproved hypotheses (GRH, Elliott–Halberstam).",
        "An unconditional theorem is the gold standard and the only thing one is 'allowed' to celebrate.",
        "Conditioning on EH/GEH yields strictly stronger certified bounds (Maynard: H≤12 under GEH) — a clearly "
        "labelled conditional lemma is real, certifiable progress, not cheating.",
        ["maynard_tao", "circle_method"],
        "a conditional lemma, certified under an EXPLICIT stated hypothesis, that strictly improves the conditional frontier."),
    Assumption(
        "correlations_are_independent",
        "Prime-tuple correlations are modeled as independent (the singular series factorizes cleanly).",
        "Independence makes the main term tractable and matches the heuristic prime density.",
        "Exploiting the correlation structure with COUPLED multidimensional weights over several shifts "
        "(Maynard–Tao) extracts strictly more than the independent model.",
        ["circle_method", "selberg_sieve"],
        "a coupled multidimensional weight that provably beats the best independent-model bound on the same target."),
]

_axes = {
    "STRUCTURE":   {"priority": 3, "verdict": "HEURISTIC: the parity structure of the weights is the deepest barrier — breaking it (parity-breaking input) is where escapes live."},
    "OBJECTIVE":   {"priority": 3, "verdict": "HEURISTIC: re-aim the objective from the endpoint to a MONOTONE certified bound — partial certified progress beats an all-or-nothing proof."},
    "REPRESENTATION":{"priority": 2, "verdict": "HEURISTIC: what machinery represents the attack (sieve-only vs sieve+automorphic) gates what is reachable."},
    "HYPOTHESIS":  {"priority": 2, "verdict": "HEURISTIC: a clearly-labelled conditional hypothesis (EH/GEH) buys a stronger certified lemma — honest, not cheating."},
    "MEASURE":     {"priority": 2, "verdict": "HEURISTIC: how correlations are measured (independent vs coupled) decides how much the main term yields."},
}
_dim = {
    "weights_respect_parity": "STRUCTURE",
    "bound_is_the_gap_value": "OBJECTIVE",
    "attack_is_sieve_only": "REPRESENTATION",
    "is_unconditional": "HYPOTHESIS",
    "correlations_are_independent": "MEASURE",
}
_edges = [
    ("weights_respect_parity", "blocks", "bound_is_the_gap_value",
     "the parity barrier blocks a parity-respecting sieve from reaching gap=2 directly"),
    ("attack_is_sieve_only", "if_false_requires", "automorphic_input",
     "escaping sieve-only needs automorphic / spectral input"),
    ("weights_respect_parity", "if_false_requires", "parity_breaking_observable",
     "breaking parity needs a non-sieve observable that sees factor parity"),
    ("is_unconditional", "if_false_requires", "stated_hypothesis",
     "a conditional improvement needs an explicit, labelled hypothesis (EH/GEH)"),
]

PACK = DomainPack(
    name="number_theory",
    keywords=[
        # English
        "prime", "primes", "twin", "twin primes", "prime gap", "prime gaps", "bounded gaps", "gap between primes",
        "sieve", "parity", "maynard", "zhang", "conjecture", "number theory", "almost prime",
        # Italian
        "primi", "numeri primi", "gemelli", "primi gemelli", "gap", "gap tra primi", "crivello", "parità",
        "congettura", "teoria dei numeri",
    ],
    box_name="the standard sieve attack on bounded prime gaps (Selberg / GPY / Maynard–Tao multidimensional sieve, "
             "parity-respecting weights, aiming straight at gap = 2)",
    assumptions=A,
    relations=_edges,
    dimension_of=_dim,
    box_assumptions={"weights_respect_parity", "attack_is_sieve_only", "bound_is_the_gap_value"},
    axes=_axes,
    known_families=["selberg_sieve", "gpy", "maynard_tao", "large_sieve", "circle_method", "automorphic_gl2"],
    info_kinds={
        "parity_breaking_observable": "a non-sieve observable that sees the parity of the number of prime factors → escapes the parity barrier.",
        "automorphic_input": "L-function / spectral / GL(2) input → reaches beyond sieve-only methods.",
        "stated_hypothesis": "an explicit hypothesis (EH/GEH/GRH) → buys a stronger, clearly-labelled CONDITIONAL lemma.",
        "coupled_weights": "multidimensional weights coupling several shifts (Maynard–Tao) → beats the independent model.",
    },
    failure_memory={},
    world_factory=None,
)
register_pack(PACK)
