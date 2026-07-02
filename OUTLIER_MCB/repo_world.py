"""repo_world — the codebase IS the world-test. The resolver is the repo, not the engine.

A candidate's world-test is compiled into an EXECUTABLE check the assistant runs in VS Code — a test
that must flip red→green, a type/contract that must hold, a benchmark that must improve — so novelty is
certified by the repo's own gates, never by the engine grading itself.

Grounding: when a real `RepoContext` (grounding.probe) is supplied, the check uses the DETECTED command
and names a REAL file to touch — it is `grounded=True` and actually runnable. Without one, a placeholder
is emitted and flagged `grounded=False`, so the rest of the engine can discount an ungrounded idea
instead of mistaking a well-worded SPEC for a real test.

Collaborators: grounding.RepoContext (the source of truth); economy.forge_bet (wraps a check in a bet).
"""
from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class RepoCheck:
    kind: str                  # test_flip | type_contract | benchmark | build_gate | property
    command: str               # the concrete thing to run in the repo
    pass_condition: str        # what must be true to WIN the bet
    fail_baseline: str         # what the box does TODAY (must currently fail / be absent)
    target: str = ""           # the real file the assistant should touch (when grounded)
    grounded: bool = False     # True ⇒ derived from a real RepoContext and actually runnable
    # ── artifact contract (a world-test is NOT just a command) ──
    artifact: str = ""             # the concrete artifact to create/modify
    test_name: str = ""            # the id of the test that encodes the prediction
    baseline_assertion: str = ""   # what the CURRENT code fails / lacks (must be red today)
    negative_control: str = ""     # the perturbation that must make the test FAIL (proving it tests the axis)
    success_condition: str = ""    # the concrete condition that wins the bet
    implementation_hint: str = ""  # the minimal change that would make it pass
    resolver: str = "repo"

    @property
    def is_full_contract(self) -> bool:
        """A grounded world-test must be a full artifact contract, not a bare command."""
        return all([self.command, self.target, self.test_name, self.baseline_assertion,
                    self.negative_control, self.success_condition, self.implementation_hint])
    note: str = ""
    def markdown(self) -> str:
        lines = [f"### Repo world-test — {self.kind}  (grounded={self.grounded}, resolver: {self.resolver})",
                 f"- **run:** `{self.command}`",
                 f"- **wins iff:** {self.pass_condition}",
                 f"- **baseline (must currently fail/absent):** {self.fail_baseline}"]
        if self.target:
            lines.append(f"- **touch:** `{self.target}`")
        if self.note:
            lines.append(f"- **note:** {self.note}")
        return "\n".join(lines)


# placeholder commands per kind, used only when no real toolchain is known.
_PLACEHOLDER = {
    "test_flip":     ("{test_cmd}", "a NEW test encoding the prediction goes GREEN without regressing the suite",
                      "the prediction has no test today, or the obvious test is red"),
    "type_contract": ("{type_cmd}", "a stricter type/invariant the candidate implies type-checks across the codebase",
                      "the contract cannot even be expressed under the current design"),
    "benchmark":     ("{bench_cmd}", "the deciding metric improves past the box baseline by a pre-registered margin",
                      "the box sits at the current benchmark number"),
    "build_gate":    ("{build_cmd}", "the candidate builds with the extra invariant enabled (or after the deletion)",
                      "the invariant is not enforceable / the stage cannot be removed under the current build"),
    "property":      ("{test_cmd} -k property", "a property/metamorphic test the candidate predicts holds",
                      "no property captures the claim today"),
}
_AXIS_KIND = {"representation": "property", "measure": "benchmark", "objective": "benchmark",
              "structure": "type_contract", "interface": "type_contract", "hypothesis": "property",
              "cost_model": "benchmark", "decomposition": "build_gate"}


def _pick_kind(axis: str, claim: str) -> str:
    t = (claim or "").lower()
    if any(w in t for w in ("type", "invariant", "contract", "interface")):
        return "type_contract"
    if any(w in t for w in ("faster", "latency", "throughput", "rate", "cost", "benchmark", "improve")):
        return "benchmark"
    if any(w in t for w in ("delete", "remove", "dissolve")):
        return "build_gate"
    return _AXIS_KIND.get((axis or "").lower(), "test_flip")


def _slug(text: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in (text or "x").lower()).strip("_")[:40] or "claim"


def _grounded_check(kind: str, repo, claim: str, axis: str = "") -> Optional[RepoCheck]:
    """Build a runnable, FULL-CONTRACT check from a real RepoContext, or None if no command exists."""
    cmd = {"test_flip": repo.test_command, "property": repo.test_command,
           "type_contract": repo.type_command, "build_gate": repo.build_command,
           "benchmark": repo.test_command}.get(kind)
    if not cmd:
        cmd = repo.test_command or repo.type_command or repo.build_command   # fall back to any real gate
        kind = "test_flip" if cmd == repo.test_command else kind
    if not cmd:
        return None
    component = repo.components[0] if repo.components else "the relevant component"
    sym = repo.symbols[0] if repo.symbols else "the public entry point"
    test_name = f"test_{_slug(axis)}_{_slug(claim)}"
    # HONESTY FIX (#8): the world-test is a NEW red-first test that ENCODES THIS idea's prediction — not an
    # edit to some arbitrary pre-existing file. Name the target after the claim (in the repo's test dir) so
    # every idea's contract is distinct and runnable, instead of pinning them all to repo.test_files[0].
    if repo.test_files:
        test_dir = os.path.dirname(repo.test_files[0]) or "tests"
        target = os.path.join(test_dir, f"{test_name}.py")
    elif repo.source_files:
        target = f"a new test next to {repo.source_files[0]}"
    else:
        target = "a new test module"
    # target the SPECIFIC new test, not the whole suite: `-k test_name` passes only if THAT test exists
    # and is green (pytest exits non-zero / "no tests ran" when it is absent) — defeats the self-fooling.
    # Applies to ANY pytest-based check, including a benchmark (its prediction is encoded as a regression
    # test that passes iff the metric beats the baseline) — so the contract is a selectable red-first test,
    # never a whole-suite run that could pass without the new test even existing.
    if "pytest" in cmd:
        cmd = f"{cmd} -k {test_name}"
    return RepoCheck(
        kind=kind, command=cmd, target=target, grounded=True,
        artifact=f"a test `{test_name}` in `{target}` exercising `{sym}`",
        test_name=test_name,
        baseline_assertion=f"on the CURRENT code `{test_name}` is RED (the prediction is unrepresented).",
        negative_control=f"shuffle/remove the '{axis or 'broken'}' structure → `{test_name}` must FAIL — "
                         f"proving it tests the axis, not noise.",
        success_condition=f"`{cmd}` passes WITH `{test_name}` green AND the rest of the suite still green.",
        implementation_hint=f"in `{component}`, make the broken assumption false, then satisfy `{test_name}`.",
        pass_condition=f"`{test_name}` goes GREEN and the existing suite still passes",
        fail_baseline="the prediction is unrepresented or red in the repo today",
        note="grounded: the repo settles this bet — run the command, do not let the engine self-grade.")


def compile_world_test(claim: str, axis: str = "", repo=None, repo_signals: Optional[Dict] = None,
                       kind: str = "") -> RepoCheck:
    """Compile a claim into a repo check. With a real `repo` (grounding.RepoContext) the check is a full
    ARTIFACT CONTRACT (command + target + test id + baseline + negative control + success + hint) and
    grounded; otherwise a clearly-flagged placeholder is returned. `repo_signals` overrides commands."""
    k = kind or _pick_kind(axis, claim)
    if repo is not None and getattr(repo, "grounded", False):
        grounded = _grounded_check(k, repo, claim, axis)
        if grounded is not None:
            return grounded
    sig = {"test_cmd": "pytest -q", "type_cmd": "mypy .", "bench_cmd": "python bench.py",
           "build_cmd": "make build", **(repo_signals or {})}
    cmd_t, pass_c, fail_b = _PLACEHOLDER[k]
    # An idea that breaks NO axis has no counterexample to construct — keep the bare placeholder so a
    # non-falsifiable / inside-the-box claim does NOT inherit a full contract (that would be self-fooling).
    if not axis:
        return RepoCheck(kind=k, command=cmd_t.format(**sig), pass_condition=pass_c, fail_baseline=fail_b,
                         grounded=False,
                         note="NOT grounded and no broken axis — no constructed counterexample exists; this is a "
                              "SPEC only. Break an axis (and/or pass grounding.probe) to make it falsifiable.")
    # CONSTRUCTED COUNTEREXAMPLE: with no project repo (an abstract / mathematical claim) the world-test is
    # still a real falsification artifact — a self-contained property test on a constructed instance where the
    # box family must fail. We emit the FULL contract for it (so the claim is genuinely falsifiable), but keep
    # grounded=False so verifiability stays HUMAN — the engine never claims to have AUTO-settled it.
    test_name = f"test_{_slug(axis)}_{_slug(claim)}"
    cmd = cmd_t.format(**sig)
    if "pytest" in cmd:
        cmd = f"{cmd} -k {test_name}"
    return RepoCheck(kind=k, command=cmd, pass_condition=pass_c, fail_baseline=fail_b, grounded=False,
                     target="a new standalone property test (constructed counterexample) — no project repo needed",
                     test_name=test_name,
                     baseline_assertion=f"on the CONSTRUCTED instance the box family is wrong / unrepresented for '{axis or 'the broken axis'}'.",
                     negative_control=f"remove or scramble the constructed '{axis or 'broken'}' structure → `{test_name}` must FAIL "
                                      f"(proving it tests the axis, not noise).",
                     success_condition=f"`{test_name}` passes: the candidate WINS on the constructed instance where the box family fails.",
                     implementation_hint="build the minimal instance where the broken assumption is FALSE, then encode the "
                                         "prediction as a property/metamorphic test on it.",
                     note="NOT grounded against a project repo (HUMAN-class): this is a CONSTRUCTED COUNTEREXAMPLE the "
                          "person must build and run — a real falsification artifact, but the engine does NOT claim to "
                          "have settled it. Pass grounding.probe(repo_path) to AUTO-settle it instead.")
