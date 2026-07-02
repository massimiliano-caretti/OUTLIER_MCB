# OUTLIER_MCB — SPEC

> An **active**, domain-agnostic engine for rigorous creativity. NOT a benchmark runner, NOT a random
> idea generator, NOT magic. It forces *assumption-negation* and lets *falsification* certify novelty.
> It is meant to sit behind a coding assistant in VS Code: when the user asks for something *new*, the
> assistant calls it before answering, so it stops answering from the average of its training memory.

## Central principle
Don't start from solutions. Start from **HIDDEN ASSUMPTIONS**.
```
ASSUMPTION → NEGATION → CONSEQUENCE → WORLD-TEST → CANDIDATE → COLLISION AUDIT → FALSIFICATION → SPEC
```
Creativity is not a new mechanism; it is *making false an assumption everyone uses without noticing.*
Einstein didn't invent a new regression — he negated *"time is absolute"*. Bell negated *"local
realism"*. OUTLIER_MCB works at the level of **which assumption of the problem are we breaking?**, not
*"which new layer/algorithm/trick?"*. The *spark* (which assumption to break) stays human; the *rigor*
(derive + falsify) is the machine's.

## Agnostic by construction: kernel ⊖ DomainPack
- **`kernel.py`** — the domain-blind engine. Knows nothing about any specific problem. Provides
  `graph_of`, `preflight`, `no_solution_before_assumption` (gate ANY proposed solution),
  `branch_on_assumptions` (the generator: K breaks in tension across distinct axes), `novelty_score`.
- **`pack.py` + `packs/`** — ALL domain knowledge lives in swappable `DomainPack`s. Built-in:
  `coding` (systems/algorithms), `math` (theorems/optimization), `generic` (universal fallback). Each
  declares its own **axes**, assumptions, known families, info-kinds, and failure memory.
- **`guard.py`** — fires when no pack matches the prompt; **refuses the canned answer**.
- **`elicit.py`** — when the domain is unknown, returns a **scaffold** the assistant fills to BUILD a
  real pack (`pack_from_spec` validates it); the kernel then falsifies. Agnosticism without magic: the
  kernel never invents domain content, it *requests* it.

There is no privileged domain anywhere in the engine: every domain is one pack among many.

## The four ways in (the human–machine loop)
```python
import OUTLIER_MCB as gsl
gsl.creative("invent a genuinely new architecture for X")   # "break THIS assumption" — the brief
gsl.judge("my concrete idea", prompt="X", repo_path=".")    # "discipline MY idea" — run the rigor on it
gsl.invent("X", repo_path=".", execute=True)                # the deep grounded runtime (a portfolio)
gsl.green_star("X")                                          # the NO-EXAMPLES zone (first principles)
```
The thesis is *the spark is human, the rigor is the machine's*. `creative` gives the spark a target;
**`judge` closes the loop** — it takes the assistant's OWN free-text idea, infers which assumption it
breaks, and runs the full rigor on IT (gate → theorem → world-test → reviewer → maturity → AUTO/HUMAN
verifiability), returning `INSIDE_THE_BOX` (not new) or `MUST_BE_AUDITED` with the concrete next step.
Everything else is for going deeper by hand.

## The pipeline modules (all pack-driven)
| Module | Public entry | What it forces |
|---|---|---|
| `assumption_graph.py` | `graph_of` (kernel) | typed graph (`implies, depends_on, blocks, if_false_requires, collapses_to, needs_new_data`); central vs derived vs **breakable**; data requirements per break |
| `preflight.py` | `preflight_creative_request` / `creative` | one call → what NOT to propose · hidden assumptions · 3 breaks · 1 recommended direction · death-gate · anti-collage · ready instructions |
| `kernel.py` | `no_solution_before_assumption` | a standard mechanism with no declared break → **INSIDE_THE_BOX** (cannot be proposed) |
| `theorem_sketch.py` | `theorem_sketch` | formal object · negated assumption · class to separate from · desired proposition · new prediction · world-test · **killer counterexample** |
| `reviewer.py` | `reviewer_attack` | "isn't this just X?" · relatives · collisions · rejection sentence · minimal defense · **max claim / forbidden claim** |
| `world_designer.py` | `design_world_test` | a falsifiable world SPEC: which family must FAIL, which candidate must WIN, controls that must collapse, leakage, deciding metric |
| `paradigm_shift.py` | `paradigm_shift` | the seven green-star questions (what does the old paradigm call noise / the new one call signal?) |
| `missing_info.py` | `detect_missing_information` | when a breakthrough is **impossible with current information**; which new info would move the ceiling |
| `lineage.py` | `declare_lineage` | which DEAD ideas (from the pack's memory) an idea descends from; inherits death unless it declares an extra break |
| `instruction_emitter.py` | `emit_assistant_instructions` | a short block to read before answering, in any assistant |

## The plural generator (`generators/` package)
The original generator did one move: negate one pre-registered assumption, one axis at a time. Applying
the engine **to itself** surfaced five more generative operators, each disciplined (it generates a
candidate but certifies nothing — the candidate still must die on a world-test):

| Operator | Axis broken | The move | Still must die by |
|---|---|---|---|
| `recombine_assumptions` | ARITY | break TWO assumptions on distinct axes at once | parsimony: must beat the ablation of EACH single break (synergy>0) |
| `invert_assumption` | OPERATOR | swap what the assumption fixes ↔ what it optimizes | symmetric world-test: must collapse when the symmetry is restored |
| `scale_break` | REGIME | "what at 1000×?" — break a true-at-small-scale assumption | must show a CROSSOVER, not a uniform win |
| `transport_break` | TRANSFER | carry a surviving break across domains (analogy) | enters with ZERO novelty credit; must pass the destination's audit |
| `what_would_have_to_be_true` | SOURCE | backward-chain from a desired capability | each link inherits its falsifier; valid only if every world-test passes |

`generate(prompt)` runs them all and returns a pooled, un-certified set. `novelty_score(..., synergy=)`
rescues the legitimate collage: an idea may reduce to a known family yet be novel if the whole strictly
beats every part. The generator got richer; the falsifier did not get weaker.

### Reaching past the registry (applying the engine to its OWN residual box)
A second self-application found that every operator above is still a *breaking* move, that the engine
built its own arena, and that "novelty = survival". Negating those gave three more capabilities —
the ones that actually push a model **outside what it already had**:

- **Non-breaking creation** — `unify` (two things are one), `instrument` (a new observable), `reframe`
  (restate the object). Creation is not only negation; these break no axis and are certified by the
  **new prediction** they make possible.
- **Discovery** — `anomaly_to_assumption(anomaly)` mines "what refused to collapse" into a **new,
  provisional assumption the registry did not contain** (inert until given an axis + falsifier). This
  is the only source of non-pre-registered assumptions: the engine discovers, it doesn't only retrieve.
- **Agency** — `self_spark(pack)` lets the **engine propose which assumption to break** (ranked by
  novelty potential), then still routes it through the same falsifier. The spark stops being only-human.

### The honesty layer (`maturity.py`)
Generation became plural, so certification became finer — not weaker. `assess_maturity(...)` separates
**coherence** (survived its tests) from **reach** (severe independent predictions) and **fecundity**
(new questions opened), on an enriched ladder: `INSIDE_THE_BOX · DEAD_COLLAGE · INDETERMINATE ·
SUSPENDED_BOLD · ALIVE_OWN_WORLD · ALIVE_LOCAL_NOVELTY · ALIVE_TRANSFERS · ALIVE_ARCHITECTURAL`. Two
fixes matter most: a bold idea with no world-test yet is **SUSPENDED, not killed** (it records what
would make it testable), and winning is split into **own-world vs foreign-world** — an idea that only
wins on the arena it designed proved little, so a transfer test on another idea's world is required
before any general claim. This is the discipline against rigor-theater and the anti-bold bias.

### The novelty market + codebase-as-resolver (applying the engine to an external audit's box)
A third self-application treated a strong external audit's own recommendations (multi-agent debate,
tree-of-thoughts, multi-objective scoring, RAG repo-context) as the **box** — and the engine flagged
them all `INSIDE_THE_BOX` (the average agentic upgrade). The non-average breaks it surfaced, now built:

- **`dissolve`** (`generators/nonbreaking.py`) — creativity by DELETION: remove a stage/assumption so the problem
  dissolves. Certified by a well-posedness test (still solvable AND simpler), not by adding anything.
- **The unit is a priced BET, not a scored idea** (`economy.py`) — `Bet`, `Ledger`, `forge_bet`. An
  idea is free; a bet (a claim + the test that settles it + what you'd stake) carries information. The
  `Ledger` is a **persistent portfolio** ranked by expected value (`stake / price`).
- **Failure is PRICED by (axis × operator), with a REOPEN rule** — an axis killed by `negate` becomes
  expensive *under negate* but stays cheap under an **untried operator** (`unify`/`instrument`/`dissolve`).
  The engine never goes blind where it once failed: `Ledger.reopen_operators(axis)` surfaces the moves
  worth retrying. This replaces the blacklist with an economy.
- **The codebase is the resolver, not the engine** (`repo_world.py`) — `compile_world_test` turns a
  claim into an EXECUTABLE check (a test that must flip red→green, a type/contract, a benchmark). A bet
  is WON only if the repo's own gate flips. The engine stops grading its own homework — and this is what
  makes it operational inside VS Code: the world-test becomes a command you actually run.

### The cognitive runtime (`invent.py`) — borrow the frameworks, invert their objective
A fourth self-application treated "import Tree-of-Thoughts / Self-Refine / Reflexion / AutoGen / DSPy
as-is" as the box — and the engine flagged all five `INSIDE_THE_BOX`, because each one's value function
rewards the *likely/correct* answer, i.e. optimizes toward the loss function we are escaping. The fix it
recommended: keep their **control structure**, invert their **objective** to

> **box_distance(candidate) × survives_falsification(candidate)** — not accuracy.

`invent(prompt)` is the resulting runtime — a portfolio of unknowns, not a single answer:

| Borrowed from | Control structure kept | Objective inverted to |
|---|---|---|
| Tree-of-Thoughts | `novelty_search` — beam search + backtracking | keep the candidates **farthest** from the box; prune the ones that collapse *into* it |
| Self-Refine | `push_further` — iterative refinement | each pass must move **farther** from the box (rarer operator, one more axis); a "safer" pass is rejected |
| Reflexion | `invent_reflect` — episodic memory + reflection | a **lost bet becomes a NEW assumption to break** (failure = next frontier), persisted in the Ledger |
| AutoGen | explorer / critic / synthesizer / **resolver** roles | adversarial **toward the box**; truth settled by the EXTERNAL resolver (the repo), never by consensus |
| DSPy | declarative composed pipeline | optimized for **disciplined novelty**, not accuracy |

`box_distance` (the anti-loss metric) rewards breaking more axes, rarer operators, and — decisively —
**requiring new information** (structure not in the current data / training distribution). That is the
operational meaning of *fighting the loss function*: the runtime is pulled toward what cannot be answered
from the prior, while falsification + the external resolver keep it from hallucinating.

### Grounding — the engine runs against the REAL environment, not placeholders (`grounding.py`)
The recurring weakness was that world-tests, routing, and scoring ran on internal heuristics, never on
the actual project, so falsification was nominal and "novelty" could be mere rebranding. Applying the
engine to that critique flagged the standard reflexes (placeholder world-tests, keyword routing,
distance-only scoring) as `INSIDE_THE_BOX` and recommended a single source of truth: **probe the repo**.

- **`probe(path) → RepoContext`** — a read-only, stdlib-only inspection of a real project: detected
  languages, the real **test / type / build commands**, sample source & test files, and a few public
  symbols. Everything below consumes it.
- **Grounded world-tests** — `compile_world_test(claim, axis, repo=…)` emits the DETECTED command and a
  REAL file to touch (`grounded=True`, actually runnable). Without a repo it returns a placeholder
  flagged `grounded=False`, so an ungrounded idea is discounted, not mistaken for a real test.
- **Grounded scoring** — `box_distance(…, grounded=False)` HALVES the distance: a grounded near idea
  beats an ungrounded far one. Distance alone rewards strangeness; grounded distance rewards quality.
- **Substance gate** — `invent()` flags `rebranding_risk` when an idea breaks an axis but is ungrounded
  and needs no new information or output — i.e. its "novelty" is only lexical.
- **Grounded routing** — `select_pack` / `guard_response` take an optional `RepoContext` and a confidence
  **margin**: when the top two packs score nearly the same, the guard fires (elicitation) instead of
  silently picking the wrong domain.
- **A learning loop, not a log** — `Ledger.policy()` / `weight_of(axis, op)` turn the win/loss record
  into a generation bias the runtime multiplies into the ranking, so losses actually change behaviour.

Use it end-to-end: `gsl.invent("…", repo_path="/path/to/project")` — every frontier idea then carries a
command you can run, and the repo (not the engine) settles the bet.

### The green-star zone — creating with NO examples (`greenstar.py`)
Every other module operates on a DomainPack: assumptions someone curated from known examples. The real
green-star zone is where there is NO pack and nothing to elicit — the idea must come from the STRUCTURE
of the problem, not from retrieval. Applying the engine to that gap flagged even *"ask the human for
examples"* as `INSIDE_THE_BOX` (it is still operating on examples) and surfaced four moves, all built:

- **First-principles generation** — `synthesize_assumptions(prompt)` crosses the universal structural
  `PRIMITIVES` (input, output, objective, object, constraint, measure, time, agent, representation,
  resource) with the universal hidden-assumption `TEMPLATES` (is-fixed / uniform / independent /
  observable / static / settled). It GENERATES assumptions no registry ever stated — for any prompt,
  with zero examples.
- **Self-bootstrapped structure** — `synthesize_pack(prompt)` builds a provisional pack with **empty
  `known_families`**: in the green-star zone the convex hull is empty, so there is nothing to forbid as
  collage. The engine constructs its own structure instead of asking for examples.
- **Inventing the dimension** (META) — `novel_axis(prompt)` pairs two primitives (e.g. `AGENT×INPUT`)
  into a new dimension of variation no pack declares — meta-creativity: invent the axis, not just break it.
- **Extrapolation, not interpolation** (REGIME) — `extrapolation(candidate)` measures distance beyond
  **all** packs (`global_families` = the global convex hull), scoring 1.0 only when a candidate breaks a
  dimension no pack has AND references no known family — genuinely outside everything the engine knows.

`green_star(prompt)` is the entrypoint: it bootstraps the structure, generates over it, and ranks by
extrapolation. Everything it returns is explicitly **UNFALSIFIED structure** — a world must be BUILT to
test it, never retrieved. This is the library working where there are no examples to average: pure
creativity, disciplined by the requirement that the leap must still be made falsifiable.

### Closing the loop — the engine RUNS, scores, and proposes concretely (`verifier.py`, `scoring.py`)
The engine used to prepare judgment (a command, a score, a SPEC) but never execute it. Applying it to
that gap flagged "emit a command", "distance-only score", and "text verifier" as `INSIDE_THE_BOX` and
demanded actual execution. Built:

- **A verifier that runs** (`run_check`, `verify`) — executes the grounded command in a bounded
  subprocess, reads pass/fail, and reports a `Verdict` that states plainly **what was verified, what was
  NOT, and why the idea is alive or dead**. `verify` then settles the bet in the ledger, whose policy
  re-weights future generation — run → read → settle → re-rank. Honest scope: it proves the gate flips,
  not that the idea is best; the Verdict says so. Execution is opt-in (`invent(..., execute=True)`).
- **A multi-factor score** (`score_idea`) — replaces distance-alone with **novelty · usefulness ·
  implementability · verifiability · risk · cost**, where the composite GATES novelty by verifiability
  and implementability, so a far-but-unbuildable idea cannot outrank a grounded, checkable one.
- **Deeper grounding** (`RepoContext.map`) — beyond file names: the project's **components**, its public
  **contract** (a package `__all__`), and its **fragile** files (TODO/FIXME density). The runtime grounds
  in the project FLOW, not a listing.
- **Concrete proposals** — each frontier idea is emitted as a minimal, actionable change: which component
  to touch, the assumption to make false, and the exact command that settles it.

End-to-end: `gsl.invent("…", repo_path="/project", execute=True)` returns a portfolio where each idea is
scored on six factors, expressed as a concrete change, and — where grounded — already RUN, with the bet
settled by the repo. The engine stops being a reminder and starts being a loop.

### Capabilities the engine found for ITSELF (not in any idea-engine literature)
Using the library massively on the question "a globally-new capability for a creativity engine", the
green-star zone (extrapolation 1.0 beyond ToT / evolutionary search / quality-diversity / TRIZ / MCTS /
RAG) and the engine's own ranking selected three to build:

- **Assumption dynamics** (`cascade.py`) — breaking one assumption is not isolated: it FORCES the
  assumptions that depended on it, FREES the ones it was blocking, and COLLAPSES the families that rested
  on it. `cascade(pack, seed)` computes the chain reaction; `biggest_lever(pack)` finds the single break
  that unlocks the most. Generation by dynamics over the typed graph, not static negation.
- **Compression as depth** (`compression.py`) — following Solomonoff/Schmidhuber, the deepest idea is the
  one that COMPRESSES the domain: a unification folds two assumptions into one, a deletion removes a
  stage. `compression_gain` measures the description-length reduction; the runtime's score now weighs
  **depth** alongside novelty, so a baroque-but-far idea cannot outrank a compressing one.
- **Synthesis of contradiction** (`dialectic.py`) — `dialectic(pack)` finds two assumptions in genuine
  tension (A blocks B) and synthesizes the THIRD object that exists only where both are broken at once —
  thesis + antithesis → synthesis, not a compromise. Contradiction-resolution as a first-class operator,
  fed into the generator pool.

All three are wired into the runtime: the generator pool now includes contradiction-syntheses, and the
multi-factor score rewards compression depth — so the engine is measurably more creative (more moves)
and more intelligent (it values what explains more with less), in ways no standard engine implements.

### Quality-Diversity + formal Novelty Search (`qd.py`, `novelty_archive.py`, `goal_setter.py`)
Two pillars of the open-endedness literature now formalize and strengthen the project's existing philosophy.
They are domain-agnostic (they read only `pack.axes` and a `Candidate`), deterministic, and zero-dependency.

- **MAP-Elites archive** (`qd.py`, after Mouret & Clune 2015; Pugh, Soros & Stanley 2016). The runtime no
  longer returns only a ranked list — it **illuminates** the idea space into a MAP of elites. A
  `BehaviorDescriptor` characterizes the *kind* of an idea on three behavior dimensions — **complexity** (a
  structural proxy standing in for cyclomatic complexity, which is not computable on an unimplemented idea),
  **abstraction_level** (implementation / interface / architecture, from the operator), and an **axes_vector**
  (a multi-hot over the pack's axes: which axes it breaks). `QDArchive` keeps the single best idea (by the
  grounded `score_idea` composite) in each behavioral cell, so a strong-but-ordinary idea can no longer crowd
  out a weaker-but-genuinely-different one — the failure mode of plain ranking. `invent()` now also returns
  this map (`inv.archive` / `inv.qd_map()`); `illuminate()` runs the MAP-Elites loop standalone (seed → sample
  a parent elite → mutate → re-place). Reported by **coverage** (cells filled) and **QD-score** (total quality).
  *Backward-compatible: the `frontier` / `best()` API is unchanged; the map is an additional, richer view.*

- **Formal Novelty Search** (`novelty_archive.py`, after Lehman & Stanley 2011). The informal `box_distance`
  becomes a relative measure: `NoveltyArchive.calculate_novelty(bd, k)` is the **sparseness** ρ — the mean
  distance from an idea's behavior descriptor to its *k* nearest neighbors among the ideas already proposed;
  `add_if_novel` admits only ideas that clear a **dynamic threshold** (the archive's current mean novelty), so
  the bar rises as the space fills. `score_idea(..., novelty_archive=…)` blends this sparseness into the novelty
  factor — an idea is novel only if it is far from *our own* prior ideas, not by a fixed hand-weighted rule.
  This is distinct from `novelty.py` (real-world prior-art search) and `novelty.world_novelty_score` (distance
  from the REAL world): novelty_search drives divergent *generation*; the novelty audit certifies the survivor
  is not a rename. The two compose — diverge internally, then check externally.

- **Intrinsic goal-setter** (`goal_setter.py`, after the open-endedness / POET line, Wang et al. 2019). A system
  that keeps improving invents its own next goal from where it is currently blind. `propose_goal(archive, pack)`
  reads the QD map — the filled cells (where we are strong and diverse) and the **empty regions** (where we have
  no good idea) — and builds a prompt asking an LLM for a NEW, executable **world-test** that forces a solution
  into an unexplored region, with the usual falsification requirements (specific & measurable · red-first
  baseline · negative control · must not re-skin an idea already on the map). The model's reply becomes the
  next thing the engine tries to fill — the open-ended loop. It calls no model itself; it only frames the goal.

Together, QD and NS make the project's slogan operational: divergent, *structured* novelty (a map of diverse
kinds, not one peak), measured *relative to what we have already had* (sparseness, not a fixed distance), and
kept honest by the same grounded composite and falsification gates — never by chasing the loss function.

The open-ended layer is completed by four more modules, each reusing the operators (never rebranding them):
- **FunSearch loop** (`creative_search.py`) — generator proposes, an EXTERNAL pluggable evaluator scores, the
  QD archive evolves; full lineage. The evaluator, not the generator, decides quality (Romera-Paredes 2023).
- **Graded prior-art audit** (`novelty.py` `prior_art_audit`) — a 5-point scale (RENAMED / COLLAGE / WEAKLY /
  PROVISIONALLY / VERIFIED_USEFUL) that NEVER claims absolute novelty, each with the query that would refute it.
- **Divergent-thinking engine** (`divergence.py`) — Guilford's fluency / flexibility / originality /
  elaboration over Boden's combinational / exploratory / transformational creativity, pruning paraphrases.
- **Tree-of-Thoughts + Self-Refine + Reflexion** (`thought_search.py`) — a thought tree pruned by an EXTERNAL
  score (never self-judgment), refinement accepted only on a real external gain, and a ReflectionMemory that
  turns a failure into the next mutation hint.
- **Recursive self-improvement** (`self_improve.py`) — the engine runs creative_search on "how should I
  improve?", then triages every proposal with judge (drop INSIDE_THE_BOX) and novelty_audit (drop renames),
  never auto-implementing. The `GSL_OPENENDED` eval mode + its ablations + `evals/readiness_openended.py`
  certify all of this with a GO_READY_OPENENDED gate that passes only when the numbers hold.

### Orchestration — from a pile of tools to one pipeline (`dossier.py`)
A self-audit (the engine on its own call-graph) found the biggest remaining gap: many capabilities were
exposed in the API but never threaded into the flow — the theorem sketch, world-test, reviewer attack,
lineage, cascade, and the **maturity verdict** were all reachable only by hand. Fixed:

- **`dossier(candidate, pack, repo)`** runs the WHOLE engine on one idea and returns a single report:
  score (novelty + depth), compression, the cascade it unlocks, the theorem sketch, the falsifiable
  world-test, the reviewer's objection, its lineage, and — finally — its **maturity** (alive / suspended
  / dead). One call now orchestrates what were seven disconnected modules.
- **`invent` carries a maturity verdict per idea** (the honesty layer was dead code in the flow; now
  every frontier idea states whether it is `ALIVE_OWN_WORLD`, `SUSPENDED_BOLD`, `DEAD_COLLAGE`, …), and
  surfaces the **biggest cascade lever**. `Invention.dossier(i)` and `Invention.reflexion()` close the
  loop — the latter mines every LOST bet into a new assumption to break next round.
- **One novelty number** — the score blends `box_distance` (within the domain) with `extrapolation`
  (beyond all domains), so the two metrics no longer rank an idea differently with no resolution.
- **A persistent ledger** — `Ledger.save/load` keep the portfolio and the policy across sessions, so the
  learning is actually persistent, not in-memory only.

## The exit axes (the only way out of the box)
A candidate must break ≥1 of the **pack's declared axes** (e.g. for `coding`: REPRESENTATION,
OBJECTIVE, DECOMPOSITION, COST_MODEL, INTERFACE). If it breaks none, it is flagged `INSIDE_THE_BOX`
before it can compete. The axes are NOT hard-coded in the engine — each pack names its own.

## Novelty scoring (graded, not binary)
`novelty_score` distinguishes a *well-phrased* idea from a *genuinely different* one:
broke an axis (0.4) · not reducible to a known family (0.3) · yields a new verifiable output (0.2) ·
controls collapse (0.1) → `INSIDE_THE_BOX/collage` < `LOCAL novelty` < `ARCHITECTURAL candidate`.

## CLI
```
python -m OUTLIER_MCB.cli creative  --problem problem.md
python -m OUTLIER_MCB.cli preflight --problem problem.md --pack coding
python -m OUTLIER_MCB.cli branch    --problem problem.md -k 3
python -m OUTLIER_MCB.cli graph     --problem problem.md
python -m OUTLIER_MCB.cli packs
python -m OUTLIER_MCB.cli elicit    --problem problem.md
```

## Engineering surface (small front door, deep toolbox)
- **Primary API** (`__all__`, ~11 symbols): `creative` · `invent` · `preflight_creative_request` ·
  pack management (`list_packs`/`get_pack`/`register_pack`/`pack_from_spec`/`elicit_pack`) · the two
  types you build (`DomainPack`/`Assumption`) · `OUTLIER_MCBError`. Everything else is a documented
  building block in `__toolbox__`, importable by name but out of the headline API.
- **Typed outputs** (`types.py`): `preflight` returns a `PreflightResult` TypedDict — an explicit,
  statically-checkable schema that is still an ordinary dict at runtime (no breakage).
- **Real faults raise; verdicts stay data** (`errors.py`): `PackNotFoundError` / `InvalidPackError` /
  `AssumptionNotFoundError` (each subclassing the historical `KeyError`/`ValueError` for compatibility).
  A verdict like `INSIDE_THE_BOX` is a legitimate RESULT and is returned, never raised.
- **Vocabulary documented, not hidden** (`GLOSSARY`): the method's load-bearing terms are defined in
  plain language; the engine's OUTPUT speaks plainly.

## Tests
`tests/test_OUTLIER_MCB.py` — a **pytest** suite (fixtures + parametrization) that verifies LOGIC, not
just non-crash: `negate`'s three kinds and content, pack validation, the agnosticism invariant (no
pack token hard-coded in any engine module), the generative operators, the novelty-market pricing math,
the runtime's distance ranking, and that genuine errors RAISE. Run `pytest -q` or, standalone,
`python tests/test_OUTLIER_MCB.py` (it shells out to pytest).

## Hard constraints honoured
No magic · no breakthrough promises · no random idea generator · deterministic, inspectable functions ·
every module has a real tested function · no empty classes · no overclaim (the engine *refuses*
paradigm claims without a demonstrated separation) · **every idea can die** · **no domain baked into
the engine** — the kernel is blind, all domain knowledge is a swappable pack.

## Closure-membership gate + representation theorems (FIX A–E)

Learned from a real failure (4 non-innovative MIL readouts — SCRIBE/CHORD/CRUX/MRE — passed the soft
verdicts and only died at hard rigor): an idea "≠ the mean" looked like an exit, but `ρ(Σ φ(x_i))` is the
whole **DeepSets closure** (universal for permutation-invariant sets). Distance from one *member* is not
distance from the *closure*. The fix, all ADDITIVE (no API broken), all tested:

- **A — closure gate** (`closures.py`): a `DomainPack` may declare `universal_closures` (e.g. `["DEEPSETS",
  "QUASI_ARITHMETIC"]`). `reduces_to_closure(candidate, closure) -> INSIDE|OUTSIDE|UNKNOWN` uses explicit
  STRUCTURAL detectors (a function of per-instance sums/means ⇒ INSIDE DeepSets; φ conditioned on the whole
  set ⇒ OUTSIDE). **Hard rule:** INSIDE a declared closure ⇒ `INSIDE_THE_BOX`, however different from a
  single member. Golden: mean, `Σe³/(τ+Σe²)`, soft-top-k, power-mean/GeM, CVaR ⇒ INSIDE; bag-conditioned φ
  ⇒ OUTSIDE. Wired into `judge`.
- **B — honest verdict ladder** (`architectural_novelty`): `ALIVE_OWN_WORLD` is NOT novelty. To be
  presentable as novel needs, in AND: (i) a proven **closure-escape**, (ii) a transfer-test on a world the
  candidate did not design, (iii) real prior-art. Without (i) the verdict is `NOT_YET_NOVEL` and its markdown
  makes no affirmative novelty claim. `gate_claim_language` blocks "innovative / new architecture" without
  closure-escape + prior-art.
- **C — real prior-art mandatory** (`honest_prior_art_status`): lexical-only / no-provider ⇒
  `INCOMPLETE_ONLINE_SEARCH`, **never** `NO_PRIOR_ART_FOUND`. `NO_PRIOR_ART` needs a real provider returning
  ≥K URL'd sources.
- **D — theorem registry** (`theorems.py`): `theorem_brief(problem)` surfaces the representation theorem
  ("new permutation-invariant pooling" → DeepSets) and routes generation to the ONLY admissible exits
  {break an axiom, condition-on-set, change the object, NEW INFORMATION}. Wired into `preflight`.
- **E — proved-theorem novelty check** (`classify_proved_theorem`): after `FORMALLY_PROVED`, classify as
  `FORMALLY_PROVED (CLASSICAL)` vs `(NOVELTY-PENDING-PRIOR-ART)` before any "new theorem" language
  ("power-mean ≥ mean" ⇒ CLASSICAL).
- **Generative steering**: `score_idea` (gated on `universal_closures`) penalizes in-closure ideas and
  rewards closure-EXITS and `requires_new_information` — more divergence, same falsifier. Anti-regression
  test: MRE/CHORD/soft-top-k stay `INSIDE_THE_BOX(DeepSets)` forever.

**Pack migration:** declare closures in the spec — `pack_from_spec({..., "universal_closures": ["DEEPSETS"]})`
— or on a `DomainPack(universal_closures=[...])`. Closure NAMES reference `CLOSURE_REGISTRY`; do not put them
in `known_families` (keep the agnosticism guard green).

## The library is a DISCOVERER first (the judge is a downstream service)
Identity: OUTLIER_MCB exists to FIND and INVENT real, new structure; external certification makes an invention
real, it does not silence it. `autonomous_discover(problem, oracle, budget)` is the inventor-first front door:
- **T1 `oracle_miner`** — read the oracle for SPARKS (holonomic recurrence via rational linear algebra, verified on
  held-out terms; modular patterns; asymptotics). A non-holonomic sequence yields no false recurrence. Breaks
  `evaluation_is_fixed`: the judge/oracle becomes a source for the inventor.
- **T2 `primitive_library`** — a self-expanding alphabet (compose + abstract on demand); invention is a RATCHET,
  with composition depth as a behavioural dimension.
- **T4 `solution_type_lattice`** — PIVOT the objective across forms (closed-form → recurrence → generating-function
  → asymptotic-with-band → algorithm → bijection → conditional-theorem) instead of stopping at CONJECTURE.
- **T3 `acquire_new_information`** — query the oracle for MORE terms (the ceiling-raising move).
- **T5 `ScratchFrontier`** — a sandbox permitting worsening detours; only the committed ledger is monotone.
- **T6 `mechanism_generalizes`** — validate a mechanism by TRANSFER to manufactured sister-landscapes (+ negative
  control), not self-vote.
- **T8 `certify_reduction`** — a discovered `A ⟺ B` reduction is `REDUCTION_ESTABLISHED`, a first-class result.

Primary metric: DISCOVERY CAPABILITY (`evals/discovery_battery.py`) — solutions/structures found, with an ablation
proving every CREATIVE stage is load-bearing. Honesty (no false PROVED, committed monotone) is the CONSTRAINT that
keeps the discoveries real. The success message is a DISCOVERY, never a defence.

## External prover / CAS backends (levels A/B/C) — the certified-settlement toolbox
A result is certified ONLY by an external resolver. A **backend** is one callable with a fixed contract:
`prove(conj) -> (status, counterexample|None, detail)` where `status ∈ {FORMALLY_PROVED, FORMALLY_DISPROVED,
TOOL_LIMIT_UNKNOWN, TOOL_UNAVAILABLE}`, plus `.backend_name`. `settle_lemma(lemma, backend=…)` maps the status to a
`LemmaCertificate` (`_PROVED_CERT` / `_REFUTED_CERT`); only a `LEMMA_CERTIFIED` status advances a `FrontierLedger`.
- **Level A — automatic:** `z3_backend`, `cvc5_backend` (SMT, `∀ ⟺ UNSAT(¬claim)`), `atp_backend('vampire'|'e')`
  (first-order, TPTP). Certificates `Z3_PROVED` / `CVC5_PROVED` / `VAMPIRE_PROVED` / `E_PROVED`.
- **Level B — proof assistant:** `isabelle_backend` (Isabelle/HOL + Sledgehammer, often closes with no hand proof →
  `ISABELLE_CHECKED`), `lean_backend` (by-hand, `sorry`-free → `LEAN_CHECKED`).
- **Level C — computational CAS:** `pari_backend` (PARI/GP, number theory over a **finite** box → `NUMERIC_VERIFIED`).
- **Portfolio:** `portfolio_backend([...])` runs a FIXED-priority list, the first valid certificate wins
  (deterministic, records `.winner`); it sets `.backend_name` to the winner so the certificate names the real solver.

Every backend is OPT-IN: absent tool → `TOOL_UNAVAILABLE` (detected with `shutil.which`, run via `subprocess` with a
timeout + argv list, no `shell=True`). New certificate statuses live in `certificates.FORMAL_CERTIFICATES`; adding
one is the only way to make it count (the `never_proves_open_conjecture` invariant enforces every certified status is
a registered external certificate). HONESTY: a finite PARI computation proves that finite domain ONLY; an open
conjecture yields at most certified partial lemmas, the parent stays `CONJECTURE`. Guard: `evals/solver_regression.py`.

## Honest limits
- The engine does **not** invent the idea. It forbids the average answer and forces the method; the
  human spark — *which* assumption to break — stays human.
- Closure detectors are STRUCTURAL heuristics on the readout description, not a CAS proof of membership;
  they rule INSIDE on recognized aggregation forms and OUTSIDE on bag-conditioned φ, else UNKNOWN.
- The built-in `coding`/`math` pack verdicts are **HEURISTIC priors** (flagged in-pack), not validated
  by a specific project. They orient; they don't certify.
- Non-ML packs have **no executable `world_factory`** yet — their world-tests are emitted as SPECs
  (property tests / constructed counterexamples), not run. Executable world-tests are the next frontier.
- Pack **selection is keyword-based**; the elicitation path is the honest mitigation when it is unsure.
