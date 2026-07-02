"""cognitive_growth — testable missing pieces for a stronger inventor.

These are not decorative "human" labels. Each function changes a decision under an external-ish check:

* causal imagination predicts counterfactual worlds and must collapse when the causal edge is shuffled;
* active experiment design picks the probe that separates rival world-models;
* role reputation prevents one weak panel role from dominating without evidence;
* executable skills must run and improve an objective task;
* artifact and taste gates keep discoveries materialized and worth pursuing.

All deterministic, zero-dependency, and conservative: they add pressure toward invention without weakening the
library's core rule that claims need settlement outside the model's own opinion.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class LinearCausalWorld:
    """A tiny structural causal model: node = bias + sum(parent * weight). Interventions override node values.

    It is intentionally small because its job is architectural: make "imagination" a falsifiable world-model,
    not a prose story. A shuffled edge set is the negative control.
    """
    equations: Dict[str, Tuple[float, Dict[str, float]]] = field(default_factory=dict)

    def simulate(self, inputs: Dict[str, float], interventions: Optional[Dict[str, float]] = None) -> Dict[str, float]:
        interventions = interventions or {}
        values = dict(inputs)
        values.update(interventions)  # interventions on exogenous variables override the observed baseline
        pending = dict(self.equations)
        for _ in range(len(pending) + 1):
            progressed = False
            for node, (bias, parents) in list(pending.items()):
                if node in interventions:
                    values[node] = interventions[node]
                    del pending[node]
                    progressed = True
                    continue
                if all(p in values for p in parents):
                    values[node] = bias + sum(values[p] * w for p, w in parents.items())
                    del pending[node]
                    progressed = True
            if not pending or not progressed:
                break
        if pending:
            raise ValueError(f"unresolved causal parents for {sorted(pending)}")
        return values

    def counterfactual_delta(self, inputs: Dict[str, float], intervention: Dict[str, float], outcome: str) -> float:
        base = self.simulate(inputs)
        changed = self.simulate(inputs, intervention)
        return round(changed[outcome] - base[outcome], 6)

    def shuffled(self) -> "LinearCausalWorld":
        """Negative control: keep weights but attach them to different parent names, breaking the mechanism."""
        names = sorted({p for _, parents in self.equations.values() for p in parents})
        if len(names) < 2:
            return LinearCausalWorld(self.equations)
        rotated = names[1:] + names[:1]
        swap = dict(zip(names, rotated))
        eq = {}
        for node, (bias, parents) in self.equations.items():
            eq[node] = (bias, {swap.get(p, p): w for p, w in parents.items()})
        return LinearCausalWorld(eq)


def counterfactual_world_prediction_collapses_when_edge_shuffled(world: LinearCausalWorld, inputs: Dict[str, float],
                                                                 intervention: Dict[str, float], outcome: str) -> bool:
    """True iff the causal prediction is load-bearing: the real edge predicts an effect and the shuffled control
    does not preserve that same effect."""
    real = world.counterfactual_delta(inputs, intervention, outcome)
    shuffled = world.shuffled().counterfactual_delta(inputs, intervention, outcome)
    return abs(real) > 1e-9 and abs(real - shuffled) > 1e-9


@dataclass
class CounterfactualExperiment:
    name: str
    intervention: Dict[str, float]
    outcome: str
    cost: float = 1.0


def experiment_splits_hypotheses_better_than_random_probe(worlds: Dict[str, LinearCausalWorld],
                                                          inputs: Dict[str, float],
                                                          experiments: List[CounterfactualExperiment]) -> Optional[CounterfactualExperiment]:
    """Pick the experiment whose predicted outcome deltas have the widest spread across rival worlds, per cost."""
    if not worlds or not experiments:
        return None

    def score(exp: CounterfactualExperiment) -> float:
        deltas = [w.counterfactual_delta(inputs, exp.intervention, exp.outcome) for w in worlds.values()]
        return (max(deltas) - min(deltas)) / max(0.1, exp.cost)

    return max(experiments, key=score)


@dataclass
class RoleReputation:
    role: str
    successes: int = 0
    attempts: int = 0

    @property
    def weight(self) -> float:
        return round((self.successes + 1) / (self.attempts + 2), 3)

    def record(self, success: bool) -> None:
        self.attempts += 1
        self.successes += int(success)


def role_vote_weight(role: str, evidence_strength: float, reputations: Dict[str, RoleReputation]) -> float:
    """A role cannot dominate from rhetoric alone: weight = evidence * calibrated role reputation."""
    rep = reputations.get(role, RoleReputation(role))
    return round(max(0.0, min(1.0, evidence_strength)) * rep.weight, 4)


@dataclass
class ExecutableSkill:
    name: str
    run: Callable[[object], object]
    verifier: Callable[[object, object], bool]
    attempts: int = 0
    successes: int = 0

    @property
    def success_rate(self) -> float:
        return round(self.successes / self.attempts, 3) if self.attempts else 0.5

    def execute(self, problem) -> object:
        result = self.run(problem)
        ok = bool(self.verifier(problem, result))
        self.attempts += 1
        self.successes += int(ok)
        if not ok:
            raise ValueError(f"skill {self.name!r} did not pass its verifier")
        return result


@dataclass(frozen=True)
class DiscoveryArtifact:
    kind: str
    location: str = ""
    verifier: str = ""
    passed: bool = False
    negative_control_passed: bool = False


def idea_without_artifact_cannot_enter_discovery_ledger(artifact: Optional[DiscoveryArtifact]) -> bool:
    """Admission gate for discovery ledgers. No material artifact + verifier + negative control ⇒ no entry."""
    return bool(artifact and artifact.location and artifact.verifier and artifact.passed and artifact.negative_control_passed)


def research_taste_score(compression: float, transfer: float, surprise: float, artifact: float,
                         false_claim_risk: float = 0.0, triviality: float = 0.0) -> float:
    """A transparent 'taste' proxy: prefer compact mechanisms that transfer and materialize; penalize hype/trivia."""
    core = 0.30 * compression + 0.25 * transfer + 0.20 * surprise + 0.25 * artifact
    penalty = 0.45 * false_claim_risk + 0.35 * triviality
    return round(max(0.0, min(1.0, core - penalty)), 4)


def taste_prefers_small_deep_mechanism_over_large_trivial_result() -> bool:
    deep = research_taste_score(compression=0.95, transfer=0.85, surprise=0.7, artifact=0.9,
                                false_claim_risk=0.05, triviality=0.05)
    large_trivial = research_taste_score(compression=0.2, transfer=0.1, surprise=0.2, artifact=1.0,
                                         false_claim_risk=0.05, triviality=0.8)
    return deep > large_trivial
