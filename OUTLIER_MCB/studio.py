"""studio — ONE front door that orchestrates the whole library (answering 'how do I use it better?').

The library grew many entrypoints (creative · invent · judge · discover · evolve_invention · conjecture
search · the cognitive panel). `explore()` is the single coherent loop that threads them with HONEST
defaults: route the domain → generate (generators + optional LLM proposer + lateral + cross-domain analogy)
→ settle by an EXTERNAL resolver (an objective evaluator for invention, z3/lean for math) → remember +
mine abstractions → deliberate with the cognitive panel → emit ONE auditable, conservative report. It adds
no new mechanism; it makes the existing ones usable as a unit, and it never overclaims.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class StudioReport:
    problem: str
    mode: str                        # invention | math
    statement: str = ""
    best_name: str = ""
    best_score: float = 0.0
    verified: bool = False
    novelty_scope: str = ""
    panel: object = None
    trace: object = None
    concept_library: object = None
    conjectures: object = None       # a ConjectureDiscovery for the math path
    evolve_result: object = None
    headline: str = ""               # a claim-ladder-gated one-line claim about the best (honest words only)

    def to_dict(self) -> Dict:
        d = {"problem": self.problem, "mode": self.mode, "statement": self.statement}
        if self.mode == "math" and self.conjectures is not None:
            d.update(self.conjectures.to_dict())
        else:
            d.update({"best": self.best_name, "score": self.best_score, "verified": self.verified,
                      "novelty_scope": self.novelty_scope})
        return d

    def markdown(self) -> str:
        L = [f"# Studio — «{self.problem}»  (mode: {self.mode})"]
        if self.mode == "math" and self.conjectures is not None:
            L.append(self.conjectures.markdown())
        else:
            L.append(f"- **best:** {self.best_name} (score {self.best_score}, verified={self.verified}) · "
                     f"novelty_scope {self.novelty_scope or 'LOCAL_ONLY'}")
            if self.trace is not None:
                L.append(self.trace.markdown())
            if self.concept_library is not None and self.concept_library.concepts:
                L.append(self.concept_library.markdown())
            if self.panel is not None:
                L.append(self.panel.markdown())
        L.append(f"\n**Statement (conservative):** {self.statement}")
        return "\n".join(L)


def explore(problem: str, *, pack=None, evaluator=None, llm=None, prior_art_provider=None, budget: int = 16,
            lateral: bool = True, use_analogy: bool = True, mine_concepts: bool = True,
            math_claim: str = "", math_variables: Optional[Dict] = None,
            math_expressions: Optional[List[str]] = None, objective: str = "usefulness") -> StudioReport:
    """The single entrypoint. INVENTION path (default): evolve candidates under an `evaluator` (a real one,
    or the structural proxy ⇒ PROVISIONAL), with optional LLM proposer / lateral / cross-domain analogy, then
    deliberate with the cognitive panel. MATH path (pass `math_claim` or `math_expressions`): generate
    conjectures and PROVE them with z3/lean. Honest by default: never 'absolute novelty' / 'proved' without
    the evidence."""
    from .pack import select_pack
    if pack is None:
        pack, _ = select_pack(problem)

    # ── MATH path: generate → prove ──
    if math_claim or math_expressions:
        from .math_discovery import Conjecture
        from .conjecture_search import discover_conjectures, generate_conjectures
        vars_ = math_variables or {"x": (-5.0, 5.0)}
        conjs = (generate_conjectures(vars_, math_expressions) if math_expressions
                 else [Conjecture(problem, claim_expr=math_claim, variables=vars_)])
        disco = discover_conjectures(conjs)
        stmt = (f"{len(disco.proved())} conjecture(s) FORMALLY PROVED in the solver's decidable fragment, "
                f"{len(disco.disproved())} disproved with guaranteed counterexamples. A proof here is real "
                f"but NOT 'a new theorem' without an online prior-art check.")
        return StudioReport(problem=problem, mode="math", statement=stmt, conjectures=disco)

    # ── INVENTION path: generate → settle → audit ──
    from .evolve import evolve_invention
    provisional = evaluator is None
    if provisional:
        from .creative_search import structural_evaluator
        evaluator = structural_evaluator(pack)            # a PROXY — outcomes are provisional, said so below
    if objective in ("novelty", "innovation", "creative_frontier"):
        from .novel_objective import novelty_objective
        evaluator = novelty_objective(evaluator=evaluator, provider=prior_art_provider)
    res = evolve_invention(problem, evaluator, budget=budget, pack=pack, lateral=lateral,
                           use_analogy=use_analogy, mine_concepts=mine_concepts, llm=llm,
                           prior_art_provider=prior_art_provider, orchestrate=True)   # showcase path: lessons + fixation + frontier IN the loop
    panel = res.panel(pack, provider=prior_art_provider)
    best = res.best()
    base = res.conservative_statement()
    stmt = (("PROVISIONAL (structural evaluator — wire a real evaluator / z3 / lean for settled results): " + base)
            if provisional else base)
    return StudioReport(problem=problem, mode="invention", statement=stmt,
                        best_name=(best.candidate_name if best else ""), best_score=(best.score if best else 0.0),
                        verified=(best.externally_settled if best else False),   # fix A: only external settlement certifies
                        novelty_scope=(best.novelty_scope if best else ""), panel=panel, trace=res.trace,
                        concept_library=res.concept_library, evolve_result=res,
                        headline=res.honest_headline())                          # #9: claim-ladder-gated headline
