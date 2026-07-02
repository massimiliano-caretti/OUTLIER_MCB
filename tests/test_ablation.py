"""test_ablation — fix C: the gameability/ablation gate. A scoring component earns its place only if it
flips a keep/drop decision; one that varies yet never flips is DECORATIVE; a constant one is untestable
here; a hard gate (correctness) is protected. Deterministic, offline."""
import OUTLIER_MCB as m


def _items():
    out = []
    for i in range(8):
        out.append({
            "correctness": 1.0,           # constant + protected → structural gate
            "reproducibility": 1.0,       # constant → untestable here
            "diversity": i / 8.0,         # varies AND dominates the ranking → earned
            "simplicity": (i % 2) * 0.01,  # varies but too small to flip → decorative
        })
    return out


def test_ablation_gate_separates_earned_decorative_untestable_and_gates():
    rep = m.ablation_gate(_items(), keep_fraction=0.5)
    assert "diversity" in rep.earned()                 # it changes who is kept
    assert "simplicity" in rep.decorative()            # varies yet never flips a decision → delete/merge
    assert "reproducibility" in rep.untestable_here()  # constant in this population → cannot be tested here
    assert "correctness" in rep.structural_gates()     # hard gate → reported, never auto-dropped
    assert "more metrics is better" in rep.markdown().lower()


def test_decorative_excludes_constant_and_protected():
    rep = m.ablation_gate(_items(), keep_fraction=0.5)
    # the honest distinction: a constant or protected component is NEVER mislabeled 'decorative'
    assert "reproducibility" not in rep.decorative()
    assert "correctness" not in rep.decorative()


def test_evolve_result_exposes_ablation():
    task = m.symbolic_invention_task()
    res = m.evolve_invention(task["problem"], task["evaluator"], budget=12, pack=task["pack"])
    ab = res.ablation()
    assert isinstance(ab, m.AblationReport)
    assert "correctness" in ab.structural_gates()      # correctness is never recommended for deletion
    assert len(ab.verdicts) == len(m.INVENTION_COMPONENTS)   # every component is judged
    assert "correctness" not in ab.decorative()        # a hard gate is never called decorative


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
