"""trace — an auditable record of HOW the engine reasoned (taken from OpenHands/SWE-agent's trace idea).

Without a trace you cannot tell reasoning from improvisation. A ReasoningTrace logs each ACTION with its
inputs, output, and the WHY; an EvidenceLedger keeps every claim tied to its source. Both render to JSON and
Markdown so a run is replayable and a reviewer can see the path, not just the answer.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class ActionStep:
    action: str
    why: str = ""
    inputs: str = ""
    output: str = ""
    evidence: Dict = field(default_factory=dict)

    def markdown(self) -> str:
        return f"- **{self.action}** — {self.why}" + (f"  → {self.output}" if self.output else "")


@dataclass
class ReasoningTrace:
    problem: str = ""
    steps: List[ActionStep] = field(default_factory=list)

    def log(self, action: str, why: str = "", inputs: str = "", output: str = "", evidence: Dict = None) -> ActionStep:
        s = ActionStep(action=action, why=why, inputs=inputs, output=output, evidence=evidence or {})
        self.steps.append(s)
        return s

    def to_dict(self) -> Dict:
        return {"problem": self.problem,
                "steps": [{"action": s.action, "why": s.why, "output": s.output, "evidence": s.evidence}
                          for s in self.steps]}

    def markdown(self) -> str:
        return "\n".join([f"### Reasoning trace — «{self.problem}» ({len(self.steps)} steps)"]
                         + [s.markdown() for s in self.steps])


@dataclass
class EvidenceLedger:
    """Every claim tied to its source — so 'novel' / 'verified' / 'improves' can be audited, not trusted."""
    entries: List[Dict] = field(default_factory=list)

    def add(self, claim: str, source: str, detail: str = "") -> None:
        self.entries.append({"claim": claim, "source": source, "detail": detail})

    def markdown(self) -> str:
        return "\n".join(["### Evidence ledger"]
                         + [f"- **{e['claim']}** ← {e['source']}" + (f" ({e['detail']})" if e["detail"] else "")
                            for e in self.entries])
