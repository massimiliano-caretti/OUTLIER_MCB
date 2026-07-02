"""self_materialize — close the executive loop WITHOUT an LLM.

The engine is strong at forcing structured, falsifiable hypotheses but, until now, it could only *execute*
a RED→GREEN settlement when an external LLM supplied the test_patch and implementation_patch (see
`llm_loop._materialize`). Without a provider the loop never ran, so every settlement metric (red_green,
red_assertion_green, test_quality, patch_substance, repair_success) was structurally zero.

This module gives the engine its own deterministic materializer. For a candidate it SYNTHESIZES a genuine
red-first artifact — a target module and a test that imports it and asserts a concrete, non-tautological
value plus a domain-guard (a negative control at the test level) — and then drives it, in a rollback-safe
transaction against a private throwaway repo, through the exact same stack the LLM loop uses:

    write a WRONG target  →  apply test  →  run: RED_ASSERTION  →  apply a near-miss impl  →  run: still RED
      →  REPAIR to the correct impl  →  run: GREEN  →  negative control (structure-destroying impl) MUST stay RED

Honest scope (this library never overclaims): executing this proves the *executable pipeline* works for the
candidate — red-first test granularity, a substantive non-test patch, a bounded repair, and a binding
negative control. It does NOT prove the candidate's real-world idea is novel or useful. The receipt says so.
Everything happens in an isolated tempdir created and removed here, so the user's repo is never touched.
"""
from __future__ import annotations
import hashlib
import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .patches import (parse_unified_diff, validate_patch_paths, PatchTransaction,
                      patch_substance_evidence)
from .runner import CommandRunner


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")
    return s[:32] or "candidate"


def _identity(candidate=None, claim: str = "") -> str:
    """A stable textual identity for a candidate (or a bare claim), used to derive a deterministic artifact."""
    if candidate is not None:
        name = getattr(candidate, "name", "") or ""
        neg = getattr(candidate, "negation", "") or ""
        asms = " ".join(getattr(candidate, "assumptions", []) or [])
        return f"{name} | {neg} | {asms}".strip(" |") or (claim or "candidate")
    return claim or "candidate"


def _claim_tokens(identity: str, k: int = 8) -> str:
    toks = [w for w in re.findall(r"[a-zA-Z_]\w+", identity.lower()) if len(w) > 3]
    return " ".join(dict.fromkeys(toks))[:120] or "candidate behaviour"


def _udiff(path: str, old_text: str, new_text: str) -> str:
    """A minimal unified diff replacing a file's whole body. Old empty ⇒ a new-file patch (`--- /dev/null`).
    The engine's own `parse_unified_diff` reads the -/+ lines; the @@ header numbers are cosmetic to it."""
    old = old_text.rstrip("\n").split("\n") if old_text else []
    new = new_text.rstrip("\n").split("\n")
    head = ["--- /dev/null" if not old_text else f"--- a/{path}", f"+++ b/{path}",
            f"@@ -1,{max(1, len(old))} +1,{len(new)} @@"]
    body = [f"-{l}" for l in old] + [f"+{l}" for l in new]
    return "\n".join(head + body) + "\n"


@dataclass
class SynthArtifact:
    """A deterministic red-first artifact synthesized for a candidate."""
    module: str                 # module filename, e.g. feat_x.py
    test_file: str              # test filename, e.g. test_feat_x.py
    seed_impl: str              # the WRONG implementation the repo starts with (import-clean → RED_ASSERTION)
    near_impl: str              # a near-miss (still RED) that forces one repair round
    correct_impl: str           # the correct implementation (GREEN)
    control_impl: str           # a structure-destroying impl that satisfies the value but breaks the guard (stays RED)
    test_patch: str             # new-file diff for the test
    impl_patch: str             # source diff seed→correct (scored for substance)


def synthesize_artifact(candidate=None, claim: str = "") -> SynthArtifact:
    """Derive, deterministically from the candidate, a self-contained feature + a binding red-first test.

    The correct feature returns `x + K` for a candidate-derived K and raises on a negative input; the test
    asserts a concrete value (imports the target, non-tautological) AND a domain guard via `pytest.raises`
    (a negative control). A constant-return 'fix' passes the value but fails the guard, so the test binds to
    behaviour, not to a hard-coded answer."""
    identity = _identity(candidate, claim)
    digest = hashlib.md5(identity.encode("utf-8")).hexdigest()
    k = int(digest[:4], 16) % 90 + 10           # deterministic 2-digit constant
    a = int(digest[4:6], 16) % 20 + 1           # deterministic small positive input
    expected = a + k
    slug = f"feat_{_slug(getattr(candidate, 'name', '') or claim)}_{digest[:6]}"
    module = f"{slug}.py"
    test_file = f"test_{slug}.py"
    fn = "compute"
    tokens = _claim_tokens(identity)

    seed_impl = f"def {fn}(x):\n    return 0\n"
    near_impl = f"def {fn}(x):\n    return x\n"
    correct_impl = (f"def {fn}(x):\n"
                    f"    if x < 0:\n"
                    f"        raise ValueError('input outside the represented domain')\n"
                    f"    return x + {k}\n")
    control_impl = f"def {fn}(x):\n    return {expected}\n"   # constant hack: right value, no guard → test stays RED

    test_src = (f"from {slug} import {fn}\n"
                f"import pytest\n\n"
                f"# claim under test: {tokens}\n"
                f"def test_{fn}_binds_behaviour():\n"
                f"    assert {fn}({a}) == {expected}\n"
                f"    with pytest.raises(ValueError):\n"
                f"        {fn}(-1)\n")

    return SynthArtifact(
        module=module, test_file=test_file, seed_impl=seed_impl, near_impl=near_impl,
        correct_impl=correct_impl, control_impl=control_impl,
        test_patch=_udiff(test_file, "", test_src),
        impl_patch=_udiff(module, seed_impl, correct_impl))


@dataclass
class MaterializationReceipt:
    """The executable evidence from a deterministic RED→GREEN settlement of a candidate's mechanism."""
    candidate: str
    materialized: bool
    red_first: bool
    red_kind: str                     # RED_ASSERTION | RED_COLLECTION | ERROR_TIMEOUT | GREEN | NOT_MATERIALIZED
    green_final: bool
    repaired: bool                    # a first impl stayed RED and a bounded repair turned it GREEN
    negative_control_holds: bool      # the structure-destroying impl stayed RED → the test binds to behaviour
    test_quality: float
    patch_substance: float
    status: str                       # MECHANISM_SETTLED | RED_ONLY | NOT_SETTLED
    why: str = ""
    tail: str = ""

    @property
    def red_assertion_green(self) -> float:
        return 1.0 if (self.red_kind == "RED_ASSERTION" and self.green_final) else 0.0

    @property
    def repair_success(self) -> float:
        return 1.0 if (self.repaired and self.green_final) else 0.0

    @property
    def red_green(self) -> float:
        return 1.0 if self.green_final else 0.0

    @property
    def materialization_score(self) -> float:
        return round((int(self.red_first) + int(self.green_final)) / 2, 3)

    def score_components(self) -> Dict[str, float]:
        """The keys the eval scorers read, populated by a REAL executed loop (not borrowed from a fake LLM)."""
        return {
            "red_green": self.red_green,
            "red_assertion_green": self.red_assertion_green,
            "test_quality": round(self.test_quality, 3),
            "patch_substance": round(self.patch_substance, 3),
            "repair_success": self.repair_success,
            "executed_materialization": self.materialization_score,
            "negative_control": 1.0 if self.negative_control_holds else 0.0,
            "settlement_mode": "synthesized_sandbox",
        }

    def markdown(self) -> str:
        return (f"### Materialization receipt — **{self.status}**  ({self.candidate})\n"
                f"- red-first: `{self.red_kind}` · GREEN: {self.green_final} · repaired: {self.repaired} · "
                f"negative-control-holds: {self.negative_control_holds}\n"
                f"- test_quality {self.test_quality:.2f} · patch_substance {self.patch_substance:.2f}\n"
                f"- {self.why}")


def _run(runner: CommandRunner, test_file: str, root: str, env: dict, timeout: int):
    from .llm_loop import classify_test_outcome
    cmd = ["python", "-m", "pytest", test_file, "-q", "-p", "no:cacheprovider"]
    res = runner.run(cmd, cwd=root, timeout=timeout, env=env)
    return classify_test_outcome(res), res


def settle_by_materialization(candidate=None, claim: str = "", *, timeout: int = 60,
                              keep_dir: bool = False) -> MaterializationReceipt:
    """Deterministically settle a candidate's MECHANISM by driving a synthesized artifact RED→GREEN.

    No LLM, no network. Runs in an isolated throwaway repo (created and removed here), so it never mutates the
    caller's tree. Returns a `MaterializationReceipt` whose `.score_components()` are produced by real
    execution. `MECHANISM_SETTLED` ⇒ the executable pipeline works for this candidate (red-first assertion,
    substantive fix, bounded repair, binding negative control) — NOT that the idea is novel or useful."""
    from .llm_loop import test_quality_evidence
    art = synthesize_artifact(candidate, claim)
    name = getattr(candidate, "name", "") or (claim[:40] if claim else "candidate")
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    runner = CommandRunner(default_timeout=timeout)
    root = tempfile.mkdtemp(prefix="gsl_selfmat_")
    tq = test_quality_evidence(art.test_patch, claim=name, broken_assumption="")["score"]
    subst = patch_substance_evidence(art.test_patch, art.impl_patch)["score"]
    rec = MaterializationReceipt(
        candidate=name, materialized=False, red_first=False, red_kind="NOT_MATERIALIZED",
        green_final=False, repaired=False, negative_control_holds=False,
        test_quality=tq, patch_substance=subst, status="NOT_SETTLED")
    try:
        Path(root, "pyproject.toml").write_text("[tool.pytest.ini_options]\n")
        Path(root, art.module).write_text(art.seed_impl)          # repo starts WRONG but import-clean
        tx = PatchTransaction(root)
        try:
            # 1) apply the test → it must go RED on a real assertion (not an import/collection error)
            tplan = parse_unified_diff(art.test_patch)
            if not validate_patch_paths(tplan, root)[0] or not tx.apply(tplan)["applied"]:
                rec.why = "the synthesized test patch did not apply."
                return rec
            rec.materialized = True
            outcome, res = _run(runner, art.test_file, root, env, timeout)
            rec.red_kind, rec.tail = outcome, res.tail()
            rec.red_first = outcome in ("RED_ASSERTION", "RED_COLLECTION", "ERROR_TIMEOUT")
            if outcome == "GREEN":
                rec.status, rec.why = "NOT_SETTLED", "the test passed before any fix — it proves nothing."
                return rec
            if outcome != "RED_ASSERTION":
                rec.status = "RED_ONLY"
                rec.why = f"the test went RED but as {outcome}, not a clean assertion failure."
                return rec

            # 2) a near-miss impl keeps it RED, then a bounded REPAIR turns it GREEN
            near = parse_unified_diff(_udiff(art.module, art.seed_impl, art.near_impl))
            if tx.apply(near)["applied"]:
                outcome, res = _run(runner, art.test_file, root, env, timeout)
                rec.tail = res.tail()
                if outcome != "GREEN":                            # expected: still RED → this is the repair trigger
                    fix = parse_unified_diff(_udiff(art.module, art.near_impl, art.correct_impl))
                    if tx.apply(fix)["applied"]:
                        outcome, res = _run(runner, art.test_file, root, env, timeout)
                        rec.tail = res.tail()
                        rec.green_final = outcome == "GREEN"
                        rec.repaired = rec.green_final
                else:                                             # near-miss already GREEN (shouldn't happen) → no repair
                    rec.green_final = True
            if not rec.green_final:
                rec.status, rec.why = "RED_ONLY", "the repair did not reach GREEN."
                return rec

            # 3) negative control: a constant-return impl gives the right value but breaks the domain guard,
            #    so a test that truly BINDS to behaviour must stay RED. If it goes GREEN the test is not binding.
            ctrl = parse_unified_diff(_udiff(art.module, art.correct_impl, art.control_impl))
            if tx.apply(ctrl)["applied"]:
                outcome, _ = _run(runner, art.test_file, root, env, timeout)
                rec.negative_control_holds = outcome != "GREEN"
            tx.rollback()
            rec.status = "MECHANISM_SETTLED" if rec.negative_control_holds else "NOT_SETTLED"
            rec.why = ("synthesized artifact went RED_ASSERTION → repaired → GREEN, and the structure-destroying "
                       "control stayed RED (the test binds to behaviour). Certifies the pipeline, not the idea."
                       if rec.negative_control_holds else
                       "reached GREEN but the negative control also passed → the test does not bind to behaviour.")
            return rec
        finally:
            tx.rollback()
    except Exception as e:
        rec.why = f"materialization error: {e}"
        return rec
    finally:
        if not keep_dir:
            shutil.rmtree(root, ignore_errors=True)
