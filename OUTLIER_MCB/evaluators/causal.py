"""evaluators.causal — settle a Candidate by an INTERVENTION test, not by correlation.

The causal sibling of evaluators.symbolic. A Candidate proposes breaking a hidden assumption of naive
association (the association is direct / the direction is known / all confounders are observed). The
broken assumption routes it to an identification strategy — primarily BACK-DOOR ADJUSTMENT: estimate the
treatment→outcome effect while controlling for the observed confounders. The estimate is then settled by
the same discipline the kernel already uses for everything else — the controls must collapse:

  • placebo — permuting the treatment must drive the estimated effect to ~0 (it is not an artifact);
  • confounding refutation — the candidate's effect must match the refutation-robust estimate (the one
    that adjusts for ALL observed confounders). A naive (no-adjustment) claim on confounded data is
    BIASED away from it — that bias IS the "correlation ≠ causation" gap, and the engine reports it.

The objective is causal CORRECTNESS, not effect size: a candidate scores high when its chosen adjustment
set yields an UNBIASED, placebo-collapsing estimate — so on confounded data the engine prefers the
candidate that correctly finds NO direct edge over the one that reports a spurious one. Honesty about the
Achilles heel is built in: a candidate that breaks the causal-sufficiency assumption (admits hidden
confounders) is reported HUMAN — observational adjustment cannot settle latent confounding; an experiment must.

The default backend is zero-dependency and deterministic (a standardized partial-regression estimator,
reusing evaluators.symbolic.least_squares). Inject a real backend (DoWhy: identify → estimate → refute,
whose refuters ARE this controls-collapse) by passing `backend=`.
"""
from __future__ import annotations
import math
import random
from typing import Callable, Dict, List, Optional, Sequence

from .symbolic import Term, expansions_for, least_squares

_EPS = 1e-9

# generic English hints for the causal capability tokens (used only when no pack resolves them).
_CAUSAL_TEXT_HINTS = {
    "confounder_adjustment": ("confound", "adjust", "backdoor", "back-door", "spurious", "common cause", "direct effect"),
    "temporal_order": ("direction", "reverse", "precede", "temporal", "time order", "arrow"),
    "latent_variable_search": ("latent", "hidden", "unobserved", "unmeasured", "sufficiency"),
    "subgroup_data": ("heterogen", "subgroup", "moderat", "effect modif"),
}


def _standardize(values: Sequence[float]) -> List[float]:
    n = len(values)
    if n == 0:
        return []
    mean = sum(values) / n
    std = math.sqrt(sum((v - mean) ** 2 for v in values) / n)
    return [(v - mean) / (std + _EPS) for v in values]


def _partial_coef(cols: Dict[str, List[float]], treatment_vals: List[float], outcome: str,
                  adjust_set: Sequence[str]) -> float:
    """Standardized partial-regression coefficient of `treatment_vals` on `outcome`, controlling for the
    adjustment set — the back-door estimate. Standardized so the threshold is scale-free."""
    n = len(treatment_vals)
    ts = _standardize(treatment_vals)
    ys = _standardize(cols[outcome])
    adj = [_standardize(cols[z]) for z in adjust_set]
    rows = [[ts[i]] + [a[i] for a in adj] for i in range(n)]
    terms: List[Term] = [Term("1", lambda r: 1.0), Term("t", lambda r: r[0])]
    for k in range(len(adjust_set)):
        terms.append(Term(f"z{k}", lambda r, k=k: r[k + 1]))
    formula = least_squares(rows, ys, terms)
    return formula.coeffs[1]            # the treatment coefficient (terms[0] is the intercept)


def causal_evaluator(data: Dict[str, Sequence[float]], treatment: str, outcome: str,
                     confounders: Sequence[str], pack=None, backend: Optional[Callable] = None,
                     edge_threshold: float = 0.15, seed: int = 0) -> Callable[[object], Dict]:
    """An EXTERNAL evaluator (Candidate -> {"score", **evidence}) that settles a candidate by an
    intervention/refutation test on `data` (column name -> values).

    The candidate's broken assumption chooses the adjustment set (breaking the 'association is direct'
    assumption → adjust for `confounders`; otherwise the naive empty set). The score in [0,1] rewards an
    UNBIASED, placebo-collapsing estimate: bias is measured against the refutation-robust estimate that
    adjusts for ALL observed confounders. Reports the spurious-edge gap (`confounding_detected`) and the
    causal verdict. A candidate that breaks the causal-sufficiency assumption is flagged HUMAN (latent
    confounding is not identifiable from observation). `backend(data, treatment, outcome, adjust_set) ->
    float` overrides the default estimator (wire DoWhy here)."""
    cols = {k: list(v) for k, v in data.items()}
    base_treatment = cols[treatment]

    def _estimate(treatment_vals, adjust_set):
        if backend is not None:
            return backend(cols, treatment_vals, outcome, adjust_set)
        return _partial_coef(cols, treatment_vals, outcome, adjust_set)

    # the refutation-robust truth: adjust for ALL observed confounders (identifiable IFF sufficiency holds).
    truth = _estimate(base_treatment, confounders)
    naive = _estimate(base_treatment, [])                       # the box's no-adjustment estimate

    def _ev(candidate) -> Dict:
        strategies = expansions_for(candidate, pack, text_hints=_CAUSAL_TEXT_HINTS)
        adjusts = "confounder_adjustment" in strategies
        latent = "latent_variable_search" in strategies
        adjust_set = list(confounders) if adjusts else []
        effect = _estimate(base_treatment, adjust_set)

        rng = random.Random(seed)
        placebo_treatment = list(base_treatment)
        rng.shuffle(placebo_treatment)
        placebo = _estimate(placebo_treatment, adjust_set)
        controls_collapse = abs(placebo) <= max(edge_threshold, 0.3 * abs(effect))

        bias = abs(effect - truth)                              # distance from the unbiased estimate
        confounding_detected = round(abs(naive - truth), 4)     # the correlation≠causation gap
        unbiased = max(0.0, 1.0 - bias)
        score = round(unbiased * (1.0 if controls_collapse else 0.5), 4)
        verdict = "EDGE" if abs(truth) > edge_threshold else "NO_EDGE"
        return {"score": score, "effect": round(effect, 4), "refutation_robust_effect": round(truth, 4),
                "naive_effect": round(naive, 4), "placebo_effect": round(placebo, 4),
                "confounding_detected": confounding_detected, "controls_collapse": controls_collapse,
                "adjusted": adjusts, "causal_verdict": verdict,
                "verifiability": "HUMAN" if latent else "AUTO"}

    return _ev
