"""divergence_ab — does the divergent phase actually take a real model out of its mode? A/B + ablation.

Conditions, each asked for K ideas per request:
  A  direct      — one call: "propose K genuinely new ideas" (the model's ordinary answer).
  B  legacy      — llm_openended_search with the single-call path (divergence=False).
  C  divergent   — llm_openended_search with the divergent → convergent phase.
Ablations (measured on the SELECTED INTENTS of one divergent round, to keep the run affordable): the full phase,
and the full phase minus one technique at a time — anti-mode, personas, observations-first, verbalized tail,
denial in the prompt, novelty rejection. Seeds are shared, so every comparison is paired per request.

The yardstick is independent of every condition: per request, the model is asked ONCE (its own call, seed 999)
for its 5 default answers. All conditions are scored against that same mode. Metrics are automatic only — no
model grades creativity (LLM judges favour familiar text):
  tail_rate     share of ideas `mode_distance` classes TAIL against the yardstick (variant threshold
                VARIANT_DISTANCE, the same one the search uses);
  mode_dist     mean distance from each idea to its nearest default answer;
  distinct      ideas left after semantic de-duplication (distance < 0.25 = same idea);
  spread        mean pairwise distance between the ideas;
  n_ideas       ideas the condition actually produced (a filter can return fewer than K);
  calls / secs  cost.
The report gives per-condition means and paired differences with bootstrap 95% intervals over requests. With
12 requests and one model this can show a LARGE effect, not a small one; an ambiguous result means "run more
requests", not "reinterpret".

Results are appended to raw.jsonl one (request, condition) at a time, so an interrupted run resumes where it
stopped:  python -m evals.divergence_ab --llm ollama:qwen3.5:4b --embedder ollama:nomic-embed-text
          python -m evals.divergence_ab --report-only
"""
from __future__ import annotations
import argparse
import dataclasses
import json
import os
import random
import re
import time
from typing import Callable, Dict, List, Optional, Sequence, Tuple

PROMPTS: List[Tuple[str, str]] = [
    ("rate_limit", "invent a new way to rate-limit the clients of an API"),
    ("cdn_cache", "invent a new caching strategy for a content delivery network"),
    ("dedup", "invent a new way to find duplicate records in a large database"),
    ("gpu_sched", "invent a new way to schedule jobs on a GPU cluster"),
    ("noisy_labels", "invent a new loss function for training with noisy labels"),
    ("distinct_count", "invent a new method to estimate the number of distinct elements in a stream"),
    ("ts_compress", "invent a new way to compress time series from sensors"),
    ("matchmaking", "invent a new matchmaking system for online games"),
    ("food_waste", "invent a new way to reduce food waste in supermarkets"),
    ("traffic_lights", "invent a new way to control traffic lights in a city"),
    ("teach_coding", "invent a new way to teach programming to beginners"),
    ("failure_predict", "invent a new method to predict machine failures in a factory"),
]
K = 4
YARDSTICK_SEED = 999
DUPLICATE_DISTANCE = 0.25
CONDITIONS = ("A_direct", "B_legacy", "C_divergent")
NEUTRAL_PERSONA = ("an experienced practitioner in this field",)
ABLATIONS: Dict[str, Dict] = {
    "full": {},
    "no_anti_mode": {"auto_mode": False},
    "no_personas": {"personas": NEUTRAL_PERSONA},
    "no_observations": {"observations_first": False},
    "no_verbalized_tail": {"verbalized_tail": False},
    "no_denial_prompt": {"denial_in_prompt": False},
    "no_novelty_filter": {"novelty_min_distance": 0.0},
}
METRICS = ("tail_rate", "mode_dist", "distinct", "spread", "n_ideas", "calls", "secs")
_COMPARED = ("tail_rate", "mode_dist", "distinct", "spread")

_IDEA_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)])?\s*(?:\*\*)?IDEA(?:\*\*)?\s*[:\-]\s*(?:\*\*)?\s*(?P<m>.+?)\s*$",
                      re.IGNORECASE)


# ── the conditions ──
def direct_prompt(problem: str, k: int = K) -> str:
    return (f"{problem}\nPropose {k} genuinely new ideas, one concrete mechanism each.\n"
            "Format, one per line:\nIDEA: <the mechanism in one or two sentences>")


def parse_direct_ideas(text: str) -> List[str]:
    from OUTLIER_MCB.local_llm import strip_reasoning
    ideas = [m.group("m").strip(" *") for m in map(_IDEA_RE.match, strip_reasoning(text).splitlines()) if m]
    return [i for i in ideas if len(i.split()) >= 3]


def run_direct(problem: str, llm, seed: int) -> Dict:
    from OUTLIER_MCB.llm import call_llm
    outs = call_llm(llm, direct_prompt(problem), temperature=0.8, n=1, seed=seed)
    return {"ideas": parse_direct_ideas(outs[0] if outs else "")[:K], "calls": 1}


def _candidate_ideas(res) -> List[str]:
    return [f"{c.name}: {c.candidate.negation}".strip() for c in res.candidates if not c.evidence.get("rebrand")]


def run_search(problem: str, llm, divergence: bool) -> Dict:
    import OUTLIER_MCB as gsl
    res = gsl.llm_openended_search(problem, llm, budget=K, samples_per_round=K, divergence=divergence)
    extra = {"provider_error": res.provider_error, "mode_echoes_rejected": res.mode_echoes_rejected}
    if divergence:
        dv = res.divergence
        extra.update(intents_generated=dv.get("intents_generated"), intents_selected=dv.get("intents_selected"),
                     rejections=dv.get("rejections"), fallback_rounds=dv.get("fallback_rounds"),
                     sampler=dv.get("sampler"), mode_answers=dv.get("mode_answers"))
    return {"ideas": _candidate_ideas(res), "calls": res.llm_call_count, "extra": extra}


def run_ablation(problem: str, llm, overrides: Dict) -> Dict:
    """One divergent round as the search runs it (same denial set, same seeds), returning the selected intents."""
    from OUTLIER_MCB.pack import select_pack
    from OUTLIER_MCB.generators import breakable
    from OUTLIER_MCB.llm_divergence import (VARIANT_DISTANCE, DivergenceConfig, build_denial_set, diverge_round,
                                            elicit_mode, resolve_sampling)
    pack, _ = select_pack(problem)
    cfg, _report = resolve_sampling(dataclasses.replace(DivergenceConfig(), **overrides), llm)
    calls = 0
    mode_map = None
    if cfg.auto_mode:
        mode_map, calls = elicit_mode(problem, pack, llm, cfg)
    answers = list(mode_map.answers) if mode_map is not None else []
    denial = build_denial_set(pack, mode_answers=answers)
    rnd = diverge_round(problem, pack, llm, cfg, denial, round_index=0, k=K, mode_map=mode_map,
                        mode_near=VARIANT_DISTANCE,           # the mode filter is anti-mode's, not novelty's
                        assumptions=[a.name for a in breakable(pack)])
    rejected: Dict[str, int] = {}
    for it in rnd.intents:
        if it.status.startswith("REJECTED_"):
            rejected[it.status] = rejected.get(it.status, 0) + 1
    return {"ideas": [it.mechanism for it in rnd.selected], "calls": calls + rnd.calls,
            "extra": {"intents_generated": len(rnd.intents), "rejected": rejected}}


def yardstick(problem: str, llm) -> Dict:
    """The model's own default answers, elicited once per request with a seed no condition uses."""
    from OUTLIER_MCB.pack import select_pack
    from OUTLIER_MCB.llm_divergence import DivergenceConfig, elicit_mode
    pack, _ = select_pack(problem)
    mode_map, calls = elicit_mode(problem, pack, llm, DivergenceConfig(seed=YARDSTICK_SEED))
    return {"ideas": list(mode_map.answers) if mode_map is not None else [], "calls": calls,
            "extra": {"probabilities": list(mode_map.probabilities) if mode_map is not None else []}}


# ── metrics ──
def distinct_count(ideas: Sequence[str], threshold: float = DUPLICATE_DISTANCE, embedder=None) -> int:
    from OUTLIER_MCB.embeddings import semantic_distance
    kept: List[str] = []
    for idea in ideas:
        if all(semantic_distance(idea, k, embedder=embedder) >= threshold for k in kept):
            kept.append(idea)
    return len(kept)


def idea_metrics(problem: str, ideas: Sequence[str], defaults: Sequence[str], embedder=None) -> Dict:
    from OUTLIER_MCB.embeddings import semantic_distance
    from OUTLIER_MCB.llm_divergence import VARIANT_DISTANCE, mean_pairwise_distance
    from OUTLIER_MCB.mode_box import declare_mode, mode_distance, TAIL
    ideas = [i for i in ideas if str(i).strip()]
    out: Dict = {"n_ideas": len(ideas), "distinct": distinct_count(ideas, embedder=embedder),
                 "spread": mean_pairwise_distance(ideas, embedder=embedder)}
    if not ideas or not defaults:
        out.update(tail_rate=None, mode_dist=None)
        return out
    mode = declare_mode(problem, list(defaults))
    near = VARIANT_DISTANCE
    out["tail_rate"] = round(sum(mode_distance(i, mode, embedder=embedder, near=near).verdict == TAIL
                                 for i in ideas) / len(ideas), 4)
    out["mode_dist"] = round(sum(min(semantic_distance(i, d, embedder=embedder) for d in defaults)
                                 for i in ideas) / len(ideas), 4)
    return out


# ── persistence + the run loop ──
def _load(path: str) -> List[Dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _append(path: str, row: Dict) -> None:
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def run(llm, out_dir: str, prompts: Sequence[Tuple[str, str]] = PROMPTS, conditions: Sequence[str] = CONDITIONS,
        ablations: Sequence[str] = tuple(ABLATIONS), log: Callable[[str], None] = print) -> List[Dict]:
    """Run every missing (request, condition) and append it to <out_dir>/raw.jsonl. Already-recorded pairs are
    skipped, so calling this again resumes an interrupted run."""
    os.makedirs(out_dir, exist_ok=True)
    raw_path = os.path.join(out_dir, "raw.jsonl")
    done = {(r["prompt_id"], r["condition"]) for r in _load(raw_path)}
    by_condition: Dict[str, Callable[[int, str], Dict]] = {
        "A_direct": lambda seed, p: run_direct(p, llm, seed),
        "B_legacy": lambda seed, p: run_search(p, llm, divergence=False),
        "C_divergent": lambda seed, p: run_search(p, llm, divergence=True)}
    jobs: List[Tuple[str, Callable[[int, str], Dict]]] = [("yardstick", lambda seed, p: yardstick(p, llm))]
    jobs += [(c, by_condition[c]) for c in conditions]
    jobs += [(f"abl_{name}", (lambda ov: lambda seed, p: run_ablation(p, llm, ov))(ABLATIONS[name]))
             for name in ablations]
    for index, (pid, problem) in enumerate(prompts):
        for cond, fn in jobs:
            if (pid, cond) in done:
                continue
            t0 = time.perf_counter()
            result = fn(100 + index, problem)
            row = {"prompt_id": pid, "problem": problem, "condition": cond, "ideas": result["ideas"],
                   "calls": result["calls"], "secs": round(time.perf_counter() - t0, 1),
                   "extra": result.get("extra", {}),
                   "provider_error": getattr(llm, "last_error", "") or ""}
            _append(raw_path, row)
            log(f"[{pid}] {cond}: {len(row['ideas'])} ideas, {row['calls']} calls, {row['secs']}s")
    return _load(raw_path)


# ── aggregation ──
def bootstrap_ci(values: Sequence[float], iters: int = 2000, seed: int = 0) -> Tuple[Optional[float], ...]:
    """(mean, low, high) of the mean with a 95% percentile bootstrap; (None, None, None) without data."""
    vals = [float(v) for v in values if v is not None]
    if not vals:
        return (None, None, None)
    rng = random.Random(seed)
    means = sorted(sum(rng.choice(vals) for _ in vals) / len(vals) for _ in range(iters))
    return (round(sum(vals) / len(vals), 4), round(means[int(0.025 * iters)], 4), round(means[int(0.975 * iters)], 4))


def score_rows(rows: Sequence[Dict], embedder=None) -> Dict[str, Dict[str, Dict]]:
    """{condition: {prompt_id: metrics}} — every condition scored against that request's yardstick."""
    defaults = {r["prompt_id"]: r["ideas"] for r in rows if r["condition"] == "yardstick"}
    scored: Dict[str, Dict[str, Dict]] = {}
    for r in rows:
        if r["condition"] == "yardstick":
            continue
        m = idea_metrics(r["problem"], r["ideas"], defaults.get(r["prompt_id"], []), embedder=embedder)
        m.update(calls=r["calls"], secs=r["secs"])
        scored.setdefault(r["condition"], {})[r["prompt_id"]] = m
    return scored


def summarize(scored: Dict[str, Dict[str, Dict]]) -> Dict:
    def paired(a: str, b: str, metric: str):
        if a not in scored or b not in scored:
            return (None, None, None), 0
        common = [p for p in scored[a] if p in scored[b]
                  and scored[a][p].get(metric) is not None and scored[b][p].get(metric) is not None]
        return bootstrap_ci([scored[a][p][metric] - scored[b][p][metric] for p in common]), len(common)
    summary: Dict = {"conditions": {}, "comparisons": {}, "ablations": {}}
    for cond, per_prompt in scored.items():
        summary["conditions"][cond] = {m: bootstrap_ci([v.get(m) for v in per_prompt.values()]) for m in METRICS}
        summary["conditions"][cond]["n_requests"] = len(per_prompt)
    for a, b in (("C_divergent", "A_direct"), ("C_divergent", "B_legacy"), ("B_legacy", "A_direct")):
        summary["comparisons"][f"{a} - {b}"] = {m: paired(a, b, m)[0] for m in _COMPARED}
    for name in ABLATIONS:
        if name != "full":
            summary["ablations"][f"full - {name}"] = {m: paired("abl_full", f"abl_{name}", m)[0] for m in _COMPARED}
    return summary


def _fmt(ci) -> str:
    mean, lo, hi = ci
    return "—" if mean is None else f"{mean:.3f} [{lo:.3f}, {hi:.3f}]"


def markdown(summary: Dict, meta: Dict) -> str:
    L = ["# Divergent phase — A/B and ablation", "",
         f"- model: `{meta.get('llm')}` · embedder: `{meta.get('embedder')}` · K={K} ideas per condition",
         f"- requests: {meta.get('n_requests')} · yardstick: the model's own 5 default answers (seed "
         f"{YARDSTICK_SEED}, a call no condition shares)",
         "- values: mean over requests [bootstrap 95% interval]; differences are paired per request", "",
         "## Conditions", "",
         "| condition | n | tail_rate ↑ | mode_dist ↑ | distinct ↑ | spread ↑ | n_ideas | calls | secs |",
         "|---|---|---|---|---|---|---|---|---|"]
    for cond in [c for c in (*CONDITIONS, *(f"abl_{a}" for a in ABLATIONS)) if c in summary["conditions"]]:
        s = summary["conditions"][cond]
        L.append(f"| {cond} | {s['n_requests']} | " + " | ".join(_fmt(s[m]) for m in METRICS) + " |")
    compared = _COMPARED
    sections = (("Paired comparisons", "comparisons"),
                ("Ablations (full minus variant: > 0 means the technique helps)", "ablations"))
    for title, block in sections:
        L += ["", f"## {title}", "", "| difference | " + " | ".join(compared) + " |", "|---|---|---|---|---|"]
        for name, vals in summary[block].items():
            L.append(f"| {name} | " + " | ".join(_fmt(vals[m]) for m in compared) + " |")
    L += ["", "An interval that contains 0 is not evidence of an effect in either direction."]
    return "\n".join(L)


def report(out_dir: str, embedder=None, meta: Optional[Dict] = None) -> Dict:
    rows = _load(os.path.join(out_dir, "raw.jsonl"))
    meta = dict(meta or {})
    meta_path = os.path.join(out_dir, "meta.json")
    if os.path.exists(meta_path):
        with open(meta_path, encoding="utf-8") as fh:
            meta = {**json.load(fh), **meta}
    meta["n_requests"] = len({r["prompt_id"] for r in rows})
    summary = summarize(score_rows(rows, embedder=embedder))
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump({"meta": meta, **summary}, fh, indent=1)
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as fh:
        fh.write(markdown(summary, meta) + "\n")
    return {"meta": meta, **summary}


def main(argv: Optional[Sequence[str]] = None) -> None:
    import OUTLIER_MCB as gsl
    from OUTLIER_MCB.llm import _llm_from_spec
    from OUTLIER_MCB.embeddings import _build_from_spec
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--llm", default="ollama:qwen3.5:4b")
    ap.add_argument("--embedder", default="ollama:nomic-embed-text")
    ap.add_argument("--out", default=os.path.join("evals", "reports", "divergence_ab"))
    ap.add_argument("--max-tokens", type=int, default=3000, dest="max_tokens")
    ap.add_argument("--report-only", action="store_true", dest="report_only")
    a = ap.parse_args(argv)
    embedder = _build_from_spec(a.embedder)
    if embedder is None:
        raise SystemExit(f"embedder {a.embedder!r} unavailable — the metrics need a semantic distance")
    gsl.set_default_embedder(embedder)
    meta = {"llm": a.llm, "embedder": a.embedder, "max_tokens": a.max_tokens}
    os.makedirs(a.out, exist_ok=True)
    if not a.report_only:
        llm = _llm_from_spec(a.llm)
        if llm is None:
            raise SystemExit(f"unrecognised --llm spec {a.llm!r}")
        if hasattr(llm, "max_tokens") and a.max_tokens:
            llm.max_tokens = a.max_tokens
        with open(os.path.join(a.out, "meta.json"), "w", encoding="utf-8") as fh:
            json.dump(meta, fh, indent=1)
        run(llm, a.out)
    result = report(a.out, embedder=embedder, meta=meta)
    print(markdown(result, result["meta"]))


if __name__ == "__main__":
    main()
