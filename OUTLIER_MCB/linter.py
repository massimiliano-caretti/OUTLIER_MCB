"""linter — an EPISTEMIC HONESTY linter for prose. Style linters (vale, alex, write-good) catch tone; none
rewrites a scientific over-claim ("breakthrough", "first", "state-of-the-art", "novel") into the strongest
form the evidence licenses. This scans text/files line by line through the library's own claim gate and reports
each over-reach with its honest rewrite. Default evidence assumes nothing proven, so bare strong claims flag —
pass evidence to license them. Deterministic, offline; a thin wrapper over gate_claim_language.
"""
from __future__ import annotations
from typing import Dict, List, Optional

from .claim_ladder import gate_claim_language

_DEFAULT_EVIDENCE = {"closure_escape": False, "prior_art_checked": False}


def lint_text(text: str, evidence: Optional[Dict] = None) -> List[Dict]:
    """Return one finding per line that over-claims: {line, original, rewritten, violations}. Only flagged
    lines are returned (a clean document returns [])."""
    ev = evidence if evidence is not None else _DEFAULT_EVIDENCE
    findings = []
    for i, line in enumerate((text or "").splitlines(), start=1):
        s = line.strip()
        if not s:
            continue
        g = gate_claim_language(s, ev)
        if not g["allowed"]:
            findings.append({"line": i, "original": s, "rewritten": g["rewritten"],
                             "violations": [v.get("word") for v in g.get("violations", [])]})
    return findings


def lint_file(path: str, evidence: Optional[Dict] = None) -> List[Dict]:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        findings = lint_text(fh.read(), evidence)
    for f in findings:
        f["path"] = path
    return findings


def lint_report(findings: List[Dict]) -> str:
    if not findings:
        return "OK — no over-claims found."
    lines = [f"{len(findings)} over-claim(s) found:"]
    for f in findings:
        loc = f.get("path", "") + (f":{f['line']}" if f.get("path") else f"line {f['line']}")
        lines.append(f"  {loc}: {f['violations']}")
        lines.append(f"    - was: {f['original']}")
        lines.append(f"    + fix: {f['rewritten']}")
    return "\n".join(lines)
