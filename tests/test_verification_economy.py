"""test_verification_economy — cheap calibrated proxies settle more at lower cost, and NEVER fabricate a pass
(Tier-2, T2.5). Deterministic and offline. The real resolver defines ground truth; a proxy may only cheaply
CONFIRM where it is precise, and everything uncertain escalates to the real resolver.
"""
import OUTLIER_MCB as gsl
from OUTLIER_MCB.verification_economy import (VerificationEconomy, calibrate_proxy, as_verdict)


# ground truth: a candidate "passes" iff its value is >= 10 (an expensive check we pretend costs 1.0)
def real(c):
    return c["v"] >= 10


def _cases():
    return [{"v": v} for v in range(0, 20)]


# ── calibration measures a proxy honestly against the real resolver ───────────────────────────────────
def test_calibration_measures_precision_and_agreement():
    good = lambda c: c["v"] >= 10          # identical to real → perfect precision
    loose = lambda c: c["v"] >= 5          # over-fires → false positives (v in [5,9] say YES but real NO)
    cg = calibrate_proxy(good, real, _cases(), cost=0.1, name="good")
    cl = calibrate_proxy(loose, real, _cases(), cost=0.1, name="loose")
    assert cg.precision == 1.0 and cg.agreement == 1.0
    assert cl.precision < 1.0 and cl.fp == 5          # v in {5,6,7,8,9}
    assert cg.trustworthy() and not cl.trustworthy()  # only the precise proxy earns trust


# ── a precise proxy cheaply CONFIRMS; the loose one is never trusted to ───────────────────────────────
def test_precise_proxy_confirms_cheaply_loose_escalates():
    econ = VerificationEconomy(real=real, real_cost=1.0)
    econ.add_proxy(lambda c: c["v"] >= 10, cost=0.1, name="tight")
    econ.add_proxy(lambda c: c["v"] >= 5, cost=0.05, name="loose")
    econ.calibrate(_cases())
    # a clearly-passing candidate is confirmed cheaply by the trusted proxy (not the cheaper untrusted one)
    o = econ.settle({"v": 15})
    assert o.verdict is True and o.settled_by == "tight" and o.escalated is False and o.cost == 0.1
    # a failing candidate: no trustworthy proxy says YES → escalate to the real resolver, which rejects it
    o2 = econ.settle({"v": 3})
    assert o2.verdict is False and o2.settled_by == "real" and o2.escalated is True


# ── the economy can NEVER fabricate a pass the real resolver would reject ──────────────────────────────
def test_economy_never_fabricates_a_pass():
    econ = VerificationEconomy(real=real, real_cost=1.0)
    econ.add_proxy(lambda c: True, cost=0.01, name="always_yes")   # a lying proxy that always says YES
    econ.calibrate(_cases())
    # 'always_yes' has many false positives → NOT trustworthy → it can never settle a pass on its own.
    for c in _cases():
        o = econ.settle(c)
        assert o.verdict == real(c), "the economy's verdict must match the real resolver, always"


# ── it actually saves cost where a proxy is trustworthy, and reports the MEASURED saving ──────────────
def test_cost_saving_is_real_and_measured():
    econ = VerificationEconomy(real=real, real_cost=1.0)
    econ.add_proxy(lambda c: c["v"] >= 10, cost=0.1, name="tight")
    econ.calibrate(_cases())
    rep = econ.cost_saving(_cases())
    assert rep["baseline_cost"] == 20.0
    assert rep["cheaply_confirmed"] == 10          # the 10 passing cases are confirmed by the cheap proxy
    assert rep["economy_cost"] < rep["baseline_cost"] and rep["saving"] > 0.0


# ── as_verdict adapts evaluators / dicts / callables uniformly ────────────────────────────────────────
def test_as_verdict_adapts_shapes():
    ev = gsl.CallableEvaluator(lambda c: {"score": 1.0, "ok": True}, passed_key="ok")
    assert as_verdict(ev, {"x": 1}) is True
    assert as_verdict(lambda c: {"passed": False}, {"x": 1}) is False
    assert as_verdict(lambda c: True, {"x": 1}) is True
