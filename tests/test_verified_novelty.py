"""The self-improvement fitness the engine designed for itself: VERIFIED-novelty (external resolver decides).

judge (meta pack) ruled a richer internal composite INSIDE_THE_BOX and pointed at `the_engine_judges_itself`:
only an external resolver certifies. So the fitness is a single externally-settled signal — the fraction of
proposals that BOTH break a box AND survive an external resolver. Self-judged novelty never counts.

Key negative control: padding the population with self-judged (unverified) novelty LOWERS the verified fitness,
so `evolutionary_self_repair` REFUSES it (never-regress) — gaming is structurally impossible.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import OUTLIER_MCB as g
from OUTLIER_MCB.verified_novelty import (Proposal, verified_novelty, verified_novelty_fitness,
                                             assess_proposal)
from OUTLIER_MCB.self_repair import evolutionary_self_repair, RepairProposal, verify_invariants

_CERT = {"status": "NUMERIC_VERIFIED"}     # an external certificate (any field's resolver works)


def test_only_novel_and_certified_counts():
    pop = [
        Proposal("verified-novel", breaks_box=True, certificate=_CERT),       # counts
        Proposal("novel-but-unverified", breaks_box=True, certificate=None),  # self-judged → does NOT count
        Proposal("certified-but-not-novel", breaks_box=False, certificate=_CERT),  # not novel → does NOT count
    ]
    rep = verified_novelty(pop)
    assert rep.verified_novel == 1 and rep.n == 3
    assert rep.verified_novelty_rate == round(1 / 3, 4)
    assert verified_novelty_fitness(pop) == rep.verified_novelty_rate


def test_external_verification_is_load_bearing_anti_gaming_ablation():
    # with an unverified-novel proposal present, self-judged novelty would over-count → the gap is positive
    pop = [Proposal("v", True, _CERT), Proposal("u", True, None)]
    rep = verified_novelty(pop)
    assert rep.novelty_only_rate == 1.0           # self-judged would count BOTH
    assert rep.verified_novelty_rate == 0.5       # external resolver counts only the certified one
    assert rep.gaming_gap == 0.5                  # verification flips the decision → not decorative


def test_assess_proposal_uses_the_library_judge():
    box_breaker = assess_proposal("measure the rate by request cost instead of by the time window",
                                  pack=g.get_pack("coding"), certificate=_CERT)
    assert box_breaker.breaks_box and box_breaker.verified_novel
    inside = assess_proposal("add more logging to the limiter", pack=g.get_pack("coding"))
    assert not inside.breaks_box                   # breaks no assumption → INSIDE_THE_BOX → not novelty


def test_padding_with_self_judged_novelty_is_refused_by_self_repair():
    """Gaming attempt: add an unverified-novel proposal. It LOWERS the verified rate → never-regress rejects it."""
    state = {"pop": [Proposal("v", True, _CERT), Proposal("u", True, None)]}   # fitness 0.5
    measure = lambda: verified_novelty_fitness(state["pop"])

    # a HONEST repair: replace the unverified one with a verified one → fitness 0.5 → 1.0 → accepted
    good = RepairProposal("verify-it", apply=lambda: state.__setitem__("pop", [Proposal("v", True, _CERT),
                                                                               Proposal("v2", True, _CERT)]),
                          rollback=lambda: state.__setitem__("pop", [Proposal("v", True, _CERT),
                                                                     Proposal("u", True, None)]))
    r1 = evolutionary_self_repair(good, measure=measure)
    assert r1.accepted and r1.after > r1.before

    # a GAMING repair: pad with more self-judged novelty → fitness drops → rejected + rolled back
    base = list(state["pop"])
    bad = RepairProposal("pad-self-judged", apply=lambda: state.__setitem__("pop", state["pop"] + [
                             Proposal("u2", True, None), Proposal("u3", True, None)]),
                         rollback=lambda: state.__setitem__("pop", base))
    r2 = evolutionary_self_repair(bad, measure=measure)
    assert not r2.accepted and r2.regressed and r2.rolled_back


def test_anti_circularity_is_a_protected_invariant():
    rep = verify_invariants()
    assert rep.ok and "fitness_requires_external_verification" in rep.passed_names
