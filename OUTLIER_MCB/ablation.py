"""ablation — the gameability / ablation gate (fix C): a scoring component earns its place ONLY if removing
it CHANGES a keep/drop decision on a held-out set. A component that never flips a decision is DECORATIVE —
'more metrics is better' is false. This is how the engine disciplines its OWN scoring: every metric must
prove it discriminates, or it is recommended for deletion (never auto-deleted — a human settles it).

The test is honest by construction: it does not ask whether a metric *moves the score* (everything does a
little), it asks whether the metric ever changes WHO IS KEPT. A signal that shifts every candidate equally,
or that is constant across the population, cannot change a ranking — and a metric that cannot change a
decision is decoration, however principled it sounds.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

# the raw inputs invention_score actually reads (the keys an ablation perturbs)
INVENTION_COMPONENTS = ("correctness", "novelty_distance", "improvement_over_baseline", "improvement_over_parent",
                        "assumption_break_depth", "diversity", "usefulness_proxy", "test_quality",
                        "reproducibility", "simplicity", "risk")

# hard gates: they govern the ABSOLUTE keep/verified decision (a cap), not the relative ranking — so a
# ranking ablation may not flip them, yet they are never decorative. Reported, never recommended for deletion.
PROTECTED_COMPONENTS = ("correctness",)


@dataclass
class ComponentVerdict:
    component: str
    status: str                  # "earned" | "decorative" | "untestable_here"
    decision_flips: int          # how many keep/drop decisions changed when this component was ablated
    mean_score_shift: float      # mean |Δscore| when ablated — a secondary signal (moving ≠ discriminating)
    varies: bool                 # did the raw input vary across the population at all?
    recommendation: str

    @property
    def influential(self) -> bool:
        return self.status == "earned"

    def markdown(self) -> str:
        mark = {"earned": "✓ keep", "decorative": "✗ DROP", "untestable_here": "· n/a",
                "structural_gate": "▣ gate"}[self.status]
        return (f"  {mark} **{self.component}** — flips {self.decision_flips} · mean |Δscore| "
                f"{self.mean_score_shift} — {self.recommendation}")


@dataclass
class AblationReport:
    verdicts: List[ComponentVerdict]
    n_items: int
    keep_fraction: float

    def decorative(self) -> List[str]:
        """Components that VARIED across the population yet never changed a keep/drop decision — the honest
        delete/merge candidates. A component that was constant here is NOT listed (it could not be tested)."""
        return [v.component for v in self.verdicts if v.status == "decorative"]

    def untestable_here(self) -> List[str]:
        """Components constant across this population — no variance to test; gather a more varied held-out set."""
        return [v.component for v in self.verdicts if v.status == "untestable_here"]

    def earned(self) -> List[str]:
        return [v.component for v in self.verdicts if v.status == "earned"]

    def structural_gates(self) -> List[str]:
        """Hard-gate components reported but never recommended for deletion (they cap, not rank)."""
        return [v.component for v in self.verdicts if v.status == "structural_gate"]

    def markdown(self) -> str:
        head = (f"## Ablation gate — {len(self.earned())} earned · {len(self.decorative())} decorative · "
                f"{len(self.untestable_here())} untestable · {len(self.structural_gates())} gates "
                f"({self.n_items} items, keep top {int(self.keep_fraction * 100)}%)")
        body = [v.markdown() for v in self.verdicts]
        if self.decorative():
            body.append(f"- DECORATIVE (varied yet never flipped a decision): {', '.join(self.decorative())} — "
                        "delete or merge; 'more metrics is better' is false.")
        if self.untestable_here():
            body.append(f"- untestable on this population (constant — no variance): "
                        f"{', '.join(self.untestable_here())} — needs a held-out set where it varies.")
        return "\n".join([head] + body)


def _topk_keep(scores: List[float], keep_fraction: float) -> List[bool]:
    """Keep the top `keep_fraction` of items by score (a RELATIVE decision: tests discriminative value).
    Ties are broken by original order so the decision is deterministic."""
    n = len(scores)
    if n == 0:
        return []
    k = max(1, min(n, int(math.ceil(keep_fraction * n))))
    order = sorted(range(n), key=lambda i: (-scores[i], i))
    keep = set(order[:k])
    return [i in keep for i in range(n)]


def ablation_gate(items: List[Dict], score_fn: Optional[Callable] = None, components: Optional[List[str]] = None,
                  decision_fn: Optional[Callable] = None, keep_fraction: float = 0.5,
                  null_value: float = 0.0, protected=PROTECTED_COMPONENTS) -> AblationReport:
    """For each component, ablate it (set its raw input to `null_value` for ALL items so it can no longer
    discriminate), re-score, and count how many keep/drop decisions flip. Zero flips ⇒ decorative.

    `items`        raw component dicts (the inputs to `score_fn`).
    `score_fn`     dict → float; defaults to invention_score(...)['score'].
    `decision_fn`  list[score] → list[bool] (keep mask); defaults to keep-top-`keep_fraction`.
    """
    from .evolve import invention_score
    score_fn = score_fn or (lambda it: invention_score(it)["score"])
    components = list(components or INVENTION_COMPONENTS)
    decide = decision_fn or (lambda scores: _topk_keep(scores, keep_fraction))

    base_scores = [score_fn(it) for it in items]
    base_keep = decide(base_scores)
    verdicts: List[ComponentVerdict] = []
    for comp in components:
        vals = [float(it.get(comp, 0.0) or 0.0) for it in items]
        varies = (max(vals) - min(vals) > 1e-9) if vals else False
        ablated_scores = [score_fn({**it, comp: null_value}) for it in items]
        ablated_keep = decide(ablated_scores)
        flips = sum(1 for a, b in zip(base_keep, ablated_keep) if a != b)
        shift = round(sum(abs(a - b) for a, b in zip(base_scores, ablated_scores)) / max(1, len(items)), 4)
        if flips > 0:
            status, rec = "earned", "changes which candidates are kept — earned"
        elif comp in protected:
            status, rec = "structural_gate", "hard gate (caps the absolute keep/verified decision) — reported, never auto-dropped"
        elif not varies:
            status, rec = "untestable_here", "constant across this population — NOT testable here; needs a held-out set where it varies"
        else:
            status, rec = "decorative", "DECORATIVE — varied yet never changed a keep/drop decision; delete or merge"
        verdicts.append(ComponentVerdict(comp, status, flips, shift, varies, rec))
    verdicts.sort(key=lambda v: ({"earned": 0, "decorative": 1, "untestable_here": 2, "structural_gate": 3}[v.status],
                                 -v.decision_flips, -v.mean_score_shift))
    return AblationReport(verdicts=verdicts, n_items=len(items), keep_fraction=keep_fraction)


@dataclass
class HackVerdict:
    """Per-candidate reward-hacking audit: does this kept candidate survive on the HARD external signal, or
    only because of fragile, gameable soft proxies?"""
    index: int
    kept: bool
    leans_on: List[str]           # non-protected components whose ablation alone drops it out of the keep set
    gamed: bool                   # kept, leans on ≥1 component, and NONE of them is a protected (external) gate

    def markdown(self) -> str:
        if not self.kept:
            return f"  · item {self.index}: not kept"
        if self.gamed:
            return f"  ✗ item {self.index}: REWARD-HACKING RISK — kept only via soft proxies {self.leans_on}"
        return f"  ✓ item {self.index}: robust (keep not fragile to a single gameable signal)"


def reward_hacking_report(items: List[Dict], score_fn: Optional[Callable] = None,
                          components: Optional[List[str]] = None, decision_fn: Optional[Callable] = None,
                          keep_fraction: float = 0.5, null_value: float = 0.0,
                          protected=PROTECTED_COMPONENTS) -> List[HackVerdict]:
    """Anti-gaming guard: a fixed scalar objective is maximally gameable, so audit EACH kept candidate for
    fragile single-signal dependence. For every non-protected component, ablate it across the pool, re-decide,
    and record which components — removed alone — drop this candidate out of the kept set (`leans_on`). A
    candidate that is kept yet leans ONLY on soft, gameable proxies (never on a protected/external gate such as
    `correctness`) is flagged `gamed`: it wins on the metric, not on the world. Robust candidates — whose keep
    survives every single-component ablation, or rests on a protected gate — are not flagged.

    The engine disciplines its OWN objective here; it reports, it never deletes (a human settles it)."""
    from .evolve import invention_score
    score_fn = score_fn or (lambda it: invention_score(it)["score"])
    components = list(components or INVENTION_COMPONENTS)
    decide = decision_fn or (lambda scores: _topk_keep(scores, keep_fraction))

    base_keep = decide([score_fn(it) for it in items])
    # precompute, per ablated component, the keep mask for the whole pool
    ablated_keep = {comp: decide([score_fn({**it, comp: null_value}) for it in items]) for comp in components}

    out: List[HackVerdict] = []
    for i, kept in enumerate(base_keep):
        if not kept:
            out.append(HackVerdict(index=i, kept=False, leans_on=[], gamed=False))
            continue
        leans = [comp for comp in components if base_keep[i] and not ablated_keep[comp][i]]
        leans_soft = [c for c in leans if c not in protected]
        gamed = bool(leans) and len(leans_soft) == len(leans)   # depends only on non-protected (gameable) signals
        out.append(HackVerdict(index=i, kept=True, leans_on=leans, gamed=gamed))
    return out


def _item_from_record(r) -> Dict:
    """Reconstruct the raw scoring inputs from a stored record (best-effort: the post-cap component values are
    used as a proxy for the raw inputs — adequate for a decorative-metric diagnostic, not for re-scoring)."""
    sc = getattr(r, "score_components", {}) or {}
    return {
        "correctness": 1.0 if getattr(r, "correctness_passed", False) else 0.0,
        "novelty_distance": sc.get("novelty", 0.0),
        "improvement_over_baseline": getattr(r, "improvement_over_baseline", 0.0) or 0.0,
        "improvement_over_parent": getattr(r, "improvement_over_parent", 0.0) or 0.0,
        "assumption_break_depth": sc.get("assumption_break_depth", 0.0),
        "diversity": sc.get("diversity", 0.0),
        "usefulness_proxy": sc.get("usefulness_proxy", 0.0),
        "test_quality": sc.get("test_quality", 0.0),
        "reproducibility": sc.get("reproducibility", 0.0),
        "simplicity": sc.get("simplicity", 0.0),
        "risk": sc.get("risk_penalty", 0.0),
        "novelty_scope": getattr(r, "novelty_scope", ""),
    }


def ablation_gate_from_records(records, keep_fraction: float = 0.5) -> AblationReport:
    """Run the ablation gate over a population of EvolutionRecords (e.g. an EvolveResult's memory)."""
    recs = records.all() if hasattr(records, "all") else list(records)
    return ablation_gate([_item_from_record(r) for r in recs], keep_fraction=keep_fraction)
