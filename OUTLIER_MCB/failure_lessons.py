"""failure_lessons — turn failures into REUSABLE operational lessons (memory that learns, not just records).

The evolution memory remembers WHAT failed; this remembers WHY, as a lesson the next round must obey: not
'candidate X failed' but 'it changed only the metric's NAME, not the causal mechanism'. It classifies a
failed record into a failure MODE (a small taxonomy), stores the lesson, retrieves the relevant ones for a
problem, and injects them into the next prompt so the engine does not repeat the same dead end.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# the failure taxonomy + the operational lesson each one teaches.
FAILURE_MODES = {
    "leakage": "passed the task AND a negative control — the gain was leakage; next time, design a control that MUST collapse.",
    "overfit_visible": "passed public cases but FAILED hidden ones; next time, settle on cases the candidate never saw.",
    "renamed_not_remechanism": "changed the NAME/metric, not the causal mechanism; next time, change what the system DOES.",
    "collage": "recombined known families without beating any part; next time, break a NEW assumption, not remix.",
    "no_world_test": "no runnable falsifier — it stayed a hypothesis; next time, ship a red-first world-test.",
    "regressed_baseline": "did not beat baseline or parent; next time, target a case where the baseline provably fails.",
    "local_only_novelty": "novel only locally; next time, check prior art ONLINE before claiming novelty.",
}


@dataclass
class FailureLesson:
    mode: str
    lesson: str
    source_id: str = ""
    problem: str = ""

    def markdown(self) -> str:
        return f"- **{self.mode}**: {self.lesson}"


def summarize_failure_mode(record) -> Optional[FailureLesson]:
    """Classify a record into a failure MODE + its lesson. Returns None for a clean, improving success."""
    comps = getattr(record, "score_components", {}) or {}
    rid = getattr(record, "id", "")
    prob = getattr(record, "problem", "")

    def L(mode):
        return FailureLesson(mode=mode, lesson=FAILURE_MODES[mode], source_id=rid, problem=prob)

    if comps.get("leakage_detected", 0) >= 1.0:
        return L("leakage")
    if comps.get("hidden") is not None and comps.get("public") is not None and comps["hidden"] < comps["public"]:
        return L("overfit_visible")
    if not getattr(record, "correctness_passed", False):
        return L("no_world_test")
    if (getattr(record, "improvement_over_baseline", 0) or 0) <= 0 and (getattr(record, "improvement_over_parent", 0) or 0) <= 0:
        return L("regressed_baseline")
    if getattr(record, "novelty_scope", "") in ("", "LOCAL_ONLY"):
        return L("local_only_novelty")
    return None


@dataclass
class LessonMemory:
    lessons: List[FailureLesson] = field(default_factory=list)

    def record(self, record) -> Optional[FailureLesson]:
        lesson = summarize_failure_mode(record)
        if lesson is not None:
            self.lessons.append(lesson)
        return lesson

    def record_all(self, records) -> None:
        for r in records:
            self.record(r)

    def retrieve(self, problem: Optional[str] = None, k: int = 5) -> List[FailureLesson]:
        """The most relevant lessons (this problem first), de-duplicated by mode (each lesson once)."""
        pool = [l for l in self.lessons if (problem is None or l.problem == problem)] or self.lessons
        seen, out = set(), []
        for l in pool:
            if l.mode not in seen:
                seen.add(l.mode); out.append(l)
        return out[:k]

    def inject_lessons_into_prompt(self, base_prompt: str, problem: Optional[str] = None) -> str:
        """Append the past failure modes to a prompt so the next attempt does not repeat them."""
        lessons = self.retrieve(problem)
        if not lessons:
            return base_prompt
        block = "\nPAST FAILURE MODES TO AVOID (do not repeat these):\n" + "\n".join(f"  - {l.mode}: {l.lesson}" for l in lessons)
        return base_prompt + block

    def avoid_repeated_failure(self, candidate, problem: Optional[str] = None) -> List[str]:
        """The failure modes this candidate risks repeating. All recorded modes for the problem are warnings;
        a candidate that breaks NOTHING (no assumptions, no falsifier) additionally risks the structural modes
        'no_world_test' and 'regressed_baseline' even if they were not seen before."""
        risky = {l.mode for l in self.retrieve(problem)}
        breaks_nothing = not (getattr(candidate, "assumptions", None) or getattr(candidate, "breaks", None))
        no_falsifier = not str(getattr(candidate, "discipline", "")).strip()
        if breaks_nothing or no_falsifier:
            risky |= {"no_world_test", "regressed_baseline"}
        return sorted(risky)

    def markdown(self) -> str:
        return "\n".join(["## Failure lessons (operational, reusable)"] + [l.markdown() for l in self.retrieve()])


# ── #6: turn a failure lesson into the NEXT concrete mutation (a failure becomes a strategy, not a penalty) ──
# each failure MODE maps to the evolution operator that DIRECTLY addresses it.
_MODE_TO_OPERATOR = {
    "no_world_test": "add_falsifier",          # it had no runnable falsifier → attach one
    "leakage": "add_falsifier",                # it passed a control → force a negative control that must fail
    "overfit_visible": "generalize_candidate", # it fit the visible cases → broaden the regime it must hold on
    "regressed_baseline": "novelty_push",      # it did not beat the box → push FARTHEST from the box
    "local_only_novelty": "cross_domain_transfer",  # novel only locally → import a distant mechanism + recheck
    "renamed_not_remechanism": "mutate_mechanism",  # it renamed, didn't re-mechanism → change what it DOES
    "collage": "mutate_mechanism",             # recombination without a new break → break a new assumption
}


def compress_failure_to_lesson(record):
    """Compress a failed record into its operational lesson PLUS the mutation it suggests (the generative half:
    a failure is not a dead end, it is the next move). Returns a dict {lesson, mode, suggested_operator} —
    or None for a clean success. `suggested_operator` is the evolution op that repairs this failure mode."""
    lesson = summarize_failure_mode(record)
    if lesson is None:
        return None
    return {"lesson": lesson, "mode": lesson.mode, "suggested_operator": _MODE_TO_OPERATOR.get(lesson.mode)}


def retrieve_lessons(memory, problem=None, k: int = 5):
    """The relevant lessons for a problem. `memory` is a LessonMemory, or any iterable of records to mine."""
    if isinstance(memory, LessonMemory):
        return memory.retrieve(problem, k=k)
    lm = LessonMemory()
    lm.record_all(memory if hasattr(memory, "__iter__") else [])
    return lm.retrieve(problem, k=k)


def mutate_from_failure_lesson(candidate, lesson, pack, parent_id: str = ""):
    """The generative payoff (#6): map a failure lesson to the evolution operator that DIRECTLY repairs that
    failure mode, and return the resulting MutationResult. A no_world_test lesson → a candidate WITH a
    falsifier; a regressed_baseline lesson → a candidate pushed farthest from the box; etc. Returns None when
    the mode has no operator (a clean success teaches no mutation)."""
    from . import evolution_ops as ops
    mode = getattr(lesson, "mode", lesson if isinstance(lesson, str) else "")
    op_name = _MODE_TO_OPERATOR.get(mode)
    if not op_name:
        return None
    op = getattr(ops, op_name, None)
    return op(pack, candidate, parent_id) if op else None


def failure_lesson_ablation(pack=None):
    """Ablation for #6: mutating FROM a 'no_world_test' lesson yields a candidate that now carries a falsifier
    the original lacked — a real repair — whereas an unrelated/clean lesson yields no mutation (no-op control)."""
    from .pack import get_pack
    from .generators.base import Candidate
    pack = pack or get_pack("coding")
    bare = Candidate(name="bare_idea", operator="proposed", breaks=["X"], assumptions=["a"],
                     negation="an idea with no falsifier", discipline="")
    repaired = mutate_from_failure_lesson(bare, FailureLesson("no_world_test", FAILURE_MODES["no_world_test"]), pack)
    none_for_clean = mutate_from_failure_lesson(bare, FailureLesson("clean", "no failure"), pack)
    gained_falsifier = repaired is not None and "FALSIFIER" in (repaired.candidate.discipline or "").upper() \
        and not (bare.discipline or "")
    return {"lesson_to_mutation": repaired is not None, "gained_a_falsifier": gained_falsifier,
            "clean_lesson_is_noop": none_for_clean is None,
            "earns_keep": gained_falsifier and none_for_clean is None}
