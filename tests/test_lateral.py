"""test_lateral — human-like lateral moves (provocation, bisociation) + open-ended search discipline
(novelty rejection, novelty-first selection, UCB operator bandit), taken selectively from the competitor
landscape. Deterministic, offline.
"""
import random

import OUTLIER_MCB as m


def _numeric():
    return m.get_pack("numeric")


# ── lateral-thinking generative moves ─────────────────────────────────────────────────────────────────
def test_provocation_is_a_deliberately_false_premise():
    c = m.provocation(_numeric())
    assert c is not None and c.operator == "provocation"
    assert "PROVOCATION" in c.negation and c.breaks                 # asserts an absurd opposite on a real axis
    assert "stepping stone" in c.discipline                         # kept only for the surviving kernel


def test_random_entry_is_a_seeded_distant_bisociation():
    a = m.random_entry(_numeric(), rng=random.Random(1))
    b = m.random_entry(_numeric(), rng=random.Random(1))
    assert a is not None and a.operator == "random_entry"
    assert a.name == b.name                                         # deterministic under the same seed
    assert {x.split("@")[1] for x in a.assumptions} == {"numeric", "causal"} or len(a.assumptions) == 2


# ── novelty rejection sampling ───────────────────────────────────────────────────────────────────────
def test_novelty_rejection():
    accept_same, sim = m.is_novel_enough("an interaction term couples the inputs",
                                         ["an interaction term couples the inputs"], threshold=0.85)
    assert accept_same is False and sim >= 0.85                     # a near-duplicate is refused
    accept_diff, _ = m.is_novel_enough("a latent confounder explains the spurious link",
                                       ["an interaction term couples the inputs"], threshold=0.85)
    assert accept_diff is True


# ── novelty-first selection (abandon the objective) ──────────────────────────────────────────────────
def test_novelty_first_ignores_fitness():
    recs = [
        m.EvolutionRecord(id="a", problem="P", candidate_name="interaction term", claim="couple inputs", score=0.9),
        m.EvolutionRecord(id="b", problem="P", candidate_name="interaction term", claim="couple inputs", score=0.8),
        m.EvolutionRecord(id="c", problem="P", candidate_name="a wholly different galaxy idea", claim="orbit drift", score=0.1),
    ]
    picked = m.novelty_first(recs, k=1)
    assert picked[0].id == "c"                                     # the sparsest, despite the LOWEST score


# ── UCB operator bandit ──────────────────────────────────────────────────────────────────────────────
def test_operator_bandit_explores_then_exploits():
    b = m.OperatorBandit(["invert", "blend", "scale"], c=0.3)      # exploit-leaning exploration constant
    assert b.select() == "invert"                                  # untried first (exploration)
    for _ in range(8):                                             # try every arm a few times
        b.record("invert", 0.1); b.record("blend", 0.9); b.record("scale", 0.2)
    assert b.select() == "blend"                                   # once explored, exploits the high-reward op
    assert b.mean("blend") > b.mean("invert")


# ── opt-in wiring into the evolve loop (default OFF ⇒ no regression) ──────────────────────────────────
def test_evolve_with_lateral_and_rejection():
    task = m.symbolic_invention_task()
    res = m.evolve_invention(task["problem"], task["evaluator"], budget=16, pack=task["pack"],
                             lateral=True, reject_near_duplicates=True)
    ops = {r.mutation_operator for r in res.memory.all()}
    assert "provocation" in ops or "random_entry" in ops           # a lateral move entered the population
    assert len(res.memory.records) <= 16                           # rejection only ever reduces the count


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
