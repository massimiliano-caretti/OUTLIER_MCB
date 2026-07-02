"""test_wiring_6_to_9 — proves the remaining isolated capabilities are now wired into the orchestration:
#6 divergent runner seeds the orchestrated loop, #7 repo_semantics grounds judge, #8 the memory router feeds
the llm_loop prompt, #9 preflight induces a provisional pack for unknown domains. Offline, deterministic."""
import inspect
import OUTLIER_MCB as m


# ── #6 divergent runner inside the orchestrated evolve loop ───────────────────────────────────────────
def test_orchestrated_loop_seeds_from_divergent_runner():
    t = m.symbolic_invention_task()
    res = m.evolve_invention(t["problem"], t["evaluator"], budget=16, pack=t["pack"], orchestrate=True)
    steps = res.trace.steps if hasattr(res.trace, "steps") else []
    assert any("divergent" in str(s).lower() for s in steps)     # the bandit runner ran in the loop
    assert res.best().externally_settled                          # correctness preserved


# ── #7 repo_semantics grounds judge ───────────────────────────────────────────────────────────────────
def test_judge_with_repo_path_has_semantic_grounding():
    j = m.judge("speed up analyze_repo_semantics impact_surface", prompt="perf", repo_path="OUTLIER_MCB")
    rg = j.repo_grounding
    assert rg is not None and rg["grounded"] is True
    assert "repo_semantics" in rg["impact_surface"]["modules"]
    assert rg["falsifiers"] and rg["falsifiers"][0]["file"].endswith(".py")


def test_judge_without_repo_is_unchanged():
    j = m.judge("just add caching", prompt="a rate limiter", pack=m.get_pack("coding"))
    assert j.repo_grounding is None                               # no repo → no semantic grounding (backward-compat)


# ── #8 memory router feeds the llm_loop prompt ────────────────────────────────────────────────────────
def test_memory_router_routes_into_llm_prompt():
    from OUTLIER_MCB.llm_loop import _build_prompt, llm_openended_search

    class _Arch:
        def elites(self):
            return []
    prompt = _build_prompt("a rate limiter", m.get_pack("coding"), _Arch(), [], "", "", set(), 2,
                           memory_block="ROUTED-CUES")
    assert "ROUTED-CUES" in prompt
    assert "memory_router" in inspect.signature(llm_openended_search).parameters   # the opt-in hook exists


def test_creative_memory_router_builds_a_nonempty_block():
    from OUTLIER_MCB.failure_lessons import LessonMemory, FailureLesson
    lm = LessonMemory()
    lm.lessons.append(FailureLesson("leakage", "passed a negative control", "id", "a rate limiter"))
    plan = m.CreativeMemoryRouter(lesson_memory=lm, pack=m.get_pack("coding")).plan("a rate limiter")
    assert plan.prompt_block.strip()


# ── #9 preflight induces a provisional pack for unknown domains ───────────────────────────────────────
def test_preflight_induces_pack_for_unknown_domain_but_keeps_elicitation():
    pf = m.preflight_creative_request("a fairer matchmaking system for an online multiplayer game")
    assert pf.get("elicitation_required") is True and pf["domain_guard"]["pack"] == "generic"   # unchanged honesty
    assert len(pf.get("inferred_pack_assumptions", [])) >= 3      # but now a provisional space is offered
    assert pf.get("inferred_pack") is not None


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
