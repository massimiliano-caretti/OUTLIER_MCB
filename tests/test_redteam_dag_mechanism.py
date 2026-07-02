"""test_redteam_dag_mechanism — #10 a red team that GENERATES its own attacks, #12 staged falsification via
an experiment DAG, #7 a deeper mechanism-level abstraction miner. Deterministic, offline."""
import OUTLIER_MCB as m


class _Cand:
    def __init__(self, value=1.0):
        self.value = value
        self.name = "inv(x)"
        self.negation = "break the additive box"


# ── #10 red team ──────────────────────────────────────────────────────────────────────────────────────
def test_red_team_keeps_robust_rejects_leaky():
    check = lambda cand, case: float(getattr(cand, "value", 0)) * case > 0.5
    rt = m.red_team_from_check(check, public_cases=[1.0, 2.0], mutators=[lambda x: x * 0.6],
                               negative_controls=[0.0])
    r = rt.evaluate(_Cand(1.0))
    assert r.passed and r.components["survived_fraction"] == 1.0 and r.components["leakage_detected"] == 0.0

    leaky = lambda cand, case: True                        # passes the negative control too → leakage
    r2 = m.red_team_from_check(leaky, public_cases=[1.0], negative_controls=[0.0]).evaluate(_Cand())
    assert not r2.passed and r2.components["leakage_detected"] == 1.0


def test_red_team_is_a_correctness_gate_and_attack_errors_count_as_break():
    assert m.RedTeamEvaluator([]).is_correctness is True
    def boom(cand):
        raise RuntimeError("x")
    r = m.RedTeamEvaluator([m.Attack(name="boom", survived=boom)]).evaluate(_Cand())
    assert not r.passed and "boom" in r.error                # an attack that errors is a break, never a pass


def test_rebrand_attack_breaks_on_a_close_prior_art_match():
    class _Match:                                            # a provider returning a near-identical work
        def research(self, q):
            return {"matches": [{"title": q, "url": "u", "similarity": 0.95}]}
    att = m.rebrand_attack(_Match(), claim_text="a distributed rate limiter")
    assert att.survived(_Cand()) is False                    # renamed known idea ⇒ does not survive
    class _Empty:
        def research(self, q):
            return {"matches": []}
    assert m.rebrand_attack(_Empty(), claim_text="x").survived(_Cand()) is True


# ── #12 experiment DAG (staged falsification) ───────────────────────────────────────────────────────────
def test_experiment_dag_blocks_downstream_when_a_link_breaks():
    dag = m.ExperimentDAG()
    dag.add_step("baseline_fails", lambda: True)
    dag.add_step("passes_hidden", lambda: True, requires=["baseline_fails"])
    dag.add_step("survives_redteam", lambda: False, requires=["passes_hidden"])
    dag.add_step("settled_claim", lambda: True, requires=["survives_redteam"])
    rep = dag.run()
    assert not rep.settled
    assert rep.by_name["settled_claim"].status == "SKIPPED"        # never ran — prerequisite broke
    assert rep.blocked() == ["survives_redteam", "settled_claim"]
    assert "UNSETTLED" in rep.conservative_statement()


def test_experiment_dag_settled_only_end_to_end():
    dag = m.ExperimentDAG()
    dag.add_step("a", lambda: True)
    dag.add_step("b", lambda: (True, "passed"), requires=["a"])
    rep = dag.run()
    assert rep.settled and rep.all_passed and rep.blocked() == []


def test_experiment_dag_detects_cycles_and_unknown_prereqs():
    import pytest
    bad = m.ExperimentDAG()
    bad.add_step("x", lambda: True, requires=["y"])
    bad.add_step("y", lambda: True, requires=["x"])
    with pytest.raises(ValueError):
        bad.run()
    miss = m.ExperimentDAG()
    miss.add_step("x", lambda: True, requires=["ghost"])
    with pytest.raises(ValueError):
        miss.run()


# ── #7 mechanism-level abstraction (deeper than exact-set clustering) ──────────────────────────────────
def test_mechanism_miner_finds_cross_cutting_levers_that_exact_miner_misses():
    pack = m.get_pack("coding")
    a, b, c = [x.name for x in pack.assumptions][:3]
    recs = [m.EvolutionRecord(id="r1", problem="P1", candidate_name="x", broken_assumptions=[a, b]),
            m.EvolutionRecord(id="r2", problem="P2", candidate_name="y", broken_assumptions=[a, c]),
            m.EvolutionRecord(id="r3", problem="P3", candidate_name="z", broken_assumptions=[b])]
    exact = m.mine_abstractions(recs, min_support=2)
    mech = m.mine_mechanism_abstractions(recs, pack=pack, min_support=2)
    assert exact.all() == []                                  # every full break-set differs → exact miner finds nothing
    names = {c.name for c in mech.all()}
    assert ("mechanism_" + a) in names                        # the recurring lever `a` (in r1 AND r2) is surfaced
    assert all(c.level == "mechanism" for c in mech.all())


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
