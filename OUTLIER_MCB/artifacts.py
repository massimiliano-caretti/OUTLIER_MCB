"""artifacts — classify and validate a RepoCheck as a real, runnable artifact contract.

A world-test is only as honest as the artifact it points to. This module distinguishes a check the
engine could actually settle from one that only LOOKS complete, without running anything destructive:

  AUTO_MATERIALIZED   grounded, full contract, AND the named test already exists in the repo
  AUTO_CONTRACT_ONLY  grounded, full contract, but the test is not written yet (the assistant must)
  HUMAN_ONLY          no runnable check — a conceptual claim a person must build and judge
  INVALID             the contract is missing required fields — not a world-test at all

Collaborators: verifier.materialized / validate_artifact_contract (the file-level facts).
"""
from __future__ import annotations
from typing import List

AUTO_MATERIALIZED = "AUTO_MATERIALIZED"
AUTO_CONTRACT_ONLY = "AUTO_CONTRACT_ONLY"
HUMAN_ONLY = "HUMAN_ONLY"
INVALID = "INVALID"

_CONTRACT_FIELDS = ("command", "target", "test_name", "baseline_assertion",
                    "negative_control", "success_condition", "implementation_hint")


def validate_artifact_contract(check, repo=None) -> List[str]:
    """Return the contract fields that are missing ([] = a complete artifact contract)."""
    return [f for f in _CONTRACT_FIELDS if not str(getattr(check, f, "")).strip()]


def artifact_contract_score(check) -> float:
    """Fraction of the artifact contract that is filled — a full check scores 1.0, a bare command ~0.14."""
    filled = sum(1 for f in _CONTRACT_FIELDS if str(getattr(check, f, "")).strip())
    return round(filled / len(_CONTRACT_FIELDS), 3)


def materialized_artifact(check, root: str = ".") -> bool:
    """Has the named test actually been written into the repo?"""
    from .verifier import materialized
    return materialized(check, root)


def expected_test_present(check, root: str = ".") -> bool:
    """Alias: is the check's expected test present in the repo?"""
    return materialized_artifact(check, root)


def artifact_class(check, root: str = None) -> str:
    """Classify the check into one of the four honest classes."""
    if validate_artifact_contract(check):
        return INVALID
    if not getattr(check, "grounded", False) or not getattr(check, "is_full_contract", False):
        return HUMAN_ONLY
    if root is not None and materialized_artifact(check, root):
        return AUTO_MATERIALIZED
    return AUTO_CONTRACT_ONLY
