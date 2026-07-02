"""Tests for the LLM-in-the-loop engine — deterministic, OFFLINE (a fake LLM), with a temp git-less repo.
Run: python -m pytest tests/test_llm_loop.py -q."""
import json
import os
import sys
import tempfile
import warnings
from pathlib import Path

import pytest

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import OUTLIER_MCB as gsl  # noqa: E402
from OUTLIER_MCB.llm import CallableLLMProvider, parse_candidates  # noqa: E402
from OUTLIER_MCB.llm_loop import (llm_openended_search, llm_evidence_score,  # noqa: E402
                                    classify_test_outcome)
from OUTLIER_MCB.llm_loop import test_quality_score as quality_score  # noqa: E402  (test_* alias: not a test)
from OUTLIER_MCB.patches import (parse_unified_diff, validate_patch_paths,  # noqa: E402
                                   patch_substance_score, PatchTransaction)
from OUTLIER_MCB.prior_art import PriorArtResult, OnlinePriorArtProvider  # noqa: E402
from OUTLIER_MCB.runner import CommandRunner, CommandResult, UnsafeCommandError, to_argv  # noqa: E402

_TEST_PATCH = "--- /dev/null\n+++ b/tests/test_feature.py\n@@ -0,0 +1,3 @@\n+from feature import f\n+def test_f():\n+    assert f() == 42\n"
_IMPL_PATCH = "--- a/feature.py\n+++ b/feature.py\n@@ -1,2 +1,2 @@\n def f():\n-    return 0\n+    return 42\n"
_GOOD = {"name": "answer42", "broken_assumption": "time_windowed", "operator": "invert",
         "claim": "f returns 42 by breaking the default", "why_standard_families_fail": "they assume 0",
         "world_test_description": "assert f()==42", "test_patch": _TEST_PATCH, "implementation_patch": _IMPL_PATCH,
         "novelty_rationale": "n", "risk": "low"}
_REBRAND = {"name": "token_bucket", "broken_assumption": "time_windowed",
            "claim": "a token bucket rate limiter", "world_test_description": "x"}


def _scripted(batches):
    it = iter(batches)
    return CallableLLMProvider(lambda p: next(it, json.dumps([_GOOD])))


def _temp_repo():
    d = tempfile.mkdtemp()
    Path(d, "feature.py").write_text("def f():\n    return 0\n")
    (Path(d) / "tests").mkdir()
    Path(d, "tests", "test_smoke.py").write_text("def test_smoke():\n    assert True\n")
    Path(d, "pyproject.toml").write_text("[tool.pytest.ini_options]\n")
    return d


class _FakeOnlinePriorArt(OnlinePriorArtProvider):
    def __init__(self, results=None, fail=False, name="fake_online"):
        super().__init__()
        self.name = name
        self._results = results or []
        self._fail = fail

    def _fetch(self, query):
        if self._fail:
            raise RuntimeError("offline")
        return list(self._results)


# ── parsing / validation (no crash on bad output) ──
def test_invalid_llm_json_is_discarded_without_crashing():
    r = parse_candidates("this is not json")
    assert r.valid == [] and r.discarded
    r2 = parse_candidates(json.dumps([{"name": "x"}]))      # missing required fields
    assert r2.valid == [] and r2.discarded


def test_patch_path_traversal_is_rejected():
    plan = parse_unified_diff("--- /dev/null\n+++ b/../../etc/evil\n@@ -0,0 +1,1 @@\n+x\n")
    ok, errs = validate_patch_paths(plan, ".")
    assert ok is False and any("travers" in e for e in errs)


# ── the loop calls the LLM multiple times ──
def test_loop_calls_llm_multiple_times_when_budget_exceeds_samples():
    r = llm_openended_search("invent something", _scripted([json.dumps([_GOOD])]),
                             budget=8, samples_per_round=2)
    assert r.llm_call_count == 4                            # 8 // 2 rounds → 4 calls, not 1
    assert r.llm_call_count > 1


# ── rebrand can't win ──
def test_rebrand_of_known_family_cannot_win():
    r = llm_openended_search("design a rate limiter", _scripted([json.dumps([_REBRAND, _REBRAND])]),
                             budget=4, samples_per_round=2)
    assert r.rebrand_count >= 1
    rebrands = [c for c in r.candidates if c.verdict in ("RENAMED_PRIOR_ART", "COLLAGE_OF_PRIOR_ART")]
    assert rebrands and all(c.score < 0.3 for c in rebrands)   # gated down, cannot be the winner


# ── without materialization a candidate stays unmaterialized (no GREEN, low score) ──
def test_without_materialization_no_green_and_score_is_capped():
    r = llm_openended_search("invent something", _scripted([json.dumps([_GOOD])]),
                             budget=4, samples_per_round=2, materialize=False)
    assert r.materialized_count == 0 and r.green_final_count == 0
    assert all(not c.evidence.get("green_final") for c in r.candidates)


def test_local_only_prior_art_scope_caps_novelty_component():
    provider = gsl.CompositePriorArtProvider([
        gsl.OfflinePriorArtProvider([{"title": "sourdough bread recipe", "summary": "flour water salt"}])
    ])
    r = llm_openended_search("invent something", _scripted([json.dumps([_GOOD])]),
                             budget=1, samples_per_round=1, prior_art_provider=provider)
    ev = r.candidates[0].evidence
    assert ev["prior_art_scope"] == "LOCAL_ONLY"
    assert ev["prior_art_scoped_verdict"] == "LOCAL_ONLY_NOVELTY"
    assert ev["prior_art_component"] <= 0.55
    assert r.to_dict()["best"]["prior_art_scope"] == "LOCAL_ONLY"


def test_partial_online_prior_art_scope_is_propagated_and_capped():
    provider = gsl.CompositePriorArtProvider([
        _FakeOnlinePriorArt([PriorArtResult(title="sourdough bread recipe", summary="flour water salt")])
    ])
    r = llm_openended_search("invent something", _scripted([json.dumps([_GOOD])]),
                             budget=1, samples_per_round=1, prior_art_provider=provider)
    ev = r.candidates[0].evidence
    assert ev["prior_art_scope"] == "ONLINE_PRIOR_ART_CHECKED"
    assert ev["prior_art_coverage_level"] == "PARTIAL"
    assert ev["prior_art_scoped_verdict"] == "PROVISIONALLY_NOVEL_ON_CHECKED_SOURCES"
    assert ev["prior_art_component"] <= 0.82
    assert r.to_dict()["best"]["prior_art_checked_sources"]


# ── WITH materialization: the test is written, fails RED, then passes GREEN after the patch ──
def test_materialization_runs_red_then_green():
    d = _temp_repo()
    try:
        r = llm_openended_search("invent a feature returning 42", _scripted([json.dumps([_GOOD])]),
                                 repo_path=d, budget=2, samples_per_round=1, materialize=True)
        assert r.materialized_count >= 1                    # the test file was written into the repo
        assert r.red_first_count >= 1                       # it was RED before the patch
        assert r.green_final_count >= 1                     # and GREEN after the implementation patch
        assert (Path(d) / "tests" / "test_feature.py").exists()
        assert "return 42" in (Path(d) / "feature.py").read_text()
    finally:
        import shutil
        shutil.rmtree(d, ignore_errors=True)


# ── the winner is chosen by the external score, NOT the LLM's order ──
def test_winner_is_chosen_by_external_score_not_llm_order():
    # the LLM lists the rebrand FIRST, the good materializable one SECOND; the good one must still win
    d = _temp_repo()
    try:
        r = llm_openended_search("invent a feature returning 42",
                                 _scripted([json.dumps([_REBRAND, _GOOD])]),
                                 repo_path=d, budget=2, samples_per_round=2, materialize=True)
        assert r.best().name == "answer42"                  # second in LLM order, first by evidence
        assert r.best().score > 0.5 and r.best().evidence.get("green_final")
    finally:
        import shutil
        shutil.rmtree(d, ignore_errors=True)


# ── the LLM loop fills a non-trivial MAP-Elites archive from diverse candidates ──
def test_llm_loop_fills_a_nontrivial_archive():
    # a fake LLM emitting 4 different broken assumptions → distinct behavioral cells (the QD point)
    cands = [dict(_GOOD, name=f"c{i}", broken_assumption=a, test_patch="", implementation_patch="")
             for i, a in enumerate(["time_windowed", "tenant_independent", "stateless_local", "cost_uniform"])]
    r = llm_openended_search("design a rate limiter", _scripted([json.dumps(cands)]),
                             budget=4, samples_per_round=4)
    assert r.archive.coverage() >= 3                        # several distinct cells, not one point
    # and it beats GSL_FULL's single-best frontier coverage (measured in the eval mode); here, sanity:
    assert r.valid_count >= 4


# ── the executable score rewards GREEN and punishes cosmetic/rebrand ──
def test_gsl_llm_loop_fake_mode_beats_gsl_full_on_the_five_metrics():
    # the eval-harness acceptance: the LLM-loop mode (fake LLM, REAL materialization run once) must beat
    # GSL_FULL on materialization, LLM-call count, red→green, archive coverage, and anti-rebrand.
    from evals.run_eval import run
    S = run(modes=["GSL_FULL", "GSL_LLM_LOOP_FAKE"])["summary"]
    f, l = S["GSL_FULL"], S["GSL_LLM_LOOP_FAKE"]
    for m in ("materialization_score", "llm_call_count_score", "red_green_score",
              "qd_coverage_score", "anti_rebrand_score",
              # §11 severe metrics: realistic failure modes, each 0 for the heuristic GSL_FULL
              "red_assertion_green_score", "test_quality_score", "patch_substance_score",
              "duplicate_rejection_score", "repair_success_score"):
        assert l[m] > f[m], f"GSL_LLM_LOOP_FAKE must beat GSL_FULL on {m} ({l[m]} vs {f[m]})"


def test_llm_evidence_score_rewards_green_punishes_cosmetic():
    green = llm_evidence_score({"green_final": True, "red_first": True, "has_patch": True,
                                "test_specific": True, "novelty_distance": 1.0, "prior_art_weak": True, "cell_new": True})
    cosmetic = llm_evidence_score({"green_final": False, "has_patch": True, "only_cosmetic": True})
    rebrand = llm_evidence_score({"rebrand": True, "has_patch": False})
    assert green > 0.8 > cosmetic and rebrand == 0.0


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════
# §11 — severe failure-mode tests: the loop must improve against REALISTIC ways an LLM "wins" without inventing.
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════

# §1 — command execution is conservative: shell injection in a command is REFUSED, not run.
def test_command_runner_blocks_shell_injection():
    d = tempfile.mkdtemp()
    try:
        res = CommandRunner().run("pytest -q; touch hacked", cwd=d)
        assert res.returncode == 126 and "shell operators" in res.error
        assert not (Path(d) / "hacked").exists()                 # the injected command never ran
        for bad in ("a | b", "a && b", "a > f", "a `b`", "a $(b)"):
            with pytest.raises(UnsafeCommandError):
                to_argv(bad)
        assert to_argv(["pytest", "-q", ";touch x"]) == ["pytest", "-q", ";touch x"]   # list form: one safe token
    finally:
        import shutil
        shutil.rmtree(d, ignore_errors=True)


def test_subprocess_llm_provider_does_not_use_a_shell():
    d = tempfile.mkdtemp()
    try:
        prov = gsl.SubprocessLLMProvider(f"true; touch {Path(d) / 'pwned'}")
        out = prov.complete("hello")
        assert out and "_error" in out[0]                        # refused, returned as an error completion
        assert not (Path(d) / "pwned").exists()
    finally:
        import shutil
        shutil.rmtree(d, ignore_errors=True)


# §1/§2 — a patch that escapes the repo via a symlink is rejected before any write.
def test_patch_symlink_escape_is_rejected():
    d = tempfile.mkdtemp()
    outside = tempfile.mkdtemp()
    try:
        os.symlink(outside, os.path.join(d, "link"))
        plan = parse_unified_diff("--- /dev/null\n+++ b/link/evil.py\n@@ -0,0 +1,1 @@\n+x\n")
        ok, errs = validate_patch_paths(plan, d)
        assert ok is False and any("escape" in e for e in errs)
    finally:
        import shutil
        shutil.rmtree(d, ignore_errors=True); shutil.rmtree(outside, ignore_errors=True)


# §3 — a test that already PASSES before the patch is not a valid RED (it proves nothing).
def test_passing_test_is_not_a_valid_red():
    d = _temp_repo()                                             # feature.f() returns 0
    try:
        tp = ("--- /dev/null\n+++ b/tests/test_pass.py\n@@ -0,0 +1,3 @@\n"
              "+from feature import f\n+def test_p():\n+    assert f() == 0\n")   # already green
        cand = dict(_GOOD, name="already_green", test_patch=tp, implementation_patch="")
        r = llm_openended_search("x", _scripted([json.dumps([cand])]), repo_path=d,
                                 budget=1, samples_per_round=1, materialize=True)
        c = r.candidates[0]
        assert c.evidence.get("red_first") is False and not c.evidence.get("green_final")
        assert c.score < 0.5
    finally:
        import shutil
        shutil.rmtree(d, ignore_errors=True)


# §3 — a broken-import 'failure' is RED_COLLECTION (a plumbing fix), never the rewarded RED_ASSERTION.
def test_broken_import_is_red_collection_not_assertion():
    d = _temp_repo()
    try:
        tp = ("--- /dev/null\n+++ b/tests/test_imp.py\n@@ -0,0 +1,3 @@\n"
              "+import nonexistent_module_xyz\n+def test_i():\n+    assert nonexistent_module_xyz.v == 1\n")
        cand = dict(_GOOD, name="brokenimport", test_patch=tp, implementation_patch="")
        r = llm_openended_search("x", _scripted([json.dumps([cand])]), repo_path=d,
                                 budget=1, samples_per_round=1, materialize=True)
        assert r.candidates[0].evidence.get("red_kind") == "RED_COLLECTION"
        assert r.red_collection_count >= 1 and r.red_assertion_count == 0
    finally:
        import shutil
        shutil.rmtree(d, ignore_errors=True)


def test_classify_test_outcome_distinguishes_red_kinds():
    assert classify_test_outcome(CommandResult([], 0)) == "GREEN"
    assert classify_test_outcome(CommandResult([], 1, stdout="E AssertionError\n1 failed")) == "RED_ASSERTION"
    assert classify_test_outcome(CommandResult([], 2, stderr="ImportError: no module named x")) == "RED_COLLECTION"
    assert classify_test_outcome(CommandResult([], 124, timed_out=True)) == "ERROR_TIMEOUT"


# §3/§8 — monotonicity: RED_ASSERTION→GREEN beats RED_COLLECTION→GREEN beats not-materialized; rebrand loses.
def test_score_components_are_monotonic():
    base = dict(has_patch=True, materialized=True, red_first=True, test_quality=0.9,
                prior_art_component=0.9, diversity=0.9, patch_substance=0.9, risk=0.1)
    ra_green = llm_evidence_score(dict(base, red_kind="RED_ASSERTION", green_final=True))
    rc_green = llm_evidence_score(dict(base, red_kind="RED_COLLECTION", green_final=True))
    not_mat = llm_evidence_score(dict(base, materialized=False, red_first=False, green_final=False))
    assert ra_green > rc_green > not_mat
    assert llm_evidence_score(dict(base, rebrand=True, red_kind="RED_ASSERTION", green_final=True)) == 0.0


# §4 — a tautological test (assert True) cannot beat a specific one (imports target, concrete value).
def test_tautological_test_loses_on_quality():
    good = quality_score("+from feature import f\n+def test():\n+    assert f() == 42\n", "f returns 42")
    taut = quality_score("+def test():\n+    assert True\n")
    assert good > 0.7 > taut


# §9 — patch substance: cheating patches (only-test / skip / weaken / cosmetic) cannot win.
def test_substance_rejects_cheating_patches():
    assert patch_substance_score(_TEST_PATCH, _IMPL_PATCH) > 0.8        # real source change → high
    only_test = ("--- a/tests/test_feature.py\n+++ b/tests/test_feature.py\n@@ -1,3 +1,3 @@\n from feature import f\n"
                 " def test_f():\n-    assert f() == 42\n+    assert f() == 0\n")
    assert patch_substance_score(_TEST_PATCH, only_test) == 0.0          # only edits the test
    skip_impl = ("--- a/feature.py\n+++ b/feature.py\n@@ -1,2 +1,3 @@\n def f():\n"
                 "+    import pytest; pytest.skip('later')\n     return 0\n")
    assert patch_substance_score(_TEST_PATCH, skip_impl) == 0.0          # skips the test
    cosmetic = "--- a/feature.py\n+++ b/feature.py\n@@ -1,1 +1,2 @@\n def f():\n+    # a comment only\n     return 0\n"
    assert patch_substance_score(_TEST_PATCH, cosmetic) <= 0.1          # comment-only


# §7 — duplicates do not buy coverage: four near-identical candidates collapse to one cell, some get rejected.
def test_duplicate_candidates_do_not_increase_coverage():
    c = dict(_GOOD, test_patch="", implementation_patch="")
    dups = [dict(c, name=f"d{i}") for i in range(4)]                     # same assumption + claim
    r = llm_openended_search("design a rate limiter", _scripted([json.dumps(dups)]),
                             budget=4, samples_per_round=4)
    assert r.valid_count == 4 and r.duplicates_rejected >= 1
    assert r.archive.coverage() == 1                                    # one behavioral cell, not four


# §5 — bounded repair: invalid JSON first, corrected on repair → a valid candidate is recovered.
def test_json_repair_recovers_invalid_then_valid():
    rounds = iter(["this is not json"])

    def fn(p):
        if "fixing ONE broken field" in p:
            return json.dumps([_GOOD])                                  # the repair returns valid JSON
        return next(rounds, json.dumps([_GOOD]))
    r = llm_openended_search("x", CallableLLMProvider(fn), budget=1, samples_per_round=1, max_json_repairs=1)
    assert r.json_repairs >= 1 and r.valid_count >= 1


# §5 — bounded repair: the first impl is wrong (stays RED), the impl-repair fixes it → GREEN.
def test_impl_repair_turns_red_into_green():
    d = _temp_repo()
    try:
        impl_bad = "--- a/feature.py\n+++ b/feature.py\n@@ -1,2 +1,2 @@\n def f():\n-    return 0\n+    return 41\n"
        impl_fix = "--- a/feature.py\n+++ b/feature.py\n@@ -1,2 +1,2 @@\n def f():\n-    return 41\n+    return 42\n"
        cand = dict(_GOOD, implementation_patch=impl_bad)

        def fn(p):
            if "fixing ONE broken field" in p:
                return impl_fix
            return json.dumps([cand])
        r = llm_openended_search("x", CallableLLMProvider(fn), repo_path=d, budget=1, samples_per_round=1,
                                 materialize=True, max_impl_repairs=1)
        assert r.impl_repairs >= 1 and r.green_final_count >= 1
        assert "return 42" in (Path(d) / "feature.py").read_text()
    finally:
        import shutil
        shutil.rmtree(d, ignore_errors=True)


# §2 — a failed materialization rolls the repo back to its exact prior bytes (unless kept).
def test_failed_materialization_rolls_back_repo():
    d = _temp_repo()
    try:
        before = (Path(d) / "feature.py").read_text()
        impl_bad = "--- a/feature.py\n+++ b/feature.py\n@@ -1,2 +1,2 @@\n def f():\n-    return 0\n+    return 41\n"
        cand = dict(_GOOD, implementation_patch=impl_bad)               # RED then still RED (no green), no repair
        r = llm_openended_search("x", _scripted([json.dumps([cand])]), repo_path=d,
                                 budget=1, samples_per_round=1, materialize=True)
        assert r.green_final_count == 0
        assert (Path(d) / "feature.py").read_text() == before          # source restored
        assert not (Path(d) / "tests" / "test_feature.py").exists()    # the test file was rolled back too
    finally:
        import shutil
        shutil.rmtree(d, ignore_errors=True)


def test_keep_failed_preserves_the_workdir():
    d = _temp_repo()
    try:
        impl_bad = "--- a/feature.py\n+++ b/feature.py\n@@ -1,2 +1,2 @@\n def f():\n-    return 0\n+    return 41\n"
        cand = dict(_GOOD, implementation_patch=impl_bad)
        r = llm_openended_search("x", _scripted([json.dumps([cand])]), repo_path=d, budget=1,
                                 samples_per_round=1, materialize=True, keep_failed=True)
        assert r.green_final_count == 0
        assert (Path(d) / "tests" / "test_feature.py").exists()        # kept despite the failure
    finally:
        import shutil
        shutil.rmtree(d, ignore_errors=True)


def test_patch_transaction_rolls_back_on_exit_without_commit():
    d = _temp_repo()
    try:
        before = (Path(d) / "feature.py").read_text()
        plan = parse_unified_diff(_IMPL_PATCH)
        with PatchTransaction(d) as tx:
            assert tx.apply(plan)["applied"]
            assert "return 42" in (Path(d) / "feature.py").read_text()  # applied inside the transaction
        assert (Path(d) / "feature.py").read_text() == before          # rolled back on __exit__ (no commit)
    finally:
        import shutil
        shutil.rmtree(d, ignore_errors=True)


# §10 — telemetry is machine-readable (so improvement is distinguishable from mere LLM-call spend).
def test_result_to_dict_reports_telemetry():
    r = llm_openended_search("invent something", _scripted([json.dumps([_GOOD])]),
                             budget=4, samples_per_round=2)
    d = r.to_dict()
    for key in ("llm_call_count", "valid", "discarded", "materialized", "red_assertion",
                "red_collection", "green_final", "rebrands_blocked", "duplicates_rejected", "repairs"):
        assert key in d
