"""Hard-problem frontier — attack an OPEN problem with PARTIAL certified results that never regress.

Runs end-to-end, offline, deterministic. It shows the six pieces working together on bounded prime gaps:
  F1  the request routes to the real number_theory pack (not "no keyword matched");
  F2  a classical sieve aimed at gap = 2 is DEAD_BY_BARRIER (the parity problem) — the dead route is refused;
  F4+F5+F3  a toward-objective loop settles decidable sub-lemmas externally and advances a MONOTONE certified
            frontier (a toy stand-in for H: 30 → 20 → 14), kills a false lemma with a counterexample, and keeps
            every failure as the next lever;
  honesty  the parent conjecture stays CONJECTURE — the engine NEVER prints PROVED on the open problem.

Run:  python examples/hard_problem_frontier.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import OUTLIER_MCB as gsl
from OUTLIER_MCB.math_discovery import Conjecture
from OUTLIER_MCB.frontier_search import frontier_search, LemmaCandidate


def main() -> None:
    # F1 — routing to the number-theory domain
    pack, score = gsl.pack.select_pack("infinite coppie di primi con gap limitato")
    print(f"[F1] routed to pack: {pack.name} (score {score})\n")

    # F2 — the parity barrier kills the classical sieve route to gap = 2
    j = gsl.judge("a classical Selberg sieve with parity-respecting weights to prove twin primes at gap 2",
                  pack=gsl.get_pack("number_theory"))
    print(f"[F2] classical-sieve-for-gap-2 verdict: {j.verdict}")
    if j.barrier is not None:
        print("     " + j.barrier.markdown().split("—", 1)[-1].strip()[:140] + " ...\n")

    # F5 (+F4+F3) — advance a monotone certified frontier on a toy stand-in for H; kill a false lemma
    METRIC = "H"
    candidates = [
        LemmaCandidate("H<=30", Conjecture(statement="b30", variables={"n": (1, 20)}, domain="int"),
                       METRIC, 30, "decrease", predicate=lambda n: n >= 1),
        LemmaCandidate("H<=20", Conjecture(statement="b20", variables={"n": (1, 20)}, domain="int"),
                       METRIC, 20, "decrease", predicate=lambda n: n * n >= n),
        LemmaCandidate("H<=14", Conjecture(statement="b14", variables={"n": (1, 20)}, domain="int"),
                       METRIC, 14, "decrease", predicate=lambda n: n + 1 > n),
        LemmaCandidate("H<=5 (FALSE)", Conjecture(statement="b5", variables={"n": (1, 20)}, domain="int"),
                       METRIC, 5, "decrease", predicate=lambda n: n * n < 100),   # false at n >= 10
    ]
    report = frontier_search("twin_prime_gap (toy)", candidates,
                             objective_metric=METRIC, objective_value=2)
    print("[F5] " + report.markdown())

    # honesty invariant — the parent stays CONJECTURE forever
    print(f"\n[honesty] parent status: {report.parent_status}  (residual to objective: {report.residual()})")
    assert report.parent_status == "CONJECTURE", "the engine must NEVER claim the open conjecture is proved"
    print("          The engine advanced PARTIAL certified results; it did NOT prove twin primes. By design.")


if __name__ == "__main__":
    main()
