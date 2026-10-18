"""online_llm — hosted models: Claude (official Anthropic SDK) and the OpenAI-compatible APIs (OpenAI, Gemini,
OpenRouter, Mistral, DeepSeek, Groq).

What an online model can and cannot do for the divergent phase. The prompt-level techniques of `llm_divergence`
(anti-mode, persona calls, verbalized probabilities, denial, intent → development, novelty rejection) work with
ANY model, so they run online too. The SAMPLER levers mostly do not:
  • current Claude models (Opus 5.5 / 5, Sonnet 5.5 / 5, Haiku 5.5, Fable) reject temperature / top_p / top_k with a
    400 — depth is steered by `effort` instead; only older models (Opus 4.6, Sonnet 4.6, Haiku 4.5, …) still take
    them, and only those get them;
  • OpenAI chat models take temperature / top_p / seed; reasoning models reject temperature, which the provider
    learns from the first 400 and stops sending;
  • base models, raw completion and truncation samplers (min_p, top_k, …) are local-only (see `local_llm`).
Each provider declares what it honours (`sampler_controls`), and the search reports it, so a run never claims a
hot/cool sampling split the provider did not perform.

The Anthropic SDK is an OPTIONAL dependency (`pip install anthropic`, or the `claude` extra), imported only when a
Claude provider makes its first call — the library itself stays zero-dependency. Credentials are resolved by the
SDK (ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN, or an `ant auth login` profile). OpenAI-compatible APIs read their key
from the provider's env var (OPENAI_API_KEY, GEMINI_API_KEY, …).
"""
from __future__ import annotations
import json
from typing import Dict, List, Mapping, Optional, Tuple

from .llm import LLMProvider
from .local_llm import OpenAICompatibleLLMProvider

DEFAULT_CLAUDE_MODEL = "claude-opus-5-5"

# Models that still accept temperature / top_p / top_k. Every newer model rejects non-default values with a 400.
_CLAUDE_SAMPLING_PREFIXES = ("claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5", "claude-opus-4-5",
                             "claude-sonnet-4-5", "claude-opus-4-1", "claude-opus-4-0", "claude-sonnet-4-0",
                             "claude-3")
# Models that accept the server-side refusal fallback (`fallbacks: "default"`, beta server-side-fallback-2026-07-01).
_CLAUDE_FALLBACK_MODELS = frozenset({"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"})
_FALLBACK_BETA = "server-side-fallback-2026-07-01"
_CLAUDE_SAMPLERS = frozenset({"temperature", "top_p", "top_k"})

# name → (base_url, API-key env var) for the OpenAI-compatible hosted APIs.
ONLINE_OPENAI_COMPATIBLE: Dict[str, Tuple[str, str]] = {
    "openai": ("https://api.openai.com/v1", "OPENAI_API_KEY"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "GEMINI_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "mistral": ("https://api.mistral.ai/v1", "MISTRAL_API_KEY"),
    "deepseek": ("https://api.deepseek.com/v1", "DEEPSEEK_API_KEY"),
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY"),
}


def online_provider(name: str, model: str, **kwargs) -> OpenAICompatibleLLMProvider:
    """An OpenAI-compatible hosted provider by preset name (see ONLINE_OPENAI_COMPATIBLE)."""
    try:
        base_url, key_env = ONLINE_OPENAI_COMPATIBLE[name]
    except KeyError:
        raise ValueError(f"unknown online API {name!r}; known: {', '.join(sorted(ONLINE_OPENAI_COMPATIBLE))}")
    return OpenAICompatibleLLMProvider(model, base_url, api_key_env=key_env, online=True, **kwargs)


class ClaudeRefusal(RuntimeError):
    """The whole fallback chain declined the request (stop_reason == "refusal")."""


def _is_sdk_error(error: BaseException) -> bool:
    """True for the Anthropic SDK's own exceptions (auth, rate limit, 4xx/5xx, network, timeouts)."""
    return type(error).__module__.split(".")[0] == "anthropic"


def _claude_takes_sampling(model: str) -> bool:
    return any(model.startswith(prefix) for prefix in _CLAUDE_SAMPLING_PREFIXES)


class AnthropicLLMProvider(LLMProvider):
    """Claude through the official Anthropic SDK (Messages API).

    • `effort` ("low" … "max") sets `output_config.effort`, the depth control on current models (Opus 5.5 defaults
      to "medium"); None leaves the model default.
    • `fallbacks=None` (auto) enables the server-side refusal fallback on the models that support it; False
      disables it. A request the whole chain refuses becomes a discarded `{"_error": …}` sample, never an exception.
    • temperature / top_p / top_k are sent (temperature clamped to Claude's [0, 1]) only to models that still take
      them; for every other model they are reported in `ignored_options` and `sampler_controls` is empty.
    • `client` injects a pre-built SDK client (tests, proxies, Bedrock/Vertex clients with the same surface)."""
    supports_roles = True

    def __init__(self, model: str = DEFAULT_CLAUDE_MODEL, *, max_tokens: int = 16000, effort: Optional[str] = None,
                 fallbacks: Optional[bool] = None, timeout: float = 600.0, client=None,
                 options: Optional[Mapping] = None):
        self.model = str(model or DEFAULT_CLAUDE_MODEL).strip()
        self.max_tokens = int(max_tokens)
        self.effort = effort
        self.fallbacks = (self.model in _CLAUDE_FALLBACK_MODELS) if fallbacks is None else bool(fallbacks)
        self.timeout = float(timeout)
        self.options = dict(options or {})
        self._client = client
        self.last_error = ""
        self.ignored_options: set = set()

    @property
    def sampler_controls(self) -> frozenset:
        return _CLAUDE_SAMPLERS if _claude_takes_sampling(self.model) else frozenset()

    @property
    def supports_sampling(self) -> bool:
        return "temperature" in self.sampler_controls

    def _sdk(self):
        if self._client is None:
            import anthropic                       # optional dependency, imported on first use only
            self._client = anthropic.Anthropic(timeout=self.timeout)
        return self._client

    def _request_kwargs(self, prompt: str, system: str, temperature: float, sampling: Dict) -> Dict:
        kwargs: Dict = {"model": self.model, "max_tokens": self.max_tokens,
                        "messages": [{"role": "user", "content": prompt}]}
        if system:
            kwargs["system"] = system
        if self.effort:
            kwargs["output_config"] = {"effort": self.effort}
        wanted = {"temperature": min(1.0, max(0.0, float(temperature))), **sampling}
        extra = {k: v for k, v in wanted.items() if k in self.sampler_controls and v is not None}
        self.ignored_options |= {k for k, v in wanted.items() if v is not None and k not in extra}
        if extra:
            kwargs["extra_body"] = extra
        return kwargs

    def _text(self, response) -> str:
        if getattr(response, "stop_reason", None) == "refusal":
            details = getattr(response, "stop_details", None)
            raise ClaudeRefusal(f"refused ({getattr(details, 'category', None) or 'no category'})")
        return "".join(getattr(b, "text", "") for b in (response.content or []) if getattr(b, "type", "") == "text")

    def complete(self, prompt: str, *, system: str = "", temperature: float = 0.8, n: int = 1,
                 **sampling) -> List[str]:
        sampling.pop("role", None)
        sampling.pop("seed", None)                 # the Messages API has no seed
        sampling = {**self.options, **sampling}
        out: List[str] = []
        for _ in range(max(1, int(n))):
            try:
                client = self._sdk()
                kwargs = self._request_kwargs(prompt, system, temperature, sampling)
                if self.fallbacks:
                    response = client.beta.messages.create(betas=[_FALLBACK_BETA], fallbacks="default", **kwargs)
                else:
                    response = client.messages.create(**kwargs)
                out.append(self._text(response))
            except ImportError:
                self.last_error = "the Anthropic SDK is not installed: pip install anthropic"
                out.append(json.dumps({"_error": self.last_error}))
            except Exception as e:
                if not (isinstance(e, ClaudeRefusal) or _is_sdk_error(e)):
                    raise                          # a bug, not a provider failure: never swallow it
                self.last_error = f"{type(e).__name__}: {e}"
                out.append(json.dumps({"_error": self.last_error}))
        return out


def online_from_spec(scheme: str, model: str) -> Optional[LLMProvider]:
    """`claude:` / `anthropic:` → AnthropicLLMProvider (empty model → the default Claude model); a preset name from
    ONLINE_OPENAI_COMPATIBLE → that hosted API. None for any other scheme."""
    if scheme in ("claude", "anthropic"):
        return AnthropicLLMProvider(model or DEFAULT_CLAUDE_MODEL)
    if scheme in ONLINE_OPENAI_COMPATIBLE and model:
        return online_provider(scheme, model)
    return None
