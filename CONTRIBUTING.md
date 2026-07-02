# Contributing to OUTLIER_MCB

Thanks for your interest. OUTLIER_MCB has one rule above all others:

> **If a change does not move a metric, it is innovation theatre.**

So every contribution is held to the project's own standard: it must keep the readiness gate green and
must not weaken the eval.

## Setup

```bash
pip install -e ".[test]"
python -m pytest -q
```

## Before you open a PR

```bash
python -m pytest -q                              # all tests pass
python -m evals.run_eval                         # GSL_FULL must still beat BASE_PROMPT
python -m OUTLIER_MCB.cli readiness --tests     # must report GO_READY (no blockers)
```

A PR that lowers `GSL_FULL`'s mean Verified Novelty Score toward the baseline, introduces an inert
generative operator (see `health()`), or breaks an artifact contract will fail the gate — by design.

## Principles

- **No new abstractions unless measured.** Prefer wiring existing capabilities over adding modules.
- **Domain knowledge lives in packs only.** The kernel (`kernel.py`) must stay domain-blind; the
  agnosticism test enforces this.
- **Be honest about verification.** Never report an idea as verified that the engine cannot settle
  (`AUTO`) — say `HUMAN` and explain.
- **Add a task, not just code.** A new capability should come with an `evals/tasks.jsonl` task that
  shows the metric it improves.

## Adding a domain pack

Build a `DomainPack` (or fill the scaffold from `elicit_pack`), then check it with `pack_quality(pack)`
before registering it — a weak pack launders weak structure as rigor.
