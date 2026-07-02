"""affect — intrinsic motivation as FUNCTIONAL signals: curiosity toward the unknown, joy of surprise.

The honest framing first: this is NOT emotion, sentience, or decorative feeling-words (the `meta` pack
flags those as rigor theater, and the engine itself judged "attach emotion labels" as the trap). It is
intrinsic motivation in the computational sense — Schmidhuber's and Oudeyer's curiosity (reward the
unexplored / the learnable-surprise), and Bayesian surprise (information gain) — implemented as numbers
that CHANGE WHAT THE ENGINE DOES, then measured. Two signals, each earning its keep:

  • curiosity_score — a drive toward the UNKNOWN: high for what has been explored least. Folded into
    problem-finding, it makes the engine attack what it does not understand, not just exploit what pays
    (the 'generation is the bottleneck' break the engine surfaced: don't generate more, generate outward).
  • discovery_reward (the 'joy/pride' done right) — surprise × confirmation. A result that is BOTH
    surprising (it violated the prior) AND confirmed (it survived falsification) yields a strong reward; a
    predictable or unconfirmed one yields little. A surprising TRUTH teaches the most — so the engine
    amplifies learning from genuine discovery, and a run can report how much real discovery it found.

Plain rule: curiosity decides WHERE to look; surprise-confirmation decides how much a result was WORTH.
"""
from __future__ import annotations


def curiosity_score(seed: str, domain: str, memory=None, attempts_cap: int = 5) -> float:
    """Intrinsic interest in [0,1]: 1.0 for something never tried (pure unknown), decaying as attempts
    accumulate. With no memory everything is unknown (1.0). This is the drive toward the frontier."""
    if memory is None:
        return 1.0
    o = getattr(memory, "outcomes", {}).get(f"{domain}:{seed}")
    if o is None or o.attempted == 0:
        return 1.0
    return round(max(0.0, 1.0 - o.attempted / max(1, attempts_cap)), 3)


def bayesian_surprise(expected: float, observed: float) -> float:
    """How much an outcome violated expectation, in [0,1] — the information-gain proxy. expected is the
    prior fertility we held; observed is what happened (1 confirmed / 0 refuted, or a score). The bigger
    the gap, the more there was to learn."""
    return round(min(1.0, abs(float(observed) - float(expected))), 3)


def discovery_reward(surprise: float, confirmed: bool) -> float:
    """The joy/pride of discovery as a functional intrinsic reward: high ONLY when surprising AND confirmed.
    A surprising falsehood (refuted) or an unsurprising confirmation both teach little — and score low."""
    return round(max(0.0, min(1.0, surprise)) * (1.0 if confirmed else 0.15), 3)


def curious_worth(base_worth: float, curiosity_value: float, weight: float) -> float:
    """Blend an intrinsic curiosity drive into a task worth. weight=0 ⇒ unchanged (pure exploitation);
    weight=1 ⇒ pure curiosity (explore the unknown). The explore/exploit dial."""
    w = max(0.0, min(1.0, weight))
    return round((1.0 - w) * base_worth + w * curiosity_value, 3)
