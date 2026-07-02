"""evaluators.base — a unified, objective evaluator interface (the VERIFY half of invention).

The symbolic/causal evaluators settle one Candidate on data; this adds the AlphaEvolve-useful structure
around them: a stable `EvaluationResult` (passed · score · decomposable components · error · artifacts ·
runtime), a `BaseEvaluator` contract, and combinators. The discipline the spec demands is enforced here,
not assumed:
  • an internal failure is NEVER masked — `passed=False`, `error` set, score 0 (not a structural fallback);
  • a CORRECTNESS gate is hard — if a correctness evaluator fails, the composite score is capped at 0.25;
  • a candidate cannot be 'verified' without an evaluator that actually passed.

Evaluators are domain-blind: a `candidate` is any object/dict carrying at least a name and a claim/negation;
each evaluator reads what it needs. `CallableEvaluator` adapts an existing settler (symbolic_evaluator,
causal_evaluator, code_evaluator) — which return {"score", **evidence} — straight into this interface.
"""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


@dataclass
class EvaluationResult:
    passed: bool
    score: float
    components: Dict[str, float] = field(default_factory=dict)
    error: str = ""
    artifacts: Dict = field(default_factory=dict)
    runtime_seconds: float = 0.0

    def markdown(self) -> str:
        head = "PASSED" if self.passed else ("ERROR" if self.error else "FAILED")
        L = [f"- evaluator result: **{head}** · score {round(self.score, 3)} · {round(self.runtime_seconds, 3)}s"]
        if self.components:
            L.append("    - " + " · ".join(f"{k}={round(v, 3)}" for k, v in self.components.items()))
        if self.error:
            L.append(f"    - error: {self.error}")
        return "\n".join(L)


def _cand_text(candidate) -> str:
    g = (lambda k: getattr(candidate, k, None) if not isinstance(candidate, dict) else candidate.get(k))
    return " ".join(str(g(k)) for k in ("name", "claim", "negation") if g(k))


class BaseEvaluator:
    """Implement `_run(candidate, workspace) -> EvaluationResult`. `evaluate` wraps it with timing and a
    hard error boundary so an exception becomes a clean failure (never a silent pass)."""
    name: str = "base"
    is_correctness: bool = False        # a correctness gate hard-caps the composite when it fails
    settles_externally: bool = False    # True iff this resolver settles by something REAL (repo/data/world),
                                        # not by self-judgment — only such a resolver can confer certification

    def _run(self, candidate, workspace=None) -> EvaluationResult:
        raise NotImplementedError

    def evaluate(self, candidate, workspace=None) -> EvaluationResult:
        t0 = time.time()
        try:
            res = self._run(candidate, workspace)
        except Exception as exc:        # an evaluator error is a FAILURE, never masked as a score
            return EvaluationResult(passed=False, score=0.0, error=f"{type(exc).__name__}: {exc}",
                                    runtime_seconds=round(time.time() - t0, 4))
        res.runtime_seconds = res.runtime_seconds or round(time.time() - t0, 4)
        return res


class CallableEvaluator(BaseEvaluator):
    """Adapt an existing settler `fn(candidate) -> float | {"score", **evidence}` (e.g. symbolic_evaluator)
    into the interface. `passed` is decided by `threshold` on the score, or by a `passed_key` in evidence
    (e.g. 'controls_collapse'). Components carry the numeric evidence so the score stays decomposable."""
    def __init__(self, fn: Callable, name: str = "callable", threshold: float = 0.5,
                 passed_key: str = "", is_correctness: bool = True, settles_externally: bool = False):
        self.fn, self.name, self.threshold, self.passed_key, self.is_correctness = fn, name, threshold, passed_key, is_correctness
        self.settles_externally = settles_externally   # mark True when `fn` settles by data/repo/world (e.g. symbolic/causal)

    def _run(self, candidate, workspace=None) -> EvaluationResult:
        out = self.fn(candidate)
        if isinstance(out, dict):
            score = float(out.get("score", 0.0))
            comps = {k: float(v) for k, v in out.items() if isinstance(v, (int, float)) and k != "score"}
            passed = bool(out.get(self.passed_key)) if self.passed_key else (score >= self.threshold)
            arts = {k: v for k, v in out.items() if not isinstance(v, (int, float))}
            return EvaluationResult(passed=passed, score=score, components=comps, artifacts=arts)
        score = float(out)
        return EvaluationResult(passed=score >= self.threshold, score=score, components={"score": score})


class PropertyEvaluator(BaseEvaluator):
    """Check invariants / metamorphic / property predicates. `properties` is a list of (name, predicate);
    score is the fraction that hold, `passed` iff ALL hold. A correctness gate by default."""
    def __init__(self, properties: List, name: str = "property", is_correctness: bool = True):
        self.properties, self.name, self.is_correctness = properties, name, is_correctness

    def _run(self, candidate, workspace=None) -> EvaluationResult:
        comps, held = {}, 0
        for nm, pred in self.properties:
            ok = bool(pred(candidate))
            comps[nm] = 1.0 if ok else 0.0
            held += int(ok)
        n = len(self.properties) or 1
        return EvaluationResult(passed=(held == n), score=round(held / n, 3), components=comps)


class NoveltyEvaluator(BaseEvaluator):
    """Settle NOVELTY against real prior art (a PriorArtProvider). Score = prior-art distance, but it
    PROPAGATES novelty_scope/coverage and never decides correctness (is_correctness=False). The honest cap
    that a local/incomplete search cannot yield strong novelty is applied in invention scoring, not faked here."""
    name = "novelty"
    is_correctness = False

    def __init__(self, provider, name: str = "novelty"):
        self.provider, self.name = provider, name

    def _run(self, candidate, workspace=None) -> EvaluationResult:
        from ..novelty import prior_art_audit
        nv = prior_art_audit(_cand_text(candidate), self.provider)
        comps = {"prior_art_distance": nv.prior_art_distance_score, "source_overlap": nv.source_overlap_score}
        arts = {"novelty_scope": nv.novelty_scope or "LOCAL_ONLY", "coverage_level": nv.coverage_level,
                "graded_verdict": nv.graded_verdict, "scoped_verdict": nv.scoped_verdict()}
        # a rebrand/collage 'passes' nothing; a far-from-prior-art idea passes the novelty bar.
        passed = nv.graded_verdict not in ("RENAMED_PRIOR_ART", "COLLAGE_OF_PRIOR_ART")
        return EvaluationResult(passed=passed, score=nv.prior_art_distance_score, components=comps, artifacts=arts)


class PytestEvaluator(BaseEvaluator):
    """Run a pytest selection in a workspace (RED→GREEN style). passed iff returncode 0. A correctness gate.
    Never runs without an explicit workspace + test selector (no accidental whole-suite runs)."""
    name = "pytest"
    is_correctness = True
    settles_externally = True           # a real test run against the repo is the canonical external resolver

    def __init__(self, test_selector: str, name: str = "pytest", timeout: int = 120):
        self.test_selector, self.name, self.timeout = test_selector, name, timeout

    def _run(self, candidate, workspace=None) -> EvaluationResult:
        import subprocess
        import sys
        if not workspace:
            return EvaluationResult(passed=False, score=0.0, error="no workspace given for pytest")
        proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-k", self.test_selector,
                               "-p", "no:cacheprovider"], cwd=workspace, capture_output=True,
                              text=True, timeout=self.timeout)
        passed = proc.returncode == 0
        return EvaluationResult(passed=passed, score=1.0 if passed else 0.0,
                                artifacts={"tail": (proc.stdout + proc.stderr)[-400:]})


class CompositeEvaluator(BaseEvaluator):
    """Combine evaluators with a HARD correctness gate. weighted score of sub-evaluators; if ANY
    is_correctness evaluator did not pass, the composite is `passed=False` and the score is capped at 0.25
    (a plausible-but-unverified candidate cannot score as if verified)."""
    name = "composite"

    def __init__(self, evaluators: List, weights: Optional[Dict[str, float]] = None,
                 correctness_cap: float = 0.25, name: str = "composite"):
        self.evaluators, self.weights, self.correctness_cap, self.name = evaluators, weights or {}, correctness_cap, name

    def _run(self, candidate, workspace=None) -> EvaluationResult:
        results = {e.name: e.evaluate(candidate, workspace) for e in self.evaluators}
        total_w = sum(self.weights.get(n, 1.0) for n in results) or 1.0
        raw = sum(self.weights.get(n, 1.0) * r.score for n, r in results.items()) / total_w
        correctness_ok = all(r.passed for e, r in ((e, results[e.name]) for e in self.evaluators) if e.is_correctness)
        any_error = any(r.error for r in results.values())
        score = round(raw if correctness_ok else min(raw, self.correctness_cap), 4)
        comps = {n: round(r.score, 3) for n, r in results.items()}
        comps["correctness_ok"] = 1.0 if correctness_ok else 0.0
        return EvaluationResult(
            passed=bool(correctness_ok and not any_error), score=score, components=comps,
            error="; ".join(f"{n}: {r.error}" for n, r in results.items() if r.error),
            artifacts={n: r.artifacts for n, r in results.items() if r.artifacts})
