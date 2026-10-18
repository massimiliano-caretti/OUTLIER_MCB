"""Online models (Claude via the Anthropic SDK, OpenAI-compatible hosted APIs) and the provider-aware sampler profile.

Pinned behaviours:
  • Claude requests carry model / max_tokens / system / effort and the server-side refusal fallback on the models
    that support it; temperature / top_p / top_k reach ONLY the older models that still accept them;
  • a refusal, an SDK error or a missing SDK becomes a discarded error sample; a bug in our own code is not swallowed;
  • hosted OpenAI-compatible APIs read their own key, refuse to send an anonymous request, and learn a rejected
    sampling parameter (temperature on reasoning models) or the max_completion_tokens rename from the first 400;
  • the divergent phase runs for online providers too, and its sampler profile keeps only what each provider
    honours — with the report saying so.
The SDK is replaced by an injected fake client, so these tests need neither the `anthropic` package nor a network.
"""
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import OUTLIER_MCB as gsl
from OUTLIER_MCB.llm import sampler_controls
from OUTLIER_MCB.llm_divergence import DivergenceConfig, resolve_sampling, AUTO_DIVERGE_SAMPLING
from OUTLIER_MCB.local_llm import OllamaLLMProvider, OpenAICompatibleLLMProvider, RoleRoutedLLM
from OUTLIER_MCB.online_llm import AnthropicLLMProvider, ClaudeRefusal, online_provider


# ── a fake Anthropic SDK client with the same call surface (messages.create / beta.messages.create) ──
def _message(text="hello", stop_reason="end_turn", category=None):
    return SimpleNamespace(stop_reason=stop_reason, stop_details=SimpleNamespace(category=category),
                           content=[SimpleNamespace(type="thinking", thinking=""),
                                    SimpleNamespace(type="text", text=text)])


class FakeClaudeClient:
    def __init__(self, reply=None):
        self.calls = []
        self.reply = reply or (lambda kwargs: _message("ok:" + kwargs["messages"][0]["content"]))
        outer = self

        class _Messages:
            def __init__(self, beta):
                self.beta = beta

            def create(self, **kwargs):
                outer.calls.append({"beta": self.beta, **kwargs})
                return outer.reply(kwargs)
        self.messages = _Messages(False)
        self.beta = SimpleNamespace(messages=_Messages(True))


def test_claude_request_shape_on_a_current_model():
    client = FakeClaudeClient()
    prov = AnthropicLLMProvider("claude-opus-5-5", effort="high", client=client)
    out = prov.complete("hi", system="sys", temperature=1.0, n=2, role="diverge", seed=3, min_p=0.05)
    assert out == ["ok:hi", "ok:hi"] and len(client.calls) == 2              # n independent requests
    call = client.calls[0]
    assert call["beta"] and call["betas"] == ["server-side-fallback-2026-07-01"] and call["fallbacks"] == "default"
    assert call["model"] == "claude-opus-5-5" and call["max_tokens"] == 16000 and call["system"] == "sys"
    assert call["output_config"] == {"effort": "high"}
    assert "extra_body" not in call and "temperature" not in call             # current models reject samplers
    assert prov.sampler_controls == frozenset() and not prov.supports_sampling
    assert {"temperature", "min_p"} <= prov.ignored_options


def test_claude_legacy_model_gets_sampling_and_no_fallback_beta():
    client = FakeClaudeClient()
    prov = AnthropicLLMProvider("claude-opus-4-6", client=client)
    prov.complete("hi", temperature=1.4, top_k=50)
    call = client.calls[0]
    assert not call["beta"] and "fallbacks" not in call
    assert call["extra_body"] == {"temperature": 1.0, "top_k": 50}             # clamped to Claude's [0, 1]
    assert prov.supports_sampling


def test_claude_refusal_and_sdk_errors_become_error_samples_but_bugs_propagate():
    refusing = AnthropicLLMProvider(client=FakeClaudeClient(lambda kw: _message(stop_reason="refusal",
                                                                                 category="cyber")))
    out = refusing.complete("x")
    assert "_error" in json.loads(out[0]) and "cyber" in refusing.last_error

    SDKError = type("RateLimitError", (Exception,), {"__module__": "anthropic._exceptions"})

    def rate_limited(kwargs):
        raise SDKError("429")
    limited = AnthropicLLMProvider(client=FakeClaudeClient(rate_limited))
    assert "_error" in json.loads(limited.complete("x")[0]) and "RateLimitError" in limited.last_error

    def buggy(kwargs):
        raise KeyError("our own bug")
    with pytest.raises(KeyError):
        AnthropicLLMProvider(client=FakeClaudeClient(buggy)).complete("x")
    assert issubclass(ClaudeRefusal, RuntimeError)


def test_missing_sdk_is_a_clear_error_sample(monkeypatch):
    monkeypatch.setitem(sys.modules, "anthropic", None)                       # import anthropic → ImportError
    prov = AnthropicLLMProvider()
    out = prov.complete("x")
    assert "_error" in json.loads(out[0]) and "pip install anthropic" in prov.last_error


def test_specs_reach_every_online_api():
    from OUTLIER_MCB.llm import _llm_from_spec
    claude = _llm_from_spec("claude:")
    assert isinstance(claude, AnthropicLLMProvider) and claude.model == "claude-opus-5-5"
    assert _llm_from_spec("anthropic:claude-sonnet-5-5").model == "claude-sonnet-5-5"
    for scheme, host in (("openai", "api.openai.com"), ("gemini", "generativelanguage.googleapis.com"),
                         ("openrouter", "openrouter.ai"), ("mistral", "api.mistral.ai"),
                         ("deepseek", "api.deepseek.com"), ("groq", "api.groq.com")):
        prov = _llm_from_spec(f"{scheme}:some-model")
        assert isinstance(prov, OpenAICompatibleLLMProvider) and host in prov.base_url and prov.online
        assert "min_p" not in prov.sampler_controls and "top_p" in prov.sampler_controls
    with pytest.raises(ValueError):
        online_provider("nowhere", "m")


# ── hosted OpenAI-compatible APIs against a real local HTTP server ──
class _OpenAIish(BaseHTTPRequestHandler):
    requests = []
    reject = ()                       # parameters the "API" refuses with a 400 naming them

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])).decode())
        type(self).requests.append({"payload": payload, "auth": self.headers.get("Authorization")})
        bad = [k for k in type(self).reject if k in payload]
        if bad:
            body = {"error": {"message": f"Unsupported parameter: '{bad[0]}' is not supported with this model.",
                              "param": bad[0]}}
            if bad[0] == "max_tokens":
                body["error"]["message"] += " Use 'max_completion_tokens' instead."
            code = 400
        else:
            body, code = {"choices": [{"message": {"content": "fine"}}]}, 200
        raw = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args):
        pass


@pytest.fixture
def api():
    handler = type("H", (_OpenAIish,), {"requests": [], "reject": ()})
    httpd = HTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield handler, f"http://127.0.0.1:{httpd.server_port}/v1"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_hosted_api_needs_its_key_and_sends_it(api, monkeypatch):
    handler, url = api
    monkeypatch.delenv("FAKE_PROVIDER_KEY", raising=False)
    prov = OpenAICompatibleLLMProvider("m", url, api_key_env="FAKE_PROVIDER_KEY", online=True)
    out = prov.complete("q")
    assert "FAKE_PROVIDER_KEY" in json.loads(out[0])["_error"] and handler.requests == []   # nothing sent
    monkeypatch.setenv("FAKE_PROVIDER_KEY", "sk-test")
    prov = OpenAICompatibleLLMProvider("m", url, api_key_env="FAKE_PROVIDER_KEY", online=True)
    assert prov.complete("q", min_p=0.1, top_p=0.9) == ["fine"]
    sent = handler.requests[0]
    assert sent["auth"] == "Bearer sk-test" and sent["payload"]["top_p"] == 0.9
    assert "min_p" not in sent["payload"] and "min_p" in prov.ignored_options          # local-only sampler


def test_rejected_temperature_is_learned_and_never_resent(api):
    handler, url = api
    handler.reject = ("temperature",)
    prov = OpenAICompatibleLLMProvider("reasoner", url, api_key="k", online=True)
    assert prov.complete("q", temperature=1.0) == ["fine"]                   # 400 → dropped → retried
    assert prov.rejected_params == {"temperature"} and not prov.supports_sampling
    assert prov.complete("q", temperature=0.2) == ["fine"]
    assert "temperature" not in handler.requests[-1]["payload"] and len(handler.requests) == 3


def test_max_completion_tokens_rename_is_learned(api):
    handler, url = api
    handler.reject = ("max_tokens",)
    prov = OpenAICompatibleLLMProvider("reasoner", url, api_key="k", online=True, max_tokens=500)
    assert prov.complete("q") == ["fine"] and prov.complete("q") == ["fine"]
    last = handler.requests[-1]["payload"]
    assert last.get("max_completion_tokens") == 500 and "max_tokens" not in last


# ── the sampler profile is provider-aware ──
def test_auto_sampler_profile_keeps_only_what_each_provider_honours():
    cfg = DivergenceConfig()
    _c, local = resolve_sampling(cfg, OllamaLLMProvider("m"))
    assert local["diverge"]["options"] == AUTO_DIVERGE_SAMPLING and local["diverge"]["temperature_honoured"]
    _c, openai = resolve_sampling(cfg, online_provider("openai", "gpt"))
    assert openai["diverge"]["options"] == {"top_p": 0.95} and openai["diverge"]["not_honoured"] == ["top_k"]
    resolved, claude = resolve_sampling(cfg, AnthropicLLMProvider(client=FakeClaudeClient()))
    assert claude["diverge"]["options"] == {} and not claude["diverge"]["temperature_honoured"]
    assert resolved.diverge_sampling == {} and resolved.converge_sampling == {}
    explicit, _r = resolve_sampling(DivergenceConfig(diverge_sampling={"min_p": 0.05}), OllamaLLMProvider("m"))
    assert explicit.diverge_sampling == {"min_p": 0.05}                    # an explicit choice is never second-guessed
    routed = RoleRoutedLLM(AnthropicLLMProvider(client=FakeClaudeClient()), diverge=OllamaLLMProvider("base"))
    assert sampler_controls(routed, "diverge") >= {"temperature", "top_p"}
    assert sampler_controls(routed, "converge") == frozenset()


def test_divergent_phase_runs_on_claude_with_prompt_level_techniques_only():
    """No temperature on current Claude models — the search still elicits the mode, runs persona intents and
    develops them, and says plainly that the hot/cool split was not applied."""
    def reply(kwargs):
        prompt = kwargs["messages"][0]["content"]
        if "MOST LIKELY give" in prompt:
            return _message("ANSWER: use a token bucket per client || p=0.6")
        if "INTENT:" in prompt and "OBSERVATION:" in prompt:
            return _message("OBSERVATION: x\n"
                            "INTENT: per_client || let tenants trade unused quota in a market || p=0.03")
        cand = {"name": "quota market", "broken_assumption": "per_client", "claim": "tenants trade unused quota",
                "world_test_description": "a test only a market passes"}
        return _message(json.dumps([cand]))
    client = FakeClaudeClient(reply)
    res = gsl.llm_openended_search("invent a new rate limiter", AnthropicLLMProvider(client=client),
                                   budget=1, samples_per_round=1)
    dv = res.divergence
    assert dv["enabled"] and dv["mode_source"] == "elicited" and dv["intents_selected"] == 1
    assert not dv["sampler"]["diverge"]["temperature_honoured"]
    assert "prompt-level divergence only" in res.markdown()
    assert all("extra_body" not in c for c in client.calls) and [c.name for c in res.candidates] == ["quota market"]
