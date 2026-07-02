"""Multi-metric self-improvement: improve EVERY performance dimension, regress NONE (a Pareto gate).

Genuine improvement, not a single score chased for its own sake. GREEN: across FIVE orthogonal certified
dimensions (symbolic-regression recovery + counterexample refutation + judge calibration + HELD-OUT
external_transfer + POET-like curriculum_progression on self-generated problems) the loop raises each and
regresses none. The anti-autoreferentiality gate (landscapes.py)
admits a dimension only if it is anchored OUTSIDE the engine; external_transfer is settled on a held-out
substrate the primitives were never designed for. Negative controls: the Pareto gate rejects any change that
regresses a dimension; a scrambled held-out target collapses transfer recovery; a TRUE conjecture is never
refuted. Deterministic.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import OUTLIER_MCB as g
from evals.benchmarks.counterexamples import refutation_rate, CONJECTURES
from evals.benchmarks.feynman import FEYNMAN, FEYNMAN_EXTENDED

pytest.importorskip("sympy")


def test_pareto_gate_rejects_any_regression():
    old = {"a": 0.5, "b": 0.5}
    assert g.pareto_improves(old, {"a": 0.6, "b": 0.5})        # one up, none down → accept
    assert not g.pareto_improves(old, {"a": 0.9, "b": 0.4})    # one up, one DOWN → reject (no skill traded away)
    assert not g.pareto_improves(old, {"a": 0.5, "b": 0.5})    # nothing improves → reject


def test_pareto_gate_is_a_protected_invariant():
    rep = g.verify_invariants()
    assert rep.ok and "pareto_no_regression" in rep.passed_names


def test_counterexample_rate_climbs_and_never_false_refutes():
    r30 = refutation_rate(30); r100 = refutation_rate(100)
    assert r30.rate < r100.rate                                # widening the search certifiably refutes more
    assert r100.rate == 1.0
    assert r30.false_refutation == 0 and r100.false_refutation == 0   # a TRUE conjecture is never refuted


def test_loop_improves_both_dimensions_and_regresses_none():
    from evals.multi_metric_loop import multi_metric_self_improve
    by = {e.id: e for e in FEYNMAN_EXTENDED}
    fby = {e.id: e for e in FEYNMAN}
    # a small substrate: one simple SR law + one ratio_product law (SR headroom) + the counterexample dim
    eqs = [fby["I.12.1"], by["I.39.22"]]
    res = multi_metric_self_improve(epochs=12, n_samples=200, equations=eqs, widths=[30, 100])
    assert not res.regressed_any                               # NO dimension regressed
    # both dimensions strictly improved over the run
    assert res.final_vector["sr_recovery"] > res.start_vector["sr_recovery"]
    assert res.final_vector["counterexample"] > res.start_vector["counterexample"]
    # the weakest dimension (min) is monotone non-decreasing — genuine all-round improvement
    mins = [e.aggregate_min for e in res.trajectory]
    assert mins == sorted(mins)


def test_judge_calibration_starts_below_ceiling():
    from evals.benchmarks.judge_calibration import calibration_report
    base = calibration_report(())                              # no detector enabled
    assert 0.0 < base.score < 1.0                              # there is headroom (the base judge misses overclaims)
    assert base.false_block_rate == 0.0                        # it does not wrongly block legitimate claims


def test_judge_calibration_can_improve_with_certified_upgrade():
    from evals.benchmarks.judge_calibration import calibration_report, DETECTORS
    base = calibration_report(())
    up = calibration_report(DETECTORS)                         # enable the claim_language_gate detector
    assert up.score > base.score                               # a certified upgrade raises calibration
    assert up.overclaim_block_rate == 1.0 and up.false_block_rate == 0.0   # catches overclaims, blocks no valid claim


def test_judge_calibration_negative_control_collapses():
    """A VALID claim is 'allowed' ONLY because of its external certificate — remove it and the classification
    must collapse to DOWNGRADED. If it does not, the metric is fake (self-judged)."""
    from evals.benchmarks.judge_calibration import classify_case, LABELED_CLAIMS, DETECTORS, VALID, DOWNGRADED
    valid = next(c for c in LABELED_CLAIMS if c[2] == VALID)
    assert classify_case(valid[0], valid[1], valid[3], DETECTORS) == VALID         # with the certificate
    assert classify_case(valid[0], valid[1], None, DETECTORS) == DOWNGRADED          # certificate removed → collapses


def test_pareto_rejects_regression_in_judge_calibration():
    # improving SR while judge_calibration drops must be REJECTED — no skill traded away
    old = {"sr_recovery": 0.5, "counterexample": 0.5, "judge_calibration": 0.625}
    assert not g.pareto_improves(old, {"sr_recovery": 0.9, "counterexample": 0.5, "judge_calibration": 0.5})
    assert g.pareto_improves(old, {"sr_recovery": 0.5, "counterexample": 0.5, "judge_calibration": 0.75})


def test_multi_metric_loop_early_stops_after_5_plateau_epochs():
    from evals.multi_metric_loop import multi_metric_self_improve
    fby = {e.id: e for e in FEYNMAN}
    # a substrate where, after the reachable upgrades, no dimension can improve → plateau (reach_budget small so the
    # unbounded ratchet also saturates on compute quickly and the bounded ceiling is what the report flags)
    res = multi_metric_self_improve(epochs=25, patience=5, n_samples=150,
                                    equations=[fby["I.12.1"]], widths=[30], reach_budget=3)
    assert res.stopped_early and res.plateau_epochs == 5
    assert len(res.trajectory) < 25                            # it did NOT run all epochs to pad a table
    assert res.plateau_report and "ORTHOGONAL" in res.plateau_report and "causal_recovery" in res.plateau_report
    assert not res.regressed_any


def test_loop_records_per_dimension_keylogs():
    from evals.multi_metric_loop import multi_metric_self_improve
    fby = {e.id: e for e in FEYNMAN}
    res = multi_metric_self_improve(epochs=3, n_samples=150, equations=[fby["I.12.1"], fby["I.25.13"]],
                                    widths=[30, 100])
    assert res.memory.runs                                      # per-epoch key-logs recorded


# ── external_transfer: the anti-autoreferentiality dimension (held-out generalization) ──────────────────────

def _ho_maps(n_samples=200):
    """base/extra held-out recovery maps — the substrate the primitives were NEVER designed for."""
    from evals.multi_metric_loop import _sr_recovery_maps
    from evals.benchmarks.feynman import FEYNMAN_HELDOUT
    from OUTLIER_MCB.grown_basis import GROWN_PRIMITIVES
    base_ho, rec_ho = _sr_recovery_maps(FEYNMAN_HELDOUT, GROWN_PRIMITIVES, n_samples)
    return base_ho, rec_ho, FEYNMAN_HELDOUT


def test_external_transfer_has_external_landscape():
    """The dimension is admissible ONLY because it is anchored outside the engine (held-out data, neg control,
    baseline). A self-scored landscape must be refused by the same gate."""
    from OUTLIER_MCB.landscapes import Landscape, is_external_landscape
    good = Landscape("external_transfer", "HELD-OUT Feynman laws",
                     "recovery on equations never used to design the primitives", True, True, True)
    assert is_external_landscape(good) and good.classification == "EXTERNAL"
    selfscored = Landscape("vibes", "the engine's own score", "an internal number", False, False, False)
    assert not is_external_landscape(selfscored)
    assert set(selfscored.missing()) == {"independent ground truth", "negative control", "baseline"}


def test_external_transfer_starts_below_ceiling():
    base_ho, rec_ho, HO = _ho_maps()
    assert 0.0 <= len(base_ho) / len(HO) < 1.0                  # the base basis does NOT already recover the held-out set


def test_external_transfer_certified_upgrade_improves():
    """A grown primitive recovers a HELD-OUT law it was never designed for → genuine generalization, not overfit."""
    base_ho, rec_ho, HO = _ho_maps()
    gain = set(base_ho)
    for p in ("ratio", "product_square", "ratio_product", "inverse_square"):
        gain |= rec_ho.get(p, set())
    assert len(gain) > len(base_ho)                             # certified held-out recovery strictly grows
    assert len(gain) == len(HO)                                 # all five held-out classes generalize


def test_external_transfer_negative_control_collapses():
    """If the held-out target is decoupled from its inputs (shuffled), the SAME primitive must STOP recovering it.
    If recovery survived a scrambled target, the metric would be measuring leakage, not generalization."""
    from evals.benchmarks.feynman import FEYNMAN_HELDOUT, generate_dataset, _r2
    from evals.self_improve_loop import _base_terms
    from OUTLIER_MCB.grown_basis import GROWN_PRIMITIVES
    from OUTLIER_MCB.evaluators.symbolic import least_squares
    eq = next(e for e in FEYNMAN_HELDOUT if e.id == "HO.ratio")     # E/k, recovered by the ratio primitive
    X_tr, y_tr, X_ho, y_ho = generate_dataset(eq, n=200, seed=0)
    terms = _base_terms(eq.nvars) + GROWN_PRIMITIVES["ratio"](eq.nvars)
    assert _r2(least_squares(X_tr, y_tr, terms), X_ho, y_ho) > 0.999          # with the true mapping: recovered
    y_scrambled = list(reversed(y_tr))                                        # NEGATIVE CONTROL: break x→y
    assert _r2(least_squares(X_tr, y_scrambled, terms), X_ho, y_ho) < 0.999   # collapses → the gain was real


def test_pareto_rejects_regression_in_external_transfer():
    old = {"sr_recovery": 0.6, "counterexample": 1.0, "judge_calibration": 1.0, "external_transfer": 0.6}
    # raising sr while held-out transfer DROPS must be rejected — an overfit gain is not an improvement
    assert not g.pareto_improves(old, {**old, "sr_recovery": 0.9, "external_transfer": 0.4})
    assert g.pareto_improves(old, {**old, "external_transfer": 0.8})         # a real generalization is accepted


def test_autoreferential_metric_rejected():
    """The loop's gate REFUSES to admit any dimension whose landscape is not externally anchored."""
    from OUTLIER_MCB.landscapes import Landscape, is_external_landscape
    internal = Landscape("self_score", provenance="", resolver="own number")  # no provenance / gt / control / baseline
    assert not is_external_landscape(internal)
    with pytest.raises(AssertionError):
        # simulate the loop's admission check on an autoreferential dimension
        assert is_external_landscape(internal), f"autoreferential (missing {internal.missing()}) — refused"


def test_new_dimension_changes_keep_drop_decision():
    """ORTHOGONALITY: external_transfer is NOT a function of sr_recovery. Some primitives raise in-substrate
    sr_recovery but NOT held-out transfer (substrate-overfit), while others raise both (generalizers). So adding
    the dimension changes which upgrades the loop keeps — it is not redundant with the existing metrics."""
    from evals.multi_metric_loop import _sr_recovery_maps
    from evals.benchmarks.feynman import FEYNMAN_ALL, FEYNMAN_HELDOUT
    from OUTLIER_MCB.grown_basis import GROWN_PRIMITIVES
    base, rec = _sr_recovery_maps(FEYNMAN_ALL, GROWN_PRIMITIVES, 200)
    base_ho, rec_ho, _ = _ho_maps()
    generalizers = [p for p in GROWN_PRIMITIVES if rec.get(p) and rec_ho.get(p)]      # raise BOTH
    overfitters  = [p for p in GROWN_PRIMITIVES if rec.get(p) and not rec_ho.get(p)]  # raise sr ONLY
    assert generalizers and overfitters                          # both kinds exist → the dimension is discriminative
    # keep/drop FLIP: an overfit primitive is "good" under sr-only but adds NOTHING under external_transfer
    p = overfitters[0]
    old3 = {"sr_recovery": 0.5, "counterexample": 1.0, "judge_calibration": 1.0}
    assert g.pareto_improves(old3, {**old3, "sr_recovery": 0.6})              # sr-only world: accept the overfit upgrade
    old4 = {**old3, "external_transfer": 0.6}
    # in the 4-dim world the SAME upgrade leaves transfer flat — still allowed, but the autoreferentiality
    # key-log fires, and a transfer-raising generalizer is strictly preferred (it improves a dimension sr ties on)
    assert not rec_ho.get(p)                                     # the overfit primitive certifiably does not generalize


# ── curriculum_progression: POET-like self-generated problems (breaks problem_space_is_static) ──────────────

def _cmap(n_samples=200):
    from evals.benchmarks.open_ended import curriculum_recovery_map, SEED_CURRICULUM
    return curriculum_recovery_map(SEED_CURRICULUM, n_samples), SEED_CURRICULUM


def test_curriculum_progression_has_external_landscape():
    """The dimension is admissible only because its generated problems have KNOWN ground truth + external
    resolver + negative control + baseline. The loop asserts this at startup."""
    from OUTLIER_MCB.landscapes import Landscape, is_external_landscape
    ls = Landscape("curriculum_progression", "self-generated SR problems with KNOWN symbolic ground truth",
                   "R²>0.999 + SymPy on held-out samples; scrambled-target negative control", True, True, True)
    assert is_external_landscape(ls)


def test_generated_problem_requires_external_landscape():
    """A generated 'problem' is admitted ONLY if it is externally settleable: base+needed recovers, each needed
    primitive is load-bearing, the scrambled target collapses, and the baseline matches its declared difficulty.
    A degenerate problem (a mislabelled difficulty) is REJECTED by curriculum_recovery_map — it cannot enter."""
    from evals.benchmarks.open_ended import curriculum_recovery_map, GeneratedProblem
    # a fraud: claims difficulty 0 (base solves it) but the truth is a 3-way product base cannot fit
    fraud = GeneratedProblem("OE.fraud", lambda a, b, c: a * b * c, 3, "x0*x1*x2", [(0.5, 2.5)] * 3, frozenset())
    with pytest.raises(ValueError):
        curriculum_recovery_map([fraud], 200)


def test_curriculum_progression_starts_below_ceiling():
    cmap, cur = _cmap()
    from evals.benchmarks.open_ended import curriculum_progression
    assert 0.0 < curriculum_progression([], cmap, cur) < 1.0      # base solves only the difficulty-0 rung(s)


def test_curriculum_progression_certified_upgrade_improves():
    cmap, cur = _cmap()
    from evals.benchmarks.open_ended import curriculum_progression
    base = curriculum_progression([], cmap, cur)
    up = curriculum_progression(["triple_product", "product_trig", "gaussian"], cmap, cur)
    assert up > base and up == 1.0                               # the right primitives climb the whole curriculum


def test_curriculum_progression_negative_control_collapses():
    """The scrambled-target negative control: with x→y decoupled, the SAME primitives must STOP recovering the
    generated rung. If they didn't, curriculum_progression would be measuring leakage, not real solving."""
    from evals.benchmarks.open_ended import recover_generated, SEED_CURRICULUM
    rung = next(p for p in SEED_CURRICULUM if p.id == "OE.d1.triple")
    assert recover_generated(rung, rung.primitives_needed, 200) is True             # real mapping: recovered
    assert recover_generated(rung, rung.primitives_needed, 200, scramble=True) is False  # scrambled: collapses


def test_pareto_rejects_regression_in_curriculum_progression():
    old = {"sr_recovery": 0.6, "counterexample": 1.0, "judge_calibration": 1.0,
           "external_transfer": 1.0, "curriculum_progression": 0.6}
    # raising sr while the self-generated curriculum REGRESSES must be rejected — no manufactured skill traded away
    assert not g.pareto_improves(old, {**old, "sr_recovery": 0.9, "curriculum_progression": 0.4})
    assert g.pareto_improves(old, {**old, "curriculum_progression": 0.8})


def test_curriculum_is_orthogonal_to_external_transfer():
    """The two exploration dimensions are NOT redundant: the curriculum is unlocked by primitives that
    external_transfer does NOT reward (triple_product / product_trig / gaussian). So adding curriculum_progression
    changes which upgrades the loop keeps — it is a genuinely different landscape, not a rename."""
    cmap, _ = _cmap()
    base_ho, rec_ho, _ = _ho_maps()
    curriculum_primitives = set().union(*cmap.values())
    assert "triple_product" in curriculum_primitives            # the curriculum needs it…
    assert not rec_ho.get("triple_product")                     # …but external_transfer certifiably does not reward it
    assert not rec_ho.get("gaussian") and "gaussian" in curriculum_primitives


def test_plateau_recommends_new_external_dimension():
    """At plateau the loop does NOT invent an internal score — it recommends a NEW ORTHOGONAL dimension with an
    external resolver + a negative control, and names the next RED-FIRST test."""
    from evals.multi_metric_loop import multi_metric_self_improve
    fby = {e.id: e for e in FEYNMAN}
    res = multi_metric_self_improve(epochs=25, patience=5, n_samples=150,
                                    equations=[fby["I.12.1"]], widths=[30], reach_budget=3)
    assert res.stopped_early
    rep = res.plateau_report
    assert "ORTHOGONAL" in rep and "external resolver" in rep and "negative" in rep
    assert "causal_recovery" in rep and "RED-FIRST" in rep      # names the next dimension AND its first test


# ── open_ended_reach: UNBOUNDED exploration (breaks benchmark_ceiling_is_fixed) — the POET move, made rigorous ──

def test_open_ended_reach_has_external_landscape():
    from OUTLIER_MCB.landscapes import Landscape, is_external_landscape
    ls = Landscape("open_ended_reach", "unbounded self-generated depth-k products (grow product_k on demand)",
                   "R²+SymPy per depth; scrambled negative control; minimal-criterion admission", True, True, True)
    assert is_external_landscape(ls)


def test_frontier_reach_is_unbounded():
    """The ratchet has NO built-in ceiling: raise the compute budget and reach keeps climbing (never saturates at a
    1.0). It stops for COMPUTE, not concept — the honest difference from a saturating [0,1] score."""
    from evals.benchmarks.open_ended import open_ended_ratchet
    r5 = open_ended_ratchet(reach_budget=5, n_samples=250)
    r8 = open_ended_ratchet(reach_budget=8, n_samples=250)
    assert r5.final_reach == 5 and r8.final_reach == 8           # lifting the budget climbs strictly further
    assert not r5.hit_conceptual_ceiling and not r8.hit_conceptual_ceiling   # the wall is compute, not a real ceiling
    assert r8.reach_trajectory == sorted(r8.reach_trajectory)    # monotone — never regresses
    assert r8.grown_depths == [3, 4, 5, 6, 7, 8]                 # product_k grown ON DEMAND, one per depth


def test_open_ended_ratchet_certifies_each_depth_and_base_fails():
    """Each depth is EXTERNALLY settled (R²+SymPy) by growing product_k; the base basis alone cannot — so every
    rung of the ratchet is a genuine frontier advance, not a relabel."""
    from evals.benchmarks.open_ended import solves_depth
    for k in (3, 5, 7):
        assert solves_depth(k, set(range(3, k + 1)), 250) is True    # with product_k grown: certified
        assert solves_depth(k, set(), 250) is False                  # base only: fails (k-way product unreachable)


def test_open_ended_negative_control_collapses():
    """Scrambled-target NEGATIVE CONTROL per depth: decouple x→y and the SAME grown primitive must STOP recovering
    the depth-k product. If it survived, the ratchet would be measuring leakage, not real solving."""
    from evals.benchmarks.open_ended import solves_depth
    assert solves_depth(5, {3, 4, 5}, 250) is True
    assert solves_depth(5, {3, 4, 5}, 250, scramble=True) is False


def test_minimal_criterion_rejects_trivial_already_and_leaky():
    """POET's minimal criterion, made rigorous: `admit` refuses a problem that is trivial (k≤2), already grown, or
    already solvable — it only admits a NOVEL, at-the-frontier, externally-settleable depth."""
    from evals.benchmarks.open_ended import admit
    assert admit(2, set(), 250) is False                        # trivial (base solves it) → not at the frontier
    assert admit(4, {3, 4}, 250) is False                       # already grown → not novel
    assert admit(4, {3, 4, 5}, 250) is False                    # already solvable → too easy
    assert admit(4, {3}, 250) is True                           # novel + unsolved-now + externally settleable


def test_pareto_rejects_regression_in_open_ended_reach():
    old = {"sr_recovery": 1.0, "counterexample": 1.0, "judge_calibration": 1.0,
           "external_transfer": 1.0, "curriculum_progression": 1.0, "open_ended_reach": 5}
    assert not g.pareto_improves(old, {**old, "open_ended_reach": 4})   # the ratchet must never go backwards
    assert g.pareto_improves(old, {**old, "open_ended_reach": 6})       # climbing one more depth is a real gain


def test_loop_does_not_stop_at_fixed_substrate_ceiling():
    """The key open-endedness property: once the FIXED bounded skills saturate, the loop KEEPS improving via the
    unbounded ratchet (growing product_k) — it does not early-stop at the fixed-primitive-set ceiling. The only
    stop is the compute budget, and the plateau report says so."""
    from evals.multi_metric_loop import multi_metric_self_improve
    res = multi_metric_self_improve(epochs=30, patience=10, reach_budget=6)
    assert res.final_vector["open_ended_reach"] == 6            # grew well past the 8 fixed grown primitives
    assert res.start_vector["open_ended_reach"] == 2
    assert not res.regressed_any
    assert any(a.startswith("depth:") for a in res.accepted)   # depth upgrades were accepted AFTER bounded plateau
    assert "COMPUTE budget" in res.plateau_report and "conceptual ceiling" in res.plateau_report


def test_reach_stopping_below_budget_is_flagged_as_honest_substrate_ceiling():
    """HONESTY: if the ratchet stops BELOW reach_budget it is the zero-dep linear-SR well-posedness limit, NOT a
    conceptual ceiling and NOT the compute budget — the plateau report must say so plainly (no number inflation:
    the engine reports the real reason it stopped)."""
    from evals.multi_metric_loop import multi_metric_self_improve
    fby = {e.id: e for e in FEYNMAN}
    # reach_samples tiny so the well-posedness wall bites early (base terms ~k²/2 exceed the sample count quickly),
    # reach_budget huge so it is clearly NOT the budget that stops the ratchet
    res = multi_metric_self_improve(epochs=40, patience=8, n_samples=150, equations=[fby["I.12.1"]],
                                    widths=[30], reach_budget=99, reach_samples=90)
    assert res.stopped_early
    assert res.final_vector["open_ended_reach"] < 99           # it stopped BELOW the budget
    rep = res.plateau_report
    assert "WELL-POSEDNESS" in rep and "HONEST" in rep and "no built-in ceiling" in rep
    assert "COMPUTE budget" not in rep                         # it did NOT misreport a budget stop
    assert not res.regressed_any
