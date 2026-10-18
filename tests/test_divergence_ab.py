"""The divergence A/B harness (evals/divergence_ab.py): conditions, metrics, resume and report — offline, with a
scripted sampling-aware model, so the harness is known to work before hours of real-model time are spent on it."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evals import divergence_ab as ab
from OUTLIER_MCB.llm_divergence import DenialSet, DivergenceConfig, diverge_prompt


class Scripted:
    """Answers each role the way a local model would, and counts calls."""
    supports_roles = True
    sampler_controls = frozenset({"temperature", "seed", "top_p", "top_k"})

    def __init__(self):
        self.calls = 0

    def complete(self, prompt, *, system="", temperature=0.8, n=1, role=None, **kw):
        self.calls += 1
        if role == "mode":
            return ["ANSWER: a token bucket per client || p=0.5\nANSWER: a sliding window counter || p=0.3"]
        if role == "diverge":
            return ["OBSERVATION: x\n"
                    "INTENT: per_client || tenants trade unused quota in an internal market || p=0.03\n"
                    "INTENT: time_windowed || capacity follows measured downstream slack every second || p=0.04"]
        if "Propose 4 genuinely new ideas" in prompt:
            return ["IDEA: a token bucket per client\nIDEA: **a sliding window counter with jitter**\nno idea here"]
        mech = prompt.split("  mechanism: ", 1)[1].splitlines()[0] if "  mechanism: " in prompt else "a fixed window"
        cand = {"name": mech[:30], "broken_assumption": "per_client", "claim": mech, "world_test_description": "t"}
        return [json.dumps([cand])] * max(1, n)


def test_direct_ideas_are_parsed_tolerantly():
    assert ab.parse_direct_ideas("IDEA: one two three\n- **IDEA:** four five six\nIDEA: short\nrubbish") == [
        "one two three", "four five six"]


def test_metrics_on_known_cases():
    defaults = ["a token bucket per client", "a sliding window counter"]
    echo = ab.idea_metrics("rate limit clients", defaults, defaults)
    assert echo["tail_rate"] == 0.0 and echo["mode_dist"] == 0.0 and echo["distinct"] == 2
    far = ab.idea_metrics("rate limit clients", ["tenants trade unused quota in an internal market",
                                                 "capacity follows measured downstream slack every second"], defaults)
    assert far["tail_rate"] == 1.0 and far["mode_dist"] > 0.5
    assert ab.idea_metrics("x", [], defaults)["tail_rate"] is None
    assert ab.distinct_count(["same idea words", "same idea words", "other entirely different"]) == 2


def test_bootstrap_is_deterministic_and_brackets_the_mean():
    mean, lo, hi = ab.bootstrap_ci([0.1, 0.2, 0.3, 0.4])
    assert mean == 0.25 and lo <= mean <= hi and ab.bootstrap_ci([0.1, 0.2, 0.3, 0.4]) == (mean, lo, hi)
    assert ab.bootstrap_ci([]) == (None, None, None)


def test_run_records_every_condition_resumes_without_new_calls_and_reports(tmp_path):
    out = str(tmp_path / "ab")
    prompts = ab.PROMPTS[:2]
    model = Scripted()
    rows = ab.run(model, out, prompts=prompts, log=lambda _m: None)
    expected = {"yardstick", *ab.CONDITIONS, *(f"abl_{a}" for a in ab.ABLATIONS)}
    assert {r["condition"] for r in rows} == expected and len(rows) == 2 * len(expected)
    calls = model.calls
    ab.run(model, out, prompts=prompts, log=lambda _m: None)
    assert model.calls == calls                                         # resumed: nothing re-run
    summary = ab.report(out, meta={"llm": "scripted", "embedder": "lexical"})
    assert summary["conditions"]["C_divergent"]["n_requests"] == 2
    direct, divergent = summary["conditions"]["A_direct"], summary["conditions"]["C_divergent"]
    assert direct["tail_rate"][0] < divergent["tail_rate"][0]            # the echoing direct answer stays in the box
    assert "full - no_anti_mode" in summary["ablations"]
    md = open(os.path.join(out, "report.md"), encoding="utf-8").read()
    assert "## Paired comparisons" in md and "C_divergent - A_direct" in md
    assert json.load(open(os.path.join(out, "summary.json"), encoding="utf-8"))["meta"]["n_requests"] == 2


def test_ablation_switches_change_what_the_model_is_asked():
    denial = DenialSet()
    denial.add("known family", "token bucket")
    full = diverge_prompt("p", None, "a physicist", denial, 5, 12, ["a"])
    bare = diverge_prompt("p", None, "a physicist", denial, 5, 0, ["a"], observations=False, verbalized=False)
    assert "OBSERVATIONS" in full and "p=<0..1>" in full and "DO NOT USE" in full and full.endswith("OBSERVATION:")
    assert "OBSERVATION" not in bare and "p=<0..1>" not in bare and "DO NOT USE" not in bare
    cfg = DivergenceConfig(observations_first=False, verbalized_tail=False, denial_in_prompt=False)
    assert not (cfg.observations_first or cfg.verbalized_tail or cfg.denial_in_prompt)


def test_without_verbalized_tail_selection_ignores_the_self_reported_probability():
    from OUTLIER_MCB.llm_divergence import Intent, select_intents
    typical = Intent("a", "the model's own common answer worded at length", probability=0.9)
    rare = Intent("a", "an unusual mechanism the model says is rare", probability=0.01)
    assert select_intents([typical, rare], DenialSet(), k=1) == [rare]
    assert select_intents([typical, rare], DenialSet(), k=1, use_probability=False) == [typical]   # input order
