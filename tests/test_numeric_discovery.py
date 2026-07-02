"""test_numeric_discovery — the first PR of the law-discovery layer.

Proves, on a synthetic dataset with a KNOWN law f = 2·x0·x1 - 3 (a pure interaction; x2 is a decoy),
that the engine does scientific discovery on numeric data through its EXISTING orchestration:
  • the `numeric` pack registers and validates;
  • breaking `law_is_separable` expands the basis with the interaction term that recovers the law;
  • the symbolic evaluator settles by the DATA — the breaking candidate beats the in-box (additive)
    baseline on held-out residual AND its negative control collapses, while the box's does not help;
  • creative_search (FunSearch + QD), unchanged, finds the interaction law and stores its formula.

Deterministic and offline (pure-Python backend, seeded data). No new runtime dependency.
"""
import math
import random

import OUTLIER_MCB as gsl
from OUTLIER_MCB.generators import Candidate


# ── synthetic world with a known law ────────────────────────────────────────────────────────────────
def _make_data(n=120, seed=7):
    rng = random.Random(seed)
    X = [[rng.uniform(-2, 2), rng.uniform(-2, 2), rng.uniform(-2, 2)] for _ in range(n)]
    y = [2.0 * r[0] * r[1] - 3.0 for r in X]          # pure interaction; x2 is irrelevant
    cut = int(0.66 * n)
    return X[:cut], y[:cut], X[cut:], y[cut:]


def _box_candidate():
    return Candidate(name="box", operator="unify", breaks=[], assumptions=[],
                     negation="additive smooth baseline over the raw variables")


def _interaction_candidate():
    return Candidate(name="break_sep", operator="invert", breaks=["FORM"],
                     assumptions=["law_is_separable"],
                     negation="INVERT separability: an irreducible interaction term carries the signal")


# ── pack ──────────────────────────────────────────────────────────────────────────────────────────
def test_numeric_pack_registers_and_validates():
    pack = gsl.get_pack("numeric")
    assert pack.validate() == []
    assert "law_is_separable" in pack.by_name()
    assert pack.dimension_of["law_is_separable"] == "FORM"


def test_numeric_pack_does_not_steal_routing():
    # distinctive keywords: a plain coding/math prompt must NOT route to numeric (no regression).
    assert gsl.select_pack("write a python function to parse json")[0].name != "numeric"
    assert gsl.select_pack("prove a convergence rate for gradient descent")[0].name != "numeric"
    # but a law-discovery prompt does route to numeric.
    assert gsl.select_pack("discover a scientific law from data")[0].name == "numeric"


# ── basis: the broken assumption decides the hypothesis class ───────────────────────────────────────
def test_breaking_separability_unlocks_interaction_terms():
    box_terms = {t.label for t in gsl.basis_from_candidate(_box_candidate(), n_features=3)}
    brk_terms = {t.label for t in gsl.basis_from_candidate(_interaction_candidate(), n_features=3)}
    assert "x0*x1" not in box_terms                    # the box cannot express the coupling
    assert "x0*x1" in brk_terms                         # breaking separability can


# ── the evaluator settles by the data ───────────────────────────────────────────────────────────────
def test_breaking_candidate_beats_box_on_held_out_data():
    ev = gsl.symbolic_evaluator(_make_data())
    box, brk = ev(_box_candidate()), ev(_interaction_candidate())
    assert brk["nrmse_holdout"] < 0.05                 # the interaction law is recovered almost exactly
    assert box["nrmse_holdout"] > 0.3                  # the additive box cannot fit a product
    assert brk["score"] > box["score"]                 # the broken assumption wins, settled by data
    assert brk["controls_collapse"] is True            # shuffled columns destroy the fit ⇒ real signal
    assert "x0*x1" in brk["formula"]


def test_controls_catch_leakage():
    # a label-shuffled target has NO learnable structure: even the rich basis must NOT report a real law.
    X_tr, y_tr, X_ho, y_ho = _make_data()
    rng = random.Random(1)
    y_tr_noise = y_tr[:]; rng.shuffle(y_tr_noise)
    y_ho_noise = y_ho[:]; rng.shuffle(y_ho_noise)
    ev = gsl.symbolic_evaluator((X_tr, y_tr_noise, X_ho, y_ho_noise))
    out = ev(_interaction_candidate())
    assert out["nrmse_holdout"] > 0.5                  # nothing to fit on held-out
    assert out["score"] < 0.4                          # graded down, never a free pass


# ── integration: the existing FunSearch + QD loop finds the law, unchanged ──────────────────────────
def test_creative_search_discovers_the_interaction_law():
    pack = gsl.get_pack("numeric")
    ev = gsl.symbolic_evaluator(_make_data(), pack=pack)   # relations resolve assumption→basis
    res = gsl.creative_search("discover a scientific law from data with coupled variables",
                              evaluator=ev, pack=pack, budget=24)
    best = res.best()
    assert best is not None
    assert best.score > 0.7                            # a genuine, settled law
    assert "law_is_separable" in best.candidate.assumptions
    assert best.evidence.get("controls_collapse") is True
    assert "x0*x1" in best.evidence.get("formula", "")


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
