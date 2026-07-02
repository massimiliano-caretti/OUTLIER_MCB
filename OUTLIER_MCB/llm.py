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

    def complete(self, prompt: str, *, system: str = "", temperature: float = 0.8, n: int = 1) -> List[str]:
        full = (system + "\n\n" + prompt) if system else prompt
        try:
            out = self.fn(full)
        except TypeError:
            out = self.fn(full, n)        # callables that want the sample count
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


def _extract_json(text: str):
    """Pull the first JSON value out of an LLM completion (tolerant of code fences / surrounding prose)."""
    t = (text or "").strip()
    if "```" in t:                                  # strip a ```json fence if present
        parts = t.split("```")
        for p in parts:
            p = p.strip()
            if p.startswith(("[", "{")):
                t = p.lstrip("json").strip(); break
    for opener, closer in (("[", "]"), ("{", "}")):
        a, b = t.find(opener), t.rfind(closer)
        if a != -1 and b != -1 and b > a:
            try:
                return json.loads(t[a:b + 1])
            except json.JSONDecodeError:
                continue
    return None


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
