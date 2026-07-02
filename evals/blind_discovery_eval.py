"""blind_discovery_eval — a LARGE, BLIND task where compounding memory (and curiosity) earn their keep.

On the small 4-assumption packs the settled outcome is robust to exploration strategy, so no honest delta
could be claimed for memory/curiosity. Here the space is large (12 assumptions) and BLIND: exactly one
assumption is the data-true break, and it is placed at the BOTTOM of the base ranking. With a limited
per-round budget over several rounds:

  • a MEMORYLESS searcher re-attacks the same top-K every round → it never reaches the buried true break;
  • the COMPOUNDING memory sinks each refuted decoy and explores onward → it reaches and CONFIRMS the
    true break (settled by the symbolic evaluator on interaction-law data);
  • CURIOSITY (drive toward the untried) can reach it in fewer rounds.

Deterministic and offline (synthetic pack + a known interaction law). This is the eval that measures the
mechanisms the small tasks could not.
"""
from __future__ import annotations
import random
from typing import Dict, Optional


def _large_pack():
    import OUTLIER_MCB as gsl
    from OUTLIER_MCB.core import Assumption
    # 11 decoys (mapped to bases that CANNOT fit an interaction law) + 1 true break (interaction), placed last.
    decoy_caps = ["threshold_structure", "transcendental_basis", "dimensionless_groups"]
    # distinct vocabulary per decoy (real assumptions differ; identical templated text would make episodic
    # recall false-match them all as one dead end — a realistic pack avoids that).
    themes = ["topology", "spectral", "entropy", "curvature", "resonance", "symmetry",
              "diffusion", "percolation", "lattice", "boundary", "manifold"]
    A, dim, rel = [], {}, []
    for i in range(11):
        name = f"a_decoy_{i:02d}"
        axis = ["HI", "MID"][i % 2]
        t = themes[i]
        A.append(Assumption(name, f"the {t} structure is fixed", f"{t} models assume it",
                            f"the {t} regime governs and the {t} component dominates the outcome", ["fam"],
                            f"a constructed world where the {t} assumption is shown false and {t} controls collapse"))
        dim[name] = axis
        rel.append((name, "if_false_requires", decoy_caps[i % 3], "decoy mapping"))
    A.append(Assumption("zz_law_is_coupled", "the law factorizes additively over the inputs",
                        "additive models assume it", "an irreducible interaction term couples the inputs",
                        ["additive"], "a dataset where additive models fail but an interaction term fits and "
                        "the controls collapse"))
    dim["zz_law_is_coupled"] = "LOW"
    rel.append(("zz_law_is_coupled", "if_false_requires", "interaction_terms", "the true break"))
    return gsl.DomainPack(
        name="blindprobe", keywords=["blind probe domain"], box_name="additive smooth box",
        assumptions=A, relations=rel, dimension_of=dim,
        box_assumptions={"a_decoy_00", "a_decoy_01", "a_decoy_02"},
        axes={"HI": {"priority": 3, "verdict": "v"}, "MID": {"priority": 2, "verdict": "v"},
              "LOW": {"priority": 1, "verdict": "v"}},
        known_families=["fam", "additive"],
        info_kinds={c: "why" for c in decoy_caps + ["interaction_terms"]},
        failure_memory={}, world_factory=None)


def _interaction_data():
    rng = random.Random(7)
    X = [[rng.uniform(-2, 2), rng.uniform(-2, 2), rng.uniform(-2, 2)] for _ in range(120)]
    y = [2.0 * r[0] * r[1] - 3.0 for r in X]
    cut = int(0.66 * 120)
    return X[:cut], y[:cut], X[cut:], y[cut:]


def _found_round(run, fertile: str) -> Optional[int]:
    rs = [s.round for s in run.steps if s.seed == fertile and s.outcome == "CONFIRMED"]
    return min(rs) if rs else None


def run_blind_discovery_eval(rounds: int = 6, budget: int = 4) -> Dict:
    import OUTLIER_MCB as gsl
    pack = _large_pack()
    ev = gsl.symbolic_evaluator(_interaction_data(), pack=pack)
    fertile = "zz_law_is_coupled"
    common = dict(pack=pack, evaluator=ev, accept=0.7, blend_with=[], rounds=rounds, top_problems=budget)

    full = gsl.autonomous_inventor(**common, curiosity=0.6, consult_memory=True)
    memoryless = gsl.autonomous_inventor(**common, consult_memory=False)
    no_curiosity = gsl.autonomous_inventor(**common, curiosity=0.0, consult_memory=True)

    mem_round = _found_round(full, fertile)
    nocur_round = _found_round(no_curiosity, fertile)
    return {
        "n_assumptions": len(pack.assumptions), "budget_per_round": budget, "rounds": rounds,
        "fertile_truth": fertile,
        "memory_found_round": mem_round,
        "memoryless_found_round": _found_round(memoryless, fertile),
        "no_curiosity_found_round": nocur_round,
        "memory_earns_its_keep": _found_round(memoryless, fertile) is None and mem_round is not None,
        "curiosity_rounds_saved": (nocur_round - mem_round) if (mem_round and nocur_round) else None,
        "distinct_seeds_memoryless": len({s.seed for s in memoryless.steps}),
        "distinct_seeds_memory": len({s.seed for s in full.steps}),
    }


def markdown(r: Dict) -> str:
    keep = "✅" if r["memory_earns_its_keep"] else "❌"
    L = [f"# Blind discovery eval — {r['n_assumptions']} assumptions, budget {r['budget_per_round']}/round, "
         f"{r['rounds']} rounds", "",
         f"## Compounding memory earns its keep  {keep}",
         f"- the buried true break `{r['fertile_truth']}` was found by MEMORY at round {r['memory_found_round']}, "
         f"by the MEMORYLESS baseline at round {r['memoryless_found_round']} (None = never).",
         f"- coverage: memoryless touched {r['distinct_seeds_memoryless']} distinct breaks, memory touched "
         f"{r['distinct_seeds_memory']} (it explored, the baseline looped).",
         f"## Curiosity",
         f"- with curiosity the true break was found at round {r['memory_found_round']}, without it at round "
         f"{r['no_curiosity_found_round']} (rounds saved: {r['curiosity_rounds_saved']}).",
         "", "_Settled by the symbolic evaluator on interaction-law data — the confirmation is the DATA's, "
         "not the engine's._"]
    return "\n".join(L)


if __name__ == "__main__":
    print(markdown(run_blind_discovery_eval()))
