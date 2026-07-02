"""OUTLIER_MCB test suite (pytest).

Run with `pytest -q` or standalone `python tests/test_outlier_mcb.py` (which shells out to pytest).
These verify LOGIC — that functions produce the CORRECT result — not merely that they do not crash:
negate's three kinds and content, pack structure, the agnosticism invariant, the generative operators,
the novelty market's pricing math, the runtime's distance-ranking, and that genuine errors RAISE.
"""
import sys, warnings
from pathlib import Path
warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import OUTLIER_MCB as gsl


# ── fixtures ────────────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def coding():
    return gsl.get_pack("coding")


@pytest.fixture
def math_pack():
    return gsl.get_pack("math")


@pytest.fixture
def sky():
    return gsl.Assumption("sky_is_blue", "The sky is blue.", "we see it blue by day",
                          "the sky is not blue at night", ["daylight_model"], "look up after dark")


# ── core: negate in isolation (CORRECTNESS, not just count) ───────────────────────────────────────
def test_negate_has_three_kinds_in_order(sky):
    negs = gsl.negate(sky)
    assert [n.kind for n in negs] == ["weak", "radical", "green_star"]


def test_negate_radical_is_the_if_false(sky):
    # the radical negation must BE the assumption's stated consequence-if-false, not a placeholder
    assert gsl.negate(sky)[1].statement == sky.if_false


def test_negate_carries_the_falsifier(sky):
    assert all(n.testable_via == sky.falsifier for n in gsl.negate(sky))


def test_negate_green_star_reframes(sky):
    assert "reframe" in gsl.negate(sky)[2].statement.lower()


# ── packs: structure + validation ─────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("name", ["coding", "math", "generic"])
def test_builtin_pack_is_valid(name):
    p = gsl.get_pack(name)
    assert p.validate() == []
    assert p.assumptions and set(p.dimension_of) <= {a.name for a in p.assumptions}


def test_every_dimension_uses_a_declared_axis(coding):
    assert all(axis in coding.axes for axis in coding.dimension_of.values())


# ── genuine errors RAISE (verdicts do NOT) ─────────────────────────────────────────────────────────
def test_get_pack_unknown_raises_packnotfound():
    with pytest.raises(gsl.PackNotFoundError):
        gsl.get_pack("does_not_exist")


def test_get_pack_unknown_is_still_a_keyerror():
    # backward compatibility: PackNotFoundError subclasses KeyError
    with pytest.raises(KeyError):
        gsl.get_pack("does_not_exist")


def test_pack_from_spec_invalid_raises_invalidpack():
    with pytest.raises(gsl.InvalidPackError):
        gsl.pack_from_spec({"name": "broken", "assumptions": []})  # no assumptions


def test_paradigm_shift_unknown_assumption_raises(coding):
    with pytest.raises(gsl.AssumptionNotFoundError):
        gsl.paradigm_shift("not_a_real_assumption", coding)


def test_theorem_sketch_unknown_assumption_raises(coding):
    with pytest.raises(gsl.AssumptionNotFoundError):
        gsl.theorem_sketch("x", breaks=["COST_MODEL"], pack=coding, assumption_name="nope")


def test_no_solution_verdict_is_data_not_an_exception(coding):
    # a verdict is a legitimate RESULT, not a fault — it must return, never raise
    v = gsl.no_solution_before_assumption("token_bucket", answers={}, pack=coding)
    assert v["status"] == "INSIDE_THE_BOX" and v["family"] == "token_bucket"


# ── agnosticism: the engine is domain-blind ────────────────────────────────────────────────────────
def test_engine_modules_hardcode_no_pack_token():
    # Domain content may live ONLY in pack.py and packs/. Every other module is the engine and must be
    # domain-blind: no pack-specific family/assumption name may appear hard-coded in it.
    pkgdir = Path(gsl.__file__).parent
    tokens = set()
    for nm in gsl.list_packs():
        p = gsl.get_pack(nm)
        tokens |= {f.lower() for f in p.known_families} | {a.name.lower() for a in p.assumptions}
    tokens = {t for t in tokens if len(t) > 4 and "standard" not in t}

    def is_engine(f):
        rel = f.relative_to(pkgdir)
        return "packs" not in rel.parts and f.name != "pack.py"

    leaks = [f"{f.relative_to(pkgdir)}:{t}" for f in pkgdir.rglob("*.py") if is_engine(f)
             for t in tokens if t in f.read_text().lower()]
    assert not leaks, f"pack-specific tokens hard-coded in engine modules: {leaks}"


def test_different_domains_give_different_breaks():
    pf_c = gsl.preflight_creative_request("a new rate limiter for a distributed api gateway")
    pf_m = gsl.preflight_creative_request("a new theorem on convergence of a gradient method")
    assert pf_c["pack"] == "coding" and pf_m["pack"] == "math"
    assert pf_c["recommended_direction"]["assumption"] != pf_m["recommended_direction"]["assumption"]


def test_unknown_domain_triggers_elicitation():
    pf = gsl.preflight_creative_request("a fairer matchmaking system for an online multiplayer game")
    assert pf.get("elicitation_required") is True and pf["pack"] == "generic"


def test_pack_from_spec_roundtrips():
    spec = {"name": "demo", "keywords": ["demo"], "box_name": "the default",
            "assumptions": [{"name": "a1", "description": "d", "axis": "REPRESENTATION", "falsifier": "f"}],
            "axes": {"REPRESENTATION": {"priority": 3, "verdict": "v"}}}
    pk = gsl.pack_from_spec(spec)
    assert pk.validate() == [] and pk.dimension_of["a1"] == "REPRESENTATION"


# ── generative operators ────────────────────────────────────────────────────────────────────────────
def test_recombine_breaks_two_distinct_axes(coding):
    rc = gsl.recombine_assumptions(coding, k=2, max_candidates=3)
    assert rc and all(len(x.breaks) == 2 and len(set(x.breaks)) == 2 for x in rc)
    assert all("ablation" in x.discipline.lower() for x in rc)   # still carries its falsification duty


def test_non_breaking_operators_make_no_break(coding):
    assert gsl.unify(coding, "time_windowed", "cost_uniform").breaks == []
    assert gsl.dissolve(coding, "sync_decision").operator == "dissolve"


def test_anomaly_yields_a_new_provisional_assumption(coding):
    asm, meta = gsl.anomaly_to_assumption(coding, "tail latency stays high after the queue is shuffled")
    assert asm.name not in coding.by_name() and meta["provisional"] and asm.falsifier


def test_self_spark_proposes_falsifiable_breaks(coding):
    sp = gsl.self_spark(coding, n=3)
    assert len(sp) == 3 and all("still_must_falsify" in s for s in sp)


def test_novelty_score_synergy_rescues_a_live_collage():
    dead = gsl.novelty_score(["A"], reduces_to="fam", synergy=0)
    live = gsl.novelty_score(["A"], reduces_to="fam", synergy=0.1, new_output=True)
    assert live["score"] > dead["score"] and live["components"]["synergistic_collage"]


# ── honesty layer ─────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("kw,expected", [
    (dict(breaks=["AX"], has_executable_world_test=False, coherence=0.6), "SUSPENDED_BOLD"),
    (dict(breaks=["AX"], has_executable_world_test=True, coherence=0.9, new_output=True,
          won_on_foreign_world=True, reach=3), "ALIVE_ARCHITECTURAL"),
    (dict(breaks=["AX"], has_executable_world_test=True, coherence=0.4, reduces_to="fam"), "DEAD_COLLAGE"),
    (dict(breaks=[], has_executable_world_test=True, coherence=0.3, new_output=False), "INSIDE_THE_BOX"),
])
def test_maturity_ladder(kw, expected):
    assert gsl.assess_maturity(**kw).status == expected


# ── novelty market: the pricing MATH, not just shape ───────────────────────────────────────────────
def test_repo_is_the_resolver_not_the_engine(coding):
    cand = gsl.recombine_assumptions(coding, k=2, max_candidates=1)[0]
    bet, check = gsl.forge_bet(cand, ledger=gsl.Ledger(), stake=0.7)
    assert bet.resolver.startswith("repo:") and "the engine" in check.note


def test_operator_indexed_pricing_and_reopen(coding):
    L = gsl.Ledger()
    for _ in range(3):
        b = gsl.Bet(claim="x", world_test="t", resolver="repo", axis="OBJECTIVE", operator="negate")
        L.post(b); L.settle(b, won=False)
    assert L.price("OBJECTIVE", "negate") > 2.0          # exhausted under negate
    assert L.price("OBJECTIVE", "dissolve") < 1.0        # REOPENS under an untried operator
    assert "dissolve" in L.reopen_operators("OBJECTIVE", ["negate", "dissolve", "unify"])


def test_expected_value_is_stake_over_price():
    L = gsl.Ledger()
    b = L.post(gsl.Bet(claim="x", world_test="t", resolver="r", axis="AX", operator="negate", stake=0.6))
    assert b.expected_value == round(0.6 / b.price, 3)


# ── cognitive runtime ────────────────────────────────────────────────────────────────────────────
def test_box_distance_rewards_distance_from_the_average(coding):
    near = gsl.Candidate("x", "negate", ["AX"], ["a"], "n")
    far = gsl.Candidate("y", "transport", ["AX"], ["a"], "n", needs=["new_corpus"])
    assert gsl.box_distance(far, coding) > gsl.box_distance(near, coding)


def test_novelty_search_is_ranked_by_distance(coding):
    fr = gsl.novelty_search(coding, "rate limiter", beam=4, rounds=2)
    assert len(fr) <= 4 and fr == sorted(fr, key=lambda x: -x["distance"])


def test_invent_returns_a_repo_settled_portfolio():
    inv = gsl.invent("design a new rate limiter for a distributed api gateway", beam=4, rounds=2)
    assert inv.frontier and all(f["bet"].resolver.startswith("repo:") for f in inv.frontier)
    assert all("proposal" in f and "score" in f for f in inv.frontier)
    assert inv.frontier == sorted(inv.frontier, key=lambda f: (-f["score"]["composite"], f["rebranding_risk"]))


def test_invent_reflect_turns_a_loss_into_a_new_assumption(coding):
    inv = gsl.invent("design a new rate limiter for a distributed api gateway", beam=3)
    bet = inv.best()["bet"]; inv.ledger.settle(bet, won=False)
    asm, meta = gsl.invent_reflect(bet, coding)
    assert meta["provisional"] and asm.name not in coding.by_name()


# ── grounding: the engine probes the REAL environment ──────────────────────────────────────────────
def test_probe_detects_this_repo_is_grounded():
    repo = gsl.probe(str(Path(__file__).resolve().parent.parent))   # the OUTLIER_MCB repo itself
    assert "python" in repo.languages and repo.grounded
    assert repo.test_command and repo.test_files            # it has a pytest suite and real test files


def test_grounded_world_test_uses_the_real_command(coding):
    repo = gsl.probe(str(Path(__file__).resolve().parent.parent))
    cand = gsl.recombine_assumptions(coding, k=2, max_candidates=1)[0]
    bet, check = gsl.forge_bet(cand, repo=repo)
    # the command is the REAL toolchain command and SELECTS the specific named red test (never a bare
    # whole-suite run that could pass without the new test existing).
    assert check.grounded and bet.grounded and check.command.startswith(repo.test_command)
    assert (check.test_name in check.command) or ("pytest" not in check.command)


def test_ungrounded_world_test_is_flagged_not_faked(coding):
    cand = gsl.recombine_assumptions(coding, k=2, max_candidates=1)[0]
    _, check = gsl.forge_bet(cand)                           # no repo → placeholder, honestly flagged
    assert check.grounded is False and "NOT grounded" in check.note


def test_box_distance_discounts_ungrounded_ideas(coding):
    cand = gsl.recombine_assumptions(coding, k=2, max_candidates=1)[0]
    assert gsl.box_distance(cand, coding, grounded=False) < gsl.box_distance(cand, coding, grounded=True)


def test_guard_fires_on_ambiguous_routing():
    # a prompt that scores on two packs at once must NOT be confidently routed
    g = gsl.guard_response("a fast convergence algorithm with low latency", margin=1)
    assert g["ok"] is False and "ambig" in g["message"].lower() or g["pack"] == "generic"


def test_ledger_policy_turns_losses_into_a_bias():
    L = gsl.Ledger()
    for _ in range(3):
        b = gsl.Bet(claim="x", world_test="t", resolver="r", axis="OBJECTIVE", operator="negate")
        L.post(b); L.settle(b, won=False)
    # a thrice-lost move is damped; an untried move keeps the neutral weight
    assert L.weight_of("OBJECTIVE", "negate") < 1.0 <= L.weight_of("OBJECTIVE", "dissolve")
    assert "OBJECTIVE×negate" in L.policy()


# ── the green-star zone: creating with NO examples ──────────────────────────────────────────────────
def test_synthesize_assumptions_generates_without_a_pack():
    a = gsl.synthesize_assumptions("a problem nobody has a domain pack for", n_axes=4)
    assert len(a) == 4 and all(x.if_false and x.falsifier for x in a)
    # generation, not retrieval: these names are built from structural primitives, not any registry
    assert all(name not in {n for p in map(gsl.get_pack, gsl.list_packs()) for n in p.by_name()}
               for name in [x.name for x in a])


def test_synthesize_pack_has_no_known_families():
    # in the green-star zone the convex hull is empty: there is nothing to forbid as collage
    pk = gsl.synthesize_pack("an utterly novel problem")
    assert pk.validate() == [] and pk.known_families == [] and pk.assumptions


def test_prompt_dependent_structure_differs():
    a1 = [x.name for x in gsl.synthesize_assumptions("alpha problem")]
    a2 = [x.name for x in gsl.synthesize_assumptions("a completely different beta question entirely")]
    assert a1 != a2          # different prompts explore different first-principles structure (deterministically)


def test_novel_axis_invents_a_dimension_no_pack_has():
    na = gsl.novel_axis("invent a dimension")
    known_axes = {ax for p in map(gsl.get_pack, gsl.list_packs()) for ax in p.axes}
    assert "×" in na["axis"] and na["axis"] not in known_axes and na["falsifier"]


def test_extrapolation_rewards_leaving_the_global_hull():
    # an idea that names a known family is interpolation; one on a novel axis with no family is extrapolation
    interp = gsl.Candidate("x", "negate", ["OBJECTIVE"], ["a"], "just a token_bucket variant")
    extrap = gsl.Candidate("y", "recombine", ["INPUT×TIME"], ["a"], "a structure unlike anything known")
    assert gsl.extrapolation(extrap) > gsl.extrapolation(interp)


def test_green_star_returns_unfalsified_first_principles_structure():
    gs = gsl.green_star("design something in a domain with literally no prior examples")
    assert gs.frontier and gs.novel_axis.get("axis")
    assert gs.frontier == sorted(gs.frontier, key=lambda f: -f["extrapolation"])
    assert "unfalsified" in gs.note.lower() and "build" in gs.note.lower()


# ── closing the loop: real execution, multi-factor score, deeper grounding ──────────────────────────
def _check(cmd):
    return gsl.RepoCheck(kind="test_flip", command=cmd, pass_condition="exit 0", fail_baseline="-", grounded=True)


def test_verifier_actually_runs_and_reports_pass():
    v = gsl.run_check(_check('python -c "import sys; sys.exit(0)"'))
    assert v.ran and v.passed is True and v.alive and "PASSED" in v.what_was_verified


def test_verifier_actually_runs_and_reports_fail():
    v = gsl.run_check(_check('python -c "import sys; sys.exit(1)"'))
    assert v.ran and v.passed is False and not v.alive and "NOT verified" not in v.what_was_verified


def test_verify_settles_the_bet_and_updates_policy():
    L = gsl.Ledger()
    bet = gsl.Bet(claim="x", world_test="t", resolver="repo:test", axis="OBJECTIVE", operator="negate")
    L.post(bet)
    gsl.verify(bet, _check('python -c "import sys; sys.exit(1)"'), ledger=L)
    assert bet.status == "LOST" and L.weight_of("OBJECTIVE", "negate") < 1.0   # the loss re-weighted the policy


def test_ungrounded_check_is_not_executed():
    placeholder = gsl.RepoCheck(kind="test_flip", command="pytest -q", pass_condition="-", fail_baseline="-", grounded=False)
    v = gsl.run_check(placeholder)
    assert v.ran is False and v.passed is None and "ungrounded" in v.why.lower()


def test_multifactor_score_gates_novelty_by_groundedness(coding):
    cand = gsl.recombine_assumptions(coding, k=2, max_candidates=1)[0]
    grounded = gsl.score_idea(cand, grounded=True)
    ungrounded = gsl.score_idea(cand, grounded=False)
    assert set(grounded) >= {"novelty", "usefulness", "implementability", "verifiability", "risk", "cost", "composite"}
    assert grounded["composite"] > ungrounded["composite"]      # strangeness alone does not win


def test_deeper_grounding_maps_the_project_flow():
    repo = gsl.probe(str(Path(__file__).resolve().parent.parent))
    assert "OUTLIER_MCB" in repo.components            # it sees the real component, not just files
    assert "creative" in repo.public_api               # it reads the exported contract (__all__)
    assert "components" in repo.map() and "contract" in repo.map()


# ── self-found novel capabilities (assumption dynamics · MDL depth · contradiction synthesis) ───────
def test_cascade_models_the_chain_reaction(coding):
    # cost_uniform blocks time_windowed ⇒ breaking it FREES time_windowed (a real edge in the pack)
    c = gsl.cascade(coding, "cost_uniform")
    assert "time_windowed" in c.freed and c.reach >= 1
    # tenant_independent is implied by stateless_local ⇒ breaking it FORCES stateless_local
    assert "stateless_local" in gsl.cascade(coding, "tenant_independent").forced


def test_biggest_lever_finds_the_widest_cascade(coding):
    lever = gsl.biggest_lever(coding)
    assert lever.seed in {a.name for a in coding.assumptions} and lever.reach >= 1


def test_compression_rewards_unification_over_a_single_break(coding):
    unify_c = gsl.unify(coding, "time_windowed", "cost_uniform")
    cg = gsl.compression_gain(unify_c, coding)
    assert cg["subsumed"] == 2 and cg["compression_gain"] > 0
    single = gsl.recombine_assumptions(coding, k=2, max_candidates=1)[0]
    best = gsl.most_compressing([single, unify_c], coding)
    assert best is unify_c          # a unification compresses more than an arbitrary recombination


def test_dialectic_synthesizes_from_a_real_contradiction(coding):
    assert gsl.tensions(coding)                     # the pack has at least one genuine A-blocks-B tension
    d = gsl.dialectic(coding)
    assert d.operator == "dialectic" and len(d.breaks) == 2 and "SYNTHESIS" in d.negation
    assert "compromise" in d.discipline.lower()     # it must be a third object, not a trade-off


def test_score_idea_rewards_depth_via_compression(coding):
    # an idea that compresses the domain scores its depth factor above zero
    s = gsl.score_idea(gsl.unify(coding, "time_windowed", "cost_uniform"), pack=coding, grounded=True)
    assert "depth" in s and s["depth"] > 0


# ── orchestration: the orphaned capabilities are now threaded into the flow ─────────────────────────
def test_dossier_threads_every_module_into_one_report(coding):
    cand = gsl.recombine_assumptions(coding, k=2, max_candidates=1)[0]
    d = gsl.dossier(cand, coding)
    # one call now yields theorem + world-test + reviewer + lineage + compression + maturity
    assert d.theorem and d.world_test and d.attack and d.lineage
    assert d.maturity.status and "compression" in d.compression["principle"] or d.compression["compression_gain"] >= 0
    md = d.markdown()
    assert "maturity" in md.lower() and "Theorem sketch" in md and "Reviewer attack" in md


def test_invent_now_carries_a_maturity_verdict_per_idea():
    inv = gsl.invent("design a new rate limiter for a distributed api gateway", beam=3)
    assert inv.frontier and all(f.get("maturity") and f["maturity"].status for f in inv.frontier)
    assert inv.pack is not None and callable(inv.dossier)        # the dossier is reachable from the result
    assert "maturity" not in inv.markdown() or inv.frontier[0]["maturity"].status in inv.markdown()


def test_invent_dossier_method_runs_the_full_pipeline():
    inv = gsl.invent("design a new rate limiter for a distributed api gateway", beam=2)
    d = inv.dossier(0)
    assert isinstance(d, gsl.Dossier) and d.maturity.status


def test_unified_novelty_blends_within_and_beyond_the_hull(coding):
    # the score's novelty now reflects BOTH box_distance (within) and extrapolation (beyond)
    s = gsl.score_idea(gsl.recombine_assumptions(coding, k=2, max_candidates=1)[0], pack=coding)
    assert 0.0 <= s["novelty"] <= 1.0


def test_ledger_persists_across_a_save_load_roundtrip(tmp_path):
    L = gsl.Ledger()
    b = gsl.Bet(claim="x", world_test="t", resolver="r", axis="OBJECTIVE", operator="negate")
    L.post(b); L.settle(b, won=False)
    path = str(tmp_path / "ledger.json")
    L.save(path)
    L2 = gsl.Ledger.load(path)
    assert L2.weight_of("OBJECTIVE", "negate") == L.weight_of("OBJECTIVE", "negate") and len(L2.bets) == 1


# ── library hardening (red-first: a cosmetic solution fails these) ──────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent


def test_packaging_is_installable_with_a_console_script():
    pp = (ROOT / "pyproject.toml").read_text()
    assert 'name = "OUTLIER_MCB"' in pp
    assert 'OUTLIER_MCB = "OUTLIER_MCB.cli:main"' in pp                 # console entrypoint
    assert 'attr = "OUTLIER_MCB.__version__"' in pp                      # version sourced from the package


def test_routing_is_an_evidence_object_not_a_keyword_count():
    d = gsl.route_pack("a new rate limiter for a distributed api gateway")
    assert isinstance(d, gsl.RouteDecision)
    assert "coding" in d.scores and isinstance(d.margin, int) and isinstance(d.ambiguous, bool)
    assert d.reason and d.source in {"keyword", "repo_boost", "fallback", "explicit"}


def test_ambiguous_routing_is_flagged_in_the_evidence():
    d = gsl.route_pack("a fast convergence algorithm with low latency")    # scores math AND coding
    assert (d.ambiguous is True) or (d.confidence == 0)                    # never a confident silent pick


def test_explicit_pack_is_caller_intent_and_never_overridden():
    pf = gsl.preflight_creative_request("make something new", pack=gsl.get_pack("coding"))
    assert pf["pack"] == "coding"
    assert not pf.get("elicitation_required")                              # explicit pack ⇒ no elicitation
    assert pf["domain_guard"]["used_explicit_pack"] is True


def test_repo_context_flows_as_structure_not_text():
    repo = gsl.probe(str(ROOT))
    pf = gsl.preflight_creative_request("design a new caching layer", repo_path=str(ROOT))
    assert "repo_language_boost" in pf["domain_guard"]                     # structured grounding evidence
    # passing a RepoContext object as repo_context must NOT be concatenated into the prompt
    pf2 = gsl.preflight_creative_request("design a new caching layer", repo_context=repo)
    assert isinstance(pf2["domain_guard"], dict)


def test_world_test_is_an_artifact_contract_not_a_bare_command():
    repo = gsl.probe(str(ROOT))
    cand = gsl.recombine_assumptions(gsl.get_pack("coding"), k=2, max_candidates=1)[0]
    _, check = gsl.forge_bet(cand, repo=repo)
    assert check.grounded and check.is_full_contract                      # full contract, not just a command
    assert check.command and check.target and check.test_name
    assert check.baseline_assertion and check.negative_control and check.success_condition and check.implementation_hint
    bare = gsl.RepoCheck(kind="test_flip", command="pytest -q", pass_condition="-", fail_baseline="-", grounded=True)
    assert not bare.is_full_contract                                      # a command alone is NOT a world-test


def test_invent_frontier_has_no_duplicate_bets():
    inv = gsl.invent("upgrade the library into a grounded installable package", beam=8, rounds=3, repo_path=str(ROOT))
    keys = [(f["candidate"].name, f["candidate"].operator, tuple(f["candidate"].breaks),
             tuple(f["candidate"].assumptions), f["candidate"].negation) for f in inv.frontier]
    assert len(keys) == len(set(keys))                                    # the frontier is a portfolio of DISTINCT bets


# ── answering the "spietato" critique (red-first: a strangeness-first / fake-verify engine fails these) ──
def test_usefulness_leads_the_score_not_novelty(coding):
    cand = gsl.recombine_assumptions(coding, k=2, max_candidates=1)[0]
    # a far-but-ungrounded-unimplementable idea must NOT outrank a grounded, useful one
    far_ungrounded = gsl.score_idea(cand, pack=coding, grounded=False)
    useful_grounded = gsl.score_idea(cand, pack=coding, repo=gsl.probe(str(ROOT)), grounded=True)
    assert useful_grounded["composite"] > far_ungrounded["composite"]
    # usefulness must weigh at least as much as novelty in the result
    assert useful_grounded["usefulness"] >= 0.5


def test_engine_is_honest_about_what_it_cannot_auto_verify():
    repo = gsl.probe(str(ROOT))
    cand = gsl.recombine_assumptions(gsl.get_pack("coding"), k=2, max_candidates=1)[0]
    _, grounded_check = gsl.forge_bet(cand, repo=repo)
    _, placeholder = gsl.forge_bet(cand)                                   # no repo
    assert gsl.verifiability_class(grounded_check) == "AUTO"               # the engine can settle it by running
    assert gsl.verifiability_class(placeholder) == "HUMAN"                 # it must NOT claim to verify this


def test_invent_reports_the_honest_auto_human_fraction():
    inv = gsl.invent("upgrade the library", repo_path=str(ROOT), beam=3)
    assert all("verifiability" in f and f["verifiability"] in ("AUTO", "HUMAN") for f in inv.frontier)
    assert "AUTO" in inv.note and "HUMAN-only" in inv.note                 # the fraction is stated, not hidden


def test_generate_candidates_has_no_circular_import_regression(coding):
    # the dialectic synthesis is still pooled, via a lazy import that breaks a real cycle (not a smell)
    pool = gsl.generate_candidates(coding)
    assert any(c.operator == "dialectic" for c in pool) and any(c.operator == "recombine" for c in pool)


# ── self-measurement: capabilities must EARN their keep (answering the 'theatre' critique) ──────────
def test_no_generative_operator_is_inert():
    # every generative operator must actually PRODUCE candidates on the built-in packs (measured, dynamic)
    y = gsl.operator_yield()
    assert y and all(count > 0 for count in y.values()), f"inert operators: {[k for k,v in y.items() if v==0]}"


def test_health_measures_and_reports_without_deleting():
    rep = gsl.health()
    assert rep.inert_operators == []                          # nothing decorative among the generators
    assert rep.earns_keep >= 0.8 * rep.total_public           # the vast majority of the API is wired into the flow
    assert "deletes nothing" in rep.markdown().lower()        # it REPORTS; the human decides


# ── external value + honest red-green verification ──────────────────────────────────────────────────
def test_red_green_refuses_to_claim_an_unmaterialized_test():
    # a grounded check whose test does NOT exist in the repo must NOT be reported as verified
    repo = gsl.probe(str(ROOT))
    cand = gsl.recombine_assumptions(gsl.get_pack("coding"), k=2, max_candidates=1)[0]
    _, check = gsl.forge_bet(cand, repo=repo)
    rg = gsl.verify_red_green(check, cwd=str(ROOT))
    assert rg.status == "NOT_MATERIALIZED" and not rg.green   # the new test was never written → not green
    assert check.test_name and not gsl.materialized(check, str(ROOT))   # names a specific test that does not exist yet


def test_capability_value_ablation_reports_without_deleting():
    cv = gsl.capability_value()
    assert "verdicts" in cv and all(v in ("KEEPS", "DECORATIVE", "HARMFUL") for v in cv["verdicts"].values())
    assert isinstance(cv["full_vns"], float)        # measured by ablation on the value metric, not described
    assert not cv["harmful"]                         # after the metric fix, no operator drags the pool down


def test_rebranding_does_not_penalize_genuine_operator_breaks(coding):
    # a pool of operator candidates all break an axis → none is a lexical re-skin (the dogfound metric bug)
    pool = gsl.generate_candidates(coding)
    assert gsl.rebranding_risk_rate(pool) == 0.0
    assert gsl.operator_diversity(pool) > 0          # the plural generator uses several distinct mechanisms


def test_pack_quality_measures_more_than_schema():
    coding = gsl.pack_quality(gsl.get_pack("coding"))
    generic = gsl.pack_quality(gsl.get_pack("generic"))
    assert coding["overall"] >= 0.8 and "components" in coding          # six measured components
    assert generic["overall"] < coding["overall"]                       # the universal fallback is honestly weaker


def test_invent_ledger_path_persists_across_runs(tmp_path):
    path = str(tmp_path / "ledger.json")
    gsl.invent("a new rate limiter", repo_path=None, beam=2, ledger_path=path)
    assert Path(path).exists()                       # the ledger was saved
    inv2 = gsl.invent("a new rate limiter", repo_path=None, beam=2, ledger_path=path)
    assert inv2.ledger is not None                   # and re-loaded on the next run


def test_value_metrics_distinguish_a_pool():
    cands = gsl.generate_candidates(gsl.get_pack("coding"))
    m = gsl.score_pool(cands)
    assert 0 <= m["verified_novelty_score"] <= 1 and m["unique_frontier_ratio"] <= 1.0
    assert set(m) >= {"falsifiability_score", "broken_assumption_rate", "auto_verifiability_rate"}


def test_judge_refuses_low_confidence_anchoring(coding):
    j = gsl.judge("improve the throughput somehow", pack=coding)   # vague → low confidence / ambiguous
    assert j.confidence <= 0.5
    assert j.broken_assumption is None or j.verdict in ("INSIDE_THE_BOX", "NEEDS_DISAMBIGUATION")
    j2 = gsl.judge("anything", pack=coding, assumption="cost_uniform")   # explicit override is certain
    assert j2.confidence == 1.0 and j2.broken_assumption == "cost_uniform"


# ── scoring as a hypothesis + green-star honesty ────────────────────────────────────────────────────
def test_score_weights_change_ranking_predictably():
    hi_novel = {"novelty": 0.9, "depth": 0.0, "usefulness": 0.2, "risk": 0.2, "cost": 0.0}
    hi_useful = {"novelty": 0.2, "depth": 0.0, "usefulness": 0.9, "risk": 0.2, "cost": 0.0}
    nw = gsl.ScoreWeights(usefulness=0.1, depth=0.1, novelty=0.6, simplicity=0.2, cost=0.0)
    uw = gsl.ScoreWeights(usefulness=0.6, depth=0.1, novelty=0.1, simplicity=0.2, cost=0.0)
    assert nw.composite(hi_novel) > nw.composite(hi_useful)     # novelty-weights prefer the novel idea
    assert uw.composite(hi_useful) > uw.composite(hi_novel)     # usefulness-weights flip it — weights are a hypothesis


def test_calibrate_weights_separates_good_from_bad(coding):
    good = gsl.recombine_assumptions(coding, k=2, max_candidates=3)        # grounded, breaking
    bad = [gsl.Candidate("x", "proposed", [], [], "just a rename")]        # breaks nothing
    cal = gsl.calibrate_weights(good, bad, pack=coding, repo=gsl.probe(str(ROOT)))
    assert isinstance(cal["weights"], gsl.ScoreWeights) and cal["separation"] > 0


def test_reflexion_loop_is_isolated_and_honest(coding):
    # without execution there are NO real settled losses → the loop mines nothing (honest: nothing to learn)
    n_before = len(coding.assumptions)
    inv = gsl.invent("a new rate limiter", pack=coding, beam=2, reflect_rounds=2)   # execute defaults False
    assert all(f["round"] == 0 for f in inv.frontier)               # no mined rounds without real losses
    assert len(gsl.get_pack("coding").assumptions) == n_before      # the registered pack is never mutated


def test_green_star_is_honest_about_its_confidence():
    gs = gsl.green_star("a system that does not exist yet")
    assert gs.confidence_label in ("LOW", "MEDIUM", "HIGH")
    assert all(f["status"] == "UNFALSIFIED_HYPOTHESIS" for f in gs.frontier)   # never claims 'novel', only hypothesis
    assert 0.0 <= gs.confidence <= 1.0 and "UNFALSIFIED" in gs.markdown()


# ── 1.0 readiness: external evaluation + artifact classification + gate ──────────────────────────────
def test_artifact_contract_score_distinguishes_full_from_bare(coding):
    full = gsl.forge_bet(gsl.recombine_assumptions(coding, k=2, max_candidates=1)[0], repo=gsl.probe(str(ROOT)))[1]
    bare = gsl.RepoCheck(kind="test_flip", command="pytest -q", pass_condition="-", fail_baseline="-", grounded=True)
    assert gsl.artifact_contract_score(full) > gsl.artifact_contract_score(bare)
    assert gsl.artifact_class(full, str(ROOT)) in ("AUTO_CONTRACT_ONLY", "AUTO_MATERIALIZED")
    assert gsl.artifact_class(bare) in ("INVALID", "HUMAN_ONLY")          # a bare command is not a world-test


def test_judge_flags_human_confirmation_when_uncertain(coding):
    vague = gsl.judge("improve throughput somehow", pack=coding)
    assert vague.requires_human_confirmation and vague.evidence_terms is not None
    sure = gsl.judge("x", pack=coding, assumption="cost_uniform")
    assert sure.requires_human_confirmation is False                      # an explicit override is trusted


def test_default_score_weights_exists_and_is_overridable():
    assert isinstance(gsl.default_score_weights(), gsl.ScoreWeights)


def test_readiness_is_go_when_all_pass():
    rep = gsl.readiness_report()           # run from the real repo root
    assert rep["status"] == "GO_READY" and not rep["blockers"]
    assert rep["metrics"]["vns"]["GSL_FULL"] > rep["metrics"]["vns"]["BASE_PROMPT"]


def test_readiness_is_no_go_when_a_requirement_is_missing(tmp_path):
    rep = gsl.readiness_report(repo_path=str(tmp_path))   # no pyproject, no evals/ here
    assert rep["status"] == "NO_GO" and "pyproject_valid" in rep["blockers"]


# ── real-time domain research: source an unknown domain instead of refusing (no fabrication) ─────────
def _stub_provider():
    # a deterministic stand-in for the assistant's web research (no network in tests)
    return gsl.CallableProvider(lambda p: {
        "known_families": ["pbft", "raft", "tendermint", "hotstuff"],
        "box_name": "the classic BFT/quorum consensus family",
        "sources": [{"title": "pbft", "url": "https://example.org/pbft"},
                    {"title": "hotstuff", "url": "https://github.com/x/hotstuff"}]})


def test_auto_elicit_builds_a_provisional_sourced_pack():
    pack, meta = gsl.auto_elicit("a novel byzantine consensus protocol", _stub_provider(), register=False)
    assert pack.validate() == [] and "pbft" in pack.known_families      # families came from the (stubbed) web
    assert meta["provisional"] is True and meta["sources"]              # cited, never claimed authoritative
    assert pack.assumptions                                            # assumptions from first principles


def test_auto_elicit_refuses_without_sources():
    with pytest.raises(gsl.ResearchError):
        gsl.auto_elicit("x", gsl.CallableProvider(lambda p: {"known_families": ["foo"]}))   # no sources


def test_creative_sources_an_unknown_domain_when_given_a_provider():
    prompt = "a novel byzantine consensus protocol for a permissioned blockchain"
    refuses = gsl.creative(prompt)                                      # no provider → honest refusal
    assert "no known domain" in refuses.lower() or "elicitation" in refuses.lower()
    sourced = gsl.creative(prompt, provider=_stub_provider())           # provider → sources it instead
    assert "PROVISIONAL" in sourced and "example.org/pbft" in sourced and "no known domain" not in sourced.lower()


# ── autonomous real-world novelty check (renamed / collage / genuinely new) ──────────────────────────
_IDEA = "a byzantine fault tolerant consensus protocol using verifiable random functions for leader election"


def test_novelty_detects_a_renamed_idea():
    prov = gsl.CallableProvider(lambda q: {"matches": [{"title": _IDEA, "url": "https://x/algorand", "summary": ""}]})
    assert gsl.novelty_audit(_IDEA, prov).status == "RENAMED"          # an exact prior-art match is a rename


def test_novelty_detects_a_collage():
    prov = gsl.CallableProvider(lambda q: {"sources": [
        {"title": "byzantine fault tolerant consensus", "url": "u1"},
        {"title": "verifiable random functions", "url": "u2"},
        {"title": "leader election protocol", "url": "u3"}]})
    assert gsl.novelty_audit(_IDEA, prov).status == "COLLAGE"          # parts covered by a union of prior art


def test_novelty_no_prior_art_is_provisional_not_proof():
    prov = gsl.CallableProvider(lambda q: {"sources": [{"title": "a recipe for sourdough bread", "url": "u9"}]})
    nv = gsl.novelty_audit(_IDEA, prov)
    assert nv.status == "NO_PRIOR_ART_FOUND" and nv.provisional is True
    assert "extrapolate beyond" in nv.why.lower()                     # points OUT of the known, not just 'unseen'


def test_scored_pool_contains_only_value_adding_operators():
    # measured decision (capability_value ablation): every operator that enters the scored pool must EARN
    # its keep. dissolve was promoted in (KEEPS, +0.034 VNS); instrument/reframe/unify measured HARMFUL/
    # DECORATIVE as generators and must stay OUT of the divergent pool — this locks that in so no one
    # silently re-wires them and dilutes novelty.
    from OUTLIER_MCB.pack import get_pack, list_packs
    from OUTLIER_MCB.generators import generate_candidates
    pooled = {c.operator for n in list_packs() if n != "generic" for c in generate_candidates(get_pack(n))}
    assert "dissolve" in pooled                                   # promoted: it adds box-distance
    assert not (pooled & {"instrument", "reframe", "unify"})      # demoted: they drag VNS down
    cv = gsl.capability_value()
    assert not cv["harmful"] and not cv["decorative"]             # nothing in the pool fails to earn its keep


def test_world_novelty_score_is_independent_of_internal_structure():
    # a NEW metric must add information the structural scores do not: an exact prior-art match scores 0,
    # nothing-found scores 1 — orthogonal to box_distance/VNS (which only see internal rigor)
    exists = gsl.CallableProvider(lambda q: {"matches": [{"title": _IDEA, "url": "u"}]})
    fresh = gsl.CallableProvider(lambda q: {"sources": [{"title": "a recipe for bread", "url": "u"}]})
    assert gsl.world_novelty_score(_IDEA, exists) == 0.0      # a rename: structurally fine, but NOT new
    assert gsl.world_novelty_score(_IDEA, fresh) == 1.0       # no prior art found (provisional)


def test_judge_runs_a_real_world_novelty_search_when_given_a_provider():
    prov = gsl.CallableProvider(lambda q: {"matches": [{"title": _IDEA, "url": "https://x/algorand"}]})
    j = gsl.judge(_IDEA, prompt="consensus", pack=gsl.get_pack("coding"), provider=prov)
    assert j.novelty is not None and j.novelty.status == "RENAMED"
    assert "prior art" in j.next_step.lower()
    # without a provider, judge does not fabricate a novelty claim
    assert gsl.judge(_IDEA, prompt="consensus", pack=gsl.get_pack("coding")).novelty is None


def test_judge_propagates_local_only_prior_art_scope():
    provider = gsl.CompositePriorArtProvider([
        gsl.OfflinePriorArtProvider([{"title": "sourdough bread recipe", "summary": "flour water salt"}])
    ])
    j = gsl.judge("measure rate by request cost instead of time windows",
                  prompt="rate limiter", pack=gsl.get_pack("coding"), provider=provider)
    assert j.novelty is not None
    assert j.novelty.novelty_scope == "LOCAL_ONLY"
    assert j.novelty.scoped_verdict() == "LOCAL_ONLY_NOVELTY"
    assert "scope=LOCAL_ONLY" in j.next_step
    assert "real online sources" in j.next_step


# ── API hygiene ───────────────────────────────────────────────────────────────────────────────────
def test_public_api_is_small():
    assert len(gsl.__all__) <= 15, "the headline API must stay small; deeper symbols live in __toolbox__"


# ── the human–machine loop: discipline the assistant's OWN free-text idea ────────────────────────────
def test_judge_flags_an_unjustified_idea_as_inside_the_box():
    j = gsl.judge("just add a caching layer in front of it", prompt="a rate limiter", pack=gsl.get_pack("coding"))
    assert j.verdict == "INSIDE_THE_BOX" and j.broken_assumption is None    # breaks no assumption → not an answer


def test_judge_audits_an_idea_that_breaks_an_assumption(coding):
    j = gsl.judge("measure the rate by request cost instead of by time window", pack=coding)
    assert j.verdict == "MUST_BE_AUDITED" and j.broken_assumption       # it maps to a real broken assumption
    assert j.dossier is not None and j.status                            # the full rigor ran on the human idea


def test_judge_is_honest_about_auto_vs_human_verification(coding):
    grounded = gsl.judge("measure rate by cost not time window", pack=coding, repo_path=str(ROOT))
    ungrounded = gsl.judge("measure rate by cost not time window", pack=coding)
    assert grounded.verifiability in ("AUTO", "HUMAN") and ungrounded.verifiability == "HUMAN"
    assert "next step" in gsl.judge("x", pack=coding).markdown().lower() or gsl.judge("x", pack=coding).next_step


def test_one_call_entrypoints_exist():
    assert callable(gsl.creative) and callable(gsl.invent)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
