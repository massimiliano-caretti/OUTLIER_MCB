"""materialize — does an artifact contract actually MATERIALIZE red-first against the real repo?

`artifact_specificity` only asks "are the contract fields non-empty?". That is gameable: a contract can be
field-complete yet name a test file that does not exist, a command that runs the whole suite (so it passes
without the new test), or a test that is ALREADY present (so there is nothing red to flip). A world-test
that is not red BEFORE the change certifies nothing.

`materialization_score` is the stronger, grounded check. It reads the REAL filesystem and asks the four
questions that make a contract a genuine red→green bet:

  • target_exists          — the file the contract points at is really on disk (or sits next to a real file);
  • command_selects_test   — the command targets the SPECIFIC named test (`-k <test>`), not the whole suite,
                             so it cannot pass just because the existing suite is green;
  • test_absent_today      — that test is NOT already in the repo → it is genuinely RED right now (red-first);
  • baseline_red_stated    — the contract explicitly states the current red/absent baseline.

It is deterministic and offline (it only reads files under `repo_root`). It is INDEPENDENT of
artifact_specificity by construction: a field-complete contract can still score low here (missing target,
suite-wide command, or a test that already exists). Reports a number in [0,1]; settles nothing by itself.
"""
from __future__ import annotations
from pathlib import Path
from typing import Dict

_RED_WORDS = ("red", "absent", "unrepresented", "lacks", "lack", "missing", "fail", "no test")


def _contract_dict(check) -> Dict:
    """Accept either a RepoCheck (with attributes) or the standardized artifact_contract dict."""
    if isinstance(check, dict):
        return check
    return {"target": getattr(check, "target", ""), "test_name": getattr(check, "test_name", ""),
            "command": getattr(check, "command", ""), "baseline_assertion": getattr(check, "baseline_assertion", ""),
            "grounded": getattr(check, "grounded", False)}


def _target_resolves(target: str, root: Path) -> bool:
    """The contract's target names a real file (relative or absolute), or 'a new test next to <real file>'."""
    if not target:
        return False
    # 'a new test next to tests/foo.py' / 'a new test next to /abs/foo.py' → check the referenced file
    if " next to " in target:
        ref = target.split(" next to ", 1)[1].strip().strip("`")
        return (root / ref).exists() or Path(ref).exists()
    cleaned = target.strip().strip("`")
    return (root / cleaned).exists() or Path(cleaned).exists()


def _test_absent(test_name: str, root: Path) -> bool:
    """The named test is NOT defined anywhere under root → it is genuinely red/absent today (red-first)."""
    if not test_name:
        return False
    needle = f"def {test_name}"
    for f in root.rglob("*.py"):
        if "__pycache__" in str(f):
            continue
        try:
            if needle in f.read_text(errors="ignore"):
                return False
        except OSError:
            continue
    return True


def materialization_evidence(check, repo_root) -> Dict[str, bool]:
    """The four red-first facts, checked against the real filesystem under `repo_root`."""
    c = _contract_dict(check)
    root = Path(repo_root)
    test_name, command, baseline = c.get("test_name", ""), c.get("command", ""), c.get("baseline_assertion", "")
    return {
        "target_exists": _target_resolves(c.get("target", ""), root),
        "command_selects_test": bool(test_name) and test_name in (command or ""),
        "test_absent_today": _test_absent(test_name, root),
        "baseline_red_stated": bool(baseline.strip()) and any(w in baseline.lower() for w in _RED_WORDS),
    }


def materialization_score(check, repo_root) -> float:
    """Fraction of the four red-first materialization facts that hold, in [0,1]. 1.0 ⇒ the contract is a
    real, selectable, currently-red test against this repo; lower ⇒ it is a SPEC, not yet a materialized bet."""
    ev = materialization_evidence(check, repo_root)
    return round(sum(1 for v in ev.values() if v) / len(ev), 3)
