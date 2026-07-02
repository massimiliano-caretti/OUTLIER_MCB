"""#1 GENERATIVITY — the process-wide resolvable default LLM.

The engine's own `transform_space` diagnosed its ceiling as a missing axis (GENERATIVITY, distance 0.95): it
recombines pre-written pack assumptions and never produces content it was not given. The fix mirrors the
embedder: a content SOURCE registered once (`set_default_llm` / OUTLIER_MCB_LLM) is drawn by the generative
entrypoint, while external settlement still decides what survives. Unset ⇒ template-only path, unchanged.

Ablation: with no default LLM the generative search cannot run (it has no content source); registering one
makes the SAME call run and surface the model's content. Deterministic offline fake — no network.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import OUTLIER_MCB as gsl
from OUTLIER_MCB.llm import default_llm, SubprocessLLMProvider


# a deterministic offline fake: it proposes one valid candidate with a DISTINCTIVE name we can detect
_CAND = {"name": "GENERATIVITY_PROBE_IDEA", "broken_assumption": "time_windowed", "operator": "invert",
         "claim": "a content string only an external source could have produced",
         "why_standard_families_fail": "templates cannot emit this", "world_test_description": "assert it ran"}


def _fake_llm():
    return gsl.CallableLLMProvider(lambda prompt: json.dumps([_CAND]))


def test_without_default_llm_generative_search_refuses():
    """No content source ⇒ the generative search refuses with a clear, typed error (never a silent crash)."""
    gsl.reset_default_llm()
    saved = os.environ.pop("OUTLIER_MCB_LLM", None)
    try:
        assert default_llm() is None
        try:
            gsl.llm_openended_search("invent something new", budget=4)
            assert False, "expected OUTLIER_MCBError when no LLM is available"
        except gsl.OUTLIER_MCBError as e:
            assert "set_default_llm" in str(e)
    finally:
        if saved is not None:
            os.environ["OUTLIER_MCB_LLM"] = saved


def test_registering_default_llm_makes_the_same_call_generate():
    """The ablation/flip: the identical call that REFUSED above now runs and surfaces the model's content —
    proving the generative entrypoint draws from the process-wide default."""
    try:
        gsl.set_default_llm(_fake_llm())
        res = gsl.llm_openended_search("invent something new", budget=4, samples_per_round=4)
        assert res.candidates, "the default LLM should have produced candidates"
        names = {c.name for c in res.candidates}
        claims = " ".join(getattr(c, "claim", "") for c in res.candidates)
        assert "GENERATIVITY_PROBE_IDEA" in names or "only an external source" in claims
    finally:
        gsl.reset_default_llm()


def test_env_var_resolves_subprocess_and_is_cached_and_safe():
    """The opt-in env path builds a provider once (cached) and a missing/none spec stays the template path."""
    import OUTLIER_MCB.llm as L
    saved = os.environ.get(L._ENV_VAR_LLM)
    try:
        gsl.reset_default_llm()
        for value in (None, "none", "unknown-scheme:x"):
            if value is None:
                os.environ.pop(L._ENV_VAR_LLM, None)
            else:
                os.environ[L._ENV_VAR_LLM] = value
            assert default_llm() is None
        os.environ[L._ENV_VAR_LLM] = "subprocess:my-llm --model x"
        prov = default_llm()
        assert isinstance(prov, SubprocessLLMProvider)
        assert default_llm() is prov                       # cached: built once, not per resolution
    finally:
        if saved is None:
            os.environ.pop(L._ENV_VAR_LLM, None)
        else:
            os.environ[L._ENV_VAR_LLM] = saved
        gsl.reset_default_llm()


def test_programmatic_registration_overrides_env():
    import OUTLIER_MCB.llm as L
    saved = os.environ.get(L._ENV_VAR_LLM)
    try:
        os.environ[L._ENV_VAR_LLM] = "subprocess:should-be-ignored"
        fake = _fake_llm()
        gsl.set_default_llm(fake)
        assert default_llm() is fake
    finally:
        if saved is None:
            os.environ.pop(L._ENV_VAR_LLM, None)
        else:
            os.environ[L._ENV_VAR_LLM] = saved
        gsl.reset_default_llm()
