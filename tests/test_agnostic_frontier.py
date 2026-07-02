"""The hard-problem frontier is AGNOSTIC — it works for physics / engineering / biology / ML, not only math.

RED→GREEN: a frontier_search over ResultCandidates settled by a (non-math) SIMULATION resolver advances a
certified, monotone frontier and never regresses; a refuted candidate is killed. A no-go barrier works outside
math too: a perpetual-motion idea in the physics pack is DEAD_BY_BARRIER, while an open-system idea is not.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import OUTLIER_MCB as gsl
from OUTLIER_MCB.certificates import Certificate
from OUTLIER_MCB.frontier_search import frontier_search, ResultCandidate
from OUTLIER_MCB.barriers import barrier_membership, DEAD_BY_BARRIER, NOT_BLOCKED
from OUTLIER_MCB.pack import select_pack


def _sim(value, ok=True):
    # a deterministic, reproducible "simulation" resolver — the engineering analogue of a prover
    status = "SIMULATION_VERIFIED" if ok else "SIMULATION_FAILED"
    return Certificate(status=status, detail=f"FEM run at H={value}", domain="engineering", resolver="fem")


def test_engineering_frontier_advances_via_simulation_resolver():
    METRIC = "mass_kg"   # minimize a beam mass, settled by a reproducible simulation (no math prover involved)
    cands = [
        ResultCandidate("design-30", METRIC, 30, "decrease", settle=lambda: _sim(30)),
        ResultCandidate("design-22", METRIC, 22, "decrease", settle=lambda: _sim(22)),
        ResultCandidate("design-12 (fails sim)", METRIC, 12, "decrease", settle=lambda: _sim(12, ok=False)),
    ]
    rep = frontier_search("lightweight_beam", cands, objective_metric=METRIC, objective_value=10)
    assert rep.ledger.best("lightweight_beam", METRIC) == 22       # best simulation-verified design
    assert len(rep.advanced) == 2 and len(rep.killed) == 1         # the unverified design is killed
    assert rep.parent_status == "CONJECTURE"


def test_global_resolver_settles_non_math_candidates():
    # candidates carry only a metric; an injected resolver (e.g. a dataset eval) settles them all
    def dataset_eval(c):
        ok = c.value <= 0.95
        return Certificate(status="DATASET_EVAL_PASSED" if ok else "EVAL_FAILED", domain="ml", resolver="heldout")
    cands = [ResultCandidate("model-A", "accuracy", 0.80, "increase", settle=lambda: None),
             ResultCandidate("model-B", "accuracy", 0.90, "increase", settle=lambda: None)]
    rep = frontier_search("classifier", cands, objective_metric="accuracy", objective_value=0.99,
                          resolver=dataset_eval)
    assert rep.ledger.best("classifier", "accuracy") == 0.90


def test_thermodynamics_barrier_kills_perpetual_motion():
    phys = gsl.get_pack("physics")
    v = barrier_membership("a closed-system engine with over-unity efficiency (perpetual motion)", phys)
    assert v is not None and v.status == DEAD_BY_BARRIER and v.barrier == "THERMODYNAMICS_2ND_LAW"


def test_open_system_idea_is_not_blocked_negative_control():
    phys = gsl.get_pack("physics")
    v = barrier_membership("extract work from an external temperature gradient (an open, driven system)", phys)
    assert v is None or v.status == NOT_BLOCKED


def test_physics_barrier_is_domain_scoped():
    v = barrier_membership("a closed-system over-unity perpetual motion engine", gsl.get_pack("coding"))
    assert v is None                                                # the thermo barrier is physics/engineering only


def test_physics_pack_routes_italian_and_english():
    for prompt in ["un motore a moto perpetuo con efficienza", "perpetual motion energy machine thermodynamics"]:
        pack, score = select_pack(prompt)
        assert pack.name == "physics" and score > 0, prompt


def test_agnosticism_is_a_protected_invariant():
    rep = gsl.verify_invariants()
    assert rep.ok and "agnostic_certificates" in rep.passed_names
