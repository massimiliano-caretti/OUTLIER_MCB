"""test_experiment_loop — the EXECUTABLE active-experiment loop (Tier-2, T2.2): the engine ACQUIRES new
information (runs probes) to shrink a hypothesis space, eliminating hypotheses only by the WORLD's real
outcome — never by self-judgment. Deterministic and offline.

Scenario: a hidden number in {0,1,2,3}. Four hypotheses each claim a specific value. Two probes reveal bits.
The loop must pick the most discriminating probe, observe the world, and converge on the true hypothesis.
"""
import OUTLIER_MCB as gsl
from OUTLIER_MCB.experiment_loop import Hypothesis, run_active_experiments


def _hyps():
    # each hypothesis predicts what the probes would show IF the number were its claimed value
    def predictor(n):
        return lambda probe: (bool(n & 1) if probe == "bit0" else
                              bool(n >= 2) if probe == "bit1" else True)   # 'noise' probe: everyone predicts True
    return [Hypothesis(name=f"hyp_{n}", predict=predictor(n)) for n in range(4)]


def _world(true_n):
    return {"bit0": (lambda: bool(true_n & 1)),
            "bit1": (lambda: bool(true_n >= 2)),
            "noise": (lambda: True)}                 # a non-discriminating probe (EIG 0) — must never be chosen


# ── it acquires information until ONE hypothesis survives ──────────────────────────────────────────────
def test_loop_converges_on_the_true_hypothesis():
    res = run_active_experiments(_hyps(), _world(true_n=2))
    assert res.resolved is True
    assert res.surviving == ["hyp_2"]                 # the world settled it — the correct value
    # the two informative bits are chosen FIRST (EIG 1.0), before the non-discriminating noise probe.
    assert res.steps[0].eig == 1.0 and res.steps[1].eig == 1.0
    assert {res.steps[0].experiment, res.steps[1].experiment} == {"bit0", "bit1"}


def test_discriminating_probes_are_chosen_before_the_noise_probe():
    res = run_active_experiments(_hyps(), _world(true_n=1))
    assert res.resolved and res.surviving == ["hyp_1"]
    # noise (EIG 0) is never chosen while a discriminating bit remains — it only appears (if at all) last.
    assert res.steps[0].experiment in ("bit0", "bit1") and res.steps[0].eig == 1.0


# ── honest end condition: ambiguity that no available probe can resolve asks for a NEW observable ─────
def test_loop_reports_need_for_new_observable_when_stuck():
    # two hypotheses that agree on every available probe cannot be told apart — the honest outcome is to
    # say so (acquire a NEW observable), not to pick one.
    twins = [Hypothesis(name="A", predict=lambda p: True),
             Hypothesis(name="B", predict=lambda p: True)]      # identical predictions
    res = run_active_experiments(twins, {"only": (lambda: True)})
    assert res.resolved is False
    assert len(res.surviving) == 2 and "observable" in res.reason.lower() or "discriminate" in res.reason.lower()


# ── elimination is by the WORLD, never self-judgment: a wrong model dies honestly ─────────────────────
def test_all_hypotheses_can_be_wrong():
    # the world's true number is 3, but we only offer hypotheses for 0 and 1 → both get contradicted.
    hyps = [h for h in _hyps() if h.name in ("hyp_0", "hyp_1")]
    res = run_active_experiments(hyps, _world(true_n=3))
    assert res.resolved is False and res.surviving == []
    assert "wrong" in res.reason.lower() or "contradict" in res.reason.lower()
