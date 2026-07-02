# OUTLIER_MCB eval harness

A deterministic, offline harness that asks a concrete question: **does OUTLIER_MCB produce more
falsifiable, more specific, better-routed proposals than simple baselines** — measured in numbers, not
adjectives.

```bash
python -m evals.run_eval            # the summary table
python -m evals.run_eval --json     # raw JSON
python -m evals.run_eval --mode GSL_FULL
```

## What it measures
Four modes on frozen tasks (`tasks.jsonl`), each scored by deterministic metrics in `[0,1]`:

| mode | what it is |
|---|---|
| `BASE_PROMPT` | a generic proposal, no OUTLIER_MCB (often names a known-bad family) |
| `CHECKLIST_PROMPT` | a manual assumption/test/risk checklist |
| `GSL_PREFLIGHT` | `preflight_creative_request`: routed pack + recommended break + world-test SPEC |
| `GSL_FULL` | `invent` (generative) or `judge` (a human idea), grounded when the task needs a repo |

Metrics (`scorers.py`): `broken_assumption_rate`, `falsifiability_score`, `artifact_specificity`,
`routing_accuracy`, `unique_frontier_ratio`, `rebranding_risk`, `auto_verifiability`, and the composite
`verified_novelty_score` (fixed weights). The headline check: **GSL_FULL beats BASE_PROMPT on mean VNS**.

## What it does NOT measure
- **Not human-judged usefulness.** The scorers measure STRUCTURE (is a proposal falsifiable, specific,
  grounded, correctly routed?), not whether a person finds the idea good. That needs a human or a model.
- **Not "absolute creativity".** A high VNS means *disciplined and grounded*, not *brilliant*. The harness
  cannot tell a deep idea from a well-formed shallow one — only that GSL adds structure a bare prompt lacks.
- **Not an LLM comparison.** `BASE_PROMPT`/`CHECKLIST_PROMPT` are deterministic stand-ins, not a real model.
  Comparing GSL against an actual assistant needs an external LLM, which this offline harness deliberately avoids.
- **Not grounded execution.** `auto_verifiability` rewards a *runnable, full-contract* check; it does not
  run it. Use `OUTLIER_MCB.verify_red_green` for that (and the assistant must first write the test).

## Adding a task
Append a line to `tasks.jsonl` with: `id, domain, prompt, expected_pack, known_bad_families, must_have,
success_oracle` (and optional `idea` for a human-idea-judging task, `needs_repo: true` to ground it).

## Thresholds for 1.0 (the readiness gate)
`python -m OUTLIER_MCB.cli readiness` (or `OUTLIER_MCB.readiness_report()`) is the objective go/no-go.
It declares `GO_READY` only when ALL of these hold — never just because the unit tests pass:

| gate | threshold |
|---|---|
| `GSL_FULL` mean VNS | **> `BASE_PROMPT`** |
| `GSL_FULL` vs `CHECKLIST_PROMPT` VNS | **≥** (not worse) |
| `GSL_FULL` artifact_specificity | **> `BASE_PROMPT`** |
| `GSL_FULL` routing_accuracy | **≥ 0.75** on the included tasks |
| built-in pack_quality (coding, math) | **≥ 0.80** |
| inert operators in `health()` | **none** |
| pyproject + console script + public API | present/valid |
| `pytest -q` | passes (run with `--tests`) |

## Interpreting a regression
If a code change lowers `GSL_FULL`'s mean VNS toward `BASE_PROMPT`, the `tests/test_evals.py` check
fails — that is the point: the engine can no longer *claim* it adds value without showing it. Investigate
which metric dropped (routing? artifact? falsifiability?) and why.
