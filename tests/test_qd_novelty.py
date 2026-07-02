"""Tests for Quality-Diversity (MAP-Elites), formal Novelty Search, and the intrinsic goal-setter.
Deterministic, offline. Run: python -m pytest tests/test_qd_novelty.py -q."""
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import OUTLIER_MCB as gsl  # noqa: E402
from OUTLIER_MCB.qd import QDArchive, BehaviorDescriptor, _complexity_bin  # noqa: E402
from OUTLIER_MCB.novelty_archive import NoveltyArchive, behavior_descriptor, _distance  # noqa: E402


def _coding():
    return gsl.get_pack("coding")


# ── QD / MAP-Elites ──
def test_behavior_descriptor_dimensions():
    p = _coding()
    c = gsl.recombine_assumptions(p, k=2, max_candidates=1)[0]
    bd = BehaviorDescriptor.of(c, p)
    assert bd.abstraction_level in (1, 2, 3)
    assert len(bd.axes_vector) == len(p.axes)              # one slot per pack axis
    assert sum(bd.axes_vector) == len(set(c.breaks))       # multi-hot over the broken axes
    assert isinstance(bd.complexity, int)


def test_qd_archive_keeps_one_elite_per_cell_by_quality():
    p = _coding()
    arc = QDArchive(pack=p, quality_fn=lambda c: 0.1)      # fixed low quality
    c = gsl.generate_candidates(p)[0]
    assert arc.add(c) is True                              # empty cell → admitted
    assert arc.add(c, quality=0.05) is False               # worse → rejected
    assert arc.add(c, quality=0.9) is True                 # better → replaces the elite
    assert arc.grid[arc.cell_of(c)][0] == 0.9


def test_qd_archive_illuminates_multiple_cells():
    arc = gsl.illuminate(_coding(), "design a rate limiter", iterations=20)
    assert arc.coverage() >= 3                             # a MAP, not a single point
    assert arc.qd_score() > 0
    assert arc.best() is not None
    assert arc.empty_regions()                             # there are unfilled regions to target


def test_qd_archive_is_deterministic():
    a = gsl.illuminate(_coding(), "design a rate limiter", iterations=20)
    b = gsl.illuminate(_coding(), "design a rate limiter", iterations=20)
    assert a.coverage() == b.coverage() and a.qd_score() == b.qd_score()


def test_invent_returns_a_qd_map_without_breaking_the_frontier():
    inv = gsl.invent("design a rate limiter", repo_path=str(ROOT), beam=6, rounds=2)
    assert inv.best() is not None                          # backward-compatible frontier API
    assert inv.archive is not None and inv.qd_map() is inv.archive
    assert inv.archive.coverage() >= 2


# ── Novelty Search (sparseness) ──
def test_novelty_archive_sparseness_drops_as_space_fills():
    p = _coding()
    ns = NoveltyArchive()
    cands = gsl.generate_candidates(p)
    bd0 = behavior_descriptor(cands[0])
    assert ns.calculate_novelty(bd0) == 1.0               # empty archive → maximally novel
    for c in cands:
        ns.add(behavior_descriptor(c))
    # an idea already represented in the archive is now far LESS novel than against an empty archive
    assert ns.calculate_novelty(bd0) < 1.0


def test_novelty_distance_is_a_unit_metric():
    assert _distance(set(), set()) == 0.0
    assert _distance({"a", "b"}, {"a", "b"}) == 0.0
    assert _distance({"a"}, {"b"}) == 1.0


def test_add_if_novel_uses_a_dynamic_threshold():
    ns = NoveltyArchive()
    assert ns.add_if_novel({"alpha", "beta", "gamma"}) is True     # first always admitted
    assert ns.add_if_novel({"alpha", "beta", "gamma"}) is False    # identical → not novel enough
    assert ns.add_if_novel({"delta", "epsilon", "zeta"}) is True   # disjoint → novel → admitted


def test_scoring_uses_novelty_search_when_an_archive_is_given():
    p = _coding()
    c = gsl.recombine_assumptions(p, k=2, max_candidates=1)[0]
    plain = gsl.score_idea(c, pack=p)["novelty"]
    ns = NoveltyArchive()
    ns.add(behavior_descriptor(c))
    relative = gsl.score_idea(c, pack=p, novelty_archive=ns)["novelty"]
    assert relative < plain                                # already-seen idea is less novel relative to the archive
    assert gsl.score_idea(c, pack=p)["novelty"] == plain   # without an archive, behavior is unchanged


# ── intrinsic goal-setter ──
def test_propose_goal_reads_the_map_and_asks_for_a_falsifiable_world_test():
    p = _coding()
    arc = gsl.illuminate(p, "design a rate limiter", iterations=20)
    goal = gsl.propose_goal(arc, p)
    assert "world-test" in goal.lower()
    assert "negative control" in goal.lower()             # it demands a falsifiable test
    assert "unexplored" in goal.lower() or "no good idea" in goal.lower()
    assert p.box_name in goal                              # grounded in the domain box


def test_complexity_binning_is_coarse():
    assert _complexity_bin(1) == 0 and _complexity_bin(3) == 1 and _complexity_bin(9) == 2
