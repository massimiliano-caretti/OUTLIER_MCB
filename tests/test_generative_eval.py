"""test_generative_eval — #10 the generative-upgrade gate. Every new capability (#1 induction, #2 grounding,
#3 evaluator synthesis, #9 claim ladder) must beat its decorative control, or the gate refuses GO."""
from evals.generative_eval import run_generative_eval


def test_generative_gate_passes_and_each_feature_earns_its_keep():
    rep = run_generative_eval()
    assert rep["state"] == "GO_GENERATIVE"
    assert rep["primary"] >= 0.75
    assert all(rep["earns_keep"].values())                    # no decorative feature slips through
    assert rep["blockers"] == []


def test_each_ablation_beats_its_decorative_control():
    rep = run_generative_eval()
    d = rep["detail"]
    assert d["pack_self_induction_score"]["induction_beats_decorative"] is True
    assert d["semantic_grounding_score"]["grounding_discriminates"] is True
    assert d["evaluator_synthesis_score"]["catches_cheat"] is True
    assert d["claim_ladder_score"]["gate_is_about_evidence"] is True


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
