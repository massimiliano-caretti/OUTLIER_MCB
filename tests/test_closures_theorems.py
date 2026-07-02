"""test_closures_theorems — FIX A–E from the MIL/DeepSets failure. Golden labels for closure membership,
the honest verdict ladder, mandatory real prior-art, the representation-theorem registry/brief, and the
proved-theorem novelty check. Plus the rigor anti-regression: MRE/CHORD/soft-top-k are INSIDE the box forever.
Offline, deterministic, additive (no API broken)."""
import OUTLIER_MCB as m
from OUTLIER_MCB.pack import DomainPack
from OUTLIER_MCB.core import Assumption


def _mil_pack(closures=("DEEPSETS",)):
    return DomainPack(name="mil", assumptions=[Assumption("readout_is_mean_of_phi", "the readout is the mean", "", "")],
                      dimension_of={"readout_is_mean_of_phi": "READOUT"},
                      axes={"READOUT": {"priority": 1, "verdict": "breaking the readout changes the function class"}},
                      universal_closures=list(closures))


# ── FIX A: closure-membership golden labels ───────────────────────────────────────────────────────────
GOLDEN_INSIDE_DEEPSETS = {
    "mean": "R = mean(e) over the bag",
    "rational_power_sum": "R = sum(e^3) / (tau + sum(e^2))",
    "soft_top_k": "R = sum of softmax(e/T) * e  (attention-weighted, soft-top-k)",
    "power_mean_gem": "R = generalized power-mean (GeM) of the per-instance scores e",
    "cvar": "R = CVaR_alpha of the per-instance scores",
}


def test_fix_a_inside_deepsets_golden():
    for name, readout in GOLDEN_INSIDE_DEEPSETS.items():
        assert m.reduces_to_closure(readout, "DEEPSETS") == "INSIDE", name
        assert m.closure_membership(readout, _mil_pack())["verdict"] == "INSIDE_THE_BOX", name


def test_fix_a_bag_conditioned_phi_is_outside_deepsets():
    bag = "R = sum_i phi(x_i, S) where phi is conditioned on the whole set (instances attend to each other)"
    assert m.reduces_to_closure(bag, "DEEPSETS") == "OUTSIDE"
    assert m.closure_escape_proven(bag, _mil_pack()) is True       # OUTSIDE the only declared closure → escape


def test_convolution_closure_generalises_to_a_second_domain():
    # a bounded LINEAR TRANSLATION-EQUIVARIANT map is a convolution (Kondor & Trivedi 2018): so a "new"
    # linear shift-equivariant layer is INSIDE the closure — the criterion is not set-specific.
    for readout in ["a linear translation-equivariant filter with a shared kernel slid over the image",
                    "a novel linear translation-equivariant operator with tied weights across positions",
                    "a dilated convolution with a spaced weight-shared kernel"]:
        assert m.reduces_to_closure(readout, "CONVOLUTION") == "INSIDE", readout
    # the sanctioned exits (break linearity / break translation-equivariance) are OUTSIDE = real escapes
    for escape in ["a convolution augmented with absolute coordinate channels (position-dependent response)",
                   "a deformable convolution whose sampling offsets are predicted from the input",
                   "a nonlinear translation-equivariant morphological operator"]:
        assert m.reduces_to_closure(escape, "CONVOLUTION") == "OUTSIDE", escape


def test_convolution_theorem_is_consultable():
    tb = m.theorem_brief("a new convolutional operator that is translation-equivariant")
    assert tb is not None and tb["closure"] == "CONVOLUTION"
    assert any("linear" in x for x in tb["admissible_exits"])       # exits name breaking linearity


def test_fix_a_inside_closure_forces_inside_the_box_in_judge():
    j = m.judge("R = sum of softmax(e/T) * e, a soft-top-k attention-weighted readout", pack=_mil_pack())
    assert j.verdict == "INSIDE_THE_BOX" and j.closure["inside_closure"] == "DEEPSETS"
    assert "exit" in j.next_step.lower()                           # routed to admissible exits


# ── RIGOR ANTI-REGRESSION: these MUST be INSIDE_THE_BOX(DeepSets) forever ──────────────────────────────
def test_rigor_anti_regression_mre_chord_softtopk_stay_inside():
    forever_inside = {
        "soft_top_k": "soft-top-k readout: sum of softmax(e/T) * e",
        "MRE": "MRE: the mean of e plus a residual sum of per-instance deviations from the mean",
        "CHORD": "CHORD: concatenation of per-instance pooled moments (sum, mean, and max-pool of e)",
    }
    pack = _mil_pack()
    for name, readout in forever_inside.items():
        assert m.closure_membership(readout, pack)["verdict"] == "INSIDE_THE_BOX", name


# ── FIX B: honest verdict ladder — ALIVE_OWN_WORLD is not novelty ──────────────────────────────────────
def test_fix_b_not_yet_novel_without_closure_escape():
    # an idea the detectors cannot place (UNKNOWN membership) AND no proven escape → NOT_YET_NOVEL
    an = m.architectural_novelty("a readout based on some unspecified structure", _mil_pack(),
                                 evidence={"closure_escape": False})
    assert an["state"] == "NOT_YET_NOVEL" and an["can_say_novel"] is False
    md = an["markdown"].lower()
    assert "not yet novel — closure-escape mancante" in md
    assert "innovative" not in md and "genuinely novel" not in md and "is novel" not in md


def test_fix_b_alive_own_world_cannot_be_called_novel():
    # closure-escape proven but NO prior-art → ALIVE_OWN_WORLD, still not presentable as novel
    an = m.architectural_novelty("x", _mil_pack(), evidence={"closure_escape": True, "prior_art_checked": False})
    assert an["state"] == "ALIVE_OWN_WORLD" and an["can_say_novel"] is False
    # with closure-escape AND prior-art AND transfer → the only fully-licensed rung
    full = m.architectural_novelty("x", _mil_pack(), evidence={"closure_escape": True, "prior_art_checked": True,
                                                               "transfer_test_passed": True})
    assert full["state"] == "ALIVE_ARCHITECTURAL" and full["can_say_novel"] is True


def test_fix_b_language_guard_blocks_innovative_without_escape():
    g = m.gate_claim_language("an innovative new architecture", {"closure_escape": False, "prior_art_checked": False})
    assert g["allowed"] is False and "innovative" not in g["rewritten"].lower()
    ok = m.gate_claim_language("an innovative architecture", {"closure_escape": True, "prior_art_checked": True})
    assert ok["allowed"] is True


# ── FIX C: real prior-art mandatory; no NO_PRIOR_ART from lexical-only ─────────────────────────────────
def test_fix_c_no_provider_is_incomplete_never_no_prior_art():
    st = m.honest_prior_art_status("a genuinely new readout nobody has tried")
    assert st["status"] == "INCOMPLETE_ONLINE_SEARCH"
    # even an offline provider (lexical, no online scope) cannot yield NO_PRIOR_ART
    offline = m.CallableProvider(lambda q: {"matches": []})
    assert m.honest_prior_art_status("x", offline)["status"] == "INCOMPLETE_ONLINE_SEARCH"


def test_fix_c_real_online_search_with_urls_can_conclude():
    def online(q):
        return {"matches": [{"title": f"work {i}", "url": f"http://x/{i}", "similarity": 0.05} for i in range(4)],
                "novelty_scope": "ONLINE_PRIOR_ART_CHECKED", "coverage_level": "MULTI"}
    st = m.honest_prior_art_status("a far-out idea", m.CallableProvider(online))
    assert st["status"] != "INCOMPLETE_ONLINE_SEARCH" and st["real_sources"] >= 3


# ── FIX D: representation-theorem registry surfaces in the brief ──────────────────────────────────────
def test_fix_d_brief_cites_deepsets_and_routes_to_exits():
    tb = m.theorem_brief("invent a new permutation-invariant pooling operator")
    assert tb is not None and "deepsets" in tb["theorem"].lower()
    assert tb["admissible_exits"] and any("condition" in e.lower() for e in tb["admissible_exits"])
    pf = m.preflight_creative_request("a new permutation-invariant pooling operator")
    assert "theorem_brief" in pf and "DeepSets" in pf["instructions"]


def test_fix_d_no_theorem_for_unrelated_request():
    assert m.theorem_brief("a faster web cache eviction policy") is None


# ── FIX E: proved-theorem novelty check ───────────────────────────────────────────────────────────────
def test_fix_e_power_mean_is_classical():
    r = m.classify_proved_theorem("the power-mean is >= the mean (power mean inequality)")
    assert r["classical"] is True and r["label"] == "FORMALLY_PROVED (CLASSICAL)"


def test_fix_e_unknown_statement_is_novelty_pending():
    r = m.classify_proved_theorem("the gizmo-operator preserves the frobnication invariant under twiddling")
    assert r["classical"] is False and "NOVELTY-PENDING-PRIOR-ART" in r["label"]


# ── generative steering: inside-closure penalized, exit / new-information rewarded (gated, no regression) ──
def test_score_idea_penalizes_closure_rewards_exit_and_new_information():
    from OUTLIER_MCB.generators.base import Candidate
    from OUTLIER_MCB.scoring import score_idea
    pack = _mil_pack()
    inside = Candidate(name="R = mean(e)", operator="proposed", breaks=["READOUT"], assumptions=["readout_is_mean_of_phi"],
                       negation="R = mean(e)")
    exit_ = Candidate(name="condition phi on the whole set", operator="proposed", breaks=["READOUT"],
                      assumptions=["readout_is_mean_of_phi"], negation="phi conditioned on the whole set",
                      needs=["a new observable / new information"])
    si, se = score_idea(inside, pack=pack), score_idea(exit_, pack=pack)
    assert si.get("closure_penalty") == 1.0 and se["composite"] > si["composite"]   # the exit beats the box


def test_score_idea_unchanged_for_packs_without_closures():
    from OUTLIER_MCB.generators.base import Candidate
    from OUTLIER_MCB.scoring import score_idea
    pack = m.get_pack("coding")                                    # no universal_closures declared
    c = Candidate(name="x", operator="proposed", breaks=["COST"], assumptions=["token_bucket"], negation="x")
    f = score_idea(c, pack=pack)
    assert "closure_penalty" not in f and "new_information_bonus" not in f   # zero impact (no regression)


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
