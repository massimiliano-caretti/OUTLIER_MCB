"""evolve — the AlphaEvolve-useful loop, kept honest: generate → evaluate → remember → select → mutate.

This is the part of AlphaEvolve that serves invention (NOT optimization-for-its-own-sake): a population of
candidates evolved under an OBJECTIVE evaluator, with full lineage, compared to baseline and parent, scored
multi-objectively with HARD honesty caps, and reported auditably. It reuses OUTLIER_MCB's own machinery —
generators (breadth + mutation/recombination), the evaluator interface, prior-art scope, evolution memory —
rather than reimplementing a coding optimizer. A candidate that is not evaluated cannot win; a 'novelty'
without a confirmed online search cannot score high; an improvement must beat baseline OR parent on the metric.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from .evolution_memory import EvolutionMemory, EvolutionRecord


def _clamp(x) -> float:
    return max(0.0, min(1.0, float(x or 0)))


# ── multi-objective invention scoring with the spec's HARD caps ─────────────────────────────────────
def invention_score(c: Dict) -> Dict:
    """Decomposable, explainable invention score in [0,1] with non-negotiable caps:
      • correctness False ⇒ score ≤ 0.25 (plausible ≠ verified);
      • novelty component capped by novelty_scope: LOCAL_ONLY ≤0.55 · INCOMPLETE ≤0.35 ·
        ONLINE+PARTIAL ≤0.82 · ONLINE+MULTI/STRONG up to 1.0;
      • improvement counts only if it beats baseline OR parent.
    Returns {score, components, caps_applied}."""
    correctness = bool(c.get("correctness", False))
    scope, coverage = c.get("novelty_scope", ""), c.get("coverage_level", "")
    nov_cap = {"ONLINE_PRIOR_ART_CHECKED": (1.0 if coverage in ("MULTI", "STRONG") else 0.82),
               "INCOMPLETE_ONLINE_SEARCH": 0.35, "LOCAL_ONLY": 0.55, "": 0.55}.get(scope, 0.55)
    novelty = min(_clamp(c.get("novelty_distance", 0)), nov_cap)
    improvement = _clamp(max(c.get("improvement_over_baseline", 0) or 0, c.get("improvement_over_parent", 0) or 0))
    comp = {
        "correctness": 1.0 if correctness else 0.0,
        "novelty": round(novelty, 3),
        "improvement": round(improvement, 3),
        "assumption_break_depth": _clamp(c.get("assumption_break_depth", 0)),
        "diversity": _clamp(c.get("diversity", 0)),
        "usefulness_proxy": _clamp(c.get("usefulness_proxy", 0)),
        "test_quality": _clamp(c.get("test_quality", 0)),
        "reproducibility": _clamp(c.get("reproducibility", 0)),
        "simplicity": _clamp(c.get("simplicity", 0)),
        "risk_penalty": _clamp(c.get("risk", 0)),
    }
    base = (0.30 * comp["correctness"] + 0.18 * comp["novelty"] + 0.18 * comp["improvement"]
            + 0.10 * comp["assumption_break_depth"] + 0.08 * comp["diversity"] + 0.06 * comp["usefulness_proxy"]
            + 0.04 * comp["test_quality"] + 0.03 * comp["reproducibility"] + 0.03 * comp["simplicity"]
            - 0.10 * comp["risk_penalty"])
    caps = []
    score = _clamp(base)
    if not correctness:
        score = min(score, 0.25)
        caps.append("correctness_failed → score capped at 0.25")
    if scope in ("", "LOCAL_ONLY"):
        caps.append(f"novelty capped at {nov_cap} (no confirmed online prior-art search)")
    comp["novelty_cap"] = nov_cap
    return {"score": round(score, 4), "components": comp, "caps_applied": caps}


# ── the evolve loop ─────────────────────────────────────────────────────────────────────────────────
@dataclass
class EvolveResult:
    problem: str
    memory: EvolutionMemory
    baseline_score: float
    rounds: int = 0
    note: str = ""
    trace: object = None             # a ReasoningTrace of how the run reasoned (auditable)
    concept_library: object = None   # mined abstractions (DreamCoder) when mine_concepts=True
    mechanism_library: object = None # mined cross-cutting MECHANISMS (levers reused across different break-
                                     # sets / axes hit by different levers) when mine_concepts=True — strictly
                                     # richer than exact break-set clusters (Tier-1 wiring of an orphan)
    lesson_memory: object = None     # LessonMemory consulted DURING the loop (orchestrate=True)
    novelty_archive: object = None   # NoveltyArchive of behaviors seen DURING the loop (orchestrate=True)
    fixation: object = None          # the final problem-fixation verdict (orchestrate=True)

    def best(self) -> Optional[EvolutionRecord]:
        recs = self.memory.by_problem(self.problem)
        return max(recs, key=lambda r: r.score) if recs else None

    @property
    def externally_settled(self) -> bool:
        """True iff the best candidate was certified by an EXTERNAL resolver — never by self-judgment (fix A)."""
        b = self.best()
        return bool(b and b.externally_settled)

    def settled_best(self) -> Optional[EvolutionRecord]:
        """The best candidate that an EXTERNAL resolver actually settled — the only kind that may be called
        'verified'. Returns None when nothing was externally settled (then the run produced hypotheses only)."""
        settled = [r for r in self.memory.by_problem(self.problem) if r.externally_settled]
        return max(settled, key=lambda r: r.score) if settled else None

    def panel(self, pack, provider=None):
        """Run the cognitive panel (Skeptic/Adversary/PriorArtHunter/Analogist/…) on the best candidate —
        the roles deliberate over the winning idea and surface the path to its verdict."""
        from .agents import CognitivePanel
        b = self.best()
        return CognitivePanel(pack, provider=provider).deliberate(b.claim if b else self.problem)

    def lessons(self):
        """A LessonMemory mined from this run's records — the operational failure modes to avoid next time."""
        from .failure_lessons import LessonMemory
        lm = LessonMemory()
        lm.record_all(self.memory.by_problem(self.problem))
        return lm

    def honest_headline(self) -> str:
        """A one-line claim about the best candidate, passed through the rigor ladder (#9): strong words
        ('verified', 'novel') survive ONLY if the evidence licenses them — external settlement licenses
        'verified', an online prior-art check licenses 'novel'. Otherwise they are rewritten to honest hedges."""
        from .claim_ladder import gate_claim_language
        b = self.best()
        if b is None:
            return "no candidate evaluated."
        raw = f"candidate «{b.candidate_name}» is a verified, novel improvement over the baseline."
        evidence = {"external_settlement": b.externally_settled,
                    "prior_art_checked": b.novelty_scope == "ONLINE_PRIOR_ART_CHECKED",
                    "empirical_support": b.is_improvement, "falsifier": True}
        return gate_claim_language(raw, evidence)["rewritten"]

    def ablation(self, keep_fraction: float = 0.5):
        """The gameability/ablation gate (fix C) over THIS run's population: which scoring components actually
        changed who was kept, and which were decorative. Self-discipline for the engine's own metrics."""
        from .ablation import ablation_gate_from_records
        return ablation_gate_from_records(self.memory.by_problem(self.problem), keep_fraction=keep_fraction)

    def conservative_statement(self) -> str:
        b = self.best()
        if b is None:
            return "insufficient evidence — no candidate evaluated."
        if not b.verified:
            return "insufficient evidence — the best candidate was not verified by an evaluator."
        if not b.externally_settled:
            return ("scored, but NOT externally certified — an internal score cannot confer 'verified'; "
                    "the engine does NOT judge itself. Settle it with an external resolver (a repo test that "
                    "flips, the data, a red-team, a world-test) before calling anything verified.")
        nov = (b.prior_art_scoped_verdict or "").upper()
        # fix B: the 'novel' label is granted ONLY under a successful ONLINE prior-art search; otherwise refused.
        novel = ("provisionally novel on checked sources" if "ON_CHECKED" in nov
                 else "novelty NOT established (no successful online prior-art search — wire default_online_provider())")
        imp = "a candidate improvement over baseline/parent" if b.is_improvement else "no measured improvement"
        return (f"candidate VERIFIED by external resolver «{b.external_resolver}» · {imp} · {novel} "
                "(never 'absolute novelty' / 'proved' without formal proof + online prior-art + verifier).")

    def to_dict(self) -> Dict:
        b = self.best()
        return {
            "problem": self.problem, "baseline_score": self.baseline_score, "rounds": self.rounds,
            "candidates": len(self.memory.by_problem(self.problem)),
            "best": None if b is None else {
                "id": b.id, "name": b.candidate_name, "score": b.score, "verified": b.verified,
                "externally_settled": b.externally_settled, "external_resolver": b.external_resolver,
                "score_components": b.score_components, "novelty_scope": b.novelty_scope,
                "prior_art_scoped_verdict": b.prior_art_scoped_verdict,
                "improvement_over_baseline": b.improvement_over_baseline,
                "improvement_over_parent": b.improvement_over_parent,
                "lineage": [r.id for r in self.memory.lineage(b.id)], "mutation_operator": b.mutation_operator},
            "regressions": [r.id for r in self.memory.by_problem(self.problem)
                            if (r.improvement_over_parent or 0) < 0],
            "statement": self.conservative_statement(),
        }

    def markdown(self) -> str:
        d = self.to_dict()
        L = [f"# Evolution report — «{self.problem}»",
             f"- baseline {self.baseline_score} · candidates {d['candidates']} · rounds {self.rounds}"]
        b = d["best"]
        if b:
            L += [f"- **best:** {b['name']} (score {b['score']}, verified={b['verified']}, "
                  f"externally_settled={b['externally_settled']}"
                  + (f" by «{b['external_resolver']}»" if b['externally_settled'] else "") + ")",
                  f"  - components: " + " · ".join(f"{k}={v}" for k, v in b["score_components"].items()),
                  f"  - novelty_scope: {b['novelty_scope']} · verdict: {b['prior_art_scoped_verdict']}",
                  f"  - Δbaseline: {b['improvement_over_baseline']} · Δparent: {b['improvement_over_parent']}",
                  f"  - lineage: {' → '.join(reversed(b['lineage']))}"]
        if d["regressions"]:
            L.append(f"- regressions blocked: {d['regressions']}")
        L.append(f"\n**Statement (conservative):** {d['statement']}")
        return "\n".join(L)


def _components_for(candidate, result, baseline_score, parent_score, novelty_art, memory, problem) -> Dict:
    from .embeddings import semantic_distance
    breaks = list(getattr(candidate, "breaks", []) or [])
    text = f"{getattr(candidate, 'name', '')} {getattr(candidate, 'negation', '')}"
    others = memory.by_problem(problem)
    diversity = (min((semantic_distance(text, f"{r.candidate_name} {r.claim}") for r in others), default=1.0)
                 if others else 1.0)
    return {
        "correctness": result.passed,
        "novelty_distance": (novelty_art or {}).get("distance", 0.0),
        "novelty_scope": (novelty_art or {}).get("novelty_scope", ""),
        "coverage_level": (novelty_art or {}).get("coverage_level", ""),
        "improvement_over_baseline": (result.score - baseline_score) if baseline_score is not None else 0.0,
        "improvement_over_parent": (result.score - parent_score) if parent_score is not None else 0.0,
        "assumption_break_depth": min(1.0, len(set(breaks)) / 2.0),
        "diversity": diversity,
        "usefulness_proxy": result.score if result.passed else 0.0,
        "test_quality": 1.0 if result.passed else 0.0,
        "reproducibility": 1.0,                          # deterministic evaluators here
        "simplicity": max(0.0, 1.0 - len(getattr(candidate, "assumptions", []) or []) / 4.0),
        "risk": min(1.0, len(getattr(candidate, "needs", []) or []) / 3.0),
    }


def _llm_candidates(problem: str, pack, llm, n: int = 4) -> List:
    """An external LLM PROPOSER: it proposes content; the objective evaluator (never the LLM, never the
    engine) decides. Parses the model's JSON candidates into the engine's Candidate type. Opt-in: without
    an `llm` nothing changes. No hard dependency — `llm` is any object with `.complete(prompt, system, n)`."""
    from .llm import parse_candidates
    from .generators import Candidate
    system = ("Break a hidden assumption the standard solutions share. Reply ONLY with a JSON array of "
              '{"name","broken_assumption","operator","claim","why_standard_families_fail",'
              '"world_test_description","test_patch","implementation_patch","novelty_rationale","risk"}.')
    out: List = []
    try:
        completions = llm.complete(f"PROBLEM: {problem}\nDOMAIN BOX: {pack.box_name}\nReturn {n} candidates.",
                                   system=system, n=1)
    except Exception:
        return out
    for comp in completions:
        for cd in parse_candidates(comp).valid:
            ba = str(cd.get("broken_assumption", "")).strip()
            axis = pack.dimension_of.get(ba, "")
            out.append(Candidate(name=str(cd.get("name", "llm"))[:48], operator="llm_proposed",
                                 breaks=[axis] if axis else [], assumptions=[ba] if ba else [],
                                 negation=str(cd.get("claim", "")), needs=[],
                                 discipline=str(cd.get("world_test_description", ""))))
    return out[:n]


def _novelty_art(candidate, provider) -> Optional[Dict]:
    if provider is None:
        return None
    from .novelty import prior_art_audit
    text = f"{getattr(candidate, 'name', '')} {getattr(candidate, 'negation', '')}"
    nv = prior_art_audit(text, provider)
    return {"distance": nv.prior_art_distance_score, "novelty_scope": nv.novelty_scope or "LOCAL_ONLY",
            "coverage_level": nv.coverage_level, "scoped_verdict": nv.scoped_verdict()}


def evolve_invention(problem: str, evaluator, budget: int = 24, memory: Optional[EvolutionMemory] = None,
                     pack=None, prior_art_provider=None, mode: str = "breadth", baseline_candidate=None,
                     lateral: bool = False, reject_near_duplicates: bool = False,
                     novelty_threshold: float = 0.9, use_analogy: bool = False,
                     mine_concepts: bool = False, llm=None, cognitive_protocols: bool = False,
                     orchestrate: bool = False) -> EvolveResult:
    """Evolve candidates for `problem` under an objective `evaluator` (a BaseEvaluator). `mode='breadth'`
    explores many distinct candidates; `'depth'` improves a few through mutation chains. Every candidate is
    evaluated, scored with `invention_score`, compared to baseline + parent, and recorded with lineage.

    `lateral=True` seeds in human-like lateral moves (provocation + random-entry/bisociation).
    `reject_near_duplicates=True` (ShinkaEvolve's novelty rejection sampling) refuses to spend the budget on
    a candidate too similar to the population — both opt-in, so the default loop is unchanged."""
    from .pack import select_pack, list_packs, get_pack
    from .generators import generate_candidates, invert_assumption, scale_break, dissolve, conceptual_blend, breakable
    from .lateral import is_novel_enough, provocation, random_entry
    from .evaluators.base import BaseEvaluator, CallableEvaluator
    if not isinstance(evaluator, BaseEvaluator):
        evaluator = CallableEvaluator(evaluator, name="objective", passed_key="controls_collapse")
    if pack is None:
        pack, _ = select_pack(problem)
    memory = memory if memory is not None else EvolutionMemory()
    counter = [0]
    # orchestration memories — consulted DURING the loop, not only after it (fixes the write-only/post-hoc gaps)
    lesson_mem = novelty_arch = None
    if orchestrate:
        from .failure_lessons import LessonMemory, summarize_failure_mode, mutate_from_failure_lesson
        from .novelty_archive import NoveltyArchive, behavior_descriptor
        from .problem_active import detect_problem_fixation
        from .lateral import provocation as _provocation, random_entry as _random_entry
        lesson_mem, novelty_arch = LessonMemory(), NoveltyArchive()

    # baseline: a non-breaking candidate (the box) settled by the same evaluator
    if baseline_candidate is None:
        from .generators.base import Candidate
        baseline_candidate = Candidate(name="baseline_box", operator="unify", breaks=[], assumptions=[],
                                       negation="the additive/box baseline (breaks nothing)")
    baseline_score = round(evaluator.evaluate(baseline_candidate).score, 4)

    def _ingest(candidate, generation, parents, parent_score, operator):
        counter[0] += 1
        result = evaluator.evaluate(candidate)
        nart = _novelty_art(candidate, prior_art_provider)
        comps = _components_for(candidate, result, baseline_score, parent_score, nart, memory, problem)
        scored = invention_score(comps)
        rid = f"g{generation}-{counter[0]:03d}"
        rec = EvolutionRecord(
            id=rid, problem=problem, candidate_name=getattr(candidate, "name", rid),
            claim=getattr(candidate, "negation", ""), parent_ids=[p.id for p in parents], generation=generation,
            broken_assumptions=list(getattr(candidate, "assumptions", []) or []),
            evaluator_name=getattr(evaluator, "name", "objective"),
            external_resolver=(getattr(evaluator, "name", "objective")
                               if getattr(evaluator, "settles_externally", False) and result.passed else ""),
            score=scored["score"],
            score_components=scored["components"], correctness_passed=result.passed,
            novelty_scope=(nart or {}).get("novelty_scope", ""),
            prior_art_scoped_verdict=(nart or {}).get("scoped_verdict", ""),
            baseline_score=baseline_score, parent_score=parent_score,
            improvement_over_baseline=comps["improvement_over_baseline"],
            improvement_over_parent=comps["improvement_over_parent"], mutation_operator=operator,
            created_at=str(counter[0]), metadata={"caps": scored["caps_applied"], "evaluator_passed": result.passed})
        memory.add(rec)
        if orchestrate:                                  # feed the loop's memories every ingest (read back below)
            lesson_mem.record(rec)
            novelty_arch.add(behavior_descriptor(candidate))
        return rec, candidate

    def _accept(candidate) -> bool:
        """Novelty rejection sampling (opt-in): refuse a candidate too similar to what is already recorded."""
        if not reject_near_duplicates:
            return True
        text = f"{getattr(candidate, 'name', '')} {getattr(candidate, 'negation', '')}"
        existing = [f"{r.candidate_name} {r.claim}" for r in memory.by_problem(problem)]
        return is_novel_enough(text, existing, threshold=novelty_threshold)[0]

    from .trace import ReasoningTrace
    trace = ReasoningTrace(problem=problem)
    trace.log("baseline", why="settle the box baseline on the same objective", output=f"baseline_score={baseline_score}")

    # generation 0: breadth (many distinct candidates) + optional lateral / cross-domain-analogy seeds
    seeds = list(generate_candidates(pack, problem))
    if lateral:
        seeds = [c for c in (provocation(pack), random_entry(pack)) if c is not None] + seeds
        trace.log("lateral_seeds", why="inject de Bono provocation + Koestler bisociation", output="2 lateral moves")
    if use_analogy:
        from .analogy import CrossDomainAnalogyEngine
        ana = [a.candidate for a in CrossDomainAnalogyEngine(pack).best_analogies(2) if a.candidate is not None]
        seeds = ana + seeds
        trace.log("cross_domain_analogy", why="transfer mechanisms from the farthest domains", output=f"{len(ana)} analogies")
    if cognitive_protocols:
        from .cognitive_protocols import cognitive_extremes
        cog = cognitive_extremes(problem, pack=pack)
        seeds = cog.candidates + seeds
        trace.log("cognitive_protocols",
                  why="inject Geneplore/SCAMPER/fixedness/remote-association seed moves",
                  output=f"{len(cog.candidates)} cognitive seeds; scores={cog.scores}")
    if orchestrate:
        # #6: run the divergent protocols COMPETITIVELY (UCB bandit) instead of injecting them flat — a
        # protocol that never produces an original, falsifiable candidate is dropped; the rest seed the search.
        from .divergent_runner import run_divergent_protocols
        dv = run_divergent_protocols(problem, pack)
        seeds = dv.candidates + seeds
        trace.log("divergent_runner",
                  why="competitive SCAMPER/Geneplore/remote-association/… under a UCB bandit; non-productive dropped",
                  output=f"{len(dv.candidates)} candidates; kept={dv.kept}; dropped={dv.dropped}")
    if llm is not None:
        proposed = _llm_candidates(problem, pack, llm, n=4)   # a REAL external proposer — settled by the evaluator, never self-judged
        seeds = proposed + seeds
        trace.log("llm_proposer", why="an external LLM proposes content; the objective evaluator (not the LLM) decides",
                  output=f"{len(proposed)} LLM candidates")
    width = budget if mode == "breadth" else max(3, budget // 3)
    gen0 = [_ingest(c, 0, [], None, c.operator) for c in seeds[:width] if _accept(c)]
    spent = len(gen0)
    trace.log("generation_0", why=f"{mode}: evaluate the seed pool by the objective", output=f"{spent} candidates")

    # generations 1..: mutate/recombine the diverse elites (depth)
    foreign = next((get_pack(n) for n in list_packs() if n not in (pack.name, "generic")), None)
    gen, by_id = 1, {r.id: c for r, c in gen0}
    while spent < budget:
        parents = memory.diverse_top_k(3, problem=problem)
        if not parents:
            break
        # READ BACK the fixation signal each round: if the population keeps attacking one assumption, break OUT
        # with a provocation / random-entry seed onto a different axis (instead of mutating the same lever again).
        if orchestrate and spent < budget:
            fox = detect_problem_fixation(memory.by_problem(problem))
            if fox["fixated"]:
                escape = _provocation(pack) or _random_entry(pack)
                if escape is not None and _accept(escape):
                    erec, ecand = _ingest(escape, gen, [], None, "fixation_escape")
                    by_id[erec.id] = ecand
                    spent += 1
                    trace.log("fixation_escape", why=f"population fixated on «{fox['dominant_seed']}» ({fox['share']})",
                              output="injected a provocation onto a different axis")
        progressed = False
        for i, prec in enumerate(parents):
            if spent >= budget:
                break
            pcand = by_id.get(prec.id)
            names = (pcand.assumptions if pcand else None) or [a.name for a in breakable(pack)]
            if not names:
                continue
            nm = names[(gen + i) % len(names)]
            ops = [("invert", lambda: invert_assumption(pack, nm)),
                   ("scale", lambda: scale_break(pack, nm, factor=1000)),
                   ("dissolve", lambda: dissolve(pack, nm)),
                   ("recombine_distant", lambda: conceptual_blend(pack, foreign) if foreign else None)]
            # READ BACK a failure lesson: if this parent failed, add the repair mutation its mode prescribes
            if orchestrate and pcand is not None and not prec.externally_settled:
                lesson = summarize_failure_mode(prec)
                if lesson is not None:
                    mr = mutate_from_failure_lesson(pcand, lesson, pack, prec.id)
                    if mr is not None and mr.candidate is not None:
                        ops = ops + [("lesson_repair", lambda r=mr.candidate: r)]
            op_name, op = ops[(gen + i) % len(ops)]
            child = op()
            if child is None or not _accept(child):
                continue
            rec, ccand = _ingest(child, gen, [prec], prec.score, op_name)
            by_id[rec.id] = ccand
            spent += 1
            progressed = True
        gen += 1
        if not progressed:
            break

    concept_library = mechanism_library = None
    if mine_concepts:
        from .abstraction import mine_abstractions, mine_mechanism_abstractions
        concept_library = mine_abstractions(memory, min_support=2)
        trace.log("mine_abstractions", why="extract reusable concepts shared by several candidates (DreamCoder)",
                  output=f"{len(concept_library.concepts)} concepts")
        # Tier-1: ALSO mine cross-cutting MECHANISMS — a lever reused across DIFFERENT break-sets, or an axis
        # hit by different levers — which the exact-break-set clustering above misses (its own docstring).
        mechanism_library = mine_mechanism_abstractions(memory, pack=pack, min_support=2)
        trace.log("mine_mechanism_abstractions", why="extract transferable mechanisms across different breaks",
                  output=f"{len(mechanism_library.concepts)} mechanisms")
    # selection: invention_score first; when orchestrating, break ties by the frontier (diversity) signal so an
    # equally-scored but more novel candidate is preferred — a no-op unless scores tie (deterministic, safe).
    keyf = ((lambda r: (r.score, r.score_components.get("diversity", 0.0))) if orchestrate else (lambda r: r.score))
    best = max(memory.by_problem(problem), key=keyf, default=None)
    trace.log("select_best", why="rank by the multi-objective invention score (hard honesty caps applied)",
              output=(f"{best.candidate_name} (score {best.score}, verified={best.verified})" if best else "none"))
    final_fixation = detect_problem_fixation(memory.by_problem(problem)) if orchestrate else None

    note = ("breadth: many distinct candidates" if mode == "breadth" else "depth: few candidates, deepened") + \
           "; every winner is evaluated, scored with hard honesty caps, and lineage-tracked."
    return EvolveResult(problem=problem, memory=memory, baseline_score=baseline_score, rounds=gen, note=note,
                        trace=trace, concept_library=concept_library, mechanism_library=mechanism_library,
                        lesson_memory=lesson_mem,
                        novelty_archive=novelty_arch, fixation=final_fixation)


# ── a verifiable task (objective evaluator + baseline + ground truth) ────────────────────────────────
def symbolic_invention_task(seed: int = 7):
    """A real, deterministic, verifiable task: discover the law behind data with a KNOWN answer
    (f = 2·x0·x1 − 3, a pure interaction). The objective evaluator settles candidates on held-out data;
    the baseline is the additive box. Used to MEASURE whether evolution actually invents (beats baseline)."""
    import random
    from .pack import get_pack
    from .evaluators import symbolic_evaluator
    from .evaluators.base import CallableEvaluator
    rng = random.Random(seed)
    X = [[rng.uniform(-2, 2), rng.uniform(-2, 2), rng.uniform(-2, 2)] for _ in range(120)]
    y = [2.0 * r[0] * r[1] - 3.0 for r in X]
    cut = int(0.66 * 120)
    pack = get_pack("numeric")
    ev = CallableEvaluator(symbolic_evaluator((X[:cut], y[:cut], X[cut:], y[cut:]), pack=pack),
                           name="symbolic", passed_key="controls_collapse", settles_externally=True)  # settles by held-out DATA
    return {"problem": "discover the law behind the data (interaction)", "pack": pack, "evaluator": ev,
            "baseline_known": "the additive box cannot fit a coupled law"}


def causal_invention_task(seed: int = 11):
    """A verifiable CAUSAL task (integrates causal discovery into the evolve loop, #8): data where Z confounds
    A and B with NO A→B. The objective evaluator settles candidates by an intervention test; only breaking
    'association is direct' (adjust for the confounder) is confirmed — correlation ≠ causation, settled."""
    import random
    from .pack import get_pack
    from .evaluators import causal_evaluator
    from .evaluators.base import CallableEvaluator
    rng = random.Random(seed)
    Z = [rng.gauss(0, 1) for _ in range(400)]
    A = [Z[i] + 0.5 * rng.gauss(0, 1) for i in range(400)]
    B = [Z[i] + 0.5 * rng.gauss(0, 1) for i in range(400)]          # confounded, no direct A→B
    pack = get_pack("causal")
    ev = CallableEvaluator(causal_evaluator({"A": A, "B": B, "Z": Z}, "A", "B", ["Z"], pack=pack),
                           name="causal", passed_key="controls_collapse", threshold=0.7,
                           settles_externally=True)  # settles by an intervention/placebo test on the DATA
    return {"problem": "does A cause B, or is it a spurious correlation via a confounder", "pack": pack, "evaluator": ev}
