"""assumption_graph — a TYPED graph of hidden assumptions (not a flat list).

Nodes = assumptions; edges carry a relation:
  implies · depends_on · blocks · if_false_requires · collapses_to · needs_new_data
The graph answers: which assumptions are CENTRAL (load-bearing), which are DERIVED, which are
BREAKABLE, and which break REQUIRES NEW DATA. It is built by the kernel from a DomainPack
(kernel.graph_of) and is completely domain-blind: every node carries its own dimension / box /
breakable flags, so no domain constants live here.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

RELATIONS = ("implies", "depends_on", "blocks", "if_false_requires", "collapses_to", "needs_new_data")


@dataclass
class AssumptionGraph:
    nodes: Dict[str, Dict] = field(default_factory=dict)   # name -> {description,in_box,dimension,breakable,falsifier}
    edges: List[Tuple[str, str, str, str]] = field(default_factory=list)   # (src, relation, dst, note)

    def out_edges(self, name: str, rel: Optional[str] = None):
        return [e for e in self.edges if e[0] == name and (rel is None or e[1] == rel)]

    def in_edges(self, name: str, rel: Optional[str] = None):
        return [e for e in self.edges if e[2] == name and (rel is None or e[1] == rel)]

    def degree(self, name: str) -> int:
        return len([e for e in self.edges if e[0] == name or e[2] == name])

    def central(self, top_k: int = 3) -> List[str]:
        """Load-bearing assumptions: most depended-on / implied (the box's pillars)."""
        score = {n: 0 for n in self.nodes}
        for s, r, d, _ in self.edges:
            if d in score and r in ("depends_on", "implies", "blocks"):
                score[d] += 2
            if s in score:
                score[s] += 1
        return [n for n, _ in sorted(score.items(), key=lambda kv: -kv[1])][:top_k]

    def breakable(self) -> List[str]:
        """Assumptions that map to a real exit axis → can be broken to leave the box."""
        return [n for n, info in self.nodes.items() if info.get("breakable")]

    def dimension_of(self, name: str) -> Optional[str]:
        return self.nodes.get(name, {}).get("dimension")

    def data_requirements(self) -> Dict[str, List[str]]:
        """assumption -> list of NEW DATA tokens its break requires (needs_new_data / if_false_requires)."""
        out: Dict[str, List[str]] = {}
        for s, r, d, _ in self.edges:
            if r in ("needs_new_data", "if_false_requires"):
                out.setdefault(s, [])
                if d not in out[s]:
                    out[s].append(d)
        return out

    def in_box(self, name: str) -> bool:
        return bool(self.nodes.get(name, {}).get("in_box"))

    def to_dict(self) -> Dict:
        return {"nodes": self.nodes,
                "edges": [{"src": s, "rel": r, "dst": d, "note": n} for s, r, d, n in self.edges]}

    def ascii(self) -> str:
        L = ["AssumptionGraph (central → derived):"]
        central = set(self.central(3))
        for n, info in self.nodes.items():
            tag = "★CENTRAL" if n in central else ("□box" if info.get("in_box") else "·")
            dim = info.get("dimension") or "—"
            L.append(f"  {tag:9s} {n:26s} axis={dim:13s} breakable={info.get('breakable')}")
        L.append("edges:")
        for s, r, d, note in self.edges:
            L.append(f"    {s} --{r}--> {d}    ({note})")
        return "\n".join(L)

    def mermaid(self) -> str:
        """A Mermaid flowchart of the graph — box assumptions in red, breakable ones in green, central ones
        starred; edges carry their relation. Deterministic (stable node ids), so it can be embedded directly
        in `creative()`'s brief or rendered by any Markdown viewer."""
        def safe(s):
            return "x" + "".join(ch if ch.isalnum() else "_" for ch in str(s))
        central = set(self.central(3))
        ids = {n: f"n{i}" for i, n in enumerate(self.nodes)}
        L = ["flowchart TD",
             "    classDef box fill:#ffe0e0,stroke:#cc3333;",
             "    classDef brk fill:#e0ffe0,stroke:#33aa33;"]
        for n, info in self.nodes.items():
            dim = info.get("dimension") or "—"
            label = f"{'★ ' if n in central else ''}{n}<br/>axis={dim}"
            cls = "box" if info.get("in_box") else ("brk" if info.get("breakable") else "")
            L.append(f'    {ids[n]}["{label}"]' + (f":::{cls}" if cls else ""))
        for s, r, d, _note in self.edges:
            if s not in ids:
                continue
            if d in ids:
                L.append(f"    {ids[s]} -->|{r}| {ids[d]}")
            else:                                       # an edge to an info token (needs_new_data target)
                L.append(f'    {safe(d)}(["{d}"])')
                L.append(f"    {ids[s]} -->|{r}| {safe(d)}")
        return "\n".join(L)
