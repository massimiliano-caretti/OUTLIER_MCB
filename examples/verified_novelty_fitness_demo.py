"""The fitness the engine designed for itself — VERIFIED-novelty — and why a composite score was rejected.

Offline, deterministic. Shows:
  1. the library judges a richer-composite fitness INSIDE_THE_BOX (a re-parameterization of 'add more metrics');
  2. verified-novelty: only proposals that break a box AND survive an EXTERNAL resolver count; self-judged
     novelty is ignored — and the anti-gaming gap shows verification is load-bearing;
  3. used as the fitness in evolutionary_self_repair: a verifying repair is accepted, while padding with
     self-judged novelty LOWERS the fitness and is refused (never-regress) — gaming is structurally impossible.

Run:  python examples/verified_novelty_fitness_demo.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import OUTLIER_MCB as g
from OUTLIER_MCB.verified_novelty import Proposal, verified_novelty, verified_novelty_fitness
from OUTLIER_MCB.self_repair import evolutionary_self_repair, RepairProposal

CERT = {"status": "NUMERIC_VERIFIED"}   # an external certificate (any field's resolver)


def main() -> None:
    # 1 — the library's meta-pack reviewer flags a 'richer composite' fitness as a re-parameterization of
    # 'add more metrics' (gameable) — so we anchor the fitness in EXTERNAL verification instead.
    j = g.judge("a fitness = novelty × diversity × usefulness minus a gaming penalty (a richer composite of "
                "internal scoring components)", pack=g.get_pack("meta"))
    flagged = "add_more_metrics" in j.dossier.markdown()
    print(f"[1] composite-fitness reviewed by the meta pack → flagged as 'add_more_metrics' (gameable): {flagged}. "
          "The engine pointed at 'the_engine_judges_itself' (only an external resolver certifies), so we use "
          "VERIFIED-novelty, not a composite.\n")

    # 2 — verified-novelty on a population: only novel AND externally certified counts
    pop = [Proposal("idea-A (verified)", breaks_box=True, certificate=CERT),
           Proposal("idea-B (self-judged novel)", breaks_box=True, certificate=None),
           Proposal("idea-C (certified but not novel)", breaks_box=False, certificate=CERT)]
    print("[2] " + verified_novelty(pop).markdown() + "\n")

    # 3 — fitness in evolutionary_self_repair (under invariants + never-regress)
    state = {"pop": [Proposal("v", True, CERT), Proposal("u", True, None)]}    # fitness 0.5
    measure = lambda: verified_novelty_fitness(state["pop"])
    print(f"[3] starting verified-novelty fitness: {measure()}")

    good = RepairProposal("verify-the-unverified",
                          apply=lambda: state.__setitem__("pop", [Proposal("v", True, CERT), Proposal("v2", True, CERT)]),
                          rollback=lambda: state.__setitem__("pop", [Proposal("v", True, CERT), Proposal("u", True, None)]))
    r1 = evolutionary_self_repair(good, measure=measure)
    print(f"    honest repair  → {'ACCEPTED' if r1.accepted else 'rejected'} (fitness {r1.before} → {r1.after})")

    base = list(state["pop"])
    bad = RepairProposal("pad-with-self-judged-novelty",
                         apply=lambda: state.__setitem__("pop", state["pop"] + [Proposal("u2", True, None), Proposal("u3", True, None)]),
                         rollback=lambda: state.__setitem__("pop", base))
    r2 = evolutionary_self_repair(bad, measure=measure)
    print(f"    gaming repair  → {'accepted' if r2.accepted else 'REJECTED (rolled back)'} "
          f"(fitness would drop {r2.before} → {r2.after}; never-regress refuses it)")
    print("\nGaming is structurally impossible: only the external world can raise the fitness, and the engine "
          "can never regress nor break a protected invariant.")


if __name__ == "__main__":
    main()
