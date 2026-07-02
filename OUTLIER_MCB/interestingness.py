"""interestingness — a metric SEPARATE from novelty: new is not enough, it must be useful AND generative.

A thing can be new and stupid. Strong creativity is new + useful + opens a direction + falsifiable, minus
arbitrariness. This composite (Schmidhuber's interestingness, sharpened) keeps the engine from rewarding
mere difference. It is decomposable and explainable; it never replaces novelty_scope — it complements it.
"""
from __future__ import annotations
from typing import Dict


def _c(x) -> float:
    return max(0.0, min(1.0, float(x or 0)))


def interestingness_score(surprise: float = 0.0, opens_new_question: float = 0.0,
                          mechanism_transfer_distance: float = 0.0, falsifiability: float = 0.0,
                          usefulness: float = 0.0, arbitrariness: float = 0.0) -> Dict:
    """[0,1]: surprise (violates the baseline's prediction) + opens a new question + transfers a far
    mechanism + is falsifiable + is useful, MINUS arbitrariness. A novel-but-arbitrary or novel-but-useless
    idea scores low; a surprising, generative, falsifiable, useful one scores high."""
    comp = {"surprise": _c(surprise), "opens_new_question": _c(opens_new_question),
            "mechanism_transfer_distance": _c(mechanism_transfer_distance), "falsifiability": _c(falsifiability),
            "usefulness": _c(usefulness), "arbitrariness": _c(arbitrariness)}
    score = (0.25 * comp["surprise"] + 0.20 * comp["opens_new_question"]
             + 0.20 * comp["mechanism_transfer_distance"] + 0.15 * comp["falsifiability"]
             + 0.20 * comp["usefulness"] - 0.30 * comp["arbitrariness"])
    return {"interestingness": round(max(0.0, min(1.0, score)), 4), "components": comp}
