"""test_memory_and_orchestration — the two new memories + the autonomous inventor that wires everything.

Episodic memory recalls and blocks reinventing a dead end; analogical memory grades domain pairings; the
orchestrator threads problem-finding + blending + transformation + all memories into one loop. Deterministic.
"""
import OUTLIER_MCB as gsl


# ── episodic memory ─────────────────────────────────────────────────────────────────────────────────
def test_episodic_recall_and_refuted_guard():
    m = gsl.EpisodicMemory()
    m.record(gsl.Episode(problem="break separability in numeric law discovery", assumption="law_is_separable",
                         outcome="REFUTED"))
    hits = m.recall("break separability in numeric law discovery")
    assert hits and hits[0][1] >= 0.8                        # near-identical recalled with high similarity
    assert m.has_refuted("break separability in numeric law discovery") is True
    assert m.has_refuted("an utterly unrelated question about sourdough") is False
    assert "DEAD END" in m.lessons("break separability in numeric law discovery")


def test_episodic_persistence(tmp_path):
    m = gsl.EpisodicMemory()
    m.record(gsl.Episode(problem="p", assumption="a", outcome="CONFIRMED", score=0.9))
    p = str(tmp_path / "epi.json")
    m.save(p)
    assert gsl.EpisodicMemory.load(p).episodes[0].outcome == "CONFIRMED"


# ── analogical memory ───────────────────────────────────────────────────────────────────────────────
def test_analogical_grades_pairings():
    m = gsl.AnalogicalMemory()
    for _ in range(3):
        m.record("numeric", "causal", transferred=True, emergence=0.9)
    m.record("numeric", "math", transferred=False)
    m.record("numeric", "math", transferred=False)
    assert m.prior("numeric", "causal") == 1.0
    assert m.analogies["numeric->causal"].status == "TRANSFERS_WELL"
    assert [o.target_domain for o in m.fertile()] == ["causal"]


# ── the autonomous inventor (orchestration) ───────────────────────────────────────────────────────────
def test_inventor_wires_mechanisms_and_compounds_memory():
    run = gsl.autonomous_inventor(pack=gsl.get_pack("numeric"), blend_with=["causal"], accept=0.0)
    assert run.steps                                         # it acted
    assert run.discovery_memory.outcomes                     # discovery memory was written
    assert run.episodic.episodes                             # episodic memory was written
    assert run.provisional is True                           # structural evaluator ⇒ honest provisional flag
    assert any(s.domain.startswith("blend:") for s in run.steps)   # blending was used


def test_inventor_skips_a_known_dead_end():
    epi = gsl.EpisodicMemory()
    # pre-seed a refutation of a single-axis numeric problem so recall blocks it
    epi.record(gsl.Episode(
        problem="What if «The inputs are coupled: an irreducible interaction term carries the signal.» "
                "— i.e. 'law_is_separable' is false in numeric?",
        assumption="law_is_separable", outcome="REFUTED"))
    run = gsl.autonomous_inventor(pack=gsl.get_pack("numeric"), blend_with=[], episodic=epi, accept=0.0)
    assert any(s.outcome == "SKIPPED" for s in run.steps)    # the dead end was not reinvented


def test_inventor_transforms_when_stuck():
    # an impossible acceptance bar ⇒ nothing clears ⇒ transformational creativity expands the space.
    run = gsl.autonomous_inventor(pack=gsl.get_pack("numeric"), blend_with=["causal"], accept=2.0)
    assert run.expanded_pack is not None
    assert "EMERGENT_REGIME" in run.expanded_pack.axes
    assert run.discovery_memory.discovered                   # the invented axis was promoted into memory


def test_markdown_renders():
    run = gsl.autonomous_inventor(pack=gsl.get_pack("numeric"), blend_with=[], accept=0.0)
    assert "Autonomous inventor" in run.markdown()


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
