"""test_discovery_eval — the autonomous inventor, settled by REAL evaluators, finds the data-true answer.

This is the honest payoff test: not 'the structure looks rigorous' but 'on data with a KNOWN answer, the
whole creative stack (problem-finding + blending + transformation + memory + affect), settled by the
symbolic/causal evaluator, confirms exactly the assumption the data support'. Deterministic, offline.
"""
from evals.discovery_eval import run_discovery_eval


def test_inventor_settles_on_the_data_true_assumption():
    rep = run_discovery_eval()
    # numeric: interaction-law data ⇒ ONLY breaking separability is confirmed by the symbolic evaluator
    assert rep["numeric"]["settled_correct"] is True
    assert rep["numeric"]["confirmed"] == ["law_is_separable"]
    # causal: confounded data ⇒ ONLY the confounder-adjustment break is confirmed by the causal evaluator
    assert rep["causal"]["settled_correct"] is True
    assert rep["causal"]["confirmed"] == ["association_is_direct"]


def test_new_capabilities_are_measured():
    caps = run_discovery_eval()["capabilities"]
    assert all(caps.values()), f"a new-capability check failed: {caps}"


def test_mechanisms_show_measurable_effect():
    rep = run_discovery_eval()
    for task in ("numeric", "causal"):
        assert rep[task]["blend_added"] is True                  # blending adds cross-domain problems
        assert rep[task]["memory_prior_fertile"] == 1.0          # memory records the fertile break (compounds)
        assert rep[task]["satisfaction"] > 0.0                   # real (surprising-confirmed) discovery happened


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
