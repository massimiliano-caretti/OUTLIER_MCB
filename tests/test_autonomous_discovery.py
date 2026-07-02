"""test_autonomous_discovery — the Automated Scientist Loop (Point 4).

Proves the high-level loop runs the scientific method over the EXISTING machinery, domain-blind: the same
`discover()` orchestrates symbolic regression and causal inference unchanged, accepts only what clears the
evaluator's controls, early-exits on success (parsimony), and escalates when a round yields nothing.
Deterministic and offline.
"""
import random

import OUTLIER_MCB as gsl


# ── data worlds (reused shapes from the P1 / P3 suites) ─────────────────────────────────────────────
def _interaction_data(n=120, seed=7):
    rng = random.Random(seed)
    X = [[rng.uniform(-2, 2), rng.uniform(-2, 2), rng.uniform(-2, 2)] for _ in range(n)]
    y = [2.0 * r[0] * r[1] - 3.0 for r in X]
    cut = int(0.66 * n)
    return X[:cut], y[:cut], X[cut:], y[cut:]


def _confounded(n=400, seed=11):
    rng = random.Random(seed)
    Z = [rng.gauss(0, 1) for _ in range(n)]
    A = [Z[i] + 0.5 * rng.gauss(0, 1) for i in range(n)]
    B = [Z[i] + 0.5 * rng.gauss(0, 1) for i in range(n)]
    return {"A": A, "B": B, "Z": Z}


# ── the loop discovers a symbolic law ───────────────────────────────────────────────────────────────
def test_discover_finds_the_symbolic_law_and_early_exits():
    pack = gsl.get_pack("numeric")
    ev = gsl.symbolic_evaluator(_interaction_data(), pack=pack)
    disc = gsl.discover("discover a law for coupled variables", ev, pack, base_budget=14)
    best = disc.best()
    assert best is not None
    assert "x0*x1" in best.evidence.get("formula", "")
    assert disc.rounds == 1                                  # parsimony: cleared on the first round
    assert any("parsimony" in line for line in disc.log)


# ── the SAME loop discovers a causal structure (domain-blind) ───────────────────────────────────────
def test_discover_finds_the_causal_structure():
    pack = gsl.get_pack("causal")
    ev = gsl.causal_evaluator(_confounded(), treatment="A", outcome="B", confounders=["Z"], pack=pack)
    disc = gsl.discover("does A cause B or is it confounded", ev, pack, base_budget=14)
    best = disc.best()
    assert best is not None
    assert best.evidence.get("causal_verdict") == "NO_EDGE"      # correct structure: no direct edge
    assert best.evidence.get("confounding_detected", 0) > 0.3    # the spurious correlation is exposed


# ── escalation: a round that yields nothing widens the search instead of crashing ───────────────────
def test_loop_escalates_when_nothing_survives():
    pack = gsl.get_pack("numeric")
    ev = gsl.symbolic_evaluator(_interaction_data(), pack=pack)
    disc = gsl.discover("unsatisfiable gate", ev, pack, rounds=3, base_budget=6,
                        accept_score=1.5)                        # impossible threshold → never accepts
    assert disc.laws == []
    assert disc.rounds == 3
    assert any("escalate" in line for line in disc.log)


def test_markdown_renders():
    pack = gsl.get_pack("numeric")
    ev = gsl.symbolic_evaluator(_interaction_data(), pack=pack)
    md = gsl.discover("discover a law", ev, pack, base_budget=14).markdown()
    assert "Automated Scientist Loop" in md and "Accepted" in md


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
