"""test_blind_discovery_eval — on a LARGE, BLIND, data-settled task, compounding memory earns its keep.

The honest payoff: with the true break buried at the bottom of a 12-assumption space and a tight per-round
budget, a MEMORYLESS searcher never reaches it, while the COMPOUNDING memory explores and CONFIRMS it
(settled by the symbolic evaluator). The curiosity delta is reported as-measured — not assumed.
"""
from evals.blind_discovery_eval import run_blind_discovery_eval


def test_memory_finds_what_memoryless_cannot():
    r = run_blind_discovery_eval(rounds=6, budget=4)
    assert r["memory_earns_its_keep"] is True                 # the headline, measured on data
    assert r["memoryless_found_round"] is None                # the baseline loops, never reaching the buried break
    assert r["memory_found_round"] is not None and r["memory_found_round"] <= 6
    assert r["distinct_seeds_memory"] > r["distinct_seeds_memoryless"]   # it explored; the baseline did not


def test_curiosity_effect_is_reported_not_assumed():
    r = run_blind_discovery_eval(rounds=6, budget=4)
    # we do not assert a curiosity win — only that the measurement is well-formed and honest.
    assert r["curiosity_rounds_saved"] is None or isinstance(r["curiosity_rounds_saved"], int)


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
