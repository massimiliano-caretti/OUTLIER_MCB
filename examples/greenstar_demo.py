"""OUTLIER_MCB demo — the SAME domain-blind engine on different domains.

Proves the core property: the kernel is domain-blind; each prompt selects (or elicits) its own
DomainPack, so the answers genuinely differ — a rate limiter never gets a maths answer, and an
unknown domain is ELICITED, never faked.
"""
import sys, warnings; warnings.filterwarnings("ignore")
from pathlib import Path
HERE = Path(__file__).resolve().parent; PKG = HERE.parent
sys.path.insert(0, str(PKG))
import OUTLIER_MCB as gsl

PROMPTS = {
    "rate limiter (systems)": "design a new rate limiter for a distributed API gateway, fairness across tenants, low latency",
    "convergence theorem (math)": "find a new theorem on convergence of a gradient method on non-convex landscapes",
    "game matchmaking (unknown)": "design a fairer matchmaking system for an online multiplayer game",
}

print("=" * 84)
print("OUTLIER_MCB — ONE domain-blind kernel, MANY domains")
print("packs available:", gsl.list_packs())
print("=" * 84)

for title, p in PROMPTS.items():
    pf = gsl.preflight_creative_request(p)
    rec = pf["recommended_direction"]
    mi = pf["missing_information"]
    print(f"\n### {title}")
    print(f"  selected pack : {pf['pack']}   (guard_ok={pf['domain_guard']['ok']})")
    print(f"  box           : {pf['box_name']}")
    print(f"  recommend     : break '{rec.get('assumption')}' on axis {rec.get('dimension')}")
    print(f"  must NOT propose: {', '.join(pf['must_not_propose'][:6])}{'…' if len(pf['must_not_propose'])>6 else ''}")
    print(f"  new info needed: {mi.get('recommended_first')}  (insufficient={mi['data_insufficient']})")
    if pf.get("elicitation_required"):
        e = gsl.elicit_pack(p)
        print("  GUARD FIRED → elicitation required. First scaffold question:")
        print(f"     “{e['request']['questions'][0]}”")
    else:
        br = gsl.branch_on_assumptions(p, gsl.get_pack(pf["pack"]), k=3)
        print("  divergence (3 branches in tension):")
        for b in br:
            print(f"     [{b['stance']:12s}] break {b['assumption']:22s} ({b['axis']}) → {b['negation'][:70]}")

print("\n" + "=" * 84)
print("Same kernel. Different domains → different assumptions, different breaks, different missing info.")
print("Unknown domains are ELICITED, never faked. No domain is baked into the engine.")
print("\nThe one-call brief an assistant would read before answering the rate-limiter prompt:")
print("-" * 84)
print(gsl.creative(PROMPTS["rate limiter (systems)"]))
