"""test_meta_pack — the SELF domain: invent()/judge() now reason about the engine's OWN improvement.

Before this pack, `invent('a better way to rank breakable assumptions')` routed to `generic` and returned
undifferentiated transports. The meta pack gives the engine a domain for itself, so a library-improvement
task breaks a real meta-assumption (the engine judges itself / novelty is naming / more metrics is better).
"""
import OUTLIER_MCB as gsl


def test_meta_pack_registers_and_is_strong():
    pack = gsl.get_pack("meta")
    assert pack.validate() == []
    assert gsl.pack_quality(pack)["overall"] >= 0.7       # a strong pack, not rigor theater
    assert pack.dimension_of["the_engine_judges_itself"] == "EVALUATION"


def test_routing_now_catches_library_improvement_prompts():
    # the exact prompt that used to fall through to generic now routes to the self domain.
    assert gsl.select_pack("a more effective way to rank breakable assumptions to maximize novelty")[0].name == "meta"
    assert gsl.select_pack("improve the creativity engine's scoring")[0].name == "meta"
    assert gsl.select_pack("write a python function to parse json")[0].name != "meta"


def test_invent_now_differentiates_on_the_meta_domain():
    meta = gsl.get_pack("meta")
    inv = gsl.invent("a more effective way to rank breakable assumptions to maximize novelty", pack=meta)
    assert inv.box == meta.box_name                        # it is escaping the META box, not generic
    assert inv.frontier
    meta_names = set(meta.by_name())
    assert any(set(f["candidate"].assumptions) & meta_names for f in inv.frontier)


def test_judge_maps_a_meta_break():
    meta = gsl.get_pack("meta")
    j = gsl.judge("settle every candidate by an external resolver, never by the engine's own score",
                  pack=meta, assumption="the_engine_judges_itself")
    assert j.verdict == "MUST_BE_AUDITED"
    assert j.broken_assumption == "the_engine_judges_itself"


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
