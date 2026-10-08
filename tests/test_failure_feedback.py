"""failure_feedback — negative verdicts persist across calls and demote the spent break in the next brief."""
import json

import OUTLIER_MCB as gsl
from OUTLIER_MCB import kernel
from OUTLIER_MCB.failure_feedback import FailureStore, resolve_store, ENV_VAR

PROMPT = "invent a new rate limiter"



def test_store_records_only_negative_verdicts_and_counts_repeats(tmp_path):
    s = FailureStore(str(tmp_path / "m.json"))
    assert s.record("coding", "x", "MUST_BE_AUDITED") is None
    s.record("coding", "fair queue", "RENAMED", assumption="tenant_independent")
    e = s.record("coding", "fair queue", "RENAMED", assumption="tenant_independent")
    assert e["count"] == 2 and e["status"] == "DEAD_RENAMED"
    s.save()
    again = FailureStore(str(tmp_path / "m.json"))
    assert again.spent("coding") == [{"assumption": "tenant_independent", "deaths": 2, "verdicts": ["RENAMED"]}]


def test_two_deaths_demote_the_recommended_break_without_mutating_the_registered_pack(tmp_path):
    path = str(tmp_path / "m.json")
    before = gsl.assistant_route(PROMPT).break_assumption
    s = FailureStore(path)
    for _ in range(2):
        s.record("coding", "idea on " + before, "COLLAGE", assumption=before)
    s.save()
    after = gsl.assistant_route(PROMPT, memory=path)
    assert after.break_assumption and after.break_assumption != before
    assert "Already spent" in after.brief and before in after.brief
    assert gsl.get_pack("coding").failure_memory == {}             # only a copy carries the memory
    assert gsl.assistant_route(PROMPT).break_assumption == before   # no memory → unchanged


def test_judge_persists_a_negative_verdict_and_creative_lists_it(tmp_path):
    path = str(tmp_path / "m.json")
    j = gsl.judge("a token bucket per client", prompt=PROMPT, memory=path)
    assert j.verdict == "INSIDE_THE_BOX"
    data = json.loads((tmp_path / "m.json").read_text())
    assert any(e["idea"] == "a token bucket per client" for e in data["coding"].values())
    assert "«a token bucket per client»" in gsl.creative(PROMPT, memory=path)


def test_env_var_and_corrupt_file(tmp_path, monkeypatch):
    p = tmp_path / "bad.json"
    p.write_text("{not json")
    assert FailureStore(str(p)).data == {}                         # corrupt store never blocks a verdict
    monkeypatch.setenv(ENV_VAR, str(tmp_path / "env.json"))
    assert resolve_store().path == str(tmp_path / "env.json")
    monkeypatch.delenv(ENV_VAR)
    assert resolve_store() is None


def test_one_death_only_reorders_within_priority():
    p = gsl.get_pack("coding")
    g = gsl.graph_of(p)
    top = kernel._ranked_breakable(p, g)[0]
    s = FailureStore(None)
    s.record("coding", "i", "INSIDE_THE_BOX", assumption=top)
    p1 = s.apply(p)
    prio = lambda q, n: q.axes[q.dimension_of[n]]["priority"]            # noqa: E731
    new_top = kernel._ranked_breakable(p1, gsl.graph_of(p1))[0]
    assert prio(p, new_top) == prio(p, top)                          # still the same priority level
