import OUTLIER_MCB as gsl


def _seed_memories(problem):
    pack = gsl.get_pack("numeric")
    evolution = gsl.EvolutionMemory()
    evolution.add(gsl.EvolutionRecord(
        id="ok",
        problem=problem,
        candidate_name="CoupledLaw",
        claim="interaction term improves numeric discovery",
        broken_assumptions=["law_is_separable"],
        score=0.82,
        correctness_passed=True,
        evaluator_name="toy",
    ))
    evolution.add(gsl.EvolutionRecord(
        id="bad1",
        problem=problem,
        candidate_name="RenamedMetricA",
        broken_assumptions=["noise_is_iid"],
        score=0.1,
        correctness_passed=False,
    ))
    evolution.add(gsl.EvolutionRecord(
        id="bad2",
        problem=problem,
        candidate_name="RenamedMetricB",
        broken_assumptions=["noise_is_iid"],
        score=0.12,
        correctness_passed=False,
    ))

    discovery = gsl.DiscoveryMemory()
    discovery.record("law_is_separable", axis="INTERACTION", domain="numeric", confirmed=True)
    discovery.record("static_world", axis="TIME", domain="numeric", confirmed=False)
    discovery.record("static_world", axis="TIME", domain="numeric", confirmed=False)
    discovery.promote("hidden_phase_transition", axis="REGIME", domain="numeric")

    episodic = gsl.EpisodicMemory()
    episodic.record(gsl.Episode(
        problem=problem,
        assumption="law_is_separable",
        domain="numeric",
        outcome="CONFIRMED",
        score=0.8,
    ))

    analogical = gsl.AnalogicalMemory()
    analogical.record(
        "ecology",
        "numeric",
        transferred=True,
        mapping="use niche pressure as a selector for rare mechanisms",
        emergence=0.9,
    )

    skills = gsl.SkillLibrary.with_seed()
    lessons = gsl.LessonMemory()
    lessons.record(gsl.EvolutionRecord(
        id="leak",
        problem=problem,
        candidate_name="LeakageWin",
        correctness_passed=True,
        score_components={"leakage_detected": 1.0},
        improvement_over_baseline=1.0,
    ))
    return pack, evolution, discovery, episodic, analogical, skills, lessons


def test_creative_memory_router_combines_memories_into_actionable_plan():
    problem = "discover a non-obvious numeric law outside separable averages"
    pack, evolution, discovery, episodic, analogical, skills, lessons = _seed_memories(problem)
    router = gsl.CreativeMemoryRouter(
        pack=pack,
        evolution_memory=evolution,
        discovery_memory=discovery,
        episodic_memory=episodic,
        analogical_memory=analogical,
        skill_library=skills,
        lesson_memory=lessons,
    )

    plan = router.plan(problem, k=20)
    sources = {cue.source for cue in plan.cues}
    assert {"unknown_space", "lesson", "discovery", "episode", "analogy", "skill", "evolution"} <= sources
    assert plan.recommended_strategy in gsl.STRATEGIES
    assert "MEMORY ROUTER" in plan.prompt_block
    assert "EXPLORE" in plan.prompt_block
    assert "AVOID / MUTATE" in plan.prompt_block
    assert "TRANSFER" in plan.prompt_block
    assert "REUSE SKILLS" in plan.prompt_block


def test_prompt_sampler_injects_router_and_uses_its_strategy():
    problem = "discover a non-obvious numeric law outside separable averages"
    pack, evolution, discovery, episodic, analogical, skills, lessons = _seed_memories(problem)
    router = gsl.CreativeMemoryRouter(
        pack=pack,
        evolution_memory=evolution,
        discovery_memory=discovery,
        episodic_memory=episodic,
        analogical_memory=analogical,
        skill_library=skills,
        lesson_memory=lessons,
    )
    sampler = gsl.PromptSampler(
        pack,
        memory=evolution,
        evaluator_objective="beat hidden numeric cases with falsifiable controls",
        memory_router=router,
    )

    prompt = sampler.sample(problem)
    assert "MEMORY ROUTER" in prompt
    assert "STRATEGY: explore_unknown_axis" in prompt
    assert "leakage" in prompt
    assert "ecology->numeric" in prompt


def test_router_prioritizes_mutating_failures_when_unknown_space_is_absent():
    problem = "same constrained problem"
    pack, evolution, discovery, episodic, analogical, skills, lessons = _seed_memories(problem)
    discovery.discovered.clear()
    router = gsl.CreativeMemoryRouter(
        evolution_memory=evolution,
        discovery_memory=discovery,
        episodic_memory=episodic,
        analogical_memory=analogical,
        skill_library=skills,
        lesson_memory=lessons,
    )

    plan = router.plan(problem, k=20)
    assert plan.recommended_strategy == "mutate_failed_candidate"
    assert any(c.action == "avoid_failure_mode" for c in plan.cues)
