"""test_honesty_fixes — the Tier-0 honesty bugs found by the self-audit.

Each test encodes a way the engine could emit a FALSE 'verified / settled / novel / grounded' result — the
exact failure class the library's own thesis forbids. They are red on the buggy code and green after the fix.
Deterministic and offline.
"""
from types import SimpleNamespace

import OUTLIER_MCB as gsl
from OUTLIER_MCB.prior_art import OnlinePriorArtProvider, PriorArtResult
from OUTLIER_MCB.repo_world import _grounded_check


# ── #5: a discovery must NOT be accepted when controls were never run (missing key ≠ controls passed) ──
def test_discovery_rejects_when_controls_absent():
    pack = gsl.get_pack("numeric")

    def high_score_no_controls(_cand):
        return {"score": 0.99}   # scores high but NEVER emits controls_collapse

    disc = gsl.discover("law without controls", high_score_no_controls, pack,
                        rounds=1, base_budget=8, require_controls=True)
    assert disc.laws == [], "a law with no controls run must not be accepted under require_controls"


def test_discovery_still_accepts_when_controls_collapse_true():
    pack = gsl.get_pack("numeric")

    def high_score_with_controls(_cand):
        return {"score": 0.99, "controls_collapse": True}

    disc = gsl.discover("law with controls", high_score_with_controls, pack,
                        rounds=1, base_budget=8, require_controls=True)
    assert disc.laws, "a law whose controls collapse must still be accepted"


# ── #7: an online provider that returns NOTHING with no scope must not be laundered into 'checked' ─────
class _EmptyOnline(OnlinePriorArtProvider):
    """An online provider whose search comes back empty (indistinguishable from a silent failure)."""
    def __init__(self):
        super().__init__()
        self.name = "empty-online"

    def _fetch(self, query):
        return []


class _NonEmptyOnline(OnlinePriorArtProvider):
    def __init__(self):
        super().__init__()
        self.name = "hit-online"

    def _fetch(self, query):
        return [PriorArtResult(title="a hit", url="http://x")]


def test_empty_online_search_is_not_certified_as_checked():
    cached = gsl.CachedPriorArtProvider(_EmptyOnline(), ttl_seconds=100, clock=lambda: 0.0)
    out = cached.research("q")
    assert out["novelty_scope"] == "INCOMPLETE_ONLINE_SEARCH", \
        "an empty online return with no reported scope cannot be certified as a completed search"


def test_nonempty_online_search_is_still_checked():
    cached = gsl.CachedPriorArtProvider(_NonEmptyOnline(), ttl_seconds=100, clock=lambda: 0.0)
    out = cached.research("q")
    assert out["novelty_scope"] == "ONLINE_PRIOR_ART_CHECKED"


# ── #8: the world-test target must be tied to the IDEA, not a single arbitrary existing test file ──────
# ── #12: a tiny absolute amplification over near-dead parts is not synergy ─────────────────────────────
def test_dead_collage_is_not_credited_as_synergy():
    assert gsl.synergy_score(0.10, [0.05, 0.05]) == 0.0        # tiny absolute gain → no synergy
    assert gsl.synergy_score(1.0, [0.4, 0.5]) == 0.5          # a real amplification is still credited


# ── #14: the first in-loop bet is left OPEN, not auto-won by comparing a score to itself ───────────────
def test_first_creative_bet_is_not_auto_won():
    from OUTLIER_MCB.economy import Ledger
    from OUTLIER_MCB.creative_search import creative_search
    pack = gsl.get_pack("coding")
    ledger = Ledger()
    creative_search("improve throughput", pack=pack, ledger=ledger, budget=4)
    stats = ledger.summary()
    assert stats["open"] >= 1, "the first bet (no prior baseline) must stay OPEN, not be an automatic win"


# ── #10: the invent frontier head is diversity-aware, not N clones of the farthest assumption ─────────
def test_invent_frontier_is_diversified():
    from OUTLIER_MCB.invent import _diversify
    def item(name, asms, score):
        return {"candidate": SimpleNamespace(assumptions=asms, name=name), "score": {"composite": score}}
    # four top items all break assumption A (the degenerate case), one breaks B lower-scored.
    frontier = [item("a1", ["A"], 0.9), item("a2", ["A"], 0.88), item("a3", ["A"], 0.86),
                item("b1", ["B"], 0.80), item("a4", ["A"], 0.84)]
    out = _diversify(frontier)
    assert out[0]["candidate"].name == "a1"                 # best score still leads
    assert out[1]["candidate"].name == "b1"                 # the distinct axis is surfaced next, not a4
    assert {f["candidate"].name for f in out} == {"a1", "a2", "a3", "a4", "b1"}   # nothing dropped


# ── #15: the four common entry points accept simple inputs instead of crashing ────────────────────────
def test_ergonomic_entry_points_accept_simple_inputs():
    import pytest
    assert 0.0 <= gsl.library_health(".") <= 1.0                               # a stray path → default set
    assert gsl.detect_missing_information("invent a better cache") is not None  # pack optional
    assert gsl.find_high_leverage_questions("invent a better cache") is not None
    assert gsl.self_diagnose(None) is not None                                  # nothing recorded → empty report
    with pytest.raises(TypeError):
        gsl.self_diagnose(".")                                                  # wrong type → CLEAR error


def _repo(test_files):
    return SimpleNamespace(test_command="pytest -q", type_command="mypy .", build_command="",
                           test_files=test_files, source_files=["src/mod.py"],
                           components=["mod"], symbols=["fn"])


# ── #1/#2: a name-dropped 'inter-instance' phrase over a PER-INSTANCE aggregation is not a closure escape ──
def test_per_instance_aggregation_stays_inside_deepsets():
    # mean-pooling per-instance features is ρ(Σφ) — INSIDE DeepSets — even if it mentions interaction.
    text = "mean-pool the per-instance features (a soft inter-instance note)"
    assert gsl.reduces_to_closure(text, "DEEPSETS") == "INSIDE"


def test_genuine_bag_conditioning_still_escapes_deepsets():
    # a real set-conditioned encoder (no per-instance encoding) is still OUTSIDE DeepSets.
    text = "phi is a self-attention encoder over the bag; instances attend to each other, then sum"
    assert gsl.reduces_to_closure(text, "DEEPSETS") == "OUTSIDE"


def test_incidental_context_word_does_not_trip_set_transformer():
    # the bare word 'context' must not classify an innocuous plain mean as a Set-Transformer membership.
    text = "in this context, R = mean(e) over the bag"
    assert gsl.reduces_to_closure(text, "SET_TRANSFORMER") in ("UNKNOWN", "OUTSIDE")


def test_grounded_check_target_is_idea_specific():
    repo = _repo(["tests/test_cvc5_backend.py", "tests/test_other.py"])
    a = _grounded_check("test_flip", repo, claim="pooling breaks permutation", axis="representation")
    b = _grounded_check("test_flip", repo, claim="objective becomes curiosity", axis="objective")
    # two different ideas must NOT be pinned to the same arbitrary existing file
    assert a.target != b.target, "different ideas must target different (idea-named) test files"
    # the target must not silently be the first pre-existing test file
    assert a.target != "tests/test_cvc5_backend.py"
    # the target should carry the claim/axis identity (the new red-first test file)
    assert a.test_name in a.target
