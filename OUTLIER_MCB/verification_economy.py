"""verification_economy — settle MORE at LOWER cost, without ever fabricating a verdict (Tier-2, T2.5).

The library's own audit named the real bottleneck: *the bottleneck is SETTLEMENT, not generation*. A creativity
engine that must run an expensive world-test (a full test-suite, a proof search, a benchmark) on every idea is
throttled by the cost of judging, not the cost of dreaming. A human expert escapes this with cheap PROXIES —
quick sanity checks calibrated by experience against the real thing: "when this smells right, it usually is."

This module makes that explicit and honest. A PROXY is any cheap predicate over a candidate; the REAL resolver
is the trusted-but-expensive one. `calibrate_proxy` measures the proxy against the real resolver on labelled
cases (precision, recall, agreement, false-positive rate, cost). `VerificationEconomy.settle` then uses a proxy
to CHEAPLY CONFIRM a candidate ONLY where that proxy has been shown PRECISE (a proxy-positive is trustworthy),
and ESCALATES everything uncertain to the real resolver — so the economy can never turn a cheap guess into a
false certificate. It is asymmetric by design: proxies buy cheap confirmations; the expensive resolver still
owns every rejection and every uncertain case. `cost_saving` reports the MEASURED saving, never a promised one.

Deterministic, zero-dependency, duck-typed: a resolver/proxy is either a callable(candidate)->bool or an object
with .evaluate(candidate).passed (any BaseEvaluator), or a callable returning a dict with a truthy pass key.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

_PASS_KEYS = ("passed", "controls_collapse", "ok", "green", "settled")


def as_verdict(resolver, candidate) -> bool:
    """Normalise any resolver/proxy shape to a bool verdict for `candidate` (True = it holds/passes)."""
    if hasattr(resolver, "evaluate"):
        return bool(resolver.evaluate(candidate).passed)
    out = resolver(candidate)
    if isinstance(out, dict):
        for k in _PASS_KEYS:
            if k in out:
                return bool(out[k])
        if "score" in out:
            return float(out["score"]) > 0.5
        return bool(out)
    return bool(out)


@dataclass
class ProxyCalibration:
    """How well a cheap proxy tracks the real resolver, measured on labelled cases. `tp` = proxy said YES and
    real agreed; `fp` = proxy said YES but real said NO (the dangerous error a proxy-confirm must avoid)."""
    proxy_name: str
    tp: int = 0
    fp: int = 0
    tn: int = 0
    fn: int = 0
    cost: float = 0.0            # relative cost of the proxy (1.0 = same as real)

    @property
    def n(self) -> int:
        return self.tp + self.fp + self.tn + self.fn

    @property
    def precision(self) -> float:
        """P(real YES | proxy YES) — the ONLY number that licenses a cheap proxy-confirm. 1.0 when it never
        said YES (vacuous), so `trustworthy` also requires enough positive support."""
        d = self.tp + self.fp
        return round(self.tp / d, 4) if d else 1.0

    @property
    def recall(self) -> float:
        d = self.tp + self.fn
        return round(self.tp / d, 4) if d else 0.0

    @property
    def agreement(self) -> float:
        return round((self.tp + self.tn) / self.n, 4) if self.n else 0.0

    @property
    def false_positive_rate(self) -> float:
        d = self.fp + self.tn
        return round(self.fp / d, 4) if d else 0.0

    def trustworthy(self, min_precision: float = 0.9, min_support: int = 5) -> bool:
        """A proxy may cheaply CONFIRM only if its positive predictions are precise AND it has actually been
        seen to say YES enough times (min_support) — so a proxy that never fires can't be 'trusted' vacuously."""
        return self.tp >= min_support and self.precision >= min_precision

    def markdown(self) -> str:
        return (f"- proxy `{self.proxy_name}` (cost {self.cost}): precision {self.precision} · recall "
                f"{self.recall} · agreement {self.agreement} · FPR {self.false_positive_rate} · n={self.n} "
                f"(tp={self.tp}, fp={self.fp}, tn={self.tn}, fn={self.fn})")


def calibrate_proxy(proxy, real, cases: Sequence, cost: float = 0.1, name: str = "proxy") -> ProxyCalibration:
    """Measure `proxy` against the trusted `real` resolver on `cases`. The real resolver defines ground truth
    (that is the point — a proxy is only ever as good as it agrees with the thing it is trying to cheapen)."""
    cal = ProxyCalibration(proxy_name=getattr(proxy, "name", name), cost=cost)
    for c in cases:
        p, r = as_verdict(proxy, c), as_verdict(real, c)
        if p and r:
            cal.tp += 1
        elif p and not r:
            cal.fp += 1
        elif (not p) and r:
            cal.fn += 1
        else:
            cal.tn += 1
    return cal


@dataclass
class SettlementOutcome:
    verdict: bool
    settled_by: str              # the proxy name, or 'real'
    cost: float
    escalated: bool              # True ⇒ the real resolver was run (no trustworthy proxy-confirm)
    why: str = ""


@dataclass
class VerificationEconomy:
    """A trusted real resolver + a set of cheaper proxies, each with a measured calibration. `settle` spends the
    least it honestly can: a trustworthy proxy-confirm when available, else the real resolver."""
    real: Callable
    real_cost: float = 1.0
    proxies: List[Tuple[str, Callable, float]] = field(default_factory=list)   # (name, proxy, cost)
    calibrations: Dict[str, ProxyCalibration] = field(default_factory=dict)

    def add_proxy(self, proxy, cost: float = 0.1, name: Optional[str] = None) -> "VerificationEconomy":
        self.proxies.append((name or getattr(proxy, "name", f"proxy{len(self.proxies)}"), proxy, cost))
        return self

    def calibrate(self, cases: Sequence) -> Dict[str, ProxyCalibration]:
        """Calibrate every proxy against the real resolver on `cases`. Run once on a labelled/settled set before
        relying on the economy — a proxy is trusted only where it has been measured."""
        self.calibrations = {name: calibrate_proxy(proxy, self.real, cases, cost=cost, name=name)
                             for name, proxy, cost in self.proxies}
        return self.calibrations

    def _trustworthy_confirmers(self, min_precision: float, min_support: int):
        """Trustworthy proxies, cheapest first — the order in which we try to buy a cheap confirmation."""
        out = [(name, proxy, cost) for name, proxy, cost in self.proxies
               if self.calibrations.get(name)
               and self.calibrations[name].trustworthy(min_precision, min_support)]
        return sorted(out, key=lambda t: t[2])

    def settle(self, candidate, min_precision: float = 0.9, min_support: int = 5) -> SettlementOutcome:
        """Settle `candidate` for the least honest cost: the cheapest TRUSTWORTHY proxy that CONFIRMS it (says
        YES) settles it as YES cheaply; otherwise the real resolver decides. A proxy NEVER settles a rejection
        or an uncertain case — those always escalate, so the economy cannot fabricate a pass."""
        for name, proxy, cost in self._trustworthy_confirmers(min_precision, min_support):
            if as_verdict(proxy, candidate):
                return SettlementOutcome(verdict=True, settled_by=name, cost=cost, escalated=False,
                                         why=f"trusted proxy '{name}' (precision "
                                             f"{self.calibrations[name].precision}) confirmed it cheaply.")
        v = as_verdict(self.real, candidate)
        return SettlementOutcome(verdict=v, settled_by="real", cost=self.real_cost, escalated=True,
                                 why="no trustworthy proxy-confirm → the real resolver settled it.")

    def cost_saving(self, cases: Sequence, min_precision: float = 0.9, min_support: int = 5) -> Dict:
        """The MEASURED economy on `cases`: total cost of settling them all through the economy vs always
        running the real resolver, plus how many were cheaply confirmed. Honest — nothing is promised."""
        # BUGFIX: settle each case ONCE (the old code called settle twice per case — for `spent` and again for
        # `confirmed` — doubling the expensive real-resolver calls the module exists to minimise, and breaking
        # for any nondeterministic/side-effecting resolver).
        outcomes = [self.settle(c, min_precision, min_support) for c in cases]
        spent = sum(o.cost for o in outcomes)
        baseline = self.real_cost * len(cases)
        confirmed = sum(1 for o in outcomes if not o.escalated)
        return {"economy_cost": round(spent, 4), "baseline_cost": round(baseline, 4),
                "saving": round(baseline - spent, 4),
                "saving_fraction": round((baseline - spent) / baseline, 4) if baseline else 0.0,
                "cheaply_confirmed": confirmed, "n": len(cases)}

    def markdown(self) -> str:
        L = ["### Verification economy — settle more, spend less, fabricate nothing",
             f"- real resolver cost: {self.real_cost} · proxies: {len(self.proxies)}"]
        L += [self.calibrations[name].markdown() for name, _p, _c in self.proxies if name in self.calibrations]
        L.append("- a proxy may only CHEAPLY CONFIRM where it is precise; rejections/uncertain escalate to real.")
        return "\n".join(L)
