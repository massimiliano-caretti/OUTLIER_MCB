"""self_evolve — the engine improves its OWN modules, controlled by tests, evaluators and memory.

Recursive self-improvement is only safe if it cannot self-confirm: here every proposal is a hypothesis until
a real test passes, novelty is qualified by online prior-art scope, a negative delta is recorded as a
regression, and DRY-RUN changes NOTHING on disk. It reuses the engine on itself (judge + the meta pack's
generators) to PROPOSE improvements, the patch validator to refuse unsafe patches, and EvolutionMemory to
keep lineage. Applying a patch requires `dry_run=False` AND a passing test in a rollback-safe transaction —
the library never accepts a change just because a model (or the engine) liked it.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .evolution_memory import EvolutionMemory, EvolutionRecord
from .evolve import invention_score


def _module_purpose(target_module: str) -> str:
    try:
        with open(target_module) as fh:
            text = fh.read()
        if '"""' in text:
            doc = text.split('"""', 2)[1].strip().splitlines()
            return doc[0].strip() if doc else target_module
    except Exception:
        pass
    return target_module


def validate_improvement_patch(patch: str, repo_root: str = ".") -> tuple:
    """Refuse an unsafe patch (path traversal / symlink / outside repo) BEFORE any apply. Returns (ok, errors).
    Reuses the hardened patches.py validator — self-improvement never escapes the repo."""
    from .patches import parse_unified_diff, validate_patch_paths
    try:
        plan = parse_unified_diff(patch)
    except Exception as exc:
        return False, [f"unparseable patch: {exc}"]
    return validate_patch_paths(plan, repo_root)


@dataclass
class SelfEvolveResult:
    target_module: str
    dry_run: bool
    memory: EvolutionMemory
    proposals: List[Dict] = field(default_factory=list)
    applied: List[str] = field(default_factory=list)        # ids actually applied (always [] in dry_run)
    note: str = ""

    def best(self) -> Optional[EvolutionRecord]:
        recs = self.memory.all()
        return max(recs, key=lambda r: r.score) if recs else None

    def to_dict(self) -> Dict:
        b = self.best()
        return {"target_module": self.target_module, "dry_run": self.dry_run,
                "proposals": len(self.proposals), "applied": self.applied,
                "best": None if b is None else {"name": b.candidate_name, "score": b.score,
                                                "verified": b.verified, "delta": b.improvement_over_parent,
                                                "lineage": [r.id for r in self.memory.lineage(b.id)]},
                "statement": ("DRY-RUN: proposals are UNVERIFIED hypotheses — nothing applied, no file changed."
                              if self.dry_run else
                              "proposals are UNVERIFIED hypotheses; this function RECORDS proposals only and applies "
                              "NOTHING (no evaluator / transactional-apply path is wired here) — `applied` stays empty. "
                              "To actually apply, route a real patch through validate_improvement_patch + a passing test.")}

    def markdown(self) -> str:
        d = self.to_dict()
        L = [f"# Self-evolve — {self.target_module}  (dry_run={self.dry_run})",
             f"- proposals: {d['proposals']} · applied: {d['applied'] or 'none'}"]
        for p in self.proposals[:6]:
            L.append(f"  - [{p['operator']}] {p['name']} · score {p['score']} · verified={p['verified']}")
        L.append(f"\n**Statement:** {d['statement']}")
        return "\n".join(L)


def self_evolve(target_module: str, budget: int = 5, dry_run: bool = True,
                memory: Optional[EvolutionMemory] = None, prior_art_provider=None) -> SelfEvolveResult:
    """Propose improvements to `target_module` using the engine on itself and record them with lineage. This
    function PROPOSES ONLY — it applies NOTHING (there is no evaluator/transactional-apply path here), so
    `applied` is always empty regardless of `dry_run`. A proposal is an UNVERIFIED hypothesis (no evaluator on a
    real patch ⇒ not verified). To actually apply a change, use `evolutionary_self_repair` with a real measure."""
    from .pack import get_pack
    from .generators import generate_candidates
    from .judge import judge
    memory = memory if memory is not None else EvolutionMemory()
    purpose = _module_purpose(target_module)
    problem = f"improve {target_module}: {purpose}"

    # the engine judges its own improvement on the SELF (meta) domain, then proposes assumption-breaks
    meta = get_pack("meta")
    verdict = judge(f"a better design for: {purpose}", pack=meta)
    cands = generate_candidates(meta, problem)[:max(1, budget)]

    proposals: List[Dict] = []
    for i, c in enumerate(cands):
        scope = "LOCAL_ONLY"
        if prior_art_provider is not None:
            from .novelty import prior_art_audit
            scope = prior_art_audit(c.negation, prior_art_provider).novelty_scope or "LOCAL_ONLY"
        # DRY-RUN: no patch, no test ⇒ correctness False ⇒ score capped at 0.25 ⇒ an honest hypothesis, not a win.
        scored = invention_score({"correctness": False, "novelty_scope": scope,
                                  "assumption_break_depth": min(1.0, len(c.breaks) / 2.0)})
        rec = EvolutionRecord(
            id=f"se-{i:03d}", problem=problem, candidate_name=c.name, claim=c.negation,
            broken_assumptions=list(c.assumptions), generation=0, evaluator_name="",  # no evaluator ⇒ not verified
            score=scored["score"], score_components=scored["components"], correctness_passed=False,
            novelty_scope=scope, mutation_operator=c.operator, created_at=str(i),
            metadata={"verdict": verdict.verdict, "dry_run": dry_run})
        memory.add(rec)
        proposals.append({"id": rec.id, "name": c.name, "operator": c.operator, "score": rec.score,
                          "verified": rec.verified, "rationale": c.negation[:100]})

    note = ("DRY-RUN: " if dry_run else "") + \
           f"{len(proposals)} improvement hypotheses recorded; verdict on the module: {verdict.verdict}. " + \
           "No file changed; nothing applied (this function proposes only — there is no apply path here)."
    return SelfEvolveResult(target_module=target_module, dry_run=dry_run, memory=memory,
                            proposals=proposals, applied=[], note=note)
