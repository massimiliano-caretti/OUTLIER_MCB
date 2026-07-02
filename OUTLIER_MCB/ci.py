"""ci — novelty/honesty as a REGRESSION GATE. pytest tests code and great_expectations validates data; nothing
makes the build FAIL when a "novel" idea is really INSIDE_THE_BOX, or when a public claim overreaches its
evidence. These assertions turn the library's verdicts into test primitives you can drop into any suite/CI.
Pure wrappers over judge + gate_claim_language; they only raise AssertionError — no core path changes.
"""
from __future__ import annotations
from typing import Dict, Optional

from .judge import judge
from .claim_ladder import gate_claim_language


class NoveltyRegression(AssertionError):
    """Raised when an idea claimed to be novel is INSIDE_THE_BOX."""


class ClaimOverreach(AssertionError):
    """Raised when a claim asserts more than its evidence licenses."""


def assert_outside_the_box(idea: str, pack=None, prompt: Optional[str] = None) -> None:
    """Fail (NoveltyRegression) if `idea` reduces to the box. Use in tests/CI to guarantee a design keeps
    breaking a real assumption and never silently regresses into a rename of a known method."""
    j = judge(idea, prompt=prompt, pack=pack) if pack is not None else judge(idea, prompt=prompt)
    if j.verdict == "INSIDE_THE_BOX":
        inside = (j.closure or {}).get("inside_closure") if isinstance(getattr(j, "closure", None), dict) else None
        detail = f" (inside «{inside}»)" if inside else ""
        raise NoveltyRegression(f"INSIDE_THE_BOX{detail}: {j.next_step or 'breaks no axis'} — idea: {idea!r}")


def assert_claim_honest(text: str, evidence: Optional[Dict] = None) -> None:
    """Fail (ClaimOverreach) if `text` claims more than `evidence` supports; the error carries the honest
    rewrite. Default evidence assumes nothing proven, so unearned strong words (breakthrough/first/novel) fail
    until you supply evidence={'closure_escape': ..., 'prior_art_checked': ...}."""
    ev = evidence if evidence is not None else {"closure_escape": False, "prior_art_checked": False}
    g = gate_claim_language(text, ev)
    if not g["allowed"]:
        raise ClaimOverreach(f"claim overreaches evidence — allowed form: {g['rewritten']!r} "
                             f"(violations: {[v.get('word') for v in g.get('violations', [])]})")
