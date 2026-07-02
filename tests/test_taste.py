"""test_taste — the EARNED taste model (Tier-2 T2.1) and its wiring into invent(), plus the Tier-1 wiring of
mine_mechanism_abstractions into evolve. Deterministic and offline.

Taste is a LEARNED, calibrated value over UNVERIFIED ideas, trained ONLY on externally-settled outcomes. The
tests prove: it separates winning-shaped ideas from losing ones, it is neutral (0.5) when untrained (safe cold
start), it can be audited (Brier/separation), and it re-ranks without ever fabricating a certificate.
"""
from types import SimpleNamespace

import OUTLIER_MCB as gsl
from OUTLIER_MCB.taste import EarnedTaste, earned_taste_from_ledger, taste_rerank


def _cand(operator, breaks, needs=()):
    return SimpleNamespace(operator=operator, breaks=list(breaks), assumptions=list(breaks), needs=list(needs))


# ── learns which SHAPES survive, neutral when it hasn't ───────────────────────────────────────────────
def test_taste_learns_survival_shape():
    t = EarnedTaste()
    winner, loser = _cand("dissolve", ["representation"]), _cand("recombine", ["cost"])
    for _ in range(5):
        t.observe_candidate(winner, survived=True)
        t.observe_candidate(loser, survived=False)
    assert t.value(winner) > 0.7 > t.value(loser)                 # history separates the two shapes
    unseen = _cand("transport", ["measure"])
    assert t.value(unseen) == 0.5                                 # never-seen shape → neutral, never distorts


def test_cold_taste_is_neutral_and_uninformative():
    t = EarnedTaste()
    assert t.value(_cand("invert", ["objective"])) == 0.5
    assert t.is_informative() is False                            # nothing learned yet → do not consult


# ── it is auditable, not merely trusted ───────────────────────────────────────────────────────────────
def test_taste_calibration_reports_separation():
    t = EarnedTaste()
    good, bad = _cand("dissolve", ["representation"]), _cand("recombine", ["cost"])
    for _ in range(6):
        t.observe_candidate(good, survived=True)
        t.observe_candidate(bad, survived=False)
    cal = t.calibration([(good, True), (bad, False)])
    assert cal["separation"] > 0.0 and 0.0 <= cal["brier"] <= 1.0


# ── learns from a Ledger's SETTLED bets (external labels only) ─────────────────────────────────────────
def test_earned_taste_from_ledger():
    from OUTLIER_MCB.economy import Ledger, Bet
    led = Ledger()
    for _ in range(3):
        led.settle(led.post(Bet(claim="a", world_test="w", resolver="repo", axis="representation",
                                 operator="dissolve")), won=True)
        led.settle(led.post(Bet(claim="b", world_test="w", resolver="repo", axis="cost",
                                 operator="recombine")), won=False)
    led.post(Bet(claim="open", world_test="w", resolver="repo", axis="x", operator="negate"))  # OPEN → ignored
    t = earned_taste_from_ledger(led)
    assert t.is_informative()
    assert t.feature_value("axis:representation") > t.feature_value("axis:cost")


def test_taste_rerank_promotes_winning_shape():
    t = EarnedTaste()
    win, lose = _cand("dissolve", ["representation"]), _cand("recombine", ["cost"])
    for _ in range(5):
        t.observe_candidate(win, survived=True)
        t.observe_candidate(lose, survived=False)
    # the LOSER-shaped idea has a slightly higher raw composite, but taste should lift the winner-shaped one.
    frontier = [{"candidate": lose, "score": {"composite": 0.60}},
                {"candidate": win, "score": {"composite": 0.55}}]
    out = taste_rerank(frontier, t, weight=0.5)
    assert out[0]["candidate"] is win
    assert "taste" in out[0]["score"] and "taste_blended" in out[0]["score"]


# ── invent(taste=...) integration: opt-in, safe, no fabricated certificate ────────────────────────────
def test_invent_accepts_taste_without_regression():
    inv_plain = gsl.invent("invent a better rate limiter", beam=4, rounds=1)
    inv_taste = gsl.invent("invent a better rate limiter", beam=4, rounds=1, taste=True)
    assert inv_plain.frontier and inv_taste.frontier             # both produce a portfolio
    # a cold taste (no settled bets) must not change the honest note or fabricate anything
    assert "NOT claimed verified" in inv_taste.note


# ── Tier-1: mine_mechanism_abstractions is now wired into evolve's mine_concepts path ─────────────────
def test_evolve_mines_mechanisms_when_concepts_on():
    pack = gsl.get_pack("numeric")
    ev = gsl.CallableEvaluator(lambda c: {"score": 0.8, "controls_collapse": True}, passed_key="controls_collapse")
    res = gsl.evolve_invention("discover a law", ev, budget=10, pack=pack, mine_concepts=True)
    assert res.concept_library is not None
    assert res.mechanism_library is not None                     # the orphan capability now runs in the flow


# ── Tier-1/gap-#4: invent() can GROW its conceptual space when asked (transformational creativity) ─────
def test_invent_expand_when_stuck_grows_a_new_axis():
    base = gsl.invent("invent a better rate limiter", beam=4, rounds=1)
    grown = gsl.invent("invent a better rate limiter", beam=4, rounds=1, expand_when_stuck=True)
    assert grown.frontier                                          # still produces a portfolio
    assert "Transformational" in grown.note                       # a genuinely new axis was invented + explored
    # honesty is preserved: no fabricated verification claim sneaks in with the expansion
    assert "NOT claimed verified" in grown.note and "NOT claimed verified" in base.note
