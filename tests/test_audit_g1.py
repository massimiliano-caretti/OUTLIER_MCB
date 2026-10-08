"""Regression tests for audit G1 (kernel / pack / activation / guard / judge / closures / barriers / ci /
handoff / research / preflight / cli). Each test pins one CONFIRMED defect so it cannot silently return."""
import copy

import pytest

import OUTLIER_MCB as gsl
from OUTLIER_MCB import kernel
from OUTLIER_MCB.activation import should_activate
from OUTLIER_MCB.pack import REGISTRY, get_pack, pack_scores, select_pack, keyword_hit
from OUTLIER_MCB.barriers import barrier_membership, DEAD_BY_BARRIER, NOT_BLOCKED


# ── activation: word-anchored triggers, EN + IT inflections ─────────────────────────────────────────
@pytest.mark.parametrize("prompt", [
    "I knew it", "renewal of the license", "read the news", "the better half of the file",
    "fix bug in newton solver", "originally it returned None", "fix this off-by-one bug"])
def test_activation_does_not_fire_on_substrings(prompt):
    assert should_activate(prompt) is False


@pytest.mark.parametrize("prompt", [
    "invent a new rate limiter", "make it new", "nuova idea per la cache", "nuovi approcci al caching",
    "inventare un algoritmo", "è stato inventato ieri?", "un'invenzione", "scoprire un metodo", "una scoperta",
    "migliorare l'uso della libreria", "il modo migliore", "ripensare da zero", "find a better way to cache",
    "reinvent caching", "think outside the box", "improve the library"])
def test_activation_fires_on_real_triggers(prompt):
    assert should_activate(prompt) is True


# ── pack routing: word-anchored keywords + Italian keywords ─────────────────────────────────────────
def test_keyword_hit_is_word_anchored_but_inflection_tolerant():
    assert keyword_hit("primi", "numeri primi gemelli") and keyword_hit("gap", "prime gaps")
    assert keyword_hit("load balanc", "a load balancer") and keyword_hit("self-improve", "self-improvement")
    assert not keyword_hit("primi", "comprimi i file") and not keyword_hit("primi", "concurrency primitives")
    assert not keyword_hit("gap", "singapore office") and not keyword_hit("twin", "twinkle star")
    assert not keyword_hit("proof", "a waterproof case")


@pytest.mark.parametrize("prompt", ["comprimi i file e esprimi il risultato", "singapore office", "twinkle star"])
def test_substring_false_positives_no_longer_route(prompt):
    assert select_pack(prompt)[0].name == "generic"


@pytest.mark.parametrize("prompt,expected", [
    ("inventa un nuovo algoritmo di ottimizzazione con convergenza garantita", "math"),
    ("inventa una nuova inferenza causale con confondenti nascosti", "causal"),
    ("inventa un limitatore distribuito con bassa latenza", "coding"),
    ("scopri una legge empirica con la regressione simbolica", "numeric")])
def test_italian_prompts_route_to_their_pack(prompt, expected):
    assert select_pack(prompt)[0].name == expected


def test_guard_domain_confidence_matches_router():
    coding = get_pack("coding")
    assert gsl.domain_confidence("a scheduler for a queue", coding) == dict(pack_scores("a scheduler for a queue"))["coding"]


# ── kernel: ceiling words, stale graph cache, failure count, note-less relations ──────────────────────
def test_ceiling_detects_end_of_string_and_italian():
    p = get_pack("coding")
    g = kernel.graph_of(p)
    assert kernel._missing_info("make it new", p, g, None)["data_insufficient"] is True
    assert kernel._missing_info("voglio un approccio nuovo", p, g, None)["data_insufficient"] is True
    assert kernel._missing_info("renew the token", p, g, None)["data_insufficient"] is False


def test_graph_cache_invalidates_on_in_place_relation_edit():
    p = copy.deepcopy(get_pack("coding"))
    g1 = kernel.graph_of(p)
    r = list(p.relations[0]); r[2] = "CHANGED_TOKEN"; p.relations[0] = tuple(r)
    g2 = kernel.graph_of(p)
    assert g2 is not g1 and g2.edges[0][2] == "CHANGED_TOKEN"


def test_failure_count_matches_whole_identifier_only():
    p = copy.deepcopy(get_pack("coding"))
    name = p.assumptions[0].name
    p.failure_memory = {"x": {"status": "DEAD", "assumption": "per_request_" + name}}
    assert kernel._failure_count(p, name) == 0
    p.failure_memory = {"x": {"status": "DEAD", "assumption": name}}
    assert kernel._failure_count(p, name) == 1


def test_three_field_relations_do_not_crash_creative():
    spec = {"name": "g1_three_field", "keywords": ["zzzq"],
            "assumptions": [{"name": "a1", "description": "d", "if_false": "f", "falsifier": "x y z w", "axis": "A"},
                            {"name": "a2", "description": "d", "if_false": "f", "axis": "A"}],
            "axes": {"A": {"priority": 3, "verdict": "v"}}, "relations": [["a1", "implies", "a2"]],
            "known_families": ["fam"]}
    p = gsl.pack_from_spec(spec)
    assert "break" in gsl.creative("invent zzzq", pack=p)
    assert kernel.graph_of(p).edges == [("a1", "implies", "a2", "")]


# ── closures: closure names are case-insensitive ─────────────────────────────────────────────────────
def test_lowercase_declared_closure_does_not_keyerror():
    p = copy.deepcopy(get_pack("coding"))
    p.universal_closures = ["deepsets"]
    assert gsl.closure_membership("a mean pooling readout", p)["verdict"] == "INSIDE_THE_BOX"
    assert gsl.architectural_novelty("a mean pooling readout", p)["state"] == "INSIDE_THE_BOX"


# ── barriers: no fabricated escapes, no false kills ─────────────────────────────────────────────────
@pytest.mark.parametrize("idea", ["a perpetual motion machine driven by magnets",
                                  "a self-powered perpetual motion wheel with a pump",
                                  "a data-driven perpetual motion generator"])
def test_thermo_barrier_not_escaped_by_incidental_words(idea):
    assert barrier_membership(idea, get_pack("physics")).status == DEAD_BY_BARRIER


def test_thermo_barrier_does_not_kill_free_energy_potentials():
    v = barrier_membership("compute the Helmholtz free energy of a lattice model", get_pack("physics"))
    assert v is None or v.status != DEAD_BY_BARRIER


def test_parity_barrier_bare_limitato_is_not_an_escape():
    nt = get_pack("number_theory")
    assert barrier_membership("un crivello limitato ai primi gemelli", nt).status == DEAD_BY_BARRIER
    assert barrier_membership("a sieve for bounded gaps between twin primes", nt).status == NOT_BLOCKED


# ── ci / handoff: a DEAD_BY_BARRIER idea must never pass ─────────────────────────────────────────────
_PERPETUAL = "a perpetual motion machine that breaks the closed-system assumption by creating energy from nothing"


def test_ci_fails_dead_by_barrier():
    with pytest.raises(gsl.NoveltyRegression):
        gsl.assert_outside_the_box(_PERPETUAL, pack=get_pack("physics"))


def test_handoff_rejects_dead_by_barrier():
    ph = get_pack("physics")
    c = gsl.handoff_contract("invent a new perpetual motion engine", creative=True, pack=ph)
    out = {"idea": _PERPETUAL, "broken_assumption": "closed-system assumption: energy is conserved",
           "world_test": "it would fail if measured output never exceeds input against a baseline",
           "claim": "a candidate design to test"}
    r = gsl.accept_handoff(out, c, pack=ph)
    assert r["accepted"] is False and r["receipt"] is None
    assert any("DEAD_BY_BARRIER" in x for x in r["reasons"])


def test_italian_world_test_is_recognised():
    from OUTLIER_MCB.handoff import validate_world_test
    assert validate_world_test("l'idea fallisce se non supera il limitatore classico sullo stesso carico")


# ── judge: None idea, unknown assumption override ───────────────────────────────────────────────────
def test_judge_none_idea_does_not_crash():
    assert gsl.judge(None).verdict == "INSIDE_THE_BOX"


def test_judge_unknown_assumption_raises_and_case_is_resolved():
    coding = get_pack("coding")
    name = coding.assumptions[0].name
    with pytest.raises(gsl.AssumptionNotFoundError):
        gsl.judge("anything", pack=coding, assumption=name + "_typo")
    assert gsl.judge("anything", pack=coding, assumption=name.upper()).broken_assumption == name


# ── research / creative: a sourced pack must not hijack later routing ────────────────────────────────
def test_sourced_pack_is_not_registered_and_has_no_request_keywords():
    from OUTLIER_MCB.research import _keywords
    assert not {"invent", "novel", "better", "nuovo", "inventa"} & set(_keywords("invent a novel better nuovo inventa bread"))
    before = set(REGISTRY)
    prov = gsl.CallableProvider(lambda p: {"known_families": ["sourdough"],
                                           "sources": [{"title": "t", "url": "https://example.org/x"}]})
    gsl.creative("invent a novel bread baking method", provider=prov)
    assert set(REGISTRY) == before
    assert select_pack("invent a novel way to cool a laptop")[0].name == "generic"


# ── cli: a long inline --problem is text, not a crash ───────────────────────────────────────────────
def test_cli_read_accepts_long_inline_prompt():
    from OUTLIER_MCB.cli import _read
    long = "invent " * 80
    assert _read(long) == long
    assert _read(".") == "."            # a directory is not a problem file


# ── routing: a repo-language boost alone is not a domain match ──────────────────────────────────────
def test_repo_boost_without_keyword_evidence_is_not_confident():
    class _PyRepo:
        def primary_language(self):
            return "python"
    d = gsl.route_pack("invent a new way to bake bread", repo=_PyRepo())
    assert d.repo_language_boost is True and d.ambiguous is True
    d2 = gsl.route_pack("invent a new rate limiter for the api gateway", repo=_PyRepo())
    assert d2.selected_pack == "coding" and d2.ambiguous is False
