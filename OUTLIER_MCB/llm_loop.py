"""llm_loop — the LLM-in-the-loop engine: propose → prior-art gate → MATERIALIZE a failing test → run it
RED → write a patch → run it GREEN → score by EXECUTION → archive → reflect/repair failures → next prompt.

This is the change that turns OUTLIER_MCB from a heuristic idea framework into a real engine. The heuristic
runtime (`invent`) often ends NOT_MATERIALIZED because nobody writes the test/patch. Here an LLM writes them
as unified diffs, `patches.py` applies them TRANSACTIONALLY to the repo, and the bet is settled by ACTUALLY
RUNNING the test. A candidate cannot win unless its NEW test failed for the RIGHT reason — a real assertion
(`RED_ASSERTION`), not a broken import (`RED_COLLECTION`) — before its patch, and went GREEN after a patch
that changes real source (not one that skips/weakens the test). The winner is chosen by the external
`llm_evidence_score`, decomposed into readable, configurable components — never by the LLM's own ordering.

Borrowed and inverted: FunSearch (external evaluator picks winners), MAP-Elites (a QDArchive of diverse
elites + a diversity gate), Reflexion / Self-Refine (failures become the next prompt AND a bounded, targeted
repair of the single broken field), Novelty Search / prior-art gate (a graded verdict over claim+name+
rationale+world-test+patch-intent, never "absolute novelty"). Fully opt-in: no `llm`, no behaviour change.
"""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .generators import Candidate, breakable
from .qd import QDArchive
from .llm import parse_candidates
from .patches import (parse_unified_diff, validate_patch_paths, PatchTransaction,
                      patch_substance_evidence)
from .runner import CommandRunner

_SYSTEM = ("You are an inventive but rigorous engineer. Break a hidden assumption the standard solutions share, "
           "and PROVE it with a failing test then a minimal patch. Reply ONLY with a JSON array of candidates.")
_SYSTEM_REPAIR = ("You are fixing ONE broken field of a previous proposal. Reply with ONLY the corrected value "
                  "(a JSON array, or a single unified diff) — no prose, no explanation, no other fields.")

_SCHEMA_HINT = (
    'Each candidate is a JSON object: {"name","broken_assumption","operator","claim",'
    '"why_standard_families_fail","world_test_description","test_patch","implementation_patch",'
    '"novelty_rationale","risk"}. test_patch/implementation_patch are UNIFIED DIFFS (--- /+++ /@@).')


# ── decomposed, configurable executable scoring (§8: readable components, hard to game) ──
DEFAULT_SCORE_WEIGHTS: Dict[str, float] = {
    "red_green": 0.42,          # RED_ASSERTION→GREEN is the whole point; RED_COLLECTION→GREEN is heavily discounted
    "test_quality": 0.16,       # a non-tautological test that imports the target and checks a concrete value
    "prior_art": 0.14,          # far from known families / archive / pack terms (graded, never "absolute")
    "diversity": 0.10,          # opens a NEW behavioral cell rather than repeating one
    "patch_substance": 0.18,    # changes real source, not the test; no skip/xfail/assert-weakening
    "risk_penalty": 0.15,       # subtracted: self-declared risk
}


def _outcome_red_green(ev: Dict) -> float:
    """The RED→GREEN component — the scientific core. Only a real-assertion RED that goes GREEN scores 1.0."""
    rk = ev.get("red_kind")
    if not ev.get("green_final"):
        if rk == "RED_ASSERTION":
            return 0.15                                   # failed for the right reason, but never fixed
        if ev.get("materialized"):
            return 0.05                                   # written + ran, no GREEN
        return 0.0                                        # not materialized at all
    if rk == "RED_ASSERTION":
        return 1.0                                        # the only fully-rewarded chain
    if rk == "RED_COLLECTION":
        return 0.35                                       # "fixed" an import/syntax error — cheap, discounted
    if rk == "ERROR_TIMEOUT":
        return 0.2
    if ev.get("red_first"):
        return 0.85                                       # legacy: known RED-first, kind unrecorded
    return 0.6


def score_components(ev: Dict) -> Dict[str, float]:
    """Expose the score's parts so a run can SHOW why a candidate won/lost (and so it is hard to game)."""
    test_q = ev.get("test_quality")
    prior = ev.get("prior_art_component")
    div = ev.get("diversity")
    subst = ev.get("patch_substance")
    return {
        "red_green": round(_outcome_red_green(ev), 3),
        "test_quality": round(float(test_q) if test_q is not None
                              else (0.9 if ev.get("test_specific") else 0.3), 3),
        "prior_art": round(float(prior) if prior is not None
                           else (0.0 if ev.get("rebrand") else 0.9 if ev.get("prior_art_weak") else 0.3), 3),
        "diversity": round(float(div) if div is not None else (0.9 if ev.get("cell_new") else 0.5), 3),
        "patch_substance": round(float(subst) if subst is not None
                                 else (0.1 if ev.get("only_cosmetic") else 0.8 if ev.get("has_patch") else 0.0), 3),
        "risk_penalty": round(float(ev.get("risk", 0.0) or 0.0), 3),
    }


def llm_evidence_score(ev: Dict, weights: Optional[Dict[str, float]] = None) -> float:
    """A composite of EXECUTABLE evidence in [0,1] — the winner is decided by this, not by the LLM. The score
    is a weighted sum of readable components (see `score_components`); a rebrand is a hard zero. Weights are
    configurable (defaults in `DEFAULT_SCORE_WEIGHTS`)."""
    if ev.get("rebrand"):
        return 0.0
    w = dict(DEFAULT_SCORE_WEIGHTS)
    if weights:
        w.update(weights)
    c = score_components(ev)
    s = (w["red_green"] * c["red_green"] + w["test_quality"] * c["test_quality"]
         + w["prior_art"] * c["prior_art"] + w["diversity"] * c["diversity"]
         + w["patch_substance"] * c["patch_substance"] - w["risk_penalty"] * c["risk_penalty"])
    return round(max(0.0, min(1.0, s)), 3)


# ── test-quality scoring (§4: a test must be specific, not tautological) ──
_TAUTOLOGY_BODIES = {"true", "1", "1==1", "true==true", "not false", "bool(true)", "1.0"}
_RISK_WORDS = {"high": 0.8, "medium": 0.4, "low": 0.1, "": 0.2}


def _risk_value(risk) -> float:
    if isinstance(risk, (int, float)):
        return max(0.0, min(1.0, float(risk)))
    return _RISK_WORDS.get(str(risk or "").strip().lower(), 0.3)


def _added_lines(patch: str) -> List[str]:
    return [l[1:] for l in (patch or "").splitlines() if l.startswith("+") and not l.startswith("+++")]


def _is_tautological_assert(line: str) -> bool:
    body = line.strip()
    if not body.lower().startswith("assert"):
        return False
    body = body[len("assert"):].strip().rstrip(",").split("#")[0].strip()
    norm = body.replace(" ", "").lower()
    if norm in _TAUTOLOGY_BODIES:
        return True
    if "==" in norm:                                      # `x == x` / `1 == 1`
        a, _, b = norm.partition("==")
        if a and a == b:
            return True
    return False


def _tokens(text: str) -> set:
    import re
    return {w for w in re.findall(r"[a-zA-Z_]\w+", (text or "").lower()) if len(w) > 2}


def test_quality_evidence(test_patch: str, claim: str = "", broken_assumption: str = "") -> Dict:
    """Diagnose how SPECIFIC a test is. A test that imports the target code and checks a concrete expected
    value scores high; `assert True`, no import, or no concrete value scores low — so the LLM cannot win by
    writing an easy test. Property/metamorphic tests and negative controls earn a bonus."""
    added = _added_lines(test_patch)
    text = "\n".join(added)
    low = text.lower()
    asserts = [l for l in added if "assert" in l.lower()]
    non_taut = [l for l in asserts if not _is_tautological_assert(l)]
    has_import = any(l.strip().startswith(("import ", "from ")) for l in added)
    has_concrete = any(op in text for op in ("==", "!=", " is ", "<=", ">=", "approx", "raises", "assertEqual",
                                             "assertAlmostEqual", "assertIs", "assertIn")) and bool(non_taut)
    metamorphic = any(k in low for k in ("parametrize", "hypothesis", "@given", "metamorphic", "property",
                                         "invariant", "for _ in range", "for i in range"))
    negative_control = any(k in low for k in ("raises", "with pytest.raises", "should_fail", "must_not",
                                              "assertraises"))
    claim_tok = _tokens(claim) | _tokens(broken_assumption)
    refs_claim = bool(claim_tok & _tokens(text))
    reasons = []
    score = 0.0
    if not asserts:
        return {"score": 0.05, "reasons": ["no assertion in the test"], "non_tautological_asserts": 0,
                "has_import": has_import, "has_concrete_value": False, "metamorphic": False,
                "negative_control": False, "references_claim": refs_claim}
    if non_taut:
        score += 0.45
    else:
        reasons.append("only tautological assertions (e.g. assert True / x == x)")
    if has_import:
        score += 0.20
    else:
        reasons.append("does not import the target code")
    if has_concrete:
        score += 0.20
    else:
        reasons.append("no concrete expected value")
    if metamorphic:
        score += 0.10
    if negative_control:
        score += 0.10
    if refs_claim:
        score += 0.10
    if not non_taut:
        score = min(score, 0.15)                         # a tautology can never be a quality test
    return {"score": round(max(0.0, min(1.0, score)), 3), "reasons": reasons,
            "non_tautological_asserts": len(non_taut), "has_import": has_import,
            "has_concrete_value": has_concrete, "metamorphic": metamorphic,
            "negative_control": negative_control, "references_claim": refs_claim}


def test_quality_score(test_patch: str, claim: str = "", broken_assumption: str = "") -> float:
    return test_quality_evidence(test_patch, claim, broken_assumption)["score"]


def _test_is_specific(test_patch: str) -> bool:
    """Kept for back-compat: a coarse boolean. The graded signal is `test_quality_score`."""
    t = (test_patch or "")
    return ("assert" in t) and ("def test" in t or "def " in t)


# ── RED granularity (§3: distinguish a real assertion failure from a broken-import 'failure') ──
_COLLECTION_MARKERS = ("errors during collection", "error collecting", "syntaxerror", "importerror",
                       "modulenotfounderror", "indentationerror", "no module named", "cannot import",
                       "internalerror", "usage error", "collected 0 items", "no tests ran",
                       "fixture", "conftest")
_ASSERTION_MARKERS = ("assertionerror", "failed", "assert ")


def classify_test_outcome(result) -> str:
    """Map a CommandResult to one of: GREEN · RED_ASSERTION · RED_COLLECTION · ERROR_TIMEOUT.
    Only `RED_ASSERTION` (the test failed for the scientific reason it was written) is a 'good' RED; an
    import/syntax/collection error is `RED_COLLECTION` and is discounted, because 'it failed then passed'
    is then merely a fix of broken plumbing, not evidence of a real gap."""
    if getattr(result, "timed_out", False):
        return "ERROR_TIMEOUT"
    if result.returncode == 0:
        return "GREEN"
    out = result.output.lower()
    has_assertion = ("assertionerror" in out) or ("1 failed" in out) or (" failed" in out and "passed" in out)
    # pytest exit codes: 2 collection/usage · 3 internal · 4 usage · 5 no tests collected
    if result.returncode in (2, 3, 4, 5) and not has_assertion:
        return "RED_COLLECTION"
    if any(m in out for m in _COLLECTION_MARKERS) and not has_assertion:
        return "RED_COLLECTION"
    if has_assertion or any(m in out for m in _ASSERTION_MARKERS):
        return "RED_ASSERTION"
    if "traceback" in out and "assertionerror" not in out:
        return "RED_COLLECTION"                           # a runtime crash, not an assertion
    return "RED_COLLECTION"                               # conservative default: an unproven RED is not a good RED


def _test_command(plan, repo_root: str) -> List[str]:
    """An argv LIST (never a shell string → zero injection surface) to run the materialized test."""
    test_file = next((f.path for f in plan.files if "test" in f.path.lower()), plan.files[0].path)
    if test_file.endswith(".py") and "test" in test_file.lower():
        return ["python", "-m", "pytest", test_file, "-q", "-p", "no:cacheprovider"]
    return ["python", test_file]


def _to_candidate(cd: Dict, pack) -> Candidate:
    """Convert a validated LLM candidate dict into the existing Candidate type (no API change)."""
    ba = str(cd.get("broken_assumption", "")).strip()
    axis = pack.dimension_of.get(ba, "") or (ba.upper().replace(" ", "_") if ba else "")
    needs = []
    if cd.get("test_patch"):
        needs.append("test_artifact")
    return Candidate(name=str(cd.get("name", "cand"))[:48], operator=str(cd.get("operator", "proposed")),
                     breaks=([axis] if axis else []), assumptions=([ba] if ba else []),
                     negation=str(cd.get("claim", "")), needs=needs,
                     discipline=str(cd.get("world_test_description", "")))


# ── prior-art / anti-rebrand gate (§6: compare the whole idea, not just name+claim) ──
def _idea_signature(cd: Dict) -> str:
    """The full surface a prior-art search should see: name + claim + rationale + world-test + patch INTENT
    (the added source lines), so a rebrand can't hide behind a fresh name with old internals."""
    parts = [cd.get("name", ""), cd.get("claim", ""), cd.get("novelty_rationale", ""),
             cd.get("world_test_description", ""), cd.get("why_standard_families_fail", "")]
    impl = cd.get("implementation_patch", "")
    parts += [l for l in _added_lines(impl)][:12]         # patch intent: the added source lines
    return " ".join(p for p in parts if p)


def _scoped_prior_art_verdict(verdict: str, scope: str) -> str:
    """Qualify novelty by the search scope, including legacy providers that do not expose scoped_verdict()."""
    if verdict == "PROVISIONALLY_NOVEL" and scope == "ONLINE_PRIOR_ART_CHECKED":
        return "PROVISIONALLY_NOVEL_ON_CHECKED_SOURCES"
    if verdict in ("WEAKLY_NOVEL", "PROVISIONALLY_NOVEL") and scope == "LOCAL_ONLY":
        return "LOCAL_ONLY_NOVELTY"
    if verdict in ("WEAKLY_NOVEL", "PROVISIONALLY_NOVEL") and scope == "INCOMPLETE_ONLINE_SEARCH":
        return "PRIOR_ART_INCOMPLETE"
    return verdict


def _prior_art_evidence(nv, verdict: str, source: str, *, fallback_scope: str = "") -> Dict:
    scope = getattr(nv, "novelty_scope", "") or fallback_scope
    scoped = nv.scoped_verdict() if getattr(nv, "novelty_scope", "") else _scoped_prior_art_verdict(verdict, scope)
    return {"verdict": verdict, "scoped_verdict": scoped, "source": source,
            "distance": getattr(nv, "prior_art_distance_score", 0.0),
            "overlap": getattr(nv, "source_overlap_score", 0.0),
            "matches": list(getattr(nv, "closest_matches", []) or [])[:3],
            "novelty_scope": scope,
            "coverage_level": getattr(nv, "coverage_level", "") or ("NONE" if scope == "LOCAL_ONLY" else ""),
            "checked_sources": list(getattr(nv, "checked_sources", []) or []),
            "failed_sources": list(getattr(nv, "failed_sources", []) or []),
            "retrieved_at": getattr(nv, "retrieved_at", "")}


def _prior_art_gate(cd: Dict, pack, archive: QDArchive, provider) -> Tuple[str, Dict]:
    """Return (graded_verdict, evidence). With a provider, search the real world; otherwise compare locally
    against the archive's elites + the pack's known families + the pack's axis terms (rename/collage detectors
    over the FULL idea signature). Never returns 'absolute novelty'."""
    from .novelty import prior_art_audit, GRADED_VERDICTS
    idea = _idea_signature(cd)
    if provider is not None:
        nv = prior_art_audit(idea, provider)
        verdict = nv.graded_verdict or "PROVISIONALLY_NOVEL"
        return verdict, _prior_art_evidence(nv, verdict, "provider", fallback_scope="LOCAL_ONLY")
    # local provider: prior art = archive elites + known families + pack axis terms (so collage shows up)
    matches = [{"title": c.name, "summary": c.negation} for _cell, _q, c in archive.elites()]
    matches += [{"title": f, "summary": f} for f in pack.known_families]
    matches += [{"title": a, "summary": a} for a in getattr(pack, "axes", {}).keys()]
    local = type("P", (), {"research": staticmethod(lambda q: {"matches": matches})})()
    nv = prior_art_audit(idea, local)
    verdict = nv.graded_verdict if nv.graded_verdict in GRADED_VERDICTS else "PROVISIONALLY_NOVEL"
    # a LOCAL-only gate (no online world search) — a 'novel' verdict here is the weakest kind.
    ev = _prior_art_evidence(nv, verdict, "local", fallback_scope="LOCAL_ONLY")
    ev["checked_sources"] = [{"provider": "local_archive_pack", "online": False, "count": len(matches)}]
    return verdict, ev


_REBRAND_VERDICTS = ("RENAMED_PRIOR_ART", "COLLAGE_OF_PRIOR_ART")
_NOVEL_VERDICTS = ("WEAKLY_NOVEL", "PROVISIONALLY_NOVEL", "VERIFIED_USEFUL_NOVELTY")


# a novel verdict is only as strong as the search that backed it (review: penalize local/incomplete scope).
_SCOPE_CAP = {"INCOMPLETE_ONLINE_SEARCH": 0.35, "LOCAL_ONLY": 0.55, "": 0.55}
_COVERAGE_CAP = {"PARTIAL": 0.82, "NONE": 0.55}


def _prior_art_component(verdict: str, evidence: Dict) -> float:
    """Map a graded verdict + distance into [0,1] for the score (rebrands collapse toward 0). A 'novel'
    verdict is then DOWNWEIGHTED by how thorough the prior-art search actually was: a candidate that looks
    novel only against a LOCAL or INCOMPLETE search is worth less than one confirmed against multiple online
    sources (novelty_scope + coverage_level). Rebrands/collages are not boosted — only novel verdicts are
    scaled."""
    if verdict == "RENAMED_PRIOR_ART":
        return 0.0
    if verdict == "COLLAGE_OF_PRIOR_ART":
        return 0.1
    base = {"WEAKLY_NOVEL": 0.6, "PROVISIONALLY_NOVEL": 0.9, "VERIFIED_USEFUL_NOVELTY": 1.0}.get(verdict, 0.5)
    comp = min(1.0, 0.5 * base + 0.5 * float(evidence.get("distance", base)))
    comp = min(comp, _SCOPE_CAP.get(evidence.get("novelty_scope", ""), 1.0))
    comp = min(comp, _COVERAGE_CAP.get(evidence.get("coverage_level", ""), 1.0))
    return round(comp, 3)


# ── diversity gate (§7: force structural exploration, reject near-duplicates) ──
@dataclass
class _DiversityState:
    max_per_assumption: int = 3
    max_per_cell: int = 2
    dup_distance: float = 0.12
    per_assumption: Dict[str, int] = field(default_factory=dict)
    per_cell: Dict = field(default_factory=dict)
    forbidden_assumptions: set = field(default_factory=set)

    def reset_round(self):
        self.per_assumption = {}
        self.per_cell = {}

    def check(self, cd: Dict, cand: Candidate, archive: QDArchive) -> Tuple[bool, str]:
        ba = str(cd.get("broken_assumption", "")).strip().lower() or "?"
        if self.per_assumption.get(ba, 0) >= self.max_per_assumption:
            return False, f"too many candidates this round break '{ba}' (cap {self.max_per_assumption})"
        cell = archive.cell_of(cand)
        if self.per_cell.get(cell, 0) >= self.max_per_cell:
            return False, f"behavioral cell already filled {self.max_per_cell}× this round"
        # near-duplicate ONLY against the elite occupying the SAME cell — a candidate in a different
        # behavioral niche is structurally diverse even if it shares wording with another.
        incumbent = archive.grid.get(cell)
        if incumbent is not None:
            from .embeddings import semantic_distance
            elite = incumbent[1]
            text = f"{cand.name} {' '.join(cand.assumptions)} {cand.negation}"
            if semantic_distance(text, f"{elite.name} {' '.join(elite.assumptions)} {elite.negation}") < self.dup_distance:
                return False, f"near-duplicate of archived elite «{elite.name}» in the same cell"
        self.per_assumption[ba] = self.per_assumption.get(ba, 0) + 1
        self.per_cell[cell] = self.per_cell.get(cell, 0) + 1
        if self.per_assumption[ba] >= self.max_per_assumption:
            self.forbidden_assumptions.add(ba)
        return True, ""

    def diversity_component(self, cd: Dict, cand: Candidate, archive: QDArchive) -> float:
        cell_new = archive.cell_of(cand) not in archive.grid
        ba = str(cd.get("broken_assumption", "")).strip().lower()
        crowd = self.per_assumption.get(ba, 1)
        return round((0.9 if cell_new else 0.5) / max(1, crowd) + (0.1 if cell_new else 0.0), 3)


# ── bounded, targeted repair (§5: Self-Refine on the single broken field, not the whole proposal) ──
def _repair_field(llm, kind: str, context: str) -> str:
    """Ask the model to fix ONLY the broken field. `kind` ∈ {json,test,impl}. Returns the raw completion."""
    if kind == "json":
        ask = ("Your previous reply was not a valid candidate JSON array. Errors:\n" + context +
               "\nReply with ONLY a corrected JSON array of candidate objects. " + _SCHEMA_HINT)
    elif kind == "test":
        ask = ("Your test_patch was not usable:\n" + context +
               "\nReply with ONLY a corrected unified diff for the TEST file (--- /+++ /@@). It must fail "
               "with a real AssertionError (not an import/syntax error) before any implementation.")
    else:
        ask = ("After your test went RED, your implementation_patch did NOT make it GREEN:\n" + context +
               "\nReply with ONLY a corrected unified diff for the IMPLEMENTATION (non-test source).")
    outs = llm.complete(ask, system=_SYSTEM_REPAIR, n=1)
    return outs[0] if outs else ""


# ── transactional materialisation (§2: snapshot → RED → impl → GREEN → rollback unless kept) ──
def _materialize(cd: Dict, repo_root: str, *, runner: CommandRunner, timeout: int, llm=None,
                 max_test_repairs: int = 0, max_impl_repairs: int = 0, keep_failed: bool = False,
                 dry_run: bool = False, telemetry: Optional[Dict] = None) -> Dict:
    """Apply test_patch (RED — proof it catches a real gap), then implementation_patch (GREEN wins), inside a
    transaction that ROLLS BACK on any failure (unless keep_failed). Returns evidence flags + verifier tail.
    Never escapes the repo (paths validated before any write)."""
    tel = telemetry if telemetry is not None else {}
    ev: Dict = {"materialized": False, "red_first": False, "green_final": False, "red_kind": "NOT_MATERIALIZED",
                "tail": "", "patch_repairs": 0}
    # Disable bytecode caching for materialized runs: rapid same-size rewrites (e.g. `return 41`→`return 42`
    # within the same second) defeat __pycache__'s mtime+size invalidation, so a fresh `python` would import
    # STALE bytecode and report a false RED/GREEN. With no .pyc ever written, the source is always read fresh.
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    test_patch = cd.get("test_patch")
    if not test_patch:
        return ev
    tx = PatchTransaction(repo_root)
    try:
        # 1) apply the test (with bounded repair if it doesn't apply)
        plan = parse_unified_diff(test_patch)
        ok, errs = validate_patch_paths(plan, repo_root)
        if not ok:
            ev["tail"] = "rejected unsafe patch: " + "; ".join(errs)
            return ev
        res = tx.apply(plan)
        tries = 0
        while not res["applied"] and llm is not None and tries < max_test_repairs:
            tries += 1; tel["test_repairs"] = tel.get("test_repairs", 0) + 1
            test_patch = _repair_field(llm, "test", "; ".join(res["errors"]) or "test_patch did not apply")
            plan = parse_unified_diff(test_patch)
            if not validate_patch_paths(plan, repo_root)[0]:
                break
            res = tx.apply(plan)
        if not res["applied"]:
            ev["tail"] = "test_patch did not apply"
            return ev
        ev["materialized"] = True; ev["patch_repairs"] = tries
        cmd = _test_command(plan, repo_root)

        # 2) run RED, classify, optionally repair a RED_COLLECTION into a real RED_ASSERTION
        result = runner.run(cmd, cwd=repo_root, timeout=timeout, env=env)
        outcome = classify_test_outcome(result)
        ev["tail"] = result.tail()
        tries = 0
        while outcome == "RED_COLLECTION" and llm is not None and tries < max_test_repairs:
            tries += 1; tel["test_repairs"] = tel.get("test_repairs", 0) + 1
            fixed = _repair_field(llm, "test", "the test failed at COLLECTION (import/syntax), not on an "
                                  "assertion:\n" + result.tail())
            fplan = parse_unified_diff(fixed)
            if not validate_patch_paths(fplan, repo_root)[0] or not tx.apply(fplan)["applied"]:
                break
            plan = fplan; cmd = _test_command(plan, repo_root)
            result = runner.run(cmd, cwd=repo_root, timeout=timeout, env=env)
            outcome = classify_test_outcome(result); ev["tail"] = result.tail()
        ev["red_kind"] = outcome
        ev["red_first"] = outcome in ("RED_ASSERTION", "RED_COLLECTION", "ERROR_TIMEOUT")
        if outcome == "GREEN":
            ev["red_first"] = False                       # the test passed before any patch → it proves nothing
            tx.rollback()
            return ev

        # 3) apply the implementation, run GREEN (with bounded repair)
        impl = cd.get("implementation_patch")
        if impl:
            iplan = parse_unified_diff(impl)
            if validate_patch_paths(iplan, repo_root)[0] and tx.apply(iplan)["applied"]:
                result2 = runner.run(cmd, cwd=repo_root, timeout=timeout, env=env)
                ev["green_final"] = classify_test_outcome(result2) == "GREEN"; ev["tail"] = result2.tail()
                tries = 0
                while not ev["green_final"] and llm is not None and tries < max_impl_repairs:
                    tries += 1; tel["impl_repairs"] = tel.get("impl_repairs", 0) + 1
                    fixed = _repair_field(llm, "impl", "the test is still RED after your patch:\n" + result2.tail())
                    fiplan = parse_unified_diff(fixed)
                    if not validate_patch_paths(fiplan, repo_root)[0] or not tx.apply(fiplan)["applied"]:
                        break
                    result2 = runner.run(cmd, cwd=repo_root, timeout=timeout, env=env)
                    ev["green_final"] = classify_test_outcome(result2) == "GREEN"; ev["tail"] = result2.tail()

        # 4) keep on GREEN (so a real win lands in the repo), else roll back unless keep_failed
        if dry_run:
            tx.rollback()
        elif ev["green_final"] or keep_failed:
            tx.commit()
        else:
            tx.rollback()
        return ev
    except Exception as e:                                 # any failure → leave the repo exactly as found
        tx.rollback()
        ev["tail"] = f"materialization error: {e}"
        return ev


# ── the prompt (every round carries archive elites + failures + verifier tail + prior-art + forbidden cells) ──
def _build_prompt(problem, pack, archive, failures, verifier_tail, prior_art_warn, forbidden, samples,
                  memory_block: str = "") -> str:
    asms = ", ".join(a.name for a in breakable(pack)) or "—"
    fams = ", ".join(pack.known_families[:8]) or "—"
    elites = "; ".join(f"{c.name} (q={q})" for _c, q, c in archive.elites()[:5]) or "none yet"
    fails = "; ".join(failures[-5:]) or "none yet"
    from .orthogonal_germs import orthogonal_germ_instruction, orthogonal_germ_relevant
    L = [f"PROBLEM: {problem}",
         f"DOMAIN BOX: {pack.box_name}",
         f"ASSUMPTIONS YOU MAY BREAK: {asms}",
         f"KNOWN FAMILIES TO BEAT (do NOT rebrand these): {fams}",
         f"CURRENT BEST ELITES (be DIFFERENT from these): {elites}",
         f"PAST FAILURES (do not repeat): {fails}"]
    if orthogonal_germ_relevant(pack, problem):        # only push the new-basis move when it is on-topic
        L.append(orthogonal_germ_instruction(pack))
    if forbidden:
        L.append(f"ASSUMPTIONS ALREADY SATURATED this search (break a DIFFERENT one): {', '.join(sorted(forbidden))}")
    if verifier_tail:
        L.append(f"LAST VERIFIER OUTPUT (tail): {verifier_tail[-400:]}")
    if prior_art_warn:
        L.append(f"PRIOR-ART WARNINGS: {prior_art_warn}")
    if memory_block:                                 # #8: cues routed from the creative memories (router)
        L.append(memory_block)
    L += [f"\nReturn {samples} DIFFERENT candidates as a JSON array. {_SCHEMA_HINT}",
          "Each must break a DIFFERENT assumption and include a failing test_patch (real assertion, not a "
          "broken import) plus an implementation_patch that changes real source — not one that skips the test."]
    return "\n".join(L)


@dataclass
class LLMCandidate:
    name: str
    score: float
    verdict: str
    candidate: Candidate
    evidence: Dict = field(default_factory=dict)


@dataclass
class LLMSearchResult:
    problem: str
    archive: QDArchive
    candidates: List[LLMCandidate] = field(default_factory=list)
    llm_call_count: int = 0
    valid_count: int = 0
    discarded_count: int = 0
    materialized_count: int = 0
    red_first_count: int = 0
    red_assertion_count: int = 0
    red_collection_count: int = 0
    error_timeout_count: int = 0
    green_final_count: int = 0
    rebrand_count: int = 0
    duplicates_rejected: int = 0
    json_repairs: int = 0
    test_repairs: int = 0
    impl_repairs: int = 0
    rejected: List[Dict] = field(default_factory=list)    # [{name, reason}]
    reflections: List[str] = field(default_factory=list)

    def best(self) -> Optional[LLMCandidate]:
        return max(self.candidates, key=lambda c: c.score) if self.candidates else None

    def to_dict(self) -> Dict:
        """Machine-readable telemetry (§10) — so you can tell improvement from mere LLM-call spend."""
        b = self.best()
        return {
            "problem": self.problem,
            "llm_call_count": self.llm_call_count,
            "valid": self.valid_count, "discarded": self.discarded_count,
            "materialized": self.materialized_count,
            "red_assertion": self.red_assertion_count, "red_collection": self.red_collection_count,
            "error_timeout": self.error_timeout_count, "red_first": self.red_first_count,
            "green_final": self.green_final_count, "rebrands_blocked": self.rebrand_count,
            "duplicates_rejected": self.duplicates_rejected,
            "repairs": {"json": self.json_repairs, "test": self.test_repairs, "impl": self.impl_repairs},
            "archive_coverage": self.archive.coverage(), "qd_score": self.archive.qd_score(),
            "best": None if not b else {
                "name": b.name, "score": b.score, "verdict": b.verdict,
                "components": score_components(b.evidence), "green_final": b.evidence.get("green_final"),
                "red_kind": b.evidence.get("red_kind"),
                "prior_art_scope": b.evidence.get("prior_art_scope"),
                "prior_art_scoped_verdict": b.evidence.get("prior_art_scoped_verdict"),
                "prior_art_coverage_level": b.evidence.get("prior_art_coverage_level"),
                "prior_art_checked_sources": b.evidence.get("prior_art_checked_sources", []),
                "prior_art_failed_sources": b.evidence.get("prior_art_failed_sources", [])},
            "rejected_reasons": self.rejected[-12:],
        }

    def markdown(self) -> str:
        b = self.best()
        L = [f"## llm-search — «{self.problem}»",
             f"- LLM calls: {self.llm_call_count} · candidates valid/discarded: {self.valid_count}/{self.discarded_count}"
             f" · repairs json/test/impl: {self.json_repairs}/{self.test_repairs}/{self.impl_repairs}",
             f"- materialized: {self.materialized_count} · RED_ASSERTION: {self.red_assertion_count} · "
             f"RED_COLLECTION: {self.red_collection_count} · GREEN-final: {self.green_final_count} · "
             f"rebrands blocked: {self.rebrand_count} · duplicates rejected: {self.duplicates_rejected}",
             f"- archive coverage: {self.archive.coverage()} cells · QD-score {self.archive.qd_score()}"]
        if b:
            c = score_components(b.evidence)
            scope = b.evidence.get("prior_art_scope") or "unscoped"
            scoped_verdict = b.evidence.get("prior_art_scoped_verdict") or b.verdict
            L.append(f"- BEST (external score {b.score}, {b.verdict}): «{b.name}» — green={b.evidence.get('green_final')}"
                     f", red={b.evidence.get('red_kind')}, prior_art={scoped_verdict}/{scope}")
            L.append(f"  components: " + " · ".join(f"{k}={v}" for k, v in c.items()))
        if self.reflections:
            L.append("- failure reflections: " + " | ".join(self.reflections[-5:]))
        return "\n".join(L)


def llm_openended_search(problem: str, llm=None, repo_path: Optional[str] = None, budget: int = 30,
                         islands: int = 4, samples_per_round: int = 4, execute: bool = False,
                         materialize: bool = False, prior_art_provider=None,
                         ledger_path: Optional[str] = None,
                         max_json_repairs: int = 0, max_test_repairs: int = 0, max_impl_repairs: int = 0,
                         keep_failed: bool = False, dry_run: bool = False, timeout: int = 60,
                         weights: Optional[Dict[str, float]] = None,
                         max_per_assumption: int = 3, max_per_cell: int = 2,
                         memory_router=None) -> LLMSearchResult:
    """Run the LLM-in-the-loop search. The LLM is called once per round (budget // samples_per_round rounds);
    each candidate is prior-art gated, diversity gated, optionally MATERIALIZED (test RED → patch GREEN, in a
    rollback-safe transaction) and scored by execution into readable components. Bounded repair fixes a broken
    JSON/test/impl field instead of discarding the whole proposal. Opt-in: an `llm` provider is required; when
    omitted it is resolved from the process-wide default (`set_default_llm` / OUTLIER_MCB_LLM)."""
    if llm is None:                                   # GENERATIVITY: draw the content source from the default
        from .llm import default_llm
        llm = default_llm()
    if llm is None:
        from .errors import OUTLIER_MCBError
        raise OUTLIER_MCBError(
            "llm_openended_search needs an LLM content source. Pass llm=…, or register one with "
            "gsl.set_default_llm(provider) / export OUTLIER_MCB_LLM=subprocess:<your-llm-cli>.")
    from .pack import select_pack
    pack, _ = select_pack(problem)
    repo = None
    if repo_path is not None:
        from .grounding import probe
        repo = probe(repo_path)
    archive = QDArchive(pack=pack, repo=repo)
    res = LLMSearchResult(problem=problem, archive=archive)
    runner = CommandRunner(default_timeout=timeout)
    div = _DiversityState(max_per_assumption=max_per_assumption, max_per_cell=max_per_cell)
    failures: List[str] = []
    verifier_tail = ""
    rounds = max(1, budget // max(1, samples_per_round))

    for _r in range(rounds):
        div.reset_round()
        prior_warn = "; ".join(f"{c.name}:{c.verdict}" for c in res.candidates[-4:]
                               if c.verdict in _REBRAND_VERDICTS) or ""
        mem_block = ""
        if memory_router is not None:                # #8: route the creative memories into the prompt each round
            try:
                mem_block = memory_router.plan(problem).prompt_block
            except Exception:
                mem_block = ""
        prompt = _build_prompt(problem, pack, archive, failures, verifier_tail, prior_warn,
                               div.forbidden_assumptions, samples_per_round, memory_block=mem_block)
        completions = llm.complete(prompt, system=_SYSTEM, n=samples_per_round)
        res.llm_call_count += 1
        for comp in completions:
            pr = parse_candidates(comp)
            # JSON repair (§5): if a completion yielded nothing valid, ask for a corrected JSON array
            tries = 0
            while not pr.valid and tries < max_json_repairs:
                tries += 1; res.json_repairs += 1
                errs = "; ".join(e for d in pr.discarded for e in d.get("errors", []))
                comp = _repair_field(llm, "json", errs or "not valid JSON")
                pr = parse_candidates(comp)
            res.discarded_count += len(pr.discarded)
            for cd in pr.valid:
                res.valid_count += 1
                verdict, pa_ev = _prior_art_gate(cd, pack, archive, prior_art_provider)
                rebrand = verdict in _REBRAND_VERDICTS
                cand = _to_candidate(cd, pack)
                # a rebrand is recorded as a candidate (proof the gate fired) but hard-scored to 0 and never
                # archived/materialized — it cannot become the winner, and it does not count as a duplicate.
                if rebrand:
                    res.rebrand_count += 1
                    ev_r = {"rebrand": True, "prior_art_component": 0.0, "prior_art_evidence": pa_ev,
                            "prior_art_scope": pa_ev.get("novelty_scope"),
                            "prior_art_scoped_verdict": pa_ev.get("scoped_verdict"),
                            "prior_art_coverage_level": pa_ev.get("coverage_level"),
                            "prior_art_checked_sources": pa_ev.get("checked_sources", []),
                            "prior_art_failed_sources": pa_ev.get("failed_sources", []),
                            "has_patch": bool(cd.get("test_patch") or cd.get("implementation_patch"))}
                    res.candidates.append(LLMCandidate(name=cand.name, score=llm_evidence_score(ev_r, weights),
                                                       verdict=verdict, candidate=cand, evidence=ev_r))
                    failures.append(f"{cand.name}: rebrand of prior art")
                    res.rejected.append({"name": cand.name, "reason": "rebrand of prior art"})
                    res.reflections.append(f"{cand.name} → rebrand of prior art")
                    continue
                # diversity gate (§7): reject near-duplicates / over-crowded assumptions/cells
                accepted, drop_reason = div.check(cd, cand, archive)
                if not accepted:
                    res.duplicates_rejected += 1
                    res.rejected.append({"name": cand.name, "reason": drop_reason})
                    res.reflections.append(f"{cand.name} → {drop_reason}")
                    continue
                tq = test_quality_score(cd.get("test_patch", ""), cd.get("claim", ""),
                                        cd.get("broken_assumption", ""))
                subst = patch_substance_evidence(cd.get("test_patch", ""), cd.get("implementation_patch", ""))
                ev: Dict = {
                    "rebrand": rebrand, "prior_art_component": _prior_art_component(verdict, pa_ev),
                    "prior_art_evidence": pa_ev, "prior_art_weak": verdict in _NOVEL_VERDICTS,
                    "prior_art_scope": pa_ev.get("novelty_scope"),
                    "prior_art_scoped_verdict": pa_ev.get("scoped_verdict"),
                    "prior_art_coverage_level": pa_ev.get("coverage_level"),
                    "prior_art_checked_sources": pa_ev.get("checked_sources", []),
                    "prior_art_failed_sources": pa_ev.get("failed_sources", []),
                    "has_patch": bool(cd.get("test_patch") or cd.get("implementation_patch")),
                    "test_specific": _test_is_specific(cd.get("test_patch", "")),
                    "test_quality": tq, "patch_substance": subst["score"], "patch_substance_evidence": subst,
                    "only_cosmetic": subst["only_cosmetic"], "risk": _risk_value(cd.get("risk")),
                    "diversity": div.diversity_component(cd, cand, archive),
                    "cell_new": archive.cell_of(cand) not in archive.grid,
                }
                tel: Dict = {}
                if materialize and repo is not None and repo.grounded and cd.get("test_patch"):
                    mat = _materialize(cd, repo.root, runner=runner, timeout=timeout, llm=llm,
                                       max_test_repairs=max_test_repairs, max_impl_repairs=max_impl_repairs,
                                       keep_failed=keep_failed, dry_run=dry_run, telemetry=tel)
                    ev.update(materialized=mat["materialized"], red_first=mat["red_first"],
                              red_kind=mat["red_kind"], green_final=mat["green_final"])
                    res.materialized_count += int(mat["materialized"])
                    res.red_first_count += int(mat["red_first"])
                    res.red_assertion_count += int(mat["red_kind"] == "RED_ASSERTION")
                    res.red_collection_count += int(mat["red_kind"] == "RED_COLLECTION")
                    res.error_timeout_count += int(mat["red_kind"] == "ERROR_TIMEOUT")
                    res.green_final_count += int(mat["green_final"])
                    res.test_repairs += tel.get("test_repairs", 0)
                    res.impl_repairs += tel.get("impl_repairs", 0)
                    verifier_tail = mat["tail"] or verifier_tail
                score = llm_evidence_score(ev, weights)
                archive.add(cand, quality=score)
                res.candidates.append(LLMCandidate(name=cand.name, score=score, verdict=verdict,
                                                   candidate=cand, evidence=ev))
                if score < 0.3:
                    reason = ("RED_COLLECTION not RED_ASSERTION" if ev.get("red_kind") == "RED_COLLECTION" else
                              "no GREEN / unmaterialized test" if not ev.get("green_final") else "low evidence")
                    failures.append(f"{cand.name}: {reason}")
                    res.rejected.append({"name": cand.name, "reason": reason})
                    res.reflections.append(f"{cand.name} → {reason}")
    return res
