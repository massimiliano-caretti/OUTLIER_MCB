"""experiment_loop — the EXECUTABLE active-experiment loop: ACQUIRE new information to shrink a hypothesis
space (Tier-2, T2.2; gap #2 'you cannot invent past your data without going to get new data').

active_experiment.py can already CHOOSE the most discriminating experiment (max expected information gain per
cost), but nothing produces the per-hypothesis predictions it consumes, and nothing RUNS the chosen experiment
and updates beliefs — so the capability sat inert. This closes the loop and makes it the one move that leaves
the training distribution honestly: it does not reason harder over fixed data, it goes and OBSERVES.

Given rival hypotheses (each predicts an outcome for each probe) and a set of world PROBES (each returns the
real observable), the loop repeatedly: builds the experiments from the CURRENTLY-ALIVE hypotheses, picks the
one whose outcome they most disagree on (next_best_experiment), RUNS it against the world, and eliminates every
hypothesis whose prediction contradicts what the world actually showed. Elimination is by the WORLD's outcome
only — never by self-judgment — so the loop cannot talk itself into an answer; it must observe its way to one.
It stops when one hypothesis survives, no discriminating experiment remains (EIG=0), or the probes run out.

Deterministic given the world. Composes Experiment + next_best_experiment; adds the executor + the belief
update the audit found missing.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from .active_experiment import Experiment, expected_information_gain, next_best_experiment


@dataclass
class Hypothesis:
    """A rival explanation. `predict(probe_name) -> bool` is what THIS hypothesis expects a probe to show."""
    name: str
    predict: Callable
    alive: bool = True


@dataclass
class RunStep:
    experiment: str
    eig: float
    outcome: bool
    eliminated: List[str] = field(default_factory=list)
    remaining: int = 0

    def markdown(self) -> str:
        killed = f" → eliminated {', '.join(self.eliminated)}" if self.eliminated else " → nothing eliminated"
        return f"- ran **{self.experiment}** (EIG {self.eig}) · world showed {self.outcome}{killed} · {self.remaining} left"


@dataclass
class ActiveExperimentResult:
    steps: List[RunStep] = field(default_factory=list)
    surviving: List[str] = field(default_factory=list)
    resolved: bool = False           # True ⇒ exactly one hypothesis survived (the world settled it)
    reason: str = ""

    def markdown(self) -> str:
        L = ["### Active experiment loop — acquired information until the world settled it"]
        L += [s.markdown() for s in self.steps]
        L.append(f"- **surviving:** {', '.join(self.surviving) or 'none'} — {self.reason}")
        return "\n".join(L)


def build_experiments(hypotheses: List[Hypothesis], probe_names: List[str]) -> List[Experiment]:
    """Turn ALIVE hypotheses' predictions into Experiments — the per-hypothesis `predicts` the selector needs.
    EIG is then computed over the CURRENT uncertainty, so the choice adapts as hypotheses are eliminated."""
    alive = [h for h in hypotheses if h.alive]
    out = []
    for name in probe_names:
        out.append(Experiment(name=name, predicts={h.name: bool(h.predict(name)) for h in alive}))
    return out


def run_active_experiments(hypotheses: List[Hypothesis], probes: Dict[str, Callable],
                           max_rounds: Optional[int] = None) -> ActiveExperimentResult:
    """Shrink the hypothesis space by ACQUIRING information. `probes[name]() -> bool` is the real world (the
    external oracle). Each round runs the most discriminating experiment and eliminates every hypothesis the
    world contradicts. Stops on a unique survivor, on no-discriminating-experiment (EIG=0), or on exhausted
    probes/rounds — the honest end conditions (the loop never invents a verdict the world did not give)."""
    res = ActiveExperimentResult()
    remaining_probes = list(probes.keys())
    rounds = 0
    while True:
        alive = [h for h in hypotheses if h.alive]
        if len(alive) <= 1:
            # CONFIRMATION (honest): survival-by-elimination is NOT proof — a lone survivor must not be
            # contradicted by any observation still available. Run the remaining probes against it; if any
            # contradicts, it dies too. Only then may we claim the world settled it.
            if len(alive) == 1 and remaining_probes:
                h = alive[0]
                for name in list(remaining_probes):
                    outcome = bool(probes[name]())
                    remaining_probes.remove(name)
                    contradicted = bool(h.predict(name)) != outcome
                    if contradicted:
                        h.alive = False
                    res.steps.append(RunStep(experiment=name, eig=0.0, outcome=outcome,
                                             eliminated=([h.name] if contradicted else []),
                                             remaining=sum(1 for x in hypotheses if x.alive)))
                    if contradicted:
                        break
                alive = [h for h in hypotheses if h.alive]
            # BUGFIX: 'resolved' requires at least one real OBSERVATION — a lone survivor never tested against
            # any probe is NOT settled (survival-by-elimination with zero evidence is not proof, per the module
            # contract). Distinguish: no hypotheses / lone-but-unobserved / confirmed / all-wrong.
            observed = len(res.steps) >= 1
            if not hypotheses:
                res.resolved, res.reason = False, "no hypotheses to disambiguate."
            elif len(alive) == 1 and observed:
                res.resolved, res.reason = True, ("one hypothesis survived AND was confirmed against every "
                                                  "observation made — the world settled it.")
            elif len(alive) == 1:
                res.resolved, res.reason = False, ("one hypothesis remains but NO observation was made (no "
                                                   "probes) — nothing is settled; acquire an observable.")
            else:
                res.resolved, res.reason = False, ("every hypothesis was contradicted by the world (the model "
                                                   "was wrong).")
            break
        if not remaining_probes:
            res.reason = "ran out of probes with several hypotheses still alive — need a NEW observable."
            break
        if max_rounds is not None and rounds >= max_rounds:
            res.reason = f"stopped after {max_rounds} rounds with {len(alive)} hypotheses still alive."
            break
        experiments = build_experiments(hypotheses, remaining_probes)
        exp = next_best_experiment(experiments)
        eig = expected_information_gain(exp) if exp else 0.0
        if exp is None or eig == 0.0:
            res.reason = "no remaining experiment discriminates the survivors — they agree on every probe left."
            break
        outcome = bool(probes[exp.name]())            # RUN it: observe the real world
        remaining_probes.remove(exp.name)
        rounds += 1
        eliminated = []
        for h in hypotheses:
            if h.alive and bool(h.predict(exp.name)) != outcome:
                h.alive = False
                eliminated.append(h.name)
        res.steps.append(RunStep(experiment=exp.name, eig=eig, outcome=outcome, eliminated=eliminated,
                                 remaining=sum(1 for h in hypotheses if h.alive)))
    res.surviving = [h.name for h in hypotheses if h.alive]
    return res
