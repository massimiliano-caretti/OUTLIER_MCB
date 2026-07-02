"""orchestrate — ONE scientific loop that composes every capability, so none sits as dead code (Tier-1 + Tier-2
wiring). `autonomous()` runs the tracks whose inputs are present; each track uses a real capability with correct
types, and NOTHING is faked when an input is missing (the honest 'no theater' rule the library is built on).

The tracks (each optional, activated only by its inputs):
  • IDEA        — incubate() persisted dead-ends/wins into fresh anomalies → invent() with EARNED TASTE and
                  transformational axis-growth → a ranked idea frontier.  [incubation · taste · transformation]
  • REFINE      — self_refine() the top idea, accepting a successor ONLY if an EXTERNAL idea-evaluator improves.
  • SETTLE      — from a verification_context (check + cases) synthesize a full anti-cheat evaluator, validate it,
                  RED-TEAM candidate solutions, and settle them through a VERIFICATION ECONOMY (a cheap
                  calibrated proxy confirms; everything else escalates to the real synthesized evaluator).
  • DISAMBIGUATE— run_active_experiments() to ACQUIRE information and eliminate rival hypotheses by the world.
  • RECORD      — write settled outcomes back into memory so the NEXT run's incubation composes on them.

`AutonomousResult.used_capabilities` names every capability that actually ran — the test asserts each is wired.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


@dataclass
class AutonomousResult:
    prompt: str
    invention: object = None                 # the Invention (idea frontier)
    incubated: List = field(default_factory=list)
    refinement: Optional[Dict] = None
    evaluator_issues: Optional[List[str]] = None
    settlements: List = field(default_factory=list)
    red_team: List = field(default_factory=list)
    representations: List = field(default_factory=list)
    experiments: object = None
    physics: object = None            # best invented toy universe (Point 1)
    language: object = None           # invented formal language + expressive power (Point 3)
    meaning: List = field(default_factory=list)   # endogenous symbols grounded (Point 2)
    aesthetics: object = None         # elegance vector of an artifact (Point 4)
    revived: List = field(default_factory=list)
    used_capabilities: List[str] = field(default_factory=list)
    note: str = ""

    def markdown(self) -> str:
        L = [f"## Autonomous creative loop — «{self.prompt}»",
             f"- capabilities exercised: {', '.join(self.used_capabilities) or 'none'}"]
        if self.invention is not None:
            L.append(f"- idea frontier: {len(self.invention.frontier)} candidates "
                     f"(best breaks: {', '.join(self.invention.frontier[0]['candidate'].breaks) if self.invention.frontier else '—'})")
        if self.incubated:
            L.append(f"- incubation surfaced {len(self.incubated)} cross-domain connection(s) as fresh anomalies")
        if self.refinement is not None:
            L.append(f"- self-refine: {'accepted' if self.refinement['improved'] else 'rejected'} "
                     f"(before {self.refinement['before']} → after {self.refinement['after']})")
        if self.evaluator_issues is not None:
            L.append(f"- synthesized evaluator gaps: {self.evaluator_issues or 'none (public+hidden+controls)'}")
        if self.settlements:
            cheap = sum(1 for s in self.settlements if not s.escalated)
            L.append(f"- settled {len(self.settlements)} solution(s); {cheap} cheaply via a trusted proxy")
        if self.representations:
            acc = [v for v in self.representations if v.accepted]
            L.append(f"- representation invention: {len(acc)}/{len(self.representations)} candidate(s) REDUCE "
                     f"the problem (control-gated)" + (f" — best: {acc[0].representation}" if acc else ""))
        if self.experiments is not None:
            L.append(f"- active experiments: {self.experiments.reason}")
        L.append(f"- {self.note}")
        return "\n".join(L)


def _public_only_proxy(check: Callable, cases: List) -> Callable:
    """A CHEAP proxy: the raw check on the FIRST public case only (no hidden cases, no negative controls) —
    the fast smell-test the verification economy will calibrate against the full synthesized evaluator."""
    first = cases[0]
    return lambda solution: bool(check(solution, first))


def autonomous(prompt: str, *, pack=None, memory=None, taste=None, repo_path: Optional[str] = None,
               idea_evaluator: Optional[Callable] = None, verification_context: Optional[Dict] = None,
               solutions: Optional[List] = None, hypotheses: Optional[List] = None,
               world_probes: Optional[Dict] = None, representation_context: Optional[Dict] = None,
               invent_physics: bool = False, language_family: Optional[List] = None,
               ground_log: Optional[List] = None, aesthetic_artifact: Optional[str] = None,
               beam: int = 5, rounds: int = 2,
               min_precision: float = 0.9, min_support: int = 3) -> AutonomousResult:
    """Run the composed loop. Every argument beyond `prompt` gates a track — pass what you have; the engine uses
    each capability only where its inputs are real. Returns an AutonomousResult recording what actually ran."""
    from .invent import invent
    res = AutonomousResult(prompt=prompt)
    used = res.used_capabilities

    # ── IDEA track: incubation → invent(taste, transformation) ──────────────────────────────────────────
    anomalies = None
    if memory is not None:
        from .incubation import incubate, revive_barren
        res.incubated = incubate(memory)
        res.revived = revive_barren(memory)
        anomalies = [c.conjecture for c in res.incubated] or None
        if res.incubated:
            used.append("incubation")
    inv = invent(prompt, pack=pack, beam=beam, rounds=rounds, repo_path=repo_path,
                 taste=taste, expand_when_stuck=True, anomalies=anomalies)
    res.invention = inv
    used.append("invent")
    if any(f["candidate"].operator == "orthogonal_germ" for f in inv.frontier):
        used.append("orthogonal_germs")
    if taste is not None and taste is not False:
        used.append("earned_taste")
    if "Transformational" in inv.note:                      # expand_when_stuck grew a new axis
        used.append("transformation")

    # ── REFINE track: self_refine the top idea, gated by an EXTERNAL idea-evaluator ────────────────────
    if idea_evaluator is not None and inv.frontier:
        from .thought_search import self_refine
        res.refinement = self_refine(inv.frontier[0]["candidate"], "push farther from the box",
                                     idea_evaluator, inv.pack)
        used.append("self_refine")

    # ── SETTLE track: synthesize evaluator → validate → red-team → verification economy (over SOLUTIONS) ─
    if verification_context and solutions:
        from .evaluator_synthesis import synthesize_evaluator, validate_evaluator
        from .red_team import red_team_from_check
        from .verification_economy import VerificationEconomy
        ctx = dict(verification_context)
        synth = synthesize_evaluator(prompt, ctx)
        res.evaluator_issues = validate_evaluator(synth)
        used += ["synthesize_evaluator", "validate_evaluator"]
        # red team the solutions (boundary mutators + negative controls it must FAIL + optional rebrand probe)
        rt = red_team_from_check(ctx["check"], list(ctx.get("public_cases") or ctx.get("cases") or []),
                                 mutators=ctx.get("mutators", ()), negative_controls=ctx.get("negative_controls", ()),
                                 provider=ctx.get("provider"), claim_text=prompt)
        if rt.attacks:
            res.red_team = [rt.evaluate(s) for s in solutions]
            used.append("red_team_from_check")
        # verification economy: a cheap proxy confirms cheaply where calibrated; else escalate to `synth`.
        econ = VerificationEconomy(real=synth, real_cost=1.0)
        pub = list(ctx.get("public_cases") or ctx.get("cases") or [])   # guard: matches line 123, no list(None)
        if pub:                                                          # and no cases[0] IndexError on empty
            econ.add_proxy(_public_only_proxy(ctx["check"], pub), cost=0.1, name="public_only")
        econ.calibrate(solutions)
        res.settlements = [econ.settle(s, min_precision=min_precision, min_support=min_support) for s in solutions]
        used.append("verification_economy")

    # ── REPRESENT track: invent a re-encoding that makes the problem easier for a fixed solver (control-gated) ─
    if representation_context:
        from .representation import invent_representation
        rc = representation_context
        res.representations = invent_representation(rc["candidates"], rc["solver"], rc["instances"], rc["labels"],
                                                    margin=rc.get("margin", 0.15))
        used.append("invent_representation")

    # ── FRONTIER tracks (Points 1-4): reach the creativity inventors from the ONE composed entry ─────────
    if invent_physics:
        from evals.benchmarks.physics_emergence import best_invented_emergence
        res.physics = best_invented_emergence(trials=12)          # invent toy universes; keep the most emergent
        used.append("invent_physics")
    if language_family:
        from .language_inventor import integer_baseline, invent_new_language, expressive_power
        base = integer_baseline()
        lang = invent_new_language(base, language_family)
        res.language = {"macros": dict(lang.macros), "expressive_power": expressive_power(lang, base, language_family)}
        used.append("invent_language")
    if ground_log:
        from .semantic_grounding import SymbolRegistry, find_recurring_patterns, ground_new_symbol
        reg = SymbolRegistry()
        res.meaning = [s for s in (ground_new_symbol(p, ground_log, reg)
                                   for p, _ in find_recurring_patterns(ground_log)[:3]) if s]
        if res.meaning:
            used.append("ground_symbols")
    if aesthetic_artifact:
        from .aesthetics import elegance_score
        res.aesthetics = elegance_score(aesthetic_artifact)
        used.append("aesthetics")

    # ── DISAMBIGUATE track: acquire information to eliminate rival hypotheses ───────────────────────────
    if hypotheses and world_probes:
        from .experiment_loop import run_active_experiments
        res.experiments = run_active_experiments(hypotheses, world_probes)
        used.append("active_experiments")

    # ── RECORD: settled outcomes feed the NEXT run's incubation (cross-session composition) ────────────
    if memory is not None and res.settlements:
        domain = getattr(inv.pack, "name", "generic")
        for s in res.settlements:
            memory.record(assumption=prompt[:60], axis="settlement", domain=domain, confirmed=bool(s.verdict))
        used.append("memory_record")

    res.note = ("Each track ran only where its inputs were real — nothing fabricated. Ideas are provisional; "
                "only the SETTLE and DISAMBIGUATE tracks carry external verdicts.")
    return res
