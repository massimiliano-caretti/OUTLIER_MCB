"""packs/meta — the SELF domain: reasoning about how to improve a creativity/falsification engine.

Why this exists: applied to its own internals (`invent('a better way to rank breakable assumptions')`),
the engine routed to `generic` and returned undifferentiated transports — it had no pack for its OWN
domain. This pack names the hidden assumptions of the average answer to "improve a creativity engine"
(add more metrics, more generators, a bigger prompt, let it score itself) so a meta-improvement must break
one of THEM. Verdicts are HEURISTIC priors distilled from the engine's own thesis, not validated truth.

Pass it explicitly for a library-improvement task: `gsl.invent(prompt, pack=gsl.get_pack('meta'))` /
`gsl.judge(idea, pack=gsl.get_pack('meta'))`.
"""
from __future__ import annotations
from ..core import Assumption
from ..pack import DomainPack, register_pack

A = [
    Assumption("more_metrics_is_better",
               "Adding scoring components makes the engine better.",
               "A richer score looks more rigorous, so more factors seem strictly better.",
               "A metric that cannot be gamed-tested is decorative; fewer falsifiable signals beat more.",
               ["add_more_metrics", "internal_scoring", "ensemble_of_heuristics"],
               "an ablation where removing the metric leaves verified-novelty unchanged proves it was decorative."),
    Assumption("generation_is_the_bottleneck",
               "Better idea GENERATION is what the engine needs most.",
               "Creativity feels like a generation problem, so more operators seem to be the lever.",
               "The bottleneck is SETTLEMENT, not generation: more candidates without verification is noise.",
               ["more_generators", "bigger_prompt"],
               "a run where adding generators raises coverage but not verified-novelty shows generation was not the lever."),
    Assumption("the_engine_judges_itself",
               "The engine can certify the quality of its own output.",
               "It already computes a score, so letting that score decide seems sufficient.",
               "Only an EXTERNAL resolver (repo / data / world) certifies; self-judgment is circular.",
               ["internal_scoring", "ensemble_of_heuristics"],
               "a candidate that scores high internally yet fails an external world-test exposes the circularity."),
    Assumption("novelty_is_naming",
               "A fresh name or a recombination of known parts is novelty.",
               "A new label and a clever mashup read as new, so naming feels like inventing.",
               "Novelty is a broken assumption plus a world-test where the known family provably fails.",
               ["rename_the_output", "ensemble_of_heuristics"],
               "a prior-art search that finds the renamed mechanism downgrades the claim to a rebrand."),
    Assumption("pack_knowledge_is_in_the_engine",
               "Domain logic can live wherever it is convenient in the engine.",
               "Hard-coding a domain token in a kernel module is the quick path that just works.",
               "Domain knowledge must live ONLY in packs; an engine that bakes in a domain is not agnostic.",
               ["internal_scoring"],
               "the agnosticism guard finding a pack-specific token in an engine module refutes the convenience."),
    Assumption("problem_space_is_static",
               "The engine only SOLVES the problems it is given; the problem set is fixed.",
               "Benchmarks are handed to you, so 'improving' reads as scoring higher on a fixed set.",
               "A fixed benchmark has a ceiling; real exploration MANUFACTURES new, harder, externally-settled "
               "problems (a curriculum) and climbs them — raising the ceiling instead of saturating it.",
               ["solve_the_given_benchmark", "more_generators"],
               "a generated problem with KNOWN ground truth that the current engine cannot yet solve, settled by an "
               "external resolver, raises the ceiling — while a scrambled-target version stays unsolvable (negative control)."),
    Assumption("benchmark_ceiling_is_fixed",
               "Any curriculum saturates: once every rung is solved, exploration is DONE (a score hits 1.0 and stops).",
               "A finite benchmark and a finite primitive set have a ceiling, so a saturating metric feels inevitable.",
               "Open-endedness needs an UNBOUNDED generator over an EXPANDING primitive space plus a minimal-criterion "
               "gate (novel AND unsolved-now AND externally settleable): a RATCHET (max certified depth) that never "
               "saturates and never regresses. The only real ceiling is compute — declared honestly — not the concept.",
               ["saturating_score", "fixed_curriculum", "fixed_primitive_set"],
               "a ratchet reach that keeps climbing (each new depth certified by an external resolver + a scrambled "
               "negative control) with no built-in 1.0 — a saturating [0,1] score is the tell of a fixed ceiling."),
]

_axes = {
    "EVALUATION":  {"priority": 3, "verdict": "HEURISTIC: who CERTIFIES is the deepest lever — an external resolver beats any internal score."},
    "NOVELTY":     {"priority": 3, "verdict": "HEURISTIC: novelty by falsification (a broken axis + a failing family) beats novelty by naming."},
    "AGNOSTICISM": {"priority": 3, "verdict": "HEURISTIC: keeping the engine domain-blind (all knowledge in packs) is load-bearing, not cosmetic."},
    "SCORING":     {"priority": 2, "verdict": "HEURISTIC: fewer falsifiable, ungameable signals beat more decorative metrics."},
    "GENERATION":  {"priority": 2, "verdict": "HEURISTIC: settlement, not generation, is usually the bottleneck — verify before you generate more."},
    "EXPLORATION": {"priority": 3, "verdict": "HEURISTIC: manufacturing new externally-settled problems (a curriculum that raises the ceiling) beats squeezing a fixed benchmark."},
}
_dim = {"the_engine_judges_itself": "EVALUATION", "novelty_is_naming": "NOVELTY",
        "pack_knowledge_is_in_the_engine": "AGNOSTICISM", "more_metrics_is_better": "SCORING",
        "generation_is_the_bottleneck": "GENERATION", "problem_space_is_static": "EXPLORATION",
        "benchmark_ceiling_is_fixed": "EXPLORATION"}
_edges = [
    ("the_engine_judges_itself", "if_false_requires", "external_resolver", "external certification needs a repo/data/world resolver"),
    ("novelty_is_naming", "if_false_requires", "prior_art_corpus", "refuting a rebrand needs a real prior-art corpus"),
    ("more_metrics_is_better", "if_false_requires", "ablation_evidence", "pruning a decorative metric needs ablation evidence"),
    ("pack_knowledge_is_in_the_engine", "blocks", "the_engine_judges_itself", "baked-in domain logic corrupts external judgment"),
    ("problem_space_is_static", "if_false_requires", "generated_problem_landscape", "manufacturing harder problems needs an externally-settled problem landscape"),
    ("benchmark_ceiling_is_fixed", "if_false_requires", "unbounded_generator", "unlimited exploration needs an unbounded generator over an expanding primitive space"),
    ("benchmark_ceiling_is_fixed", "blocks", "problem_space_is_static", "a saturating curriculum is just the static problem space wearing a score"),
]

PACK = DomainPack(
    name="meta",
    keywords=["creativity engine", "falsification engine", "assumption-negation", "novelty audit",
              "improve the engine", "scoring metric", "domain pack", "breakable assumption",
              "self-improve", "rigor theater"],
    box_name="the average way to improve a creativity engine: add more metrics, more generators, a bigger prompt, let it score itself",
    assumptions=A,
    relations=_edges,
    dimension_of=_dim,
    box_assumptions={"more_metrics_is_better", "generation_is_the_bottleneck", "the_engine_judges_itself"},
    axes=_axes,
    known_families=["add_more_metrics", "bigger_prompt", "more_generators", "internal_scoring",
                    "rename_the_output", "ensemble_of_heuristics", "solve_the_given_benchmark"],
    info_kinds={"external_resolver": "a repo/data/world that settles a bet → ends self-judgment circularity.",
                "prior_art_corpus": "a real corpus to search → tells a rebrand from genuine novelty.",
                "ablation_evidence": "remove-and-measure data → tells a load-bearing metric from a decorative one.",
                "held_out_task": "an unseen task → tells generalization from overfitting to the engine's own arena.",
                "generated_problem_landscape": "a manufactured problem with KNOWN ground truth + external resolver + "
                "negative control → lets the engine raise its own ceiling without self-judging.",
                "unbounded_generator": "a generator over an EXPANDING primitive space (grow a primitive on demand) → "
                "turns a saturating curriculum into a ratchet with no built-in ceiling (only compute bounds it)."},
    failure_memory={},
    world_factory=None,
)
register_pack(PACK)
