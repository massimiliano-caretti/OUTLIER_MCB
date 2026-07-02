"""test_activation — make library use a DEFAULT ROUTINE for any AI assistant: the one-call brief, the
provider-agnostic snippet, the trigger detection, the activation files, and the CLI. Deterministic.
"""
import os

import OUTLIER_MCB as m

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(m.__file__)))


def test_should_activate_on_novelty_triggers():
    assert m.SUPPORTED_ASSISTANT_LANGUAGES == ("en", "it")
    assert m.should_activate("invent a new rate limiter") is True
    assert m.should_activate("inventa qualcosa di mai visto") is True       # any language
    assert m.should_activate("migliorare l'uso della libreria verso LLM") is True
    assert m.should_activate("improve the library for continuous LLM use") is True
    assert m.should_activate("fix this off-by-one bug") is False            # not a creativity request


def test_assistant_brief_has_rules_and_a_break():
    brief = m.assistant_brief("invent a new caching architecture")
    assert "STANDING ROUTINE" in brief                                      # the non-negotiable routine
    assert "novelty_scope" in brief and "absolute novelty" in brief         # the honesty rules
    assert "break" in brief.lower()                                         # the engine's preflight (which assumption)


def test_assistant_route_is_compact_for_continuous_use():
    quiet = m.assistant_route("fix this off-by-one bug")
    assert quiet.activate is False and quiet.action == "answer_directly"

    route = m.assistant_route("invent a new caching architecture")
    assert route.activate is True
    assert route.entrypoint in {"creative", "elicit_pack|green_star"}
    assert route.break_assumption
    assert route.novelty_scope_required is True
    assert route.languages == ("en", "it")
    assert "novelty_scope" in route.must_report
    assert "EN:" in route.brief and "IT:" in route.brief
    assert "STANDING ROUTINE" not in route.brief                              # compact by default
    assert "STANDING ROUTINE" in m.assistant_route("invent a cache", full_brief=True).brief


def test_activation_snippet_is_provider_agnostic():
    snip = m.activation_snippet()
    for tool in ("Claude", "ChatGPT", "Gemini", "Cursor"):
        assert tool in snip                                                 # works for any assistant
    assert "assistant_brief" in snip and "explore(" in snip and "z3" in snip


def test_activation_files_exist():
    for f in ("AGENTS.md", ".cursorrules"):
        path = os.path.join(_ROOT, f)
        assert os.path.exists(path)
        text = open(path).read()
        assert "OUTLIER_MCB" in text and "assistant_brief" in text and "novelty_scope" in text


def test_cli_activate_and_brief_and_explore(capsys):
    from OUTLIER_MCB.cli import main
    main(["activate"]); assert "standing routine" in capsys.readouterr().out.lower()
    main(["brief", "--problem", "invent a new scheduler"]); assert "STANDING ROUTINE" in capsys.readouterr().out
    main(["route", "--problem", "invent a new scheduler", "--json"])
    out = capsys.readouterr().out
    assert '"activate": true' in out and '"languages": [' in out
    main(["explore", "--problem", "invent a new rate limiter", "--budget", "6"])
    assert "Studio" in capsys.readouterr().out


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
