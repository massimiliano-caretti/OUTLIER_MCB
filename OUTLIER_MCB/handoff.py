"""handoff — an OUTLIER_MCB AgentHandoffContract. When a parent agent hands a CREATIVE sub-task to a subagent,
free-text ("use the library") makes the discipline optional and unverifiable. This packages the discipline
into a small, machine-checkable contract and an ACCEPTANCE GATE that rejects a subagent's output on SUBSTANCE
(it must prove a broken assumption + a world-test + a bounded novelty claim), not on the mere presence of
fields — so the contract cannot degrade into bureaucracy.

Two conditions are wired in, exactly as the library's own analysis required:
  1) the contract CARRIES the route/context (route_snapshot + request) and the gate is fed the same pack, so
     the substance check (judge) is robust rather than phrasing-sensitive;
  2) the gate applies ONLY to creative handoffs (`creative=True`); routine sub-tasks bypass it, so we never
     impose the novelty bar where it would be pure bureaucracy.

Pure composition of shipped, tested primitives (assistant_route + assert_outside_the_box + assert_claim_honest
+ novelty_receipt). Opt-in; changes no core path.
"""
from __future__ import annotations
import re
from typing import Dict, List, Optional

from .activation import assistant_route
from .judge import judge
from .ci import assert_claim_honest, ClaimOverreach
from .receipt import novelty_receipt

SCHEMA_VERSION = "1.0"
# the substance-bearing fields a creative subagent must return (checked for substance, not just presence)
_REQUIRED = ("idea", "broken_assumption", "world_test", "claim")

# markers of a real falsification test: a condition under which the idea would FAIL (baseline/kill/control)
_KILL_MARKERS = ("fail", "falsif", "kill", "counterexample", "counter-example", "control", "baseline",
                 "worse", "does not", "would break", "breaks if", "unless", "reject", "collapse", "refut",
                 "must not", "should not", "drop", "no better than")


def _content_tokens(s) -> set:
    return {w.lower() for w in re.split(r"[^A-Za-z0-9]+", str(s or "")) if len(w) > 3}


def validate_world_test(world_test: str) -> bool:
    """A world-test is substantive only if it describes a situation that could make the idea FAIL — a kill /
    falsification condition (a baseline, a control, or a 'must reject / would break' clause). A placeholder
    like 'x' or 'we say there is a test' has no such condition and is rejected."""
    s = (world_test or "").strip().lower()
    return len(s) >= 12 and any(mk in s for mk in _KILL_MARKERS)


def validate_broken_assumption(declared: str, idea: str, route_break: Optional[str] = None,
                               judge_break: Optional[str] = None) -> bool:
    """A declared broken assumption is substantive only if it is a real statement (not a placeholder) that
    actually REFERS to the idea (or the route/judge-detected break) — and, when judge detected the real break,
    does not CONTRADICT it. This turns a presence-check into a substance-check: 'x' / 'we say so' are rejected;
    a statement that names something in the idea (e.g. 'subagent_success = task_completion') is accepted."""
    s = (declared or "").strip()
    if len(s) < 6 and "=" not in s and "->" not in s:
        return False                                   # bare placeholder ("x")
    d = _content_tokens(s)
    if not d:
        return False                                   # only stop-words ("we say so")
    jb = _content_tokens(judge_break)
    if jb:                                             # judge detected the real break → declared must be
        return bool(d & jb)                            # CONSISTENT with it (overlap), else it contradicts it
    return bool(d & (_content_tokens(idea) | _content_tokens(route_break)))   # must reference the idea/route


def handoff_contract(request: str, creative: Optional[bool] = None, pack=None, provider=None) -> Dict:
    """Build the contract to hand to a subagent. Snapshots the route (so context travels with the hand-off)
    and states what the subagent must report and how its output will be judged.

    `creative` defaults to the router's own decision (`route.activate`) so the contract is coherent with the
    router by default. An explicit True/False overrides it; when an override CONFLICTS with the router (e.g.
    the parent forces `creative=True` on a request the router would not activate), the snapshot records
    `forced_creative=True` so the incoherence is transparent, not hidden. For a non-creative handoff the
    substance gate is intentionally NOT applied (anti-bureaucracy)."""
    route = assistant_route(request, pack=pack, provider=provider)
    activate = bool(getattr(route, "activate", False))
    resolved = activate if creative is None else bool(creative)
    snapshot = {k: getattr(route, k, None) for k in
                ("prompt", "activate", "action", "entrypoint", "pack",
                 "break_assumption", "break_axis", "novelty_scope_required")}
    snapshot["forced_creative"] = bool(resolved and not activate)   # explicit override that conflicts w/ router
    route_must = list(getattr(route, "must_report", None) or [])
    must_report = list(_REQUIRED) + [f for f in route_must if f not in _REQUIRED]
    return {
        "schema_version": SCHEMA_VERSION,
        "request": request,
        "creative": resolved,
        "route_snapshot": snapshot,                 # condition 1: context travels with the contract
        "must_report": must_report,
        "acceptance": "substance" if resolved else "task_completion",
    }


def accept_handoff(output: Dict, contract: Dict, pack=None, evidence: Optional[Dict] = None) -> Dict:
    """Accept or reject a subagent's output against its contract. For a non-creative handoff the gate is
    skipped (accepted). For a creative handoff the output is accepted ONLY if every required field is present
    AND passes the SUBSTANCE checks: the idea does not reduce to the box (judge, fed the same pack/context as
    condition 1) and the claim does not overreach its evidence. On acceptance a tamper-evident novelty_receipt
    is attached. Returns {accepted, reasons, skipped, receipt}."""
    if not contract.get("creative", True):
        return {"accepted": True, "reasons": [], "skipped": True, "receipt": None,
                "note": "routine (non-creative) handoff — substance gate intentionally not applied"}

    reasons: List[str] = []
    for f in _REQUIRED:
        if not str(output.get(f, "") or "").strip():
            reasons.append(f"missing required field: {f}")
    if reasons:                                     # presence gate first (cheap), before the substance gate
        return {"accepted": False, "reasons": reasons, "skipped": False, "receipt": None}

    prompt = contract.get("request")
    idea = output["idea"]
    j = judge(idea, pack=pack, prompt=prompt) if pack is not None else judge(idea, prompt=prompt)

    # SUBSTANCE 1 — the idea must not reduce to the average answer
    if j.verdict == "INSIDE_THE_BOX":
        step = (j.next_step or "breaks no axis")
        reasons.append(f"INSIDE_THE_BOX — the idea reduces to the average answer ({str(step)[:70]})")
    # SUBSTANCE 2 — the declared broken assumption must be real and (when a pack grounds the detected break)
    # consistent with it. Without a pack, judge's broken_assumption is a generic axis label, too coarse to
    # enforce token-consistency against a domain-specific statement — so we only check it references the idea.
    route_break = (contract.get("route_snapshot") or {}).get("break_assumption")
    detected_break = getattr(j, "broken_assumption", None) if pack is not None else None
    if not validate_broken_assumption(output["broken_assumption"], idea, route_break, detected_break):
        reasons.append("broken_assumption is not substantive (placeholder, or inconsistent with the "
                       "assumption the idea actually breaks)")
    # SUBSTANCE 3 — the world-test must carry a real kill/falsification condition, not a placeholder
    if not validate_world_test(output["world_test"]):
        reasons.append("world_test lacks a falsification/kill condition (no baseline / control / "
                       "'would fail / must reject' clause)")
    # SUBSTANCE 4 — the claim must match its evidence
    try:
        assert_claim_honest(output["claim"], evidence)
    except ClaimOverreach as e:
        reasons.append(f"over-claim — {str(e)[:90]}")

    accepted = not reasons
    receipt = novelty_receipt(output["idea"], prompt=prompt, pack=pack, evidence=evidence) if accepted else None
    return {"accepted": accepted, "reasons": reasons, "skipped": False, "receipt": receipt}


def handoff_report(result: Dict) -> str:
    if result.get("skipped"):
        return "ACCEPTED (routine handoff — substance gate not applied)."
    if result["accepted"]:
        h = (result.get("receipt") or {}).get("hash", "")
        return f"ACCEPTED — substance verified; receipt {h}"
    return "REJECTED:\n" + "\n".join(f"  - {r}" for r in result["reasons"])
