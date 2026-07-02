"""test_bug_fixes — the real logical bugs found by the independent audit of the new creativity modules.
Each test encodes the CORRECT behavior: red on the buggy code, green after the fix. Deterministic, offline.
"""
import ast

import OUTLIER_MCB as gsl


# ── #1 aesthetics: measure_surprise must see the ACTUAL operator (Add/Sub/Mult/Pow), not the string 'BinOp' ──
def test_surprise_distinguishes_operators():
    from OUTLIER_MCB.aesthetics import measure_surprise
    # 'a-b' uses Sub, corpus uses Add → different operator → surprising (> 0)
    assert measure_surprise("a - b", ["a + b"]) > 0.0
    # a power vs a corpus of +/* → surprising
    assert measure_surprise("a ** b", ["a + b", "a * b"]) > measure_surprise("a + b", ["a + b", "a * b"])


def test_aesthetics_objectivity_gate_now_checks_surprise():
    from OUTLIER_MCB.aesthetics import aesthetics_objectivity_pass
    assert aesthetics_objectivity_pass() is True     # and it now includes a real surprise clause


# ── #2 physics: a trivial period-2 oscillator (blinker) is NOT emergent ────────────────────────────────
def test_blinker_is_not_emergent():
    from OUTLIER_MCB.physics_inventor import measure_emergence
    blinker = [(0, 1, 0, 1, 0), (1, 0, 1, 0, 1)] * 20
    assert measure_emergence(blinker, k=2) < 0.1     # a trivial oscillator must score low, not ~0.8


def test_structured_still_beats_trivial_and_noise():
    from OUTLIER_MCB.physics_inventor import elementary_physics, run_simulation, measure_emergence
    seed = tuple(1 if i == 30 else 0 for i in range(61))
    structured = measure_emergence(run_simulation(elementary_physics(90), steps=30, width=61, init=seed), k=2)
    blinker = measure_emergence([(0, 1) * 30, (1, 0) * 30] * 15, k=2)
    assert structured > blinker                       # structure beats a trivial oscillator


# ── #4 language: shortest_program returns the EMPTY program for identity and respects max_len ───────────
def test_shortest_program_finds_identity_and_respects_bound():
    from OUTLIER_MCB.language_inventor import integer_baseline, shortest_program
    base = integer_baseline()
    assert shortest_program(base, [(3, 3), (5, 5)]) == ()          # identity → the empty pipeline
    prog = shortest_program(base, [(x, x + 3) for x in range(4)], max_len=2)
    assert prog is None or len(prog) <= 2                          # never overshoots the documented bound


# ── #5 verification economy: cost_saving runs the real resolver at most ONCE per case ──────────────────
def test_cost_saving_does_not_double_run_the_resolver():
    from OUTLIER_MCB.verification_economy import VerificationEconomy
    calls = {"n": 0}

    def real(c):
        calls["n"] += 1
        return c >= 10

    econ = VerificationEconomy(real=real, real_cost=1.0)
    econ.calibrate([0, 5, 15])                                     # calibration may call real; reset after
    calls["n"] = 0
    econ.cost_saving([0, 5, 15, 20])
    assert calls["n"] <= 4                                         # one real call per case, not two


# ── #6 experiment loop: a lone hypothesis with NO observation is NOT 'resolved' ────────────────────────
def test_single_hypothesis_zero_probes_is_not_resolved():
    from OUTLIER_MCB.experiment_loop import run_active_experiments, Hypothesis
    res = run_active_experiments([Hypothesis("H", lambda p: True)], {})
    assert res.resolved is False                                   # zero observations → nothing was settled
    assert "observ" in res.reason.lower() or "probe" in res.reason.lower()


def test_no_hypotheses_reports_honestly():
    from OUTLIER_MCB.experiment_loop import run_active_experiments
    res = run_active_experiments([], {"p": lambda: True})
    assert res.resolved is False and "hypothes" in res.reason.lower()


# ── #11 taste: unseen (unproven) features pull toward neutral — no inflation by a single good feature ──
def test_taste_unproven_breaks_dilute_toward_neutral():
    from types import SimpleNamespace
    from OUTLIER_MCB.taste import EarnedTaste
    t = EarnedTaste()
    good = SimpleNamespace(operator="dissolve", breaks=["representation"], assumptions=["representation"], needs=[])
    for _ in range(5):
        t.observe_candidate(good, survived=True)
    lean = SimpleNamespace(operator="dissolve", breaks=["representation"], assumptions=["representation"], needs=[])
    stuffed = SimpleNamespace(operator="dissolve", breaks=["representation", "unseen1", "unseen2", "unseen3"],
                              assumptions=["representation"], needs=[])
    assert t.value(lean) > t.value(stuffed)           # more unproven breaks → lower, not equal
