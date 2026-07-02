"""problem_active — find better QUESTIONS, not just better answers (improvement #4).

Creativity is often choosing the right problem. This builds on find_problems / ProblemGenerator and adds the
two missing pieces: ranking a question by novelty × testability (a beautiful-but-untestable question is
worthless), and detecting PROBLEM FIXATION — when the engine keeps attacking the same assumption/axis and
should deliberately jump elsewhere. Thin over the existing engines; the fixation detector is the new signal.
"""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional


def find_high_leverage_questions(context, k: int = 5):
    """Propose the worth-attacking questions for a context {pack, prompt, memory, curiosity}. Wraps
    find_problems so a caller can pass one context object. Returns a ProblemPortfolio (ranked by worth).
    ERGONOMICS (#15): a plain string is accepted as the prompt (the common case), and a missing pack is
    routed from the prompt — so `find_high_leverage_questions("invent a better cache")` just works."""
    if isinstance(context, str):
        context = {"prompt": context}
    if not context.get("pack") and context.get("prompt"):
        from .pack import select_pack
        context = {**context, "pack": select_pack(context["prompt"])[0]}
    from .problem_finding import find_problems
    return find_problems(pack=context.get("pack"), prompt=context.get("prompt", ""), k=k,
                         memory=context.get("memory"), curiosity=float(context.get("curiosity", 0.0)),
                         blend_with=context.get("blend_with"))


def _testability(problem) -> float:
    """How settle-able a question is: it must name what would CONFIRM/REFUTE attacking it, and sit on a real
    axis. A question with no `settles` and no axis is rhetoric, not a testable problem."""
    has_settle = 1.0 if str(getattr(problem, "settles", "")).strip() else 0.0
    has_axis = 1.0 if str(getattr(problem, "axis", "")).strip() else 0.0
    return round(0.6 * has_settle + 0.4 * has_axis, 3)


def rank_problem_by_novelty_and_testability(problem, w_novelty: float = 0.5) -> Dict:
    """Score a single problem by novelty × testability — the two that matter for a worth-attacking question.
    Returns {score, novelty, testability}. A novel-but-untestable question is penalized, by design."""
    comps = getattr(problem, "components", {}) or {}
    novelty = float(comps.get("novelty_potential", comps.get("frontier", 0.0)) or 0.0)
    test = _testability(problem)
    score = round(w_novelty * novelty + (1.0 - w_novelty) * test, 4)
    return {"score": score, "novelty": round(novelty, 3), "testability": test}


def rank_questions(problems, w_novelty: float = 0.5) -> List:
    """Re-rank a list of problems by novelty × testability (highest first)."""
    return sorted(problems, key=lambda p: -rank_problem_by_novelty_and_testability(p, w_novelty)["score"])


def generate_problem_family(seed_problem: str, pack, n: int = 3):
    """A family of related-but-distinct problems around a seed (ProblemGenerator variants). Widens the search
    over QUESTIONS, not answers."""
    from .problem_generator import ProblemGenerator
    return ProblemGenerator(pack).generate_problem_variants(seed_problem, n=n)


def _seed_of(item) -> str:
    if isinstance(item, str):
        return item
    seed = getattr(item, "seed", "") or ""
    if seed:
        return seed
    broken = getattr(item, "broken_assumptions", None) or getattr(item, "assumptions", None) or []
    return broken[0] if broken else (getattr(item, "axis", "") or "")


def detect_problem_fixation(items, threshold: float = 0.5, min_items: int = 3) -> Dict:
    """The NEW signal: are we stuck attacking the same assumption/axis? Given problems (or records, or seed
    strings), flag fixation when one seed dominates a fraction ≥ threshold of a population of ≥ min_items, and
    suggest jumping to an under-attacked direction. Fixation is the enemy of divergent search."""
    seeds = [_seed_of(it) for it in items]
    seeds = [s for s in seeds if s]
    n = len(seeds)
    if n < min_items:
        return {"fixated": False, "reason": f"too few items ({n} < {min_items}) to judge fixation",
                "dominant_seed": "", "share": 0.0, "distinct": len(set(seeds))}
    counts = Counter(seeds)
    seed, freq = counts.most_common(1)[0]
    share = round(freq / n, 3)
    fixated = share >= threshold and len(counts) > 1 or (len(counts) == 1 and n >= min_items)
    return {"fixated": bool(fixated), "dominant_seed": seed, "share": share, "distinct": len(counts),
            "suggestion": (f"break OUT of «{seed}» — {int(share * 100)}% of attempts target it; "
                           "force a different axis (provocation / random-entry / cross-domain transfer)")
                          if fixated else "search is diverse enough across seeds"}


def problem_active_ablation(pack=None) -> Dict:
    """Ablation for #4: (a) ranking by novelty × testability puts a testable question above an equally-novel
    UNtestable one (a constant ranker cannot); (b) fixation detection fires on a one-seed population and not
    on a diverse one."""
    from .problem_finding import Problem
    testable = Problem(question="q1", domain="d", seed="a", axis="REPRESENTATION", worth=0.9,
                       components={"novelty_potential": 0.8}, settles="a control that must collapse")
    untestable = Problem(question="q2", domain="d", seed="b", axis="", worth=0.9,
                         components={"novelty_potential": 0.8}, settles="")
    ranked = rank_questions([untestable, testable])
    ranking_discriminates = ranked[0] is testable and (
        rank_problem_by_novelty_and_testability(testable)["score"] > rank_problem_by_novelty_and_testability(untestable)["score"])
    fixated = detect_problem_fixation(["a", "a", "a", "b"])["fixated"]
    diverse = detect_problem_fixation(["a", "b", "c", "d"])["fixated"]
    return {"ranking_discriminates": ranking_discriminates, "fixation_fires_on_stuck": fixated,
            "fixation_quiet_on_diverse": not diverse,
            "earns_keep": ranking_discriminates and fixated and not diverse}
