"""readiness_discovery — an honest gate for DISCOVERY claims (distinct from the 1.0 release gate).

It does not ask "do the unit tests pass"; it asks "is this library entitled to make discovery claims, and
how strong?". It probes real runtime capabilities — explicit novelty_scope, an honest offline fallback,
conservative discovery metrics, non-overclaiming math, and whether a live online prior-art search actually
works — and returns one of:

  NOT_READY_DISCOVERY          a core honesty capability is missing.
  LOCAL_ONLY_READY             honest locally, but NO confirmed online prior-art search → no global novelty.
  ONLINE_AUDIT_READY           an online prior-art search is reachable; novelty can be scoped to it.
  DISCOVERY_EXPERIMENTAL_READY online audit AND a formal math backend (SymPy) are both available.

The rule the prompt demands: without a reachable online provider it can NEVER declare online-ready.
"""
from __future__ import annotations
from typing import Dict, Optional

DISCOVERY_STATES = ("NOT_READY_DISCOVERY", "LOCAL_ONLY_READY", "ONLINE_AUDIT_READY", "DISCOVERY_EXPERIMENTAL_READY")
_CORE = ("novelty_scope_supported", "offline_fallback_honest", "discovery_metrics_conservative",
         "math_no_overclaim", "no_absolute_verdicts")


def readiness_discovery_report(online_provider=None, probe_query: str = "a novel distributed rate limiter") -> Dict:
    """Probe discovery-readiness. Pass `online_provider` (a PriorArtProvider / CompositePriorArtProvider) to
    test live online prior art; without one the report cannot exceed LOCAL_ONLY_READY."""
    import OUTLIER_MCB as gsl
    checks: Dict[str, Dict] = {}

    def chk(name, passed, detail=""):
        checks[name] = {"passed": bool(passed), "detail": detail}

    # 1. explicit novelty_scope on the verdict
    v = gsl.NoveltyVerdict(idea="x", status="", confidence=0.0)
    chk("novelty_scope_supported", hasattr(v, "novelty_scope") and hasattr(v, "scoped_verdict"),
        "NoveltyVerdict carries novelty_scope + scoped_verdict()")

    # 2. offline fallback is honest: a local-only search cannot yield strong provisional novelty
    off = gsl.CompositePriorArtProvider([gsl.OfflinePriorArtProvider([{"title": "an unrelated thing"}])])
    ov = gsl.prior_art_audit(probe_query, off)
    chk("offline_fallback_honest", ov.novelty_scope == "LOCAL_ONLY" and ov.graded_verdict != "PROVISIONALLY_NOVEL",
        f"scope={ov.novelty_scope}, verdict={ov.graded_verdict}")

    # 3. discovery metrics are conservative (a weak link caps confidence)
    dc = gsl.discovery_confidence(structure=1.0, semantic_novelty=1.0, materialization=0.0,
                                  verification=0.0, novelty_scope="LOCAL_ONLY")
    chk("discovery_metrics_conservative", dc["discovery_confidence"] <= 0.5 and bool(dc["caps_applied"]),
        f"confidence={dc['discovery_confidence']}")

    # 4. math discovery does not overclaim
    sketch = gsl.investigate_conjecture(gsl.Conjecture("an unjustified claim"), use_sympy=False)
    false_id = gsl.investigate_conjecture(gsl.Conjecture("x*x == x", variables={"x": (-5.0, 5.0)}),
                                          predicate=lambda x: abs(x * x - x) < 1e-9, use_sympy=False)
    chk("math_no_overclaim", sketch.status == "SKETCH" and false_id.status == "COUNTEREXAMPLE_FOUND",
        f"sketch={sketch.status}, false_identity={false_id.status}")

    # 5. graded verdicts never say 'absolute'
    chk("no_absolute_verdicts", all("absolute" not in g.lower() for g in gsl.GRADED_VERDICTS))

    # 6. live online prior art reachable?
    online_ok, online_detail = False, "no online provider supplied"
    if online_provider is not None:
        try:
            comp = (online_provider if isinstance(online_provider, gsl.CompositePriorArtProvider)
                    else gsl.CompositePriorArtProvider([online_provider]))
            r = comp.research(probe_query)
            online_ok = r.get("novelty_scope") == "ONLINE_PRIOR_ART_CHECKED"
            online_detail = f"scope={r.get('novelty_scope')}; checked={[c['provider'] for c in r.get('checked_sources', [])]}"
        except Exception as exc:
            online_detail = f"failed: {exc}"
    chk("online_prior_art_reachable", online_ok, online_detail)

    # 7. formal math backend (for experimental-ready)
    try:
        import sympy  # noqa: F401
        sympy_ok = True
    except ImportError:
        sympy_ok = False
    chk("formal_math_backend", sympy_ok, "SymPy available" if sympy_ok else "SymPy not installed (optional)")

    core_ok = all(checks[c]["passed"] for c in _CORE)
    if not core_ok:
        state = "NOT_READY_DISCOVERY"
    elif not online_ok:
        state = "LOCAL_ONLY_READY"
    elif not sympy_ok:
        state = "ONLINE_AUDIT_READY"
    else:
        state = "DISCOVERY_EXPERIMENTAL_READY"

    failing = [n for n, c in checks.items() if not c["passed"]]
    note = ("no reachable online provider → cannot declare online-ready (LOCAL_ONLY at best)."
            if not online_ok else "online prior-art search confirmed reachable.")
    return {"state": state, "checks": checks, "failing": failing, "note": note}


def markdown(report: Dict) -> str:
    L = [f"# Discovery readiness — {report['state']}", "", f"_{report['note']}_", "", "## Checks"]
    for name, c in report["checks"].items():
        L.append(f"- {'✅' if c['passed'] else '⚠'} {name}  {c['detail']}")
    return "\n".join(L)
