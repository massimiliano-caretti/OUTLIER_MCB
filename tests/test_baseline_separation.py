"""Executable separation from the known family: the idea's test must stay RED under the best KNOWN family
(baseline_patch) and go GREEN under the idea. A test the known family also passes proves nothing new."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_llm_loop import _TEST_PATCH, _IMPL_PATCH, _temp_repo  # noqa: E402

from OUTLIER_MCB.llm_loop import _materialize, llm_evidence_score, score_components  # noqa: E402
from OUTLIER_MCB.runner import CommandRunner  # noqa: E402

# the known family returns 7 (still RED on `f() == 42`) — the idea is separated from it
_BASELINE_FAILS = "--- a/feature.py\n+++ b/feature.py\n@@ -1,2 +1,2 @@\n def f():\n-    return 0\n+    return 7\n"
# the known family ALSO returns 42 — the test does not separate the idea from it
_BASELINE_PASSES = "--- a/feature.py\n+++ b/feature.py\n@@ -1,2 +1,2 @@\n def f():\n-    return 0\n+    return 42\n"


def _run(baseline):
    repo = _temp_repo()
    cd = {"test_patch": _TEST_PATCH, "implementation_patch": _IMPL_PATCH, "baseline_patch": baseline}
    ev = _materialize(cd, repo, runner=CommandRunner(), timeout=60)
    return ev, repo


def test_known_family_that_fails_the_test_means_separation():
    ev, repo = _run(_BASELINE_FAILS)
    assert ev["red_kind"] == "RED_ASSERTION" and ev["baseline_kind"] == "RED_ASSERTION"
    assert ev["beats_baseline"] is True and ev["green_final"] is True
    assert "return 42" in Path(repo, "feature.py").read_text()       # the idea, not the baseline, landed


def test_known_family_that_passes_the_test_is_not_separated_and_is_capped():
    ev, repo = _run(_BASELINE_PASSES)
    assert ev["baseline_kind"] == "GREEN" and ev["beats_baseline"] is False
    full = {"green_final": True, "red_kind": "RED_ASSERTION", "test_quality": 1.0, "prior_art_component": 1.0,
            "diversity": 1.0, "patch_substance": 1.0, "risk": 0.0}
    assert llm_evidence_score(full) > 0.8
    assert llm_evidence_score(dict(full, beats_baseline=False)) <= 0.25     # below the keep threshold
    assert llm_evidence_score(dict(full, beats_baseline=True)) >= llm_evidence_score(full)
    assert score_components(dict(full, beats_baseline=False))["baseline_separation"] == 0.0


def test_baseline_is_always_rolled_back_and_bad_baselines_are_neutral():
    ev, repo = _run("--- a/missing.py\n+++ b/missing.py\n@@ -1,1 +1,1 @@\n-x\n+y\n")
    assert ev["beats_baseline"] is None and ev["green_final"] is True
    ev, _ = _run("--- a/.git/hooks/pre-commit\n+++ b/.git/hooks/pre-commit\n@@ -0,0 +1,1 @@\n+rm -rf /\n")
    assert ev["beats_baseline"] is None and "unsafe" in ev["baseline_tail"]
    # no baseline at all → the score is exactly what it was before this feature
    ev, _ = _run(None)
    assert ev["beats_baseline"] is None and score_components(ev)["baseline_separation"] == 0.5
