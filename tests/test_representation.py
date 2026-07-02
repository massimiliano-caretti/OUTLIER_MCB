"""test_representation — inventing the encoding that makes a hard problem easy, gated by a control (T2.4).
Deterministic and offline.

Task: decide whether n is divisible by 3. A fixed solver only knows how to check 'is the value 0'. On the RAW
integer it is almost always wrong; under a 'mod 3' representation it is perfect. A structure-destroying control
must collapse the gain — otherwise it is a relabelling, not a new notation.
"""
import OUTLIER_MCB as gsl
from OUTLIER_MCB.representation import Representation, representation_reducibility, invent_representation


_INSTANCES = list(range(30))
_LABELS = [n % 3 == 0 for n in _INSTANCES]


def _solver(encoded):
    return encoded == 0                       # the fixed solver only recognises 'is it zero'


def test_mod3_representation_reduces_the_problem():
    rep = Representation(name="mod3", encode=lambda n: n % 3)
    v = representation_reducibility(rep, _solver, _INSTANCES, _LABELS)
    assert v.status == "REDUCES" and v.accepted
    assert v.accuracy == 1.0 and v.reducibility >= 0.15        # perfect under mod3, a real gain over the raw integer
    assert v.control_gap >= 0.15                               # the structure-destroying control collapses it


def test_identity_representation_gives_no_gain():
    rep = Representation(name="identity", encode=lambda n: n)
    v = representation_reducibility(rep, _solver, _INSTANCES, _LABELS)
    assert v.status == "NO_GAIN" and not v.accepted


def test_invent_representation_ranks_the_reducing_one_first():
    cands = [Representation(name="identity", encode=lambda n: n),
             Representation(name="mod3", encode=lambda n: n % 3),
             Representation(name="times2", encode=lambda n: 2 * n)]   # no help
    verdicts = invent_representation(cands, _solver, _INSTANCES, _LABELS)
    assert verdicts[0].representation == "mod3" and verdicts[0].accepted
    assert not any(v.accepted for v in verdicts if v.representation != "mod3")


# ── a 'decorative' re-encoding whose control lifts accuracy just as much is rejected ──────────────────
def test_decorative_representation_is_rejected():
    # a constant encoding: every instance maps to the same value. If that value makes the solver's accuracy
    # equal to the base rate, the control (misaligned) gives the SAME accuracy → not real structure.
    labels_all_false = [False] * len(_INSTANCES)              # base rate: solver must say 'not zero'
    rep = Representation(name="const1", encode=lambda n: 1)   # solver(1) == 0 → always False → matches all
    v = representation_reducibility(rep, _solver, _INSTANCES, labels_all_false)
    assert v.status in ("DECORATIVE", "NO_GAIN") and not v.accepted   # never REDUCES: the control holds too


# ── wired into the orchestrator's REPRESENT track (no dead code) ──────────────────────────────────────
def test_representation_track_in_autonomous():
    ctx = {"candidates": [Representation(name="mod3", encode=lambda n: n % 3)],
           "solver": _solver, "instances": _INSTANCES, "labels": _LABELS}
    res = gsl.autonomous("decide divisibility by 3", representation_context=ctx, beam=3, rounds=1)
    assert "invent_representation" in res.used_capabilities
    assert res.representations and res.representations[0].accepted
