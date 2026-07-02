"""dossier — orchestrate the whole engine into ONE analysis per idea.

The library grew many capabilities that were exposed but never threaded into the flow: the theorem
sketch, the world-test, the reviewer attack, the lineage, the cascade, the compression, the maturity
verdict. A self-audit flagged this as the biggest missing logic — a pile of tools is not a pipeline.
`dossier(candidate, pack)` runs them all on a single idea and returns one coherent report: what it
claims, the world that would kill it, the reviewer's objection, what it descends from, the chain
reaction it unlocks, how much it compresses, and — finally — whether it is alive, suspended, or dead.

Collaborators: scoring, cascade, compression, theorem_sketch, world_designer, reviewer, lineage, maturity.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class Dossier:
    idea: str
    score: dict
    maturity: object
    compression: dict
    cascade: Optional[object] = None
    theorem: Optional[object] = None
    world_test: Optional[object] = None
    attack: Optional[object] = None
    lineage: Optional[object] = None
    def markdown(self) -> str:
        parts = [f"# Dossier — {self.idea}",
                 f"**maturity: {self.maturity.status}** — {self.maturity.note}",
                 f"**score:** composite {self.score['composite']} "
                 f"(novelty {self.score['novelty']} · depth {self.score['depth']} · "
                 f"useful {self.score['usefulness']} · risk {self.score['risk']} · cost {self.score['cost']})",
                 f"**compression:** {self.compression['principle']} (gain {self.compression['compression_gain']})"]
        if self.cascade and self.cascade.reach:
            parts.append("\n" + self.cascade.markdown())
        for section in (self.theorem, self.world_test, self.attack, self.lineage):
            if section is not None:
                parts.append("\n" + section.markdown())
        return "\n\n".join(parts)


def dossier(candidate, pack, repo=None) -> Dossier:
    """Assemble the full analysis of one candidate idea by threading every relevant module."""
    from .scoring import score_idea
    from .compression import compression_gain
    from .cascade import cascade
    from .theorem_sketch import sketch
    from .world_designer import design_world_test
    from .reviewer import attack as reviewer_attack
    from .lineage import declare_lineage
    from .maturity import assess

    axis = candidate.breaks[0] if candidate.breaks else ""
    seed = candidate.assumptions[0] if candidate.assumptions else ""
    in_pack = seed in pack.by_name()
    new_output = candidate.operator in ("unify", "instrument", "reframe")
    grounded = bool(repo is not None and getattr(repo, "grounded", False))

    score = score_idea(candidate, pack=pack, repo=repo)
    comp = compression_gain(candidate, pack)
    cas = cascade(pack, seed) if in_pack else None
    theorem = sketch(candidate.name, breaks=candidate.breaks, pack=pack,
                     assumption_name=(seed if in_pack else "")) if candidate.breaks else None
    world = design_world_test(axis, pack) if axis in pack.axes else None
    attack = reviewer_attack(candidate.name, pack, breaks=candidate.breaks, new_output=new_output)
    lineage = declare_lineage(candidate.name, pack, breaks=candidate.breaks, idea_text=candidate.negation)

    maturity = assess(
        breaks=candidate.breaks,
        has_executable_world_test=grounded,
        coherence=score["composite"],
        reduces_to=(lineage.inferred_family if lineage.inherits_death else None),
        new_output=new_output,
        open_questions=([f"does the cascade ({cas.reach}) actually unlock those breaks?"] if (cas and cas.reach) else []),
        what_would_make_it_testable=("" if grounded else "ground it in a repo (gsl.probe) or build the world-test SPEC."),
    )
    return Dossier(idea=candidate.name, score=score, maturity=maturity, compression=comp,
                   cascade=cas, theorem=theorem, world_test=world, attack=attack, lineage=lineage)
