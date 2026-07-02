# OUTLIER_MCB

A domain-agnostic **discoverer / inventor** for disciplined creativity — it exists to FIND and INVENT new,
real structure (reframe problems, leave the box, solve things not yet known). External certification
(z3 / Lean / an oracle) is a **downstream service** that makes an invention *real*, not a gate that silences it.

**The inventor is the front door.** `autonomous_discover(problem, oracle=…)` drives the creative pipeline:
mine the oracle for sparks → grow the primitive alphabet on demand → **pivot the form of the answer** when one
is impossible (closed-form → recurrence → generating-function → asymptotic → algorithm → bijection → conditional
theorem) → certify the survivor externally → acquire NEW information when stalled → explore worsening detours in a
sandbox while the committed ledger stays monotone. On success the library reports a **discovery** ("I found/invented
X, certified thus"), never a defence ("cannot prove Y"). The falsification layer keeps the discoveries real: it
forbids a *fake* PROVED (a fake discovery betrays the goal) and never regresses what is already real.

It is also a *discipline layer*: name the hidden assumption a domain's standard solutions share, break it on an
explicit axis, state the test that would kill the new idea, search for prior art, and gate the strength of the
final claim to the evidence that exists. Novelty is certified by **survival against a falsification test plus a
prior-art search**, never by naming or a confidence score — so that what the inventor finds actually counts.

[![CI](https://github.com/massimiliano-caretti/OUTLIER_MCB/actions/workflows/ci.yml/badge.svg)](https://github.com/massimiliano-caretti/OUTLIER_MCB/actions/workflows/ci.yml)
[![python](https://img.shields.io/badge/python-3.8%2B-blue)](#install)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![typed](https://img.shields.io/badge/typed-PEP%20561-informational)](OUTLIER_MCB/py.typed)
[![dependencies](https://img.shields.io/badge/runtime%20deps-0-brightgreen)](pyproject.toml)
[![status](https://img.shields.io/badge/status-beta-yellow)](CHANGELOG.md)
[![tests](https://img.shields.io/badge/tests-pytest-blueviolet)](tests/)

> One place to discover everything: `python -c "import OUTLIER_MCB as m; print(m.capabilities_markdown())"`
> lists every entry point. One composed executor: `m.autonomous("<your request>", ...)` — each argument gates
> a track, and only the tracks with real inputs run.

Pure-Python, zero required runtime dependencies. Deterministic by default (no `Math.random`, no network, no
model) — every optional capability that needs a model, the network, or a repo is opt-in and named as such.

---

## What it really does (and what it does not)

**Does:** given a request like *"invent a new X"*, it
1. routes the request to a `DomainPack` — a small, hand-written or induced set of the **hidden assumptions**
   the average answer for that domain relies on (`packs/`);
2. **negates** those assumptions on distinct structural axes, producing candidate "moves" (recombine, invert,
   push-to-scale, transport across domains, dissolve a stage, …) — each carrying the **world-test that would
   refute it** (`generators/`, `kernel.py`);
3. **scores** each candidate by a transparent, decomposed function — distance-from-the-average-answer gated by
   *verifiability* and *implementability*, minus risk and cost (`scoring.py`, `invent.py`);
4. **gates the claim**: an idea that breaks no assumption is labelled `INSIDE_THE_BOX`; one that reduces to a
   known universal closure (e.g. a permutation-invariant pooling that is just DeepSets `ρ(Σ φ(xᵢ))`) is caught
   as such (`closures.py`, `theorems.py`); a strong word ("novel", "theorem") is locked to the evidence rung it
   has actually reached (`claim_ladder.py`, `maturity.py`);
5. optionally **settles** a candidate against reality: a repo test that must go RED→GREEN, a CAS/SMT prover for
   a math claim, or data for a symbolic-regression claim (`repo_world.py`, `verifier.py`, `math_discovery.py`,
   `evaluators/`).

**Does not:** it does not invent the idea for you (the creative spark is the human's / the LLM's input), it does
not guarantee novelty, and it never claims "absolute novelty" or calls an unproved statement a theorem. Absence
of a prior-art match is reported as *incomplete search*, not as proof of novelty.

### Honest default vs. wired-up

This distinction is load-bearing, so it is stated plainly:

| Capability | Default (offline, zero-dep) | When you wire the optional input |
|---|---|---|
| Candidate **content** | recombinations of the pack's hand-written assumptions (templated) | an LLM proposes the content (`llm_openended_search`, opt-in) |
| **Distance/novelty** metric | token-set Jaccard by default; a stronger **in-box** deterministic option (`NgramEmbedder`: token + char-3-gram + light stemming) closes much of the paraphrase gap with no model | a real embedder via cosine (`set_default_embedder` / env var) for learned semantics |
| **Prior-art** scope | `LOCAL_ONLY` by default; an **in-box** curated, cited corpus (`OfflineCorpusProvider`, ~40 famous methods) raises this to `OFFLINE_CORPUS_CHECKED` — catches renames of DeepSets / token bucket / MAP-Elites / ToT with no network | arXiv / OpenAlex / Crossref / GitHub providers for the live web (`prior_art.py`) |
| **Settlement** | structural score (no execution) | a repo test, a prover, or data settles the bet |

So **out of the box OUTLIER_MCB is a deterministic scaffolding and bookkeeping tool for rigor**, not a
content generator. Its value at that tier is *method enforcement and honest claim-gating*. Its value as a
*generator* depends entirely on the optional model you wire in. The library is explicit about which tier you
are on at every step (`novelty_scope`, `AUTO`/`HUMAN` verifiability, the claim ladder).

---

## Install

```bash
pip install -e .          # from a checkout (PyPI package not yet published)
```

## Quickstart — the four entrypoints

```python
import OUTLIER_MCB as gsl

# 1) "break THIS assumption" — a brief to read before you answer
print(gsl.creative("invent a new rate limiter for a distributed API gateway"))

# 2) "discipline MY idea" — run the rigor on a free-text proposal
print(gsl.judge("measure the rate by request cost instead of by time window",
                prompt="a rate limiter", repo_path=".").markdown())
# → MUST_BE_AUDITED (breaks 'time_windowed') · or INSIDE_THE_BOX if it breaks nothing

# 3) the runtime — a portfolio of candidates, each with a settle-able bet
inv = gsl.invent("a new caching layer", repo_path=".", beam=6)
print(inv.markdown())

# 4) the no-examples zone — first-principles structure, labelled UNFALSIFIED hypotheses
print(gsl.green_star("a system that does not exist yet").markdown())
```

The kernel knows nothing about any domain; all domain knowledge lives in swappable `DomainPack`s (built-in:
`coding`, `math`, `generic`, `causal`, `numeric`, `meta`; or induce one with `infer_domain_pack` /
`elicit_pack`).

---

## How it works (mechanism)

```
request → DomainPack (hidden assumptions) → negate on distinct axes → candidate moves (+ world-test each)
        → transparent score (box_distance gated by verifiability/implementability − risk − cost)
        → claim gates (INSIDE_THE_BOX? reduces to a known closure? what claim is the evidence entitled to?)
        → [optional] settle: repo RED→GREEN | prover | data | prior-art search → honest verdict
```

- **Assumption graph + negation** (`assumption_graph.py`, `core.py`, `kernel.py`): the typed structure the
  whole engine reasons over; negation produces weak / radical / "green-star" variants of an assumption.
- **Generators** (`generators/`): the breaking operators (recombine, invert, scale, transport, abduce) and the
  non-breaking ones (unify, instrument, reframe, dissolve) — each emits a `Candidate` whose `discipline` field
  is the test it must still survive (e.g. a recombination must *beat the ablation of each single break*).
- **Quality-Diversity** (`qd.py`, MAP-Elites; `novelty_archive.py`, Novelty Search): keep the best candidate of
  each *behavioral cell* (complexity × abstraction × broken-axes), not a single winner — to map a space rather
  than climb one hill.
- **Closure gate** (`closures.py`, `theorems.py`): a registry of representation theorems; an idea inside a
  universal closure is `INSIDE_THE_BOX` even if it differs from any single named member.
- **Honesty ladder** (`claim_ladder.py`, `maturity.py`, `novelty.py`): `idea → hypothesis → conjecture →
  theorem → verified-useful-novelty`, each earned by a specific check; words are gated to the rung reached.
- **Settlement** (`verifier.py`, `repo_world.py`, `math_discovery.py` with optional z3/SymPy, `evaluators/` for
  symbolic-regression/causal claims): the external resolver, not an internal score, decides.

Everything is decomposed and inspectable: scores are weighted sums of named factors, verdicts carry the
evidence that produced them, and runs are deterministic so results are reproducible.

---

## Related work and how OUTLIER_MCB differs

It overlaps with several lines of work but occupies a different niche: **a falsification/honesty discipline
layer**, rather than a generator or an optimizer. Honest comparison:

| Related system / method | What it optimizes / produces | Where OUTLIER_MCB differs |
|---|---|---|
| **FunSearch** (Romera-Paredes et al., 2024) — LLM + evaluator evolutionary search over programs | best program for a fixed scoring function | Same generator→external-evaluator→archive skeleton (and it is reused in `creative_search.py`), but the objective here is *box-distance × survives-falsification*, not a fixed score; and the LLM is optional, not central. |
| **AlphaEvolve** (DeepMind, 2025) — evolutionary coding agent that improves real code | measured improvement on a benchmark | OUTLIER_MCB does not run an autonomous improvement agent; its evolutionary parts (`evolve.py`) are bounded and require an external resolver to certify a win. |
| **"The AI Scientist"** (Sakana AI, 2024) — end-to-end automated paper generation | full papers + experiments | OUTLIER_MCB generates *no* prose conclusions and runs *no* autonomous pipeline; it disciplines a single idea and refuses claims the evidence does not support. |
| **MAP-Elites / Novelty Search / POET** (Mouret & Clune 2015; Lehman & Stanley 2011) | behavioral diversity / open-endedness | Used directly (`qd.py`, `novelty_archive.py`), but wrapped by a *falsification* gate: diverse-but-untestable is not credited. |
| **Tree-of-Thoughts / Reflexion / Self-Refine / DSPy** | better LLM reasoning/optimization traces | These improve *generation*; the explicit thesis here (encoded in the `meta` pack) is that *settlement, not generation, is usually the bottleneck* — so the design effort is on gating and external resolution. |
| **TRIZ / lateral thinking / SCAMPER** (Altshuller; de Bono) | human ideation heuristics | Several are implemented as operators (`lateral.py`, `cognitive_protocols.py`), but each is forced to emit a refutation test rather than a suggestion. |
| **Literature/novelty tools** (Semantic Scholar, Elicit, Consensus, ResearchRabbit) | retrieve and summarize prior art | OUTLIER_MCB does not have its own corpus; it *consumes* such sources through pluggable providers and converts "no match found" into an explicit, scoped *incomplete-search* verdict rather than a novelty claim. |

The one-line distinction: **most of these maximize a quality/novelty objective or generate-and-rank;
OUTLIER_MCB's job is to make a claim *cheaper to refute* and to refuse to overstate it.** That is also its
main limitation — it is only as creative as the spark and the model you give it.

---

## Optional capabilities (all opt-in, all named)

### The composed loop and the creativity frontier (2.1)

`autonomous(prompt, …)` is a single, composed scientific loop; every argument gates a *track* that runs only
when its input is present (nothing is faked), and the result records which capabilities actually ran:

| track | capability | what it adds |
|---|---|---|
| ideas | `EarnedTaste`, `incubate`, transformational axis growth | rank unverified ideas by a value LEARNED from settled outcomes; reconnect persisted dead-ends/wins offline; grow a new axis when the space saturates |
| settle | `synthesize_evaluator` + `red_team_from_check` + `VerificationEconomy` | build an anti-cheat evaluator from a claim's own materials, adversarially attack candidate solutions, and settle them cheaply through calibrated proxies that never fabricate a pass |
| disambiguate | `run_active_experiments` | acquire information: run probes and eliminate rival hypotheses by the world's outcome, never by self-judgment |
| represent | `invent_representation` | search for an encoding that makes a hard problem easy, accepted only when a structure-destroying control collapses |

**Creativity frontier (proof-of-concept, toy domains — labelled as such).** Four exploratory capabilities, each
scored by an *external* metric with a negative control and locked by a protected invariant (so a trivial or
self-serving result cannot inflate the score): invent a toy "physics" and score its emergent structure
(`propose_new_physics`); coin an endogenous concept for a recurring pattern and score it by compression
(`ground_new_symbol`); invent a compact primitive-set DSL with a sound interpreter and score its expressive
power (`invent_new_language`); measure objective aesthetic properties of an artifact (`elegance_score`). These
are research prototypes on small domains, not production creativity, and the capability index says so.

### Runtime knobs for leaving the distribution (`invent(...)`)

These were extrapolated by running the engine on its own improvement and wired into the runtime; each is
opt-in, deterministic offline, and covered by an ablation test. They do not change default behaviour.

| knob | what it does |
|---|---|
| `set_default_llm(p)` / `OUTLIER_MCB_LLM` | register a content SOURCE so generation stops being recombination of pack assumptions (settlement still gates what survives) |
| `invent(anomalies=[…])` | mine each residual the box calls noise into a provisional assumption and break it |
| `invent(blend_with=["math",…])` | fuse the routed pack with distant domains, admitting a blend only if its emergence clears the gate |
| `invent(induce_pack=True)` | when no pack maps, induce a provisional one from the prompt instead of the generic fallback |
| `invent(discovery_path=…)` | load dead ends refuted in past sessions to re-rank this run; record settled outcomes back |
| `reward_hacking_report(items)` | flag a candidate kept only via gameable soft proxies, not the external gate |

### Semantic distance (lexical default → real semantics with one switch)

The creativity metrics and `diverge` use a **lexical** token distance by default (deterministic, zero-dep),
which sees shared *words* and not shared *meaning* — so a reworded known idea reads as "far" (spuriously
novel). The default is **process-wide resolvable**: register a real embedder once and *every* `embedder=None`
distance (novelty, memory, frontier, blending, dedup, divergence) becomes cosine-semantic.

```python
import OUTLIER_MCB as gsl
from OUTLIER_MCB.embeddings import CallableEmbedder
gsl.set_default_embedder(CallableEmbedder(lambda t: my_model.encode(t)))   # one call, whole engine
# or, without code: export OUTLIER_MCB_EMBEDDER=sentence-transformers:all-MiniLM-L6-v2
```

With nothing registered and the env var unset it stays lexical: the library never imports a model on its own.
The effect is verified by an ablation (`tests/test_semantic_default.py`): under the lexical default a reworded
near-duplicate *survives* a dedup; registering a semantic default *flips* that keep/drop decision.

### Prior-art scope — a novelty verdict is only as strong as what was searched

```python
prov = gsl.CompositePriorArtProvider([gsl.ArxivPriorArtProvider(), gsl.OpenAlexProvider()])
v = gsl.prior_art_audit("my idea", prov)
print(v.scoped_verdict(), v.novelty_scope)
```

- no online provider → `LOCAL_ONLY` (capped at `WEAKLY_NOVEL`; cannot yield strong novelty);
- providers configured but all failed → `INCOMPLETE_ONLINE_SEARCH` (reported, never faked);
- at least one source answered → `ONLINE_PRIOR_ART_CHECKED` (the only scope under which
  `PROVISIONALLY_NOVEL_ON_CHECKED_SOURCES` is allowed — still **not** absolute novelty).

### LLM-in-the-loop with real verification

The heuristic runtime proposes structure but often ends `NOT_MATERIALIZED` — nobody writes the test/patch. The
LLM loop closes that: an LLM writes a **failing test** and a **minimal patch** as unified diffs; the library
applies them to the repo **transactionally** and **runs them**; a candidate cannot win unless its new test
failed for the **right reason** (`RED_ASSERTION`, not a broken-import `RED_COLLECTION`) before the patch and
went **GREEN** after a patch that changes real source (not one that skips/weakens the test). The winner is
chosen by an external, decomposed `llm_evidence_score`, never by the LLM.

```python
llm = gsl.CallableLLMProvider(my_model)            # or gsl.SubprocessLLMProvider("my-llm-cli")
res = gsl.llm_openended_search("invent X", llm, repo_path=".", budget=30, materialize=True)
print(res.markdown())
```

It is fully opt-in (no `llm` ⇒ nothing else changes), needs no network and no runtime dependency, and refuses
untrusted model output (bad JSON, an escaping patch, a shell operator in a command). It is a disciplined search
kernel, **not** an agent.

---

## Hard-problem frontier (open problems, partial certified results, never regress)

For genuinely hard OPEN problems (prime gaps, number-theory conjectures), the unit of progress is not a proof
of the conjecture — it is a **monotone sequence of partial results, each settled by an external resolver**, that
only ever moves toward the objective. The non-negotiable rule: **the engine never prints "PROVED" on an open
conjecture.** The honesty layer is what makes the progress real; scope expands, the claim never does.

```python
import OUTLIER_MCB as gsl
from OUTLIER_MCB.math_discovery import Conjecture
from OUTLIER_MCB.frontier_search import frontier_search, LemmaCandidate

# a sieve aimed straight at gap = 2 is a proven-dead route (the parity problem) — judge refuses it
j = gsl.judge("a classical Selberg sieve for twin primes at gap 2", pack=gsl.get_pack("number_theory"))
assert j.verdict == "DEAD_BY_BARRIER"            # and j.barrier names the admissible exits

# advance a monotone, externally-certified frontier; a false sub-lemma is killed by a counterexample
report = frontier_search("twin_prime_gap", candidates=[...LemmaCandidate(...)...],
                         objective_metric="H", objective_value=2)
print(report.markdown())                          # parent stays CONJECTURE — never PROVED
```

The pieces (each pure-Python, deterministic, with a RED→GREEN test + a negative control):

| module | role |
|---|---|
| `packs/number_theory.py` | the hidden assumptions of the standard sieve attack on prime gaps (Selberg / GPY / Maynard–Tao / large sieve); IT/EN routing |
| `barriers.py` | no-go theorems as a kill gate — the **parity problem** marks a sieve-for-gap-2 `DEAD_BY_BARRIER` and names the exits (integrated into `judge`) |
| `frontier_ledger.py` | a monotone frontier: a claim is accepted only if it carries a valid **external certificate** AND strictly improves; regressions and uncertified claims are rejected |
| `math_discovery.settle_lemma` | settle a partial **lemma** to `Z3_PROVED` / `LEAN_CHECKED` / `NUMERIC_VERIFIED` (exhaustive over a finite domain, zero-dep) — never `PROVED` on the parent |
| `frontier_search.py` | the loop: skip dead routes → settle survivors → advance the frontier → turn each failure into the next assumption to break |
| `evals/frontier_regression.py` | a CI invariant that **fails** if a change lowers a certified result or admits an uncertified claim |

Run the end-to-end demo: `python examples/hard_problem_frontier.py`. z3 / Lean / SymPy stay **opt-in** and
degrade gracefully; the zero-dep numeric path settles decidable lemmas exhaustively (a real certificate, not
sampling). These are known techniques (Maynard–Tao, the parity problem) — the value is the engine's
*infrastructure for certified partial progress*, not a new theorem.

### Autonomous discovery — the inventor is the front door (measured)

```python
import OUTLIER_MCB as gsl
gsl.autonomous_discover("count binary trees", oracle=[1,1,2,5,14,42,132,429,1430,4862]).markdown()
# DISCOVERED — a holonomic recurrence (n+2)a(n+1)=(4n+2)a(n), verified on held-out terms, generalises to sisters.
```

The pipeline (`autonomous_discovery.py`) makes the INVENTOR the default: **mine the oracle for sparks** (holonomic
recurrences, modular patterns, asymptotics — `oracle_miner.py`, T1) → **grow the primitive alphabet** on demand,
a ratchet (`primitive_library.py`, T2) → **pivot the solution form** when one is impossible (closed-form →
recurrence → generating-function → asymptotic → algorithm → bijection → conditional-theorem, `solution_type_lattice.py`,
T4) → **certify the survivor externally** (the judge, downstream) → **acquire new information** on a stall (T3) →
**explore worsening detours** in a sandbox while the committed ledger stays monotone (`ScratchFrontier`, T5) →
**validate the mechanism by transfer** to manufactured sister-landscapes with a negative control (T6). A discovered
**reduction** `A ⟺ B` is a first-class `REDUCTION_ESTABLISHED` result (T8), distinct from PROVED and CONJECTURE.

`python -m evals.discovery_battery` — the primary metric is DISCOVERY CAPABILITY: on a battery (holonomic +
non-holonomic) it discovers **6/6** (3 recurrences rediscovered, 2 non-holonomic **pivoted** to a certified
algorithm, 1 via the primitive ratchet), **0 false PROVED**. The **ablation** proves every creative stage is
load-bearing — remove the pivot and it drops to 4, remove the ratchet and it drops to 5. Honesty (no false PROVED,
committed monotone) is the constraint that keeps those discoveries real, not the point of the exercise.

### External prover / CAS backends — a portfolio, opt-in, three levels (A / B / C)

Every result is certified ONLY by an EXTERNAL resolver (never self-judgment). Each backend obeys one contract —
`prove(conj) -> (status, counterexample|None, detail)` with `.backend_name` — and **degrades to `TOOL_UNAVAILABLE`
if its tool is not installed** (detected with `shutil.which`, run via `subprocess` with a timeout and an argv list,
never `shell=True`, deterministic). No new runtime dependency is mandatory.

| level | backend | tool | decides | certificate |
|---|---|---|---|---|
| **A — automatic (SMT)** | `z3_backend` | Z3 | decidable arithmetic, ∀ via UNSAT(¬claim) | `Z3_PROVED` / `Z3_REFUTED` |
| **A — automatic (SMT)** | `cvc5_backend` | cvc5 | a 2nd SMT engine (different theories) — closes what z3 leaves unknown | `CVC5_PROVED` |
| **A — automatic (ATP)** | `atp_backend('vampire'\|'e')` | Vampire / E | first-order goals (quantifiers, relational axioms) via TPTP | `VAMPIRE_PROVED` / `E_PROVED` |
| **B — auto with a proof assistant** | `isabelle_backend` | Isabelle/HOL + Sledgehammer | the middle band: often closes a goal with NO hand-written proof | `ISABELLE_CHECKED` |
| **C — computational CAS** | `pari_backend` | PARI/GP | number theory over a **finite** box (isprime/forprime…) | `NUMERIC_VERIFIED` (finite domain only) |
| **B — proof assistant (by hand)** | `lean_backend` | Lean | a machine-checked, `sorry`-free proof | `LEAN_CHECKED` |
| **portfolio** | `portfolio_backend([...])` | any subset | runs the list in **fixed priority**, the first valid certificate wins (deterministic, records the winner) | the winner's certificate |

```python
import OUTLIER_MCB as gsl
port = gsl.portfolio_backend()                         # z3 → cvc5 → Vampire → E → Isabelle → PARI (absent ones skip)
cert = gsl.settle_lemma(lemma, backend=port)           # first external certificate wins; port.winner names the solver
```

**Honesty (non-negotiable):** a finite PARI/GP computation is a proof of that FINITE domain ONLY — an
unbounded/too-large domain returns `TOOL_LIMIT_UNKNOWN`, never `FORMALLY_PROVED`; an open conjecture (twin primes,
Riemann…) yields at most certified partial lemmas while the **parent stays `CONJECTURE`**. `python
examples/portfolio_demo.py` shows the portfolio closing a lemma z3-SMT alone cannot, the monotone frontier
advancing, and the parent never proved. `evals/solver_regression.py` is the CI guard: it FAILS if a certified
result drops, if a `FORMALLY_PROVED` appears without an external backend, or if an open conjecture is ever
certified. These provers are KNOWN tools — the value is the integration engineering, not a new theorem.

**Agnostic across ALL fields, not just math.** The same machinery attacks physics, biology, chemistry,
mechanics, ML, medicine, software — domain knowledge lives in **packs**, and a partial result is settled by the
domain's own external resolver. The certificate vocabulary (`certificates.py`) is agnostic: FORMAL
(`LEAN_CHECKED`/`ISABELLE_CHECKED`/`Z3_PROVED`/`CVC5_PROVED`/`VAMPIRE_PROVED`/`E_PROVED`/`NUMERIC_VERIFIED`, a proof) ·
EMPIRICAL (`SIMULATION_VERIFIED`/`EXPERIMENT_REPRODUCED`/
`DATASET_EVAL_PASSED`/`BENCHMARK_MEASURED`/`REPO_TEST_GREEN`, a reproducible measurement — honestly *not* a proof)
· META (`INVARIANTS_VERIFIED`). A `ResultCandidate` carries its own resolver `settle()`, so a physics simulation
or a wet-lab reproduction advances the monotone frontier exactly like a math lemma; barriers are agnostic too
(the **Second Law of Thermodynamics** kills a closed-system perpetual-motion route in the `physics` pack). See
`python examples/agnostic_domains_demo.py`. *That the engine works for every field is itself a protected
invariant* — a change cannot quietly make it math-only.

## Multi-metric self-improvement — raise EVERY skill, regress NONE (measured)

A single score can be chased for its own sake; this is the honest version. The library cycles on itself over a
**vector** of externally-certified performance dimensions and keeps a change ONLY under a **Pareto gate**
(`gsl.pareto_improves`): at least one dimension up, **none** down — it can never trade one skill away for
another (locked by the protected invariant `pareto_no_regression`).

```bash
python -m evals.multi_metric_loop       # 30 epochs over five orthogonal certified dimensions
```

Each epoch diagnoses the **weakest** skill (key-logs) and strengthens it; an **early stop** (`patience=10`) halts
at the ceiling with a **plateau report** (what's stuck, why, and the next orthogonal dimension to add). Measured
over five certified dimensions, all rose and none regressed: **symbolic-regression recovery 0.2778 → 0.9444**
(17/18 Feynman laws, Coulomb 1/r² recovered), **counterexample refutation 0.3333 → 1.0**,
**judge_calibration 0.625 → 1.0** (the JUDGE itself, measured on an external labelled adversarial set — overclaims
now blocked), **external_transfer 0.2 → 1.0** (recovery on a **HELD-OUT** substrate the primitives were never
designed for), and **curriculum_progression 0.2 → 1.0** (a **POET-like** dimension: the engine manufactures its
own increasing-difficulty problems and solves them) — so the **weakest skill went 0.2 → 0.9444**. The 6-line
improvement curve is in `REPORT_EN.pdf` / `REPORT_IT.pdf` (Section 5); Section 6 is an honest capability
comparison vs POET / Voyager / DreamCoder.

Both exploration dimensions are **anti-autoreferential**. A recursive self-improver's worst failure is to improve
a metric it designed itself, scored by its own internal number — a gain that means nothing outside the repo.
`OUTLIER_MCB/landscapes.py` makes the rule enforceable: a dimension may enter the main Pareto vector **only**
if its `Landscape` is externally anchored (`is_external_landscape` — provenance + external resolver + independent
ground truth + **negative control** + baseline); otherwise it is `INTERNAL_ONLY` and is refused. `external_transfer`
is settled on held-out data; `curriculum_progression` is settled by R²+SymPy on the generated problem's KNOWN
ground truth — and both have a **scrambled-target negative control** that must collapse the gain (proving it is
real solving, not leakage). `curriculum_progression` absorbs **POET**'s open-ended problem generation but
subordinates it to that tribunal: a manufactured problem counts only if it is externally settleable, and the
generated curriculum is orthogonal to the held-out transfer dimension (it rewards different primitives).

### Unlimited exploration — the open-ended ratchet (POET-level, made rigorous)

A fixed curriculum still saturates (`curriculum_progression` tops out at 1.0). POET is *unlimited* because it keeps
generating ever-harder problems over agents that keep improving — but POET's "solved" is the agent's own reward, a
**self-judgment**. OUTLIER_MCB takes the open-endedness and settles every problem **outside** the engine. A
sixth dimension, **`open_ended_reach`**, is an **unbounded ratchet**:

```bash
python -m evals.benchmarks.open_ended      # reach 2 → 9, each depth externally certified; lift the budget → further
```

For **every** depth `k` there is a generated problem (the k-way product) with KNOWN ground truth, and an
**expanding** primitive space (`product_k`, grown on demand). Admission uses POET's **minimal criterion** made
rigorous — a depth is admitted only if it is *novel* AND *unsolved-now* AND *externally settleable* (R²+SymPy) AND
its **scrambled-target negative control collapses**. `frontier_reach` is the deepest certified depth: monotone,
never regressing, with **no built-in 1.0**. In the multi-metric loop, once the five bounded skills saturate the
engine keeps exploring by growing `product_k` — it does **not** stop at the fixed-primitive-set ceiling; it stops
only at the **compute budget** (`reach_budget`), and the plateau report says so. That is the honest version of
"unlimited": no conceptual ceiling, bounded only by compute — and, unlike POET, every step is externally certified,
never self-judged.

When all bounded dimensions plateau, the rule is to add a new orthogonal externally-anchored dimension (next:
`causal_recovery`), never to optimize weights or invent an internal score.

**A 500-epoch run, reported honestly.** Asked for 500 epochs, the engine made **25 externally-certified
improvements** (11 bounded + 14 ratchet depths, `open_ended_reach` 2 → 16), regressed nothing, and **early-stopped
at epoch 35 — it did not pad to 500**. It stopped at the zero-dep linear-SR *well-posedness* limit (base terms grow
~k²/2 and must stay below the sample count), an honest substrate/compute ceiling — and the plateau report says so,
distinguishing it from a compute-budget stop. Raising `reach_samples` climbs strictly further (reach 16 at n=300 →
22 at n=600 → 26 at n=1000, √-scaling with compute). 500 *genuine* improvements are not available on this linear-SR
substrate, and the engine refuses to fabricate them — the number it reports is the real one.

## Recursive self-improvement — measured (0.357 → 0.857, never regressing)

The library cycles on itself to raise its own **verified-novelty fitness** on a concrete, externally-certified
substrate (the Feynman SR benchmark). Each epoch it diagnoses the bottleneck (key-logs), proposes a new basis
primitive for a form it has no example of (the *unknown zone*), and keeps it ONLY if the **data certify it**
(held-out R²>0.999 + exact SymPy form) and it strictly raises recovery — so the recovered set only grows, the
fitness **never regresses**, gaming is impossible (an external resolver settles every point), and the honest
zero-dep default basis is never mutated.

```bash
python -m evals.self_improve_loop        # 10 epochs; verified-novelty fitness 0.3571 → 0.8571 (5/14 → 12/14 laws)
```

It discovered new primitives (`ratio, triple_product, product_square, product_trig, gaussian, ratio_product,
inverse_square`), each certified on data, now a permanent opt-in capability: `gsl.grown_backend()` recovers far
more Feynman laws than the default — the documented default stays honestly limited.

When the 14-law substrate plateaued at 12/14, the limit was the *substrate*, not the metric: adding more
certified laws (`FEYNMAN_EXTENDED`) and the matching new primitives reopened headroom, and the loop climbed
again to **16/18** (`self_improve(equations=FEYNMAN_ALL)`: 0.2778 → 0.8889) — strictly additive, never
regressing. The per-epoch improvement curve and trajectory are in `REPORT_EN.pdf` / `REPORT_IT.pdf`.

## A fitness for self-improvement that cannot be gamed — VERIFIED-novelty

What signal should the library maximize when cycling on itself? Asked to design it, the library rejected the
obvious answer: a richer internal composite (`novelty × diversity × …`) is judged INSIDE_THE_BOX — a
re-parameterization of *add more metrics*, and **gameable** (a loop that maximizes a self-judged score learns to
hack the score). The break the engine pointed at is `the_engine_judges_itself`: **only an external resolver
certifies.** So the fitness is one ungameable number:

```python
import OUTLIER_MCB as g
# the fraction of proposals that BOTH break a known box AND survive an EXTERNAL resolver
fitness = g.verified_novelty_fitness(proposals)     # self-judged novelty NEVER counts
g.evolutionary_self_repair(repair, measure=lambda: g.verified_novelty_fitness(state["pop"]))
```

`verified_novelty` carries its own anti-gaming ablation (`novelty_only_rate` vs the verified rate — the gap is
how much self-judgment would inflate), and a protected invariant
(`fitness_requires_external_verification`) locks the anti-circularity. Wired as the `measure` in
`evolutionary_self_repair`, it lets the library improve itself under the two gates that can never be removed:
never break a protected invariant, never regress. **Padding with self-judged novelty lowers the verified rate, so
the loop refuses it — gaming is structurally impossible.** Demo: `python examples/verified_novelty_fitness_demo.py`.

## Self-diagnosis & evolutionary self-repair (alive, never regresses)

When a task is NOT finished, the post-mortem is the asset. The engine drops diagnostic **point-logs** during a
run into a **separate diagnostic memory**, mines them with `self_diagnose` (weak spots, the bottleneck), and may
then try to **repair itself** — under two non-negotiable gates: it keeps a fix only if **every protected
invariant still holds** AND the health metric **did not regress** (re-measured, not assumed). Otherwise it rolls
back and records the failed attempt as a new diagnostic point (a failure is information, never discarded).

```python
import OUTLIER_MCB as gsl
mem = gsl.DiagnosticMemory()
with gsl.diagnostic_run("bounded prime gaps", memory=mem) as log:
    gsl.frontier_search("twin_primes", candidates=[...], objective_metric="H", objective_value=2, log=log)
print(gsl.self_diagnose(mem).markdown())          # → bottleneck phase + weak spots + next lever
print(gsl.verify_invariants().markdown())          # → the SOLID, untouchable behaviors (must all hold)

res = gsl.evolutionary_self_repair(proposal, measure=health_fn)   # accepted ONLY if no invariant breaks AND no regression
```

The **protected invariants** are the explicit «solid things that must not be touched» (`INVARIANT_REGISTRY`):
the four entrypoints exist, the engine never claims PROVED on an open conjecture, the frontier rejects
regressions, a deterministic offline distance exists, the parity barrier still fires. An accepted improvement is
recorded on the monotone frontier (`INVARIANTS_VERIFIED`), so the engine's health can only move forward across
self-repairs. Demo: `python examples/self_repair_demo.py`. The repair *proposal* is supplied by the caller/LLM —
the spark is external, the two gates (never regress, never break a solid invariant) are the machine's.

**The LLM interviews the library first.** Before proposing a patch, the LLM calls `repair_brief(memory)` to get
the engine's feedback on *what* and *how* to fix — the bottleneck, the candidate levers, and the hard
constraints (the protected invariants it may never break, plus never-regress). It then decides if the diagnosis
is right and acts; `evolutionary_self_repair` enforces the very constraints the brief listed, regardless.

## Official benchmark (certified ground truth) — what the verifiable SR component actually recovers

Beyond the bundled self-eval, the library's symbolic-regression component is measured against an **external,
official benchmark with certified ground truth**: the **Feynman Symbolic Regression Database** (Udrescu &
Tegmark, *AI Feynman*, Science Advances 2020), the de-facto standard adopted by **SRBench** (La Cava et al.,
NeurIPS 2021). The ground truth is the *published physics equation* — not ours. We follow SRBench's two criteria:
the *accuracy solution* (test R² > 0.999) and the stricter *symbolic solution* (SymPy equivalence).

```bash
python -m evals.benchmarks.feynman          # runs the benchmark, prints the per-equation table
```

Measured result, on a documented subset of 14 of the 100 Feynman equations (deterministic, zero-dep):

| metric | result |
|---|---|
| **symbolic solutions** (exact form, SymPy) | **5 / 14** — `μ·Nn`, `q2·Ef`, `3/2·pr·V`, dot product, `sin(x)+2y` |
| accuracy solutions (R² > 0.999) | 6 / 14 · median R² 0.9985 |

**Honest scope (read this).** The zero-dependency SR is *linear-in-basis* (it fits Σ coeff·term over a basis a
broken assumption unlocks: products `x_i·x_j`, sums of squares, single-variable `sin/cos`, simple ratios). So it
**exactly recovers the algebraically-simple Feynman equations and honestly fails** the transcendental / true
division / ≥3-way ones (Gaussian, Coulomb `1/r²`, `q/C`, `m·g·z`) — those need an external backend (PySR/gplearn),
wireable via `symbolic_evaluator(backend=…)`. The table separates a true symbolic recovery from an accuracy-only
approximation (e.g. `I.10.7` passes R²>0.999 with a linear fit but is *not* the right form — shown as such). No
cherry-picking, no inflation: the failures are reported. A second official benchmark applies to the (preliminary)
causal component — the **Tübingen cause-effect pairs** (MPI Tübingen, 108 pairs, human-labelled direction; best
published methods ≈ 80–83%) — and is a documented next target (requires the official dataset).

## Evaluation (bundled, deterministic, offline)

The repo ships an offline eval harness. **Read the limits first:** it measures *structure* (are ideas
falsifiable, distinct, grounded, correctly routed?), **not** human-judged quality; and its baselines are
deterministic stand-ins, **not** a real LLM — so the numbers compare *the scaffold against simpler scaffolds*,
not against a strong model. A model-in-the-loop comparison is out of scope for an offline harness.

```bash
python -m evals.run_eval                  # BASE / CHECKLIST / GSL_PREFLIGHT / GSL_FULL on the bundled dataset
python -m OUTLIER_MCB.cli readiness    # the project's internal go/no-go gate
```

On the bundled dataset, `GSL_FULL` scores higher than a bare prompt on every structural metric (falsifiability,
artifact specificity, routing, rebrand-avoidance); the per-mode table and the open-ended ablations
(`GSL_NO_QD_ARCHIVE`, `GSL_NO_DIVERGENCE`, `GSL_NO_PRIOR_ART`) are in [`evals/`](evals/) and reproducible with
the commands above. These results say the components are non-decorative on this harness; they do **not** claim
state-of-the-art creativity.

---

## Public API

A deliberately small front door (`gsl.__all__`); everything else is a documented building block in
`gsl.__toolbox__`.

| entrypoint | use |
|---|---|
| `creative(prompt)` | the brief — which assumption to break |
| `judge(idea, …)` | discipline a free-text idea (`INSIDE_THE_BOX` vs `MUST_BE_AUDITED`) |
| `invent(prompt, repo_path=…)` | the runtime — a scored, settle-able portfolio |
| `green_star(prompt)` | the no-examples zone — first-principles hypotheses |
| `readiness_report()` | the internal go/no-go gate |

## Development

```bash
pip install -e ".[test]"
python -m pytest -q
```

## Citing

If this project is useful in your work, please cite it — see [CITATION.cff](CITATION.cff) (GitHub renders a
"Cite this repository" button from it).

## Keywords & topics

For discovery by people, search engines, and AI assistants: assumption-negation, falsification engine,
disciplined creativity, invention, discovery, novelty detection, prior-art search, hypothesis testing,
scientific method, epistemics, claim verification, honest AI, LLM tools, AI agents, agentic reasoning,
program synthesis, symbolic regression, quality-diversity, MAP-Elites, open-endedness, automated discovery,
active learning, domain-agnostic, zero-dependency, typed Python.

_Suggested GitHub topics:_ `creativity` `falsification` `invention` `discovery` `novelty-detection`
`prior-art` `llm` `ai-agents` `agentic` `reasoning` `scientific-method` `program-synthesis`
`quality-diversity` `open-endedness` `symbolic-regression` `automated-discovery` `epistemics`
`active-learning` `python` `research-tool`.

## License

MIT — see [LICENSE](LICENSE). You are free to use, modify, and distribute it with attribution; the software is
provided "as is", without warranty. Third-party methods and papers the design engages with are cited in
["Related work and how OUTLIER_MCB differs"](#related-work-and-how-outlier_mcb-differs) — the library
ships no third-party code or corpus, and treats "no prior-art match found" as an incomplete search, never as a
proof of novelty.
