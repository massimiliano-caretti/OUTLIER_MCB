"""Mutation testing: a test must kill the mutants of the lines its own implementation changed."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_llm_loop import _temp_repo  # noqa: E402

from OUTLIER_MCB.llm_loop import _materialize  # noqa: E402
from OUTLIER_MCB.mutation import changed_lines, mutants  # noqa: E402
from OUTLIER_MCB.runner import CommandRunner  # noqa: E402

_IMPL = ("--- a/feature.py\n+++ b/feature.py\n@@ -1,2 +1,4 @@\n def f():\n-    return 0\n"
         "+    if g(5) > 0:\n+        return 42\n+    return -1\n")
_G = "\n\ndef g(x):\n    return x\n"
_STRONG = ("--- /dev/null\n+++ b/tests/test_feature.py\n@@ -0,0 +1,3 @@\n+from feature import f\n"
           "+def test_f():\n+    assert f() == 42\n")
_WEAK = ("--- /dev/null\n+++ b/tests/test_feature.py\n@@ -0,0 +1,3 @@\n+from feature import f\n"
         "+def test_f():\n+    assert f() != 0\n")


def _run(test_patch):
    repo = _temp_repo()
    Path(repo, "feature.py").write_text("def f():\n    return 0\n" + _G)
    ev = _materialize({"test_patch": test_patch, "implementation_patch": _IMPL}, repo,
                      runner=CommandRunner(), timeout=60, mutation_budget=4)
    return ev, repo


def test_mutants_only_touch_changed_lines():
    before = "def f():\n    return 0\n" + _G
    after = "def f():\n    if g(5) > 0:\n        return 42\n    return -1\n" + _G
    lines = changed_lines(before, after)
    assert lines == {2, 3, 4}
    ms = mutants(after, lines, max_mutants=10)
    assert ms and all(int(d.split("@L")[1]) in lines for d, _ in ms)
    assert mutants("def broken(:\n", None) == []


def test_strong_test_kills_mutants_weak_test_does_not_and_files_are_restored():
    strong, repo = _run(_STRONG)
    # f() == 42 kills the mutants on the taken branch; it never reaches `return -1`, and g(5) > 1 is still true —
    # exactly the coverage gap mutation testing exists to expose (keyword scoring would call this test perfect).
    assert strong["green_final"] and strong["mutants"] == 4 and strong["mutation_score"] == 0.5
    assert sorted(strong["mutant_survivors"]) == ["feature.py:return_none@L4", "feature.py:shift_constant@L2"]
    assert "return 42" in Path(repo, "feature.py").read_text()      # restored after mutation, idea kept
    weak, _ = _run(_WEAK)
    assert weak["green_final"] and weak["mutation_score"] == 0.0 and len(weak["mutant_survivors"]) == 4


def test_budget_zero_disables_mutation():
    repo = _temp_repo()
    ev = _materialize({"test_patch": _STRONG, "implementation_patch": _IMPL.replace("g(5) > 0", "True")}, repo,
                      runner=CommandRunner(), timeout=60, mutation_budget=0)
    assert ev["green_final"] and "mutation_score" not in ev


def test_prompt_carries_real_importable_symbols():
    from OUTLIER_MCB.llm_loop import _repo_block, _build_prompt
    from OUTLIER_MCB.qd import QDArchive
    import OUTLIER_MCB as gsl
    repo = _temp_repo()
    Path(repo, "limiter.py").write_text("def allow_request(key):\n    return True\n\nclass TokenBucket:\n    pass\n")
    block = _repo_block("invent a new rate limiter that decides allow_request", repo)
    assert "from limiter import allow_request, TokenBucket" in block
    assert "MODULES WITH NO TEST YET" in block and "limiter" in block
    assert _repo_block("anything", None) == ""
    pack = gsl.get_pack("coding")
    p = _build_prompt("x", pack, QDArchive(pack=pack), [], "", "", set(), 1, repo_block=block)
    assert "REPO SYMBOLS YOU CAN IMPORT" in p
