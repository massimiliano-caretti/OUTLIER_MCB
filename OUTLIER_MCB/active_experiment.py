"""active_experiment — choose the NEXT experiment that best discriminates the competing hypotheses.

A generator proposes and evaluates; a SCIENTIST asks 'which test, run next, most reduces my uncertainty?'.
Given hypotheses that predict different outcomes on candidate experiments, the most informative experiment
is the one whose outcome the hypotheses most DISAGREE on (maximal expected information gain, normalized by
cost). This is the active-learning move that turns the engine from a generator into an investigator.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Experiment:
    name: str
    predicts: Dict[str, bool] = field(default_factory=dict)   # hypothesis name -> its predicted outcome
    cost: float = 1.0

    def markdown(self) -> str:
        return f"- **{self.name}** (cost {self.cost}) · EIG {expected_information_gain(self)}"


def expected_information_gain(experiment: Experiment) -> float:
    """[0,1]: the binary entropy of the hypotheses' predictions. 1.0 when they split 50/50 (the experiment
    fully discriminates them); 0.0 when they all agree (it tells you nothing new)."""
    preds = list(experiment.predicts.values())
    if not preds:
        return 0.0
    p = sum(1 for x in preds if x) / len(preds)
    if p in (0.0, 1.0):
        return 0.0
    return round(-(p * math.log2(p) + (1 - p) * math.log2(1 - p)), 3)


def disambiguation_score(experiment: Experiment) -> float:
    """How well the experiment tells the hypotheses apart — here, its expected information gain."""
    return expected_information_gain(experiment)


def cost_of_test(experiment: Experiment) -> float:
    return max(0.0, float(experiment.cost))


def next_best_experiment(experiments: List[Experiment]) -> Optional[Experiment]:
    """The experiment maximizing expected information gain PER unit cost — run this one next."""
    if not experiments:
        return None
    return max(experiments, key=lambda e: expected_information_gain(e) / max(0.1, cost_of_test(e)))
