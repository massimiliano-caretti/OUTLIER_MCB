"""The local-LLM divergence stack: sampling-aware providers, the divergent → convergent phase, and its wiring.

Each test pins one mechanism so that removing it turns the test RED:
  • the HTTP providers put temperature / seed / samplers / raw mode on the WIRE (checked against a real local
    HTTP server, not a mock of urllib) and never raise into the loop;
  • `call_llm` forwards sampling options only to providers that accept them (legacy providers are untouched);
  • the subprocess provider finally honours the temperature (argv placeholders + environment);
  • intents are parsed tolerantly, and selection rejects near-known / mode-echo / duplicate intents, prefers the
    verbalized tail and covers distinct assumptions, unoccupied niches first;
  • the search runs hot independent persona calls then cool convergent calls, denies the declared mode and the
    failure memory, records deaths, and leaves legacy providers on the exact previous path.
"""
import json
import os
import random
import stat
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import OUTLIER_MCB as gsl
from OUTLIER_MCB.llm import call_llm, CallableLLMProvider, SubprocessLLMProvider, _llm_from_spec
from OUTLIER_MCB.local_llm import (OllamaLLMProvider, OpenAICompatibleLLMProvider, RoleRoutedLLM,
                                   provider_from_spec, strip_reasoning)
from OUTLIER_MCB.llm_divergence import (DivergenceConfig, DenialSet, Intent, parse_intents, parse_mode_answers,
                                        resolve_divergence, select_intents, mean_pairwise_distance,
                                        niche_key)
from OUTLIER_MCB.mode_box import declare_mode


# ── a real local HTTP server: records every request, answers like Ollama / an OpenAI-compatible server ──
class _Recorder(BaseHTTPRequestHandler):
    requests = []
    reply = None                       # callable(path, payload) -> dict

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])).decode())
        type(self).requests.append({"path": self.path, "payload": payload,
                                    "auth": self.headers.get("Authorization")})
        body = json.dumps(type(self).reply(self.path, payload)).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def server():
    handler = type("Handler", (_Recorder,), {"requests": [], "reply": None})
    httpd = HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield handler, f"http://127.0.0.1:{httpd.server_port}"
    finally:
        httpd.shutdown()
        httpd.server_close()


def _ollama_reply(path, payload):
    if path == "/api/chat":
        content = "<think>hidden</think>chat:" + payload["messages"][-1]["content"]
        return {"message": {"role": "assistant", "content": content}}
    if path == "/api/generate":
        return {"response": "raw:" + payload["prompt"]}
    if path == "/api/embed":
        return {"embeddings": [[1.0, 0.0]] if "a" in payload["input"][0] else [[0.0, 1.0]]}
    raise AssertionError(path)


# ── providers on the wire ──
def test_ollama_chat_puts_temperature_seed_and_samplers_on_the_wire(server):
    handler, url = server
    handler.reply = staticmethod(_ollama_reply)
    prov = OllamaLLMProvider("qwen3:8b", url, options={"top_k": 40})
    out = prov.complete("hello", system="sys", temperature=1.3, n=3, seed=10, min_p=0.05, max_tokens=64,
                        role="diverge", bogus_knob=1)
    assert out == ["chat:hello"] * 3                                  # <think> stripped, 3 independent samples
    assert len(handler.requests) == 3 and {r["path"] for r in handler.requests} == {"/api/chat"}
    first = handler.requests[0]["payload"]
    assert first["model"] == "qwen3:8b" and first["stream"] is False and first["think"] is False
    assert first["messages"] == [{"role": "system", "content": "sys"}, {"role": "user", "content": "hello"}]
    assert first["options"] == {"temperature": 1.3, "seed": 10, "top_k": 40, "min_p": 0.05, "num_predict": 64}
    assert [r["payload"]["options"]["seed"] for r in handler.requests] == [10, 11, 12]   # distinct per sample
    assert prov.ignored_options == {"bogus_knob"}                     # reported, never sent


def test_ollama_raw_mode_prompts_a_base_model_without_template(server):
    handler, url = server
    handler.reply = staticmethod(_ollama_reply)
    prov = OllamaLLMProvider("qwen3:8b-base", url, completion=True)
    assert prov.complete("1.", system="List:", temperature=0.9) == ["raw:List:\n\n1."]
    req = handler.requests[0]
    assert req["path"] == "/api/generate" and req["payload"]["raw"] is True and "think" not in req["payload"]
    assert req["payload"]["options"] == {"temperature": 0.9}


def test_openai_compatible_chat_and_completion_wire_format(server):
    handler, url = server

    def reply(path, payload):
        if path.endswith("/chat/completions"):
            return {"choices": [{"message": {"content": "C:" + payload["messages"][-1]["content"]}}]}
        return {"choices": [{"text": "T:" + payload["prompt"]}]}
    handler.reply = staticmethod(reply)
    chat = OpenAICompatibleLLMProvider("m", url + "/v1", api_key="k")
    assert chat.complete("q", temperature=0.2, seed=3, top_n_sigma=1.0, min_p=0.1) == ["C:q"]
    p = handler.requests[0]
    assert p["path"] == "/v1/chat/completions" and p["auth"] == "Bearer k"
    assert p["payload"]["temperature"] == 0.2 and p["payload"]["seed"] == 3
    assert p["payload"]["top_n_sigma"] == 1.0 and p["payload"]["min_p"] == 0.1
    raw = OpenAICompatibleLLMProvider("m", url + "/v1", completion=True, api_key="")
    assert raw.complete("go") == ["T:go"]
    assert handler.requests[1]["path"] == "/v1/completions" and handler.requests[1]["auth"] is None


def test_transport_failure_is_an_error_sample_not_an_exception():
    prov = OllamaLLMProvider("m", "http://127.0.0.1:9", timeout=2)        # nothing listens on port 9
    out = prov.complete("x", n=2)
    assert len(out) == 2 and all("_error" in json.loads(o) for o in out)
    assert prov.last_error
    assert gsl.parse_candidates(out[0]).valid == []                        # discarded by the loop, never crashes
    res = gsl.llm_openended_search("invent a new rate limiter", RoleRoutedLLM(prov), budget=1, samples_per_round=1)
    assert res.provider_error and "provider error" in res.markdown() and res.to_dict()["provider_error"]


def test_ollama_embedder_spec_gives_semantic_distance_and_degrades_to_lexical(server, monkeypatch):
    from OUTLIER_MCB.embeddings import _build_from_spec, CallableEmbedder
    handler, url = server
    handler.reply = staticmethod(_ollama_reply)
    emb = _build_from_spec(f"ollama:nomic-embed-text@{url}")
    assert isinstance(emb, CallableEmbedder)
    assert emb.distance("a cat", "a dog") == 0.0 and emb.distance("a cat", "the moon") == 1.0
    assert _build_from_spec("ollama:nomic-embed-text@http://127.0.0.1:9") is None   # unreachable ⇒ lexical


def test_specs_resolve_to_the_right_provider_and_env_routes_the_divergent_role(monkeypatch):
    o = provider_from_spec("ollama:qwen3:8b@http://box:11434")
    assert isinstance(o, OllamaLLMProvider) and o.model == "qwen3:8b" and o.host == "http://box:11434"
    assert provider_from_spec("ollama-raw:qwen3:8b").completion is True
    oa = provider_from_spec("openai-raw:m@http://h:8080/v1")
    assert isinstance(oa, OpenAICompatibleLLMProvider) and oa.completion and oa.base_url == "http://h:8080/v1"
    for bad in ("openai-raw:m", "ollama:", "nope:x", "plain"):
        assert provider_from_spec(bad) is None
    assert isinstance(_llm_from_spec("ollama:qwen3:8b"), OllamaLLMProvider)
    gsl.reset_default_llm()
    monkeypatch.setenv("OUTLIER_MCB_LLM", "ollama:inst")
    monkeypatch.setenv("OUTLIER_MCB_LLM_DIVERGE", "ollama-raw:base")
    routed = gsl.default_llm()
    assert isinstance(routed, RoleRoutedLLM)
    assert routed.provider_for("diverge").model == "base" and routed.provider_for("diverge").completion
    assert routed.provider_for("converge").model == "inst" and routed.provider_for(None).model == "inst"
    assert gsl.default_llm() is routed                                      # cached per spec pair


def test_strip_reasoning_removes_inline_chain_of_thought():
    assert strip_reasoning("<think>a\nb</think>\n[1]") == "[1]"


# ── call_llm: sampling reaches only the providers that can take it ──
def test_call_llm_forwards_options_only_to_providers_that_accept_them():
    seen = {}

    class Legacy:
        def complete(self, prompt, *, system="", temperature=0.8, n=1):
            seen["legacy"] = temperature
            return ["ok"]

    class Aware:
        def complete(self, prompt, *, system="", temperature=0.8, n=1, **kw):
            seen["aware"] = (temperature, kw)
            return ["ok"]
    call_llm(Legacy(), "p", temperature=1.2, role="diverge", seed=1, min_p=None)
    call_llm(Aware(), "p", temperature=1.2, role="diverge", seed=1, min_p=None)
    assert seen["legacy"] == 1.2
    assert seen["aware"] == (1.2, {"role": "diverge", "seed": 1})          # None = unset, not sent


def test_role_routed_llm_dispatches_by_role():
    calls = []

    class P:
        supports_sampling = True

        def __init__(self, name):
            self.name = name

        def complete(self, prompt, *, system="", temperature=0.8, n=1, **kw):
            calls.append((self.name, temperature, kw.get("role")))
            return [self.name]
    r = RoleRoutedLLM(P("inst"), diverge=P("base"))
    assert r.complete("x", role="diverge", temperature=1.1) == ["base"]
    assert r.complete("x", role="converge", temperature=0.2) == ["inst"]
    assert r.complete("x") == ["inst"]
    assert calls[0] == ("base", 1.1, "diverge") and calls[1] == ("inst", 0.2, "converge")


def test_subprocess_provider_honours_temperature_via_placeholders_and_env():
    d = tempfile.mkdtemp()
    script = Path(d, "fake_llm.py")
    script.write_text("import os, sys\n"
                      "sys.stdin.read()\n"
                      "print(sys.argv[1], os.environ['OUTLIER_MCB_LLM_TEMPERATURE'], "
                      "os.environ['OUTLIER_MCB_LLM_ROLE'], os.environ.get('OUTLIER_MCB_LLM_SEED'), "
                      "os.environ.get('OUTLIER_MCB_LLM_MIN_P'))\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    prov = SubprocessLLMProvider(f"{sys.executable} {script} --temp={{temperature}}")
    out = call_llm(prov, "hi", temperature=1.25, n=2, role="diverge", seed=5, min_p=0.05)
    assert [o.split() for o in out] == [["--temp=1.25", "1.25", "diverge", "5", "0.05"],
                                        ["--temp=1.25", "1.25", "diverge", "6", "0.05"]]
    assert prov.complete("hi")[0].split() == ["--temp=0.8", "0.8", "None", "None"]   # role '' · no seed · no min_p


# ── parsing ──
def test_parse_intents_line_format_markdown_json_and_garbage():
    text = ("OBSERVATION: caches assume reads dominate\n"
            "1. **INTENT:** objective_is_given || price each request by its regret instead of its latency || p=0.04\n"
            "- INTENT: representation_is_fixed || store deltas between consecutive states, not states || p=7%\n"
            "INTENT: x || too short\n"
            "INTENT: decomposition_is_natural || merge the two stages into one streaming pass over the data\n"
            "INTENT: objective_is_given || price each request by its regret instead of its latency || p=0.04\n")
    its = parse_intents(text, persona="P")
    assert [i.assumption for i in its] == ["objective_is_given", "representation_is_fixed", "decomposition_is_natural"]
    assert [i.probability for i in its] == [0.04, 0.07, None] and all(i.persona == "P" for i in its)
    js = parse_intents('[{"assumption": "a", "mechanism": "do the thing very differently", "p": 0.2}]')
    assert len(js) == 1 and js[0].probability == 0.2
    assert parse_intents("no structure at all") == []
    answers, probs = parse_mode_answers("ANSWER: use an LRU cache || p=0.6\n2. ANSWER: add a CDN layer\njunk")
    assert answers == ["use an LRU cache", "add a CDN layer"] and probs == [0.6, None]


# ── selection ──
def _intent(a, m, p=None):
    return Intent(assumption=a, mechanism=m, probability=p)


def test_select_intents_rejects_near_known_mode_echo_and_duplicates():
    denial = DenialSet()
    denial.add("known family", "least recently used eviction cache")
    mode = declare_mode("speed up reads", ["put a redis cache in front of the database",
                                           "add a redis cache with time to live expiry"])
    its = [_intent("a1", "least recently used eviction cache", 0.01),                       # near known
           _intent("a2", "put a redis cache in front of the database tier", 0.02),          # mode echo
           _intent("a3", "route queries to replicas chosen by predicted contention", 0.03),
           _intent("a3", "route queries to replicas chosen by predicted contention", 0.03),  # duplicate
           _intent("a4", "precompute answers during idle power troughs of the datacenter", 0.05)]
    chosen = select_intents(its, denial, k=5, mode_map=mode)
    status = [i.status for i in its]
    assert status[0] == "REJECTED_NEAR_KNOWN" and status[1] == "REJECTED_MODE"
    assert status[3] == "REJECTED_DUPLICATE"
    assert [i.assumption for i in chosen] == ["a3", "a4"]


def test_select_intents_prefers_the_tail_and_covers_distinct_unoccupied_assumptions():
    its = [_intent("busy", "alpha mechanism with distinct wording one", 0.01),
           _intent("busy", "beta mechanism with other wording two", 0.02),
           _intent("free", "gamma approach using unrelated vocabulary three", 0.6),     # the model's own mode
           _intent("free", "delta approach using unrelated vocabulary four", 0.05),
           _intent("other", "epsilon idea built from fresh terms five", 0.08)]
    chosen = select_intents(its, DenialSet(), k=3, occupied_assumptions={"busy"})
    assert [i.assumption for i in chosen] == ["free", "other", "busy"]          # unoccupied niches first, one each
    assert chosen[0].mechanism.startswith("delta")                                  # tail (p=0.05) beats p=0.6
    assert {i.status for i in its if i not in chosen} == {"SURPLUS"}


class _TopicalEmbedder:
    """The distance profile measured on a CDN prompt with nomic-embed-text: the default answers are different KINDS of
    mechanism (0.43+ apart), every on-topic sentence sits 0.33–0.42 from them, a paraphrase sits below 0.25."""
    kind = "semantic"

    def distance(self, a, b):
        if a == b:
            return 0.0
        if "least recently used" in a.lower() and "least recently used" in b.lower():
            return 0.12                                              # a paraphrase of the LRU default
        return 0.45 if all("cache" in t.lower() for t in (a, b)) else 0.4


def test_mode_filter_keeps_new_mechanisms_when_the_defaults_are_far_apart():
    """Regression for the live CDN run: with a threshold derived from the closest pair of defaults (0.45 here), every
    on-topic intent (0.4) was branded NEAR_MODE. One variant threshold for the whole search keeps them."""
    from OUTLIER_MCB.llm_divergence import VARIANT_DISTANCE
    mode = declare_mode("invent a new caching strategy for a CDN",
                        ["hierarchical cache with edge nodes and regional hubs",
                         "a least recently used eviction policy for cache memory",
                         "time to live headers for cache freshness"])
    emb = _TopicalEmbedder()
    new = _intent("node_independent", "a global Lagrange multiplier prices storage across every server", 0.02)
    paraphrase = _intent("x", "evict the least recently used objects first when memory is full", 0.02)
    chosen = select_intents([new, paraphrase], DenialSet(), k=2, mode_map=mode, embedder=emb)
    assert chosen == [new] and paraphrase.status in ("REJECTED_MODE", "REJECTED_NEAR_KNOWN")
    assert DivergenceConfig().novelty_min_distance == VARIANT_DISTANCE


def test_request_words_are_not_a_reused_mechanism():
    """'rate limiter' in a default answer is the PROBLEM ("rate-limit API clients"), not a mechanism: an idea that
    names the problem must not be branded a component swap of that answer (it was, in the first live run)."""
    from OUTLIER_MCB.mode_box import mode_distance
    mode = declare_mode("invent a new way to rate-limit API clients",
                        ["Fixed window rate limiter", "Token bucket algorithm"])
    assert "rate limiter" not in mode.shared_surface()
    idea = "Adversarial-gradient rate limiter: throttle clients by the gradient of their error rate"
    assert mode_distance(idea, mode).verdict == "TAIL"
    assert mode_distance("token bucket per API client", mode).verdict in ("MODE_ECHO", "NEAR_MODE")


def test_naming_the_box_to_negate_it_is_not_reusing_it():
    """Live run: 'predator-prey dynamics replace fixed window counters' was branded a component swap of 'Fixed window
    rate limiter'. Words after a contrast cue (EN + IT) are what the idea leaves; a real variant still is NEAR_MODE."""
    from OUTLIER_MCB.mode_box import mode_distance
    mode = declare_mode("invent a new way to rate-limit API clients",
                        ["Fixed window rate limiter", "Token bucket algorithm"])
    for idea in ("Epoch-independent predator-prey dynamics replace fixed window counters with population cycles",
                 "instead of a token bucket, clients trade unused quota in an internal market",
                 "invece di una finestra fissa, cicli preda-predatore regolano la capacità"):
        assert mode_distance(idea, mode).verdict == "TAIL", idea
    assert mode_distance("a fixed window limiter with a larger window", mode).verdict == "NEAR_MODE"


def test_niche_key_maps_phrasing_onto_the_pack_assumption():
    known = ["time_windowed", "per_client"]
    assert niche_key("breaking time_windowed by enforcing decay", known) == "time_windowed"
    assert niche_key("  A NEW Hidden One ", known) == "a new hidden one"


def test_resolve_divergence_is_auto_on_only_for_sampling_aware_providers():
    class Aware:
        supports_sampling = True
    assert resolve_divergence(None, CallableLLMProvider(lambda p: "")) is None
    assert isinstance(resolve_divergence(None, Aware()), DivergenceConfig)
    assert resolve_divergence(False, Aware()) is None
    assert resolve_divergence({"diverge_calls": 2}, None).diverge_calls == 2
    with pytest.raises(ValueError):
        DivergenceConfig(personas=())


# ── the search, end to end, with a scripted sampling-aware model ──
_CAND_TEMPLATE = {"broken_assumption": "", "operator": "invert", "claim": "", "why_standard_families_fail": "x",
                  "world_test_description": "a test only the broken assumption passes"}


class ScriptedLocalModel:
    """A sampling-aware fake: answers the mode / diverge / converge roles like a local model would, and records
    every call (role, temperature, seed, prompt)."""
    supports_sampling = True

    def __init__(self, intents_per_call=None):
        self.calls = []
        self.intents_per_call = intents_per_call or [
            ["INTENT: time_windowed || charge each client by the variance it adds to the queue || p=0.03",
             "INTENT: per_client || use a token bucket for each client || p=0.5"],
            ["INTENT: per_client || let clients trade unused quota in a small internal market || p=0.04",
             "INTENT: time_windowed || charge each client by the variance it adds to the queue || p=0.03"],
            ["INTENT: fixed_budget || grant capacity from measured downstream slack every second || p=0.02"]]

    def complete(self, prompt, *, system="", temperature=0.8, n=1, role=None, seed=None, **kw):
        self.calls.append({"role": role, "temperature": temperature, "seed": seed, "prompt": prompt})
        if role == "mode":
            return ["ANSWER: use a token bucket per client || p=0.6\nANSWER: use a sliding window counter || p=0.3"]
        if role == "diverge":
            i = sum(1 for c in self.calls if c["role"] == "diverge") - 1
            return ["OBSERVATION: x\n" + "\n".join(self.intents_per_call[i % len(self.intents_per_call)])]
        mech = prompt.split("  mechanism: ", 1)[1].splitlines()[0] if "  mechanism: " in prompt else "fallback idea"
        cand = dict(_CAND_TEMPLATE, name=("idea " + mech)[:40], claim=mech,
                    broken_assumption=prompt.split("broken assumption: ", 1)[1].splitlines()[0]
                    if "broken assumption: " in prompt else "time_windowed")
        return [json.dumps([cand])] * max(1, n)


def test_divergent_search_runs_hot_persona_calls_then_cool_convergent_calls():
    model = ScriptedLocalModel()
    res = gsl.llm_openended_search("invent a new rate limiter", model, budget=3, samples_per_round=3,
                                   divergence=DivergenceConfig(denial_in_prompt=True))
    roles = [c["role"] for c in model.calls]
    assert roles[0] == "mode" and roles[1:4] == ["diverge"] * 3 and set(roles[4:]) == {"converge"}
    div_calls = [c for c in model.calls if c["role"] == "diverge"]
    conv_calls = [c for c in model.calls if c["role"] == "converge"]
    assert all(c["temperature"] == 1.0 for c in div_calls) and all(c["temperature"] == 0.2 for c in conv_calls)
    assert len({c["seed"] for c in div_calls}) == 3                              # independent samples
    personas = [c["prompt"].split("You are ", 1)[1].split(".", 1)[0] for c in div_calls]
    assert len(set(personas)) == 3                                               # a distinct lens per call
    # denial prompting: the model's own default answers and the known families are DO-NOT-USE constraints
    assert "use a token bucket per client" in div_calls[0]["prompt"] and "[known family]" in div_calls[0]["prompt"]
    dv = res.divergence
    assert dv["enabled"] and dv["mode_source"] == "elicited" and dv["intents_generated"] == 5
    assert dv["rejections"] == {"DUPLICATE": 1, "MODE": 1}             # the token-bucket variant + the repeat
    assert dv["intents_selected"] == 3 and len(conv_calls) == 3
    assert res.llm_call_count == 1 + 3 + 3
    assert all(c.evidence.get("intent") for c in res.candidates)                 # every candidate traces its intent
    assert ({c.evidence["intent"]["assumption"] for c in res.candidates}
            == {"time_windowed", "per_client", "fixed_budget"})
    d = res.to_dict()
    assert d["divergence"]["enabled"] and d["candidate_spread"] is not None
    assert "divergent phase" in res.markdown()


def test_every_intent_rejected_falls_back_to_a_cool_legacy_call():
    model = ScriptedLocalModel(intents_per_call=[["INTENT: per_client || use a token bucket per client || p=0.6"]])
    res = gsl.llm_openended_search("invent a new rate limiter", model, budget=2, samples_per_round=2,
                                   divergence=DivergenceConfig(denial_in_prompt=True))
    assert res.divergence["fallback_rounds"] == 1 and res.divergence["intents_selected"] == 0
    fallback = [c for c in model.calls if c["role"] == "converge"]
    assert len(fallback) == 1 and fallback[0]["temperature"] == 0.2
    assert "YOUR DEFAULT ANSWERS" in fallback[0]["prompt"]


def test_declared_mode_replaces_elicitation_and_is_denied():
    model = ScriptedLocalModel()
    res = gsl.llm_openended_search("invent a new rate limiter", model, budget=3, samples_per_round=3,
                                   mode=["leaky bucket queue per tenant", "fixed window counter in redis"],
                                   divergence=DivergenceConfig(denial_in_prompt=True))
    assert "mode" not in [c["role"] for c in model.calls]
    assert res.divergence["mode_source"] == "declared"
    assert "leaky bucket queue per tenant" in next(c for c in model.calls if c["role"] == "diverge")["prompt"]


def test_legacy_provider_keeps_the_exact_previous_path():
    prompts = []

    def fn(prompt):
        prompts.append(prompt)
        return json.dumps([dict(_CAND_TEMPLATE, name="legacy idea", claim="c", broken_assumption="time_windowed")])
    res = gsl.llm_openended_search("invent a new rate limiter", CallableLLMProvider(fn), budget=8, samples_per_round=4)
    assert res.llm_call_count == 2 and len(prompts) == 2 and res.divergence == {"enabled": False}
    assert "DEVELOP THIS INTENT" not in prompts[0] and "YOUR DEFAULT ANSWERS" not in prompts[0]


def test_failure_memory_is_denied_and_this_runs_deaths_are_recorded(tmp_path):
    from OUTLIER_MCB.failure_feedback import FailureStore
    from OUTLIER_MCB.pack import select_pack
    path = str(tmp_path / "mem.json")
    pack, _ = select_pack("invent a new rate limiter")
    store = FailureStore(path)
    store.record(pack.name, "auction slots to the highest bidder every tick", "INSIDE_THE_BOX", assumption="per_client")
    store.save()
    model = ScriptedLocalModel()
    gsl.llm_openended_search("invent a new rate limiter", model, budget=3, samples_per_round=3, memory=path,
                             divergence=DivergenceConfig(denial_in_prompt=True))
    assert "auction slots to the highest bidder every tick" in next(
        c for c in model.calls if c["role"] == "diverge")["prompt"]

    # a rebrand of a known family is recorded as a death in the persistent store
    rebrand = {"name": "token_bucket", "broken_assumption": "time_windowed",
               "claim": "a token bucket rate limiter", "world_test_description": "x"}
    res = gsl.llm_openended_search("design a rate limiter",
                                   CallableLLMProvider(lambda prompt: json.dumps([rebrand, rebrand])),
                                   budget=2, samples_per_round=2, memory=path)
    assert res.rebrand_count >= 1
    assert any(e["status"] == "DEAD_RENAMED" for e in FailureStore(path).entries(pack.name).values())


def test_candidate_echoing_the_declared_mode_is_rejected_and_remembered(tmp_path):
    from OUTLIER_MCB.failure_feedback import FailureStore
    path = str(tmp_path / "mem.json")
    echo = dict(_CAND_TEMPLATE, name="per tenant token bucket", claim="use a token bucket per tenant",
                broken_assumption="time_windowed")
    res = gsl.llm_openended_search("invent a new rate limiter", CallableLLMProvider(lambda p: json.dumps([echo])),
                                   budget=1, samples_per_round=1, mode=["use a token bucket per client"], memory=path)
    assert res.mode_echoes_rejected == 1 and not [c for c in res.candidates if c.name == echo["name"]]
    assert res.to_dict()["mode_echoes_rejected"] == 1
    statuses = {e["status"] for e in FailureStore(path).data.get(res.archive.pack.name, {}).values()}
    assert statuses & {"DEAD_MODE_ECHO", "DEAD_NEAR_MODE"}


def test_divergent_phase_widens_the_spread_of_a_mode_collapsed_model():
    """A/B on the SAME stochastic model (seeded): a tempered, mode-collapsed sampler over a fixed idea pool that
    honours explicit denials (so denial_in_prompt is switched on here — on qwen3.5:4b the A/B run found the
    opposite, which is why it is off by default). Legacy = one call per round; divergent = anti-mode + hot persona
    intents + denial + novelty rejection. The divergent phase must reach more DISTINCT ideas and a wider spread. This checks the
    mechanism does what it is designed to do on a model with these properties — it is not evidence about any
    real model (that is what the live check and an A/B on real prompts are for)."""
    pool = ["token bucket per client", "sliding window counter", "fixed window counter", "leaky bucket queue",
            "adaptive concurrency limit from latency gradient", "credit market between tenants",
            "variance priced admission control", "slack driven capacity grants", "proof of work for bursts",
            "reinforcement learned throttling policy"]
    weights = [0.40, 0.25, 0.15, 0.10, 0.04, 0.02, 0.015, 0.01, 0.0075, 0.0075]

    class Tempered:
        supports_sampling = True

        def __init__(self):
            self.rng = random.Random(1234)

        def _draw(self, prompt, temperature):
            denied = prompt.split("DO NOT USE", 1)[1] if "DO NOT USE" in prompt else ""
            allowed = [(i, w) for i, (idea, w) in enumerate(zip(pool, weights)) if idea not in denied]
            ws = [w ** (1.0 / max(temperature, 1e-3)) for _i, w in allowed]
            return pool[self.rng.choices([i for i, _w in allowed], weights=ws)[0]]

        def complete(self, prompt, *, system="", temperature=0.8, n=1, role=None, **kw):
            if role == "mode":
                return ["ANSWER: token bucket per client || p=0.4\nANSWER: sliding window counter || p=0.25"]
            if role == "diverge":
                ideas = {self._draw(prompt, temperature) for _ in range(5)}
                return ["\n".join(f"INTENT: a{pool.index(x)} || {x} as the core mechanism || p=0.05" for x in ideas)]
            idea = (prompt.split("  mechanism: ", 1)[1].split(" as the core", 1)[0] if "  mechanism: " in prompt
                    else self._draw(prompt, temperature))
            return [json.dumps([dict(_CAND_TEMPLATE, name=idea, claim=idea, broken_assumption="time_windowed")])
                    for _ in range(n)]

    legacy = gsl.llm_openended_search("invent a new rate limiter", Tempered(), budget=12, samples_per_round=4,
                                      divergence=False, max_per_assumption=99, max_per_cell=99)
    divergent = gsl.llm_openended_search("invent a new rate limiter", Tempered(), budget=12, samples_per_round=4,
                                         max_per_assumption=99, max_per_cell=99,
                                         divergence=DivergenceConfig(denial_in_prompt=True))
    distinct = lambda r: {c.name for c in r.candidates}
    assert len(distinct(divergent)) > len(distinct(legacy))
    assert not ({"token bucket per client", "sliding window counter"} & distinct(divergent))   # the mode is left
    assert divergent.candidate_spread() > legacy.candidate_spread()


def test_mean_pairwise_distance():
    assert mean_pairwise_distance(["only one"]) is None
    assert mean_pairwise_distance(["same words here", "same words here"]) == 0.0


def test_intents_without_the_assumption_field_are_kept():
    """A 4B local model wrote `INTENT: <mechanism> || p=…` on more than half its lines; they used to be dropped."""
    its = parse_intents("INTENT: make latency an explicit transaction fee rather than a rate limit || p=0.06\n"
                        "INTENT: per_client || tenants trade unused quota in a market || p=3%\n"
                        "INTENT: assign clients to specialized niches by their behaviour\n"
                        "INTENT: x || p=0.1")
    assert [(i.assumption, i.probability) for i in its] == [("", 0.06), ("per_client", 0.03), ("", None)]
    assert its[0].mechanism.startswith("make latency")


def test_by_default_the_defaults_are_filtered_not_listed():
    """The A/B run: naming the denied answers in the prompt pulled the ideas back toward them. By default they are
    kept out of every prompt and enforced by the filters only."""
    model = ScriptedLocalModel()
    res = gsl.llm_openended_search("invent a new rate limiter", model, budget=3, samples_per_round=3)
    prompts = [c["prompt"] for c in model.calls if c["role"] in ("diverge", "converge")]
    assert prompts and not any("use a token bucket per client" in p or "DO NOT USE" in p
                               or "YOUR DEFAULT ANSWERS" in p for p in prompts)
    assert res.divergence["rejections"].get("MODE") == 1                   # the token-bucket variant still dies
    assert not DivergenceConfig().verbalized_tail and not DivergenceConfig().denial_in_prompt


class _DriftingModel(ScriptedLocalModel):
    """Develops each intent into a default answer the first time, and correctly once told it drifted."""
    def complete(self, prompt, *, system="", temperature=0.8, n=1, role=None, seed=None, **kw):
        if role == "converge" and "  mechanism: " in prompt and "DRIFTED BACK" not in prompt:
            self.calls.append({"role": role, "temperature": temperature, "seed": seed, "prompt": prompt})
            cand = dict(_CAND_TEMPLATE, name="token bucket per client", claim="use a token bucket per client",
                        broken_assumption="time_windowed")
            return [json.dumps([cand])]
        return super().complete(prompt, system=system, temperature=temperature, n=n, role=role, seed=seed, **kw)


def test_a_development_that_drifts_into_the_mode_is_retried_once():
    model = _DriftingModel()
    res = gsl.llm_openended_search("invent a new rate limiter", model, budget=3, samples_per_round=3)
    dv = res.divergence
    assert res.mode_echoes_rejected == 3 and dv["drift_retries"] == 3 and dv["drift_recovered"] == 3
    retries = [c for c in model.calls if c["role"] == "converge" and "DRIFTED BACK" in c["prompt"]]
    assert len(retries) == 3 and all("use a token bucket per client" in r["prompt"] for r in retries)
    assert {c.evidence["intent"]["assumption"] for c in res.candidates} == {"time_windowed", "per_client",
                                                                           "fixed_budget"}
    off = gsl.llm_openended_search("invent a new rate limiter", _DriftingModel(), budget=3, samples_per_round=3,
                                   divergence=DivergenceConfig(drift_retries=False))
    assert off.divergence["drift_retries"] == 0 and not off.candidates


def test_an_invalid_convergent_completion_is_repaired_by_default():
    class Garbled(ScriptedLocalModel):
        def complete(self, prompt, *, system="", temperature=0.8, n=1, role=None, seed=None, **kw):
            if role == "converge" and "  mechanism: " in prompt:
                self.calls.append({"role": role, "prompt": prompt, "temperature": temperature, "seed": seed})
                return ["sorry, here is my idea in prose"]
            if "not a valid candidate JSON array" in prompt:
                cand = dict(_CAND_TEMPLATE, name="repaired idea", claim="tenants trade unused quota",
                            broken_assumption="per_client")
                return [json.dumps([cand])]
            return super().complete(prompt, system=system, temperature=temperature, n=n, role=role, seed=seed, **kw)
    res = gsl.llm_openended_search("invent a new rate limiter", Garbled(), budget=3, samples_per_round=3)
    # all three convergent completions were repaired; the identical repairs then meet the ordinary duplicate gate
    assert res.json_repairs == 3 and res.valid_count == 3
    assert [c.name for c in res.candidates] == ["repaired idea"] and res.duplicates_rejected == 2
    plain = gsl.llm_openended_search("invent a new rate limiter", Garbled(), budget=3, samples_per_round=3,
                                     divergence=DivergenceConfig(converge_json_repairs=0))
    assert plain.json_repairs == 0 and not plain.candidates
