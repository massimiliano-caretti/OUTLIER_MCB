"""prompt_sampler — build prompts that push generation toward the UNKNOWN, not the average.

AlphaEvolve prompts from the best programs; we add what serves invention: the assumptions NOT yet broken,
recent failures (don't repeat them), prior-art warnings (don't rebrand), the lineage, the evaluator's
OBJECTIVE, and an explicit demand to break a NEW assumption or find a NEW mechanism — never a rename or a
collage. Domain-blind and LLM-agnostic: it returns a string for whatever model the caller wires.
"""
from __future__ import annotations
from typing import List, Optional

STRATEGIES = ("explore_unknown_axis", "exploit_best_parent", "recombine_distant_parents",
              "mutate_failed_candidate", "invert_core_assumption", "search_counterexample",
              "simplify_and_generalize", "transfer_mechanism_from_distant_domain")

_STRATEGY_DIRECTIVE = {
    "explore_unknown_axis": "Break an assumption NOT yet broken below — open a NEW axis, not a re-skin of an explored one.",
    "exploit_best_parent": "Take the best candidate below and IMPROVE its mechanism so it beats its own score.",
    "recombine_distant_parents": "Blend two DISTANT candidates into an emergent mechanism neither has alone.",
    "mutate_failed_candidate": "Take a recent FAILURE and change its MECHANISM (not its wording) so it can pass.",
    "invert_core_assumption": "Invert the most central assumption — treat what it fixes as the variable.",
    "search_counterexample": "Propose the world/input where the current best FAILS, then a fix that survives it.",
    "simplify_and_generalize": "Find a simpler mechanism that still passes, then widen its domain of validity.",
    "transfer_mechanism_from_distant_domain": "Import a mechanism from a DISTANT domain as a disciplined analogy.",
}


class PromptSampler:
    """Build an invention prompt from a pack + an EvolutionMemory. `evaluator_objective` names what an
    objective evaluator will measure (so the model optimizes the real target, not plausibility)."""
    def __init__(self, pack, memory=None, evaluator_objective: str = "", memory_router=None):
        self.pack, self.memory, self.evaluator_objective = pack, memory, evaluator_objective
        self.memory_router = memory_router
        self._i = 0

    def _explored(self, problem: str) -> set:
        if self.memory is None:
            return set()
        return {a for r in self.memory.by_problem(problem) for a in r.broken_assumptions}

    def sample(self, problem: str, strategy: Optional[str] = None, prior_art_warnings: Optional[List[str]] = None) -> str:
        router_plan = self.memory_router.plan(problem) if self.memory_router is not None else None
        router_strategy = router_plan.recommended_strategy if router_plan is not None else ""
        strat = strategy or (router_strategy if router_strategy in STRATEGIES else STRATEGIES[self._i % len(STRATEGIES)])
        self._i += 1
        explored = self._explored(problem)
        breakable = [a.name for a in self.pack.assumptions if self.pack.dimension_of.get(a.name)]
        unexplored = [n for n in breakable if n not in explored] or ["(all known axes explored — INVENT a new one)"]
        recs = self.memory.by_problem(problem) if self.memory else []
        best = sorted(recs, key=lambda r: -r.score)[:3]
        failures = [r for r in recs if not r.correctness_passed][-3:]

        L = [f"PROBLEM: {problem}",
             f"DOMAIN BOX (do NOT re-propose): {self.pack.box_name}",
             f"EVALUATOR OBJECTIVE (this is what will be MEASURED): {self.evaluator_objective or 'an objective, runnable evaluator'}",
             f"KNOWN FAMILIES (do NOT rebrand these): {', '.join(self.pack.known_families[:8]) or '—'}",
             f"ASSUMPTIONS ALREADY BROKEN (explored — go elsewhere): {', '.join(sorted(explored)) or 'none yet'}",
             f"ASSUMPTIONS NOT YET BROKEN (prefer these): {', '.join(unexplored)}",
             f"BEST CANDIDATES SO FAR (beat these): {', '.join(f'{r.candidate_name}={r.score}' for r in best) or 'none yet'}",
             f"RECENT FAILURES (do NOT repeat): {', '.join(r.candidate_name for r in failures) or 'none yet'}"]
        if prior_art_warnings:
            L.append(f"PRIOR-ART WARNINGS (these resemble existing work — escape them): {', '.join(prior_art_warnings)}")
        if router_plan is not None and router_plan.prompt_block:
            L.append(router_plan.prompt_block)
        L += [f"\nSTRATEGY: {strat} — {_STRATEGY_DIRECTIVE[strat]}",
              "\nHARD RULES:",
              "  1. Do NOT rename/rebrand. Change the MECHANISM (a functional difference, not wording).",
              "  2. Do NOT recycle a known family or recombine them into a collage.",
              "  3. Produce a TEST / experiment / proof that an objective evaluator can run.",
              "  4. State explicitly what would FALSIFY the candidate (the negative control).",
              "  5. Say WHY the baseline / best parent FAILS where your candidate would win.",
              "Return one candidate: name · broken_assumption · mechanism · world_test · falsifier · why_parent_fails."]
        return "\n".join(L)
