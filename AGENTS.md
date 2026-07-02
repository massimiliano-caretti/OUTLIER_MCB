# Using OUTLIER_MCB (standing routine for AI coding assistants)

This project uses **OUTLIER_MCB**, an assumption-negation + falsification engine for rigorous, honest
invention and discovery. It works with ANY assistant — Claude, ChatGPT, Gemini, Cursor, Copilot, …

**When the user asks for something new / novel / invented / discovered in English or Italian, you MUST use the
library — this is a routine, not an option.**

**Quando l'utente chiede qualcosa di nuovo / originale / inventato / scoperto in inglese o italiano, devi usare
la libreria: è una routine, non un'opzione.** Get the brief first, then obey it:

```bash
python -c "import OUTLIER_MCB as m; print(m.assistant_brief('''<the user request>'''))"
```

For continuous use after the first activation, route every turn through the compact decision API:

```bash
python -m OUTLIER_MCB route --problem "<the user request>" --json
```

If `activate` is false, answer normally. If true, follow `entrypoint`, `next_call`, and always report the
broken assumption, world-test/death-gate, claim-ladder status, and `novelty_scope`.

Se `activate` è false, rispondi normalmente. Se è true, segui `entrypoint`, `next_call`, e riporta sempre
assunzione rotta, world-test/death-gate, stato della claim ladder e `novelty_scope`.

For the full loop (generate → settle by an EXTERNAL resolver → audit → one honest report):

```python
import OUTLIER_MCB as m
# inventing (settled by data / repo tests / an objective evaluator; prior art checked online; honest novelty_scope)
m.explore("<request>", evaluator=<objective>, prior_art_provider=<online>, llm=<your model>)
# discovering theorems (settled by z3 / lean — the solver decides, never the model)
m.explore("<claim>", math_claim="x**2 + y**2 >= 2*x*y", math_variables={"x": (-5, 5), "y": (-5, 5)})
```

## The non-negotiable rules (why this exists)

1. **Do NOT answer a 'new / novel / invent / discover' request from memory.** Run the library first; it
   removes the average answer and makes you break a hidden assumption.
2. **Break a hidden assumption and name it.** An idea that breaks none is `INSIDE_THE_BOX` — not an answer.
3. **Settle EXTERNALLY** — data, repo tests, z3, lean. The engine never self-certifies; neither should you.
4. **Check prior art ONLINE** when you claim novelty; always report `novelty_scope`:
   `LOCAL_ONLY` · `INCOMPLETE_ONLINE_SEARCH` · `ONLINE_PRIOR_ART_CHECKED`.
5. **NEVER** say "absolute novelty" / "new theorem" / "never seen before" without a formal proof **and** an
   online prior-art check **and** a passing verifier. Use the graded verdicts:
   `RENAMED` · `COLLAGE` · `WEAKLY_NOVEL` · `PROVISIONALLY_NOVEL_ON_CHECKED_SOURCES` · `VERIFIED_USEFUL_NOVELTY`.
6. **For math/theorems**, a result is `FORMALLY_PROVED` only when z3/lean confirms it; otherwise it is a
   `SKETCH`, an `EMPIRICALLY_SUPPORTED` conjecture, or `COUNTEREXAMPLE_FOUND`. No proof ⇒ not a theorem.

The spark is yours; the rigor is the machine's — and every candidate must be able to **die** on a world-test.

## Useful one-liners

```python
m.creative("invent X")                      # the lightweight brief: which assumption to break
m.assistant_route("invent X")               # compact per-turn router for continuous LLM use
m.judge("my idea", prompt="...")            # discipline a free-text idea: INSIDE_THE_BOX vs MUST_BE_AUDITED
m.prior_art_audit("my idea", provider)      # graded novelty against real sources (never "absolute")
m.readiness_discovery_report()              # are we entitled to discovery claims? (LOCAL_ONLY without online)
```
