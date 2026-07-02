"""Agnostic across ALL fields — the same engine attacks physics / engineering / ML, not only mathematics.

Offline, deterministic. Shows that the hard-problem machinery is domain-blind: domain knowledge lives in PACKS,
and a partial result is settled by the DOMAIN's own external resolver — a math proof, a reproducible SIMULATION,
a wet-lab reproduction, a held-out ML eval, a benchmark, or a green repo test — never the engine's own opinion.

  • routing picks the right pack per field (number_theory, physics);
  • a no-go BARRIER works outside math too: a closed-system perpetual-motion idea is DEAD_BY_BARRIER (2nd law);
  • an ENGINEERING frontier (minimize a beam mass) advances via a SIMULATION certificate and never regresses;
  • the repair INTERVIEW: the library tells an LLM WHAT/HOW to fix and the CONSTRAINTS, before any patch.

Run:  python examples/agnostic_domains_demo.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import OUTLIER_MCB as gsl
from OUTLIER_MCB.certificates import Certificate
from OUTLIER_MCB.frontier_search import frontier_search, ResultCandidate
from OUTLIER_MCB.self_diagnosis import DiagnosticMemory, diagnostic_run


def main() -> None:
    # 1 — agnostic routing: each field selects its own pack
    for prompt in ["infinite coppie di primi con gap limitato",
                   "un motore termodinamico ad alta efficienza (non a moto perpetuo)"]:
        pack, score = gsl.pack.select_pack(prompt)
        print(f"[routing] «{prompt[:42]}…» → pack '{pack.name}' (score {score})")

    # 2 — a no-go barrier outside mathematics: the 2nd law kills a closed-system over-unity claim
    j = gsl.judge("a closed-system engine with over-unity efficiency (perpetual motion)", pack=gsl.get_pack("physics"))
    print(f"\n[barrier] perpetual-motion verdict: {j.verdict}")
    if j.barrier is not None:
        print(f"          exits: {j.barrier.exits[0]}")

    # 3 — an ENGINEERING frontier settled by a reproducible SIMULATION (no math prover involved)
    def sim(value, ok=True):
        return Certificate(status="SIMULATION_VERIFIED" if ok else "SIMULATION_FAILED",
                           detail=f"FEM run, mass={value}kg", domain="engineering", resolver="fem")
    cands = [ResultCandidate("beam-30", "mass_kg", 30, "decrease", settle=lambda: sim(30)),
             ResultCandidate("beam-22", "mass_kg", 22, "decrease", settle=lambda: sim(22)),
             ResultCandidate("beam-12 (sim fails)", "mass_kg", 12, "decrease", settle=lambda: sim(12, ok=False))]
    rep = frontier_search("lightweight_beam", cands, objective_metric="mass_kg", objective_value=10)
    print("\n[engineering] " + rep.markdown().splitlines()[1])
    print(f"              parent stays {rep.parent_status} — partial certified progress, never regressing.")

    # 4 — the repair INTERVIEW: the LLM asks the library what/how to fix and the constraints, before patching
    mem = DiagnosticMemory()
    with diagnostic_run("lightweight_beam", memory=mem) as log:
        frontier_search("lightweight_beam", cands, objective_metric="mass_kg", objective_value=10, log=log)
    print("\n[repair interview]\n" + gsl.repair_brief(mem).markdown())


if __name__ == "__main__":
    main()
