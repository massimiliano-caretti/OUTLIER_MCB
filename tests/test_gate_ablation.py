"""test_gate_ablation — the epistemic gate's effect is MEASURABLE: on renames of famous methods a naive
novelty heuristic yields false novelty, the gate drives it to zero, and it does not over-reject genuinely
off-corpus ideas (the negative control). Deterministic and offline.
"""
import OUTLIER_MCB as gsl


def test_gate_removes_false_novelty_and_does_not_over_reject():
    a = gsl.epistemic_gate_ablation()
    assert a.naive_false_novelty == a.n_renamed             # the naive heuristic calls every rename 'novel'
    assert a.gated_false_novelty == 0                       # the gate catches all of them
    assert a.false_novelty_reduction == 1.0                 # a measured 100% reduction, not a philosophy
    assert a.gated_rejects_off_corpus == 0                  # control: off-corpus ideas are NOT wrongly rejected


def test_ablation_renders():
    md = gsl.epistemic_gate_ablation().markdown()
    assert "Epistemic-gate ablation" in md and "false-novelty" in md
