"""No-go / representation theorems as GENERATORS: their admissible exits become branches of the brief."""
import OUTLIER_MCB as gsl
from OUTLIER_MCB.barriers import barrier_branches, relevant_barriers, BARRIER_REGISTRY
from OUTLIER_MCB.theorems import theorem_branches


def test_barrier_topics_make_exits_branches_in_any_language_and_pack():
    br = barrier_branches("prove the twin prime conjecture with a new idea", gsl.get_pack("generic"))
    assert [b["exit"] for b in br] == BARRIER_REGISTRY["PARITY_PROBLEM"].exits
    assert all(b["world_test"] and b["killed_if"] for b in br)
    assert {b["barrier"] for b in barrier_branches("inventa un nuovo motore a moto perpetuo")} == {"THERMODYNAMICS_2ND_LAW"}


def test_unrelated_requests_get_no_theorem_exits():
    assert barrier_branches("invent a new rate limiter", gsl.get_pack("coding")) == []
    assert relevant_barriers("minimize the Gibbs free energy of a mixture") == []   # a potential, not over-unity
    assert "[theorem exits]" not in gsl.creative("invent a new rate limiter")


def test_creative_lists_exits_for_barriers_and_representation_theorems():
    s = gsl.creative("invent a new perpetual motion engine")
    assert "[theorem exits]" in s and "make the system OPEN" in s
    tb = theorem_branches("invent a new permutation-invariant pooling layer")
    assert tb and all(b["barrier"] == "DeepSets universality" for b in tb)
    assert "[theorem exits]" in gsl.creative("invent a new permutation-invariant pooling layer")
