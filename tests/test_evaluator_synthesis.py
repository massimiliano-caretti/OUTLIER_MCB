"""test_evaluator_synthesis — #3 the engine invents the VERIFIER, not just the idea. Synthesizes a
HiddenEvaluator (public + held-out hidden + negative controls) from a claim's materials, validates its
structure, scores its quality (baseline must fail, oracle must pass), and ablates it (the structure must
catch a cheat a public-only evaluator accepts). Offline, deterministic."""
import pytest
import OUTLIER_MCB as m
from OUTLIER_MCB.evaluator_synthesis import (synthesize_evaluator, validate_evaluator,
                                                evaluator_quality_score, evaluator_ablation, EvaluatorSynthesisError)


class _Sol:
    def __init__(self, fn, name="sol"):
        self.fn, self.name = fn, name


def _context():
    check = lambda sol, case: sol.fn(case)
    honest = _Sol(lambda c: c > 0, "honest")          # the true mechanism
    leaky = _Sol(lambda c: True, "leaky")             # passes everything incl. controls → leakage
    baseline = _Sol(lambda c: c < -100, "box")        # the box: fails the public cases
    return {"check": check, "cases": [1, 2, 3, 4], "perturb": lambda c: -abs(c) - 1,
            "baseline": baseline, "oracle": honest, "claim_baseline_fails": True,
            "leaky_candidate": leaky, "honest_candidate": honest}


def test_synthesizes_evaluator_with_public_hidden_and_controls():
    ev = synthesize_evaluator("classify positive", _context())
    assert validate_evaluator(ev) == []                       # complete anti-cheating structure
    assert ev.hidden.public_cases and ev.hidden.hidden_cases and ev.hidden.negative_controls
    assert "hidden_cases" in ev.sources and "negative_controls" in ev.sources
    assert ev.settles_externally is True                      # it is an external resolver (fix A compatible)


def test_refuses_to_synthesize_without_check_or_cases():
    with pytest.raises(EvaluatorSynthesisError):
        synthesize_evaluator("x", {"cases": [1]})             # no check
    with pytest.raises(EvaluatorSynthesisError):
        synthesize_evaluator("x", {"check": lambda s, c: True})  # no cases


def test_quality_requires_baseline_to_fail_and_oracle_to_pass():
    ctx = _context()
    q = evaluator_quality_score(synthesize_evaluator("c", ctx), ctx)
    assert q["score"] == 1.0 and q["usable"] is True
    assert q["components"]["baseline_fails"] is True and q["components"]["oracle_passes"] is True
    # an evaluator whose claim's baseline does NOT actually fail scores lower behaviorally
    ctx_bad = {**ctx, "baseline": _Sol(lambda c: c > 0, "not_really_box")}   # 'baseline' actually passes
    q2 = evaluator_quality_score(synthesize_evaluator("c", ctx_bad), ctx_bad)
    assert q2["components"]["baseline_fails"] is False and q2["score"] < 1.0


def test_ablation_structure_catches_a_cheat_public_only_misses():
    ctx = _context()
    ab = evaluator_ablation(synthesize_evaluator("c", ctx), ctx)
    assert ab["ran"] and ab["structure_earns_its_place"] is True
    assert ab["naive_accepts_cheat"] is True and ab["synthesized_rejects_cheat"] is True
    assert ab["both_accept_honest"] is True


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
