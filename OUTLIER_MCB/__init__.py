"""OUTLIER_MCB — an ACTIVE assumption-negation + falsification engine for rigorous creativity.

A domain-agnostic forcing function for a coding assistant: when the user asks for something *new*, it
stops the assistant from answering with the average of its training memory and makes it break a hidden
assumption, formalize the claim, design a world-test, run a collision audit, and only then propose a
SPEC. No magic, no random idea generator: novelty is CERTIFIED by survival against the known families
+ a broken assumption, never by naming.

Pipeline: PROMPT → ASSUMPTION GRAPH → NEGATION → BRANCHES IN TENSION → THEOREM SKETCH → WORLD-TEST
          → COLLISION AUDIT → REVIEWER ATTACK → SURVIVAL/DEATH → SPEC.

START HERE:
    import OUTLIER_MCB as gsl
    print(gsl.creative("invent a genuinely new architecture for <your problem>"))

Agnostic by construction: the kernel knows nothing about any domain; all domain knowledge lives in a
swappable DomainPack (built-in: coding, math, generic; plus any you elicit). The same engine runs on a
rate limiter, a convergence theorem, or a domain it has never seen.
"""
# ── typed faults (genuine errors raise; verdicts stay data) ──
from .errors import (OUTLIER_MCBError, PackNotFoundError, InvalidPackError, AssumptionNotFoundError)
# ── explicit output schemas (the dicts are typed, not abandoned) ──
from .types import PreflightResult, MissingInfo, BreakOption, HiddenAssumption
# ── shared types + the domain-agnostic negation engine ──
from .core import Assumption, Negation, negate
from .assumption_graph import AssumptionGraph, RELATIONS

# ── the domain-blind kernel ──
from . import kernel
from .kernel import (graph_of, no_solution_before_assumption, novelty_score, branch_on_assumptions)

# ── DomainPacks: the only place domain knowledge lives ──
from .pack import DomainPack, register_pack, get_pack, list_packs, select_pack, route_pack, RouteDecision
from .pack_quality import pack_quality
from .artifacts import (validate_artifact_contract, artifact_contract_score, materialized_artifact, expected_test_present, artifact_class)
from . import packs   # registers coding / math / generic on import

# ── agnosticism honesty: guard + elicitation bridge ──
from .guard import guard_response, domain_confidence
from .elicit import elicit_pack, pack_from_spec, ElicitationRequest, iterative_elicit
# ── DomainPack SELF-INDUCTION: induce the conceptual space from evidence instead of hand-writing it (#1) ──
from .pack_induction import (infer_domain_pack, expand_pack_with_discovered_assumptions, validate_inferred_pack,
                             pack_induction_ablation)

# ── the one-call entrypoint + the preflight it wraps ──
from .preflight import creative, preflight_creative_request, preflight
from .instruction_emitter import emit_assistant_instructions
# ── the human–machine loop: discipline the assistant's OWN free-text idea (the missing half) ──
from .judge import judge, Judgment
# ── first-principles reviewer: critique from the claim's own logic, not only the pack's known families ──
from .first_principles_reviewer import (first_principles_attack, FirstPrinciplesCritique, FalsifiableObjection)
# ── real-time domain research: source an UNKNOWN domain from the web instead of refusing ──
from .research import auto_elicit, CallableProvider, WebResearchProvider, ResearchError
# ── autonomous novelty check: search the real world for prior art (renamed/collage vs genuinely new) ──
from .novelty import (novelty_audit, NoveltyVerdict, world_novelty_score,
                      prior_art_audit, prior_art_distance_score, source_overlap_score,
                      rebranding_detector, collage_detector, GRADED_VERDICTS)
# ── real, multi-source prior art with explicit novelty_scope + provenance (absence ≠ proof, scoped) ──
from .prior_art import (PriorArtProvider, PriorArtResult, OfflinePriorArtProvider, OnlinePriorArtProvider,
                        CompositePriorArtProvider, CachedPriorArtProvider, ArxivPriorArtProvider,
                        OpenAlexProvider, GitHubPriorArtProvider, CrossrefProvider, GitHubCodeSearchProvider,
                        CallableOnlineProvider, PriorArtError, NOVELTY_SCOPES, novelty_scope_of,
                        coverage_level_of, default_online_provider)
# ── offline prior-art corpus: catch renames of famous methods with NO network (better default than LOCAL_ONLY) ──
from .known_methods import (OfflineCorpusProvider, KnownMethod, KNOWN_METHODS, known_method_names)
# ── the epistemic gate's effect, MEASURED (turns 'philosophical distinctiveness' into a number) ──
from .gate_ablation import epistemic_gate_ablation, GateAblation
# ── red-first materialization: is an artifact contract a real, currently-RED test against the repo? ──
from .materialize import materialization_score, materialization_evidence

# ── the plural, disciplined generator ──
# breaking operators: recombine / invert / scale / transport / abduce
# non-breaking operators (creation ≠ only negation): unify / instrument / reframe
# discovery + agency (push past the training distribution): anomaly_to_assumption / self_spark
from .generators import (generate, generate_candidates, Candidate, recombine_assumptions,
                         invert_assumption, scale_break, transport_break, what_would_have_to_be_true,
                         unify, instrument, reframe, dissolve, anomaly_to_assumption, self_spark,
                         conceptual_blend, blend_emergence, blend_domains)
# ── the honesty layer: coherence ≠ value, proposing ≠ certifying ──
from .maturity import assess as assess_maturity, Maturity, STATUSES
# ── the rigor ladder: a strong word is locked to the rung its evidence reaches (brilliant, not lying) (#9) ──
from .claim_ladder import classify_claim, gate_claim_language, claim_ladder_ablation, ClaimStatus, LADDER
# ── closure-membership gate + representation-theorem registry (FIX A/B/D/E): INSIDE a universal closure ⇒ box ──
from .closures import (reduces_to_closure, closure_membership, closure_escape_proven, architectural_novelty,
                       UniversalClosure, CLOSURE_REGISTRY, ARCHITECTURE_LADDER, INSIDE, OUTSIDE, UNKNOWN)
# ── a more robust (concept-lexicon + stemming + anchor-fallback) closure recogniser, generalising over
#    diverse phrasings where the keyword detector abstains; deterministic, zero-dependency, opt-in ──
from .closure_recognition import (robust_closure_verdict, RobustClosureRecognizer, semantic_closure_verdict,
                                  combined_closure_verdict)
# ── composed, low-risk creativity/honesty tools (pure composition of the primitives above; opt-in) ──
from .box_map import box_map, box_map_markdown
from .assumption_diff import assumption_diff, assumption_diff_markdown
from .receipt import novelty_receipt, verify_receipt, receipt_markdown
from .ci import assert_outside_the_box, assert_claim_honest, NoveltyRegression, ClaimOverreach
from .linter import lint_text, lint_file, lint_report
from .handoff import (handoff_contract, accept_handoff, handoff_report,
                      validate_world_test, validate_broken_assumption)
from .theorems import (theorem_brief, find_theorem_for, classify_proved_theorem, RepresentationTheorem,
                       REPRESENTATION_THEOREMS, KNOWN_THEOREMS)
# ── F2: no-go theorems as a KILL gate — a proven barrier (parity problem) rules a dead ROUTE, names the exits ──
from .barriers import (barrier_membership, Barrier, BarrierVerdict, BARRIER_REGISTRY,
                       DEAD_BY_BARRIER, NOT_BLOCKED)
# ── agnostic external certificates: math proof · physics simulation · wet-lab reproduction · ML eval · repo test ──
from .certificates import (Certificate, is_external_certificate, EXTERNAL_CERTIFICATES, FORMAL_CERTIFICATES,
                          EMPIRICAL_CERTIFICATES, META_CERTIFICATES, RESOLVER_KINDS, kind_of)
# ── F3: the monotone externally-certified frontier — «always toward the objective, never back» ──
from .frontier_ledger import (FrontierLedger, FrontierClaim, ClaimResult, is_certified, CERTIFIED_STATUSES,
                              ACCEPTED, REGRESSION_REJECTED, UNCERTIFIED_REJECTED)
# ── F5: the toward-objective loop — generate sub-lemmas, kill the false, settle, advance the frontier ──
from .frontier_search import (frontier_search, FrontierSearchReport, LemmaCandidate, ResultCandidate,
                             propose_sublemmas)
# ── self-diagnosis: point-logs + a SEPARATE diagnostic memory + self_diagnose (weak spots / bottlenecks) ──
from .self_diagnosis import (DiagnosticPoint, DiagnosticLog, DiagnosticMemory, diagnostic_run,
                             self_diagnose, DiagnosisReport, PhaseWeakness, POINT_STATUSES)
# ── evolutionary self-repair: try a fix, keep it ONLY if no protected invariant breaks AND no regression ──
from .self_repair import (evolutionary_self_repair, RepairProposal, RepairResult, verify_invariants,
                          library_health, ProtectedInvariant, InvariantReport, INVARIANT_REGISTRY,
                          repair_brief, RepairBrief)
# ── the self-improvement fitness the engine designed for itself: VERIFIED-novelty (external resolver decides) ──
from .verified_novelty import (verified_novelty, verified_novelty_fitness, assess_proposal, Proposal,
                              VerifiedNoveltyReport, pareto_improves)
# ── grown SR primitives the engine discovered for itself by recursive self-improvement (opt-in; default stays honest) ──
from .grown_basis import (grown_backend, grown_basis_terms, GROWN_PRIMITIVES, MAX_GROWN_ARITY)
# ── anti-autoreferentiality gate: a dimension enters the main Pareto vector only if anchored OUTSIDE the engine ──
from .landscapes import Landscape, is_external_landscape, EXTERNAL, INTERNAL_ONLY
from .novelty import honest_prior_art_status
# ── grounding: probe the REAL environment so falsification stops running on placeholders ──
from .grounding import probe, RepoContext
# ── semantic repo grounding: AST world-model (call graph, test map, impact surface, missing evaluators) (#2) ──
from .repo_semantics import (analyze_repo_semantics, repo_world_model, impact_surface, suggest_repo_falsifiers,
                             is_grounded, repo_grounding_ablation, RepoModel, ModuleInfo)
# ── the novelty market: a priced BET is the unit, the REPO is the resolver ──
from .economy import Bet, Ledger, bet_from_candidate, forge_bet
# ── cumulative discovery memory: confirmed/refuted assumptions compound across sessions ──
from .discovery_memory import DiscoveryMemory, AssumptionOutcome
# ── episodic + analogical memory (the two forms the engine asked for) ──
from .memory import EpisodicMemory, Episode, AnalogicalMemory, AnalogyOutcome
# ── active memory routing: retrieve what changes the next creative move ──
from .memory_router import CreativeMemoryRouter, MemoryCue, MemoryPlan
# ── intrinsic motivation as FUNCTIONAL signals: curiosity toward the unknown, joy of surprise-confirmed ──
from .affect import curiosity_score, bayesian_surprise, discovery_reward, curious_worth
# ── the autonomous inventor: orchestrate problem-finding + blending + transformation + the memories ──
from .orchestrator import autonomous_inventor, InventionRun, InventionStep
from .repo_world import compile_world_test, RepoCheck
# ── the cognitive runtime: borrow ToT/Self-Refine/Reflexion/AutoGen/DSPy control, INVERT their objective ──
from .invent import (invent, Invention, novelty_search, push_further, box_distance, invent_reflect, illuminate)
# ── Quality-Diversity (MAP-Elites) + formal Novelty Search + intrinsic goal-setter ──
from .qd import QDArchive, BehaviorDescriptor
from .novelty_archive import NoveltyArchive, behavior_descriptor
from .goal_setter import propose_goal
# ── problem-finding: the engine PROPOSES which problems are worth attacking (the creative spark) ──
from .problem_finding import find_problems, Problem, ProblemPortfolio
# ── transformational creativity: the engine GROWS its own conceptual space (invents a new axis) ──
from .transformation import (transform_space, propose_transformation, TransformationResult,
                             TRANSFORMATION_STATES)
# ── FunSearch-style creative search: generator → EXTERNAL evaluator → QD archive → evolve ──
from .creative_search import (creative_search, structural_evaluator, code_evaluator,
                              CreativeSearchResult, CreativeRecord)
# ── external evaluators that settle by something REAL: symbolic regression settles by the DATA ──
from .evaluators import (symbolic_evaluator, basis_from_candidate, expansions_for, least_squares,
                         Formula, Term, DEFAULT_BUILDERS, causal_evaluator, pysr_backend, gplearn_backend, dowhy_backend,
                         EvaluationResult, BaseEvaluator, CallableEvaluator, PropertyEvaluator,
                         NoveltyEvaluator, PytestEvaluator, CompositeEvaluator, HiddenEvaluator)
# ── harder verification + better experiments (the decisive next step, per the roadmap) ──
from .interestingness import interestingness_score
from .active_experiment import (Experiment, next_best_experiment, expected_information_gain,
                                disambiguation_score, cost_of_test)
from .world_tests import WorldTestGenerator, GeneratedWorld
# ── a dedicated red team: it GENERATES the attacks meant to break a candidate (boundary / control / rebrand) ──
from .red_team import (RedTeamEvaluator, Attack, boundary_attacks, negative_control_attacks,
                       rebrand_attack, red_team_from_check)
# ── evaluator synthesis: invent the VERIFIER from a claim's materials, not just the idea (#3) ──
from .evaluator_synthesis import (synthesize_evaluator, validate_evaluator, evaluator_quality_score,
                                  evaluator_ablation, SynthesizedEvaluator, EvaluatorSynthesisError)
# ── staged falsification: a DAG of experiments, each gated on its prerequisites passing ──
from .experiment_dag import (ExperimentDAG, Experiment as ExperimentStep, ExperimentOutcome, DAGReport)
# ── the gameability/ablation gate: a metric earns its place only if it changes a keep/drop decision ──
from .ablation import (ablation_gate, ablation_gate_from_records, AblationReport, ComponentVerdict,
                       INVENTION_COMPONENTS, reward_hacking_report, HackVerdict)
# ── memory that LEARNS: failure taxonomy + operational lessons retrieved into the next attempt ──
from .failure_lessons import (FailureLesson, LessonMemory, summarize_failure_mode, FAILURE_MODES,
                              compress_failure_to_lesson, retrieve_lessons, mutate_from_failure_lesson,
                              failure_lesson_ablation)
# ── the Automated Scientist Loop: generate → settle-on-data → accept-if-controls-collapse → escalate ──
from .discovery import discover, Discovery, DiscoveredLaw
# ── evolutionary invention (AlphaEvolve-useful): population + lineage + baseline/parent + hard caps ──
from .evolution_memory import EvolutionMemory, EvolutionRecord
from .evolve import (evolve_invention, invention_score, EvolveResult, symbolic_invention_task,
                     causal_invention_task)
from .evolution_ops import (MutationResult, mutate_assumption, mutate_mechanism, mutate_objective,
                            add_falsifier, simplify_candidate, generalize_candidate, recombine_distant,
                            cross_domain_transfer, novelty_push, ALL_OPERATORS)
from .prompt_sampler import PromptSampler, STRATEGIES
from .unknown_space import (suggest_unknown_region, novelty_frontier, unexplored_assumptions,
                            unexplored_axes, recommend_next_mutations, failure_clusters, UnknownRegion)
from .self_evolve import self_evolve, SelfEvolveResult, validate_improvement_patch
# ── lateral thinking + open-ended search (selectively taken from ShinkaEvolve / DGM / de Bono / Koestler) ──
from .lateral import provocation, random_entry, is_novel_enough, novelty_first, OperatorBandit
# ── selectively taken from competitors: analogy (distant transfer), POET problems, DreamCoder abstractions, Voyager skills ──
from .analogy import (CrossDomainAnalogyEngine, Analogy, OnlineCrossDomainAnalogyEngine, OnlineMechanism,
                      DISTANT_DOMAINS, MechanismTransfer, discover_remote_mechanisms, transfer_mechanism,
                      testable_analogy_claim, analogy_prior_art_audit, analogy_online_ablation)
from .problem_generator import ProblemGenerator, GeneratedProblem
# ── active problem-finding (#4): better QUESTIONS — leverage ranking + fixation detection ──
from .problem_active import (find_high_leverage_questions, rank_problem_by_novelty_and_testability,
                             rank_questions, generate_problem_family, detect_problem_fixation, problem_active_ablation)
# ── divergent protocol runner (#7): SCAMPER/Geneplore/… run competitively under a UCB bandit ──
from .divergent_runner import (run_divergent_protocols, score_protocol_output, select_protocols_by_bandit,
                               DivergentResult, protocol_ablation)
# ── real novelty frontier (#8): conceptual vs BEHAVIORAL vs prior-art novelty, kept separate ──
from .frontier import (conceptual_novelty, behavioral_novelty, prior_art_novelty, frontier_score,
                       behavior_signature, sparse_unknown_regions, frontier_ablation)
# ── objective break: optimize for verified novelty/frontier movement, not only task loss ──
from .novel_objective import (NoveltyObjectiveEvaluator, NoveltyObjectiveWeights,
                              novelty_objective, recursive_novelty_search)
from .abstraction import (mine_abstractions, compress_candidates_to_concepts, mine_mechanism_abstractions,
                          Concept, ConceptLibrary)
from .skills import Skill, SkillLibrary, SEED_SKILLS
# ── light cognitive roles (AutoGen/CrewAI idea only) + auditable reasoning trace (OpenHands/SWE-agent) ──
from .agents import CognitivePanel, AgentEvidence, PanelReport
from .trace import ReasoningTrace, ActionStep, EvidenceLedger
from .cognitive_growth import (LinearCausalWorld, CounterfactualExperiment,
                               counterfactual_world_prediction_collapses_when_edge_shuffled,
                               experiment_splits_hypotheses_better_than_random_probe,
                               RoleReputation, role_vote_weight, ExecutableSkill,
                               DiscoveryArtifact, idea_without_artifact_cannot_enter_discovery_ledger,
                               research_taste_score, taste_prefers_small_deep_mechanism_over_large_trivial_result)
# ── T2.1: an EARNED (learned, calibrated) taste over unverified ideas — complements cognitive_growth's
#    static research_taste_score heuristic; this one updates from the engine's own settled track record ──
from .taste import (EarnedTaste, candidate_features, earned_taste_from_ledger, earned_taste_from_records,
                    taste_rerank)
# ── T2.5: settle MORE at LOWER cost via calibrated cheap proxies — the settlement bottleneck the engine named ──
from .verification_economy import (VerificationEconomy, ProxyCalibration, SettlementOutcome,
                                   calibrate_proxy, as_verdict)
# ── T2.3: incubation — let persisted dead ends & distant wins RECONNECT offline (the delayed-insight step) ──
from .incubation import incubate, revive_barren, IncubatedConnection, RevivedDeadEnd
# ── T2.2: the EXECUTABLE active-experiment loop — acquire new information to shrink a hypothesis space ──
from .experiment_loop import (Hypothesis, ActiveExperimentResult, RunStep, build_experiments,
                              run_active_experiments)
# ── the composed scientific loop: one entry that ORCHESTRATES every capability (no dead code) ──
from .orchestrate import autonomous, AutonomousResult
# ── the math discoverer's toward-objective loop (wires frontier_search + propose_sublemmas + pivot) ──
from .math_frontier import math_frontier, MathFrontierResult
# ── T2.4: invent the REPRESENTATION that makes a hard problem easy, disciplined by a control ──
from .representation import (Representation, ReducibilityVerdict, representation_reducibility,
                            invent_representation)
# ── Orthogonal Latent Germs: grow a new basis, accept only with external reducibility + collapsing control ──
from .orthogonal_germs import (OrthogonalLatentGerm, OrthogonalGermVerdict, propose_orthogonal_germ,
                               evaluate_orthogonal_germ, lexical_orthogonality, known_box_surface,
                               orthogonal_germ_instruction, orthogonal_germ_relevant)
# ── Point 1: invent whole new consistent 'physics' (toy universes), scored by external emergence ──
from .physics_inventor import (Physics, Law, propose_new_physics, elementary_physics, run_simulation,
                               measure_emergence, emergence_of, coherence_controls_pass)
# ── Point 2: endogenous semantic grounding — the engine coins its OWN concepts, scored by MDL compression ──
from .semantic_grounding import (EndogenousSymbol, SymbolRegistry, find_recurring_patterns, ground_new_symbol,
                                 verify_grounding, conceptual_compression, grounding_controls_pass)
# ── Point 3: invent a new FORMAL LANGUAGE (a primitive-set DSL) when solutions are too verbose ──
from .language_inventor import (FormalLanguage, integer_baseline, invent_new_language, shortest_program,
                                expressive_power, is_sound, soundness_controls_pass)
# ── Point 4: aesthetics as objective AST metrics — beauty measured, never asserted (an extra Pareto dim) ──
from .aesthetics import (measure_symmetry, measure_simplicity, measure_surprise, elegance_score,
                         aesthetics_objectivity_pass)
# ── the single front door: route → generate → settle externally → audit → one honest report ──
from .studio import explore, StudioReport
# ── batteries-included: a zero-config, offline, end-to-end tour so first-run works with no setup ──
from .demo import demo
# ── activation: make library use a DEFAULT ROUTINE for any AI assistant (Claude/ChatGPT/Gemini/Cursor) ──
from .activation import (assistant_brief, assistant_route, activation_snippet, should_activate,
                         AssistantRoute, SUPPORTED_ASSISTANT_LANGUAGES, STANDING_RULES, TRIGGERS)
# ── the self-describing capability index: how an LLM drives the WHOLE engine automatically ──
from .capabilities import capabilities, capabilities_markdown, Capability
# ── divergent-thinking engine: fluency / flexibility / originality / elaboration (Guilford + Boden) ──
from .divergence import diverge, DivergenceResult, DivergentIdea
# ── pluggable semantic-distance adapter: lexical by default, inject a real embedder for true semantics ──
from .embeddings import (LexicalEmbedder, NgramEmbedder, CallableEmbedder, semantic_distance, default_embedder,
                         set_default_embedder, reset_default_embedder)
# ── Tree-of-Thoughts + Self-Refine + Reflexion, pruned by an EXTERNAL score (never self-judgment) ──
from .thought_search import (thought_tree, ThoughtTree, ThoughtNode, prune_by_external_score,
                             self_refine, ReflectionMemory)
# ── explicit cognitive-creativity protocols (Geneplore, SCAMPER, fixedness breaking, remote association) ──
from .cognitive_protocols import (CognitiveMove, CognitiveProtocolResult, scamper, geneplore,
                                  functional_fixedness_breaker, remote_association, cognitive_extremes)
# ── the recursive central test: OUTLIER_MCB proposes improvements to itself, triaged by judge + novelty ──
from .self_improve import propose_self_improvements, SelfImprovementReport, SelfImprovementProposal
# ── LLM-in-the-loop: propose → prior-art gate → MATERIALIZE a failing test → run RED→GREEN → score (opt-in) ──
from .llm import (LLMProvider, CallableLLMProvider, SubprocessLLMProvider, parse_candidates, CANDIDATE_SCHEMA,
                  set_default_llm, reset_default_llm, default_llm)
from .runner import CommandRunner, CommandResult, UnsafeCommandError, to_argv
from .patches import (parse_unified_diff, validate_patch_paths, apply_patch_plan, PatchPlan,
                      PatchTransaction, patch_substance_score, patch_substance_evidence, is_test_path)
from .llm_loop import (llm_openended_search, llm_evidence_score, LLMSearchResult, LLMCandidate,
                       score_components, classify_test_outcome, test_quality_score, test_quality_evidence,
                       DEFAULT_SCORE_WEIGHTS)
# ── close the loop: a real multi-factor score + a verifier that EXECUTES and settles the bet ──
from .scoring import score_idea, ScoreWeights, calibrate_weights, default_score_weights, synergy_score
from .readiness import readiness_report
from .readiness_discovery import readiness_discovery_report, DISCOVERY_STATES as READINESS_DISCOVERY_STATES
from .verifier import (run_check, verify, Verdict, verifiability_class,
                       verify_red_green, materialized, RedGreen)
# ── close the executive loop WITHOUT an LLM: synthesize a red-first artifact and drive it RED→GREEN ──
from .self_materialize import (settle_by_materialization, synthesize_artifact,
                               MaterializationReceipt, SynthArtifact)
# ── external value: metrics that score a POOL of ideas (falsifiable, distinct, grounded) ──
from .metrics import (score_pool, verified_novelty_score, broken_assumption_rate, falsifiability_score, operator_diversity,
                      unique_frontier_ratio, rebranding_risk_rate, artifact_specificity, auto_verifiability_rate,
                      discovery_confidence)
# ── novel capabilities the engine found for itself (assumption dynamics, MDL depth, contradiction synthesis) ──
from .cascade import cascade, biggest_lever, Cascade
from .compression import compression_gain, most_compressing
from .dialectic import dialectic, all_syntheses, tensions
# ── orchestration: thread every capability into ONE analysis per idea ──
from .dossier import dossier, Dossier
# ── self-measurement: which capabilities EARN their keep (report, never delete) ──
from .health import health, operator_yield, capability_value, CapabilityReport
# ── the green-star zone: create with NO examples — pure first-principles structure ──
from .greenstar import (green_star, GreenStarExploration, synthesize_pack, synthesize_assumptions,
                        novel_axis, extrapolation, global_families, PRIMITIVES)

# ── the deeper pipeline (all pack-driven, all domain-agnostic) ──
from .theorem_sketch import sketch as theorem_sketch, TheoremSketch
# ── honest math discovery: conjecture → counterexample → empirical → (SymPy) formal proof ──
from .math_discovery import (investigate_conjecture, Conjecture, Counterexample, ProofAttempt,
                             MathDiscoveryResult, empirical_test, MATH_STATES, z3_backend,
                             lean_emit, lean_backend,
                             settle_lemma, LemmaCertificate, LEMMA_STATES, LEMMA_CERTIFIED)
# ── extra EXTERNAL prover/CAS backends (opt-in, degrade to TOOL_UNAVAILABLE): cvc5, Isabelle, Vampire/E, PARI ──
from .cvc5_backend import cvc5_backend
from .isabelle_backend import isabelle_backend, emit_isabelle_theory
from .atp_backend import atp_backend
from .pari_backend import pari_backend
from .solver_portfolio import portfolio_backend, default_backends
# ── the INVENTOR-first pipeline: the library as a DISCOVERER (the judge is a downstream service) ──
from .oracle_miner import (mine_invariants, guess_holonomic, guess_modular_pattern, guess_polynomial_recurrence,
                           guess_algebraic_gf, guess_polynomial_closed_form, guess_multiplicative, guess_asymptotic,
                           guess_k_automatic, MinedSparks, HolonomicRecurrence, PolynomialRecurrence, AlgebraicGF,
                           PolynomialClosedForm, MultiplicativeStructure, AsymptoticLaw, KAutomatic)
from .solution_type_lattice import (SOLUTION_FORMS, pivot as pivot_solution_type, next_form, describe as describe_form)
from .primitive_library import PrimitiveLibrary, Primitive, BASE_PRIMITIVES, compose, becomes_constant
from .autonomous_discovery import (autonomous_discover, certify_reduction, acquire_new_information,
                                   mechanism_generalizes, ScratchFrontier, DiscoveryResult,
                                   DISCOVERY_STATES as AUTONOMOUS_DISCOVERY_STATES)
# ── close the loop GENERATE→PROVE: generate conjectures, verify with z3/lean, refine the disproved ──
from .conjecture_search import (discover_conjectures, generate_conjectures, mine_conjectures_from_formula,
                                refine_with_counterexample_cells, ConjectureDiscovery, ConjectureResult)
from .paradigm_shift import paradigm_shift, ParadigmShift, SEVEN_QUESTIONS
from .reviewer import attack as reviewer_attack, AttackCard
from .world_designer import design_world_test, WorldTestSpec
from .missing_info import detect_missing_information, MissingInfoReport
from .lineage import declare_lineage, Lineage

__version__ = "2.1.0"

# Backward-compatible alias: historically this resolved to autonomous_discovery.DISCOVERY_STATES because that
# import came last. Keep it stable, but expose explicit aliases to avoid ambiguity for new callers.
DISCOVERY_STATES = AUTONOMOUS_DISCOVERY_STATES

# ── PRIMARY API — these are the only symbols you need to start. `__all__` is deliberately small so
#    `from OUTLIER_MCB import *` and the docs surface ONE clear way in. Everything else (the operators,
#    the market, the runtime internals) stays importable by its explicit name (e.g. gsl.recombine_assumptions)
#    as a documented building block — see __toolbox__ — but is not part of the headline API.
__all__ = [
    # the four ways in (the human–machine loop)
    "creative",                 # "break THIS assumption" — the one-call brief
    "judge",                    # "discipline MY idea" — run the rigor on the assistant's own proposal
    "invent",                   # the deep runtime: a portfolio of unknowns, each with an executable bet
    "green_star",               # the NO-EXAMPLES zone: pure first-principles structure, beyond the hull
    "preflight_creative_request",  # the full typed PreflightResult, if you want every field
    "list_packs", "get_pack", "register_pack",   # domain packs
    "pack_from_spec", "elicit_pack", "auto_elicit",   # build a pack for an unknown domain (auto_elicit = from the web)
    "DomainPack", "Assumption",                   # the two types a user constructs
    "OUTLIER_MCBError",                          # catch every fault
    "Judgment",                                   # the result of judge()
]

# Building blocks — importable by name, not in the headline API. Listed here so they are discoverable.
__toolbox__ = [
    # routing evidence
    "select_pack", "route_pack", "RouteDecision", "pack_quality",
    # kernel + scoring
    "kernel", "graph_of", "branch_on_assumptions", "no_solution_before_assumption", "novelty_score",
    # first-principles reviewer (critique beyond the pack's known families)
    "first_principles_attack", "FirstPrinciplesCritique", "FalsifiableObjection",
    # generative operators (break / non-break / discovery / agency)
    "generate", "Candidate", "recombine_assumptions", "invert_assumption", "scale_break",
    "transport_break", "what_would_have_to_be_true", "unify", "instrument", "reframe", "dissolve",
    "anomaly_to_assumption", "self_spark",
    # conceptual blending: fuse two domains into emergent structure (toward human-level invention)
    "conceptual_blend", "blend_emergence", "blend_domains",
    # grounding · honesty layer · novelty market · runtime internals
    "probe", "RepoContext", "assess_maturity", "Maturity", "STATUSES", "Bet", "Ledger", "forge_bet",
    "DiscoveryMemory", "AssumptionOutcome",
    "EpisodicMemory", "Episode", "AnalogicalMemory", "AnalogyOutcome",
    "CreativeMemoryRouter", "MemoryCue", "MemoryPlan",
    "autonomous_inventor", "InventionRun", "InventionStep",
    "curiosity_score", "bayesian_surprise", "discovery_reward", "curious_worth",
    "compile_world_test", "RepoCheck", "novelty_search", "push_further", "box_distance", "invent_reflect",
    "score_idea", "ScoreWeights", "calibrate_weights", "default_score_weights", "synergy_score",
    "readiness_report", "readiness_discovery_report", "READINESS_DISCOVERY_STATES",
    "DISCOVERY_STATES", "pack_quality", "iterative_elicit",
    "infer_domain_pack", "expand_pack_with_discovered_assumptions", "validate_inferred_pack", "pack_induction_ablation",
    # the rigor ladder (#9): lock strong words to the evidence rung they require
    "classify_claim", "gate_claim_language", "claim_ladder_ablation", "ClaimStatus", "LADDER",
    # closure-membership gate + representation theorems (FIX A/B/D/E)
    "reduces_to_closure", "closure_membership", "closure_escape_proven", "architectural_novelty",
    "robust_closure_verdict", "RobustClosureRecognizer", "semantic_closure_verdict", "combined_closure_verdict",
    "box_map", "box_map_markdown", "assumption_diff", "assumption_diff_markdown",
    "novelty_receipt", "verify_receipt", "receipt_markdown",
    "assert_outside_the_box", "assert_claim_honest", "NoveltyRegression", "ClaimOverreach",
    "lint_text", "lint_file", "lint_report",
    "handoff_contract", "accept_handoff", "handoff_report", "validate_world_test", "validate_broken_assumption",
    "UniversalClosure", "CLOSURE_REGISTRY", "ARCHITECTURE_LADDER",
    "theorem_brief", "find_theorem_for", "classify_proved_theorem", "RepresentationTheorem",
    "REPRESENTATION_THEOREMS", "honest_prior_art_status",
    "barrier_membership", "Barrier", "BarrierVerdict", "BARRIER_REGISTRY", "DEAD_BY_BARRIER", "NOT_BLOCKED",
    "FrontierLedger", "FrontierClaim", "ClaimResult", "is_certified", "CERTIFIED_STATUSES",
    "ACCEPTED", "REGRESSION_REJECTED", "UNCERTIFIED_REJECTED",
    "frontier_search", "FrontierSearchReport", "LemmaCandidate", "ResultCandidate", "propose_sublemmas",
    "Certificate", "is_external_certificate", "EXTERNAL_CERTIFICATES", "FORMAL_CERTIFICATES",
    "EMPIRICAL_CERTIFICATES", "META_CERTIFICATES", "RESOLVER_KINDS", "kind_of",
    "DiagnosticPoint", "DiagnosticLog", "DiagnosticMemory", "diagnostic_run", "self_diagnose",
    "DiagnosisReport", "PhaseWeakness", "POINT_STATUSES",
    "evolutionary_self_repair", "RepairProposal", "RepairResult", "verify_invariants", "library_health",
    "ProtectedInvariant", "InvariantReport", "INVARIANT_REGISTRY", "repair_brief", "RepairBrief",
    "verified_novelty", "verified_novelty_fitness", "assess_proposal", "Proposal", "VerifiedNoveltyReport",
    "pareto_improves",
    "grown_backend", "grown_basis_terms", "GROWN_PRIMITIVES", "MAX_GROWN_ARITY",
    "Landscape", "is_external_landscape", "EXTERNAL", "INTERNAL_ONLY",
    # active problem-finding (#4) · online analogy API (#5) · failure→mutation (#6) · divergent runner (#7) · real frontier (#8)
    "find_high_leverage_questions", "rank_problem_by_novelty_and_testability", "rank_questions",
    "generate_problem_family", "detect_problem_fixation", "problem_active_ablation",
    "discover_remote_mechanisms", "transfer_mechanism", "testable_analogy_claim", "analogy_prior_art_audit",
    "MechanismTransfer", "analogy_online_ablation",
    "compress_failure_to_lesson", "retrieve_lessons", "mutate_from_failure_lesson", "failure_lesson_ablation",
    "run_divergent_protocols", "score_protocol_output", "select_protocols_by_bandit", "DivergentResult", "protocol_ablation",
    "conceptual_novelty", "behavioral_novelty", "prior_art_novelty", "frontier_score", "behavior_signature",
    "sparse_unknown_regions", "frontier_ablation",
    "NoveltyObjectiveEvaluator", "NoveltyObjectiveWeights", "novelty_objective", "recursive_novelty_search",
    # semantic repo grounding (#2): AST world-model, impact surface, file-anchored falsifiers
    "analyze_repo_semantics", "repo_world_model", "impact_surface", "suggest_repo_falsifiers",
    "is_grounded", "repo_grounding_ablation", "RepoModel", "ModuleInfo",
    "validate_artifact_contract", "artifact_contract_score", "artifact_class", "materialized_artifact", "expected_test_present",
    "run_check", "verify", "Verdict", "verifiability_class",
    "verify_red_green", "materialized", "RedGreen",
    "settle_by_materialization", "synthesize_artifact", "MaterializationReceipt", "SynthArtifact",
    "score_pool", "verified_novelty_score", "broken_assumption_rate", "falsifiability_score",
    "unique_frontier_ratio", "rebranding_risk_rate", "artifact_specificity", "auto_verifiability_rate",
    # self-found novel capabilities + orchestration
    "cascade", "biggest_lever", "Cascade", "compression_gain", "most_compressing",
    "dialectic", "all_syntheses", "tensions", "dossier", "Dossier", "operator_diversity",
    "health", "operator_yield", "capability_value", "CapabilityReport",
    # green-star zone (no examples)
    "GreenStarExploration", "synthesize_pack", "synthesize_assumptions", "novel_axis",
    "extrapolation", "global_families", "PRIMITIVES",
    # deeper pipeline (all pack-driven)
    "theorem_sketch", "paradigm_shift", "reviewer_attack", "design_world_test",
    # honest math discovery (Step 7)
    "investigate_conjecture", "Conjecture", "Counterexample", "ProofAttempt", "MathDiscoveryResult",
    "empirical_test", "MATH_STATES", "z3_backend", "lean_emit", "lean_backend",
    "settle_lemma", "LemmaCertificate", "LEMMA_STATES", "LEMMA_CERTIFIED",
    "cvc5_backend", "isabelle_backend", "emit_isabelle_theory", "atp_backend", "pari_backend",
    "portfolio_backend", "default_backends",
    "mine_invariants", "guess_holonomic", "guess_modular_pattern", "guess_polynomial_recurrence",
    "guess_algebraic_gf", "guess_polynomial_closed_form", "guess_multiplicative", "guess_asymptotic",
    "guess_k_automatic", "MinedSparks", "HolonomicRecurrence", "PolynomialRecurrence", "AlgebraicGF",
    "PolynomialClosedForm", "MultiplicativeStructure", "AsymptoticLaw", "KAutomatic",
    "SOLUTION_FORMS", "pivot_solution_type", "next_form", "describe_form",
    "PrimitiveLibrary", "Primitive", "BASE_PRIMITIVES", "compose", "becomes_constant",
    "autonomous_discover", "certify_reduction", "acquire_new_information", "mechanism_generalizes",
    "ScratchFrontier", "DiscoveryResult", "AUTONOMOUS_DISCOVERY_STATES", "DISCOVERY_STATES",
    # GENERATE→PROVE conjecture search
    "discover_conjectures", "generate_conjectures", "mine_conjectures_from_formula",
    "refine_with_counterexample_cells", "ConjectureDiscovery", "ConjectureResult",
    "detect_missing_information", "declare_lineage", "emit_assistant_instructions",
    # real-world novelty + red-first materialization (autonomous research / stronger-than-specificity metric)
    "novelty_audit", "NoveltyVerdict", "world_novelty_score",
    "prior_art_audit", "prior_art_distance_score", "source_overlap_score",
    "rebranding_detector", "collage_detector", "GRADED_VERDICTS",
    "materialization_score", "materialization_evidence",
    # real multi-source prior art + honest novelty_scope (Step 1)
    "PriorArtProvider", "PriorArtResult", "OfflinePriorArtProvider", "OnlinePriorArtProvider",
    "CompositePriorArtProvider", "ArxivPriorArtProvider", "OpenAlexProvider", "GitHubPriorArtProvider",
    "PriorArtError", "NOVELTY_SCOPES", "novelty_scope_of", "coverage_level_of", "CachedPriorArtProvider",
    "OfflineCorpusProvider", "KnownMethod", "KNOWN_METHODS", "known_method_names",
    "epistemic_gate_ablation", "GateAblation",
    "CrossrefProvider", "GitHubCodeSearchProvider", "CallableOnlineProvider", "default_online_provider",
    "discovery_confidence",
    # Quality-Diversity (MAP-Elites) + formal Novelty Search + intrinsic goal-setter
    "illuminate", "QDArchive", "BehaviorDescriptor",
    "NoveltyArchive", "behavior_descriptor", "propose_goal",
    "find_problems", "Problem", "ProblemPortfolio",
    "transform_space", "propose_transformation", "TransformationResult", "TRANSFORMATION_STATES",
    "creative_search", "structural_evaluator", "code_evaluator", "CreativeSearchResult", "CreativeRecord",
    # external evaluators (settle by the DATA, not by self-judgment)
    "symbolic_evaluator", "basis_from_candidate", "expansions_for", "least_squares", "Formula", "Term",
    "DEFAULT_BUILDERS", "causal_evaluator",
    # optional real backends (lazy import; no hard dependency)
    "pysr_backend", "gplearn_backend", "dowhy_backend",
    # unified objective evaluator interface (the VERIFY half) + evolutionary invention
    "EvaluationResult", "BaseEvaluator", "CallableEvaluator", "PropertyEvaluator",
    "NoveltyEvaluator", "PytestEvaluator", "CompositeEvaluator", "HiddenEvaluator",
    # harder verification + better experiments + interestingness
    "interestingness_score", "Experiment", "next_best_experiment", "expected_information_gain",
    "disambiguation_score", "cost_of_test", "WorldTestGenerator", "GeneratedWorld",
    # a dedicated red team (generates attacks) + staged falsification (experiment DAG)
    "RedTeamEvaluator", "Attack", "boundary_attacks", "negative_control_attacks", "rebrand_attack",
    "red_team_from_check", "ExperimentDAG", "ExperimentStep", "ExperimentOutcome", "DAGReport",
    # evaluator synthesis (#3): assemble a settling evaluator (public/hidden/controls) from a claim's materials
    "synthesize_evaluator", "validate_evaluator", "evaluator_quality_score", "evaluator_ablation",
    "SynthesizedEvaluator", "EvaluatorSynthesisError",
    # the gameability/ablation gate (a metric earns its place only if it flips a keep/drop decision)
    "ablation_gate", "ablation_gate_from_records", "AblationReport", "ComponentVerdict", "INVENTION_COMPONENTS",
    "reward_hacking_report", "HackVerdict",
    # memory that learns from failures
    "FailureLesson", "LessonMemory", "summarize_failure_mode", "FAILURE_MODES",
    "EvolutionMemory", "EvolutionRecord", "evolve_invention", "invention_score", "EvolveResult",
    "symbolic_invention_task", "causal_invention_task",
    # evolution operators · prompt sampler · unknown-space search · recursive self-evolve
    "MutationResult", "mutate_assumption", "mutate_mechanism", "mutate_objective", "add_falsifier",
    "simplify_candidate", "generalize_candidate", "recombine_distant", "cross_domain_transfer",
    "novelty_push", "ALL_OPERATORS", "PromptSampler", "STRATEGIES",
    "suggest_unknown_region", "novelty_frontier", "unexplored_assumptions", "unexplored_axes",
    "recommend_next_mutations", "failure_clusters", "UnknownRegion",
    "self_evolve", "SelfEvolveResult", "validate_improvement_patch",
    # lateral thinking + open-ended search (de Bono provocation, Koestler bisociation, novelty rejection, UCB)
    "provocation", "random_entry", "is_novel_enough", "novelty_first", "OperatorBandit",
    # competitor-derived: cross-domain analogy · POET problem generation · DreamCoder abstractions · Voyager skills
    "CrossDomainAnalogyEngine", "Analogy", "OnlineCrossDomainAnalogyEngine", "OnlineMechanism", "DISTANT_DOMAINS",
    "ProblemGenerator", "GeneratedProblem",
    "mine_abstractions", "compress_candidates_to_concepts", "mine_mechanism_abstractions", "Concept", "ConceptLibrary",
    # T2.1 earned taste — a learned, calibrated value over unverified ideas
    "EarnedTaste", "candidate_features", "earned_taste_from_ledger", "earned_taste_from_records", "taste_rerank",
    # T2.5 verification economy — cheap calibrated proxies for expensive world-tests
    "VerificationEconomy", "ProxyCalibration", "SettlementOutcome", "calibrate_proxy", "as_verdict",
    # T2.3 incubation — offline reconnection of dead ends & distant wins (delayed insight)
    "incubate", "revive_barren", "IncubatedConnection", "RevivedDeadEnd",
    # T2.2 executable active-experiment loop — acquire new information to shrink a hypothesis space
    "Hypothesis", "ActiveExperimentResult", "RunStep", "build_experiments", "run_active_experiments",
    # the composed scientific loop orchestrating every capability
    "autonomous", "AutonomousResult",
    # the math toward-objective loop (frontier_search + sub-lemmas + solution-form pivot)
    "math_frontier", "MathFrontierResult",
    # T2.4 representation invention — a new encoding that makes the hard easy, gated by a control
    "Representation", "ReducibilityVerdict", "representation_reducibility", "invent_representation",
    # Point 1 physics invention — invent toy universes, scored by external emergence (structure not disorder)
    "Physics", "Law", "propose_new_physics", "elementary_physics", "run_simulation", "measure_emergence",
    "emergence_of", "coherence_controls_pass",
    # Point 2 endogenous semantic grounding — self-coined concepts scored by MDL conceptual compression
    "EndogenousSymbol", "SymbolRegistry", "find_recurring_patterns", "ground_new_symbol", "verify_grounding",
    "conceptual_compression", "grounding_controls_pass",
    # Point 3 formal-language invention — a primitive-set DSL with a sound interpreter, scored by expressive power
    "FormalLanguage", "integer_baseline", "invent_new_language", "shortest_program", "expressive_power",
    "is_sound", "soundness_controls_pass",
    # Point 4 aesthetics — objective AST beauty metrics + elegance as a strict Pareto dimension
    "measure_symmetry", "measure_simplicity", "measure_surprise", "elegance_score", "aesthetics_objectivity_pass",
    "Skill", "SkillLibrary", "SEED_SKILLS",
    # cognitive agent roles + auditable reasoning trace
    "CognitivePanel", "AgentEvidence", "PanelReport", "ReasoningTrace", "ActionStep", "EvidenceLedger",
    "LinearCausalWorld", "CounterfactualExperiment",
    "counterfactual_world_prediction_collapses_when_edge_shuffled",
    "experiment_splits_hypotheses_better_than_random_probe", "RoleReputation", "role_vote_weight",
    "ExecutableSkill", "DiscoveryArtifact", "idea_without_artifact_cannot_enter_discovery_ledger",
    "research_taste_score", "taste_prefers_small_deep_mechanism_over_large_trivial_result",
    # the single front door + activation routine for AI assistants
    "explore", "StudioReport", "demo",
    "assistant_brief", "assistant_route", "AssistantRoute", "activation_snippet", "should_activate",
    "SUPPORTED_ASSISTANT_LANGUAGES", "STANDING_RULES", "TRIGGERS",
    "capabilities", "capabilities_markdown", "Capability",
    # the Automated Scientist Loop (Point 4)
    "discover", "Discovery", "DiscoveredLaw",
    "diverge", "DivergenceResult", "DivergentIdea",
    "LexicalEmbedder", "NgramEmbedder", "CallableEmbedder", "semantic_distance", "default_embedder",
    "set_default_embedder", "reset_default_embedder",
    "thought_tree", "ThoughtTree", "ThoughtNode", "prune_by_external_score", "self_refine", "ReflectionMemory",
    "CognitiveMove", "CognitiveProtocolResult", "scamper", "geneplore", "functional_fixedness_breaker",
    "remote_association", "cognitive_extremes",
    "propose_self_improvements", "SelfImprovementReport", "SelfImprovementProposal",
    # LLM-in-the-loop (opt-in: real generation + test/patch materialization + executable scoring)
    "LLMProvider", "CallableLLMProvider", "SubprocessLLMProvider", "parse_candidates", "CANDIDATE_SCHEMA",
    "set_default_llm", "reset_default_llm", "default_llm",
    "CommandRunner", "CommandResult", "UnsafeCommandError", "to_argv",
    "parse_unified_diff", "validate_patch_paths", "apply_patch_plan", "PatchPlan",
    "PatchTransaction", "patch_substance_score", "patch_substance_evidence", "is_test_path",
    "llm_openended_search", "llm_evidence_score", "LLMSearchResult", "LLMCandidate",
    "score_components", "classify_test_outcome", "test_quality_score", "test_quality_evidence",
    "DEFAULT_SCORE_WEIGHTS",
    # faults + typed outputs
    "PackNotFoundError", "InvalidPackError", "AssumptionNotFoundError",
    "PreflightResult", "MissingInfo", "BreakOption", "HiddenAssumption",
]

# A small glossary so the method's vocabulary is documented, not hidden (the terms are load-bearing,
# like 'gradient' in optimization — but the OUTPUT and these definitions speak plainly).
GLOSSARY = {
    "box": "the most-probable / average solution for a domain — what an LLM answers from memory.",
    "INSIDE_THE_BOX": "a proposal that breaks no hidden assumption — not yet an answer, by design.",
    "green_star": "the most radical, reframing negation of an assumption (vs a weak or moderate one).",
    "death_gate": "the conditions under which any idea is rejected (reducible / no signal / leakage).",
    "anti_collage": "the rule that combining known mechanisms is not novelty unless it beats its parts.",
    "box_distance": "how unlike the average answer a candidate is — the anti-loss-function metric.",
    "bet": "the unit of output: a claim + the test that settles it + what you'd stake (see economy.py).",
}
