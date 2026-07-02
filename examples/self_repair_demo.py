"""Self-diagnosis + evolutionary self-repair — the library that notices it erred and fixes itself, never back.

Offline, deterministic. It shows the full loop:
  1. a task run that does NOT reach its objective drops diagnostic POINTS (a keylog) into a SEPARATE memory;
  2. self_diagnose mines that memory → the weak spots + the bottleneck;
  3. verify_invariants confirms the SOLID things (the untouchable behaviors) all hold;
  4. evolutionary_self_repair keeps a fix ONLY if no protected invariant breaks AND the metric does not regress
     — a good repair is accepted (frontier advances), a regressing / invariant-breaking one is ROLLED BACK.

Run:  python examples/self_repair_demo.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import OUTLIER_MCB as gsl
from OUTLIER_MCB.math_discovery import Conjecture
from OUTLIER_MCB.frontier_search import frontier_search, LemmaCandidate
from OUTLIER_MCB.self_diagnosis import DiagnosticMemory, diagnostic_run, self_diagnose
from OUTLIER_MCB.self_repair import evolutionary_self_repair, RepairProposal, verify_invariants, library_health


def main() -> None:
    mem = DiagnosticMemory()

    # 1 — a run that cannot reach the objective (H=2) leaves a post-mortem
    with diagnostic_run("bounded prime gaps", memory=mem) as log:
        cands = [LemmaCandidate("H<=14", Conjecture(statement="b14", variables={"n": (1, 5)}, domain="int"),
                                "H", 14, "decrease", predicate=lambda n: True),
                 LemmaCandidate("H<=5 (false)", Conjecture(statement="b5", variables={"n": (1, 20)}, domain="int"),
                                "H", 5, "decrease", predicate=lambda n: n * n < 100)]
        frontier_search("twin_primes", cands, objective_metric="H", objective_value=2, log=log)

    # 2 — autodiagnose
    print(self_diagnose(mem).markdown())

    # 3 — the solid, untouchable invariants
    print("\n" + verify_invariants().markdown())
    print(f"\nlibrary health = {library_health()}  (fraction of protected invariants holding)\n")

    # 4 — evolutionary self-repair on a demo health metric, gated by never-regress + invariants
    state = {"metric": 0.6}
    led = gsl.FrontierLedger()

    good = RepairProposal("tune-the-bottleneck",
                          apply=lambda: state.__setitem__("metric", 0.85),
                          rollback=lambda: state.__setitem__("metric", 0.6),
                          rationale="addresses the diagnosed bottleneck")
    r1 = evolutionary_self_repair(good, measure=lambda: state["metric"], ledger=led, memory=mem)
    print(r1.markdown())

    bad = RepairProposal("regressing-change",
                         apply=lambda: state.__setitem__("metric", 0.3),
                         rollback=lambda: state.__setitem__("metric", state["metric"]),
                         rationale="a change that would go backwards")
    r2 = evolutionary_self_repair(bad, measure=lambda: state["metric"], ledger=led, memory=mem)
    print("\n" + r2.markdown())

    print(f"\nhealth frontier (monotone): {led.best('library', 'health')}  "
          f"— a regression was refused, the engine never went backwards.")


if __name__ == "__main__":
    main()
