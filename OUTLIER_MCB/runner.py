"""runner — a conservative, stdlib-only command runner for the LLM loop.

The loop executes commands that are derived from UNTRUSTED LLM output (a CLI a user wired in, a pytest
invocation on a file path a model chose). `subprocess.run(..., shell=True)` on that is a command-injection
hazard: `pytest -q; touch hacked` would run the `touch`. This runner removes the shell entirely.

Rules (deliberately stricter than ordinary application code — see §1 of the brief):
  • Commands are executed as an argv `list[str]`; a shell is NEVER spawned (`shell=False` always).
  • A string command is tokenised with `shlex.split`, NOT handed to `/bin/sh`.
  • Shell metacharacters (`; | & > < ` $() && || newline …`) are REFUSED with `UnsafeCommandError`
    unless the caller explicitly opts into `allow_shell_operators=True` (the test/materialisation paths
    never do). This blocks pipes, redirection, chaining and substitution before anything runs.
  • Every run is bounded by a timeout; a timeout is reported as a result, never an unbounded hang.

Pure stdlib. No new runtime dependency. Used by `llm.SubprocessLLMProvider` and `llm_loop` materialisation.
"""
from __future__ import annotations
import shlex
import subprocess
from dataclasses import dataclass
from typing import List, Optional, Sequence, Union

# Characters that only have meaning to a shell. Their presence in a string command means the caller is
# (knowingly or not) relying on shell semantics we refuse to provide.
_SHELL_OPERATORS = (";", "|", "&", ">", "<", "`", "$(", "${", "&&", "||", "\n", "\r", "\t",
                    ">>", "2>", "<<", "$(", "*", "?", "~", "(", ")", "{", "}", "[", "]", "!", "#")

# A conservative subset actually worth blocking — globbing/braces are noisy, so we block the operators
# that enable injection, chaining, redirection and substitution. Kept narrow to avoid false positives on
# legitimate argv (e.g. a regex passed as one already-split token is fine; it is the *string* form we guard).
_INJECTION_OPERATORS = (";", "|", "&", ">", "<", "`", "$(", "${", "&&", "||", "\n", "\r", ">>", "2>", "<<")


class UnsafeCommandError(ValueError):
    """Raised when a string command contains shell operators and shell operators are not allowed."""


def contains_shell_operators(command: str) -> List[str]:
    """Return the shell operators found in a STRING command (empty list ⇒ safe to tokenise)."""
    return [op for op in _INJECTION_OPERATORS if op in command]


@dataclass
class CommandResult:
    argv: List[str]
    returncode: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    error: str = ""              # set when the process could not be launched at all

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out and not self.error

    @property
    def output(self) -> str:
        return (self.stdout + self.stderr)

    def tail(self, n: int = 8) -> str:
        return "\n".join(self.output.strip().splitlines()[-n:])


def to_argv(command: Union[str, Sequence[str]], *, allow_shell_operators: bool = False) -> List[str]:
    """Normalise a command into an argv list. A list is taken as-is (each element is one already-safe
    token); a string is `shlex.split`. Strings with shell operators raise unless explicitly allowed."""
    if isinstance(command, (list, tuple)):
        return [str(x) for x in command]
    if not isinstance(command, str):
        raise UnsafeCommandError(f"command must be str or list[str], got {type(command).__name__}")
    if not allow_shell_operators:
        bad = contains_shell_operators(command)
        if bad:
            raise UnsafeCommandError(f"shell operators are forbidden in command: {bad} in {command!r}")
    return shlex.split(command)


class CommandRunner:
    """Runs commands without a shell. The single execution path for the LLM loop's CLI/test/materialise calls.

    `allow_shell_operators=False` (the default, and the only value the test/materialise paths use) makes a
    command containing `;`, `|`, `>`, backticks, `$(...)`, `&&` etc. raise `UnsafeCommandError` before launch.
    """
    def __init__(self, *, allow_shell_operators: bool = False, default_timeout: int = 60):
        self.allow_shell_operators = allow_shell_operators
        self.default_timeout = default_timeout

    def run(self, command: Union[str, Sequence[str]], *, cwd: Optional[str] = None,
            timeout: Optional[int] = None, input: Optional[str] = None,
            env: Optional[dict] = None) -> CommandResult:
        timeout = self.default_timeout if timeout is None else timeout
        try:
            argv = to_argv(command, allow_shell_operators=self.allow_shell_operators)
        except UnsafeCommandError as e:
            return CommandResult(argv=[], returncode=126, error=str(e))
        if not argv:
            return CommandResult(argv=[], returncode=127, error="empty command")
        try:
            p = subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                               timeout=timeout, input=input, shell=False, env=env)
            return CommandResult(argv=argv, returncode=p.returncode, stdout=p.stdout or "", stderr=p.stderr or "")
        except subprocess.TimeoutExpired as e:
            out = (e.stdout or "") if isinstance(e.stdout, str) else ""
            err = (e.stderr or "") if isinstance(e.stderr, str) else ""
            return CommandResult(argv=argv, returncode=124, stdout=out, stderr=err, timed_out=True,
                                 error=f"timeout after {timeout}s")
        except (OSError, subprocess.SubprocessError) as e:
            return CommandResult(argv=argv, returncode=127, error=str(e))


# A module-level default for callers that don't need their own configured instance.
default_runner = CommandRunner()
