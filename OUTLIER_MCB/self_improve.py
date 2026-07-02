"""self_improve — the central test: OUTLIER_MCB uses its OWN tools to propose improvements to itself.

This is the recursive loop the whole project is for. It runs the open-ended creative search on the problem
"how should OUTLIER_MCB improve?", then TRIAGES every proposal through the honesty machinery:

  • judge()        — drop INSIDE_THE_BOX proposals (they break no assumption → not real improvements);
  • novelty_audit  — drop RENAMED/COLLAGE proposals (rebranding of capabilities already present);
  • the result is a list of proposals that MUST_BE_AUDITED — each with the assumption it breaks and the
    world-test that would settle it. It NEVER auto-implements: a human decides, and only a proposal with a
    test + metric + ablation + reason earns its place (the project's own acceptance bar).

Honest by construction: it does not claim the survivors are novel or correct — only that they are not
obviously inside the box or obvious renames. Deterministic. Collaborators: creative_search, judge, novelty.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional

_PROBLEM = ("find architectural improvements to OUTLIER_MCB that increase verifiable creativity, novelty "
            "audit, and quality-diversity without creating decorative metrics")


@dataclass
class SelfImprovementProposal:
    idea: str
    breaks_assumption: str
    verdict: str                 # INSIDE_THE_BOX | MUST_BE_AUDITED | NEEDS_DISAMBIGUATION
    novelty_status: str = ""     # RENAMED | COLLAGE | NO_PRIOR_ART_FOUND | "" (no provider)
    accepted: bool = False       # survives the box-gate and the rebranding-gate
    world_test: str = ""


@dataclass
class SelfImprovementReport:
    problem: str
    proposals: List[SelfImprovementProposal] = field(default_factory=list)
    qd_coverage: int = 0
    def accepted(self) -> List[SelfImprovementProposal]:
        return [p for p in self.proposals if p.accepted]
    def markdown(self) -> str:
        acc = self.accepted()
        L = [f"## self-improvement — «{self.problem}»",
             f"- {len(self.proposals)} proposals · {len(acc)} survive (not inside-the-box, not a rename) · "
             f"QD coverage {self.qd_coverage}",
             "- NOTE: survivors are MUST_BE_AUDITED, never auto-implemented — a human settles each by its world-test."]
        for p in acc[:10]:
            L.append(f"  • breaks **{p.breaks_assumption or '—'}** → «{p.idea[:90]}»  ({p.verdict})")
        return "\n".join(L)


def propose_self_improvements(budget: int = 30, provider=None, repo_path: Optional[str] = None) -> SelfImprovementReport:
    """Run the recursive self-improvement loop and return the triaged proposals. With a `provider` (a real
    prior-art search), rebranding/collage proposals are also dropped; without one, only the box-gate applies."""
    from .creative_search import creative_search
    from .judge import judge
    from .pack import select_pack
    pack, _ = select_pack(_PROBLEM)
    repo = None
    if repo_path is not None:
        from .grounding import probe
        repo = probe(repo_path)
    res = creative_search(_PROBLEM, budget=budget, pack=pack, repo=repo)

    proposals: List[SelfImprovementProposal] = []
    seen = set()
    for _cell, _q, cand in res.archive.elites():
        idea = cand.negation
        if idea in seen:
            continue
        seen.add(idea)
        j = judge(idea, prompt=_PROBLEM, repo_path=repo_path, provider=provider)
        novelty_status = j.novelty.status if getattr(j, "novelty", None) else ""
        # accept iff it breaks the box AND is not an obvious rename/collage of an existing capability
        accepted = (j.verdict == "MUST_BE_AUDITED") and (novelty_status not in ("RENAMED", "COLLAGE"))
        proposals.append(SelfImprovementProposal(
            idea=idea, breaks_assumption=(j.broken_assumption or ""), verdict=j.verdict,
            novelty_status=novelty_status, accepted=accepted,
            world_test=(j.dossier.world.success_condition if getattr(getattr(j, "dossier", None), "world", None) else "")))
    return SelfImprovementReport(problem=_PROBLEM, proposals=proposals, qd_coverage=res.archive.coverage())
