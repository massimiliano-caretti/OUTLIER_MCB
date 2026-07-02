# Changelog

All notable changes to OUTLIER_MCB are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project uses semantic versioning.

## [2.1.0]

### Added — composed loop, earned taste, and a self-describing capability index
- **`autonomous(prompt, …)`** — one composed scientific loop that orchestrates every capability as optional
  tracks (incubate → invent with learned taste & transformational axis growth → settle via a synthesized
  evaluator + red-team + a calibrated verification economy → represent → disambiguate via active experiments →
  record). Each track runs only when its input is present; the result names the capabilities that actually ran.
- **`EarnedTaste`** — a calibrated value over *unverified* ideas, learned from externally-settled outcomes only
  (never self-judgment). **`VerificationEconomy`** — cheap, calibrated proxies that confirm only where precise
  and escalate everything else, so a pass is never fabricated. **`incubate` / `run_active_experiments` /
  `invent_representation`** — offline reconnection of dead-ends, information-acquiring experiments, and
  control-gated representation invention.
- **`capabilities()` / `capabilities_markdown()`** — a single self-describing index of every entry point, and
  **`assistant_route()`** — a compact per-turn router (English + Italian) so an assistant can drive the whole
  engine automatically. `assistant_brief` now points to both.
- **Creativity frontier (proof-of-concept, toy domains, clearly labelled):** invent a toy "physics"
  (`propose_new_physics`, scored by emergent structure), coin an endogenous concept (`ground_new_symbol`, scored
  by MDL compression), invent a primitive-set DSL (`invent_new_language`, scored by expressive power), and
  measure objective aesthetics (`elegance_score`). Each has an external metric with a negative control and a
  protected honesty invariant (now 13, all passing); registered as Pareto dimensions under the strict
  no-regression gate.

### Fixed
- Logic bugs found by an independent audit of the new modules: aesthetic surprise now reads the real operator
  (was constant); emergence penalises trivial oscillators; a lone hypothesis with no observation is not
  "resolved"; `shortest_program` returns the empty program and respects its bound; `cost_saving` runs the real
  resolver once per case; taste dilutes toward neutral for unproven feature-stuffing.

### Packaging
- Expanded keywords, real repository URLs, `CITATION.cff`, README badges and a keywords/topics section.

## [Unreleased]

### Added — three COMPLEMENTARY discovery axes (chosen using the library on itself: it measured its own blind spots)
Asked the library which new representation axes would add the most exploratory power, then measured empirically WHICH
canonical sequences the current discoverer finds NO structure for — those are the real gaps. `judge` ruled the
additions INSIDE_THE_BOX (engineering, not novelty); the justification is the measured coverage gain, orthogonal to
the existing additive-recurrence axes. Each axis is held-out verified with a negative control:
- **Axis 1 — MULTIPLICATIVE / number-theoretic** (`guess_multiplicative`): detects `a(m·n)=a(m)·a(n)` for coprime
  m,n (so the sequence is set by its values on prime powers) — Euler φ, divisor σ/d, μ. Requires `a(1)=1` and many
  verified coprime pairs. Negative controls: primes, Fibonacci → None. Was: the library found NOTHING on φ/d(n).
- **Axis 2 — ASYMPTOTIC with a certified band** (`guess_asymptotic`): fits `n^α / n·log n / rⁿ / exp(c√n)` and
  CERTIFIES that `a(n)/model` stays in a tight band on held-out terms — a real growth law where exact structure is
  absent. Turns "primes → ALGORITHM" into "primes ~ 1.92·n^1.22, band [1.02, 1.04]" (fills the `ASYMPTOTIC_WITH_BAND`
  lattice rung that had no miner). Honestly approximate — a band, not an exact law. Negative control: a bounded
  sequence (Thue-Morse) → None.
- **Axis 3 — k-AUTOMATIC / digit axis** (`guess_k_automatic`): detects a finite automaton on the base-k digits of n
  (`a(k·n+r)=f_r(a(n))`, small value alphabet) — Thue-Morse gives exactly `a(2n)=a(n), a(2n+1)=1−a(n)`. Rejects the
  all-identity (mere periodicity) and large-alphabet cases. Negative control: primes → None.
- **Honesty refinement**: the non-linear miner now REJECTS a degenerate single-position relation like `a(n)²=a(n)`
  ("the values are binary" — true but trivial); a real invariant must couple ≥2 distinct window positions. So
  Thue-Morse now reports its actual 2-automaton, not the trivial idempotent law.
- Wired into `mine_invariants` (order: closed-form → holonomic → multiplicative → k-automatic → non-linear →
  algebraic → asymptotic) and `autonomous_discover` (`MULTIPLICATIVE` / `K_AUTOMATIC` / `ASYMPTOTIC_WITH_BAND`
  forms). Battery extended (euler_phi, thue_morse): **10/10 discovered, 0 false PROVED**, ablation intact.
  `tests/test_discovery_inventor.py` adds per-axis tests + negative controls; invariants 8/8.

### Added — the oracle miner breaks out of the linear box (agnostic, held-out verified)
- `oracle_miner.guess_polynomial_recurrence`: searches the NON-LINEAR space — polynomial (Somos-like)
  recurrences among `a(n)..a(n+order)` of total degree >= 2 with `n`-polynomial coefficients. Finds laws
  holonomic guessing structurally cannot (positive control: Somos-4); returns None on structureless input
  (negative controls: primes, perturbed Somos). Domain-agnostic — any integer oracle.
- `oracle_miner.guess_algebraic_gf`: searches whether the ordinary generating function is ALGEBRAIC of low
  degree, `P(x,y)=0` (positive control: Catalan; negative control: primes).
- Both wired into `mine_invariants` (new `MinedSparks.polynomial` / `.algebraic` fields) so every oracle,
  in any domain, is now swept across holonomic, non-linear, and algebraic structure — not just linear.
- Tests: `tests/test_polynomial_recurrence.py` (positive + negative + perturbation controls).

#### Follow-up — wired into the DEFAULT pipeline + a new closed-form space + an honest generative/invariant split
A review (using the library on itself; `judge` ruled both INSIDE_THE_BOX — engineering, not novelty) found the
non-linear space worked in isolation but NOT through the default `mine_invariants` / `autonomous_discover`
(default `max_order=3 < 4`, and too few terms). Fixed and extended:
- **Pipeline wiring**: `mine_invariants` now sweeps the non-linear (`max_order=4`) and algebraic spaces with MORE
  terms (they need more data than the linear one), so the discoverer actually FINDS Somos-4 by default — verified
  by a pipeline-level test, not only a hand-tuned call.
- **New space `guess_polynomial_closed_form`** (+ `MinedSparks.closed_form`): detects an explicit polynomial
  `a(n)=poly(n)` via exact rational fitting + held-out reproduction — the CLOSED_FORM top of the solution lattice,
  tried FIRST. Negative controls: Catalan/primes yield no false closed form.
- **Honest generative vs invariant split**: a non-linear relation LINEAR in the leading term is a GENERATIVE
  recurrence (`NONLINEAR_RECURRENCE`, e.g. Somos); one quadratic in it is a certified STRUCTURAL INVARIANT
  (`STRUCTURAL_INVARIANT`, e.g. `floor(nφ)`: consecutive differences ∈ {1,2}, verified on 79 further terms) — a real
  law, honestly NOT labelled a full solution. `PolynomialRecurrence.is_generative` decides.
- **Held-out margin strengthened** 2 → 4 in the non-linear/algebraic miners (spurious fits rejected on more unseen
  terms). `autonomous_discover` reports the strongest certified form (closed-form → recurrence → non-linear/
  invariant → algebraic-GF → pivot). Battery extended (cubic closed-form + Somos-4): 8/8 discovered, 0 false PROVED,
  ablation still shows every creative stage load-bearing. `tests/test_discovery_inventor.py` adds the pipeline-level
  + no-hallucination tests.

### Added — the INVENTOR is the front door: `autonomous_discover` (the judge becomes a downstream service)
Re-centres the library on its identity — a DISCOVERER/INVENTOR — with external certification as a *service* that
makes an invention real, not a gate that reduces everything to CONJECTURE. `judge` certified the core move
(**MUST_BE_AUDITED, breaks `evaluation_is_fixed`**): the oracle becomes a SOURCE OF SPARKS, not only a refuter.
Substrate: integer-sequence discovery (concrete, deterministic, zero-dep). Fixes the eight trap that were silencing
the inventor:
- **T1 `oracle_miner.py`**: mines candidate invariants from exact oracle values — a **holonomic (P-recursive)
  recurrence** guessed by rational linear algebra and VERIFIED on held-out terms, plus modular patterns and an
  asymptotic ratio. Honest: a non-holonomic sequence (primes) yields NO recurrence rather than a hallucinated one.
  It rediscovers Catalan's recurrence `(n+2)a(n+1)=(4n+2)a(n)` from 8 terms.
- **T2 `primitive_library.py`**: a self-expanding alphabet — the engine composes and ABSTRACTS primitives on demand
  (DreamCoder-style), so invention is a RATCHET. A target unreachable at composition depth 1 is solved at depth 2
  and then depth 1 after abstraction — the alphabet grows by itself.
- **T4 `solution_type_lattice.py`**: when a form is impossible, PIVOT the objective to the next real form
  (closed-form → recurrence → generating-function → asymptotic-with-band → algorithm → bijection → conditional
  theorem) instead of stopping at CONJECTURE. Every form is a legitimate discovery.
- **T3 `acquire_new_information`**: query the oracle for MORE terms than the current representation holds — the move
  that raises the ceiling when ricombining the known is not enough.
- **T5 `ScratchFrontier`**: a creative sandbox where a WORSENING detour is allowed (escape a local optimum); only
  the committed record stays monotone, so nothing real is lost.
- **T6 `mechanism_generalizes`**: validate a discovered MECHANISM by TRANSFER to manufactured sister-landscapes with
  known ground truth (+ a scrambled-input negative control) — creativity certified by transfer, not self-vote.
- **T7 `autonomous_discover(problem, oracle, budget)`**: the inventor-first orchestrator wiring T1→T2→T4→external
  certification (the judge, downstream)→T3 on stall→T5 detour→T6 transfer. On success it returns a DISCOVERY.
- **T8 `certify_reduction`** + `DISCOVERY_STATES`: a discovered REDUCTION (A ⟺ B, externally checked with a negative
  control) is `REDUCTION_ESTABLISHED` — a first-class result distinct from PROVED and CONJECTURE.
- **Primary metric — `evals/discovery_battery.py`**: DISCOVERY CAPABILITY on a battery (holonomic + non-holonomic).
  Measured: **6/6 discovered** (3 recurrences rediscovered, 2 non-holonomic PIVOTED to a certified ALGORITHM, 1 via
  the primitive ratchet), **0 false PROVED**. The **ablation** shows every CREATIVE stage is load-bearing: full 6 →
  no-pivot 4 → no-ratchet 5 (the discovery count drops when a creative stage is removed — it is the creativity, not
  the judge, that finds things). `tests/test_discovery_inventor.py` pins T1–T8 with negative controls.
- Honesty preserved: no false PROVED, the committed ledger never regresses, invariants 8/8; suite 660 → 674. The
  library's success message is now a DISCOVERY, not a defence. README/SPEC reframed: discoverer first, judge as a
  service subsystem.

### Added — external prover / CAS backends + a deterministic solver portfolio (levels A/B/C)
More external safety nets to CLOSE more lemmas (open → certified) without ever cheating or regressing. Every backend
obeys the existing contract (`prove(conj) -> (status, counterexample|None, detail)`, `.backend_name`), is OPT-IN,
and degrades to `TOOL_UNAVAILABLE` when its tool is absent (`shutil.which` detection; `subprocess` with a timeout
and an argv list; never `shell=True`; deterministic). `judge` ruled the design INSIDE_THE_BOX — correct and honest:
these are KNOWN tools; the value is the integration engineering, not a new theorem.
- **`_solver_common.py`**: safe plumbing shared by the backends — `which`, `run_tool` (no-shell subprocess with a
  hard timeout), and `ast`-based compilers from the Python-infix arithmetic fragment to **SMT-LIB**, **TPTP TFF**,
  and **PARI/GP** (the last passes number-theory functions like `isprime` through). The compilers are unit-tested
  WITHOUT any binary, so the translation is verified even where the tool is not installed.
- **`cvc5_backend`** (G3): a 2nd SMT solver in portfolio with z3 (same ¬claim strategy) → `CVC5_PROVED`.
- **`atp_backend('vampire'|'e')`** (G4): first-order ATPs via TPTP; SZS-status parsing → `VAMPIRE_PROVED`/`E_PROVED`.
- **`isabelle_backend`** (G1): Isabelle/HOL + Sledgehammer — the middle band between automatic (z3) and by-hand
  (Lean); a clean machine-checked build → `ISABELLE_CHECKED`. `emit_isabelle_theory` is exported and unit-tested.
- **`pari_backend`** (G2): PARI/GP over a FINITE integer box (number theory) → `NUMERIC_VERIFIED`. HONESTY: an
  unbounded/too-large domain returns `TOOL_LIMIT_UNKNOWN` — a finite computation is NEVER a proof of an infinite
  conjecture (tested without the binary).
- **`portfolio_backend`** (G5): runs a FIXED-priority list (z3 → cvc5 → Vampire → E → Isabelle → PARI); the first
  valid certificate wins; it mutates `.backend_name` to the WINNER so `settle_lemma` records that solver's real
  certificate; `.winner`/`.trace` for diagnosis. Deterministic (priority, not wall-clock). Verified: it closes a
  lemma z3 alone leaves unknown (a stand-in solver decides) → the certificate is the winner's, not a generic label.
- **G6 — certificates**: `certificates.py` FORMAL set + `RESOLVER_KINDS` and `math_discovery.LEMMA_CERTIFIED` gain
  `ISABELLE_CHECKED`/`CVC5_PROVED`/`VAMPIRE_PROVED`/`E_PROVED` (PARI reuses `NUMERIC_VERIFIED`); `settle_lemma` maps
  each backend to its certificate via a table. `FrontierLedger` accepts them as external evidence automatically.
- **G7 — anti-regression guard**: `evals/solver_regression.py` + `tests/test_solver_regression.py` FAIL if the
  portfolio closes fewer baseline lemmas, if a `FORMALLY_PROVED` appears without an external certificate, or if an
  OPEN conjecture is ever certified. «Never regress» is now a test, not a promise.
- **G8 — demo**: `examples/portfolio_demo.py` drops barrier-killed routes, sends sub-lemmas to the portfolio,
  advances the monotone frontier with the certified winners, and shows the parent staying `CONJECTURE` (never PROVED).
- **Invariant kept, not weakened**: `never_proves_open_conjecture` is now SEMANTIC — every certified lemma status
  must be a registered external FORMAL certificate and there is no bare parent `PROVED` — so the vocabulary can grow
  with real external provers while the honesty guarantee holds. Suite 633 → 660 (4 skip where a tool is absent);
  invariants 8/8. In THIS environment only z3 is installed, so the new backends' proof paths are exercised via the
  unit-tested compilers + the portfolio (fake stand-ins) + graceful `TOOL_UNAVAILABLE`; installing the tools lights
  up their world-tests unchanged.

### Fixed — library-assisted code audit (script-by-script, verified by external tools + the engine on itself)
A full audit (pyflakes + py_compile + repo-wide dead-code scan + four parallel line-by-line reviewers, each finding
verified by EXECUTING the code) surfaced real defects. The codebase was already clean (0 bare-excepts, 0 mutable
defaults, 0 `== None`, 0 unreferenced public functions); these are the genuine bugs found and fixed, each pinned
by a regression test in `tests/test_audit_fixes.py`:
- **HIGH — the Pareto gate crashed / silently accepted on a key-set change** (`verified_novelty.py:pareto_improves`).
  A dimension missing from `new` raised `KeyError` (the worst regression — a dropped skill — went uncaught); an
  extra new dimension was ignored, so a change could be "accepted" while a brand-new skill sat at 0.0. Now a
  dropped/regressed dimension is rejected (never crashes) and a bare new dimension can't game the gate. The core
  anti-regression guarantee was accidental (safe only because `measure()` emits fixed keys); now it is enforced.
- **HIGH — the scrambled-target negative control was VACUOUS** (`evals/benchmarks/open_ended.py`). Both resolvers
  ended `return scramble is False and …`, so under `scramble=True` they returned `False` UNCONDITIONALLY — the
  leak-detection guards in `admit`/`curriculum_recovery_map` could never fire, and the negative-control tests
  passed on a tautology. Fixed so a scrambled fit that STILL hits R²>0.999 is reported as a leak; verified the real
  rungs genuinely collapse (scrambled held-out R² ≈ −0.47, earned) and added a **variance guard** so a degenerate
  constant-target problem (where `_r2` inflates and `reversed(y)==y`) is refused as not-settleable.
- **HIGH — closure detectors matched SUBSTRINGS, not tokens** (`closures.py`). `"assume"` fired `"sum"`,
  `"meaningful"` fired `"mean"` → genuinely novel readouts were mislabelled `INSIDE_THE_BOX` and rejected (consumed
  by `judge`/`scoring`). Now whole-token matching (lookaround on alphanumerics); genuine mentions still detected.
- **MEDIUM-HIGH — `judge()` contradicted its own gate** (`judge.py`). An idea breaking NO assumption became
  `MUST_BE_AUDITED` merely for containing a common word (`predict`/`score`/…) via `_NEW_OUTPUT_HINTS`, while the
  internal no-solution gate said `INSIDE_THE_BOX`. Now MUST_BE_AUDITED requires an actual broken assumption.
- **MEDIUM — `novelty_score([])` read as LOCAL novelty (0.4)** (`kernel.py`). The irreducibility credit wasn't
  gated on a broken axis, so breaking nothing scored 0.4. Now the +0.3 requires `breaks`.
- **MEDIUM — `VERIFIED_USEFUL_NOVELTY` survived a non-online scope** (`novelty.py`). The honesty downgrade only
  fired for `PROVISIONALLY_NOVEL`; a passing verifier under `LOCAL_ONLY`/`INCOMPLETE_ONLINE_SEARCH` still printed
  the strongest label (contradicting its own "novelty NOT established" warning). Now that label is also downgraded.
- **MEDIUM — `self_evolve` claimed it applied patches when it never does** (`self_evolve.py`). With `dry_run=False`
  it printed "applied only the patches whose tests passed" though `applied` is always empty (no apply path). The
  messaging + docstring are now honest: it proposes only.
- **LOW — cleanups:** dead `_default_runner` exposed as `default_runner` + corrected `code_evaluator` docstring
  (it claimed a default real runner that was never wired); removed dead `patches._removed`; added `Dict` to
  `analogy.py`'s typing import (a latent `get_type_hints` NameError); dropped three unused imports flagged as
  possible wiring bugs (`orchestrator.blend_emergence`/`Dict`, `invent.recombine_assumptions` — verified NOT
  wiring bugs: the values are already carried on `problem.components` / applied inside `generate_candidates`).
- **Verified NO defect (checked, reported for the record):** frontier monotonicity, all 8 protected invariants
  (each a real, non-vacuous predicate), the prior-art verdict thresholds/branch order, `gate_claim_language`
  (no strong-word path escapes its gate), `frontier_reach` on non-contiguous depths, `admit`'s unsolved-now
  criterion, cascade edge-direction, and `evolutionary_self_repair`'s rollback-on-regression. Suite 626 → 633.

### Measured — a 500-epoch self-improvement run (honest: no padding, no inflated numbers)
Ran the library's own `multi_metric_self_improve(epochs=500)` and reported EXACTLY what happened. The engine made
**25 externally-certified improvements** (11 bounded + 14 ratchet depths, `open_ended_reach` 2 → 16), regressed
NOTHING, then **early-stopped at epoch 35** — it did NOT pad to 500. It stopped because the ratchet hit the
zero-dep linear-SR **well-posedness** limit (base terms grow ~k²/2 and must stay below the sample count), an HONEST
substrate/compute ceiling, not a conceptual one. With `reach_samples` raised the ratchet climbs strictly further
(reach 16 at n=300 → 22 at n=600 → 26 at n=1000 — √-scaling with compute), confirming the mechanism is unbounded
and only the substrate/compute bounds it. **500 genuine improvements are not available on this linear-SR substrate
and the engine refuses to fake them** — the number reported is the real one.
- **`evals/multi_metric_loop.py`**: added a `reach_samples` parameter (default 300) so a heavier compute budget
  lets the ratchet certify deeper depths; the plateau report now DISTINGUISHES a stop at the compute budget
  (`reach == reach_budget`, liftable) from a stop BELOW it (the well-posedness wall — flagged as an honest
  substrate ceiling, not a conceptual one, and not misreported as a budget stop).
- **`tests/test_multi_metric_loop.py`**: `test_reach_stopping_below_budget_is_flagged_as_honest_substrate_ceiling`
  asserts the report states the real reason it stopped (no number inflation).

### Added — UNLIMITED exploration: `open_ended_reach`, an unbounded ratchet (POET-level open-endedness, made rigorous)
`curriculum_progression` (previous cycle) saturates at 1.0 — a fixed list over a fixed primitive set has a ceiling,
so the engine explored MORE but not "unlimitedly" like POET. This cycle removes the ceiling. `judge` (meta pack)
approved the plan: **MUST_BE_AUDITED, breaks `benchmark_ceiling_is_fixed` (confidence 1.0)**, axis EXPLORATION,
maturity SUSPENDED_BOLD → it demanded the falsifier (an `unbounded_generator` + external resolver), which this
cycle builds. **Why POET is unlimited and how we match it WITHOUT its autoreferentiality**: POET keeps an
ever-growing problem population admitted by a minimal criterion (novel AND solvable-at-the-frontier) over agents
that keep improving — but POET's "solved" is the agent's own reward (a self-judgment). We take the open-endedness
and settle every problem OUTSIDE the engine.
- **`OUTLIER_MCB/grown_basis.py`**: `product_k_builder(k)` — an UNBOUNDED primitive family (the k-way product,
  for ANY k). The primitive space is no longer the eight discovered families; it EXPANDS on demand.
- **`evals/benchmarks/open_ended.py`**: the ratchet. `product_problem(k)` (a generated depth-k problem with KNOWN
  ground truth, one for every k), `solves_depth` (external resolver R²+SymPy, `scramble` = negative control),
  `admit` (POET's **minimal criterion** made rigorous: novel AND unsolved-now AND externally settleable AND its
  scrambled control collapses), `frontier_reach` (the RATCHET metric — deepest certified depth, monotone, no
  built-in 1.0), and `open_ended_ratchet(reach_budget)` which climbs reach 2 → N, growing `product_k` per depth,
  each externally certified. `python -m evals.benchmarks.open_ended` reaches depth 9 and further as the budget rises.
- **`OUTLIER_MCB/packs/meta.py`**: assumption `benchmark_ceiling_is_fixed` + `unbounded_generator` info-kind,
  so the JUDGE distinguishes a saturating score (a fixed ceiling) from a true ratchet.
- **`evals/multi_metric_loop.py`**: `open_ended_reach` wired as the 6th Pareto dimension (an integer depth, excluded
  from the [0,1] "weakest skill" aggregate but still gated against regression). The key result: **once the five
  bounded skills saturate, the loop KEEPS improving by growing `product_k`** (reach 2 → 6 with `reach_budget=6`) —
  it no longer early-stops at the fixed-primitive-set ceiling. The plateau report now states that `open_ended_reach`
  is bounded by COMPUTE (`reach_budget`), not by a conceptual ceiling: raise the budget and exploration continues.
- **Measured (6 dimensions, Pareto-monotone, no regression)**: the five bounded dims as before (min 0.2 → 0.9444)
  PLUS **open_ended_reach 2 → 6** (unbounded; compute-capped, liftable). Report Section 5 gains the reach column +
  an "open-ended ratchet" note; Section 6 updates the POET row. Suite 618 → 625.
- **`tests/test_multi_metric_loop.py`** adds 7 red-first tests: `*_has_external_landscape`,
  `test_frontier_reach_is_unbounded` (budget 5 vs 8 climbs strictly further, monotone, no conceptual ceiling),
  `test_open_ended_ratchet_certifies_each_depth_and_base_fails`, `test_open_ended_negative_control_collapses`,
  `test_minimal_criterion_rejects_trivial_already_and_leaky`, `test_pareto_rejects_regression_in_open_ended_reach`,
  `test_loop_does_not_stop_at_fixed_substrate_ceiling`.
- **Honest limit**: "unlimited" means "no conceptual ceiling — bounded only by compute/conditioning", exactly as
  POET is compute-bounded in practice. We do NOT claim infinite reach in finite time; we claim the ratchet has no
  built-in saturation and every depth it reaches is externally certified.

### Added — POET absorbed: `curriculum_progression`, a 5th dimension where the engine GENERATES its own problems
Breaks `problem_space_is_static` (new meta-pack axis EXPLORATION): the engine no longer only SOLVES a fixed
benchmark — it MANUFACTURES its own increasing-difficulty problems and climbs them. But, per the library's own
law, a self-generated problem is worthless unless settled WITHOUT the engine's opinion. `judge` (meta pack)
approved the plan: **MUST_BE_AUDITED, breaks `problem_space_is_static` (confidence 1.0)**, axis EXPLORATION,
maturity SUSPENDED_BOLD → it demanded the falsifier be built (external resolver + generated_problem_landscape),
which this cycle does.
- **`evals/benchmarks/open_ended.py`** (new): a POET-like SR curriculum. Each `GeneratedProblem` carries KNOWN
  symbolic ground truth (fixed by construction), an external resolver (R²>0.999 + SymPy on held-out samples), a
  baseline (base basis solves only difficulty 0), a difficulty score (minimal grown primitives needed), and a
  **scrambled-target NEGATIVE CONTROL**. `curriculum_recovery_map` REJECTS any degenerate problem at construction
  (base+needed must recover, each needed primitive must be load-bearing, the scrambled target must collapse, the
  baseline must match the declared difficulty) — a mislabelled problem cannot enter. `harder_problem` returns the
  easiest not-yet-solved rung (open-endedness disciplined by a real ceiling).
- **`OUTLIER_MCB/packs/meta.py`**: new axis **EXPLORATION** + assumption `problem_space_is_static` (with its
  world-test and the `generated_problem_landscape` info-kind), so the JUDGE can reason about self-generated
  curricula honestly instead of collapsing them to "add more generators".
- **`evals/multi_metric_loop.py`**: `curriculum_progression` wired as the 5th Pareto dimension (measure + propose +
  Landscape gate). It is ORTHOGONAL to `external_transfer`: its rungs are unlocked by the primitives transfer does
  NOT reward (triple_product, product_trig, gaussian), so the two exploration dimensions pull toward DIFFERENT
  upgrades and together cover the primitive set faster.
- **Measured (5 dimensions, Pareto-monotone, no regression)**: sr_recovery 0.2778 → 0.9444, counterexample
  0.3333 → 1.0, judge_calibration 0.625 → 1.0, external_transfer 0.2 → 1.0, **curriculum_progression 0.2 → 1.0**
  (5/5 self-generated rungs solved) — weakest skill 0.2 → 0.9444, EARLY STOP epoch 21. Report Section 5 now plots
  the 6-line curve; a new Section 6 gives an honest capability comparison vs POET/Voyager/DreamCoder (no
  head-to-head superiority claim). Suite 610 → 618.
- **`tests/test_multi_metric_loop.py`** adds 8 red-first tests: `*_has_external_landscape`,
  `test_generated_problem_requires_external_landscape` (a fraud problem is rejected), `*_starts_below_ceiling`,
  `*_certified_upgrade_improves`, `*_negative_control_collapses`,
  `test_pareto_rejects_regression_in_curriculum_progression`, `test_curriculum_is_orthogonal_to_external_transfer`,
  `test_plateau_recommends_new_external_dimension`.
- **Honest scope**: this cycle absorbs POET (area 1). Voyager's skill library (`skills.py`) and DreamCoder's
  abstraction mining (`abstraction.py`) already EXIST but are not yet Pareto dimensions — they enter next, each
  only via a transfer test + negative control (one orthogonal dimension per cycle, by design).

### Added — a 4th certified dimension `external_transfer` + the ANTI-AUTOREFERENTIALITY gate (`landscapes.py`)
The deepest failure mode of a recursive self-improver is AUTOREFERENTIALITY: improving on a metric/benchmark the
system itself designed, scored by its own internal number — a "gain" that predicts nothing outside the repo. This
cycle makes the rule explicit, checkable, and ENFORCED before a dimension may enter the main Pareto vector.
`judge` (meta pack) approved the plan (MUST_BE_AUDITED, breaks `the_engine_judges_itself` — the new dimension is
settled on a HELD-OUT substrate, not self-judged).
- **`OUTLIER_MCB/landscapes.py`** (new, exported): a `Landscape` declares where a dimension's ground truth
  comes from. `is_external_landscape(...)` is True **only** if ALL of {provenance, external resolver, independent
  ground truth, negative control, baseline} hold; otherwise the dimension is `INTERNAL_ONLY` and **cannot** be
  optimized in the main loop. `multi_metric_self_improve` now asserts every admitted dimension is external —
  an autoreferential metric is refused at startup, not silently optimized.
- **`external_transfer`** — the anti-autoreferentiality dimension: fraction of a **HELD-OUT** Feynman substrate
  (`FEYNMAN_HELDOUT`, 5 laws the grown primitives were NEVER designed for) that the engine recovers (R²>0.999 +
  SymPy form). A gain here cannot be substrate-overfit. **Negative control**: a scrambled held-out target
  (inputs decoupled from output) collapses recovery below the R² threshold — so the metric measures
  generalization, not leakage. **Improved in the loop 0.2 → 1.0** (5/5 held-out laws generalized) by exactly the
  primitives that transfer (ratio, product_square, ratio_product, inverse_square); triple_product / product_trig /
  gaussian raise in-substrate sr_recovery but NOT transfer — an autoreferentiality key-log fires for each, and an
  orthogonality test (`test_new_dimension_changes_keep_drop_decision`) certifies the dimension is non-redundant.
- **Measured (4 dimensions, Pareto-monotone, no regression)**: sr_recovery 0.2778 → 0.9444, counterexample
  0.3333 → 1.0, judge_calibration 0.625 → 1.0, **external_transfer 0.2 → 1.0** — weakest skill **0.2 → 0.9444**.
  EARLY STOP at epoch 21 (patience 10) with a plateau report recommending the next orthogonal dimension
  (`causal_recovery`). Report PDFs' Section 5 now plots the 5-line curve (incl. external_transfer); suite 610.
- **`tests/test_multi_metric_loop.py`** adds 7 red-first tests: `*_has_external_landscape`,
  `*_starts_below_ceiling`, `*_certified_upgrade_improves`, `*_negative_control_collapses`,
  `test_pareto_rejects_regression_in_external_transfer`, `test_autoreferential_metric_rejected`,
  `test_new_dimension_changes_keep_drop_decision`.

### Added — a 3rd orthogonal certified dimension (judge_calibration) + early-stop, so the JUDGE improves too
The inventor had improved a lot; the risk was the JUDGE letting an overclaim through. So the loop now raises the
JUDGE itself as a certified Pareto dimension, and stops honestly at the ceiling instead of padding epochs.
`judge` (meta pack) approved the plan (MUST_BE_AUDITED, breaks `the_engine_judges_itself` — the judge is now
measured EXTERNALLY, not self-judged).
- **`evals/benchmarks/judge_calibration.py`**: an EXTERNAL labelled set of adversarial claims (OVERCLAIM /
  DEAD_ROUTE / INSIDE / VALID). The classifier uses the base judge plus the `claim_language_gate` detector (the
  library's own `gate_claim_language`/`classify_claim`) to catch overclaims ('proven', 'theorem', 'novel'
  above their evidence rung). Orthogonal to SR/counterexamples — it measures the JUDGE, not fitting. Negative
  control: a VALID claim with its certificate REMOVED collapses to DOWNGRADED; the gate never false-blocks a
  legitimate claim (`false_block_rate = 0`). **Improved in the loop 0.625 → 1.0** by one certified upgrade.
- **Early stop (patience=10)** in `multi_metric_self_improve` + a **plateau report** (weakest dimension, last
  upgrades tried, why they did not improve, the next ORTHOGONAL certified dimension to add — `causal_recovery` —
  and the next RED-FIRST test). The 30-epoch run now stops at epoch 21 instead of padding 9 empty epochs.
- **Measured (3 dimensions, Pareto-monotone, no regression)**: sr_recovery 0.2778 → 0.9444, counterexample
  0.3333 → 1.0, **judge_calibration 0.625 → 1.0** — weakest skill 0.2778 → 0.9444. Report PDFs' Section 5 now
  has the 4-line curve (incl. judge_calibration). `tests/test_multi_metric_loop.py` adds the five red-first
  tests (`*_starts_below_ceiling`, `*_can_improve_with_certified_upgrade`, `*_negative_control_collapses`,
  `test_pareto_rejects_regression_in_judge_calibration`, `test_multi_metric_loop_early_stops_after_5_plateau_epochs`).

### Added — MULTI-METRIC self-improvement: raise EVERY performance dimension, regress NONE (a Pareto gate)
Genuine all-round improvement, not one score chased for its own sake. The library cycles on itself over a VECTOR
of externally-certified dimensions and keeps a change ONLY under a Pareto gate (≥1 up, NONE down) — it can never
trade one skill away for another. `judge` (meta pack) approved the plan (MUST_BE_AUDITED, still anchored to an
external resolver).
- **`evals/multi_metric_loop.py`** (`multi_metric_self_improve(epochs=30)`): two orthogonal certified
  dimensions — symbolic-regression recovery (Feynman) + counterexample refutation — each epoch diagnoses the
  WEAKEST skill (key-logs) and strengthens it; the aggregate reported is the min (the weakest skill).
  **Measured (30 epochs): sr_recovery 0.2778 → 0.9444 (17/18 laws, Coulomb now recovered) AND counterexample
  0.3333 → 1.0 (all false conjectures refuted) — weakest skill 0.2778 → 0.9444, no dimension regressed.**
- **`evals/benchmarks/counterexamples.py`**: a second, orthogonal certified substrate — refute false
  conjectures with a real counterexample (a verified fact; a TRUE conjecture is never falsely refuted),
  improvable by widening the search window (n²+n+41 fails at 40, n²−79n+1601 at 80, Fermat F₅).
- **`pareto_improves(old, new)`** (in the library) + new protected invariant **`pareto_no_regression`**: the
  gate rejects any per-dimension regression; locked into the invariant suite (now 8/8).
- **`ratio_product_invsq`** primitive (Coulomb `q1·q2/(4π ε r²)`) added to `GROWN_PRIMITIVES` — strictly
  additive, the 14-law recoveries unchanged. Report PDFs' Section 5 now shows the multi-line Pareto curve.
  `tests/test_multi_metric_loop.py`.

### Added — more headroom: extended substrate + 2 new primitives → self-improvement climbs to 16/18 (was 12/14)
The 14-law substrate plateaued at 12/14 — not because the verified-novelty metric was exhausted, but because the
SUBSTRATE was. Adding more certified laws + the matching new primitives reopened headroom; the loop kept rising.
- **`FEYNMAN_EXTENDED`** (4 more official Feynman laws: `n·kb·T/V`, `q·v·B/p`, `μ·q·Volt/d`, `P/(4π r²)`) +
  `FEYNMAN_ALL`; the documented 14-law benchmark is unchanged (no regression).
- **Two new grown primitives** (`ratio_product` x_i·x_j·x_k/x_l, `inverse_square` x_i/x_j²) added to
  `GROWN_PRIMITIVES` — each certified on data (R²>0.999 + exact symbolic form). The 14-law recoveries are
  unchanged (verified: still 5 by default, 12 by the grown backend) — strictly additive, never regressing.
- **Recursive loop on the extended substrate**: verified-novelty fitness **0.2778 → 0.8889 (16/18 laws)**,
  discovering all 7 primitives across 7 epochs, then an honest plateau (Coulomb 1/r² and the relativistic factor
  need a richer/external backend). The report PDFs' improvement curve now shows this longer climb.

### Added — a RECURSIVE self-improvement run: the engine raised its own fitness 0.357 → 0.857 (never regressing)
The library cycled on itself on a concrete, externally-certified substrate (the Feynman SR benchmark), using its
own diagnostics + verified-novelty fitness, and genuinely improved — no cheating, no regression, honest ceiling.
- **`evals/self_improve_loop.py`** (`self_improve(epochs=10)`): each epoch diagnoses the bottleneck (key-logs in
  a `DiagnosticMemory`), proposes a new basis primitive for a form it has no example of (the "unknown zone"), and
  keeps it ONLY if the DATA certifies it (held-out R²>0.999 AND exact SymPy symbolic form) and it strictly raises
  recovery. The recovered set only grows ⇒ the fitness NEVER regresses (recorded on the monotone FrontierLedger);
  the honest zero-dep DEFAULT basis is never mutated. **Verified-novelty fitness 0.3571 → 0.8571** (5/14 → 12/14
  Feynman laws), discovering `ratio, triple_product, product_square, product_trig, gaussian`.
- **`grown_basis.py`** (`grown_backend()`, `GROWN_PRIMITIVES`, `grown_basis_terms`): the accepted primitives as a
  PERMANENT, opt-in, zero-dep, deterministic SDK capability — `grown_backend()` recovers 12/14 vs the default's
  5/14, while the documented default stays honestly limited. `tests/test_self_improve_loop.py`.
- **Report**: `make_report.py` now embeds the per-epoch **improvement curve (matplotlib)** + the trajectory table
  in `REPORT_EN.pdf` / `REPORT_IT.pdf` (`self_improvement_curve.png`).

### Added — the self-improvement fitness, designed by running the engine on itself: VERIFIED-novelty
Before implementing, the candidate fitness was run through the library. `judge` (meta pack) ruled a richer
internal composite (novelty × diversity × … − gaming) INSIDE_THE_BOX — a re-parameterization of
`add_more_metrics`, and gameable; `invent` pointed at the deeper break `the_engine_judges_itself` (only an
external resolver certifies). The result is a single, ungameable signal, not a composite.
- **`verified_novelty.py`**: `verified_novelty_fitness(proposals)` = the fraction of proposals that BOTH break a
  known box AND survive an EXTERNAL resolver (a benchmark recovery / repo test / data / real prior-art). Self-
  judged novelty NEVER counts; the external resolver is the GATE, not a weighted term. Carries its own anti-
  gaming ablation (`novelty_only_rate` vs verified, `gaming_gap`) showing external verification is load-bearing.
  `assess_proposal(idea, …)` asks the library's own `judge` whether an idea breaks a box.
- **New protected invariant `fitness_requires_external_verification`**: a novel-but-uncertified proposal must
  contribute 0 — the anti-circularity (`the_engine_judges_itself`) is now locked into the invariant suite.
- **Wired into `evolutionary_self_repair`** as the `measure`: the library can cycle on itself maximizing
  verified creativity under the two gates that can never be removed (never break a protected invariant, never
  regress). Padding the population with self-judged novelty LOWERS the verified rate, so the loop refuses it —
  gaming is structurally impossible. `tests/test_verified_novelty.py`; example
  `examples/verified_novelty_fitness_demo.py`.

### Added — a real external SR backend (gplearn) + a measured before/after report (PDF, EN + IT)
- **`gplearn_backend`** (`evaluators/backends.py`, alongside `pysr_backend`; lazy-import, deterministic via
  `random_state`): wires gplearn (genetic-programming SR) into `symbolic_evaluator(backend=…)`, reaching laws
  the zero-dep linear basis cannot (division, ≥3-way products, transcendental products). Fixed `_Predictor` to
  expose `.terms` so any external backend works with the evaluator (also fixes `pysr_backend`).
- **Measured before/after** on the Feynman subset: wiring gplearn raises true **symbolic recovery from 5/14
  (36%) to 8/14 (57%)** and median R² 0.9985 → 1.0 (reaches `q/C`, `ω/c`, `m·g·z`, `r·F·sin θ`, `ε·Ef²/2`),
  while the rigor (invariants/frontier) stays 100%. gplearn is stochastic — it gains the hard equations and, on
  this seed, misses two easy ones; reported as-is. `tests/test_benchmark_gplearn.py` (opt-in, skips if gplearn
  absent): the backend recovers a division law the default cannot.
- **`evals/benchmarks/make_report.py`**: generates a metrics+benchmark report as two PDFs (`REPORT_EN.pdf`,
  `REPORT_IT.pdf`) — internal correctness computed live, benchmark results from the documented measured run,
  honest interpretation, reproduce commands. Separates the JUDGE (rigor, ~100%) from the INVENTOR (the band
  that grows with what you wire in).

### Added — an OFFICIAL, certified third-party benchmark (Feynman / SRBench) for the verifiable SR component
- **`evals/benchmarks/feynman.py`**: the library's symbolic regression is measured against the **Feynman
  Symbolic Regression Database** (Udrescu–Tegmark, *AI Feynman*, Science Advances 2020; standardized by SRBench,
  La Cava et al., NeurIPS 2021) — certified, published ground truth. SRBench's two criteria are reported: the
  *accuracy solution* (test R² > 0.999) and the stricter *symbolic solution* (SymPy equivalence, opt-in).
- **Measured result** (documented subset of 14 of the 100 equations, deterministic, zero-dep): **5/14 exact
  symbolic solutions** (`μ·Nn`, `q2·Ef`, `3/2·pr·V`, the 3-term dot product, `sin(x)+2y`); 6/14 accuracy
  solutions, median R² 0.9985. The harness honestly distinguishes a true symbolic recovery from an accuracy-only
  approximation, and shows the failures (transcendental / true-division / ≥3-way forms the linear-in-basis SR
  cannot express — wireable to an external backend via `symbolic_evaluator(backend=…)`). No inflation.
  `tests/test_benchmark_feynman.py`; run `python -m evals.benchmarks.feynman`.
- The **Tübingen cause-effect pairs** (MPI Tübingen, 108 human-labelled pairs) is documented as the official
  benchmark for the preliminary causal component (next target; requires the official dataset).

### Added — the hard-problem frontier is now DOMAIN-AGNOSTIC (physics, biology, chemistry, ML, software, … not just math)
The engine is agnostic by construction; the hard-problem machinery was math-coupled, so it was generalized
without regressing the math path.
- **Agnostic external certificates** (`certificates.py`): one vocabulary for «settled by an external resolver»
  across fields — FORMAL (`LEAN_CHECKED`/`Z3_PROVED`/`NUMERIC_VERIFIED`, a proof), EMPIRICAL
  (`SIMULATION_VERIFIED`/`EXPERIMENT_REPRODUCED`/`DATASET_EVAL_PASSED`/`BENCHMARK_MEASURED`/`REPO_TEST_GREEN`, a
  reproducible measurement, honestly NOT a proof), META (`INVARIANTS_VERIFIED`). `is_external_certificate`,
  `Certificate`, `RESOLVER_KINDS`. The `FrontierLedger` now accepts any of these, so a physics simulation or a
  wet-lab reproduction advances a monotone certified frontier exactly like a math lemma; mere sampling stays
  rejected (`tests/test_certificates.py`).
- **`ResultCandidate` + pluggable resolver** (`frontier_search.py`): a domain-agnostic partial result carries
  its OWN external resolver `settle()` (or a global `resolver`); the loop is blind to the domain. The math
  `LemmaCandidate`/`settle_lemma` stay the default math instance (`tests/test_agnostic_frontier.py`).
- **A non-math barrier** (`barriers.py`): the **Second Law of Thermodynamics** kills a closed-system
  perpetual-motion / over-unity route (`DEAD_BY_BARRIER`) and names the exits, scoped to `physics`/`engineering`
  — proving no-go gates are agnostic, not math-only. New `physics` DomainPack (`packs/physics.py`).
- **Agnosticism is a protected invariant** (`agnostic_certificates`): a non-math certificate must advance a
  frontier and sampling must be rejected — locked so a future change cannot quietly make the engine math-only.
- **Repair INTERVIEW** (`self_repair.repair_brief`): before proposing a patch, the LLM queries the library for
  WHAT/HOW to fix (bottleneck + levers) and the hard CONSTRAINTS (the protected invariants + never-regress); it
  then decides and acts, and `evolutionary_self_repair` enforces the very constraints the brief listed
  (`tests/test_repair_brief.py`). Example: `examples/agnostic_domains_demo.py`.

### Added — self-diagnosis + evolutionary self-repair (the library notices it erred and fixes itself, never back)
- **Point-logs + a SEPARATE diagnostic memory** (`self_diagnosis.py`): drop diagnostic POINTS during a run
  (`DiagnosticLog.ok/weak/bottleneck/blocked/failed`, deterministic integer `seq`, no wall-clock), kept in a
  `DiagnosticMemory` distinct from the result memories. `diagnostic_run(task, memory)` records the keylog even
  if the body raises (a crash is the post-mortem worth keeping). `frontier_search(..., log=…)` is instrumented
  (opt-in) so a run that does not reach its objective leaves a post-mortem.
- **`self_diagnose`** → a ranked picture of weak spots + the dominant bottleneck + the next lever (reports
  only; the fix is gated). `tests/test_self_diagnosis.py`.
- **Protected invariants** (`self_repair.py`, `INVARIANT_REGISTRY` + `verify_invariants`): the explicit «cose
  solide che non si possono toccare» — the four entrypoints exist, the engine never claims PROVED on an open
  conjecture, the frontier rejects regressions, a deterministic distance exists, the parity barrier still
  fires. Re-run as the external resolver for a repair.
- **`evolutionary_self_repair`**: keep a fix ONLY if (1) every protected invariant still holds AND (2) the
  health metric did not regress (re-measured, «valutare se davvero non è regredita»); otherwise ROLL BACK and
  record the failed attempt as a diagnostic point. An accepted strict improvement is logged on the monotone
  FrontierLedger (new certified status `INVARIANTS_VERIFIED`), so the engine's health can only move forward.
  `tests/test_self_repair.py`; example `examples/self_repair_demo.py`.

### Added — hard-problem frontier (attack OPEN problems with PARTIAL certified results that never regress)
The honesty layer is the engine of progress here, not a brake: scope expands, the claim never does. Nothing
below ever prints "PROVED" on an open conjecture — the parent stays `CONJECTURE`.
- **F1 — `number_theory` DomainPack** (`packs/number_theory.py`): the hidden assumptions of the standard
  sieve attack on prime gaps (parity-respecting weights, sieve-only, aim-at-gap-2, unconditional, independent
  correlations), with known families (Selberg / GPY / Maynard–Tao / large sieve / circle method) and IT/EN
  keyword routing (`tests/test_number_theory_pack.py`).
- **F2 — barriers as a kill gate** (`barriers.py`): no-go theorems that rule a dead ROUTE. The parity problem
  marks a classical sieve aimed at gap = 2 `DEAD_BY_BARRIER` and names the admissible exits; integrated into
  `judge` and pack-scoped (`tests/test_barriers.py`).
- **F3 — monotone certified frontier** (`frontier_ledger.py`): `FrontierLedger.claim(...)` accepts a partial
  result ONLY if it carries a valid external certificate AND strictly improves the frontier; a worsening claim
  is `REGRESSION_REJECTED`, an uncertified one `UNCERTIFIED_REJECTED`; deterministic sorted-JSON persistence
  (`tests/test_frontier_ledger.py`).
- **F4 — external settlement of partial LEMMAS** (`math_discovery.settle_lemma`): a lemma is settled to
  `LEAN_CHECKED` / `Z3_PROVED` / `NUMERIC_VERIFIED` (exhaustive over a finite integer domain, zero-dep) or
  refuted / `UNKNOWN_TIMEOUT` — never `PROVED` on the parent; only a certified lemma may advance the frontier
  (`tests/test_settle_lemma.py`).
- **F5 — toward-objective loop** (`frontier_search.py`): skip barrier-dead routes → settle survivors → advance
  the monotone frontier → turn each failed lemma into the next assumption to break. Reaches the same frontier
  under any sub-lemma ordering and never regresses (`tests/test_frontier_search.py`).
- **F6 — anti-regression CI invariant** (`evals/frontier_regression.py` + CI step): fails if a change lowers a
  certified frontier result or lets an uncertified claim onto the frontier (`tests/test_frontier_regression.py`).
- Example: `examples/hard_problem_frontier.py` (routing → barrier → certified frontier advance → honest
  CONJECTURE on twin primes).

### Added — six capabilities extrapolated by running the engine on itself (each opt-in, each with an ablation test)
- **GENERATIVITY — a resolvable default content source** (`set_default_llm` / `reset_default_llm` /
  `OUTLIER_MCB_LLM`): `transform_space` diagnosed the engine's ceiling as a missing axis (it recombines
  pre-written pack assumptions, never producing content it was not given). The LLM is now a process-wide
  default the generative entrypoint draws from; external settlement still decides what survives. Unset ⇒
  template path, unchanged (`tests/test_default_llm.py`).
- **Noise → signal** (`invent(anomalies=[…])`): each observed residual the box discards is mined into a
  provisional assumption (`anomaly_to_assumption`) and generates candidates that break it — offline, without
  needing a settled loss (`tests/test_anomaly_mining.py`).
- **Anti-gaming guard** (`reward_hacking_report`): audits each kept candidate for fragile single-signal
  dependence and flags one that survives only via gameable soft proxies, never via the external gate
  (`tests/test_reward_hacking.py`).
- **Emergent cross-domain blending** (`invent(blend_with=[…], blend_threshold=…)`): fuses the routed pack with
  distant domains and admits a blend only if its emergence clears the gate, so it cannot collapse to a
  transport (`Candidate.emergence`; `tests/test_blend_in_invent.py`).
- **Autonomous conceptual space** (`invent(induce_pack=True)`): when no pack maps the prompt, induce a
  provisional one from the problem's own words instead of the generic fallback (`tests/test_induce_in_invent.py`).
- **Cross-session composing memory** (`invent(discovery_memory=…/discovery_path=…)`): dead ends refuted in
  past sessions bias this run's ranking, and settled outcomes are recorded back and persisted
  (`tests/test_discovery_memory_in_invent.py`).

### Changed
- **Lifted the lexical novelty ceiling (breaks `novelty_is_naming`).** The semantic-distance default is now
  PROCESS-WIDE RESOLVABLE: `set_default_embedder(emb)` / `reset_default_embedder()` and the env var
  `OUTLIER_MCB_EMBEDDER=sentence-transformers:<model>` upgrade EVERY `embedder=None` distance (novelty,
  judge, memory, frontier, blending) to real semantics in one switch. Unset/offline ⇒ lexical fallback, so
  default behaviour stays deterministic and zero-dependency (the library never imports a model on its own).
  Verified by `tests/test_semantic_default.py`: under the lexical default a reworded near-duplicate survives
  a dedup (novelty-by-naming); registering a semantic default FLIPS that keep/drop decision. The idea was
  itself routed through `judge(pack=meta)` → `MUST_BE_AUDITED` before implementation.

## [1.0.0]

First stable release. The library moved from an internal-only prototype to a measured, grounded SDK with
an objective readiness gate.

### Added
- **Four entrypoints**: `creative` (the brief), `judge` (discipline a free-text idea), `invent` (the
  grounded runtime), `green_star` (the no-examples zone).
- **Agnostic kernel ⊖ DomainPack** architecture; built-in `coding` / `math` / `generic` packs, plus
  elicitation (`elicit_pack` / `pack_from_spec`) to build your own.
- **Grounding** (`probe`, `RepoContext`): real project signals; **artifact-contract** `RepoCheck`s.
- **Honest verification**: `verify_red_green` (a *new* test must exist and be green), `AUTO` vs `HUMAN`
  verifiability classes, the four artifact classes.
- **Learning loop**: priced-bet `Ledger` (with `save`/`load`), Reflexion auto-regeneration
  (`invent(reflect_rounds=…)`).
- **Self-measurement**: `health()`, `capability_value()` (ablation), `pack_quality()`.
- **Deterministic eval harness** (`evals/`) with baselines, scorers, and a `verified_novelty_score`;
  CLI `python -m evals.run_eval`.
- **Readiness gate**: `readiness_report()` and `python -m OUTLIER_MCB.cli readiness` — an objective
  GO_READY / NO_GO for releases.
- **Scoring as a hypothesis**: configurable `ScoreWeights` + `calibrate_weights`.
- Packaging: `pyproject.toml`, console script, `py.typed`, `python -m OUTLIER_MCB`.

### Notes / honest limits
- The eval measures *structure* (falsifiable, distinct, grounded, well-routed), not human-judged value.
- Baselines are deterministic stand-ins, not a real LLM; a model-in-the-loop comparison is out of scope
  for the offline harness.
