"""test_studio — the single front door `explore()` (#3 use-it-better) and the external LLM proposer wired
into the evolve loop (#2). Deterministic, offline (a scripted fake LLM; no network).
"""
import OUTLIER_MCB as m

_LLM_PAYLOAD = ('[{"name":"LLM interaction law","broken_assumption":"law_is_separable","operator":"proposed",'
                '"claim":"an irreducible interaction term couples the inputs",'
                '"why_standard_families_fail":"additive models cannot fit a product",'
                '"world_test_description":"fit an interaction term and check held-out residual",'
                '"test_patch":"","implementation_patch":"","novelty_rationale":"coupling","risk":"low"}]')


def _fake_llm():
    return m.CallableLLMProvider(lambda prompt: [_LLM_PAYLOAD])


def _has_z3():
    try:
        import z3  # noqa: F401
        return True
    except ImportError:
        return False


# ── #2 external LLM proposer (settled by the evaluator, not the LLM) ─────────────────────────────────
def test_llm_proposer_is_settled_by_the_evaluator():
    task = m.symbolic_invention_task()
    res = m.evolve_invention(task["problem"], task["evaluator"], budget=14, pack=task["pack"], llm=_fake_llm())
    assert any(r.mutation_operator == "llm_proposed" for r in res.memory.all())   # the LLM proposed content
    # the LLM idea breaks separability ⇒ the OBJECTIVE evaluator confirms it (not the LLM, not the engine)
    llm_recs = [r for r in res.memory.all() if r.mutation_operator == "llm_proposed"]
    assert any(r.correctness_passed for r in llm_recs)


# ── #3 the single front door ─────────────────────────────────────────────────────────────────────────
def test_explore_invention_path():
    task = m.symbolic_invention_task()
    rep = m.explore(task["problem"], pack=task["pack"], evaluator=task["evaluator"], budget=14)
    assert rep.mode == "invention" and rep.verified is True
    assert rep.panel is not None and rep.trace is not None
    assert "Studio" in rep.markdown() and "never 'absolute novelty'" in rep.statement.lower()  # honest disclaimer


def test_explore_default_is_provisional():
    rep = m.explore("invent a new rate limiter for a distributed gateway", budget=8)
    assert rep.mode == "invention" and "PROVISIONAL" in rep.statement   # no real evaluator ⇒ honest provisional


def test_explore_math_path():
    rep = m.explore("AM-GM inequality", math_claim="x**2 + y**2 >= 2*x*y",
                    math_variables={"x": (-5.0, 5.0), "y": (-5.0, 5.0)})
    assert rep.mode == "math" and rep.conjectures is not None
    if _has_z3():
        assert rep.conjectures.proved()                                  # the solver proved it
    assert "not 'a new theorem'" in rep.statement.lower() or "decidable" in rep.statement.lower()


def test_explore_with_llm():
    task = m.symbolic_invention_task()
    rep = m.explore(task["problem"], pack=task["pack"], evaluator=task["evaluator"], budget=14, llm=_fake_llm())
    assert any(s.action == "llm_proposer" for s in rep.trace.steps)      # the proposer step is traced


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
