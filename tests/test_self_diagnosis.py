"""Self-diagnosis — point-logs + a separate diagnostic memory + self_diagnose.

A run that does not finish leaves a post-mortem; self_diagnose ranks the weak spots and names the bottleneck.
Negative control: an all-OK, completed run yields a 'healthy, nothing to repair' report.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import OUTLIER_MCB as gsl
from OUTLIER_MCB.self_diagnosis import (DiagnosticLog, DiagnosticMemory, diagnostic_run, self_diagnose)
from OUTLIER_MCB.math_discovery import Conjecture
from OUTLIER_MCB.frontier_search import frontier_search, LemmaCandidate


def test_point_log_records_and_validates_status():
    log = DiagnosticLog(task="t")
    log.ok("gen", "generated"); log.bottleneck("settle", "slow solver"); log.failed("settle", "no certificate")
    assert len(log.points) == 3 and [p.seq for p in log.points] == [0, 1, 2]
    assert len(log.unresolved()) == 2
    try:
        log.point("x", "NOPE", "bad")
        assert False, "invalid status must raise"
    except ValueError:
        pass


def test_diagnostic_run_records_even_on_exception():
    mem = DiagnosticMemory()
    try:
        with diagnostic_run("crashy", memory=mem) as log:
            log.weak("gen", "thin")
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert len(mem.runs) == 1 and mem.runs[0]["task"] == "crashy"   # the crash post-mortem was kept


def test_self_diagnose_finds_bottleneck_and_weak_spots():
    mem = DiagnosticMemory()
    with diagnostic_run("task A", memory=mem) as log:
        log.ok("generation", "ok")
        log.bottleneck("settlement", "solver timed out")
        log.failed("settlement", "no external certificate")
        log.mark_completed(False)
    rep = self_diagnose(mem)
    assert not rep.healthy
    assert rep.bottleneck_phase == "settlement"
    assert rep.unresolved_runs == 1 and rep.total_runs == 1
    assert rep.weak_spots[0].phase == "settlement"
    assert "settlement" in rep.dominant_failure


def test_healthy_run_has_nothing_to_repair():
    mem = DiagnosticMemory()
    with diagnostic_run("clean", memory=mem) as log:
        log.ok("generation", "ok"); log.ok("settlement", "certified"); log.mark_completed(True)
    rep = self_diagnose(mem)
    assert rep.healthy and not rep.weak_spots


def test_memory_round_trip_is_deterministic():
    mem = DiagnosticMemory()
    with diagnostic_run("t", memory=mem) as log:
        log.failed("settle", "x"); log.mark_completed(False)
    path = os.path.join(tempfile.mkdtemp(), "diag.json")
    mem.save(path)
    again = DiagnosticMemory.load(path)
    assert len(again.unresolved_runs()) == 1
    again.save(path)
    with open(path) as f:
        first = f.read()
    again.save(path)
    with open(path) as f:
        assert f.read() == first


def test_frontier_search_emits_diagnostics_when_objective_not_reached():
    log = DiagnosticLog(task="twin")
    cands = [LemmaCandidate("H<=14", Conjecture(statement="b14", variables={"n": (1, 5)}, domain="int"),
                            "H", 14, "decrease", predicate=lambda n: True),
             LemmaCandidate("H<=5 FALSE", Conjecture(statement="b5", variables={"n": (1, 20)}, domain="int"),
                            "H", 5, "decrease", predicate=lambda n: n * n < 100)]
    frontier_search("twin_primes", cands, objective_metric="H", objective_value=2, log=log)
    assert not log.completed                                  # objective (H=2) not reached
    statuses = {p.status for p in log.points}
    assert "OK" in statuses and "FAILED" in statuses and "BOTTLENECK" in statuses
    rep = self_diagnose(log)
    assert rep.bottleneck_phase in ("frontier", "settlement")
