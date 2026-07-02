"""receipt — a serializable, tamper-evident NOVELTY/HONESTY RECEIPT for a claim. Competitors score novelty or
faithfulness; none emits a falsifiable certificate that anyone can re-check: the broken axis, the world-test
that would kill the idea, the closure verdict, the prior-art scope, and the strongest claim the evidence
licenses — plus a content hash. Pure composition of judge + closure gate + novelty_audit + the claim gate.
Deterministic and offline by default (no timestamp, no network) so the same claim yields the same receipt.
"""
from __future__ import annotations
import hashlib
import json
from typing import Dict, Optional

from .judge import judge
from .claim_ladder import gate_claim_language
from .closures import closure_escape_proven

SCHEMA_VERSION = "1.0"


def _s(v):
    """Coerce a judge field to a JSON-serialisable value: keep primitives/None, stringify anything else
    (e.g. a MissingInfoReport). Keeps the receipt hashable regardless of judge's internal object types."""
    return v if (v is None or isinstance(v, (str, int, float, bool))) else str(v)


def _canonical_hash(payload: Dict) -> str:
    body = {k: v for k, v in payload.items() if k != "hash"}
    # default=str keeps the hash robust to any non-JSON value that slips through (belt-and-suspenders)
    dumped = json.dumps(body, sort_keys=True, ensure_ascii=False, default=str)
    return "sha256:" + hashlib.sha256(dumped.encode()).hexdigest()[:32]


def novelty_receipt(idea: str, prompt: Optional[str] = None, pack=None, prior_art_provider=None,
                    evidence: Optional[Dict] = None, claim: Optional[str] = None) -> Dict:
    """Emit a falsifiable receipt for `idea`. Optional: `pack` (sharpens the broken axis + closure), a
    `prior_art_provider` (a real search — otherwise prior art is honestly UNCHECKED), `evidence` overrides, and
    the `claim` text to gate. The receipt never fabricates: unknown fields are null, unproven scopes stay
    provisional, and the max claim is exactly what gate_claim_language allows given the evidence present."""
    j = judge(idea, prompt=prompt, pack=pack) if pack is not None else judge(idea, prompt=prompt)
    closure = j.closure if isinstance(getattr(j, "closure", None), dict) else None

    # prior art: only a real provider yields a checked status; absence is UNCHECKED, never NO_PRIOR_ART
    if prior_art_provider is not None:
        from .novelty import novelty_audit
        na = novelty_audit(idea, prior_art_provider)
        prior_art = {"status": na.status, "scope": na.novelty_scope or na.claim_scope or "",
                     "provisional": bool(na.provisional), "confidence": round(float(na.confidence), 2),
                     "sources_searched": na.sources_searched}
        # HONEST: only a REAL online prior-art check counts. An offline/lexical corpus is capped at
        # INCOMPLETE by honest_prior_art_status, so it must NOT license a novelty claim here either.
        prior_art_checked = (getattr(na, "novelty_scope", "") == "ONLINE_PRIOR_ART_CHECKED")
    else:
        prior_art = {"status": "PRIOR_ART_UNCHECKED", "provisional": True, "sources_searched": 0}
        prior_art_checked = False

    # CONSERVATIVE consistency: credit a closure-escape only if the structural gate proves it AND judge does
    # not rule the idea INSIDE_THE_BOX. A certificate must never grant an escape the verdict does not endorse.
    escape = (j.verdict != "INSIDE_THE_BOX") and bool(closure_escape_proven(idea, pack)) if pack is not None else False
    ev = evidence if evidence is not None else {"closure_escape": escape, "prior_art_checked": prior_art_checked}
    ev = {k: _s(v) for k, v in ev.items()}          # sanitize caller-supplied evidence so the receipt stays serialisable
    claim_text = claim or f"{idea} — a novel contribution"
    g = gate_claim_language(claim_text, ev)

    receipt = {
        "schema_version": SCHEMA_VERSION,
        "idea": idea,
        "verdict": j.verdict,
        "broken_axis": _s(getattr(j, "broken_assumption", None)),
        "world_test": _s(getattr(j, "testability_request", None)),
        "closure_verdict": {"inside_closure": (closure or {}).get("inside_closure"),
                            "closure_escape_proven": escape},
        "prior_art": prior_art,
        "max_claim_allowed": g["rewritten"],
        "claim_as_written_allowed": bool(g["allowed"]),
        "evidence_used": ev,
    }
    receipt["hash"] = _canonical_hash(receipt)
    return receipt


def verify_receipt(receipt: Dict) -> bool:
    """Re-check a receipt's content hash — True iff it has not been tampered with since issue."""
    return isinstance(receipt, dict) and receipt.get("hash") == _canonical_hash(receipt)


def receipt_markdown(receipt: Dict) -> str:
    r = receipt
    pa = r["prior_art"]
    return "\n".join([
        f"## Novelty/Honesty Receipt — «{r['idea']}»",
        f"- **verdict:** {r['verdict']}",
        f"- **broken axis:** {r['broken_axis']}",
        f"- **world-test (would kill it):** {r['world_test']}",
        f"- **closure:** inside={r['closure_verdict']['inside_closure']} · "
        f"escape_proven={r['closure_verdict']['closure_escape_proven']}",
        f"- **prior art:** {pa['status']} (provisional={pa.get('provisional')}, "
        f"sources={pa.get('sources_searched')})",
        f"- **max claim allowed:** {r['max_claim_allowed']}",
        f"- **hash:** `{r['hash']}` (re-checkable with verify_receipt)",
    ])
