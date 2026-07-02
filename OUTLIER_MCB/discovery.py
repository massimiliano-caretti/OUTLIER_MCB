"""discovery — the Automated Scientist Loop (Point 4): orchestrate generation → settlement → portfolio.

This is the capstone that ties the data-settling evaluators (evaluators.symbolic, evaluators.causal)
into one autonomous loop, reusing the machinery that already exists: creative_search (FunSearch) as the
hypothesis generator, the QDArchive as the accumulating database, and an EXTERNAL evaluator as the
settler. It adds the one thing those parts lack — a high-level loop that runs the scientific method:

  GENERATE (creative_search) → VERIFY (the evaluator settles on the data) → ACCEPT (only what clears the
  gate AND whose controls collapse) → REFINE (nothing survived ⇒ escalate the search) → repeat.

The refinement discipline is Occam-then-escalate: start with a small budget (the simplest hypotheses,
closest to the box) and STOP as soon as a law clears the controls — parsimony, don't search harder than
the data demand. Only when a round yields nothing does the loop widen (the Reflexion move: a failed round
is the reason to escalate, not a crash). The loop never certifies by itself — a law is accepted only when
the evaluator's controls collapse, the same death-gate the rest of the engine uses.

Domain-blind by construction: `discover` knows nothing about formulas or confounders. The caller binds a
dataset into an evaluator and picks the pack; `discover` orchestrates. The same loop runs symbolic
regression and causal inference unchanged. Honest limits: it accepts what the evaluator's controls settle
and no more — `verifiability == "HUMAN"` evidence (e.g. latent confounding) is surfaced, never auto-certified.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from .creative_search import creative_search
from .qd import QDArchive


@dataclass
class DiscoveredLaw:
    """One accepted finding: a hypothesis that cleared the evaluator's controls, with its evidence and
    lineage. For symbolic the evidence carries the formula; for causal, the verdict and the
    confounding gap. Best-of-kind: at most one per distinct set of broken assumptions."""
    name: str
    score: float
    breaks: List[str]
    assumptions: List[str]
    evidence: Dict
    round: int
    lineage: List[str] = field(default_factory=list)

    def headline(self) -> str:
        ev = self.evidence
        if "formula" in ev:
            return f"law: {ev['formula']}  (held-out nrmse {ev.get('nrmse_holdout', '?')})"
        if "causal_verdict" in ev:
            return (f"causal: {ev['causal_verdict']} (effect {ev.get('effect', '?')}, "
                    f"confounding {ev.get('confounding_detected', '?')})")
        return f"score {self.score}"


@dataclass
class Discovery:
    problem: str
    laws: List[DiscoveredLaw]
    rounds: int
    archive: object                       # the accumulated QDArchive (a MAP of best-of-kind hypotheses)
    log: List[str] = field(default_factory=list)
    note: str = ""

    def best(self) -> Optional[DiscoveredLaw]:
        return self.laws[0] if self.laws else None

    def markdown(self) -> str:
        L = [f"## Automated Scientist Loop — «{self.problem}»",
             f"- rounds: {self.rounds} · accepted laws: {len(self.laws)} · "
             f"QD coverage: {self.archive.coverage()} cells"]
        if self.laws:
            L.append("\n### Accepted (best-of-kind, ranked; each cleared the controls)")
            for i, law in enumerate(self.laws, 1):
                human = " · ⚠ HUMAN (not auto-certified)" if law.evidence.get("verifiability") == "HUMAN" else ""
                L.append(f"{i}. **[{'×'.join(law.assumptions) or 'box'}]** score {law.score} "
                         f"· round {law.round}{human}")
                L.append(f"   - {law.headline()}")
        else:
            L.append("\n_No hypothesis cleared the controls — the data do not (yet) support a settled law._")
        if self.log:
            L.append("\n### Loop trace")
            L.extend(f"- {line}" for line in self.log)
        if self.note:
            L.append("\n" + self.note)
        return "\n".join(L)


def discover(problem: str, evaluator: Callable, pack, rounds: int = 4, base_budget: int = 12,
             accept_score: float = 0.7, require_controls: bool = True, escalate: float = 2.0,
             archive: Optional[QDArchive] = None) -> Discovery:
    """Run the autonomous discovery loop. `evaluator(candidate) -> {"score", **evidence}` settles each
    hypothesis on the data (bind a dataset into evaluators.symbolic_evaluator / causal_evaluator). `pack`
    supplies the assumptions to break. A finding is ACCEPTED iff its score ≥ `accept_score` and (when
    `require_controls`) its controls collapse. The loop early-exits the moment any law is accepted
    (parsimony); otherwise it escalates the budget by `escalate` and tries again, up to `rounds`.

    Returns a Discovery: the best-of-kind accepted laws (ranked), the accumulated QD archive, and a trace
    of the loop's reasoning."""
    arc = archive if archive is not None else QDArchive(pack=pack)
    accepted: Dict[tuple, DiscoveredLaw] = {}
    log: List[str] = []
    budget = float(base_budget)

    rnd = 0
    for rnd in range(1, rounds + 1):
        res = creative_search(problem, evaluator=evaluator, pack=pack, archive=arc, budget=int(budget))
        for rec in res.records:
            ev = rec.evidence or {}
            # HONESTY FIX (#5): a MISSING controls_collapse key means the controls were never run — that is
            # NOT the same as controls passing. Default to False so an evaluator that never emits a control
            # cannot get its "law" accepted under require_controls (the module's whole death-gate).
            controls = ev.get("controls_collapse", False)
            if rec.score >= accept_score and (controls or not require_controls):
                key = tuple(sorted(rec.candidate.assumptions)) or ("box",)
                prior = accepted.get(key)
                if prior is None or rec.score > prior.score:
                    accepted[key] = DiscoveredLaw(
                        name=rec.name, score=rec.score, breaks=list(rec.candidate.breaks),
                        assumptions=list(rec.candidate.assumptions), evidence=ev, round=rnd,
                        lineage=list(rec.operator_path))
        log.append(f"round {rnd}: budget {int(budget)}, evaluations {len(res.records)}, "
                   f"accepted-so-far {len(accepted)}")
        if accepted:
            log.append(f"round {rnd}: a law cleared the controls → stop (parsimony; do not over-search).")
            break
        budget *= escalate
        log.append(f"round {rnd}: nothing survived the controls → escalate the search to budget {int(budget)}.")

    laws = sorted(accepted.values(), key=lambda l: -l.score)
    auto = sum(1 for l in laws if l.evidence.get("verifiability") != "HUMAN")
    note = (f"Settled by the evaluator's controls, not by self-judgment. {auto}/{len(laws)} accepted "
            f"laws are AUTO; any HUMAN-flagged finding (e.g. latent confounding) is surfaced, never "
            f"auto-certified. The QD archive is the portfolio of best-of-kind hypotheses across rounds.")
    return Discovery(problem=problem, laws=laws, rounds=rnd, archive=arc, log=log, note=note)
