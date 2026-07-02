"""llm_loop_demo — the LLM-in-the-loop engine, end-to-end, OFFLINE.

Runs the full loop with a DETERMINISTIC FAKE LLM (no network, no API key) against a throwaway repo, so you
can watch a candidate materialize a failing test, go RED, get a patch, go GREEN, and win by EXECUTABLE score.
Swap the fake for `gsl.CallableLLMProvider(your_model)` or `gsl.SubprocessLLMProvider("your-cli")` for real.

    python examples/llm_loop_demo.py
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import OUTLIER_MCB as gsl  # noqa: E402

TEST_PATCH = ("--- /dev/null\n+++ b/tests/test_feature.py\n@@ -0,0 +1,3 @@\n"
              "+from feature import f\n+def test_f():\n+    assert f() == 42\n")
# the FIRST implementation is WRONG (returns 41 → the test stays RED); a bounded impl-repair fixes it to 42.
IMPL_BAD = ("--- a/feature.py\n+++ b/feature.py\n@@ -1,2 +1,2 @@\n def f():\n-    return 0\n+    return 41\n")
IMPL_FIX = ("--- a/feature.py\n+++ b/feature.py\n@@ -1,2 +1,2 @@\n def f():\n-    return 41\n+    return 42\n")

GOOD = {"name": "break_default_zero", "broken_assumption": "time_windowed", "operator": "invert",
        "claim": "the feature should return 42, not the default 0",
        "why_standard_families_fail": "they hard-code the default", "world_test_description": "assert f()==42",
        "test_patch": TEST_PATCH, "implementation_patch": IMPL_BAD, "novelty_rationale": "breaks the default",
        "risk": "low"}
REBRAND = {"name": "token_bucket", "broken_assumption": "time_windowed",
           "claim": "token_bucket", "world_test_description": "token_bucket"}   # no test → cannot win by evidence


def fake_llm_factory():
    """A deterministic fake: round 1 proposes a rebrand + the good candidate (whose first patch is wrong),
    then keeps proposing the good one. When asked to REPAIR the broken impl, it returns the corrected diff."""
    batches = iter([json.dumps([REBRAND, GOOD]), "garbage, not json", json.dumps([GOOD])])

    def fn(prompt):
        if "fixing ONE broken field" in prompt:        # a bounded repair request → return the corrected diff
            return IMPL_FIX
        return next(batches, json.dumps([GOOD]))
    return gsl.CallableLLMProvider(fn)


def main():
    repo = tempfile.mkdtemp(prefix="gsl_llm_demo_")
    try:
        Path(repo, "feature.py").write_text("def f():\n    return 0\n")
        (Path(repo) / "tests").mkdir()
        Path(repo, "tests", "test_smoke.py").write_text("def test_smoke():\n    assert True\n")
        Path(repo, "pyproject.toml").write_text("[tool.pytest.ini_options]\n")

        result = gsl.llm_openended_search(
            "invent a feature that returns 42 by breaking the default", fake_llm_factory(),
            repo_path=repo, budget=6, samples_per_round=2, materialize=True,
            max_json_repairs=1, max_impl_repairs=1)

        print(result.markdown())
        print(f"\nBounded repairs used — json:{result.json_repairs} test:{result.test_repairs} "
              f"impl:{result.impl_repairs}  (the first patch returned 41; the impl-repair fixed it to 42)")
        best = result.best()
        print("\nWinner chosen by EXECUTABLE score (not the LLM's order):")
        print(f"  «{best.name}»  score={best.score}  verdict={best.verdict}  "
              f"red={best.evidence.get('red_kind')}  GREEN={best.evidence.get('green_final')}")
        print(f"\nThe repo now contains the materialized test: tests/test_feature.py exists = "
              f"{(Path(repo) / 'tests' / 'test_feature.py').exists()}")
        print(f"  and the patch was applied: feature.py = {Path(repo, 'feature.py').read_text().strip()!r}")
        print("\nHonest limits: this is a FAKE LLM and a toy repo. With a real provider, candidate quality and "
              "prior-art search are only as good as the model/provider you wire in; a candidate still cannot "
              "win unless its NEW test was RED before its patch and GREEN after.")
    finally:
        shutil.rmtree(repo, ignore_errors=True)


if __name__ == "__main__":
    main()
