"""test_agents_trace — light cognitive roles (#9), the auditable reasoning trace (#12), and the wiring of
analogy / abstraction / panel into the evolve loop. Deterministic, offline.
"""
import OUTLIER_MCB as m


# ── #12 reasoning trace ───────────────────────────────────────────────────────────────────────────────
def test_reasoning_trace_and_evidence_ledger():
    t = m.ReasoningTrace(problem="P")
    t.log("generate", why="seed the pool", output="5 candidates")
    t.log("evaluate", why="settle on the objective", output="best 0.9")
    assert len(t.steps) == 2 and "generate" in t.markdown()
    assert t.to_dict()["steps"][0]["action"] == "generate"
    led = m.EvidenceLedger()
    led.add("verified", "pytest", "RED→GREEN")
    assert "verified" in led.markdown() and "pytest" in led.markdown()


# ── #9 cognitive panel ────────────────────────────────────────────────────────────────────────────────
def test_cognitive_panel_roles_and_conservative_synthesis():
    panel = m.CognitivePanel(m.get_pack("numeric"))
    rep = panel.deliberate("measure the law by an irreducible interaction term, not an additive proxy")
    roles = {e.role for e in rep.evidence}
    assert {"Skeptic", "Adversary", "PriorArtHunter", "Analogist", "Theorist"} <= roles
    assert rep.by_role("PriorArtHunter").evidence["novelty_scope"] == "LOCAL_ONLY"   # honest without a provider
    assert "never 'absolute novelty'" in rep.synthesis.lower()                        # conservative disclaimer
    assert "Cognitive panel" in rep.markdown()


# ── wiring into the evolve loop ───────────────────────────────────────────────────────────────────────
def test_evolve_wires_trace_analogy_concepts_and_panel():
    task = m.symbolic_invention_task()
    res = m.evolve_invention(task["problem"], task["evaluator"], budget=14, pack=task["pack"],
                             use_analogy=True, mine_concepts=True)
    # #12: a trace is always built and records the key decisions
    assert res.trace is not None and len(res.trace.steps) >= 3
    actions = {s.action for s in res.trace.steps}
    assert "cross_domain_analogy" in actions and "mine_abstractions" in actions and "select_best" in actions
    # DreamCoder abstractions attached
    assert res.concept_library is not None
    # the panel deliberates over the winning idea
    rep = res.panel(task["pack"])
    assert isinstance(rep, m.PanelReport) and rep.evidence


def test_default_evolve_still_has_trace_no_regression():
    task = m.symbolic_invention_task()
    res = m.evolve_invention(task["problem"], task["evaluator"], budget=10, pack=task["pack"])
    assert res.trace is not None and res.concept_library is None      # trace always; concepts only opt-in


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
