# Working in OUTLIER_MCB — OUTLIER_MCB is ON

This repo contains **OUTLIER_MCB**, a domain-agnostic assumption-negation + falsification engine.
It exists so that when the user asks for something *new*, you do NOT answer from the average of your
training memory — you break a hidden assumption and let falsification certify the novelty.

> **STANDING ROUTINE (one call).** On any new/novel/invent/discover request, run
> `python -c "import OUTLIER_MCB as m; print(m.assistant_brief('''<request>'''))"` and obey it; or the full
> loop `m.explore('<request>', evaluator=…, prior_art_provider=…, llm=…)` (math: `m.explore(q, math_claim=…,
> math_variables=…)` → z3/lean decides). Provider-agnostic rules live in [AGENTS.md](AGENTS.md) /
> [.cursorrules](.cursorrules). Never claim "absolute novelty" without online prior-art + a passing verifier.
> For continuous use after the first activation, run
> `python -m OUTLIER_MCB route --problem "<request>" --json` each turn and follow `activate`, `entrypoint`,
> and `next_call`. This contract is bilingual: English + Italian / inglese + italiano.

## AUTO-ACTIVATION (do this without being asked)

When the user's request contains any **creativity trigger** — in any language —
(`inventa, nuovo, originale, mai visto, non ovvio, fuori dagli schemi, ripensa, da zero,
new, novel, invent, rethink, from scratch, breakthrough, a better/different way`):

**BEFORE writing your answer**, run:
```bash
python -c "import OUTLIER_MCB as gsl; print(gsl.creative('''<the user's request>'''))"
```
Read the printed brief and **obey it** while you answer. It tells you: the box you must NOT
re-propose, the assumptions to break, the branches in tension, the world-test that would kill each
idea, and the maximum claim you are allowed to make.

If the brief says **elicitation required** (unknown domain): do NOT fake an answer, and do NOT just give
up either. **Research the domain in real time** — search the web, GitHub, and publications for the known
approaches (the "families") and cite them — then hand that to the engine so it sources the domain instead
of refusing. You are the research provider:
```python
def research(prompt):
    # YOU do the web/GitHub/paper search here and return REAL findings with citations
    return {"known_families": [...], "box_name": "...", "sources": [{"title": "...", "url": "..."}]}
print(gsl.creative(request, provider=gsl.CallableProvider(research)))
```
The result is a PROVISIONAL pack: families from real sources, assumptions from first principles, still
falsified by the engine — never presented as authoritative. With no sources it raises (no fabrication).
If you prefer to fill the scaffold by hand: `pack = gsl.pack_from_spec(filled_spec); gsl.creative(request, pack=pack)`.

For a **deep push toward genuinely new ideas** (a portfolio of unknowns, each with an executable
repo-settled bet), use the cognitive runtime instead of a single answer:
```bash
python -c "import OUTLIER_MCB as gsl; print(gsl.invent('''<the user's request>''').markdown())"
```
`invent()` maximizes **box_distance × survives_falsification** (not accuracy): it searches for the ideas
*farthest* from the average answer, settles each by a real repo check (a test that must flip, a type, a
benchmark), and turns a losing bet into the next assumption to break. The objective is to leave the
training distribution, disciplined by falsification — never to produce the most-probable answer.

## Then DISCIPLINE YOUR OWN idea (close the loop)

`creative()` tells you which assumption to break — the spark is still yours. Once YOU have a concrete
idea, run the rigor on IT before proposing it:
```bash
python -c "import OUTLIER_MCB as gsl; print(gsl.judge('''<your concrete idea>''', prompt='''<the request>''', repo_path='.').markdown())"
```
`judge()` returns a verdict: **INSIDE_THE_BOX** (it breaks no assumption → do not propose it as new) or
**MUST_BE_AUDITED** (it breaks a real assumption → here is its theorem, world-test, reviewer objection,
maturity, and whether the repo can settle it AUTO or only a HUMAN can). The spark is yours; the rigor is
the machine's — applied to YOUR idea, not a canned one.

## Then CHECK IT IS ACTUALLY NEW (search the real world)

Breaking an assumption is not enough — the idea might already exist, renamed or recombined. Before you
present anything as new, search the web / GitHub / publications for prior art and let the engine classify:
```python
def search(idea):   # YOU do the real web search and return what exists, with citations
    return {"matches": [{"title": "...", "url": "...", "summary": "..."}]}   # or {"sources": [...]}
print(gsl.novelty_audit("<your idea>", gsl.CallableProvider(search)).markdown())
# RENAMED (a close match → not new) · COLLAGE (covered by a union of works → a new name, not a new mechanism)
# · NO_PRIOR_ART_FOUND (PROVISIONAL — absence is not proof; to be genuinely new, EXTRAPOLATE beyond it: green_star)
```
This is the point of the whole library: it is not the loss function (the average of the known) that
should guide you, but the drive to invent BEYOND it. `NO_PRIOR_ART_FOUND` is the START of novelty work,
not the end — push into the green-star zone until the idea is something the searched world does not contain.

## The contract for your answer (non-negotiable)
1. Never propose a standard mechanism from memory until you can name the **assumption it breaks**.
2. Anything that stays inside the domain's box → label it `INSIDE_THE_BOX`; it is not an answer.
3. Give **≥3 branches in tension**, each breaking a *different* axis.
4. For the chosen branch state: broken assumption · the world-test that would kill it · the known
   family it must beat · the **max claim allowed** (no "paradigm" without a demonstrated separation).
5. If the brief flags `data_insufficient`: say so — a new combination cannot raise the ceiling; name
   the new information required.

## Why this exists (the spark stays human, the rigor is the machine's)
The library does not invent the idea for you. It removes the average answer and forces the method;
*which* assumption to break is the human/your creative spark — but every candidate must still be able
to **die** on a world-test. See `OUTLIER_MCB_SPEC.md` and `OUTLIER_MCB/activate.md`.

## Closure gate + representation theorems (FIX A–E) — do not re-propose a closed family

If a request is "a new X in a family with a representation theorem" (e.g. a permutation-invariant pooling
→ **DeepSets** `ρ(Σ φ(x_i))`), an idea that merely "differs from one member" is still `INSIDE_THE_BOX`.
- A pack can declare `universal_closures` (e.g. `["DEEPSETS","QUASI_ARITHMETIC"]`); `closure_membership(idea,
  pack)` rules `INSIDE_THE_BOX` on membership (`closures.py`), and `judge` enforces it.
- `theorem_brief(problem)` surfaces the theorem and the ONLY admissible exits {break an axiom, condition on
  the set, change the object, NEW INFORMATION}; `preflight` attaches it.
- Honesty ladder: `ALIVE_OWN_WORLD` is **not** novelty — `architectural_novelty(...)` needs closure-escape +
  prior-art (+ transfer) before "novel/innovative"; `honest_prior_art_status(...)` caps lexical-only to
  `INCOMPLETE_ONLINE_SEARCH` (never `NO_PRIOR_ART`); `classify_proved_theorem(...)` labels a proof CLASSICAL
  vs NOVELTY-PENDING. Never say "new architecture / new theorem" without these. See SPEC §"Closure gate".

## Repo facts
- Pure-Python, no heavy deps. Engine is domain-blind (`OUTLIER_MCB/kernel.py`); all domain knowledge
  lives in swappable packs (`OUTLIER_MCB/packs/`: coding, math, generic — add your own by elicitation).
- Tests: `pytest -q` (or `python tests/test_outlier_mcb.py`, which shells out to pytest). Demo: `python examples/greenstar_demo.py`.
- This folder **is** a git repo (branch `main`) — commit before risky edits so you can undo.
