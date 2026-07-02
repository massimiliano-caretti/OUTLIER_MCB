"""test_feynman_summary — the honest headline on the official Feynman/SRBench ground truth: failures are
counted, symbolic recoveries are the strict measure, nothing is cherry-picked. Deterministic, offline.
"""
import pytest

pytest.importorskip("sympy")

from evals.benchmarks.feynman import feynman_summary, FEYNMAN_ALL


def test_summary_is_honest_and_counts_failures():
    s = feynman_summary()
    assert s["total_documented"] == len(FEYNMAN_ALL)
    # strict symbolic recoveries <= accuracy solutions <= total; failures are the remainder (not hidden)
    assert 0 <= s["symbolic_exact"] <= s["accuracy_solutions"] <= s["total_documented"]
    assert s["failed"] == s["total_documented"] - s["accuracy_solutions"]
    assert s["failed"] > 0                                  # the hard forms honestly fail (no inflation)
    assert "official Feynman" in s["ground_truth"]
