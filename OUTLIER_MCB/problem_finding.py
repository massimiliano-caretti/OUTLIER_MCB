"""problem_finding — the engine PROPOSES which problems are worth attacking, not just answers a prompt.

Getzels & Csikszentmihalyi: problem FINDING — deciding which question to pose — separates creative
achievement from mere problem solving. Every other entrypoint answers a GIVEN prompt; this one supplies
the spark that is usually the human's: it surveys a domain (and, via conceptual blending, pairs of domains)
and returns a ranked portfolio of worth-attacking problems.

`worth` is not a decorative metric — it is built from signals the engine already trusts and that are
themselves falsifiable:
  • leverage     — the cascade REACH of breaking the assumption (cascade.py): a lever, not a pebble;
  • frontier     — does the break REQUIRE new information? (a problem that needs new data can exceed the
                   current ceiling; one that does not is engineering, not discovery);
  • novelty_pot. — is the axis NOT already saturated/dead in failure_memory?
  • centrality   — is the assumption load-bearing in the typed graph?
  • emergence    — (cross-domain only) how distant the two blended domains are.

Honest by construction: this RANKS priorities, it does not promise the problems are solvable. Each problem
states what would REFUTE its worth (if the cascade turns out to be leakage). It never claims novelty.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Problem:
    question: str
    domain: str                  # pack name, or 'blend:a⊕b' for a cross-domain problem
    seed: str                    # the assumption whose break defines the problem
    axis: str
    worth: float                 # [0,1] priority
    components: Dict[str, float] = field(default_factory=dict)
    why_worth: str = ""
    settles: str = ""            # what would CONFIRM or REFUTE that attacking it pays off
    def markdown(self) -> str:
        c = " · ".join(f"{k} {v}" for k, v in self.components.items())
        return (f"- **[{self.domain}] worth {self.worth}** — {self.question}\n"
                f"    - {c}\n    - why: {self.why_worth}\n    - settles: {self.settles}")


@dataclass
class ProblemPortfolio:
    problems: List[Problem] = field(default_factory=list)
    note: str = ""
    def best(self) -> Optional[Problem]:
        return self.problems[0] if self.problems else None
    def markdown(self) -> str:
        L = ["## Problem-finding — worth-attacking problems (ranked; the spark, still to be falsified)"]
        L += [p.markdown() for p in self.problems]
        if self.note:
            L.append("\n" + self.note)
        return "\n".join(L)


def _dead_axes(pack) -> set:
    """Axes already exhausted in this pack. Robust to either convention: the failure_memory key is the dead
    assumption's name (mapped via dimension_of, as self_spark does), or the value carries an explicit
    'axis'/'assumption'."""
    out = set()
    for k, v in (pack.failure_memory or {}).items():
        if not str(v.get("status", "")).startswith("DEAD"):
            continue
        out.add(pack.dimension_of.get(k))
        if v.get("axis"):
            out.add(v["axis"])
        if v.get("assumption"):
            out.add(pack.dimension_of.get(v["assumption"]))
    return out - {None}


def _worth(pack, seed, g, dead_axes, central) -> Dict:
    from .cascade import cascade
    casc = cascade(pack, seed)
    axis = pack.dimension_of.get(seed, "")
    needs = g.data_requirements().get(seed, [])
    comp = {
        "leverage": round(min(1.0, casc.reach / 3.0), 3),
        "frontier": 1.0 if needs else 0.3,
        "novelty_potential": 0.4 if axis in dead_axes else 1.0,
        "centrality": 1.0 if seed in central else 0.5,
    }
    worth = round(0.4 * comp["leverage"] + 0.25 * comp["frontier"]
                  + 0.2 * comp["novelty_potential"] + 0.15 * comp["centrality"], 3)
    why = (f"breaking '{seed}' cascades to {casc.reach} other assumption(s)"
           + (f", requires new information ({', '.join(needs)})" if needs else ", needs no new information")
           + (f"; axis '{axis}' is already saturated here" if axis in dead_axes else ""))
    settles = (f"attacking it pays off only if breaking '{seed}' truly unlocks its cascade on a world-test; "
               f"if the controls (shuffle the broken structure) do not collapse, the leverage was leakage — drop it.")
    return {"worth": worth, "components": comp, "why": why, "settles": settles, "axis": axis}


def find_problems(pack=None, prompt: str = "", k: int = 5, blend_with: Optional[List] = None,
                  memory=None, curiosity: float = 0.0) -> ProblemPortfolio:
    """Survey a domain (and optional foreign domains to blend with) and return the top-`k` worth-attacking
    problems, ranked. `blend_with` is a list of pack names or packs; pass None to auto-pair with the other
    registered non-generic packs (cross-domain problem finding via conceptual blending). Pass a
    `discovery_memory.DiscoveryMemory` as `memory` to fold the CUMULATIVE learned prior into worth (fertile
    assumptions rise, refuted dead ends sink and their axes count as saturated) — the compounding advantage.
    Without `memory` the ranking is byte-for-byte unchanged."""
    from . import kernel
    from .pack import select_pack, get_pack, list_packs
    if pack is None:
        pack, _ = select_pack(prompt)
    g = kernel.graph_of(pack)
    dead = _dead_axes(pack)
    if memory is not None:
        dead = dead | memory.barren_axes(pack.name)         # accumulated refutations saturate their axes
    central = set(g.central(3))
    breakable = [a.name for a in pack.assumptions if pack.dimension_of.get(a.name)]

    def _fold_prior(base_worth, seed, comps):
        worth = base_worth
        if memory is not None:
            p = memory.prior(seed, pack.name)
            comps = {**comps, "learned_prior": p}
            # factor in [0.7, 1.3] centred on the untried prior (0.5 → ×1.0): fertile lifts, barren damps.
            worth = round(min(1.0, base_worth * (0.7 + 0.6 * p)), 3)
        if curiosity > 0.0:                              # intrinsic drive toward the unknown (explore)
            from .affect import curiosity_score, curious_worth
            cs = curiosity_score(seed, pack.name, memory)
            comps = {**comps, "curiosity": cs}
            worth = curious_worth(worth, cs, curiosity)
        return worth, comps

    problems: List[Problem] = []
    for seed in breakable:
        w = _worth(pack, seed, g, dead, central)
        worth, comps = _fold_prior(w["worth"], seed, w["components"])
        a = pack.by_name()[seed]
        problems.append(Problem(
            question=f"What if «{a.if_false}» — i.e. '{seed}' is false in {pack.name}?",
            domain=pack.name, seed=seed, axis=w["axis"], worth=worth,
            components=comps, why_worth=w["why"], settles=w["settles"]))

    # cross-domain problem finding: blend with foreign domains for problems neither poses alone.
    if blend_with is None:
        blend_with = [n for n in list_packs() if n not in (pack.name, "generic")]
    from .generators import conceptual_blend, blend_emergence
    for other in blend_with:
        fp = get_pack(other) if isinstance(other, str) else other
        if fp is None or fp.name == pack.name:
            continue
        blend = conceptual_blend(pack, fp)
        if blend is None:
            continue
        a_name, b_name = (x.split("@")[0] for x in blend.assumptions)
        emergence = blend_emergence(pack.by_name()[a_name].if_false, fp.by_name()[b_name].if_false)
        wa = _worth(pack, a_name, g, dead, central)["components"]["leverage"]
        worth = round(0.5 * emergence + 0.3 * wa + 0.2, 3)   # emergence-led; floor so a real blend ranks
        problems.append(Problem(
            question=blend.negation, domain=f"blend:{pack.name}⊕{fp.name}",
            seed=f"{a_name}⊕{b_name}", axis="·".join(blend.breaks), worth=worth,
            components={"emergence": emergence, "leverage": wa},
            why_worth=f"a cross-domain problem neither {pack.name} nor {fp.name} poses alone (emergence {emergence})",
            settles="pays off only if the blend passes a world-test NEITHER parent break passes alone "
                    "(emergence>0); if it reduces to one domain, it was a transport, not a real problem."))

    problems.sort(key=lambda p: (-p.worth, p.domain, p.seed))
    note = (f"Found {len(problems)} candidate problems in '{pack.name}'"
            + (f" (+blends with {', '.join(str(b if isinstance(b, str) else b.name) for b in blend_with)})" if blend_with else "")
            + ". `worth` is a falsifiable PRIORITY (leverage·frontier·novelty·centrality), not a promise of a solution.")
    return ProblemPortfolio(problems=problems[:max(1, k)], note=note)
