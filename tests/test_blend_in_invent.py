"""#4 Emergent cross-domain blending, reachable from the headline runtime, with an emergence gate.

Conceptual blending (Fauconnier & Turner) is credited with much human invention, but `conceptual_blend`
was generator-only. `invent(..., blend_with=[...])` fuses the routed pack with named distant domains and
admits a blend ONLY if its emergence (distance between the two parent breaks) clears `blend_threshold` — so
a distant fusion enters the pool while a self-blend / near-domain blend that would collapse to a transport
is gated out. Competitors search within one representation; none require an emergent property to accept.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import OUTLIER_MCB as gsl


def _operators(inv):
    return [getattr(it["candidate"], "operator", None) for it in inv.frontier]


def test_blend_appears_only_with_blend_with():
    pack = gsl.get_pack("coding")
    base = _operators(gsl.invent("a rate limiter", pack=pack, beam=5, rounds=2))
    blended = _operators(gsl.invent("a rate limiter", pack=pack, beam=5, rounds=2, blend_with=["math"]))
    assert "blend" not in base
    assert "blend" in blended


def test_self_blend_is_excluded():
    pack = gsl.get_pack("coding")
    ops = _operators(gsl.invent("a rate limiter", pack=pack, beam=5, rounds=2, blend_with=["coding"]))
    assert "blend" not in ops


def test_emergence_gate_excludes_low_emergence_blend():
    # generic⊕numeric have emergence 0.929 < 1.0 — a threshold above it must gate the blend out, below it admit it
    pack = gsl.get_pack("generic")
    gated = _operators(gsl.invent("design something", pack=pack, beam=4, rounds=1,
                                  blend_with=["numeric"], blend_threshold=0.95))
    admitted = _operators(gsl.invent("design something", pack=pack, beam=4, rounds=1,
                                     blend_with=["numeric"], blend_threshold=0.90))
    assert "blend" not in gated
    assert "blend" in admitted


def test_unknown_pack_name_is_ignored():
    pack = gsl.get_pack("coding")
    ops = _operators(gsl.invent("a rate limiter", pack=pack, beam=4, rounds=1, blend_with=["no_such_pack"]))
    assert "blend" not in ops          # nothing to blend with → no crash, no blend
