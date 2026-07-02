"""evals.llm_benchmark — the model-in-the-loop benchmark (the first genuinely interesting result).

The deterministic baselines in `baselines.py` prove OUTLIER_MCB beats a *fixed stand-in*. They CANNOT
prove it beats a real model answering without the library — they are not a model. This harness closes that
gap. It runs three arms over the same tasks, scored by the SAME scorers, so the comparison is apples-to-apples:

    llm_only       — the model answers the bare prompt (the real floor).
    llm_checklist  — the model answers with a manual assumption/test/risk checklist prepended (structure only).
    llm_greenstar  — the model answers with the OUTLIER_MCB preflight brief prepended, AND its free-text
                     answer is disciplined by judge() into a scored, falsifiable output.

It is NOT run in CI: it needs a real model. You inject one as an `LLMProvider` — any callable
`str -> str` wrapping Claude / GPT / a local model. With no provider the harness refuses (it never fakes a
model result). A tiny deterministic `FakeLLM` exists ONLY to self-test the plumbing offline.

    from evals.llm_benchmark import run_llm_benchmark
    def my_llm(prompt: str) -> str: ...        # call your real model here
    print(run_llm_benchmark(my_llm))           # mean scores per arm, same scorers as the offline eval
"""
from __future__ import annotations
from typing import Callable, Dict, List, Optional

LLMProvider = Callable[[str], str]   # prompt -> completion

CHECKLIST_PREFIX = (
    "Before answering, fill this checklist explicitly:\n"
    "- Assumption you are breaking:\n- World-test that could falsify your idea:\n"
    "- Known family it must beat:\n- The maximum claim you are allowed to make:\n\nNow answer: ")


def _present(text: str, *markers: str) -> bool:
    """Did the model's OWN answer state this (a world-test, a negative control, a baseline)? The benchmark
    must credit what the ANSWER contains, not what the repo could always supply — otherwise every arm ties."""
    t = (text or "").lower()
    return any(m in t for m in markers)


def _standardize(mode: str, task: dict, completion: str, repo_path: Optional[str]) -> Dict:
    """Map a model's free-text answer into the standardized scorer schema. TEXT-AWARE on purpose: judge()
    still infers the broken assumption / verdict / verifiability and the repo supplies the runnable command,
    but the falsifiability-bearing fields (world-test, baseline, negative control) are only granted when the
    ANSWER ITSELF states them — so a brief that makes the model write a falsifiable answer actually scores
    higher than one that does not."""
    import OUTLIER_MCB as gsl
    from evals.baselines import _std, _contract, _materialization
    rp = repo_path if task.get("needs_repo") else None
    repo = gsl.probe(rp) if rp else None
    provider = gsl.CallableProvider(lambda q, _m=task.get("prior_art"): {"matches": _m}) if task.get("prior_art") else None
    j = gsl.judge(completion, prompt=task["prompt"], repo_path=rp, provider=provider)
    pack = gsl.select_pack(task["prompt"])[0]
    axis = pack.dimension_of.get(j.broken_assumption or "", "")
    check = gsl.compile_world_test(completion, axis, repo=repo)

    # the answer only EARNS each falsifiability field if it actually stated it
    has_world_test = _present(completion, "world-test", "world test", "construct", "build a ", "counterexample")
    has_negative = _present(completion, "negative control", "shuffle", "collapse", "reduce to", "reduces to", "baseline")
    has_baseline = _present(completion, "must beat", "fails", "diverges", "today", "current", "starv", "wasted", "over-admit")
    contract = _contract(check)
    if not has_negative:
        contract["negative_control"] = ""
    if not has_baseline:
        contract["baseline_assertion"] = ""

    # RED-FIRST MATERIALIZATION, text-aware: an answer earns materialization only if it named a concrete,
    # selectable, currently-red test of its own — a `test_...` id plus a `pytest -k`-style command. This is
    # what the OUTLIER_MCB brief (point 7b) now explicitly asks for, so a more runnable answer scores higher.
    import re
    m = re.search(r"\btest_[a-z0-9_]{3,}", completion)
    stated_test = m.group(0) if m else ""
    mentions_cmd = bool(re.search(r"pytest|-k\b|\bcommand\b|`[^`]*test[^`]*`", completion, re.I))
    if stated_test:
        contract["test_name"] = stated_test
        contract["command"] = f"{repo.test_command} -k {stated_test}" if repo else f"pytest -k {stated_test}"
        contract["target"] = (check.target if (has_world_test or repo) else contract.get("target", ""))
    elif not mentions_cmd:
        contract["test_name"] = ""           # no named test and no command → not materialized
        contract["command"] = ""
        contract["target"] = "" if not has_world_test else contract.get("target", "")
    materialization = gsl.materialization_score(contract, repo.root) if repo else 0.0
    return _std(mode, task, text=completion, pack=pack.name, broken_assumption=j.broken_assumption or "",
                world_test=(check.success_condition if has_world_test else ""),
                negative_control=(check.negative_control if has_negative else ""),
                artifact_contract=contract, verifiability=j.verifiability,
                score_components={"verdict": j.verdict, "novelty": (j.novelty.status if j.novelty else None),
                                  "materialization_score": materialization})


def _prompt_for(arm: str, task: dict) -> str:
    base = task["prompt"]
    if arm == "llm_checklist":
        return CHECKLIST_PREFIX + base
    if arm == "llm_greenstar":
        import OUTLIER_MCB as gsl
        return gsl.creative(base) + "\n\nNow answer the request, obeying the brief above:\n" + base
    return base


ARMS = ("llm_only", "llm_checklist", "llm_greenstar")


def run_llm_benchmark(llm: LLMProvider, tasks: Optional[List[dict]] = None,
                      repo_path: Optional[str] = None) -> Dict:
    """Run the three arms over `tasks` with a REAL model `llm`, scored by the offline scorers. Returns
    {summary: {arm: {metric: mean}}, rows: [...]}. Raises if no model is supplied — it never fakes one."""
    if llm is None:
        raise ValueError("run_llm_benchmark needs a real LLMProvider (str->str). It will not fake a model.")
    from pathlib import Path
    from evals.run_eval import load_tasks
    from evals.scorers import score_output, primary_score
    tasks = tasks if tasks is not None else load_tasks()
    repo_path = repo_path or str(Path(__file__).resolve().parent.parent)
    rows, agg = [], {a: {} for a in ARMS}
    for task in tasks:
        for arm in ARMS:
            completion = llm(_prompt_for(arm, task))
            out = _standardize(arm, task, completion, repo_path)
            scores = score_output(out, task)
            scores["primary_score"] = primary_score(out, task)
            rows.append({"task": task["id"], "arm": arm, **scores})
            for k, v in scores.items():
                agg[arm].setdefault(k, []).append(v)
    summary = {a: {k: round(sum(v) / len(v), 3) for k, v in m.items()} for a, m in agg.items()}
    return {"summary": summary, "rows": rows, "n_tasks": len(tasks),
            "note": "model-in-the-loop result. The OUTLIER_MCB arm both PROMPTS and DISCIPLINES (judge) the answer."}


def emit_prompts(out_path: str, tasks: Optional[List[dict]] = None, repo_path: Optional[str] = None) -> Dict:
    """ASSISTANT-IN-THE-LOOP, no API key needed: write the per-task, per-arm prompts to a JSON file. The
    real model already in your editor (Claude in VS Code) answers them, you save the answers next to each
    prompt, then call `score_completions`. This validates the library with the SAME model you actually use."""
    import json
    from pathlib import Path
    from evals.run_eval import load_tasks
    tasks = tasks if tasks is not None else load_tasks()
    work = {t["id"]: {arm: _prompt_for(arm, t) for arm in ARMS} for t in tasks}
    Path(out_path).write_text(json.dumps(
        {"_instructions": "Answer EACH prompt below as you normally would, genuinely — do NOT try to make any "
                          "arm win. Replace each prompt string with your answer, keep the keys, save, then run "
                          "score_completions on this file.", "completions": work}, indent=2))
    return work


def score_completions(completions, tasks: Optional[List[dict]] = None, repo_path: Optional[str] = None) -> Dict:
    """Score answers produced by the real assistant. `completions` is a path to (or a dict of) the filled
    file: {task_id: {arm: answer}}. Same scorers as the offline eval — a true model-in-the-loop result."""
    import json
    from pathlib import Path
    from evals.run_eval import load_tasks
    from evals.scorers import score_output, primary_score
    if isinstance(completions, str):
        data = json.loads(Path(completions).read_text())
        completions = data.get("completions", data)
    tasks = {t["id"]: t for t in (tasks if tasks is not None else load_tasks())}
    repo_path = repo_path or str(Path(__file__).resolve().parent.parent)
    rows, agg = [], {a: {} for a in ARMS}
    for tid, by_arm in completions.items():
        task = tasks.get(tid)
        if task is None:
            continue
        for arm, answer in by_arm.items():
            if arm not in ARMS:
                continue
            out = _standardize(arm, task, answer, repo_path)
            scores = score_output(out, task)
            scores["primary_score"] = primary_score(out, task)
            rows.append({"task": tid, "arm": arm, **scores})
            for k, v in scores.items():
                agg[arm].setdefault(k, []).append(v)
    summary = {a: {k: round(sum(v) / len(v), 3) for k, v in m.items()} for a, m in agg.items() if m}
    return {"summary": summary, "rows": rows, "n_tasks": len(completions),
            "note": "ASSISTANT-IN-THE-LOOP: answers came from the real model in the editor, scored by the offline scorers."}


class FakeLLM:
    """A deterministic stand-in used ONLY to self-test the harness offline. It is NOT a real result: it
    echoes the request with a fixed twist, so the plumbing (prompt → completion → judge → score) is exercised
    without a network call. Do not read anything into its numbers."""
    def __call__(self, prompt: str) -> str:
        tail = prompt.strip().splitlines()[-1]
        return f"measure the request stream by its cost instead of by the time window, for: {tail}"


def _print_summary(result: Dict) -> None:
    cols = ["primary_score", "verified_novelty_score", "robust_verified_novelty_score",
            "falsifiability_score", "rebranding_risk", "anti_gaming_score"]
    print(f"{'ARM':<16}" + "".join(f"{c.split('_')[0][:8]:<10}" for c in cols))
    for arm, m in result["summary"].items():
        print(f"{arm:<16}" + "".join(f"{m.get(c, 0.0):<10.3f}" for c in cols))
    print("\n" + result.get("note", ""))


def main(argv=None):
    """Assistant-in-the-loop CLI — validate the library with the model already in your editor, no API key.

        python -m evals.llm_benchmark --emit prompts.json     # 1. write the prompts
        #   2. answer each prompt in VS Code, paste answers over the prompt strings, save as completions.json
        python -m evals.llm_benchmark --score completions.json # 3. score your real answers
    """
    import argparse
    ap = argparse.ArgumentParser(prog="evals.llm_benchmark", description=main.__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--emit", metavar="PATH", help="write the per-task, per-arm prompts to PATH for you to answer")
    g.add_argument("--score", metavar="PATH", help="score a filled completions file (the real model's answers)")
    g.add_argument("--selftest", action="store_true", help="run the plumbing offline with a deterministic FakeLLM")
    ap.add_argument("--task", action="append", help="restrict to these task ids (repeatable)")
    args = ap.parse_args(argv)
    from evals.run_eval import load_tasks
    tasks = [t for t in load_tasks() if (not args.task or t["id"] in args.task)]
    if args.emit:
        emit_prompts(args.emit, tasks=tasks)
        print(f"wrote {len(tasks)} tasks × {len(ARMS)} arms to {args.emit}. Answer each prompt, then "
              f"--score it.")
    elif args.score:
        _print_summary(score_completions(args.score, tasks=tasks))
    else:
        _print_summary(run_llm_benchmark(FakeLLM(), tasks=tasks))


if __name__ == "__main__":
    main()
