"""G5 — solver portfolio: run several backends, the FIRST valid certificate wins (fixed priority, deterministic).

Fully testable without any absent tool: fake backends drive the orchestration; the real z3 confirms an end-to-end
proof; all-absent degrades cleanly. The DONE-critical property — the portfolio closes a lemma z3 alone leaves
unknown — is shown with a fake solver standing in for cvc5/isabelle/etc.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import OUTLIER_MCB as g


def _fake(name, status, ce=None, detail="fake"):
    def prove(conj):
        return status, ce, detail
    prove.backend_name = name
    return prove


def test_portfolio_first_certificate_wins_with_winner_name():
    # z3 leaves it unknown; a second solver decides → the portfolio returns PROVED and records the winner
    port = g.portfolio_backend(backends=[_fake("z3", "TOOL_LIMIT_UNKNOWN"), _fake("cvc5", "FORMALLY_PROVED")])
    cert = g.settle_lemma(g.Conjecture("x", claim_expr="x > 0", variables={"x": (1, 2)}), backend=port)
    assert cert.status == "CVC5_PROVED" and cert.certified is True    # the WINNER's real certificate, not a generic label
    assert port.winner == "cvc5"
    assert port.trace == [("z3", "TOOL_LIMIT_UNKNOWN"), ("cvc5", "FORMALLY_PROVED")]


def test_portfolio_is_deterministic_priority_not_fastest():
    # two solvers both decide → the FIXED-priority (first-listed) one wins, every run
    order = [_fake("z3", "FORMALLY_PROVED", detail="z3"), _fake("cvc5", "FORMALLY_PROVED", detail="cvc5")]
    for _ in range(3):
        port = g.portfolio_backend(backends=order)
        st, ce, detail = port(g.Conjecture("x", claim_expr="x > 0", variables={"x": (1, 2)}))
        assert st == "FORMALLY_PROVED" and port.winner == "z3"        # priority, never wall-clock


def test_portfolio_disproof_propagates_counterexample():
    port = g.portfolio_backend(backends=[_fake("z3", "TOOL_LIMIT_UNKNOWN"),
                                         _fake("cvc5", "FORMALLY_DISPROVED", ce={"x": "0"})])
    cert = g.settle_lemma(g.Conjecture("x", claim_expr="x > 0", variables={"x": (0, 2)}), backend=port)
    assert cert.status == "Z3_REFUTED" and cert.counterexample == {"x": "0"}   # refutation is settled, not certified-true
    assert cert.certified is False


def test_portfolio_all_tools_absent_degrades_cleanly():
    port = g.portfolio_backend(backends=[_fake("cvc5", "TOOL_UNAVAILABLE"), _fake("isabelle", "TOOL_UNAVAILABLE")])
    st, ce, detail = port(g.Conjecture("x", claim_expr="x > 0", variables={"x": (1, 2)}))
    assert st == "TOOL_UNAVAILABLE" and "no solver available" in detail   # no crash
    assert port.winner is None


def test_portfolio_none_decides_aggregates_reasons():
    port = g.portfolio_backend(backends=[_fake("z3", "TOOL_LIMIT_UNKNOWN"), _fake("cvc5", "TOOL_LIMIT_UNKNOWN")])
    st, ce, detail = port(g.Conjecture("x", claim_expr="x > 0", variables={"x": (1, 2)}))
    assert st == "TOOL_LIMIT_UNKNOWN" and "z3=" in detail and "cvc5=" in detail


def test_portfolio_with_real_z3_proves_amgm():
    import importlib.util
    if importlib.util.find_spec("z3") is None:
        import pytest
        pytest.skip("z3 not installed")
    port = g.portfolio_backend()                                    # the real default portfolio; z3 is present
    amgm = g.Conjecture("AM-GM", claim_expr="x**2 + y**2 >= 2*x*y", variables={"x": (-9, 9), "y": (-9, 9)})
    cert = g.settle_lemma(amgm, backend=port)
    assert cert.status == "Z3_PROVED" and cert.certified and port.winner == "z3"
