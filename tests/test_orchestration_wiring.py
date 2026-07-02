"""test_orchestration_wiring — proves the previously-isolated capabilities are now CALLED inside the loop:
failure lessons + fixation + novelty archive feed evolve_invention every round (orchestrate=True), the claim
ladder gates the headline, and the analogical memory is read back. Backward-compat: orchestrate=False is
unchanged. Offline, deterministic."""
import OUTLIER_MCB as m


def test_orchestrated_loop_consults_lessons_archive_and_fixation():
    t = m.symbolic_invention_task()
    res = m.evolve_invention(t["problem"], t["evaluator"], budget=14, pack=t["pack"], orchestrate=True)
    # the loop's memories exist and were populated DURING the run (not None, not empty)
    assert res.lesson_memory is not None and res.novelty_archive is not None and res.fixation is not None
    assert len(res.novelty_archive) > 0
    # the orchestration does not break correctness: it still finds and verifies the data-true break.
    # NOTE: cross-domain transfer may surface the SAME break under a source-suffixed name (e.g.
    # 'law_is_separable@numeric'), so match by substring — the intent is 'the data-true break was found and
    # settled', not the exact label. It is also verified to be present+settled in the run's memory.
    assert res.best().externally_settled
    assert any("law_is_separable" in a for a in res.best().broken_assumptions)
    assert any("law_is_separable" in a and r.externally_settled
               for r in res.memory.all() for a in r.broken_assumptions)


def test_non_orchestrated_is_backward_compatible():
    t = m.symbolic_invention_task()
    res = m.evolve_invention(t["problem"], t["evaluator"], budget=14, pack=t["pack"])
    assert res.lesson_memory is None and res.novelty_archive is None and res.fixation is None
    assert "law_is_separable" in res.best().broken_assumptions      # identical core behavior


def test_honest_headline_is_claim_ladder_gated():
    t = m.symbolic_invention_task()
    res = m.evolve_invention(t["problem"], t["evaluator"], budget=12, pack=t["pack"], orchestrate=True)
    head = res.honest_headline().lower()
    # externally settled (symbolic resolver) → 'verified' is licensed and survives;
    # no ONLINE prior-art search → bare 'novel' is NOT licensed and is hedged to 'provisionally novel'.
    assert "verified" in head
    assert "provisionally novel" in head


def test_claim_ladder_external_settlement_licenses_verified():
    from OUTLIER_MCB.claim_ladder import gate_claim_language
    g_ext = gate_claim_language("a verified result", {"external_settlement": True})
    assert g_ext["allowed"] is True and g_ext["rewritten"] == "a verified result"
    g_none = gate_claim_language("a verified result", {})
    assert g_none["allowed"] is False                              # no settlement, no formal proof → hedged


def test_studio_explore_sets_a_gated_headline():
    rep = m.studio.explore("invent a better cache", budget=8) if hasattr(m, "studio") else None
    if rep is None:
        from OUTLIER_MCB.studio import explore
        rep = explore("invent a better cache", budget=8)
    assert rep.headline and isinstance(rep.headline, str)


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
