"""#7 Cross-session composing memory — a failure in one session biases the next session's creative move.

Open-endedness needs cumulative memory: confirmed/refuted assumptions and their genealogy must compound, not
be forgotten per run. `DiscoveryMemory` recorded that, and the kernel's rarity ranking already consults a
pack's `failure_memory` — but nothing wired the two together. `invent(..., discovery_memory=…/discovery_path=…)`
loads the accumulated dead ends, re-ranks around them, and records each SETTLED outcome back. Competitors are
stateless per run.

Ablation: an assumption refuted in a PRIOR session is deprioritized in THIS session's ranking (a clean order
flip among equal-priority breaks); without the memory the order is unchanged.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import OUTLIER_MCB as gsl
from OUTLIER_MCB.discovery_memory import DiscoveryMemory
from OUTLIER_MCB.kernel import graph_of, _ranked_breakable


def _rank(pack):
    return _ranked_breakable(pack, graph_of(pack))


def test_memory_round_trips_and_marks_barren():
    dm = DiscoveryMemory()
    for _ in range(3):
        dm.record("tenant_independent", "OBJECTIVE", "coding", confirmed=False)
    path = os.path.join(tempfile.mkdtemp(), "dm.json")
    dm.save(path)
    reloaded = DiscoveryMemory.load(path)
    assert "tenant_independent" in {o.assumption for o in reloaded.barren()}
    assert "tenant_independent" in reloaded.as_failure_memory("coding")


def test_prior_session_refutation_deprioritizes_the_assumption():
    pack = gsl.get_pack("coding")
    # baseline: tenant_independent and time_windowed share priority 3 → tenant_independent first (by name)
    base = _rank(pack)
    assert base.index("tenant_independent") < base.index("time_windowed")

    # SESSION 1 refuted tenant_independent repeatedly → barren; persist
    dm = DiscoveryMemory()
    for _ in range(3):
        dm.record("tenant_independent", "OBJECTIVE", "coding", confirmed=False)
    path = os.path.join(tempfile.mkdtemp(), "dm.json")
    dm.save(path)

    # SESSION 2 consumes it: the worn break now ranks AFTER its equal-priority sibling
    inv = gsl.invent("a rate limiter", pack=pack, beam=5, rounds=2, discovery_path=path)
    assert "tenant_independent" in (inv.pack.failure_memory or {})
    worn = _rank(inv.pack)
    assert worn.index("tenant_independent") > worn.index("time_windowed")
    # and the original registry pack is untouched (we never mutate it)
    assert not (gsl.get_pack("coding").failure_memory or {})


def test_without_execute_nothing_is_recorded():
    """Honest: with no settlement (execute=False), no outcome is fabricated into the memory."""
    dm = DiscoveryMemory()
    gsl.invent("a rate limiter", pack=gsl.get_pack("coding"), beam=4, rounds=1, discovery_memory=dm)
    assert not dm.outcomes
