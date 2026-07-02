"""test_self_materialize — the engine closes the executive loop WITHOUT an LLM.

The settlement is settled by REAL execution in a private throwaway repo: a synthesized red-first test goes
RED_ASSERTION, a bounded repair takes it GREEN, and a structure-destroying negative control must stay RED.
No numbers are asserted that a fake could fabricate — each comes from a spawned pytest run.
"""
import OUTLIER_MCB as gsl


def test_settles_a_bare_claim_red_assertion_then_green():
    r = gsl.settle_by_materialization(claim="share one global budget across tenants by weighted fair queueing")

    assert r.status == "MECHANISM_SETTLED"
    assert r.red_kind == "RED_ASSERTION"     # a clean assertion failure, not an import/collection error
    assert r.green_final and r.repaired
    assert r.negative_control_holds          # the test binds to behaviour, not a constant
    assert r.red_green == 1.0 and r.red_assertion_green == 1.0 and r.repair_success == 1.0


def test_settles_a_real_invent_candidate():
    inv = gsl.invent("design a new rate limiter with fairness across tenants", beam=5, rounds=1)
    cand = inv.best()["candidate"]

    r = gsl.settle_by_materialization(cand)

    assert r.status == "MECHANISM_SETTLED"
    sc = r.score_components()
    for key in ("red_green", "red_assertion_green", "test_quality", "patch_substance", "repair_success"):
        assert sc[key] == 1.0, (key, sc)
    assert sc["settlement_mode"] == "synthesized_sandbox"


def test_synthesis_is_deterministic_and_candidate_specific():
    a1 = gsl.synthesize_artifact(claim="alpha")
    a2 = gsl.synthesize_artifact(claim="alpha")
    b = gsl.synthesize_artifact(claim="beta")

    assert a1.impl_patch == a2.impl_patch and a1.module == a2.module   # deterministic
    assert a1.module != b.module                                       # candidate-specific


def test_synthesized_test_is_high_quality_and_patch_is_substantive():
    art = gsl.synthesize_artifact(claim="cost-weighted admission control")
    from OUTLIER_MCB.llm_loop import test_quality_evidence
    from OUTLIER_MCB.patches import patch_substance_evidence

    tq = test_quality_evidence(art.test_patch, claim="cost weighted admission")
    assert tq["has_import"] and tq["has_concrete_value"] and tq["negative_control"]
    assert tq["score"] >= 0.8

    subst = patch_substance_evidence(art.test_patch, art.impl_patch)
    assert subst["touches_source"] and subst["score"] == 1.0


def test_leaves_no_trace_on_disk():
    import tempfile, os
    before = set(os.listdir(tempfile.gettempdir()))
    gsl.settle_by_materialization(claim="idempotent cleanup check")
    after = set(os.listdir(tempfile.gettempdir()))
    leaked = {d for d in (after - before) if d.startswith("gsl_selfmat_")}
    assert not leaked, leaked


def test_capability_is_registered_and_resolves():
    from OUTLIER_MCB.capabilities import _CAPS
    entries = {c.entry for c in _CAPS}
    assert "settle_by_materialization" in entries
    assert all(hasattr(gsl, c.entry) for c in _CAPS)   # every capability entrypoint resolves


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
