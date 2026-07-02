"""multi_metric_loop — genuine self-improvement: raise EVERY performance dimension, regress NONE (a Pareto gate).

A single score can be chased for its own sake. This loop instead tracks a VECTOR of externally-certified
performance metrics across DIFFERENT capabilities, and accepts a change ONLY if it improves at least one
dimension AND regresses none — so the engine truly gets better all-round, never trading one skill for another.

Dimensions (each settled by an EXTERNAL resolver — see landscapes.py — never self-judged):
  • sr_recovery       — symbolic-regression laws recovered exactly on the Feynman substrate (R²>0.999 + SymPy form);
  • counterexample    — FALSE conjectures refuted with a real counterexample (a verified fact);
  • judge_calibration — adversarial claims classified correctly against GROUND-TRUTH labels;
  • external_transfer — laws recovered on a HELD-OUT substrate the primitives were NEVER designed for (the
                        anti-autoreferentiality dimension: a gain here cannot be substrate-overfit; negative
                        control = shuffled targets must collapse it);
  • curriculum_progression — fraction of a SELF-GENERATED increasing-difficulty curriculum the engine solves
                        (POET-like: it manufactures its own harder problems with KNOWN ground truth, settled
                        externally by R²+SymPy, scrambled-target negative control). Breaks problem_space_is_static;
  • open_ended_reach   — an UNBOUNDED ratchet: the deepest self-generated depth-k product the engine certifies,
                        growing product_k on demand over an EXPANDING primitive space. No built-in 1.0 ceiling —
                        it climbs until the compute budget (`reach_budget`), so exploration is UNLIMITED (POET-like)
                        yet every depth is externally settled. Breaks benchmark_ceiling_is_fixed. (Excluded from the
                        [0,1] "weakest skill" aggregate since it is an integer depth, not a rate.)

Each epoch (library-driven): DIAGNOSE the weakest dimension (key-log), PROPOSE an upgrade for it (a new SR
primitive, or a wider counterexample search window), MEASURE the FULL vector, and keep it only if the Pareto gate
holds (no dimension down, at least one up). The aggregate reported is min(vector) — the weakest skill — so
'better' means the whole profile rises, not one number. Deterministic. Run:  python -m evals.multi_metric_loop
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from OUTLIER_MCB.self_diagnosis import DiagnosticLog, DiagnosticMemory


from OUTLIER_MCB.verified_novelty import pareto_improves as pareto_accept   # the Pareto gate lives in the library


def _sr_recovery_maps(equations, primitives, n_samples):
    """Precompute, once: the laws recovered by the BASE basis, and the extra laws each primitive recovers
    (symbolic-certified). sr_recovery for a set of primitives is then |base ∪ their recoveries| / N — fast."""
    from evals.self_improve_loop import _recovers
    base = {eq.id for eq in equations if _recovers(eq, None, n_samples)}
    rec = {name: {eq.id for eq in equations if eq.id not in base and _recovers(eq, b, n_samples)}
           for name, b in primitives.items()}
    return base, rec


@dataclass
class MultiMetricEpoch:
    epoch: int
    bottleneck: str
    proposed: str
    accepted: bool
    vector: Dict[str, float]
    aggregate_min: float
    aggregate_mean: float
    note: str


@dataclass
class MultiMetricResult:
    trajectory: List[MultiMetricEpoch] = field(default_factory=list)
    start_vector: Dict[str, float] = field(default_factory=dict)
    final_vector: Dict[str, float] = field(default_factory=dict)
    accepted: List[str] = field(default_factory=list)
    memory: object = None
    patience: int = 10
    stopped_early: bool = False
    plateau_epochs: int = 0
    plateau_report: str = ""

    @property
    def regressed_any(self) -> bool:
        return any(self.final_vector[d] < self.start_vector[d] for d in self.start_vector)

    def markdown(self) -> str:
        dims = sorted(self.start_vector)
        L = [f"## Multi-metric self-improvement — improve EVERY dimension, regress NONE (Pareto gate)",
             f"- start vector: {self.start_vector}",
             f"- final vector: {self.final_vector}",
             f"- regressed any dimension? **{self.regressed_any}**  (must be False)",
             f"- early stop: {self.stopped_early} (patience {self.patience}; plateau {self.plateau_epochs} epochs)",
             f"- accepted upgrades: {self.accepted}", "",
             "| epoch | weakest dim | proposed | ok | " + " | ".join(dims) + " | min |",
             "|---|---|---|---|" + "---|" * (len(dims) + 1)]
        for r in self.trajectory:
            L.append(f"| {r.epoch} | {r.bottleneck} | {r.proposed} | {'✓' if r.accepted else '·'} | "
                     + " | ".join(str(r.vector[d]) for d in dims) + f" | {r.aggregate_min} |")
        if self.plateau_report:
            L += ["", self.plateau_report]
        return "\n".join(L)


def multi_metric_self_improve(epochs: int = 30, n_samples: int = 250, equations=None,
                              widths: Optional[List[int]] = None, patience: int = 10,
                              memory: Optional[DiagnosticMemory] = None, reach_budget: int = 6,
                              reach_samples: int = 300) -> MultiMetricResult:
    from evals.benchmarks.feynman import FEYNMAN_ALL
    from evals.benchmarks.counterexamples import refutation_rate
    from OUTLIER_MCB.grown_basis import GROWN_PRIMITIVES
    equations = equations if equations is not None else FEYNMAN_ALL
    widths = widths if widths is not None else [30, 50, 100]
    memory = memory if memory is not None else DiagnosticMemory()

    from evals.benchmarks.feynman import FEYNMAN_HELDOUT
    from evals.benchmarks.open_ended import (SEED_CURRICULUM, curriculum_recovery_map,
                                             curriculum_progression as _cur_prog, frontier_reach, admit)
    base, rec = _sr_recovery_maps(equations, GROWN_PRIMITIVES, n_samples)
    base_ho, rec_ho = _sr_recovery_maps(FEYNMAN_HELDOUT, GROWN_PRIMITIVES, n_samples)   # HELD-OUT (never designed for)
    cur_map = curriculum_recovery_map(SEED_CURRICULUM)   # SELF-GENERATED, externally certified (own fixed sampling — a fixed benchmark, decoupled from the SR loop's n_samples)
    n_eq = len(equations)
    n_ho = len(FEYNMAN_HELDOUT)
    sr_pool = list(GROWN_PRIMITIVES.keys())

    # ── anti-autoreferentiality gate: every dimension in the MAIN Pareto vector must be EXTERNALLY anchored ──
    from OUTLIER_MCB.landscapes import Landscape, is_external_landscape
    LANDSCAPES = {
        "sr_recovery": Landscape("sr_recovery", "Feynman/SRBench (Udrescu–Tegmark 2020)",
                                 "held-out R²>0.999 + SymPy symbolic equivalence", True, True, True),
        "counterexample": Landscape("counterexample", "number-theory conjectures (n²+n+41, Fermat, …)",
                                    "a concrete counterexample where the predicate is False (verified)", True, True, True),
        "judge_calibration": Landscape("judge_calibration", "labelled adversarial-claim set",
                                       "ground-truth labels (overclaim/valid/dead-route/inside)", True, True, True),
        "external_transfer": Landscape("external_transfer", "HELD-OUT Feynman laws (different physics, same classes)",
                                       "recovery on equations NEVER used to design the primitives", True, True, True),
        "curriculum_progression": Landscape("curriculum_progression",
                                            "SELF-GENERATED SR problems with KNOWN symbolic ground truth (open_ended.py)",
                                            "R²>0.999 + SymPy on held-out samples; scrambled-target negative control",
                                            True, True, True),
        "open_ended_reach": Landscape("open_ended_reach",
                                      "UNBOUNDED self-generated depth-k products (grow product_k on demand)",
                                      "R²>0.999 + SymPy per depth; scrambled-target negative control; minimal-criterion admission",
                                      True, True, True),
    }
    for nm, ls in LANDSCAPES.items():
        assert is_external_landscape(ls), f"dimension '{nm}' is autoreferential (missing {ls.missing()}) — refused"

    from evals.benchmarks.judge_calibration import judge_calibration_rate, DETECTORS as JC_DETECTORS
    _jc_cache: Dict[frozenset, float] = {}

    state = {"primitives": [], "width_idx": 0, "judge_detectors": [], "grown_depths": []}

    def _recovered(s):
        got = set(base)
        for p in s["primitives"]:
            got |= rec.get(p, set())
        return got

    def sr_recovery(s) -> float:
        return round(len(_recovered(s)) / n_eq, 4)

    def counterexample(s) -> float:
        return refutation_rate(widths[s["width_idx"]]).rate

    def judge_calibration(s) -> float:
        key = frozenset(s["judge_detectors"])      # cached by detector-set (judge runs are the slow part)
        if key not in _jc_cache:
            _jc_cache[key] = judge_calibration_rate(tuple(sorted(s["judge_detectors"])))
        return _jc_cache[key]

    def _recovered_ho(s):
        got = set(base_ho)
        for p in s["primitives"]:
            got |= rec_ho.get(p, set())
        return got

    def external_transfer(s) -> float:            # HELD-OUT generalization — the anti-autoreferentiality dimension
        return round(len(_recovered_ho(s)) / n_ho, 4)

    def curriculum_progression(s) -> float:       # SELF-GENERATED increasing-difficulty problems (POET-like, externally settled)
        return _cur_prog(s["primitives"], cur_map)

    def open_ended_reach(s) -> int:               # UNBOUNDED ratchet: deepest externally-certified depth (no 1.0 ceiling)
        return frontier_reach(s["grown_depths"])

    def measure(s) -> Dict[str, float]:
        return {"sr_recovery": sr_recovery(s), "counterexample": counterexample(s),
                "judge_calibration": judge_calibration(s), "external_transfer": external_transfer(s),
                "curriculum_progression": curriculum_progression(s), "open_ended_reach": open_ended_reach(s)}

    def _propose(s, dim, cur):
        """A STRICTLY-improving upgrade for `dim` (skipping ones that would add nothing), or (None, None). Each
        proposal raises its dimension and leaves the others untouched ⇒ the Pareto gate always accepts it."""
        if dim == "sr_recovery":
            have = _recovered(s)
            nxt = next((p for p in sr_pool if p not in s["primitives"] and (rec.get(p, set()) - have)), None)
            if nxt is not None:
                return f"primitive:{nxt}", {**s, "primitives": s["primitives"] + [nxt]}
        elif dim == "counterexample":
            for wi in range(s["width_idx"] + 1, len(widths)):
                if refutation_rate(widths[wi]).rate > cur["counterexample"]:
                    return f"width:{widths[wi]}", {**s, "width_idx": wi}
        elif dim == "judge_calibration":
            for det in JC_DETECTORS:
                if det not in s["judge_detectors"]:
                    trial_dets = tuple(sorted(s["judge_detectors"] + [det]))
                    if judge_calibration_rate(trial_dets) > cur["judge_calibration"]:
                        return f"judge_detector:{det}", {**s, "judge_detectors": s["judge_detectors"] + [det]}
        elif dim == "external_transfer":
            have = _recovered_ho(s)               # a primitive that generalizes to a HELD-OUT (unseen) equation
            nxt = next((p for p in sr_pool if p not in s["primitives"] and (rec_ho.get(p, set()) - have)), None)
            if nxt is not None:
                return f"primitive:{nxt}", {**s, "primitives": s["primitives"] + [nxt]}
        elif dim == "curriculum_progression":
            have = set(s["primitives"])           # unlock the EASIEST not-yet-solved generated rung (climb the frontier)
            for rid in sorted(cur_map, key=lambda r: len(cur_map[r])):
                if cur_map[rid] <= have:
                    continue
                for prim in cur_map[rid]:
                    if prim not in s["primitives"] and prim in sr_pool:
                        trial = {**s, "primitives": s["primitives"] + [prim]}
                        if curriculum_progression(trial) > cur["curriculum_progression"]:
                            return f"primitive:{prim}", trial
        elif dim == "open_ended_reach":
            reach = frontier_reach(s["grown_depths"])   # UNBOUNDED: grow product_{reach+1} on demand (bounded only by compute)
            k = reach + 1
            if reach < reach_budget and admit(k, s["grown_depths"], reach_samples):   # minimal criterion: novel + unsolved-now + externally settleable
                return f"depth:{k}", {**s, "grown_depths": s["grown_depths"] + [k]}
        return None, None

    # open_ended_reach is an UNBOUNDED ratchet (an integer depth, no 1.0 ceiling): it is a real Pareto dimension
    # (monotone, never regresses) but it must NOT enter the [0,1] aggregates — the "weakest skill" min is over the
    # bounded capabilities. Excluding it keeps the aggregate honest while the ratchet still gates against regression.
    UNBOUNDED = {"open_ended_reach"}
    def _bounded(v):
        return [x for k, x in v.items() if k not in UNBOUNDED]

    cur = measure(state)
    result = MultiMetricResult(start_vector=dict(cur), final_vector=dict(cur), memory=memory, patience=patience)
    no_improve_streak = 0
    last_tried: List[str] = []

    for e in range(1, epochs + 1):
        log = DiagnosticLog(task=f"multi_metric_epoch_{e}")
        for d, v in sorted(cur.items()):
            (log.ok if v >= max(_bounded(cur)) or d in UNBOUNDED else log.weak)("metric", f"{d} = {v}")
        # try the WEAKEST dimension first, then the rest (weakest→strongest), for a strictly-improving upgrade
        order = sorted(cur, key=lambda d: (cur[d], d))
        bottleneck = order[0]
        log.bottleneck("performance", f"weakest dimension: {bottleneck} = {cur[bottleneck]}")
        proposed, trial = None, None
        for dim in order:
            proposed, trial = _propose(state, dim, cur)
            if proposed is not None:
                break

        accepted = False
        if proposed is not None:
            last_tried = (last_tried + [proposed])[-patience:]
            new = measure(trial)
            # PARETO GATE — no dimension regresses AND at least one strictly improves (never trade a skill away)
            if pareto_accept(cur, new):
                # AUTOREFERENTIALITY KEY-LOG: an internal skill (sr_recovery) grew but the held-out
                # external_transfer did NOT — the gain may be substrate-specific, not a real generalization.
                if new["sr_recovery"] > cur["sr_recovery"] and new["external_transfer"] <= cur["external_transfer"]:
                    log.weak("autoreferentiality", f"{proposed} raised sr_recovery but NOT held-out transfer "
                             f"({cur['external_transfer']}→{new['external_transfer']}) — gain is substrate-specific, not certified generalization")
                state, cur, accepted = trial, new, True
                result.accepted.append(proposed)
                log.ok("upgrade", f"accepted {proposed}: {result_vector_str(cur)} (no dimension regressed)")
            else:
                log.weak("upgrade", f"rejected {proposed}: would not Pareto-improve")
        else:
            log.bottleneck("performance", "no strictly-improving upgrade left for any dimension (plateau)")

        no_improve_streak = 0 if accepted else no_improve_streak + 1
        agg_min = round(min(_bounded(cur)), 4)
        log.mark_completed(True)
        memory.record(log)
        result.final_vector = dict(cur)
        result.trajectory.append(MultiMetricEpoch(
            epoch=e, bottleneck=bottleneck, proposed=proposed or "(none)", accepted=accepted,
            vector=dict(cur), aggregate_min=agg_min, aggregate_mean=round(sum(_bounded(cur)) / len(_bounded(cur)), 4),
            note=("accepted" if accepted else "plateau/rejected")))

        # EARLY STOP — patience consecutive epochs without an accepted Pareto upgrade ⇒ the ceiling is reached
        if no_improve_streak >= patience:
            result.stopped_early = True
            result.plateau_epochs = no_improve_streak
            result.plateau_report = _plateau_report(bottleneck, cur, last_tried, reach_budget)
            break

    return result


_NEXT_DIMENSIONS = {  # orthogonal certified dimensions to raise the ceiling once the current ones plateau
    "causal_recovery": "edge-orientation accuracy / confounder detection on synthetic data with ground-truth causal structure",
    "materialized_red_green": "a toy repo where the inventor's patch must take a NEW test RED→GREEN without weakening it",
    "prior_art_collision_recall": "an offline deterministic prior-art provider: rename/collage recall",
    "formal_math_settlement": "decidable lemmas settled by z3/exhaustive numeric (false_proof_rate must stay 0)",
    # ── the four CREATIVITY dimensions (invent new universes/meaning/languages/beauty), each externally
    #    verified with a protected honesty invariant; see creative_dimensions() and self_repair.py ──
    "physics_invention": "best emergent-structure score of an INVENTED toy universe (evals/benchmarks/physics_emergence)",
    "conceptual_compression": "MDL compression from self-coined endogenous symbols (evals/benchmarks/compression)",
    "expressive_power": "solution-length gain of an INVENTED formal language over a baseline (evals/benchmarks/expressiveness)",
    "elegance": "objective AST beauty (symmetry/simplicity/surprise) of the artifact (evals/benchmarks/aesthetics)",
}


def creative_dimensions() -> Dict[str, float]:
    """Measure the four externally-verified CREATIVITY dimensions (Points 1–4) as a profile the same Pareto gate
    (pareto_accept) protects — so the loop can raise 'invent new universes / meaning / languages / beauty' without
    ever regressing any of them or any hard dimension. Each value comes from its external benchmark, never a
    self-judged score; each is locked by a protected invariant in self_repair.py."""
    from evals.benchmarks.physics_emergence import physics_invention_score
    from evals.benchmarks.compression import conceptual_compression_score
    from evals.benchmarks.expressiveness import expressive_power_score
    from evals.benchmarks.aesthetics import elegance_dimension_score
    return {
        "physics_invention": round(physics_invention_score(trials=12), 4),
        "conceptual_compression": round(min(1.0, conceptual_compression_score() / 3.0), 4),   # normalise to [0,1]
        "expressive_power": round(min(1.0, expressive_power_score() / 3.0), 4),                # normalise to [0,1]
        "elegance": round(elegance_dimension_score(), 4),
    }


def _plateau_report(weakest: str, vector: Dict[str, float], last_tried: List[str], reach_budget: int = None) -> str:
    nxt = next(iter(_NEXT_DIMENSIONS.items()))
    lines = [
        "## Plateau report — every current dimension is at its certified ceiling",
        f"- weakest dimension: **{weakest}** = {vector[weakest]}  ·  full vector: {result_vector_str(vector)}",
        f"- last upgrades tried (none Pareto-improved): {last_tried or '—'}",
        "- why they did not improve: each remaining upgrade adds no NEW certified recovery on its dimension "
        "(the substrate/detector pool is exhausted) — optimizing weights or inventing an internal score is FORBIDDEN.",
    ]
    if reach_budget is not None and "open_ended_reach" in vector:
        r = vector["open_ended_reach"]
        if r >= reach_budget:
            lines.append(f"- NOTE: `open_ended_reach` = {r} is at the COMPUTE budget (reach_budget={reach_budget}), "
                         "NOT a conceptual ceiling — raise reach_budget and the ratchet keeps climbing (unlimited "
                         "exploration). The bounded [0,1] skills above are what plateaued.")
        else:
            lines.append(f"- NOTE: `open_ended_reach` = {r} stopped BELOW the budget (reach_budget={reach_budget}): it "
                         "hit the zero-dep linear-SR WELL-POSEDNESS limit (base terms ~k²/2 must stay below the sample "
                         "count) — an HONEST substrate/compute ceiling, not a conceptual one. A richer substrate (more "
                         "samples or a non-linear backend) would go deeper; the ratchet mechanism itself has no built-in ceiling.")
    lines += [
        "- to raise the bounded ceiling, add ONE new ORTHOGONAL certified dimension with an external resolver + a "
        f"negative control. Recommended next: **{nxt[0]}** — {nxt[1]}.",
        f"- next RED-FIRST test: `test_{nxt[0]}_starts_below_ceiling` (then `_can_improve_with_certified_upgrade`, "
        "`_negative_control_collapses`, `test_pareto_rejects_regression_in_" + nxt[0] + "`).",
    ]
    return "\n".join(lines)


def result_vector_str(v: Dict[str, float]) -> str:
    return ", ".join(f"{k}={x}" for k, x in sorted(v.items()))


if __name__ == "__main__":   # pragma: no cover
    print(multi_metric_self_improve().markdown())
