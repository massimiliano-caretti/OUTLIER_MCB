"""test_repo_semantics — #2 semantic repo grounding. AST analysis of a real (fixture) repo: functions,
classes, imports, call graph, test→module map, impact surface, file-anchored falsifiers, and the rule that a
proposal touching no behavior is NOT grounded. Offline, deterministic. Includes the discrimination ablation."""
import os
import OUTLIER_MCB as m
from OUTLIER_MCB.repo_semantics import (analyze_repo_semantics, repo_world_model, impact_surface,
                                           suggest_repo_falsifiers, is_grounded, repo_grounding_ablation)


def _fixture(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "pkg" / "core.py").write_text(
        "def rate_limit(x):\n    return x\n\nclass Bucket:\n    def fill(self):\n        return 1\n")
    (tmp_path / "pkg" / "api.py").write_text(
        "from pkg.core import rate_limit\n\ndef serve(r):\n    return rate_limit(r)\n")
    (tmp_path / "tests" / "test_core.py").write_text(
        "from pkg import core\n\ndef test_rate_limit():\n    assert core.rate_limit(1) == 1\n")
    return str(tmp_path)


def test_detects_functions_classes_and_imports(tmp_path):
    model = analyze_repo_semantics(_fixture(tmp_path))
    syms = model.all_symbols()
    assert {"rate_limit", "serve", "Bucket"} <= syms
    assert model.public_api()["pkg.core"] == ["rate_limit", "Bucket"]
    assert "rate_limit" in model.call_graph["pkg.api"]          # api calls core.rate_limit (in-repo edge)


def test_links_tests_to_modules_and_finds_untested(tmp_path):
    model = analyze_repo_semantics(_fixture(tmp_path))
    assert model.test_map["tests.test_core"] == ["pkg.core"]    # the test is mapped to the module it imports
    assert model.modules_without_tests() == ["pkg.api"]         # api has public API but no test → opportunity


def test_impact_surface_and_file_anchored_falsifiers(tmp_path):
    model = repo_world_model(_fixture(tmp_path))
    surf = impact_surface("change how rate_limit behaves under burst", model)
    assert surf["grounded"] and "rate_limit" in surf["symbols"] and "pkg.core" in surf["modules"]
    fals = suggest_repo_falsifiers("rate_limit", model)
    assert fals and fals[0]["module"] == "pkg.core" and fals[0]["file"].endswith("core.py")
    assert "RED" in fals[0]["falsifier"]                        # a concrete currently-failing test


def test_a_proposal_touching_no_behavior_is_not_grounded(tmp_path):
    model = analyze_repo_semantics(_fixture(tmp_path))
    assert is_grounded("rate_limit smarter", model) is True
    assert is_grounded("an abstract philosophical musing about nothing concrete", model) is False
    assert suggest_repo_falsifiers("an abstract philosophical musing", model) == []   # nothing real to falsify


def test_grounding_ablation_discriminates(tmp_path):
    model = analyze_repo_semantics(_fixture(tmp_path))
    ab = repo_grounding_ablation(model)
    assert ab["grounding_discriminates"] is True
    assert ab["real_grounded"] and not ab["decorative_grounded"]
    assert ab["real_falsifiers"] > ab["decorative_falsifiers"] == 0


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
