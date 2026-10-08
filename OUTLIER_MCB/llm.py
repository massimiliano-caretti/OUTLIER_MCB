"""llm — a stdlib-only LLM provider protocol + lightweight JSON validation for the LLM-in-the-loop engine.

The library never hard-depends on any model SDK: a provider is just something with `.complete(...)`. Two
implementations ship — `CallableLLMProvider` (wrap any Python callable, e.g. an Anthropic/OpenAI client or a
deterministic fake for tests) and `SubprocessLLMProvider` (pipe the prompt to any CLI on stdin, read stdout).
Without a provider the whole library behaves exactly as before; the LLM loop is opt-in.

LLM output is UNTRUSTED, so it is always validated against a tiny stdlib JSON schema (no jsonschema dep): a
completion that is not valid JSON, or a candidate missing required fields, is DISCARDED with a recorded
reason — never crashes the loop.
"""
from __future__ import annotations
import json
import os
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple


class LLMProvider:
    """Protocol: `complete(prompt, *, system="", temperature=0.8, n=1) -> list[str]` returns up to `n`
    candidate completions. Subclass or duck-type it."""
    def complete(self, prompt: str, *, system: str = "", temperature: float = 0.8, n: int = 1) -> List[str]:
        raise NotImplementedError


class CallableLLMProvider(LLMProvider):
    """Wrap any callable. `fn(prompt)` may return a single string OR a list of strings (a batch of samples).
    A scripted fake can hold internal state and return the next batch per call — perfect for offline tests."""
    def __init__(self, fn: Callable[[str], object]):
        self.fn = fn

    def _wants_n(self) -> bool:
        """True iff fn cannot be called with the prompt alone but can with (prompt, n)."""
        import inspect
        try:
            sig = inspect.signature(self.fn)
        except (TypeError, ValueError):             # builtins / C callables without a signature: prompt only
            return False
        try:
            sig.bind("p")
            return False
        except TypeError:
            pass
        try:
            sig.bind("p", 1)
            return True
        except TypeError:
            return False

    def complete(self, prompt: str, *, system: str = "", temperature: float = 0.8, n: int = 1) -> List[str]:
        full = (system + "\n\n" + prompt) if system else prompt
        if self._wants_n():
            out = self.fn(full, n)        # callables that want the sample count
        else:
            # Decided by SIGNATURE, not by catching TypeError: a TypeError raised INSIDE fn (a real bug) used to
            # trigger a second call fn(full, n) — consuming a stateful fake's next batch twice and masking the
            # original error with a misleading "takes 1 positional argument" one.
            out = self.fn(full)
        if isinstance(out, str):
            return [out]
        return [str(x) for x in (out or [])]


class SubprocessLLMProvider(LLMProvider):
    """Run a CLI `command`, pipe the prompt to its stdin, read its stdout as the completion. n>1 reruns it.

    SECURITY (§1): the command is NEVER run through a shell. It is tokenised with `shlex.split` and executed
    as an argv list, and shell operators (`;`, `|`, `&&`, redirection, `$(...)` …) are refused — so an LLM
    CLI invocation cannot smuggle in a second command. Pass extra args inline (`"my-llm --model x"`); for a
    real pipeline, wrap it in your own script and point the command at that script.
    """
    def __init__(self, command: str, timeout: int = 120, allow_shell_operators: bool = False):
        self.command = command
        self.timeout = timeout
        from .runner import CommandRunner
        self._runner = CommandRunner(allow_shell_operators=allow_shell_operators, default_timeout=timeout)

    def complete(self, prompt: str, *, system: str = "", temperature: float = 0.8, n: int = 1) -> List[str]:
        full = (system + "\n\n" + prompt) if system else prompt
        out = []
        for _ in range(max(1, n)):
            r = self._runner.run(self.command, input=full, timeout=self.timeout)
            if r.error and not r.stdout:
                out.append(json.dumps({"_error": r.error}))
            else:
                out.append(r.stdout)
        return out


# ── GENERATIVITY: the process-wide resolvable default LLM (the engine's own diagnosis of its missing axis) ──
# Without a provider the engine only RECOMBINES pre-written pack assumptions — it cannot produce content it was
# never given. Symmetric to embeddings.set_default_embedder, the LLM is now a process-wide resolvable default:
# one `set_default_llm(provider)` (or OUTLIER_MCB_LLM=subprocess:<cmd>) lets every generative entrypoint draw
# CONTENT from a model, while the external settlement (RED→GREEN, prior-art gate) still decides what survives —
# so generation never becomes ungrounded noise. Unset ⇒ None ⇒ the deterministic template path, unchanged: the
# library never spawns a model on its own.
_DEFAULT_LLM: Optional[LLMProvider] = None


def set_default_llm(provider: Optional[LLMProvider]) -> None:
    """Register the process-wide default LLM provider (a content SOURCE for GENERATIVITY). Pass None to reset to
    the template-only default. Programmatic registration always wins over the env var."""
    global _DEFAULT_LLM
    _DEFAULT_LLM = provider


def reset_default_llm() -> None:
    """Forget any registered default LLM (back to env-resolved, else template-only). Mainly for tests."""
    set_default_llm(None)


_ENV_VAR_LLM = "OUTLIER_MCB_LLM"
_ENV_LLM_CACHE: Dict[str, Optional[LLMProvider]] = {}


def _llm_from_spec(spec: str) -> Optional[LLMProvider]:
    """Build the provider a spec names, or None for 'no LLM (template path)'. Recognised:
      '' / 'none'                → None (deterministic template path)
      'subprocess:<command>'     → SubprocessLLMProvider(<command>)  (no shell; operators refused)
    An unknown scheme resolves to None (never a silent wrong model)."""
    key = spec.lower()
    if not spec or key == "none":
        return None
    if key.startswith("subprocess:"):
        command = spec.split(":", 1)[1].strip()
        return SubprocessLLMProvider(command) if command else None
    return None


def _llm_from_env() -> Optional[LLMProvider]:
    """Resolve OUTLIER_MCB_LLM, opt-in and CACHED by spec (a subprocess provider is built once, not per call).
    Unset ⇒ None ⇒ template path (determinism by default preserved)."""
    spec = os.environ.get(_ENV_VAR_LLM, "").strip()
    if not spec or spec.lower() == "none":
        return None
    if spec not in _ENV_LLM_CACHE:
        _ENV_LLM_CACHE[spec] = _llm_from_spec(spec)
    return _ENV_LLM_CACHE[spec]


def default_llm() -> Optional[LLMProvider]:
    """The resolved default LLM: a programmatic registration if set, else the env-configured provider, else None
    (the template-only path). Generative entrypoints call this when their `llm` argument is omitted."""
    if _DEFAULT_LLM is not None:
        return _DEFAULT_LLM
    return _llm_from_env()


# ── the structured-candidate schema (validated, untrusted input) ──
CANDIDATE_SCHEMA = {
    "required": ["name", "broken_assumption", "claim", "world_test_description"],
    "types": {"name": str, "broken_assumption": str, "operator": str, "claim": str,
              "why_standard_families_fail": str, "world_test_description": str,
              "test_patch": str, "implementation_patch": str, "novelty_rationale": str},
}


def validate_obj(obj: object, schema: Dict) -> Tuple[bool, List[str]]:
    """Minimal stdlib JSON-schema check: required keys present + declared types match. Returns (ok, errors)."""
    errors: List[str] = []
    if not isinstance(obj, dict):
        return False, ["not a JSON object"]
    for key in schema.get("required", []):
        if not str(obj.get(key, "")).strip():
            errors.append(f"missing/empty required field '{key}'")
    for key, typ in schema.get("types", {}).items():
        if key in obj and obj[key] is not None and not isinstance(obj[key], typ):
            errors.append(f"field '{key}' must be {typ.__name__}, got {type(obj[key]).__name__}")
    return (not errors), errors


_FENCE_RE = re.compile(r"```[ \t]*[A-Za-z0-9_+-]*[ \t]*\r?\n(.*?)```", re.DOTALL)
_MAX_DECODE_ATTEMPTS = 256


def _first_json_value(text: str):
    """Decode the first JSON value in `text` that is a CANDIDATE container: an object, or an array holding at
    least one object. Each '{' / '[' is tried IN ORDER with raw_decode — so an object that merely contains an
    array field is returned whole (not its inner list), and a prose citation like '[1]' before the JSON is
    skipped. Falls back to the first decodable container of any shape. None when nothing decodes."""
    dec = json.JSONDecoder()
    fallback = None
    attempts = 0
    for i, ch in enumerate(text):
        if ch not in "[{":
            continue
        attempts += 1
        if attempts > _MAX_DECODE_ATTEMPTS:          # bounded work on a huge, bracket-heavy completion
            break
        try:
            val, _end = dec.raw_decode(text, i)
        except ValueError:
            continue
        if isinstance(val, dict) or (isinstance(val, list) and any(isinstance(x, dict) for x in val)):
            return val
        if fallback is None:
            fallback = val
    return fallback


def _extract_json(text: str):
    """Pull the first JSON value out of an LLM completion (tolerant of code fences / surrounding prose).
    Fenced blocks (```json … ```) are tried first, then the whole completion."""
    t = (text or "").strip()
    fallback = None
    for block in _FENCE_RE.findall(t) + [t]:
        val = _first_json_value(block.strip())
        if isinstance(val, dict) or (isinstance(val, list) and any(isinstance(x, dict) for x in val)):
            return val
        if fallback is None and val is not None:
            fallback = val
    return fallback


@dataclass
class ParseResult:
    valid: List[Dict] = field(default_factory=list)
    discarded: List[Dict] = field(default_factory=list)    # [{raw, errors}]


def parse_candidates(text: str, schema: Dict = CANDIDATE_SCHEMA) -> ParseResult:
    """Parse one LLM completion into validated candidate dicts. Accepts a JSON array, a single object, or
    {"candidates": [...]}. Invalid candidates are DISCARDED with reasons — the loop never crashes on bad output."""
    res = ParseResult()
    data = _extract_json(text)
    if data is None:
        res.discarded.append({"raw": (text or "")[:160], "errors": ["not valid JSON"]})
        return res
    if isinstance(data, dict) and "candidates" in data and isinstance(data["candidates"], list):
        data = data["candidates"]
    items = data if isinstance(data, list) else [data]
    for it in items:
        ok, errs = validate_obj(it, schema)
        (res.valid if ok else res.discarded).append(it if ok else {"raw": str(it)[:160], "errors": errs})
    return res
