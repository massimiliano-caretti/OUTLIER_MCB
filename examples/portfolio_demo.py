"""portfolio_demo (G8) — the loop closing in on the objective, with an external safety net, never overclaiming.

It takes candidate SUB-LEMMAS toward an open problem (bounding prime gaps — the `number_theory` pack), DROPS routes
a known barrier kills (e.g. the parity barrier), sends the rest to the PORTFOLIO of external provers, records each
certified winner on a MONOTONE frontier, and turns every undecided lemma into the next assumption to break.

Prints: which solver/method closed what, the frontier advancing (never regressing), and — the non-negotiable —
the PARENT conjecture staying CONJECTURE (never PROVED). Deterministic; runs with only z3 (others opt-in).

Run:  python examples/portfolio_demo.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import OUTLIER_MCB as g
from OUTLIER_MCB.barriers import barrier_membership
from OUTLIER_MCB.frontier_ledger import FrontierLedger

PARENT = "the twin prime conjecture (there are infinitely many primes p with p+2 prime)"

def _isprime(n):
    n = int(n)
    if n < 2:
        return False
    d = 2
    while d * d <= n:
        if n % d == 0:
            return False
        d += 1
    return True


# candidate sub-lemmas toward the parent. Each is a SELF-CONTAINED, externally-settleable statement — NOT the
# infinite parent. `route` is the human description a barrier can veto.
SUBLEMMAS = [
    {"id": "amgm_lemma", "route": "an algebraic inequality used in the sieve weights",
     "conj": g.Conjecture("AM-GM weight bound", claim_expr="x**2 + y**2 >= 2*x*y",
                          variables={"x": (-9, 9), "y": (-9, 9)}), "pred": None},
    {"id": "euler_prime_finite", "route": "a finite computational prime fact z3's SMT cannot express (needs isprime)",
     "conj": g.Conjecture("n^2+n+41 is prime for n in [0,5]", variables={"n": (0, 5)}, domain="int"),
     "pred": (lambda n: _isprime(n * n + n + 41))},
    {"id": "finite_density", "route": "a finite-box arithmetic fact (exhaustive)",
     "conj": g.Conjecture("n^2 >= n on [1,50]", variables={"n": (1, 50)}, domain="int"),
     "pred": (lambda n: n * n >= n)},
    {"id": "parity_route", "route": "close the gap to exactly 2 with parity-respecting sieve weights that beat the parity barrier",
     "conj": g.Conjecture("gap=2 via parity-only weights", claim_expr="x > 0", variables={"x": (1, 2)}), "pred": None},
]


def main():
    port = g.portfolio_backend()
    ledger = FrontierLedger()
    next_assumptions = []
    closed = 0
    print(f"# Portfolio demo — attacking: {PARENT}\n")
    for s in SUBLEMMAS:
        barred = barrier_membership(s["route"], pack=g.get_pack("number_theory"))
        if barred is not None and getattr(barred, "verdict", "") == "INSIDE":
            print(f"· {s['id']:18} DROPPED — barrier: {getattr(barred, 'barrier', '?')} ({getattr(barred, 'why', '')[:60]})")
            next_assumptions.append(s["route"])
            continue
        cert = g.settle_lemma(s["conj"], predicate=s["pred"], backend=port)
        winner = getattr(port, "winner", None) or cert.method
        if cert.certified:
            closed += 1
            r = ledger.claim(PARENT, "certified_sub_lemmas", float(closed), "increase", {"status": cert.status})
            adv = f"frontier ADVANCED → {r.value}" if r.accepted else f"unchanged ({r.outcome})"
            print(f"✓ {s['id']:18} CLOSED    {cert.status:16} via {winner:18} → {adv}")
        else:
            print(f"? {s['id']:18} UNDECIDED {cert.status:16} via {winner:18} → next assumption to break")
            next_assumptions.append(s["route"])

    print(f"\n## Frontier (monotone, externally certified): certified_sub_lemmas = "
          f"{ledger.best(PARENT, 'certified_sub_lemmas')}")
    print(f"## Parent stays a CONJECTURE (never PROVED): {PARENT}")
    print("   — each certified sub-lemma is a THEOREM for THAT lemma only; the infinite parent remains CONJECTURE.")
    if next_assumptions:
        print("\n## Undecided → the next assumptions to break:")
        for a in next_assumptions:
            print(f"  - {a}")
    return closed


if __name__ == "__main__":
    main()
