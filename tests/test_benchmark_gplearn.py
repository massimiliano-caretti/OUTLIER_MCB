"""Wiring a REAL external SR backend (gplearn) extends the inventor beyond the zero-dep linear basis.

Opt-in: skipped if gplearn is not installed (it is never a hard dependency). Deterministic (random_state).
GREEN: the gplearn backend recovers a DIVISION law (q/C) that the zero-dep default basis structurally cannot —
proving the engine's `symbolic_evaluator(backend=…)` hook genuinely raises capability, while the rigor (the
judge/frontier) is untouched.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

gplearn = pytest.importorskip("gplearn")     # opt-in: no gplearn ⇒ skip, never fail

import OUTLIER_MCB as g
from evals.benchmarks.feynman import recover, FEYNMAN


def _eq(eid):
    return next(e for e in FEYNMAN if e.id == eid)


def test_default_cannot_recover_division():
    r = recover(_eq("I.25.13"))                                  # q / C, zero-dep basis has no true division
    assert not r.solved


def test_gplearn_backend_recovers_division():
    backend = g.gplearn_backend(function_set=("add", "sub", "mul", "div", "sqrt"),
                                population_size=800, generations=18, random_state=0)
    r = recover(_eq("I.25.13"), backend=backend)                 # q / C
    assert r.solved and r.r2 > 0.999                              # a real recovery the default could not reach
    if r.symbolic is not None:
        assert r.symbolic is True                                 # and it is the EXACT form x0/x1
