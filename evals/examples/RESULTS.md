# Model-in-the-loop result (assistant-in-the-loop, no API)

The deterministic baselines prove OUTLIER_MCB beats a fixed stand-in. This is the first result with
the REAL model already in the editor (Claude in VS Code) answering, scored by the offline scorers.

## How it was produced (reproducible)
```
python -m evals.llm_benchmark --emit prompts.json     # writes per-task, per-arm prompts
#   the assistant answers each prompt BLIND (not told which arm wins), answers saved as completions
python -m evals.llm_benchmark --score evals/examples/completions_blind_10task.json
```

## Result — 10 generative tasks, blind, mean scores
| arm | VNS | RVNS | falsifiability | artifact_specificity |
|-----|-----|------|----------------|----------------------|
| llm_only       | 0.431 | 0.431 | 0.125 | 0.260 |
| llm_checklist  | 0.542 | 0.472 | 0.300 | 0.320 |
| llm_greenstar  | 0.567 | 0.567 | 0.375 | 0.380 |

The OUTLIER_MCB brief made the real model write a more falsifiable, less box-bound answer:
VNS +0.136 over the bare prompt, falsifiability 3x. Per task, greenstar beats bare on VNS in 5/10.

## Honest caveats
- The answers were produced by one assistant, so there is author bias; the SCORING is deterministic
  and the falsifiability gain is driven by the brief eliciting a world-test / baseline / negative control.
- The margin is real but modest: a strong model already answers competently from the bare prompt.
- These scorers measure STRUCTURE (falsifiable / distinct / grounded / honest), not human-judged value.
- To remove author bias entirely, run --emit, have the model answer each prompt in a fresh context,
  and --score. The harness never fabricates answers (it refuses without a real model).

---

# Bias-reduced rerun (independent blind subagents) — the honest number

The result above used answers written by ONE assistant aware of the experiment (author bias). We reran it
with THREE independent subagents, each answering only one arm, none told about the comparison or about
OUTLIER_MCB. The only difference between arms is the prompt (the treatment).

## Result — 10 generative tasks, blind subagents, mean scores
| arm | VNS | RVNS | falsifiability | artifact | rebranding_risk |
|-----|-----|------|----------------|----------|-----------------|
| llm_only       | 0.550 | 0.550 | 0.175 | 0.300 | 0.00 |
| llm_checklist  | 0.575 | 0.526 | 0.325 | 0.340 | 0.00 |
| llm_greenstar  | 0.571 | 0.532 | 0.375 | 0.380 | 0.20 |

## How much does the library add (bias-reduced)
- Composite VNS vs a bare prompt: **+4%** (0.550 -> 0.571) — within noise.
- Composite VNS vs a 4-line checklist: **-1%** (0.575 -> 0.571) — no gain.
- Falsifiability vs bare: **+114%** (0.175 -> 0.375) — the one robust, large effect.
- Falsifiability vs checklist: **+15%** (0.325 -> 0.375) — small but real.
- Per-task VNS wins: greenstar>bare 4/10; greenstar>checklist 2/10.

## What changed when we removed author bias
The biased run reported VNS +32% over bare; bias-reduced it is +4%. Most of the apparent gain was the
author writing weaker bare answers — a fresh agent's bare answer is much stronger (VNS 0.431 -> 0.550).
The HONEST conclusion: on a structural composite, OUTLIER_MCB adds ~nothing over a good prompt or a
checklist; its one measurable, robust contribution is making the model's answer markedly more FALSIFIABLE
(it states a world-test / baseline / negative control it otherwise omits): ~2x vs a bare prompt, +15% vs a
checklist. RVNS even sits slightly below bare because the briefed answers named known families (a small
honesty penalty). This is a structural proxy, n=10, single run — not a measure of human-judged value.

---

# Lever: the brief demands a red-first artifact contract (v1.5.1)

After the bias-reduced run showed the library adds ~0% on the composite but real falsifiability, we made the
OUTLIER_MCB brief (instruction_emitter point 7b) ask the model for a NAMED, currently-red, selectable test
(test id + target + baseline + negative control + exact `pytest -k` command), and made the benchmark's
materialization scorer text-aware. We then regenerated ONLY the greenstar arm with the new brief (the
llm_only / llm_checklist answers are byte-identical to the bias-reduced run, so the comparison is clean).

## Result — 10 tasks, blind subagents, only the greenstar prompt changed
| arm | VNS | falsifiability | materialization | artifact_specificity |
|-----|-----|----------------|-----------------|----------------------|
| llm_only                | 0.521 | 0.175 | 0.075 | 0.140 |
| llm_checklist           | 0.560 | 0.325 | 0.200 | 0.260 |
| greenstar (old brief)   | 0.557 | 0.375 | 0.175 | 0.300 |
| greenstar (NEW brief 7b)| 0.560 | 0.325 | **0.400** | **0.520** |

The brief change (old -> new greenstar) lifted materialization +129% (0.175 -> 0.400) and artifact_specificity
+73% (0.300 -> 0.520): the real model now writes a concrete, selectable, red-first test contract it otherwise
omits. greenstar now beats a 4-line checklist ~2x on both — a gain a plain checklist does NOT give. VNS is
flat (materialization is not in the VNS composite) and falsifiability wobbled within noise. Eval-side, the
matching Lever 1 (`-k` selects the test in every pytest contract) raised GSL_FULL materialization 0.25 -> 0.33.

---

# Does the open-ended layer help a REAL model? (diverge-brief vs freeform-N, blind)

Question: does giving the model OUTLIER_MCB's `diverge()` brief (6 distinct assumptions to break, across
Boden categories) make it produce a better SET of approaches than just asking "give me 6 different ideas"?
Two blind subagents, 4 design/theory problems, 6 approaches each. Scored on the model's own text.

| measure | freeform-6 | diverge-brief-6 |
|---|---|---|
| lexical set spread (mean pairwise distance) | 0.925 | 0.919 (−1%) |
| originality (closest pair distance) | 0.879 | 0.861 (−2%) |
| **distinct assumptions/axes covered per set** | **1.00** | **2.25 (2.25×)** |

## Honest two-sided conclusion
- On **lexical diversity**, the layer does NOT help: a strong model asked for "6 genuinely different ideas"
  is already near the diversity ceiling (~0.92); the brief is a wash (−1%).
- On **structural coverage**, the layer DOES help: freeform answers cluster on ~1 assumption, the diverge
  brief spreads them across 2.25× more distinct assumptions/axes. This is partly the instruction working as
  designed (it told the model to break different assumptions), not an emergent surprise — but it is a real,
  measured effect, and it is exactly what Quality-Diversity is FOR: stop the model clustering on one cell.
- Caveat: axis-mapping uses fragile lexical inference over the pack's known axes; freeform ideas that break
  an axis outside the pack vocabulary map to 0. The number is a relative signal, not human-judged value.

Takeaway: the open-ended layer's value is **breadth of structural coverage**, not lexier text — and that is
the honest claim to make, not "more creative".
