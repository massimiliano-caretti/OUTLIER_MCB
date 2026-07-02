"""pack — the agnosticism boundary.

A DomainPack is ALL the domain knowledge the kernel needs, and the ONLY place domain knowledge may
live. The kernel (kernel.py) is blind to any domain; it operates on whatever pack it is given. This
is what makes OUTLIER_MCB agnostic: every domain is ONE pack among many, never baked into the engine.

A pack declares:
  assumptions   — the hidden assumptions shared by the domain's known solutions
  relations     — typed edges among them (implies/depends_on/blocks/if_false_requires/collapses_to/needs_new_data)
  axes          — the breakable axes of THIS domain (name -> {priority, verdict})  (not hard-coded I/S/O/O)
  dimension_of  — assumption -> axis
  box_assumptions — the conjunction that keeps you in the domain's "default solution"
  known_families  — the solution families to collide a candidate against
  info_kinds      — new-information tokens this domain could acquire (-> why)
  failure_memory  — dead ideas in this domain (so we never reincarnate them)
  world_factory   — optional: axis -> an EXECUTABLE world builder (None for non-ML domains)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple
from .core import Assumption
from .assumption_graph import RELATIONS
from .errors import PackNotFoundError, InvalidPackError


@dataclass
class DomainPack:
    name: str
    keywords: List[str] = field(default_factory=list)
    box_name: str = "the most-probable solution from training memory"
    assumptions: List[Assumption] = field(default_factory=list)
    relations: List[Tuple[str, str, str, str]] = field(default_factory=list)
    dimension_of: Dict[str, str] = field(default_factory=dict)
    box_assumptions: set = field(default_factory=set)
    axes: Dict[str, Dict] = field(default_factory=dict)          # axis -> {"priority":int,"verdict":str}
    known_families: List[str] = field(default_factory=list)
    info_kinds: Dict[str, str] = field(default_factory=dict)
    failure_memory: Dict[str, Dict] = field(default_factory=dict)
    world_factory: Optional[Callable[[str], object]] = None
    universal_closures: List[str] = field(default_factory=list)   # FIX A: families defined by a representation
    #   theorem (e.g. "DEEPSETS", "QUASI_ARITHMETIC"); an idea INSIDE one is INSIDE_THE_BOX. See closures.py.

    def by_name(self) -> Dict[str, Assumption]:
        return {a.name: a for a in self.assumptions}

    def validate(self) -> List[str]:
        """Return a list of schema problems ([] = valid). Keeps elicited packs honest."""
        issues: List[str] = []
        names = {a.name for a in self.assumptions}
        if not self.assumptions:
            issues.append("pack has no assumptions")
        for a, ax in self.dimension_of.items():
            if a not in names:
                issues.append(f"dimension_of references unknown assumption '{a}'")
            if self.axes and ax not in self.axes:
                issues.append(f"dimension_of uses undeclared axis '{ax}'")
        for s, r, d, *_ in self.relations:
            if r not in RELATIONS:
                issues.append(f"relation '{r}' not in {RELATIONS}")
            if s not in names:
                issues.append(f"relation source '{s}' is not an assumption")
        return issues


REGISTRY: Dict[str, DomainPack] = {}


def register_pack(p: DomainPack) -> DomainPack:
    issues = p.validate()
    if issues:
        raise InvalidPackError(f"invalid DomainPack '{p.name}': {issues}")
    REGISTRY[p.name] = p
    return p


def get_pack(name: str) -> DomainPack:
    _ensure_loaded()
    try:
        return REGISTRY[name]
    except KeyError:
        raise PackNotFoundError(f"no registered pack named '{name}'; available: {sorted(REGISTRY)}")


def list_packs() -> List[str]:
    _ensure_loaded()
    return sorted(REGISTRY)


def _ensure_loaded() -> None:
    if not REGISTRY:
        from . import packs  # noqa: F401  (registers all built-in packs on import)


# programming languages that should bias routing toward the software ("coding") pack.
_SOFTWARE_LANGS = {"python", "javascript", "typescript", "go", "rust", "java", "ruby", "c++", "c"}


def pack_scores(prompt: str, repo=None) -> List[Tuple[str, int]]:
    """Score every registered (non-generic) pack against the prompt, plus a repo-language boost when a
    real RepoContext is given. Returns [(pack_name, score)] sorted best-first — the routing evidence."""
    _ensure_loaded()
    t = (prompt or "").lower()
    boost_software = bool(repo is not None and (repo.primary_language() in _SOFTWARE_LANGS))
    scores = []
    for name, p in REGISTRY.items():
        if name == "generic":
            continue
        hits = sum(1 for k in p.keywords if k in t) + (1 if (boost_software and name == "coding") else 0)
        scores.append((name, hits))
    return sorted(scores, key=lambda kv: -kv[1])


def select_pack(prompt: str, repo=None) -> Tuple[DomainPack, int]:
    """Pick the best-matching registered pack (keyword overlap + optional repo-language boost). Returns
    (pack, score); score == 0 ⇒ no confident match → the generic fallback (and the guard should fire).
    Kept for backward compatibility — the richer `route_pack` returns the full decision evidence."""
    scores = pack_scores(prompt, repo)
    if not scores or scores[0][1] == 0:
        return REGISTRY.get("generic"), 0
    return REGISTRY[scores[0][0]], scores[0][1]


@dataclass
class RouteDecision:
    """The EVIDENCE behind a routing choice — not a bare keyword count. Inspectable and falsifiable."""
    selected_pack: str
    scores: Dict[str, int]
    confidence: int
    margin: int
    ambiguous: bool
    reason: str
    used_explicit_pack: bool = False
    repo_language_boost: bool = False
    source: str = "keyword"             # explicit | repo_boost | keyword | fallback
    def as_dict(self) -> Dict:
        return self.__dict__


def route_pack(prompt: str, repo=None, pack: Optional[DomainPack] = None) -> RouteDecision:
    """Decide which pack to use and WHY. An explicit `pack` is caller intent and always wins. Otherwise
    score every pack, compute the margin to the runner-up, and flag ambiguity (a near-tie) so the caller
    can elicit instead of guessing. A real RepoContext biases toward the software pack and is recorded."""
    _ensure_loaded()
    if pack is not None:
        return RouteDecision(selected_pack=pack.name, scores={pack.name: 99}, confidence=99, margin=99,
                             ambiguous=False, reason="explicit pack supplied by the caller (intent honoured)",
                             used_explicit_pack=True, source="explicit")
    scores = dict(pack_scores(prompt, repo))
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    boost = bool(repo is not None and getattr(repo, "primary_language", lambda: None)() in _SOFTWARE_LANGS)
    if not ranked or ranked[0][1] == 0:
        return RouteDecision("generic", scores, 0, 0, True, "no keyword matched any pack",
                             repo_language_boost=boost, source="fallback")
    top, second = ranked[0][1], (ranked[1][1] if len(ranked) > 1 else 0)
    margin = top - second
    ambiguous = margin < 1
    return RouteDecision(ranked[0][0], scores, top, margin, ambiguous,
                         ("clear lead over the runner-up" if not ambiguous else "ambiguous: top two are near-tied"),
                         repo_language_boost=boost, source=("repo_boost" if boost else "keyword"))
