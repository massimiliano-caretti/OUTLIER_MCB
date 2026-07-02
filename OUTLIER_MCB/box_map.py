"""box_map — make "the box" legible. Nobody visualises the space an idea must ESCAPE; this projects the
library's own creative preflight (assumption axes + the representation-closure lattice + admissible exits) into
a machine-readable map and a diagram, so a human can SEE which assumption to break. Pure composition of existing
exports (preflight_creative_request + CLOSURE_REGISTRY) — deterministic, offline, opt-in; changes no core path.
"""
from __future__ import annotations
from typing import Dict, List, Optional

from .preflight import preflight_creative_request
from .closures import CLOSURE_REGISTRY


def _closures_for(pf: Dict) -> List[Dict]:
    """The universal closures that govern this box (from the theorem brief and any declared pack closures)."""
    out, seen = [], set()
    tb = pf.get("theorem_brief") or {}
    names = []
    if isinstance(tb, dict) and tb.get("closure"):
        names.append(tb["closure"])
    pack = pf.get("pack")
    names += list(getattr(pack, "universal_closures", []) or [])
    for name in names:
        c = CLOSURE_REGISTRY.get(str(name).upper())
        if c and c.name not in seen:
            seen.add(c.name)
            out.append({"name": c.name, "theorem": c.theorem, "exits": list(c.exits)})
    return out


def _mermaid(box_name: str, axes: List[Dict], closures: List[Dict]) -> str:
    lines = ["graph TD", f'  BOX["THE BOX: {box_name[:60]}"]']
    for i, ax in enumerate(axes):
        aid = f"A{i}"
        lines.append(f'  {aid}["break {ax.get("assumption","?")}\\n(axis: {ax.get("dimension","?")})"]')
        lines.append(f"  BOX -->|escape via {ax.get('dimension','?')}| {aid}")
    for j, c in enumerate(closures):
        cid = f"C{j}"
        lines.append(f'  {cid}(["closure: {c["name"]}"])')
        lines.append(f"  BOX -.inside.-> {cid}")
        if c["exits"]:
            lines.append(f'  {cid} ==>|only exit| E{j}["{c["exits"][0][:48]}"]')
    return "\n".join(lines)


def box_map(problem: str, pack=None) -> Dict:
    """Return a structured MAP of the box for `problem`: the box being escaped, the breakable assumption axes,
    what must NOT be re-proposed, the governing representation-closures with their ONLY admissible exits, and a
    mermaid diagram string. Composes the library's own preflight — it asserts nothing new, it makes the existing
    creative analysis visible."""
    pf = preflight_creative_request(problem, pack) if pack is not None else preflight_creative_request(problem)
    axes = list(pf.get("three_breaks") or [])
    closures = _closures_for(pf)
    admissible = []
    for c in closures:
        admissible += c["exits"]
    tb = pf.get("theorem_brief") or {}
    if isinstance(tb, dict):
        admissible += list(tb.get("admissible_exits") or [])
    seen = set(); admissible = [e for e in admissible if not (e in seen or seen.add(e))]
    return {
        "problem": problem,
        "box_name": pf.get("box_name", ""),
        "axes": axes,
        "hidden_assumptions": list(pf.get("hidden_assumptions") or pf.get("central_assumptions") or []),
        "must_not_propose": list(pf.get("must_not_propose") or []),
        "closures": closures,
        "admissible_exits": admissible,
        "elicitation_required": bool(pf.get("elicitation_required")),
        "mermaid": _mermaid(pf.get("box_name", ""), axes, closures),
    }


def box_map_markdown(problem: str, pack=None) -> str:
    m = box_map(problem, pack)
    L = [f"# Box map — «{problem}»", f"**The box (do not re-propose):** {m['box_name']}", "", "## Breakable axes"]
    for ax in m["axes"]:
        L.append(f"- **{ax.get('dimension','?')}** — break `{ax.get('assumption','?')}`: {ax.get('why','')}")
    if m["closures"]:
        L.append("\n## Governing closures (inside = not novel) and their ONLY exits")
        for c in m["closures"]:
            L.append(f"- **{c['name']}** — {c['theorem']}")
            for e in c["exits"]:
                L.append(f"    - exit → {e}")
    if m["must_not_propose"]:
        L.append("\n## Forbidden (collage / known-dead): " + ", ".join(map(str, m["must_not_propose"])))
    if m["elicitation_required"]:
        L.append("\n> ⚠ Unknown domain: elicit families/sources before trusting these axes.")
    L.append("\n## Diagram (mermaid)\n```mermaid\n" + m["mermaid"] + "\n```")
    return "\n".join(L)
