"""divergent_runner — run the human-like divergent protocols COMPETITIVELY (improvement #7).

The pieces already exist (SCAMPER, Geneplore, remote association, fixedness-breaking, provocation, random
entry, conceptual blending). This runs them against each other: each protocol proposes falsifiable candidates,
they are scored by ORIGINALITY (distance from the box), a UCB bandit learns which protocols pay off, and a
protocol that never produces an original, falsifiable candidate is DROPPED. Divergence is not 'run everything'
— it is 'keep spending where invention actually happens'. Every kept candidate still owes its death to an
evaluator: this stage only GENERATES.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


def _protocols() -> Dict[str, Callable]:
    """name -> (problem, pack) -> List[Candidate]. Each draws on an existing generator; all are falsifiable."""
    from .cognitive_protocols import scamper, geneplore, remote_association, functional_fixedness_breaker
    from .lateral import provocation, random_entry
    from .generators import conceptual_blend

    def _moves(fn):
        return lambda p, pk: [m.candidate for m in fn(p, pk)]

    def _blend(p, pk):
        from .pack import list_packs, get_pack
        foreign = next((get_pack(n) for n in list_packs() if n not in (pk.name, "generic")), None)
        c = conceptual_blend(pk, foreign) if foreign else None
        return [c] if c is not None else []

    return {
        "scamper": _moves(scamper),
        "geneplore": _moves(geneplore),
        "remote_association": _moves(remote_association),
        "fixedness": _moves(functional_fixedness_breaker),
        "provocation": lambda p, pk: [c for c in [provocation(pk)] if c is not None],
        "random_entry": lambda p, pk: [c for c in [random_entry(pk)] if c is not None],
        "blend": _blend,
    }


def _originality(candidate, pack) -> float:
    """Distance of a candidate from the domain box, in [0,1] — the lateral-thinking signal."""
    from .embeddings import semantic_distance
    text = f"{getattr(candidate, 'name', '')} {getattr(candidate, 'negation', '')}"
    return round(semantic_distance(text, getattr(pack, "box_name", "")), 3)


def _falsifiable(candidate) -> bool:
    return bool(str(getattr(candidate, "discipline", "")).strip())


def score_protocol_output(candidates, pack) -> Dict:
    """Score a protocol's output: mean originality of its FALSIFIABLE candidates, and the falsifiable rate.
    A protocol that produces nothing falsifiable scores 0 — generativity without a falsifier does not count."""
    if not candidates:
        return {"originality": 0.0, "falsifiable_rate": 0.0, "n": 0, "n_falsifiable": 0}
    fals = [c for c in candidates if _falsifiable(c)]
    orig = round(sum(_originality(c, pack) for c in fals) / len(fals), 3) if fals else 0.0
    return {"originality": orig, "falsifiable_rate": round(len(fals) / len(candidates), 3),
            "n": len(candidates), "n_falsifiable": len(fals)}


def select_protocols_by_bandit(bandit) -> str:
    """Which protocol the UCB bandit would spend the next pull on."""
    return bandit.select()


@dataclass
class DivergentResult:
    problem: str
    candidates: List = field(default_factory=list)            # kept, falsifiable, original candidates
    protocol_scores: Dict[str, Dict] = field(default_factory=dict)
    kept: List[str] = field(default_factory=list)
    dropped: List[str] = field(default_factory=list)
    bandit: object = None

    def markdown(self) -> str:
        L = [f"## Divergent protocols — «{self.problem}» ({len(self.candidates)} candidates kept)"]
        for name, sc in sorted(self.protocol_scores.items(), key=lambda kv: -kv[1]["originality"]):
            mark = "✓" if name in self.kept else "✗"
            L.append(f"  {mark} {name}: originality {sc['originality']} · falsifiable {sc['falsifiable_rate']}")
        if self.dropped:
            L.append(f"- dropped (no original falsifiable output): {', '.join(self.dropped)}")
        return "\n".join(L)


def run_divergent_protocols(problem: str, pack, memory=None, provider=None, originality_floor: float = 0.15,
                            protocols: Optional[Dict[str, Callable]] = None) -> DivergentResult:
    """Run every protocol, score it, reward a UCB bandit by originality, and KEEP only protocols that produced
    an original, falsifiable candidate (≥ floor). The bandit learns where invention happens for the next round.
    `protocols` overrides the registry (used by the ablation to inject a decorative control)."""
    from .lateral import OperatorBandit
    registry = protocols if protocols is not None else _protocols()
    bandit = OperatorBandit(list(registry))
    result = DivergentResult(problem=problem, bandit=bandit)
    for name, fn in registry.items():
        try:
            cands = fn(problem, pack) or []
        except Exception:
            cands = []
        sc = score_protocol_output(cands, pack)
        result.protocol_scores[name] = sc
        bandit.record(name, sc["originality"] if sc["n_falsifiable"] else 0.0)
        productive = sc["n_falsifiable"] > 0 and sc["originality"] >= originality_floor
        if productive:
            result.kept.append(name)
            result.candidates.extend([c for c in cands if _falsifiable(c)])
        else:
            result.dropped.append(name)
    # de-duplicate kept candidates by name, keeping the first (stable)
    seen, deduped = set(), []
    for c in result.candidates:
        key = getattr(c, "name", str(c))
        if key not in seen:
            seen.add(key); deduped.append(c)
    result.candidates = deduped
    return result


def protocol_ablation(problem: str = "a new rate limiter", pack=None) -> Dict:
    """Ablation for #7: a real protocol (scamper) is kept; a DECORATIVE protocol (returns a non-falsifiable,
    box-restating candidate) is dropped. Proves the runner keeps spending only where invention happens."""
    from .pack import get_pack
    from .generators.base import Candidate
    pack = pack or get_pack("coding")

    def decorative(p, pk):
        return [Candidate(name="restate_the_box", operator="unify", breaks=[], assumptions=[],
                          negation=getattr(pk, "box_name", "the box"), discipline="")]   # no falsifier, no break

    from .cognitive_protocols import scamper
    registry = {"scamper": lambda p, pk: [m.candidate for m in scamper(p, pk)], "decorative": decorative}
    res = run_divergent_protocols(problem, pack, protocols=registry)
    return {"kept": res.kept, "dropped": res.dropped,
            "real_kept": "scamper" in res.kept, "decorative_dropped": "decorative" in res.dropped,
            "earns_keep": "scamper" in res.kept and "decorative" in res.dropped}
