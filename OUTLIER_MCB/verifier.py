"""verifier — actually RUN the check, read the result, settle the bet. This closes the loop.

Until now the engine emitted a command but never ran it, so a bet stayed OPEN forever and "falsification"
was a reminder. `run_check` executes the grounded command (bounded subprocess, captured output) and
returns a `Verdict` that states plainly what WAS verified, what was NOT, and why the idea is alive or
dead. `verify` then settles the bet in the ledger — whose policy re-weights future generation, so a
real run actually changes what the engine proposes next.

Honest scope: running the gate proves the gate flips (or not), nothing more — it does not prove the idea
is the best or genuinely useful. The Verdict says so explicitly. Execution is opt-in and only ever runs
the command compiled from the user's own project.

Collaborators: repo_world.RepoCheck (what to run), economy.Ledger/Bet (what to settle).
"""
from __future__ import annotations
import shlex
import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass
class Verdict:
    command: str
    ran: bool
    passed: Optional[bool]          # None ⇒ nothing executed (ungrounded or could not run)
    returncode: Optional[int]
    alive: bool                     # does the idea survive this verification?
    what_was_verified: str
    what_was_not: str
    why: str
    output_tail: str = ""
    def markdown(self) -> str:
        head = "ALIVE" if self.alive else ("DEAD" if self.ran else "UNVERIFIED")
        lines = [f"### Verdict — {head}  (`{self.command}`)",
                 f"- **verified:** {self.what_was_verified}",
                 f"- **NOT verified:** {self.what_was_not}",
                 f"- **why:** {self.why}"]
        if self.output_tail:
            lines.append(f"- **output (tail):**\n```\n{self.output_tail.strip()[-400:]}\n```")
        return "\n".join(lines)


def verifiability_class(check) -> str:
    """Be honest about the Achilles heel: only a FRACTION of ideas can be settled by running a test.

    AUTO  — a grounded, full-contract repo check exists; the engine can settle this bet by execution.
    HUMAN — no executable check is possible (an architectural / conceptual claim); the world must be
            BUILT and judged by a person. The engine must NEVER claim to have 'verified' a HUMAN idea.
    """
    if check is not None and getattr(check, "grounded", False) and getattr(check, "is_full_contract", False):
        return "AUTO"
    return "HUMAN"


def run_check(check, cwd: str = ".", timeout: int = 120) -> Verdict:
    """Execute a grounded RepoCheck and report the result. Never runs an ungrounded (placeholder) check."""
    if not getattr(check, "grounded", False) or not check.command:
        return Verdict(check.command, ran=False, passed=None, returncode=None, alive=False,
                       what_was_verified="nothing — the check is not grounded (no runnable command).",
                       what_was_not="everything: novelty, correctness, usefulness.",
                       why="ungrounded: pass a real repo (grounding.probe) so a command exists to run.")
    try:
        proc = subprocess.run(shlex.split(check.command), cwd=cwd, capture_output=True,
                              text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return Verdict(check.command, ran=True, passed=False, returncode=None, alive=False,
                       what_was_verified=f"the gate started but TIMED OUT after {timeout}s.",
                       what_was_not="whether it would eventually pass.",
                       why="timeout — treat as not-yet-passing; narrow the check or raise the timeout.")
    except (FileNotFoundError, OSError) as exc:
        return Verdict(check.command, ran=False, passed=None, returncode=None, alive=False,
                       what_was_verified="nothing — the command could not be launched.",
                       what_was_not="everything.", why=f"could not run `{check.command}`: {exc}")
    passed = proc.returncode == 0
    return Verdict(
        command=check.command, ran=True, passed=passed, returncode=proc.returncode, alive=passed,
        what_was_verified=f"the gate `{check.command}` {'PASSED' if passed else 'FAILED'} (exit {proc.returncode}).",
        what_was_not="whether the idea is the BEST or genuinely useful — only that the repo's gate flips.",
        why=(check.pass_condition if passed else "the gate did not flip → the bet is settled LOST."),
        output_tail=(proc.stdout + proc.stderr)[-600:],
    )


def materialized(check, repo_root: str = ".") -> bool:
    """Has the assistant actually written the named test? (Does test_name appear in the repo source?)"""
    from pathlib import Path
    if not getattr(check, "test_name", ""):
        return False
    root = Path(repo_root)
    return any(check.test_name in f.read_text(errors="ignore")
               for f in root.rglob("*.py") if "__pycache__" not in str(f))
# (validate_artifact_contract lives in artifacts.py — the canonical, single definition)


@dataclass
class RedGreen:
    status: str            # NOT_MATERIALIZED | RED | GREEN | ERROR
    test_exists: bool
    green: bool
    why: str
    def markdown(self) -> str:
        return f"**red-green: {self.status}** (test_exists={self.test_exists}, green={self.green}) — {self.why}"


def verify_red_green(check, cwd: str = ".", timeout: int = 120) -> RedGreen:
    """Honest verification: confirm the NEW named test EXISTS and is GREEN — not merely that the suite
    passes. Until the assistant materializes the test, the engine refuses to claim verification."""
    if not getattr(check, "test_name", ""):
        return RedGreen("ERROR", False, False, "the check has no test_name — not a full artifact contract.")
    if not materialized(check, cwd):
        return RedGreen("NOT_MATERIALIZED", False, False,
                        f"`{check.test_name}` is not in the repo yet — write the test first; the engine will "
                        f"NOT claim red-green until it exists.")
    v = run_check(check, cwd=cwd, timeout=timeout)     # command targets `-k test_name`, so this is the NEW test
    if v.returncode == 5:                              # pytest: no tests collected ⇒ the named test is absent
        return RedGreen("NOT_MATERIALIZED", False, False, "pytest collected no test by that name.")
    if v.passed:
        return RedGreen("GREEN", True, True, "the named test exists and passes — the prediction is encoded and met.")
    return RedGreen("RED", True, False, "the named test exists but FAILS — the idea has not yet been realized.")


def verify(bet, check, ledger=None, cwd: str = ".", timeout: int = 120) -> Verdict:
    """Run the check AND settle the bet: on a real pass/fail the ledger records it, which re-weights the
    generation policy. This is the loop — run → read → settle → (re-rank next round)."""
    verdict = run_check(check, cwd=cwd, timeout=timeout)
    if ledger is not None and verdict.passed is not None:
        ledger.settle(bet, won=verdict.passed)
    return verdict
