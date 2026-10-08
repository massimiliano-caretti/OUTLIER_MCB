"""Regression tests for the G5 audit: patch application security/atomicity, the shell-free runner, LLM JSON
extraction, verifier/materialize test detection, the arithmetic-only aesthetics evaluator, repo-semantics test
classification + caching, transactional self-repair, atomic/bounded memories and macro naming."""
import os
import sys
import time

import pytest

from OUTLIER_MCB import aesthetics, llm, materialize, verifier
from OUTLIER_MCB.patches import PatchTransaction, apply_patch_plan, parse_unified_diff, validate_patch_paths
from OUTLIER_MCB.runner import CommandRunner


def _w(path, text, mode="w"):
    os.makedirs(os.path.dirname(str(path)), exist_ok=True)
    with open(str(path), mode) as fh:
        fh.write(text)


def _r(path, mode="r"):
    with open(str(path), mode) as fh:
        return fh.read()


# ── patches: security gate ──
def test_patch_into_git_metadata_is_rejected(tmp_path):
    plan = parse_unified_diff("--- /dev/null\n+++ b/.git/hooks/pre-commit\n@@ -0,0 +1 @@\n+echo pwned\n")
    ok, errs = validate_patch_paths(plan, tmp_path)
    assert not ok and "VCS metadata" in errs[0]
    res = apply_patch_plan(plan, tmp_path)
    assert not res["applied"] and not (tmp_path / ".git").exists()


def test_patch_targeting_repo_root_is_rejected(tmp_path):
    ok, errs = validate_patch_paths(parse_unified_diff("--- a/.\n+++ b/.\n@@\n-x\n+y\n"), tmp_path)
    assert not ok and "repo root" in errs[0]


# ── patches: parsing real-world LLM / git diffs ──
def test_git_style_multi_file_diff_applies(tmp_path):
    _w(tmp_path / "a.py", "x = 1\ny = 2\n")
    _w(tmp_path / "b.py", "z = 3\n")
    diff = ("diff --git a/a.py b/a.py\nindex 111..222 100644\n--- a/a.py\n+++ b/a.py\n@@ -1,2 +1,2 @@\n"
            " x = 1\n-y = 2\n+y = 20\ndiff --git a/b.py b/b.py\nindex 333..444 100644\n--- a/b.py\n+++ b/b.py\n"
            "@@ -1 +1 @@\n-z = 3\n+z = 30\n")
    res = apply_patch_plan(parse_unified_diff(diff), tmp_path)
    assert res["applied"], res
    assert _r(tmp_path / "a.py") == "x = 1\ny = 20\n" and _r(tmp_path / "b.py") == "z = 30\n"


def test_fenced_diff_with_trailing_prose_applies(tmp_path):
    _w(tmp_path / "c.py", "q = 1\n")
    text = "Here is the fix:\n```diff\n--- a/c.py\n+++ b/c.py\n@@ -1 +1 @@\n-q = 1\n+q = 2\n```\nThis sets q.\n"
    assert apply_patch_plan(parse_unified_diff(text), tmp_path)["applied"]
    assert _r(tmp_path / "c.py") == "q = 2\n"


def test_removed_line_starting_with_double_dash_is_not_a_file_header(tmp_path):
    _w(tmp_path / "s.sql", "-- old comment\nSELECT 1;\n")
    plan = parse_unified_diff("--- a/s.sql\n+++ b/s.sql\n@@ -1,2 +1,2 @@\n--- old comment\n+-- new comment\n SELECT 1;\n")
    assert not plan.parse_errors and len(plan.files) == 1
    assert apply_patch_plan(plan, tmp_path)["applied"]
    assert _r(tmp_path / "s.sql") == "-- new comment\nSELECT 1;\n"


# ── patches: all-or-nothing application ──
def test_multi_file_patch_is_all_or_nothing(tmp_path):
    _w(tmp_path / "e.py", "e = 1\n")
    _w(tmp_path / "g.py", "g = 1\n")
    diff = "--- a/e.py\n+++ b/e.py\n@@\n-e = 1\n+e = 2\n--- a/g.py\n+++ b/g.py\n@@\n-NOT THERE\n+g = 2\n"
    res = apply_patch_plan(parse_unified_diff(diff), tmp_path)
    assert not res["applied"] and res["files"] == []
    assert _r(tmp_path / "e.py") == "e = 1\n"           # the first file was NOT half-applied


def test_removal_hunk_against_missing_file_is_an_error(tmp_path):
    res = apply_patch_plan(parse_unified_diff("--- a/f.py\n+++ b/f.py\n@@\n-nomatch\n+zz\n"), tmp_path)
    assert not res["applied"] and not (tmp_path / "f.py").exists()


def test_binary_and_directory_targets_do_not_crash(tmp_path):
    _w(tmp_path / "bin.dat", b"\xff\xfe\x00\x81", mode="wb")
    (tmp_path / "pkgdir").mkdir()
    r1 = PatchTransaction(str(tmp_path)).apply(parse_unified_diff("--- a/bin.dat\n+++ b/bin.dat\n@@\n-x\n+y\n"))
    r2 = apply_patch_plan(parse_unified_diff("--- a/pkgdir\n+++ /dev/null\n@@\n-x\n"), tmp_path)
    assert not r1["applied"] and not r2["applied"]
    assert _r(tmp_path / "bin.dat", "rb") == b"\xff\xfe\x00\x81" and (tmp_path / "pkgdir").is_dir()


def test_crlf_is_preserved_on_apply_and_rollback_is_byte_exact(tmp_path):
    _w(tmp_path / "w.py", b"a = 1\r\nb = 2\r\n", mode="wb")
    plan = parse_unified_diff("--- a/w.py\n+++ b/w.py\n@@\n-a = 1\n+a = 5\n")
    with PatchTransaction(str(tmp_path)) as tx:
        assert tx.apply(plan)["applied"]
        assert _r(tmp_path / "w.py", "rb") == b"a = 5\r\nb = 2\r\n"
    assert _r(tmp_path / "w.py", "rb") == b"a = 1\r\nb = 2\r\n"


# ── runner ──
def test_runner_unbalanced_quote_is_a_result_not_a_crash():
    r = CommandRunner().run("echo 'abc")
    assert not r.ok and "unparseable" in r.error


def test_runner_stdin_is_not_inherited():
    t = time.time()
    r = CommandRunner().run([sys.executable, "-c", "input()"], timeout=20)
    assert time.time() - t < 15 and not r.timed_out and r.returncode != 0     # EOFError, not a hang


@pytest.mark.skipif(os.name != "posix", reason="process groups are POSIX")
def test_runner_timeout_kills_grandchildren(tmp_path):
    marker = tmp_path / "survived"
    code = ("import subprocess, sys; subprocess.Popen([sys.executable, '-c', "
            "\"import time, pathlib; time.sleep(1.5); pathlib.Path(r'%s').write_text('x')\"]); "
            "import time; time.sleep(30)" % marker)
    r = CommandRunner().run([sys.executable, "-c", code], timeout=0.5)
    assert r.timed_out
    time.sleep(2.5)
    assert not marker.exists()                         # the grandchild died with the group


# ── LLM output parsing ──
def test_extract_json_returns_whole_object_with_array_field():
    assert llm._extract_json('{"name":"a","tags":["x","y"]}') == {"name": "a", "tags": ["x", "y"]}


def test_extract_json_fenced_and_after_citation():
    assert llm._extract_json('Here:\n```json\n{"name":"a","t":["x"]}\n```') == {"name": "a", "t": ["x"]}
    assert llm._extract_json('See [1]. {"name": "a"}') == {"name": "a"}
    assert llm._extract_json("no json here") is None


def test_parse_candidates_single_object_with_list_field_is_valid():
    obj = ('{"name":"n","broken_assumption":"b","claim":"c","world_test_description":"w",'
           '"tags":["x"]}')
    pr = llm.parse_candidates(obj)
    assert len(pr.valid) == 1 and pr.valid[0]["name"] == "n"


def test_callable_provider_inner_typeerror_is_not_retried():
    calls = []

    def bad(prompt):
        calls.append(prompt)
        raise TypeError("inner bug")
    with pytest.raises(TypeError, match="inner bug"):
        llm.CallableLLMProvider(bad).complete("x")
    assert len(calls) == 1
    assert llm.CallableLLMProvider(lambda p, n: ["b"] * n).complete("x", n=2) == ["b", "b"]


# ── verifier / materialize ──
class _Check:
    grounded = True
    pass_condition = "ok"

    def __init__(self, command="", test_name=""):
        self.command, self.test_name = command, test_name


def test_run_check_with_unbalanced_quote_does_not_crash():
    v = verifier.run_check(_Check("pytest -k 'abc"))
    assert not v.ran and v.passed is None


def test_test_detection_is_word_bounded(tmp_path):
    _w(tmp_path / "test_q.py", "# mentions test_foo in a comment\ndef test_foo_bar():\n    pass\n")
    assert materialize._test_absent("test_foo", tmp_path)
    assert not verifier.materialized(_Check(test_name="test_foo"), str(tmp_path))
    _w(tmp_path / "test_r.py", "def test_foo():\n    assert 1\n")
    assert not materialize._test_absent("test_foo", tmp_path)
    assert verifier.materialized(_Check(test_name="test_foo"), str(tmp_path))


def test_test_detection_skips_venv(tmp_path):
    _w(tmp_path / ".venv" / "lib" / "test_v.py", "def test_only_in_venv():\n    pass\n")
    assert materialize._test_absent("test_only_in_venv", tmp_path)


def test_llm_loop_test_command_uses_this_interpreter_and_guards_option_paths():
    from OUTLIER_MCB.llm_loop import _test_command
    cmd = _test_command(parse_unified_diff("--- /dev/null\n+++ b/tests/test_x.py\n@@\n+def test_x(): pass\n"), ".")
    assert cmd[0] == sys.executable and "tests/test_x.py" in cmd
    cmd2 = _test_command(parse_unified_diff("--- /dev/null\n+++ b/--basetemp=test_x.py\n@@\n+x\n"), ".")
    assert "./--basetemp=test_x.py" in cmd2 and "--basetemp=test_x.py" not in cmd2


# ── aesthetics: arithmetic only, bounded ──
def test_aesthetics_eval_refuses_escapes_and_huge_powers():
    assert aesthetics._eval("().__class__.__mro__[1].__subclasses__()", {}) is None
    t = time.time()
    assert aesthetics._eval("a + b**9**9**9", {"a": 1.0, "b": 2.0}) is None
    assert aesthetics.measure_symmetry("a + b**9**9**9") >= 0.0
    assert time.time() - t < 5
    assert aesthetics._eval("m*c**2", {"m": 2.0, "c": 3.0}) == 18.0
    assert aesthetics.aesthetics_objectivity_pass()


# ── repo semantics ──
def test_repo_semantics_test_classification_is_repo_relative(tmp_path):
    from OUTLIER_MCB.repo_semantics import analyze_repo_semantics
    root = tmp_path / "tests" / "proj"
    _w(root / "core.py", "def f():\n    return 1\n")
    _w(root / "latest.py", "def g():\n    return 1\n")
    _w(root / "tests" / "test_core.py", "from core import f\ndef test_f():\n    assert f() == 1\n")
    m = analyze_repo_semantics(str(root))
    assert not m.modules["core"].is_test and not m.modules["latest"].is_test
    assert m.modules["tests.test_core"].is_test
    assert "latest" in m.modules_without_tests()


def test_repo_world_model_is_cached_and_invalidated(tmp_path):
    from OUTLIER_MCB.repo_semantics import repo_world_model
    _w(tmp_path / "core.py", "def f():\n    return 1\n")
    a = repo_world_model(str(tmp_path))
    assert repo_world_model(str(tmp_path)) is a
    _w(tmp_path / "extra.py", "def brand_new_symbol():\n    return 2\n")
    b = repo_world_model(str(tmp_path))
    assert b is not a and "brand_new_symbol" in b.all_symbols()


# ── self-repair transaction ──
def test_self_repair_rolls_back_when_apply_raises():
    from OUTLIER_MCB.self_repair import RepairProposal, evolutionary_self_repair
    from OUTLIER_MCB.self_diagnosis import DiagnosticMemory
    state = {"x": 0}

    def apply():
        state["x"] = 1
        raise RuntimeError("boom")

    def rollback():
        state["x"] = 0
    mem = DiagnosticMemory()
    res = evolutionary_self_repair(RepairProposal("p", apply, rollback), measure=lambda: 1.0, invariants=[],
                                   memory=mem)
    assert not res.accepted and res.rolled_back and "boom" in res.reason
    assert state["x"] == 0 and len(mem.runs) == 1


# ── memories: atomic + bounded ──
def test_failed_save_keeps_previous_memory_file(tmp_path):
    from OUTLIER_MCB.discovery_memory import DiscoveryMemory
    from OUTLIER_MCB.memory import EpisodicMemory, Episode
    from OUTLIER_MCB.self_diagnosis import DiagnosticMemory
    p = str(tmp_path / "dm.json")
    m = DiscoveryMemory()
    m.record("a", "X", "d", True)
    m.save(p)
    m.promote("b", "Y", "d", note=object())          # not JSON-serializable
    with pytest.raises(TypeError):
        m.save(p)
    assert DiscoveryMemory.load(p).outcomes            # the previous file is intact, not truncated
    e = EpisodicMemory()
    e.record(Episode(problem="p"))
    e.save(str(tmp_path / "ep.json"))
    assert len(EpisodicMemory.load(str(tmp_path / "ep.json")).episodes) == 1
    d = DiagnosticMemory()
    d.save(str(tmp_path / "diag.json"))
    assert DiagnosticMemory.load(str(tmp_path / "diag.json")).runs == []
    assert [f for f in os.listdir(str(tmp_path)) if f.startswith(".tmp_")] == []


def test_memories_do_not_grow_without_bound():
    from OUTLIER_MCB.discovery_memory import DiscoveryMemory
    from OUTLIER_MCB.memory import EpisodicMemory, Episode
    m = DiscoveryMemory()
    for _ in range(50):
        m.promote("b", "Y", "d", note="n")
    assert len(m.discovered) == 1
    e = EpisodicMemory(max_episodes=10)
    for i in range(25):
        e.record(Episode(problem=f"p{i}"))
    assert len(e.episodes) == 10 and e.episodes[-1].problem == "p24"


# ── language inventor ──
def test_invented_macro_never_overwrites_an_existing_one():
    from OUTLIER_MCB.language_inventor import FormalLanguage, invent_new_language
    base = FormalLanguage("b", {"inc": lambda x: x + 1, "dbl": lambda x: x * 2}, macros={"m1": ("inc", "dbl")})
    probs = [[(1, ((1 + 1) * 2 + 1) * 2), (2, ((2 + 1) * 2 + 1) * 2)],
             [(3, ((3 + 1) * 2 + 1) * 2 + 1), (0, ((0 + 1) * 2 + 1) * 2 + 1)]]
    lang = invent_new_language(base, probs, max_len=4)
    assert lang.macros["m1"] == ("inc", "dbl")
    for name in lang.macros:
        lang.run([name], 1)                            # no self-referential macro → no RecursionError


# ── evals edge input ──
def test_self_improve_with_no_equations_does_not_divide_by_zero():
    from evals.self_improve_loop import self_improve
    res = self_improve(epochs=1, equations=[])
    assert res.start_fitness == 0.0 and all(r.total == 0 for r in res.trajectory)


def test_scrubbed_env_drops_credentials_keeps_path():
    from OUTLIER_MCB.runner import scrubbed_env
    env = scrubbed_env({"X": "1"}, base={"PATH": "/bin", "OPENAI_API_KEY": "s", "GITHUB_TOKEN": "t",
                                         "AWS_SECRET_ACCESS_KEY": "u", "HOME": "/h"})
    assert env == {"PATH": "/bin", "HOME": "/h", "X": "1"}
