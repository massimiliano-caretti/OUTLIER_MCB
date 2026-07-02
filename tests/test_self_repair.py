"""Evolutionary self-repair — keep a fix ONLY if no protected invariant breaks AND the metric never regresses.

GREEN: the real library's protected invariants all hold; a metric-improving repair with invariants intact is
accepted and advances the monotone frontier. Negative controls: a repair that breaks an invariant, and one
that regresses the metric, are both rejected and ROLLED BACK — and the failure is recorded in the diagnostic
memory. Never regress is verified by re-measurement, not assumed.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import OUTLIER_MCB as gsl
from OUTLIER_MCB.self_repair import (evolutionary_self_repair, RepairProposal, verify_invariants,
                                        library_health, ProtectedInvariant)
from OUTLIER_MCB.self_diagnosis import DiagnosticMemory
from OUTLIER_MCB.frontier_ledger import FrontierLedger


def test_real_library_invariants_all_hold():
    rep = verify_invariants()
    assert rep.ok, rep.markdown()
    assert library_health() == 1.0


class _Holder:
    def __init__(self):
        self.flag = True
        self.metric = 0.5


def _custom_invariant(holder):
    return [ProtectedInvariant("flag_true", lambda: (holder.flag, "flag must stay True"), "a solid behavior")]


def test_improving_repair_is_accepted_and_advances_frontier():
    h = _Holder()
    invs = _custom_invariant(h)
    led = FrontierLedger()
    prop = RepairProposal("boost", apply=lambda: setattr(h, "metric", 0.9),
                          rollback=lambda: setattr(h, "metric", 0.5), rationale="raise the metric")
    res = evolutionary_self_repair(prop, measure=lambda: h.metric, invariants=invs, ledger=led)
    assert res.accepted and res.advanced_frontier
    assert h.metric == 0.9 and led.best("library", "health") == 0.9


def test_repair_breaking_an_invariant_is_rejected_and_rolled_back():
    h = _Holder()
    invs = _custom_invariant(h)
    mem = DiagnosticMemory()
    # this repair would raise the metric but BREAK the protected invariant (flag → False)
    def apply():
        h.flag = False
        h.metric = 0.99
    def rollback():
        h.flag = True
        h.metric = 0.5
    prop = RepairProposal("sneaky", apply=apply, rollback=rollback, rationale="trades a solid invariant for score")
    res = evolutionary_self_repair(prop, measure=lambda: h.metric, invariants=invs, memory=mem)
    assert not res.accepted and res.rolled_back
    assert "flag_true" in res.broken_invariants
    assert h.flag is True and h.metric == 0.5                 # fully restored
    assert verify_invariants(invs).ok                          # the solid invariant is intact again
    assert len(mem.runs) == 1 and not mem.runs[0]["completed"]  # failure recorded


def test_regressing_repair_is_rejected_never_regress():
    h = _Holder()
    invs = _custom_invariant(h)
    prop = RepairProposal("worsen", apply=lambda: setattr(h, "metric", 0.2),
                          rollback=lambda: setattr(h, "metric", 0.5), rationale="lowers the metric")
    res = evolutionary_self_repair(prop, measure=lambda: h.metric, invariants=invs)
    assert not res.accepted and res.regressed and res.rolled_back
    assert h.metric == 0.5                                     # never regressed


def test_health_frontier_only_moves_forward_across_repairs():
    h = _Holder()
    invs = _custom_invariant(h)
    led = FrontierLedger()
    for target in (0.6, 0.75, 0.9):
        prev = h.metric
        evolutionary_self_repair(
            RepairProposal(f"to{target}", apply=lambda t=target: setattr(h, "metric", t),
                           rollback=lambda p=prev: setattr(h, "metric", p)),
            measure=lambda: h.metric, invariants=invs, ledger=led)
    assert led.best("library", "health") == 0.9
    # offering a worse certified value must not move the frontier back
    prev = h.metric
    evolutionary_self_repair(
        RepairProposal("regress", apply=lambda: setattr(h, "metric", 0.4),
                       rollback=lambda p=prev: setattr(h, "metric", p)),
        measure=lambda: h.metric, invariants=invs, ledger=led)
    assert led.best("library", "health") == 0.9               # frontier protected
