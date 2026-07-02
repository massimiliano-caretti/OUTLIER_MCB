"""test_discovery_memory — the compounding advantage: confirmed/refuted assumptions shift future priors.

The memory accumulates assumption-level outcomes across sessions, persists, and feeds back: barren dead ends
sink (and saturate their axes) while fertile breaks rise in problem-finding. Without memory, ranking is
unchanged (non-regression).
"""
import os

import OUTLIER_MCB as gsl


def test_records_and_grades_outcomes():
    m = gsl.DiscoveryMemory()
    for _ in range(3):
        m.record("law_is_smooth", "REGULARITY", "numeric", confirmed=True)
    m.record("variables_are_raw", "FRAME", "numeric", confirmed=False)
    m.record("variables_are_raw", "FRAME", "numeric", confirmed=False)
    assert m.prior("law_is_smooth", "numeric") == 1.0
    assert m.outcomes["numeric:law_is_smooth"].status == "CONFIRMED_FERTILE"
    assert m.outcomes["numeric:variables_are_raw"].status == "REFUTED_BARREN"
    assert "FRAME" in m.barren_axes("numeric")


def test_as_failure_memory_feeds_the_kernel():
    m = gsl.DiscoveryMemory()
    m.record("law_is_polynomial", "BASIS", "numeric", confirmed=False)
    m.record("law_is_polynomial", "BASIS", "numeric", confirmed=False)
    fm = m.as_failure_memory("numeric")
    assert "law_is_polynomial" in fm and fm["law_is_polynomial"]["status"].startswith("DEAD")


def test_persistence_round_trip(tmp_path):
    m = gsl.DiscoveryMemory()
    m.record("law_is_smooth", "REGULARITY", "numeric", confirmed=True, note="paid off")
    m.promote("regime_switching", "REGIME", "numeric", note="from a transformation")
    p = str(tmp_path / "disc.mem")
    m.save(p)
    m2 = gsl.DiscoveryMemory.load(p)
    assert m2.prior("law_is_smooth", "numeric") == 1.0
    assert m2.discovered and m2.discovered[0]["assumption"] == "regime_switching"


def test_memory_shifts_problem_finding_priors():
    pack = gsl.get_pack("numeric")
    base = {p.seed: p.worth for p in gsl.find_problems(pack=pack, blend_with=[]).problems}
    m = gsl.DiscoveryMemory()
    for _ in range(3):                                   # smooth proved fertile; separable proved barren
        m.record("law_is_smooth", "REGULARITY", "numeric", confirmed=True)
        m.record("law_is_separable", "FORM", "numeric", confirmed=False)
    learned = {p.seed: p.worth for p in gsl.find_problems(pack=pack, blend_with=[], memory=m).problems}
    assert learned["law_is_smooth"] > base["law_is_smooth"]       # fertile rose
    assert learned["law_is_separable"] < base["law_is_separable"] # barren sank


def test_no_memory_is_unchanged():
    pack = gsl.get_pack("numeric")
    a = {p.seed: p.worth for p in gsl.find_problems(pack=pack, blend_with=[]).problems}
    b = {p.seed: p.worth for p in gsl.find_problems(pack=pack, blend_with=[], memory=None).problems}
    assert a == b                                        # opt-in: default path identical


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
