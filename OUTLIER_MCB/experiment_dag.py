"""experiment_dag — settle a discovery by a STAGED chain of experiments, not one verdict.

A real finding rarely turns on a single test: first the baseline must provably FAIL, only then is it worth
showing the candidate passes the HIDDEN cases, and only then is surviving the RED TEAM meaningful. This
encodes that as a DAG: each experiment declares its prerequisites and runs only if they all passed. A
downstream experiment that never runs leaves the discovery UNSETTLED — honest by construction: the chain
must complete end-to-end before anything is called confirmed, and a single broken link blocks the rest.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


@dataclass
class Experiment:
    """One node. `run() -> bool | EvaluationResult | (bool, detail)` — anything truthy/`.passed` means passed.
    `requires` lists the names that must PASS before this one is allowed to run."""
    name: str
    run: Callable
    requires: List[str] = field(default_factory=list)
    description: str = ""


@dataclass
class ExperimentOutcome:
    name: str
    status: str                 # PASSED | FAILED | SKIPPED | ERROR
    passed: bool
    detail: str = ""
    blocked_by: List[str] = field(default_factory=list)

    def markdown(self) -> str:
        mark = {"PASSED": "✓", "FAILED": "✗", "SKIPPED": "·", "ERROR": "!"}.get(self.status, "?")
        extra = f" — {self.detail}" if self.detail else ""
        if self.blocked_by:
            extra += f" (blocked by {', '.join(self.blocked_by)})"
        return f"  {mark} **{self.name}** [{self.status}]{extra}"


@dataclass
class DAGReport:
    outcomes: List[ExperimentOutcome]
    order: List[str] = field(default_factory=list)

    @property
    def by_name(self) -> Dict[str, ExperimentOutcome]:
        return {o.name: o for o in self.outcomes}

    @property
    def all_passed(self) -> bool:
        return bool(self.outcomes) and all(o.passed for o in self.outcomes)

    @property
    def settled(self) -> bool:
        """The discovery is settled ONLY if every experiment ran and passed — no skip, no error, no failure."""
        return self.all_passed and all(o.status == "PASSED" for o in self.outcomes)

    def blocked(self) -> List[str]:
        return [o.name for o in self.outcomes if o.status in ("SKIPPED", "FAILED", "ERROR")]

    def conservative_statement(self) -> str:
        if self.settled:
            return "the full experiment chain ran and PASSED end-to-end — the result is settled by staged evidence."
        first = next((o for o in self.outcomes if not o.passed), None)
        where = f" (first broke at «{first.name}»)" if first else ""
        return ("the experiment chain did NOT complete — the result is UNSETTLED; a missing or failed stage is "
                f"not evidence of anything{where}.")

    def markdown(self) -> str:
        head = "settled (chain passed end-to-end)" if self.settled else "UNSETTLED (chain broke)"
        return "\n".join([f"## Experiment DAG — {head}"] + [o.markdown() for o in self.outcomes])


def _passed_of(result) -> (bool, str):
    """Normalize a run() return into (passed, detail). Accepts bool, an EvaluationResult-like, or (bool, str)."""
    if isinstance(result, tuple) and len(result) == 2:
        return bool(result[0]), str(result[1])
    if hasattr(result, "passed"):
        return bool(result.passed), str(getattr(result, "error", "") or "")
    return bool(result), ""


class ExperimentDAG:
    """Add experiments with prerequisites; `run()` executes them in dependency order, skipping any whose
    prerequisites did not all pass. Detects cycles and unknown prerequisites before running."""

    def __init__(self):
        self.experiments: Dict[str, Experiment] = {}
        self._order: List[str] = []

    def add(self, experiment: Experiment) -> "ExperimentDAG":
        if experiment.name in self.experiments:
            raise ValueError(f"duplicate experiment name: {experiment.name}")
        self.experiments[experiment.name] = experiment
        self._order.append(experiment.name)
        return self

    def add_step(self, name: str, run: Callable, requires: Optional[List[str]] = None,
                 description: str = "") -> "ExperimentDAG":
        return self.add(Experiment(name=name, run=run, requires=list(requires or []), description=description))

    def _topological_order(self) -> List[str]:
        for exp in self.experiments.values():
            for req in exp.requires:
                if req not in self.experiments:
                    raise ValueError(f"experiment «{exp.name}» requires unknown «{req}»")
        visited: Dict[str, int] = {}      # 0 = visiting, 1 = done
        order: List[str] = []

        def visit(n: str, stack: tuple):
            state = visited.get(n)
            if state == 1:
                return
            if state == 0:
                raise ValueError("cycle in experiment DAG: " + " -> ".join(stack + (n,)))
            visited[n] = 0
            for req in self.experiments[n].requires:
                visit(req, stack + (n,))
            visited[n] = 1
            order.append(n)

        for name in self._order:          # stable: insertion order breaks ties
            visit(name, ())
        return order

    def run(self) -> DAGReport:
        order = self._topological_order()
        outcomes: Dict[str, ExperimentOutcome] = {}
        for name in order:
            exp = self.experiments[name]
            unmet = [r for r in exp.requires if not (r in outcomes and outcomes[r].passed)]
            if unmet:
                outcomes[name] = ExperimentOutcome(name=name, status="SKIPPED", passed=False, blocked_by=unmet,
                                                   detail="prerequisite did not pass")
                continue
            try:
                passed, detail = _passed_of(exp.run())
                outcomes[name] = ExperimentOutcome(name=name, passed=passed,
                                                   status="PASSED" if passed else "FAILED", detail=detail)
            except Exception as exc:
                outcomes[name] = ExperimentOutcome(name=name, status="ERROR", passed=False,
                                                   detail=f"{type(exc).__name__}: {exc}")
        return DAGReport(outcomes=[outcomes[n] for n in order], order=order)
