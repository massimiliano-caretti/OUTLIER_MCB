"""verified_novelty — the fitness for recursive self-improvement, designed by running the engine on itself.

The naive fitness for "make a creativity engine self-improve" is a richer internal score (novelty × diversity
× …). `judge` (meta pack) rules that INSIDE_THE_BOX — a re-parameterization of "add more metrics", and it is
GAMEABLE: a loop that maximizes a self-judged score learns to hack the score, not to be creative. The break the
engine itself pointed to is self-judgment (the engine grading its own output): ONLY an external resolver certifies; self-judgment is
circular.

So the fitness here is a SINGLE, externally-settled, ungameable signal — the VERIFIED-NOVELTY RATE: the fraction
of proposals that BOTH break a known box AND survive an EXTERNAL resolver (a benchmark recovery, a repo test, the
data, a real prior-art search). Novelty is NEVER counted when self-judged. Diversity/novelty are not added as
weighted terms (that is the box); the external resolver is the GATE, not a multiplier.

It carries its own anti-gaming ablation: `novelty_only_rate` (self-judged novelty, ignoring verification) vs the
verified rate — the gap is exactly how much a circular fitness would over-reward. Used as the `measure` in
`evolutionary_self_repair`, it lets the library cycle on itself maximizing verified creativity, under the two
gates that can never be removed: never break a protected invariant, never regress.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .certificates import is_external_certificate


@dataclass
class Proposal:
    """One self-improvement proposal: did it break a known box, and did an EXTERNAL resolver certify it?
    `certificate` is an external certificate (certificates.Certificate / a dict with 'status' / None). A self
    score is NOT a certificate — only a real external resolver counts."""
    name: str
    breaks_box: bool
    certificate: object = None
    resolver: str = ""

    @property
    def externally_certified(self) -> bool:
        return is_external_certificate(self.certificate)

    @property
    def verified_novel(self) -> bool:
        """The only thing that counts: novel AND externally certified."""
        return self.breaks_box and self.externally_certified


@dataclass
class VerifiedNoveltyReport:
    n: int
    verified_novel: int          # break a box AND externally certified — the signal
    novel_unverified: int        # break a box but NOT certified (self-judged novelty — does NOT count)
    verified_novelty_rate: float # the single, externally-settled fitness signal
    novelty_only_rate: float     # the GAMEABLE baseline (counts self-judged novelty) — for the ablation

    @property
    def gaming_gap(self) -> float:
        """How much a self-judged fitness would OVER-reward: novelty-only minus verified. >0 ⇒ external
        verification is load-bearing (it flips which proposals count) — not a decorative metric."""
        return round(self.novelty_only_rate - self.verified_novelty_rate, 4)

    def markdown(self) -> str:
        return ("## Verified-novelty fitness (externally settled, ungameable)\n"
                f"- **verified-novelty rate: {self.verified_novelty_rate}** "
                f"({self.verified_novel}/{self.n} break a box AND survive an external resolver)\n"
                f"- self-judged novelty-only rate: {self.novelty_only_rate} "
                f"({self.novel_unverified} novel but UNVERIFIED — not counted)\n"
                f"- anti-gaming gap (how much self-judgment would inflate): {self.gaming_gap} "
                f"{'— external verification is load-bearing' if self.gaming_gap > 0 else '— no unverified novelty present'}")


def verified_novelty(proposals: List[Proposal]) -> VerifiedNoveltyReport:
    """The fitness report. The external resolver is the GATE: a proposal counts toward verified-novelty ONLY if
    it both breaks a box and is externally certified. Deterministic, ungameable by an internal score."""
    n = len(proposals)
    novel = [p for p in proposals if p.breaks_box]
    verified = [p for p in novel if p.externally_certified]
    denom = n or 1
    return VerifiedNoveltyReport(
        n=n, verified_novel=len(verified), novel_unverified=len(novel) - len(verified),
        verified_novelty_rate=round(len(verified) / denom, 4),
        novelty_only_rate=round(len(novel) / denom, 4))


def pareto_improves(old: Dict[str, float], new: Dict[str, float]) -> bool:
    """The Pareto gate for MULTI-METRIC self-improvement: accept a change ONLY if NO performance dimension
    regresses AND at least one strictly improves. This is how the engine gets genuinely better all-round — it
    can never trade one skill away for another (the honest meaning of 'improve, never regress').

    Key-set safety (never crash, never silently accept a regression): a dimension present in `old` but MISSING
    from `new` is the worst regression (a skill dropped to nonexistence) → reject, not KeyError. A brand-new
    dimension in `new` cannot by itself justify acceptance — otherwise adding a metric would game the gate — so
    improvement is measured on the dimensions `old` actually tracks."""
    if not old:
        return False
    if any(d not in new or new[d] < old[d] for d in old):   # a dropped or regressed dimension → reject
        return False
    return any(new[d] > old[d] for d in old)                # at least one tracked dimension strictly improves


def verified_novelty_fitness(proposals: List[Proposal]) -> float:
    """The single fitness number for recursive self-improvement: the verified-novelty rate. Pass this as the
    `measure` to `evolutionary_self_repair` — a change to the library is kept only if it RAISES verified novelty
    AND breaks no protected invariant AND does not regress. Maximizing it cannot be gamed by self-judgment,
    because only an external resolver moves it."""
    return verified_novelty(proposals).verified_novelty_rate


def assess_proposal(idea: str, name: str = "", pack=None, certificate=None, resolver: str = "") -> Proposal:
    """Build a Proposal by asking the library ITSELF whether the idea breaks a box (`judge`) — outlier_mcb at
    its own side. `breaks_box` is True only when judge returns MUST_BE_AUDITED (it broke a hidden assumption);
    INSIDE_THE_BOX / DEAD_BY_BARRIER / NEEDS_DISAMBIGUATION do NOT count as novelty. Certification is external,
    supplied via `certificate` (a real resolver's verdict)."""
    from .judge import judge
    verdict = judge(idea, pack=pack).verdict
    return Proposal(name=name or idea[:40], breaks_box=(verdict == "MUST_BE_AUDITED"),
                    certificate=certificate, resolver=resolver)
