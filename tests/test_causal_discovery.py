"""test_causal_discovery — the causal layer (Point 3): correlation ≠ causation, settled by the data.

Two synthetic worlds with a KNOWN ground truth:
  • CONFOUNDED:  Z→A, Z→B, no A→B. A and B correlate only through the common cause Z (spurious edge).
  • GENUINE:     A→B directly (B = 0.9·A + noise); Z is an independent non-confounder.

Proves that breaking `association_is_direct` (adjust for the confounder) is what separates the two —
the engine's existing controls-collapse discipline applied to causality — and that latent confounding
is reported HUMAN, never AUTO. Deterministic, offline, no new runtime dependency.
"""
import random

import OUTLIER_MCB as gsl
from OUTLIER_MCB.generators import Candidate


def _confounded(n=400, seed=11):
    rng = random.Random(seed)
    Z = [rng.gauss(0, 1) for _ in range(n)]
    A = [Z[i] + 0.5 * rng.gauss(0, 1) for i in range(n)]      # Z → A
    B = [Z[i] + 0.5 * rng.gauss(0, 1) for i in range(n)]      # Z → B  (NO A → B)
    return {"A": A, "B": B, "Z": Z}


def _genuine(n=400, seed=12):
    rng = random.Random(seed)
    A = [rng.gauss(0, 1) for _ in range(n)]
    B = [0.9 * A[i] + 0.3 * rng.gauss(0, 1) for i in range(n)]  # A → B directly
    Z = [rng.gauss(0, 1) for _ in range(n)]                     # independent non-confounder
    return {"A": A, "B": B, "Z": Z}


def _naive_candidate():
    return Candidate(name="naive", operator="unify", breaks=[], assumptions=[],
                     negation="the observed association between A and B is the causal effect")


def _adjust_candidate():
    return Candidate(name="adjust", operator="invert", breaks=["CONFOUNDING"],
                     assumptions=["association_is_direct"],
                     negation="the association may be spurious via a common cause; adjust for the confounder")


def _latent_candidate():
    return Candidate(name="latent", operator="scale", breaks=["LATENT"],
                     assumptions=["causal_sufficiency"],
                     negation="a hidden unobserved confounder may exist; the effect may be unidentifiable")


# ── pack ─────────────────────────────────────────────────────────────────────────────────────────
def test_causal_pack_registers_and_validates():
    pack = gsl.get_pack("causal")
    assert pack.validate() == []
    assert pack.dimension_of["association_is_direct"] == "CONFOUNDING"


def test_causal_pack_does_not_steal_routing():
    assert gsl.select_pack("write a python function to parse json")[0].name != "causal"
    assert gsl.select_pack("does smoking cause and effect on lung cancer, a confounder analysis")[0].name == "causal"


# ── the headline: a spurious (confounded) edge vs a genuine one ────────────────────────────────────
def test_adjustment_exposes_a_spurious_edge():
    pack = gsl.get_pack("causal")
    ev = gsl.causal_evaluator(_confounded(), treatment="A", outcome="B", confounders=["Z"], pack=pack)
    naive, adjust = ev(_naive_candidate()), ev(_adjust_candidate())
    # the naive estimate sees a strong (spurious) association; adjusting for Z collapses it to ~0.
    assert abs(naive["naive_effect"]) > 0.4
    assert abs(adjust["effect"]) < 0.15
    assert adjust["causal_verdict"] == "NO_EDGE"          # ground truth: A does NOT cause B
    assert adjust["confounding_detected"] > 0.3           # the correlation≠causation gap is reported
    # the engine prefers the candidate that correctly finds no edge over the one asserting a spurious one.
    assert adjust["score"] > naive["score"]


def test_genuine_edge_survives_adjustment():
    pack = gsl.get_pack("causal")
    ev = gsl.causal_evaluator(_genuine(), treatment="A", outcome="B", confounders=["Z"], pack=pack)
    adjust = ev(_adjust_candidate())
    assert abs(adjust["effect"]) > 0.5                    # the real effect survives adjustment
    assert adjust["causal_verdict"] == "EDGE"
    assert adjust["confounding_detected"] < 0.15          # no confounding to explain it away
    assert adjust["controls_collapse"] is True            # placebo (permuted treatment) collapses


def test_latent_confounding_is_reported_human():
    pack = gsl.get_pack("causal")
    ev = gsl.causal_evaluator(_confounded(), treatment="A", outcome="B", confounders=["Z"], pack=pack)
    out = ev(_latent_candidate())
    assert out["verifiability"] == "HUMAN"                # observation cannot settle hidden confounding


def test_placebo_collapses():
    pack = gsl.get_pack("causal")
    ev = gsl.causal_evaluator(_genuine(), treatment="A", outcome="B", confounders=["Z"], pack=pack)
    out = ev(_adjust_candidate())
    assert abs(out["placebo_effect"]) < 0.15             # a permuted treatment carries no effect


# ── integration: the existing FunSearch + QD loop converges on the correct causal structure ────────
def test_creative_search_prefers_the_unconfounded_estimate():
    pack = gsl.get_pack("causal")
    ev = gsl.causal_evaluator(_confounded(), treatment="A", outcome="B", confounders=["Z"], pack=pack)
    res = gsl.creative_search("does A cause B, or is it a spurious correlation via a confounder",
                              evaluator=ev, pack=pack, budget=24)
    best = res.best()
    assert best is not None
    assert "association_is_direct" in best.candidate.assumptions   # it broke the right assumption
    assert best.evidence.get("causal_verdict") == "NO_EDGE"        # and reached the correct verdict
    assert best.evidence.get("confounding_detected", 0) > 0.3


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
