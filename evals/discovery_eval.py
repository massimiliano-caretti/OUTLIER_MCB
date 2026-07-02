"""discovery_eval — does the autonomous inventor produce DATA-SETTLED discoveries, and do the mechanisms
earn their keep? A REAL eval: the inventor is settled by symbolic/causal evaluators on data with a KNOWN
answer, not by the structural proxy. Deterministic and offline (synthetic fixtures with a ground truth).

What it measures, honestly:
  • settled_correct  — with a real evaluator, the inventor CONFIRMS exactly the assumption the data supports
                       (the interaction break on interaction data; the confounder-adjustment break on
                       confounded data). This is the headline: real discovery, not structural theater.
  • blend_added      — conceptual blending adds cross-domain candidate problems (coverage delta).
  • memory_prior     — the cumulative memory records the confirmed assumption as fertile (compounds).
  • satisfaction     — the joy-of-discovery signal accumulated from surprising-and-confirmed steps.

Honest limit (stated, not hidden): curiosity and transformation show their value on LARGE / unknown spaces;
on a fixed 4-assumption pack the settled OUTCOME is robust to them, so this eval does not claim a delta for
them — it measures what these small, deterministic tasks can actually settle.
"""
from __future__ import annotations
import random
from typing import Dict


def _numeric_task():
    import OUTLIER_MCB as gsl
    rng = random.Random(7)
    X = [[rng.uniform(-2, 2), rng.uniform(-2, 2), rng.uniform(-2, 2)] for _ in range(120)]
    y = [2.0 * r[0] * r[1] - 3.0 for r in X]              # a pure interaction law (ground truth)
    cut = int(0.66 * 120)
    data = (X[:cut], y[:cut], X[cut:], y[cut:])
    pack = gsl.get_pack("numeric")
    return pack, gsl.symbolic_evaluator(data, pack=pack), "law_is_separable", "causal"


def _causal_task():
    import OUTLIER_MCB as gsl
    rng = random.Random(11)
    Z = [rng.gauss(0, 1) for _ in range(400)]
    A = [Z[i] + 0.5 * rng.gauss(0, 1) for i in range(400)]
    B = [Z[i] + 0.5 * rng.gauss(0, 1) for i in range(400)]   # A and B confounded by Z, no A→B (ground truth)
    pack = gsl.get_pack("causal")
    ev = gsl.causal_evaluator({"A": A, "B": B, "Z": Z}, "A", "B", ["Z"], pack=pack)
    return pack, ev, "association_is_direct", "numeric"


def _confirmed(run) -> set:
    return {s.seed for s in run.steps if s.outcome == "CONFIRMED"}


def _capability_checks() -> Dict:
    """Measure the NEW discovery capabilities the primary eval (run_eval) does not — so improvement toward
    the maximum objective is actually tracked. All offline / deterministic (fixtures + fake online providers)."""
    import OUTLIER_MCB as gsl

    class _Online(gsl.OnlinePriorArtProvider):
        def __init__(self, name): super().__init__(); self.name = name
        def _fetch(self, q): return [gsl.PriorArtResult(title="unrelated work", url=f"http://{self.name}")]

    # prior-art scope + coverage: offline ⇒ LOCAL_ONLY (no strong novelty); 2 online ⇒ ONLINE + MULTI
    off = gsl.CompositePriorArtProvider([gsl.OfflinePriorArtProvider([{"title": "x"}])])
    on2 = gsl.CompositePriorArtProvider([_Online("a"), _Online("b")])
    v_off, v_on = gsl.prior_art_audit("a novel idea", off), gsl.prior_art_audit("a novel idea", on2)
    # math discovery honesty: a true identity is at least empirically supported; a false one is killed
    proved = gsl.investigate_conjecture(gsl.Conjecture("(x+1)**2==x**2+2*x+1", lhs="(x+1)**2", rhs="x**2+2*x+1",
                                                       variables={"x": (-3.0, 3.0)})).status
    killed = gsl.investigate_conjecture(gsl.Conjecture("x*x==x", variables={"x": (-3.0, 3.0)}),
                                        predicate=lambda x: abs(x * x - x) < 1e-9, use_sympy=False).status
    # discovery_confidence is conservative: a paraphrase (no online, unmaterialized, unverified) cannot be high
    para = gsl.discovery_confidence(structure=0.9, semantic_novelty=0.95, materialization=0.0,
                                    verification=0.0, novelty_scope="LOCAL_ONLY")["discovery_confidence"]
    full = gsl.discovery_confidence(structure=0.9, semantic_novelty=0.8, prior_art_distance=0.9,
                                    materialization=1.0, verification=1.0,
                                    novelty_scope="ONLINE_PRIOR_ART_CHECKED")["discovery_confidence"]
    return {
        "prior_art_local_only_no_strong_novelty": v_off.novelty_scope == "LOCAL_ONLY" and v_off.graded_verdict != "PROVISIONALLY_NOVEL",
        "prior_art_online_multi_coverage": v_on.novelty_scope == "ONLINE_PRIOR_ART_CHECKED" and v_on.coverage_level == "MULTI",
        "math_true_supported": proved in ("EMPIRICALLY_SUPPORTED", "FORMALLY_PROVED"),
        "math_false_killed": killed == "COUNTEREXAMPLE_FOUND",
        "confidence_paraphrase_capped": para <= 0.5,
        "confidence_full_high": full > 0.7,
    }


def run_discovery_eval() -> Dict:
    """Run both settled tasks + the new-capability checks + the ablations these small tasks can honestly measure."""
    import OUTLIER_MCB as gsl
    out: Dict[str, Dict] = {"capabilities": _capability_checks()}
    for name, (pack, ev, fertile, other) in {"numeric": _numeric_task(), "causal": _causal_task()}.items():
        full = gsl.autonomous_inventor(pack=pack, evaluator=ev, accept=0.7, blend_with=[],
                                       curiosity=0.3, top_problems=9)
        confirmed = _confirmed(full)
        no_blend = len(gsl.autonomous_inventor(pack=pack, evaluator=ev, accept=0.7, blend_with=[],
                                               top_problems=9).steps)
        with_blend = len(gsl.autonomous_inventor(pack=pack, evaluator=ev, accept=0.7, blend_with=[other],
                                                 top_problems=9).steps)
        mem = gsl.DiscoveryMemory()
        gsl.autonomous_inventor(pack=pack, evaluator=ev, accept=0.7, blend_with=[], discovery_memory=mem,
                                top_problems=9)
        out[name] = {
            "fertile_truth": fertile,
            "confirmed": sorted(confirmed),
            "settled_correct": fertile in confirmed and confirmed == {fertile},
            "blend_added": with_blend > no_blend,
            "memory_prior_fertile": mem.prior(fertile, pack.name),
            "satisfaction": full.total_satisfaction,
            "settled_by": "real evaluator (not structural)",
        }
    return out


def markdown(report: Dict) -> str:
    L = ["# Discovery eval — settled by real evaluators (not the structural proxy)", ""]
    caps = report.get("capabilities", {})
    if caps:
        L.append("## New-capability checks (what run_eval does not measure)")
        L += [f"- {'✅' if v else '❌'} {k}" for k, v in caps.items()]
        L.append("")
    for task, r in report.items():
        if task == "capabilities":
            continue
        ok = "✅" if r["settled_correct"] else "❌"
        L.append(f"## {task}  {ok}")
        L.append(f"- ground-truth fertile assumption: `{r['fertile_truth']}` · confirmed by data: {r['confirmed']}")
        L.append(f"- blending added cross-domain problems: {r['blend_added']} · memory prior on fertile: "
                 f"{r['memory_prior_fertile']} · satisfaction: {r['satisfaction']}")
    L += ["", "_Honest limit: curiosity & transformation prove out on large/unknown spaces; on these fixed "
          "4-assumption packs the settled outcome is robust to them, so no delta is claimed for them here._"]
    return "\n".join(L)


if __name__ == "__main__":
    print(markdown(run_discovery_eval()))
