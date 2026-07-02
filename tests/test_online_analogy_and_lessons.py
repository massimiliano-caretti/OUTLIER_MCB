"""test_online_analogy_and_lessons — #3 cross-domain analogy from real online sources, and #9 memory that
learns operational lessons from failures. Deterministic, offline (a fake mechanism provider; no network).
"""
import OUTLIER_MCB as m


# ── #3 online cross-domain analogy ────────────────────────────────────────────────────────────────────
class _FakeMechProvider:
    MECHS = {"ecology": ("carrying capacity / predator-prey", "the population stabilizes at a dynamic equilibrium"),
             "economics": ("supply-demand price signal", "the price adapts to scarcity, not a fixed quota")}

    def research(self, query):
        for d, (title, summ) in self.MECHS.items():
            if d in query:
                return {"matches": [{"title": title, "summary": summ, "source_type": "paper", "url": "http://" + d}]}
        return {"matches": []}


def test_online_analogy_transfers_distant_mechanisms():
    eng = m.OnlineCrossDomainAnalogyEngine(_FakeMechProvider(), domains=["ecology", "economics", "biology"])
    ana = eng.analogies("invent an adaptive rate limiter")
    assert ana and any(a.source_domain == "ecology" and "carrying capacity" in a.source_mechanism for a in ana)
    # every transfer is disciplined: prior-art-checked AND must pass a world-test (it never just asserts novelty)
    assert all("prior-art" in a.transfer_claim and "world-test" in a.transfer_claim for a in ana)
    assert ana[0].source_url                                       # provenance kept


# ── #9 failure lessons (memory that learns) ───────────────────────────────────────────────────────────
def _rec(rid, **kw):
    return m.EvolutionRecord(id=rid, problem="P", candidate_name=rid, **kw)


def test_summarize_failure_modes():
    assert m.summarize_failure_mode(_rec("a", score_components={"leakage_detected": 1.0})).mode == "leakage"
    assert m.summarize_failure_mode(_rec("b", score_components={"public": 1.0, "hidden": 0.0})).mode == "overfit_visible"
    assert m.summarize_failure_mode(_rec("c", correctness_passed=False)).mode == "no_world_test"
    assert m.summarize_failure_mode(_rec("d", correctness_passed=True, improvement_over_baseline=0.0,
                                         improvement_over_parent=0.0, novelty_scope="ONLINE_PRIOR_ART_CHECKED")).mode == "regressed_baseline"
    # a clean, improving, online-checked success teaches no failure lesson
    assert m.summarize_failure_mode(_rec("e", correctness_passed=True, improvement_over_baseline=0.5,
                                         novelty_scope="ONLINE_PRIOR_ART_CHECKED")) is None


def test_lesson_memory_retrieve_and_inject():
    lm = m.LessonMemory()
    lm.record_all([_rec("a", score_components={"leakage_detected": 1.0}),
                   _rec("b", score_components={"public": 1.0, "hidden": 0.0}),
                   _rec("c", score_components={"leakage_detected": 1.0})])   # duplicate mode
    modes = {l.mode for l in lm.retrieve("P")}
    assert modes == {"leakage", "overfit_visible"}                 # de-duplicated by mode
    prompt = lm.inject_lessons_into_prompt("BASE PROMPT", "P")
    assert "AVOID" in prompt and "leakage" in prompt


def test_evolve_result_exposes_lessons():
    task = m.symbolic_invention_task()
    res = m.evolve_invention(task["problem"], task["evaluator"], budget=10, pack=task["pack"])
    lm = res.lessons()
    assert isinstance(lm, m.LessonMemory)                          # the run's failures become reusable lessons


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
