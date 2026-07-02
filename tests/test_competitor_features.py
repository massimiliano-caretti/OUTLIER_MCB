"""test_competitor_features — the 4 genuinely-new mechanisms taken from competitors:
cross-domain analogy (distant transfer), POET problem generation, DreamCoder abstraction mining, and the
Voyager skill library. Deterministic, offline.
"""
import OUTLIER_MCB as m


# ── cross-domain analogy engine ──────────────────────────────────────────────────────────────────────
def test_analogy_engine_transfers_from_distant_domains():
    eng = m.CrossDomainAnalogyEngine(m.get_pack("numeric"))
    assert set(eng.source_domains()) >= {"causal", "coding", "math"}     # other registered domains
    best = eng.best_analogies(2)
    assert best and all(a.candidate is not None and a.transfer_claim for a in best)
    assert best[0].analogy_distance >= best[-1].analogy_distance         # farthest analogies first (lateral)
    assert best[0].target_domain == "numeric"


# ── POET problem generation ──────────────────────────────────────────────────────────────────────────
def test_problem_generator_makes_new_problems_with_falsifiers():
    pg = m.ProblemGenerator(m.get_pack("numeric"))
    variants = pg.generate_problem_variants("discover the law", n=2)
    assert variants and all(v.kind == "variant" and v.falsifier and v.new_measure for v in variants)
    adv = pg.generate_adversarial_world("discover the law")
    assert adv.kind == "adversarial" and "must fail" in adv.falsifier
    hard = pg.generate_harder_environment("discover the law")
    assert hard.kind == "harder" and "1000×" in hard.statement


# ── DreamCoder abstraction mining ─────────────────────────────────────────────────────────────────────
def test_abstraction_mining_extracts_shared_concepts():
    recs = [
        m.EvolutionRecord(id="1", problem="P", candidate_name="a", broken_assumptions=["law_is_separable"]),
        m.EvolutionRecord(id="2", problem="Q", candidate_name="b", broken_assumptions=["law_is_separable"]),
        m.EvolutionRecord(id="3", problem="R", candidate_name="c", broken_assumptions=["law_is_smooth"]),
    ]
    lib = m.mine_abstractions(recs, min_support=2)
    concepts = lib.all()
    assert len(concepts) == 1 and concepts[0].support == 2                # the shared structure; the singleton is NOT a concept
    assert "law_is_separable" in concepts[0].pattern
    assert lib.reuse_concept_in_new_domain(concepts[0].name, m.get_pack("causal"))   # reusable elsewhere


# ── Voyager skill library ─────────────────────────────────────────────────────────────────────────────
def test_skill_library_retrieve_record_compose(tmp_path):
    lib = m.SkillLibrary.with_seed()
    assert len(lib.skills) == len(m.SEED_SKILLS)
    got = lib.retrieve_skills("a universal claim that always holds — find a counterexample")
    assert any(s.name == "minimal_counterexample" for s in got)          # retrieved by cue overlap
    lib.record_outcome("minimal_counterexample", success=True)
    lib.record_outcome("minimal_counterexample", success=True)
    assert lib.skills["minimal_counterexample"].success_rate == 1.0      # learns its success rate
    composed = lib.compose_skills("minimal_counterexample", "find_latent_variable")
    assert composed and "∘" in composed.move                            # tool-level recombination
    p = str(tmp_path / "skills.jsonl")
    lib.save_jsonl(p)
    assert "minimal_counterexample" in m.SkillLibrary.load_jsonl(p).skills


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
