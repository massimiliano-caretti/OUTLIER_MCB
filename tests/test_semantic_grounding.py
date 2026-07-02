"""test_semantic_grounding — Point 2: the engine coins its OWN concepts for recurring patterns, scored by an
external MDL compression ratio. Empty/ungrounded symbols give no gain (controls), and the honesty is a protected
invariant. Deterministic and offline.
"""
import OUTLIER_MCB as gsl
from OUTLIER_MCB.semantic_grounding import (SymbolRegistry, find_recurring_patterns, ground_new_symbol,
                                               conceptual_compression, verify_grounding, EndogenousSymbol)


def _log():
    motif = ["settle", "timeout", "retry"]
    return motif * 8 + ["ok"] + motif * 4


def test_grounds_a_recurring_pattern_and_compresses():
    log = _log()
    reg = SymbolRegistry()
    pat = find_recurring_patterns(log)[0][0]
    sym = ground_new_symbol(pat, log, reg)
    assert sym is not None and sym.is_grounded and sym.name in reg.symbols
    assert conceptual_compression(log, [sym]) > 1.0        # naming the motif genuinely compresses the log


def test_refuses_a_non_recurring_pattern():
    log = _log()
    assert ground_new_symbol(("ok",), log) is None         # occurs once, trivial → refused (no empty concept)
    assert ground_new_symbol(("never", "seen"), log) is None


def test_ungrounded_symbol_gives_no_gain():
    log = _log()
    ghost = EndogenousSymbol("_GHOST", ("never", "seen", "here"), support=99)   # lies about its support
    assert verify_grounding(ghost, log) is False           # re-checked against the log → not grounded
    assert conceptual_compression(log, [ghost]) <= 1.0     # and it cannot compress anything


def test_no_repetition_no_gain():
    distinct = [f"e{i}" for i in range(30)]
    reg = SymbolRegistry()
    syms = [s for s in (ground_new_symbol(p, distinct, reg) for p, _ in find_recurring_patterns(distinct)) if s]
    assert conceptual_compression(distinct, syms) <= 1.0


def test_grounding_is_a_protected_invariant():
    from OUTLIER_MCB.self_repair import verify_invariants, INVARIANT_REGISTRY
    assert "symbol_is_grounded" in INVARIANT_REGISTRY
    rep = verify_invariants()
    assert rep.ok and "symbol_is_grounded" in rep.passed_names


def test_conceptual_compression_dimension_benchmark():
    from evals.benchmarks.compression import conceptual_compression_score, controls_pass
    assert controls_pass() is True
    assert conceptual_compression_score() > 1.0            # a realistic diagnostic log compresses via concepts
