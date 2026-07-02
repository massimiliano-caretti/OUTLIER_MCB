"""self_diagnosis — point-logs + a SEPARATE diagnostic memory so the engine can autodiagnose its own failures.

When a task is NOT completed, the post-mortem is the asset: WHERE was the engine weak, WHAT did not work, WHERE
were the bottlenecks. This module gives the engine a place to drop diagnostic POINTS during a run (a keylog),
a separate persistent memory for them (kept apart from DiscoveryMemory / EvolutionMemory, which hold results),
and `self_diagnose` to mine the log into a ranked picture of weak spots and the dominant bottleneck — the
input a self-repair step (see self_repair.py) then acts on, under the never-regress rule.

Honest + deterministic: a point carries an integer `seq` (no wall-clock), persistence is sorted JSON, and
`self_diagnose` only REPORTS — it does not fix. A failure is information, never discarded.
"""
from __future__ import annotations
import json
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# OK = went fine · WEAK = worked but poorly · BOTTLENECK = the slow/limiting step · BLOCKED = a gate stopped it
# · FAILED = the step did not produce its result
POINT_STATUSES = ("OK", "WEAK", "BOTTLENECK", "BLOCKED", "FAILED")
NON_OK = ("WEAK", "BOTTLENECK", "BLOCKED", "FAILED")
# severity weights — how much each non-OK status counts toward 'this phase is the problem'
_SEVERITY = {"OK": 0, "WEAK": 1, "BOTTLENECK": 3, "BLOCKED": 3, "FAILED": 4}


@dataclass
class DiagnosticPoint:
    seq: int
    phase: str
    status: str
    label: str
    detail: str = ""
    metric: str = ""
    value: Optional[float] = None

    def __post_init__(self):
        if self.status not in POINT_STATUSES:
            raise ValueError(f"status must be one of {POINT_STATUSES}, got '{self.status}'")


@dataclass
class DiagnosticLog:
    """A keylog for ONE task run. Drop points as the run proceeds; mark whether the task completed."""
    task: str
    run_id: str = ""
    points: List[DiagnosticPoint] = field(default_factory=list)
    completed: bool = False
    _seq: int = 0

    def point(self, phase: str, status: str, label: str, detail: str = "", metric: str = "",
              value: Optional[float] = None) -> DiagnosticPoint:
        p = DiagnosticPoint(self._seq, phase, status, label, detail, metric, value)
        self._seq += 1
        self.points.append(p)
        return p

    # convenience shorthands
    def ok(self, phase, label, **k):         return self.point(phase, "OK", label, **k)
    def weak(self, phase, label, **k):       return self.point(phase, "WEAK", label, **k)
    def bottleneck(self, phase, label, **k): return self.point(phase, "BOTTLENECK", label, **k)
    def blocked(self, phase, label, **k):    return self.point(phase, "BLOCKED", label, **k)
    def failed(self, phase, label, **k):     return self.point(phase, "FAILED", label, **k)

    def mark_completed(self, done: bool = True) -> None:
        self.completed = bool(done)

    def unresolved(self) -> List[DiagnosticPoint]:
        return [p for p in self.points if p.status in NON_OK]

    def to_dict(self) -> Dict:
        return {"task": self.task, "run_id": self.run_id, "completed": self.completed,
                "points": [p.__dict__ for p in self.points]}

    @classmethod
    def from_dict(cls, d: Dict) -> "DiagnosticLog":
        log = cls(task=d.get("task", ""), run_id=d.get("run_id", ""), completed=d.get("completed", False))
        log.points = [DiagnosticPoint(**p) for p in d.get("points", [])]
        log._seq = (max((p.seq for p in log.points), default=-1) + 1)
        return log


@dataclass
class DiagnosticMemory:
    """The SEPARATE memory for diagnostics (failures/weaknesses/bottlenecks), distinct from the result memories.
    Persistent, deterministic JSON, so post-mortems compound across runs and feed self-repair."""
    runs: List[Dict] = field(default_factory=list)
    _counter: int = 0

    def record(self, log: DiagnosticLog) -> str:
        if not log.run_id:
            log.run_id = f"run{self._counter}"
        self._counter += 1
        self.runs.append(log.to_dict())
        return log.run_id

    def all_points(self) -> List[DiagnosticPoint]:
        return [DiagnosticPoint(**p) for r in self.runs for p in r.get("points", [])]

    def unresolved_runs(self) -> List[Dict]:
        """Runs that did NOT complete, or that left a non-OK point — the ones worth diagnosing."""
        return [r for r in self.runs
                if not r.get("completed", False)
                or any(p["status"] in NON_OK for p in r.get("points", []))]

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"runs": self.runs, "counter": self._counter}, f, indent=2, sort_keys=True, ensure_ascii=False)

    @classmethod
    def load(cls, path: str) -> "DiagnosticMemory":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        m = cls(runs=data.get("runs", []))
        m._counter = data.get("counter", len(m.runs))
        return m


@dataclass
class PhaseWeakness:
    phase: str
    severity: int                # summed severity of non-OK points in this phase
    counts: Dict[str, int]       # status -> count
    examples: List[str]          # a few labels


@dataclass
class DiagnosisReport:
    weak_spots: List[PhaseWeakness] = field(default_factory=list)
    bottleneck_phase: str = ""
    dominant_failure: str = ""
    unresolved_runs: int = 0
    total_runs: int = 0
    next_lever: str = ""

    @property
    def healthy(self) -> bool:
        return not self.weak_spots and self.unresolved_runs == 0

    def markdown(self) -> str:
        if self.healthy:
            return "## Self-diagnosis — no weak spots recorded (nothing to repair)"
        L = [f"## Self-diagnosis — {self.unresolved_runs}/{self.total_runs} runs unresolved",
             f"- **bottleneck phase:** {self.bottleneck_phase or '—'}",
             f"- **dominant failure:** {self.dominant_failure or '—'}"]
        for w in self.weak_spots[:6]:
            L.append(f"  • **{w.phase}** (severity {w.severity}) — {w.counts}; e.g. {', '.join(w.examples[:2])}")
        if self.next_lever:
            L.append(f"- **next lever:** {self.next_lever}")
        return "\n".join(L)


def self_diagnose(source) -> DiagnosisReport:
    """Mine a DiagnosticMemory (or a single DiagnosticLog) into a ranked picture of weak spots and the dominant
    bottleneck. Reports only — the fix is self_repair's job, gated by never-regress + protected invariants."""
    if isinstance(source, DiagnosticLog):
        points = list(source.points)
        runs = [source.to_dict()]
    elif source is None:
        points, runs = [], []                     # ERGONOMICS (#15): nothing recorded yet → an empty report
    elif hasattr(source, "all_points"):
        points = source.all_points()
        runs = source.runs
    else:
        # a repo path or bare string is a common mistake — self_diagnose consumes a DiagnosticMemory/Log, not
        # a repo. Fail with a message that says exactly that, instead of an opaque AttributeError.
        raise TypeError("self_diagnose expects a DiagnosticMemory or DiagnosticLog (or None), not "
                        f"{type(source).__name__}; run diagnostics first and pass the resulting memory.")

    by_phase: Dict[str, Dict[str, int]] = {}
    examples: Dict[str, List[str]] = {}
    for p in points:
        if p.status == "OK":
            continue
        by_phase.setdefault(p.phase, {})
        by_phase[p.phase][p.status] = by_phase[p.phase].get(p.status, 0) + 1
        examples.setdefault(p.phase, [])
        if p.label not in examples[p.phase]:
            examples[p.phase].append(p.label)

    weak = []
    for phase, counts in by_phase.items():
        severity = sum(_SEVERITY[s] * n for s, n in counts.items())
        weak.append(PhaseWeakness(phase=phase, severity=severity, counts=dict(sorted(counts.items())),
                                  examples=examples.get(phase, [])))
    # deterministic ordering: worst severity first, then phase name
    weak.sort(key=lambda w: (-w.severity, w.phase))

    bottleneck = ""
    if weak:
        # the bottleneck is the phase with the most BOTTLENECK/BLOCKED weight (the limiting step), else worst severity
        def block_weight(w: PhaseWeakness) -> int:
            return w.counts.get("BOTTLENECK", 0) * 3 + w.counts.get("BLOCKED", 0) * 3
        ranked_block = sorted(weak, key=lambda w: (-block_weight(w), -w.severity, w.phase))
        bottleneck = ranked_block[0].phase if block_weight(ranked_block[0]) else weak[0].phase

    # dominant failure: the most frequent FAILED/BLOCKED (phase: label)
    fail_counts: Dict[str, int] = {}
    for p in points:
        if p.status in ("FAILED", "BLOCKED"):
            key = f"{p.phase}: {p.label}"
            fail_counts[key] = fail_counts.get(key, 0) + 1
    dominant = max(sorted(fail_counts), key=lambda k: fail_counts[k]) if fail_counts else ""

    unresolved = sum(1 for r in runs
                     if not r.get("completed", False)
                     or any(pt["status"] in NON_OK for pt in r.get("points", [])))
    next_lever = ""
    if weak:
        top = weak[0]
        next_lever = (f"attack the '{bottleneck or top.phase}' phase first (highest severity {top.severity}); "
                      "propose a repair, then accept it ONLY if no protected invariant breaks and the metric "
                      "does not regress (self_repair.evolutionary_self_repair).")
    return DiagnosisReport(weak_spots=weak, bottleneck_phase=bottleneck, dominant_failure=dominant,
                           unresolved_runs=unresolved, total_runs=len(runs), next_lever=next_lever)


@contextmanager
def diagnostic_run(task: str, memory: Optional[DiagnosticMemory] = None, run_id: str = ""):
    """Context manager: open a keylog for a task; on exit, record it into `memory` (if given). The log is
    recorded even if the body raises — a crash is exactly the post-mortem worth keeping."""
    log = DiagnosticLog(task=task, run_id=run_id)
    try:
        yield log
    finally:
        if memory is not None:
            memory.record(log)
