"""local_llm — stdlib-only HTTP providers for LOCAL models (Ollama, llama.cpp server, vLLM, LM Studio) and for
OpenAI-compatible ONLINE APIs (OpenAI, Gemini, OpenRouter, Mistral, DeepSeek, Groq — see `online_llm`).

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
only to providers able to take them. Each provider DECLARES the sampler controls it honours (`sampler_controls`) so
the search knows which levers are real: measured on Ollama 0.34, `min_p` is honoured and `top_n_sigma` is silently
ignored, so it is not declared there. A control an API rejects at run time (HTTP 400 naming it — e.g. temperature on
OpenAI reasoning models) is dropped, remembered in `rejected_params`, and the request is retried once without it.
`n` samples are drawn as n INDEPENDENT requests (local servers commonly ignore `n`), each with its own seed when a
seed is given, so the samples cannot silently be n copies of one.

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
# the sampling fields the OpenAI API itself accepts (and therefore every online OpenAI-compatible API, at most).
_OPENAI_ONLINE_FIELDS = frozenset({"seed", "top_p", "max_tokens", "stop", "presence_penalty", "frequency_penalty"})
# … plus the samplers a LOCAL OpenAI-compatible server accepts as top-level fields (llama.cpp / vLLM).
_OPENAI_FIELDS = _OPENAI_ONLINE_FIELDS | frozenset({"min_p", "top_k", "top_n_sigma", "typical_p", "repeat_penalty"})


def strip_reasoning(text: str) -> str:
    """Drop `<think>…</think>` blocks a reasoning model may inline in its answer (they are not the answer, and
    a JSON candidate hidden after a long chain of thought must still be found by the parser)."""
    return _THINK_BLOCK_RE.sub("", text or "").strip()


class HTTPStatusError(OSError):
    """A non-2xx reply; `status` and `body` let a provider react to a rejected parameter."""

    def __init__(self, url: str, status: int, body: str):
        super().__init__(f"HTTP {status} from {url}: {body[:300]}")
        self.status, self.body = status, body


def _post_json(url: str, payload: Dict, *, timeout: float, headers: Optional[Mapping[str, str]] = None) -> Dict:
    """POST `payload` as JSON and decode the JSON reply. Raises OSError/ValueError on transport or decode errors;
    an HTTP error raises HTTPStatusError carrying the body (servers explain the problem there)."""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": "application/json", **dict(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise HTTPStatusError(url, e.code, e.read().decode("utf-8", "replace")[:2000]) from e


def _sample_seed(seed, i: int):
    """The seed of the i-th independent sample: distinct per sample, so n samples are not n copies."""
    return None if seed is None else int(seed) + i


class _HTTPProvider(LLMProvider):
    """Shared request loop: n independent samples, seeds spread per sample, failures recorded, never raised."""
    supports_roles = True             # accepts role/seed keywords and reports what it honours
    _controls: frozenset = frozenset()

    @property
    def sampler_controls(self) -> frozenset:
        """The sampling keywords this provider actually puts on the wire (minus any the API rejected)."""
        return frozenset(self._controls) - self.rejected_params

    @property
    def supports_sampling(self) -> bool:
        return "temperature" in self.sampler_controls

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
        self.rejected_params: set = set()           # controls the API refused at run time (never sent again)

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
        self._controls = frozenset({"temperature", "max_tokens"} | _OLLAMA_OPTIONS)
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
    """Any OpenAI-compatible server: local (llama.cpp `llama-server`, vLLM, LM Studio, Ollama's /v1) or online
    (OpenAI, Gemini, OpenRouter, Mistral, DeepSeek, Groq — `online_llm.online_provider`). Chat mode uses
    /chat/completions; completion mode uses /completions (raw text, for base models).

    `online=False` declares the local-server samplers (min_p, top_k, top_n_sigma, …) as honoured; `online=True`
    declares only the OpenAI set (temperature, top_p, seed, penalties). The key comes from `api_key`, else the env
    var `api_key_env` (default OUTLIER_MCB_LLM_API_KEY); a provider that names a key variable which is unset fails
    each sample with a clear error instead of sending an anonymous request."""

    def __init__(self, model: str, base_url: str, *, completion: bool = False, api_key: Optional[str] = None,
                 api_key_env: Optional[str] = None, online: bool = False, timeout: float = 300.0,
                 options: Optional[Mapping] = None, max_tokens: Optional[int] = None):
        super().__init__(model, completion=completion, timeout=timeout, options=options, max_tokens=max_tokens)
        if not str(base_url or "").strip():
            raise ValueError("a base_url is required (e.g. http://localhost:8080/v1)")
        self.base_url = str(base_url).strip().rstrip("/")
        self.online = bool(online)
        self.api_key_env = api_key_env
        env = api_key_env or "OUTLIER_MCB_LLM_API_KEY"
        self.api_key = api_key if api_key is not None else os.environ.get(env, "")
        self._controls = frozenset({"temperature"} | (_OPENAI_ONLINE_FIELDS if online else _OPENAI_FIELDS))
        self._max_tokens_field = "max_tokens"

    def _request(self, prompt: str, system: str, temperature: float, seed, sampling: Dict) -> str:
        if self.api_key_env and not self.api_key:
            raise ValueError(f"no API key: set {self.api_key_env}")
        payload: Dict = {"model": self.model, "stream": False}
        candidates = {"temperature": float(temperature), "seed": seed, **sampling}
        for key, value in candidates.items():
            if value is None:
                continue
            if key in self.sampler_controls:
                payload[self._max_tokens_field if key == "max_tokens" else key] = value
            elif key not in self.rejected_params:
                self.ignored_options.add(key)
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        if self.completion:
            payload["prompt"] = (system + "\n\n" + prompt) if system else prompt
            data = self._post_adaptive("/completions", payload, headers)
            return str(data["choices"][0]["text"])
        payload["messages"] = (([{"role": "system", "content": system}] if system else [])
                               + [{"role": "user", "content": prompt}])
        data = self._post_adaptive("/chat/completions", payload, headers)
        return str(data["choices"][0]["message"].get("content") or "")

    def _post_adaptive(self, path: str, payload: Dict, headers: Dict) -> Dict:
        """POST, and on a 400 that names a sampling field we sent, drop it for good and retry once. OpenAI's newer
        models also rename `max_tokens` to `max_completion_tokens`; that rename is learned the same way."""
        try:
            return _post_json(self.base_url + path, payload, timeout=self.timeout, headers=headers)
        except HTTPStatusError as e:
            if e.status != 400:
                raise
            body = e.body.lower()
            if "max_tokens" in payload and "max_completion_tokens" in body:
                self._max_tokens_field = "max_completion_tokens"
                payload["max_completion_tokens"] = payload.pop("max_tokens")
                return _post_json(self.base_url + path, payload, timeout=self.timeout, headers=headers)
            # OpenAI-style errors quote the parameter: "Unsupported parameter: 'temperature' …", "param": "…"
            refused = [k for k in payload if k in self._controls
                       and any(q + k + q in body for q in ("'", '"', "`"))]
            if not refused:
                raise
            for key in refused:
                self.rejected_params.add(key)
                payload.pop(key, None)
            return _post_json(self.base_url + path, payload, timeout=self.timeout, headers=headers)


class RoleRoutedLLM(LLMProvider):
    """Route each call to a provider by its `role` keyword — e.g. a BASE model in raw completion mode for the
    divergent phase and the instruct model for the convergent (JSON) phase:

        RoleRoutedLLM(OllamaLLMProvider("qwen3:8b"), diverge=OllamaLLMProvider("qwen3:8b-base", completion=True))

    Roles the search uses: "diverge", "converge", "mode", "repair". A role without its own provider (or a call
    without a role) goes to `default`."""
    supports_roles = True

    def __init__(self, default: LLMProvider, **by_role: LLMProvider):
        if default is None:
            raise ValueError("RoleRoutedLLM needs a default provider")
        self.default = default
        self.by_role = {k: v for k, v in by_role.items() if v is not None}

    def provider_for(self, role: Optional[str]) -> LLMProvider:
        return self.by_role.get(role or "", self.default)

    def sampler_controls_for(self, role: Optional[str]) -> frozenset:
        from .llm import sampler_controls
        return sampler_controls(self.provider_for(role))

    @property
    def supports_sampling(self) -> bool:
        return "temperature" in self.sampler_controls_for("diverge")

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
    """Build a provider from a spec, or None when the scheme is unknown. Recognised:
      ollama:<model>[@<host>]           local, chat mode (instruct model)
      ollama-raw:<model>[@<host>]       local, raw completion mode (base model)
      openai:<model>@<base_url>         OpenAI-compatible server at base_url (local samplers declared)
      openai-raw:<model>@<base_url>     OpenAI-compatible /completions (base model)
      openai:<model>                    the OpenAI API itself (OPENAI_API_KEY)
      claude:[<model>] / anthropic:…    Claude via the Anthropic SDK (default model when omitted)
      gemini: / openrouter: / mistral: / deepseek: / groq:<model>   hosted OpenAI-compatible APIs
    A malformed spec (no model, or openai-raw without a base_url) resolves to None — never a silent wrong model."""
    scheme, sep, rest = str(spec or "").partition(":")
    if not sep:
        return None
    scheme = scheme.strip().lower()
    model, location = _split_at(rest)
    if scheme in ("claude", "anthropic"):
        from .online_llm import online_from_spec
        return online_from_spec(scheme, model)
    if not model:
        return None
    if scheme in ("ollama", "ollama-raw"):
        return OllamaLLMProvider(model, location, completion=scheme == "ollama-raw")
    if scheme == "openai" and not location:
        from .online_llm import online_provider
        return online_provider("openai", model)
    if scheme in ("openai", "openai-raw"):
        if not location:
            return None
        return OpenAICompatibleLLMProvider(model, location, completion=scheme == "openai-raw")
    from .online_llm import online_from_spec
    return online_from_spec(scheme, model)


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
