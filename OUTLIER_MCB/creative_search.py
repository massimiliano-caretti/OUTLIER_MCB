"""creative_search — a FunSearch-style evolutionary loop over OUTLIER_MCB's operators.

Literature: FunSearch (Romera-Paredes et al., DeepMind 2023) — an LLM proposes candidates, an EXTERNAL
evaluator scores them, the best are kept in a programs database, and the search evolves from them. The
key discipline is that quality is decided by an external evaluator, never by the generator grading itself.
This module reuses that control structure but plugs in OUTLIER_MCB's own machinery: the generative
operators propose, a QDArchive (MAP-Elites) is the database (diversity, not just the single best), and the
evaluator is PLUGGABLE — a code/test runner, a structural scorer, or a human-required gate that refuses to
auto-certify.

Loop (one budget unit = one evaluation):
  1. generate candidates (seed pool, then mutations of archived elites);
  2. score each with the EXTERNAL evaluator;
  3. insert into the QDArchive (keep the best of each behavioral cell);
  4. select diverse elites (round-robin over cells, NOT just the top score) as the next parents;
  5. mutate / recombine them and repeat until the budget is spent.

Deterministic (parent selection is round-robin, mutation is index-cycled), with full lineage for a
reproducible report. Collaborators: qd.QDArchive, invent._mutate, generators.generate_candidates,
scoring.score_idea (the default evaluator), repo_world (a code evaluator if you wire one).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from .generators import Candidate, generate_candidates
from .qd import QDArchive
from .invent import _mutate


@dataclass
class CreativeRecord:
    """One evaluated candidate with its lineage — the unit a reproducible report is built from."""
    name: str
    operator: str
    score: float
    round: int
    parents: List[str] = field(default_factory=list)
    operator_path: List[str] = field(default_factory=list)   # the chain of operators that produced it
    evidence: Dict = field(default_factory=dict)              # whatever the evaluator returned besides the score
    candidate: object = None


@dataclass
class CreativeSearchResult:
    problem: str
    archive: QDArchive
    records: List[CreativeRecord] = field(default_factory=list)
    rounds: int = 0
    note: str = ""
    ledger: object = None        # the in-loop ledger (if one was passed): what the run LEARNED about operators

    def best(self) -> Optional[CreativeRecord]:
        return max(self.records, key=lambda r: r.score) if self.records else None

    def lineage_diversity(self) -> float:
        """[0,1]: fraction of DISTINCT operator-paths among the records — low ⇒ everything is a child of the
        same pattern (a monoculture), high ⇒ the search explored structurally different lineages."""
        if not self.records:
            return 0.0
        paths = {"→".join(r.operator_path) or r.operator for r in self.records}
        return round(len(paths) / len(self.records), 3)

    def markdown(self) -> str:
        b = self.best()
        L = [f"## creative_search — «{self.problem}»",
             f"- evaluations: {len(self.records)} · rounds: {self.rounds} · QD coverage: {self.archive.coverage()} "
             f"cells · QD-score: {self.archive.qd_score()} · lineage diversity: {self.lineage_diversity()}"]
        if b:
            L.append(f"- best (external score {round(b.score, 3)}): [{b.operator}] {b.name}")
        L.append("\n" + self.archive.markdown())
        if self.note:
            L.append("\n" + self.note)
        return "\n".join(L)


def structural_evaluator(pack=None, repo=None) -> Callable[[Candidate], float]:
    """The default EXTERNAL evaluator: the grounded multi-factor composite (scoring.score_idea). It is
    external to the generator (a different module), but it is STRUCTURAL — swap in a code/test evaluator
    for real settlement, or a human-required gate that returns a flag instead of a number."""
    from .scoring import score_idea

    def _ev(c: Candidate) -> float:
        return score_idea(c, pack=pack, repo=repo)["composite"]
    return _ev


def code_evaluator(repo, runner: Optional[Callable[[str, str], str]] = None) -> Callable[[Candidate], float]:
    """An EXTERNAL evaluator that SETTLES BY THE REPO, not by self-judgment — the full FunSearch discipline.

    For each candidate it compiles the world-test against the real repo and scores by how REAL the bet is:
      • without a `runner`: the red-first MATERIALIZATION of the contract (is it a selectable, currently-red
        test that names a real target?) — grounding, measured against the filesystem, no execution;
      • with a `runner(command, cwd) -> "GREEN"|"RED"|...`: blends materialization with EXECUTION — a bet that
        actually goes GREEN scores highest. Pass `default_runner` (below) for the real verifier.verify_red_green
        runner, or inject a fake runner in tests to drive selection deterministically without spawning a subprocess.
        Without a runner NO execution happens (grounding only) — there is no implicit default.

    This is the evaluator to use when you want creative_search / thought_search to be settled by running the
    repo's own gates, never by the engine grading itself."""
    from .repo_world import compile_world_test
    from .materialize import materialization_score
    root = getattr(repo, "root", ".")

    def _contract(check):
        return {"target": check.target, "test_name": check.test_name, "command": check.command,
                "baseline_assertion": check.baseline_assertion, "grounded": check.grounded}

    def _ev(c: Candidate) -> float:
        axis = c.breaks[0] if c.breaks else ""
        check = compile_world_test(c.negation, axis, repo=repo)
        mat = materialization_score(_contract(check), root)
        if runner is None:
            return round(mat, 3)                       # grounding only — no execution requested
        try:
            status = runner(check.command, root)
        except Exception:
            status = "ERROR"
        executed = 1.0 if status == "GREEN" else 0.0
        return round(0.5 * mat + 0.5 * executed, 3)    # real settlement: materializable AND it passes
    return _ev


def default_runner(command: str, cwd: str) -> str:
    """The real runner: actually execute the check in the repo and return its GREEN/RED verdict. Pass this to
    `code_evaluator(repo, runner=default_runner)` to settle candidates by EXECUTION (not just materialization)."""
    from .repo_world import RepoCheck
    from .verifier import verify_red_green
    return verify_red_green(RepoCheck(kind="test_flip", command=command, pass_condition="", fail_baseline=""),
                            cwd=cwd).status


def _sample_parent(archive: QDArchive, ledger):
    """Pick the next parent. Without a ledger: the deterministic round-robin over cells (unchanged). With
    a ledger: bias toward the elite whose (axis×operator) the ledger currently rates highest — so a winning
    operator is exploited more WITHIN the run. Deterministic (ties broken by name); _mutate still cycles
    moves by index, so the same parent yields different children and diversity is not lost."""
    if ledger is None:
        return archive.sample()
    elites = archive.elites()
    if not elites:
        return None

    def weight(c: Candidate) -> float:
        axis = c.breaks[0] if c.breaks else ""
        return ledger.weight_of(axis, c.operator)
    return max(elites, key=lambda e: (weight(e[2]), e[2].name))[2]


def creative_search(problem: str, generator: Optional[Callable] = None, evaluator: Optional[Callable] = None,
                    archive: Optional[QDArchive] = None, budget: int = 40, seed: Optional[List[Candidate]] = None,
                    pack=None, repo=None, ledger=None) -> CreativeSearchResult:
    """Run the FunSearch-style loop on `problem`. `evaluator(candidate) -> float | {"score":…, **evidence}`
    is the EXTERNAL judge (defaults to the structural composite). `generator(pack, parent) -> [Candidate]`
    overrides how new candidates are produced (defaults to OUTLIER_MCB mutations). `budget` is the number
    of evaluations. Pass `ledger` (economy.Ledger) to LEARN in-loop: each evaluation posts+settles a bet so
    winning (axis×operator)s gain weight and losing ones lose it DURING the run, and parent selection is
    biased toward the operators that are paying off. The ledger NEVER alters the external evaluator's score
    (FunSearch discipline); it only steers exploration. Without a ledger nothing changes — fully
    backward-compatible. Returns a reproducible result with the QD archive, full lineage, and the ledger."""
    if pack is None:
        from .pack import select_pack
        pack, _ = select_pack(problem)
    archive = archive if archive is not None else QDArchive(pack=pack, repo=repo)
    evaluate = evaluator if evaluator is not None else structural_evaluator(pack, repo)

    def _score(c):
        out = evaluate(c)
        return (float(out["score"]), {k: v for k, v in out.items() if k != "score"}) if isinstance(out, dict) else (float(out), {})

    records: List[CreativeRecord] = []
    op_path_of: Dict[str, List[str]] = {}
    scores_seen: List[float] = []

    def _ingest(c: Candidate, rnd: int, parents: List[str], path: List[str]):
        s, evidence = _score(c)
        if ledger is not None:                       # learn in-loop: settle a bet vs the running mean
            from .economy import bet_from_candidate
            bet = ledger.post(bet_from_candidate(c))
            # HONESTY FIX (#14): settle only against a REAL prior baseline, with a strict '>'. The old code used
            # the mean of scores-so-far and, for the first candidate (no baseline), compared s>=s → an automatic
            # WIN that biased ledger-guided sampling toward whatever was evaluated first. With no baseline yet,
            # leave the bet OPEN — the Ledger is a persistent market where bets accrue evidence over time.
            if scores_seen:
                mean = sum(scores_seen) / len(scores_seen)
                ledger.settle(bet, won=(s > mean))
        scores_seen.append(s)
        archive.add(c, quality=s)
        op_path_of[c.name] = path
        records.append(CreativeRecord(name=c.name, operator=c.operator, score=round(s, 3), round=rnd,
                                      parents=parents, operator_path=path, evidence=evidence, candidate=c))

    # round 0: seed the database
    seeds = seed if seed is not None else (generate_candidates(pack, problem))
    for c in seeds[:max(1, budget)]:
        _ingest(c, 0, parents=[], path=[c.operator])
    spent = len(records)

    # rounds 1..: evolve from diverse elites
    rnd = 0
    while spent < budget:
        rnd += 1
        parent = _sample_parent(archive, ledger)        # round-robin, or ledger-biased if a ledger is given
        if parent is None:
            break
        if generator is not None:
            children = generator(pack, parent) or []
        else:
            child = _mutate(parent, pack, i=spent)      # OUTLIER_MCB structural mutation
            children = [child] if child is not None else []
        if not children:
            spent += 1                                  # avoid an infinite loop when a parent is sterile
            continue
        for ch in children:
            if spent >= budget:
                break
            path = op_path_of.get(parent.name, [parent.operator]) + [ch.operator]
            _ingest(ch, rnd, parents=[parent.name], path=path)
            spent += 1

    note = ("EXTERNAL-evaluator FunSearch loop: the generator proposes, the evaluator (not the generator) "
            "scores, the QD archive keeps the best of each KIND. Swap `evaluator` for a code/test runner to "
            "settle by execution; a human-required evaluator must NOT auto-certify.")
    return CreativeSearchResult(problem=problem, archive=archive, records=records, rounds=rnd, note=note,
                                ledger=ledger)
