"""test_incubation — the delayed-insight step (Tier-2, T2.3): persisted fertile wins in DIFFERENT domains
reconnect offline into fresh cross-domain conjectures, and barren dead ends are reopened under a new axis.
All conjectures are TO BE FALSIFIED, never asserted. Deterministic and offline.
"""
import OUTLIER_MCB as gsl
from OUTLIER_MCB.discovery_memory import DiscoveryMemory


def _memory_with_two_distant_fertile_wins():
    mem = DiscoveryMemory()
    # a fertile break in a physics-ish domain on a 'representation' axis...
    for _ in range(3):
        mem.record("energy_is_conserved_locally", axis="representation", domain="physics", confirmed=True)
    # ...and a very different fertile break in an economics-ish domain on an 'incentive' axis
    for _ in range(3):
        mem.record("agents_optimize_private_utility", axis="incentive", domain="economics", confirmed=True)
    # plus a barren dead end on a third axis
    for _ in range(3):
        mem.record("supply_matches_demand_instantly", axis="timing", domain="economics", confirmed=False)
    return mem


def test_incubate_connects_distant_fertile_wins():
    mem = _memory_with_two_distant_fertile_wins()
    conns = gsl.incubate(mem, k=5, min_attempts=1)
    assert conns, "two distant fertile wins should incubate into at least one connection"
    c = conns[0]
    assert {c.left_domain, c.right_domain} == {"physics", "economics"}   # a genuinely CROSS-domain link
    assert 0.0 <= c.surprise <= 1.0 and c.conjecture                     # ranked, and a concrete thing to try


def test_incubate_ignores_near_identical_wins():
    mem = DiscoveryMemory()
    for _ in range(3):
        mem.record("cache_is_warm", axis="state", domain="coding", confirmed=True)
    for _ in range(3):
        mem.record("cache_is_warm", axis="state", domain="coding", confirmed=True)   # same assumption
    assert gsl.incubate(mem) == []                                       # nothing distant to connect


def test_revive_barren_reopens_under_a_new_axis():
    mem = _memory_with_two_distant_fertile_wins()
    revived = gsl.revive_barren(mem, min_attempts=1)
    assert revived, "a barren dead end should be reopenable under a fertile axis seen elsewhere"
    r = revived[0]
    assert r.assumption == "supply_matches_demand_instantly"
    assert r.new_axis != r.old_axis                                      # a genuinely DIFFERENT lens


def test_incubation_asserts_nothing_only_proposes():
    mem = _memory_with_two_distant_fertile_wins()
    for c in gsl.incubate(mem):
        # the conjecture must be framed as something to BREAK/settle, never a settled claim
        assert "break" in c.conjecture.lower() or "share" in c.conjecture.lower()
