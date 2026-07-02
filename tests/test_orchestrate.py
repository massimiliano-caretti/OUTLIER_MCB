"""test_orchestrate — the composed scientific loop autonomous() wires EVERY new capability into one flow, so
none is dead code. The headline test drives all tracks at once and asserts each capability actually ran.
Deterministic and offline.
"""
import OUTLIER_MCB as gsl
from OUTLIER_MCB.discovery_memory import DiscoveryMemory
from OUTLIER_MCB.experiment_loop import Hypothesis


# ── a tiny settle-able domain: a 'solution' is a function; a 'case' is (x, expected) ───────────────────
def _check(sol, case):
    return sol(case[0]) == case[1]


def _correct(x):
    return 2 * x


def _wrong(x):
    return x


def _memory():
    mem = DiscoveryMemory()
    for _ in range(3):
        mem.record("energy_is_conserved_locally", axis="representation", domain="physics", confirmed=True)
    for _ in range(3):
        mem.record("agents_optimize_private_utility", axis="incentive", domain="economics", confirmed=True)
    for _ in range(3):
        mem.record("supply_matches_demand_instantly", axis="timing", domain="economics", confirmed=False)
    return mem


def _hyps():
    def predictor(n):
        return lambda probe: bool(n & 1) if probe == "bit0" else bool(n >= 2)
    return [Hypothesis(name=f"hyp_{n}", predict=predictor(n)) for n in range(4)]


def _world(true_n=2):
    return {"bit0": (lambda: bool(true_n & 1)), "bit1": (lambda: bool(true_n >= 2))}


# ── the whole loop: every track fed, every capability must run (proves nothing is dead code) ──────────
def test_autonomous_orchestrates_every_capability():
    mem = _memory()
    ctx = {"check": _check, "cases": [(1, 2), (2, 4), (3, 6), (4, 8)],
           "negative_controls": [(1, 999)]}          # a real solution must FAIL this
    res = gsl.autonomous(
        "find f such that f(x) = 2x",
        memory=mem, taste=True, idea_evaluator=lambda c: float(len(getattr(c, "breaks", []))),
        verification_context=ctx, solutions=[_correct, _wrong],
        hypotheses=_hyps(), world_probes=_world(true_n=2),
        beam=4, rounds=1, min_support=1)

    used = set(res.used_capabilities)
    for cap in ("incubation", "invent", "earned_taste", "self_refine", "synthesize_evaluator",
                "validate_evaluator", "red_team_from_check", "verification_economy",
                "active_experiments", "memory_record", "transformation"):
        assert cap in used, f"capability '{cap}' was not orchestrated (dead code): used={sorted(used)}"


# ── the SETTLE track: the economy's verdict always matches the real synthesized evaluator (no fabrication) ─
def test_settlement_track_matches_real_resolver():
    ctx = {"check": _check, "cases": [(1, 2), (2, 4), (3, 6), (4, 8)], "negative_controls": [(1, 999)]}
    res = gsl.autonomous("f(x)=2x", verification_context=ctx, solutions=[_correct, _wrong], min_support=1)
    verdicts = [s.verdict for s in res.settlements]
    assert verdicts == [True, False]                 # correct solution passes, wrong one fails — honestly
    assert any(not s.escalated for s in res.settlements)   # the precise proxy confirmed at least one cheaply


# ── each track is OPTIONAL: with only a prompt, just the idea track runs (no faking the rest) ─────────
def test_autonomous_runs_only_the_tracks_with_inputs():
    res = gsl.autonomous("invent a better cache", beam=4, rounds=1)
    used = set(res.used_capabilities)
    assert "invent" in used
    assert "synthesize_evaluator" not in used and "active_experiments" not in used   # no inputs → not faked
    assert res.settlements == [] and res.experiments is None


# ── the composed result renders an honest report ──────────────────────────────────────────────────────
def test_autonomous_markdown_is_honest():
    res = gsl.autonomous("invent a better cache", beam=4, rounds=1)
    md = res.markdown()
    assert "Autonomous creative loop" in md and "capabilities exercised" in md
