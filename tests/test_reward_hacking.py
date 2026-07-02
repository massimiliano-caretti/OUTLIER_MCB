"""#5 Anti-gaming — a fixed scalar objective is maximally gameable, so audit each kept candidate.

The meta pack's thesis: 'more metrics is better' is false, and the engine must police its OWN objective.
`reward_hacking_report` flags a candidate that is kept only because of fragile, gameable soft proxies — not
because of a protected/external gate (correctness). Competitors with a single fixed score have no such guard.

Deterministic sum score_fn so the keep/drop decisions are exact and the flip is unambiguous.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import OUTLIER_MCB as gsl

_COMPONENTS = ["correctness", "novelty_distance", "diversity"]
_SCORE = lambda it: it.get("correctness", 0.0) + it.get("novelty_distance", 0.0) + it.get("diversity", 0.0)

# top-3 of 6 kept: A(1.5) robust, B(1.4) gamed-on-novelty, C(1.3) leans-on-correctness; D/E/F dropped
_ITEMS = [
    {"correctness": 0.5, "novelty_distance": 0.5, "diversity": 0.5},   # 0 A robust
    {"correctness": 0.0, "novelty_distance": 1.4, "diversity": 0.0},   # 1 B gamed (soft only)
    {"correctness": 1.3, "novelty_distance": 0.0, "diversity": 0.0},   # 2 C leans on the external gate
    {"correctness": 0.2, "novelty_distance": 0.2, "diversity": 0.1},   # 3 D filler
    {"correctness": 0.1, "novelty_distance": 0.1, "diversity": 0.1},   # 4 E filler
    {"correctness": 0.0, "novelty_distance": 0.0, "diversity": 0.0},   # 5 F filler
]


def _report():
    return gsl.reward_hacking_report(_ITEMS, score_fn=_SCORE, components=_COMPONENTS, keep_fraction=0.5)


def test_gamed_candidate_is_flagged():
    r = _report()
    assert r[1].kept and r[1].gamed                      # B survives only on the soft 'novelty_distance'
    assert r[1].leans_on == ["novelty_distance"]


def test_robust_candidate_is_not_flagged():
    r = _report()
    assert r[0].kept and not r[0].gamed                  # A survives every single-component ablation
    assert r[0].leans_on == []


def test_leaning_on_the_external_gate_is_not_gaming():
    r = _report()
    assert r[2].kept and not r[2].gamed                  # C leans on correctness — the legitimate external gate
    assert "correctness" in r[2].leans_on


def test_dropped_items_are_not_flagged():
    r = _report()
    for i in (3, 4, 5):
        assert not r[i].kept and not r[i].gamed


def test_default_score_fn_runs_on_invention_components():
    """Smoke: with the real default score_fn (invention_score) it produces a verdict per item without error."""
    items = [{"correctness": 1.0, "novelty_distance": 0.8, "diversity": 0.5},
             {"correctness": 0.0, "novelty_distance": 0.9, "diversity": 0.0}]
    r = gsl.reward_hacking_report(items, keep_fraction=0.5)
    assert len(r) == 2 and all(isinstance(v.gamed, bool) for v in r)
