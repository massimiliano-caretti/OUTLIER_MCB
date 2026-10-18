"""local_llm — stdlib-only HTTP providers for LOCAL models (Ollama, llama.cpp server, vLLM, LM Studio).

Why a local model needs its own provider: the levers that measurably widen what a model proposes live in the
SAMPLER and in the CHOICE OF MODEL, and a CLI pipe (`SubprocessLLMProvider`) cannot reach them —
  • a hot divergent phase and a cool convergent phase need a real per-call temperature
    (Intent Factored Generation, Ahmed et al., ICML 2025 — arXiv:2506.09659);
  • base (non-aligned) models are markedly less mode-collapsed than their chat versions
    (West & Potts 2025 — arXiv:2505.00047), so the divergent phase should be able to run on a BASE model in raw
    completion mode while the convergent phase formats JSON with the instruct model;
  • truncation samplers (min_p, top_k, top_n_sigma …) keep high temperatures coherent. They are passed through
    when set and never on by default: the evidence for min_p in particular is disputed
    (Nguyen et al., ICLR 2025 vs Schaeffer et al., arXiv:2506.13681), so the server's defaults stay in charge.

Every provider keeps the library protocol `complete(prompt, *, system, temperature, n) -> list[str]` and accepts
extra sampling keywords (`role`, `seed`, `min_p`, `top_p`, `top_k`, `max_tokens`, …) that `llm.call_llm` forwards
only to providers able to take them. `n` samples are drawn as n INDEPENDENT requests (local servers commonly
ignore `n`), each with its own seed when a seed is given, so the samples cannot silently be n copies of one.

Transport failures never raise into the search loop: like the subprocess provider, a failed sample becomes a
`{"_error": …}` JSON string, which the candidate parser discards with a recorded reason (and `last_error` keeps
the cause for the caller).
"""
from __future__ import annotations
import json
import os
import re
import urllib.error
import urllib.request
from typing import Callable, Dict, List, Mapping, Optional

from .llm import LLMProvider, call_llm

DEFAULT_OLLAMA_HOST = "http://localhost:11434"
_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)

# Ollama `options` keys a caller may set (anything else is reported in `ignored_options`, never sent — an unknown
# option is a silent no-op or an error depending on the server version, neither of which is what the caller meant).
_OLLAMA_OPTIONS = frozenset({
    "seed", "top_k", "top_p", "min_p", "typical_p", "repeat_penalty", "repeat_last_n", "presence_penalty",
    "frequency_penalty", "num_predict", "num_ctx", "stop", "mirostat", "mirostat_tau", "mirostat_eta"})
# top-level sampling fields an OpenAI-compatible LOCAL server accepts beyond the OpenAI set (llama.cpp / vLLM).
_OPENAI_FIELDS = frozenset({
    "seed", "top_p", "max_tokens", "stop", "presence_penalty", "frequency_penalty",
    "min_p", "top_k", "top_n_sigma", "typical_p", "repeat_penalty"})


def strip_reasoning(text: str) -> str:
    """Drop `<think>…</think>` blocks a reasoning model may inline in its answer (they are not the answer, and
    a JSON candidate hidden after a long chain of thought must still be found by the parser)."""
    return _THINK_BLOCK_RE.sub("", text or "").strip()


def _post_json(url: str, payload: Dict, *, timeout: float, headers: Optional[Mapping[str, str]] = None) -> Dict:
    """POST `payload` as JSON and decode the JSON reply. Raises OSError/ValueError on transport or decode errors;
    an HTTP error body is surfaced in the message (servers explain the problem there)."""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": "application/json", **dict(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise OSError(f"HTTP {e.code} from {url}: {detail}") from e


def _sample_seed(seed, i: int):
    """The seed of the i-th independent sample: distinct per sample, so n samples are not n copies."""
    return None if seed is None else int(seed) + i


class _HTTPProvider(LLMProvider):
    """Shared request loop: n independent samples, seeds spread per sample, failures recorded, never raised."""
    supports_sampling = True          # tells the search loop it can drive temperature / role per call

    def __init__(self, model: str, *, completion: bool = False, timeout: float = 300.0,
                 options: Optional[Mapping] = None, max_tokens: Optional[int] = None):
        if not str(model or "").strip():
            raise ValueError("a model name is required")
        self.model = str(model).strip()
        self.completion = bool(completion)
        self.timeout = float(timeout)
        self.options = dict(options or {})        # per-provider sampling defaults; per-call keywords win
        self.max_tokens = max_tokens
        self.last_error = ""
        self.ignored_options: set = set()

    def complete(self, prompt: str, *, system: str = "", temperature: float = 0.8, n: int = 1,
                 **sampling) -> List[str]:
        sampling.pop("role", None)                # routing is the RoleRoutedLLM's job, not the transport's
        merged = {**self.options, **{k: v for k, v in sampling.items() if v is not None}}
        if self.max_tokens is not None:
            merged.setdefault("max_tokens", self.max_tokens)
        seed = merged.pop("seed", None)
        out: List[str] = []
        for i in range(max(1, int(n))):
            try:
                out.append(strip_reasoning(self._request(prompt, system, temperature, _sample_seed(seed, i), merged)))
            except (OSError, ValueError, KeyError, IndexError, TypeError) as e:
                self.last_error = f"{type(e).__name__}: {e}"
                out.append(json.dumps({"_error": self.last_error}))
        return out

    def _request(self, prompt: str, system: str, temperature: float, seed, sampling: Dict) -> str:
        raise NotImplementedError


class OllamaLLMProvider(_HTTPProvider):
    """Ollama's native API. Chat mode uses /api/chat (the model's template, system message separate); completion
    mode uses /api/generate with `raw: true` — no template at all, which is how a BASE model must be prompted.

    `think=False` (default) asks reasoning models to answer directly, so tokens go to the answer the engine parses;
    models without a reasoning mode accept `think: false` too. `think=None` omits the field (server default)."""

    def __init__(self, model: str, host: Optional[str] = None, *, completion: bool = False,
                 think: Optional[bool] = False, timeout: float = 300.0, options: Optional[Mapping] = None,
                 max_tokens: Optional[int] = None, keep_alive: Optional[str] = None):
        super().__init__(model, completion=completion, timeout=timeout, options=options, max_tokens=max_tokens)
        self.host = (host or os.environ.get("OLLAMA_HOST") or DEFAULT_OLLAMA_HOST).rstrip("/")
        if "://" not in self.host:
            self.host = "http://" + self.host
        self.think = think
        self.keep_alive = keep_alive

    def _options(self, temperature: float, seed, sampling: Dict) -> Dict:
        opts: Dict = {"temperature": float(temperature)}
        if seed is not None:
            opts["seed"] = seed
        for key, value in sampling.items():
            key = "num_predict" if key == "max_tokens" else key
            if key in _OLLAMA_OPTIONS:
                opts[key] = value
            else:
                self.ignored_options.add(key)
        return opts

    def _request(self, prompt: str, system: str, temperature: float, seed, sampling: Dict) -> str:
        payload: Dict = {"model": self.model, "stream": False, "options": self._options(temperature, seed, sampling)}
        if self.keep_alive is not None:
            payload["keep_alive"] = self.keep_alive
        if self.completion:
            payload.update(prompt=(system + "\n\n" + prompt) if system else prompt, raw=True)
            return str(_post_json(self.host + "/api/generate", payload, timeout=self.timeout)["response"])
        msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
        payload["messages"] = msgs
        if self.think is not None:
            payload["think"] = bool(self.think)
        return str(_post_json(self.host + "/api/chat", payload, timeout=self.timeout)["message"]["content"])


class OpenAICompatibleLLMProvider(_HTTPProvider):
    """Any OpenAI-compatible server (llama.cpp `llama-server`, vLLM, LM Studio, Ollama's /v1). Chat mode uses
    /chat/completions; completion mode uses /completions (raw text, for base models). Local-server samplers
    (min_p, top_k, top_n_sigma, …) are sent as top-level fields only when set. `api_key` defaults to the
    OUTLIER_MCB_LLM_API_KEY env var; local servers usually need none."""

    def __init__(self, model: str, base_url: str, *, completion: bool = False, api_key: Optional[str] = None,
                 timeout: float = 300.0, options: Optional[Mapping] = None, max_tokens: Optional[int] = None):
        super().__init__(model, completion=completion, timeout=timeout, options=options, max_tokens=max_tokens)
        if not str(base_url or "").strip():
            raise ValueError("a base_url is required (e.g. http://localhost:8080/v1)")
        self.base_url = str(base_url).strip().rstrip("/")
        self.api_key = api_key if api_key is not None else os.environ.get("OUTLIER_MCB_LLM_API_KEY", "")

    def _request(self, prompt: str, system: str, temperature: float, seed, sampling: Dict) -> str:
        payload: Dict = {"model": self.model, "temperature": float(temperature), "stream": False}
        if seed is not None:
            payload["seed"] = seed
        for key, value in sampling.items():
            if key in _OPENAI_FIELDS:
                payload[key] = value
            else:
                self.ignored_options.add(key)
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        if self.completion:
            payload["prompt"] = (system + "\n\n" + prompt) if system else prompt
            data = _post_json(self.base_url + "/completions", payload, timeout=self.timeout, headers=headers)
            return str(data["choices"][0]["text"])
        payload["messages"] = (([{"role": "system", "content": system}] if system else [])
                               + [{"role": "user", "content": prompt}])
        data = _post_json(self.base_url + "/chat/completions", payload, timeout=self.timeout, headers=headers)
        return str(data["choices"][0]["message"].get("content") or "")


class RoleRoutedLLM(LLMProvider):
    """Route each call to a provider by its `role` keyword — e.g. a BASE model in raw completion mode for the
    divergent phase and the instruct model for the convergent (JSON) phase:

        RoleRoutedLLM(OllamaLLMProvider("qwen3:8b"), diverge=OllamaLLMProvider("qwen3:8b-base", completion=True))

    Roles the search uses: "diverge", "converge", "mode", "repair". A role without its own provider (or a call
    without a role) goes to `default`."""
    supports_sampling = True

    def __init__(self, default: LLMProvider, **by_role: LLMProvider):
        if default is None:
            raise ValueError("RoleRoutedLLM needs a default provider")
        self.default = default
        self.by_role = {k: v for k, v in by_role.items() if v is not None}

    def provider_for(self, role: Optional[str]) -> LLMProvider:
        return self.by_role.get(role or "", self.default)

    def complete(self, prompt: str, *, system: str = "", temperature: float = 0.8, n: int = 1,
                 role: Optional[str] = None, **sampling) -> List[str]:
        return call_llm(self.provider_for(role), prompt, system=system, temperature=temperature, n=n,
                        role=role, **sampling)


# ── spec strings (OUTLIER_MCB_LLM / OUTLIER_MCB_LLM_DIVERGE / OUTLIER_MCB_EMBEDDER) ──
def _split_at(rest: str):
    """'<model>@<location>' → (model, location or None). Model names may contain ':' (qwen3:8b) but not '@'."""
    model, sep, location = rest.rpartition("@")
    return (model.strip(), location.strip() or None) if sep else (rest.strip(), None)


def provider_from_spec(spec: str) -> Optional[LLMProvider]:
    """Build an HTTP provider from a spec, or None when the scheme is not an HTTP one. Recognised:
      ollama:<model>[@<host>]           chat mode (instruct model)
      ollama-raw:<model>[@<host>]       raw completion mode (base model)
      openai:<model>@<base_url>         OpenAI-compatible chat
      openai-raw:<model>@<base_url>     OpenAI-compatible /completions (base model)
    A malformed spec (no model, or openai without a base_url) resolves to None — never a silent wrong model."""
    scheme, sep, rest = str(spec or "").partition(":")
    if not sep:
        return None
    scheme = scheme.strip().lower()
    model, location = _split_at(rest)
    if not model:
        return None
    if scheme in ("ollama", "ollama-raw"):
        return OllamaLLMProvider(model, location, completion=scheme == "ollama-raw")
    if scheme in ("openai", "openai-raw"):
        if not location:
            return None
        return OpenAICompatibleLLMProvider(model, location, completion=scheme == "openai-raw")
    return None


def ollama_embed_fn(model: str, host: Optional[str] = None, timeout: float = 120.0) -> Callable[[str], List[float]]:
    """An embedding function backed by Ollama's /api/embed (e.g. nomic-embed-text, bge-m3) — wrap it in
    embeddings.CallableEmbedder to give every novelty / diversity distance real semantics."""
    base = (host or os.environ.get("OLLAMA_HOST") or DEFAULT_OLLAMA_HOST).rstrip("/")
    if "://" not in base:
        base = "http://" + base

    def embed(text: str) -> List[float]:
        data = _post_json(base + "/api/embed", {"model": model, "input": [str(text)]}, timeout=timeout)
        return [float(x) for x in data["embeddings"][0]]
    return embed
