"""invent — the cognitive RUNTIME. It borrows the control structures of the known reasoning frameworks
(ToT search, Self-Refine loop, Reflexion memory, AutoGen roles, DSPy pipeline) but INVERTS each one's
objective, because — as the engine flagged when applied to those frameworks — every one of them rewards
the LIKELY / CORRECT answer, i.e. they optimize toward the loss function we are trying to escape.

The single inversion that does it: the metric is not accuracy, it is

    box_distance(candidate)  ×  survives_falsification(candidate)

so the runtime is pulled OUTWARD (away from the known families, toward what needs new information) while
falsification keeps it honest. Mapping of what is borrowed → how it is inverted:

  ToT search        → novelty_search: beam search whose value is DISTANCE-FROM-BOX, not plausibility;
                      it prunes branches that collapse INTO the box (the opposite of ToT's pruning).
  Self-Refine loop  → push_further: each pass must move an idea FARTHER from the box (a rarer operator,
                      one more broken axis); a pass that makes it 'safer' is rejected.
  Reflexion memory  → reflect: a LOST bet becomes a NEW assumption to break (failure = next frontier),
                      not a performance patch. Persisted in the Ledger (economy.py).
  AutoGen roles     → explorer / critic / synthesizer / resolver, ADVERSARIAL toward the box; truth is
                      settled by the EXTERNAL resolver (the repo), never by consensus among the agents.
  DSPy pipeline     → invent(): a declarative pipeline optimized for disciplined novelty, not accuracy.
"""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .generators import (generate_candidates, dissolve, scale_break,
                         invert_assumption, transport_break, breakable, Candidate)
from .economy import Ledger, forge_bet, Bet


# how far each move sits from the average answer (the loss function). Rare/cross-domain/deletion moves,
# more broken axes, and a need for NEW information (data the model does not already have) score higher.
_OP_DISTANCE = {"negate": 1, "recombine": 2, "invert": 2, "scale": 2, "abduce": 2,
                "unify": 2, "instrument": 2, "transport": 3, "dissolve": 3}


def box_distance(candidate: Candidate, pack=None, grounded: bool = True) -> float:
    """The anti-loss-function metric: how UNLIKE the box a candidate is. Higher = farther from the
    most-probable answer. Rewards breaking more axes, rarer operators, and REQUIRING NEW INFORMATION.

    Grounding gate (answering the 'rewards strangeness, not quality' critique): an ungrounded idea — one
    that cannot be tied to a runnable check — has its distance HALVED, so a grounded near idea can beat
    an ungrounded far one. Distance alone is not quality; grounded distance is."""
    d = len(set(candidate.breaks)) + _OP_DISTANCE.get(candidate.operator, 1) + len(candidate.needs)
    return float(d) if grounded else round(d * 0.5, 1)


def _foreign_pack(pack):
    from .pack import list_packs, get_pack
    for name in list_packs():
        if name != pack.name and name != "generic":
            return get_pack(name)
    return None


def push_further(candidate: Candidate, pack) -> Candidate:
    """Self-Refine, inverted: return a STRICTLY farther-from-box successor, or the candidate unchanged.
    Refinement that regresses toward the acceptable is rejected by construction."""
    name = candidate.assumptions[0] if candidate.assumptions else None
    if not name or name not in pack.by_name():
        return candidate
    base = box_distance(candidate, pack)
    successors = [c for c in (dissolve(pack, name), scale_break(pack, name)) if c]
    fp = _foreign_pack(pack)
    if fp is not None:
        t = transport_break(fp, pack)
        if t:
            successors.append(t)
    farther = [c for c in successors if box_distance(c, pack) > base]
    return max(farther, key=lambda c: box_distance(c, pack)) if farther else candidate


def novelty_search(pack, prompt: str = "", beam: int = 5, rounds: int = 2) -> List[Dict]:
    """ToT, inverted: a beam search that keeps the candidates FARTHEST from the box and prunes the ones
    that collapse into it. Each round pushes the survivors further. Returns [{distance, candidate}]."""
    pool: List[Candidate] = list(generate_candidates(pack, prompt))
    for a in breakable(pack):                        # add the deletion frontier
        d = dissolve(pack, a.name)
        if d:
            pool.append(d)
    # dedup by name, score, keep the farthest beam (NOT the most plausible)
    seen, uniq = set(), []
    for c in pool:
        if c.name not in seen:
            seen.add(c.name); uniq.append(c)
    beamset = sorted(uniq, key=lambda c: -box_distance(c, pack))[:beam]
    for _ in range(max(0, rounds - 1)):
        pushed = [push_further(c, pack) for c in beamset]
        merged, seen = [], set()
        for c in beamset + pushed:
            if c.name not in seen:
                seen.add(c.name); merged.append(c)
        beamset = sorted(merged, key=lambda c: -box_distance(c, pack))[:beam]
    return [{"distance": box_distance(c, pack), "candidate": c} for c in
            sorted(beamset, key=lambda c: -box_distance(c, pack))]


def _mutate(parent: Candidate, pack, i: int = 0) -> Optional[Candidate]:
    """Produce a structural MUTATION of a parent idea (the QD variation operator): apply one generator move
    to one of the parent's assumptions, cycling moves deterministically so illumination is reproducible."""
    names = parent.assumptions or [a.name for a in breakable(pack)]
    if not names:
        return None
    name = names[i % len(names)]
    moves = (lambda n: invert_assumption(pack, n),
             lambda n: dissolve(pack, n),
             lambda n: scale_break(pack, n, factor=1000))
    for j in range(len(moves)):
        child = moves[(i + j) % len(moves)](name)
        if child is not None:
            return child
    return None


def illuminate(pack, prompt: str = "", iterations: int = 30, seed_pool: Optional[List[Candidate]] = None,
               repo=None, quality_fn=None):
    """MAP-Elites illumination (Mouret & Clune 2015): seed an archive, then repeatedly sample a parent
    elite, mutate it, and try to place the child — keeping the best idea of each behavioral KIND. Returns a
    qd.QDArchive: a MAP of diverse, each-best-of-kind ideas, not a single optimum. Deterministic."""
    from .qd import QDArchive
    arc = QDArchive(pack=pack, repo=repo, quality_fn=quality_fn)
    seeds = seed_pool if seed_pool is not None else generate_candidates(pack, prompt)
    for c in seeds:
        arc.add(c)
    for i in range(max(0, iterations)):
        parent = arc.sample()
        if parent is None:
            break
        child = _mutate(parent, pack, i)
        if child is not None:
            arc.add(child)
    return arc


def reflect(lost_bet: Bet, pack):
    """Reflexion, oriented to discovery: turn a LOST bet into a NEW assumption to break — failure is the
    next frontier, not a performance patch. Returns a (provisional Assumption, meta) pair."""
    from .generators import anomaly_to_assumption
    anomaly = f"the bet «{lost_bet.claim[:80]}» lost on {lost_bet.resolver}, yet the box did not fully explain why"
    return anomaly_to_assumption(pack, anomaly, axis=lost_bet.axis)


@dataclass
class Invention:
    prompt: str
    box: str
    frontier: List[Dict] = field(default_factory=list)   # [{score, candidate, bet, check, maturity, …}]
    ledger: Optional[Ledger] = None
    note: str = ""
    pack: object = None
    repo: object = None
    archive: object = None        # a qd.QDArchive: the MAP-Elites illumination of the idea space (diverse elites)
    def best(self):
        return self.frontier[0] if self.frontier else None

    def qd_map(self):
        """The Quality-Diversity map (qd.QDArchive): an atlas of the best idea of EACH structural kind, not
        just the single top idea. Use .archive.markdown() for a readable map, .empty_regions() for the gaps."""
        return self.archive

    def dossier(self, i: int = 0):
        """The full orchestrated analysis of the i-th idea (theorem · world · reviewer · lineage · cascade
        · compression · maturity) — the whole engine on one idea."""
        from .dossier import dossier
        return dossier(self.frontier[i]["candidate"], self.pack, repo=self.repo)

    def reflexion(self):
        """Close the loop: for every bet that LOST, mine a new assumption to break next round (Reflexion).
        Returns the list of (provisional Assumption, meta) — feed them back to widen the next search."""
        out = []
        for f in self.frontier:
            if f["bet"].status == "LOST":
                out.append(reflect(f["bet"], self.pack))
        return out
    def markdown(self) -> str:
        L = [f"## Invention runtime — «{self.prompt}»",
             f"- **box being escaped:** {self.box}",
             "- **objective:** grounded multi-factor score (novelty gated by verifiability + implementability)",
             "",
             "### Frontier (best composite first; each is a concrete, settle-able proposal)"]
        for i, f in enumerate(self.frontier, 1):
            c, s = f["candidate"], f["score"]
            flags = ("grounded" if f["grounded"] else "UNGROUNDED") + (", rebranding-risk" if f["rebranding_risk"] else "")
            status = (f" · {f['verdict'].status}" if f.get("verdict") else "")   # GREEN | RED | NOT_MATERIALIZED
            rnd = f" · round {f['round']}" if f.get("round") else ""
            mat = f" · {f['maturity'].status}" if f.get("maturity") else ""
            L.append(f"{i}. **[{c.operator}] {c.name}**  (score {s['composite']}{mat}{rnd}, {flags}{status})")
            L.append(f"   - novelty {s['novelty']} · useful {s['usefulness']} · implementable {s['implementability']} "
                     f"· verifiable {s['verifiability']} · risk {s['risk']} · cost {s['cost']}")
            L.append(f"   - claim: {c.negation[:140]}")
            L.append(f"   - proposal: {f['proposal']}")
            if f.get("verdict"):
                L.append(f"   - verdict ({f['verdict'].status}): {f['verdict'].why}")
        if self.note:
            L.append("\n" + self.note)
        return "\n".join(L)


def _diversify(frontier: List[Dict]) -> List[Dict]:
    """Reorder (never drop) so the HEAD of the frontier shows DISTINCT broken-assumption sets instead of many
    near-duplicate recombinations of the single farthest assumption (audit #10). Greedy MMR: keep the best
    item first, then repeatedly take the highest-composite item whose assumptions are LEAST represented among
    those already chosen. Same set in, same set out — only the order changes, so best()/frontier stay valid."""
    remaining = list(frontier)
    chosen: List[Dict] = []
    seen: Counter = Counter()
    _q = lambda f: f["score"].get("taste_blended", f["score"]["composite"])   # taste flows through if present
    while remaining:
        nxt = min(remaining, key=lambda f: (sum(seen[a] for a in f["candidate"].assumptions), -_q(f)))
        remaining.remove(nxt)
        chosen.append(nxt)
        for a in nxt["candidate"].assumptions:
            seen[a] += 1
    return chosen


def _proposal(candidate, check, repo) -> str:
    """A concrete, actionable proposal for one candidate: which component to touch, the minimal change,
    and the command that would settle it — not an abstraction."""
    where = check.target or (repo.components[0] if (repo and repo.components) else "the relevant component")
    assumption = candidate.assumptions[0] if candidate.assumptions else "the box's default"
    return (f"minimal change in `{where}`: make '{assumption}' false as stated; "
            f"add a focused test, then run `{check.command}` — the repo settles it.")


def _extend_pack(pack, mined):
    """Return a COPY of `pack` extended with mined (Assumption, axis) pairs — never mutate the registry."""
    import copy
    p = copy.copy(pack)
    p.assumptions = list(pack.assumptions) + [a for a, _ in mined]
    p.dimension_of = dict(pack.dimension_of)
    for a, axis in mined:
        if axis:
            p.dimension_of[a.name] = axis
    return p


def _evaluate(cands, pack, repo, ledger, verify_fn, repo_signals, timeout, round_idx=0):
    """Turn candidates into scored, bet-backed, (optionally) verified frontier items."""
    from .scoring import score_idea
    from .maturity import assess as _assess
    from .verifier import verifiability_class
    items = []
    for c in cands:
        if not c.breaks and c.operator not in ("unify", "instrument", "reframe"):   # CRITIC: in-box → drop
            continue
        if c.operator != "orthogonal_germ":
            c = push_further(c, pack)                                                # SYNTH: go further
        bet, check = forge_bet(c, ledger=ledger, repo=repo, repo_signals=repo_signals, stake=0.5)
        new_output = c.operator in ("unify", "instrument", "reframe")
        rebranding_risk = not check.grounded and not c.needs and not new_output
        score = score_idea(c, pack=pack, repo=repo, grounded=check.grounded)
        score["composite"] = round(score["composite"] * ledger.weight_of(bet.axis, bet.operator), 3)
        bet.stake = round(min(0.95, 0.4 + 0.5 * score["composite"]), 2)
        maturity = _assess(breaks=c.breaks, has_executable_world_test=check.grounded,
                           coherence=score["composite"], new_output=new_output,
                           reduces_to=(None if c.breaks else "the box"))
        item = {"score": score, "candidate": c, "bet": bet, "check": check, "maturity": maturity,
                "grounded": check.grounded, "rebranding_risk": rebranding_risk, "round": round_idx,
                "verifiability": verifiability_class(check), "proposal": _proposal(c, check, repo)}
        if verify_fn is not None:                                                     # VERIFY: red-green, honestly
            rg = verify_fn(check, cwd=repo.root, timeout=timeout)
            ledger.settle(bet, won=(rg.status == "GREEN"))   # WON only if the SPECIFIC new test exists and is green
            item["verdict"] = rg
        items.append(item)
    return items


def invent(prompt: str, pack=None, beam: int = 5, rounds: int = 2, repo_path: Optional[str] = None,
           repo_signals: Optional[Dict] = None, ledger: Optional[Ledger] = None,
           ledger_path: Optional[str] = None, execute: bool = False, reflect_rounds: int = 0,
           timeout: int = 120, anomalies: Optional[List[str]] = None, anomaly_axis: str = "",
           blend_with: Optional[List[str]] = None, blend_threshold: float = 0.4,
           induce_pack: bool = False, discovery_memory=None, discovery_path: Optional[str] = None,
           taste=None, expand_when_stuck: bool = False, use_orthogonal_germs="auto") -> Invention:
    """THE runtime. Pipeline: EXPLORE → CRITIC → SYNTH → SCORE → RESOLVE → (execute) VERIFY.

    `repo_path` grounds it in a real project; `execute=True` runs the checks and settles the ledger.
    `reflect_rounds>0` (with execute) closes the LEARNING loop: every LOST bet is mined into a new
    assumption (Reflexion), a COPY of the pack is extended with it, and the engine regenerates around the
    failure — looping until no new loss appears (bounded).
    `anomalies` (noise-becomes-signal, offline): each observed residual the box discards as noise is mined
    into a PROVISIONAL assumption (`anomaly_to_assumption`) on `anomaly_axis` (default: the pack's
    highest-priority axis), the pack copy is extended with it, and the engine generates candidates that
    break it — so an anomaly becomes a first-class source of candidates without needing a settled loss.
    `blend_with` (emergent cross-domain blending): for each named registered pack, fuse the routed pack with
    it (`conceptual_blend`) and admit the blend only if its emergence (distance between the two parent breaks)
    is ≥ `blend_threshold` — so a distant-domain fusion enters the pool but a self-blend / near-domain blend
    that would collapse to a transport is gated out.
    `induce_pack=True` (autonomous conceptual space): when NO registered pack maps the prompt, INDUCE a
    provisional pack from the problem's own words (`infer_domain_pack`) instead of falling back to `generic` —
    so the engine can be creative in a domain nobody hand-wrote a pack for.
    `discovery_memory` / `discovery_path` (cross-session composition): accumulated dead ends (assumptions
    refuted in past sessions) are loaded into the working pack's failure_memory so the kernel deprioritizes
    worn breaks, and every SETTLED outcome of this run is recorded back (and persisted) — so a failure in one
    session steers the next. Returns a settle-able portfolio."""
    from .generators import generate_candidates
    if pack is None:
        from .pack import select_pack
        pack, _route_score = select_pack(prompt)
        if induce_pack and _route_score == 0:        # #6: no pack maps → INDUCE a provisional one, don't fall to generic
            from .pack_induction import infer_domain_pack
            pack = infer_domain_pack(prompt)
    if anomalies:                      # #3: what the old paradigm calls noise, the new treats as signal
        from .generators import anomaly_to_assumption
        axis = anomaly_axis if anomaly_axis in pack.axes else (
            max(pack.axes, key=lambda k: pack.axes[k].get("priority", 1)) if pack.axes else "")
        mined0 = [(anomaly_to_assumption(pack, a, axis=axis)[0], axis) for a in anomalies if a and a.strip()]
        if mined0:
            pack = _extend_pack(pack, mined0)
    # persistence: a ledger_path auto-loads prior bets/policy and is saved at the end.
    if ledger is None:
        ledger = Ledger.load(ledger_path) if ledger_path else Ledger()
    repo = None
    if repo_path is not None:
        from .grounding import probe
        repo = probe(repo_path)
    verify_fn = None
    if execute and repo is not None and repo.grounded:
        from .verifier import verify_red_green as verify_fn   # honest settlement: a NEW test, not the whole suite

    # #7: cross-session composing memory — accumulated dead ends bias THIS run's ranking (failure → next move)
    if discovery_path is not None and discovery_memory is None:
        from .discovery_memory import DiscoveryMemory
        discovery_memory = DiscoveryMemory.load(discovery_path)
    if discovery_memory is not None:
        fm = discovery_memory.as_failure_memory(pack.name)
        if fm:
            import copy
            pack = copy.copy(pack)
            pack.failure_memory = {**(pack.failure_memory or {}), **fm}

    cands = [it["candidate"] for it in novelty_search(pack, prompt, beam=beam, rounds=rounds)]
    orthogonal_germ_added = False
    from .orthogonal_germs import propose_orthogonal_germ, orthogonal_germ_relevant
    # "auto" delegates the decision to the library itself (is this request about representation?);
    # True/False force it on/off. Conditional so it fires when a new-basis move is on-topic, not always.
    want_germ = (orthogonal_germ_relevant(pack, prompt) if use_orthogonal_germs == "auto"
                 else bool(use_orthogonal_germs))
    if want_germ:
        cands.append(propose_orthogonal_germ(pack, prompt))
        orthogonal_germ_added = True
    if blend_with:                     # #4: emergent cross-domain blending, gated so it can't collapse to a transport
        from .generators import conceptual_blend
        from .pack import get_pack
        for tname in blend_with:
            try:
                target = get_pack(tname)
            except Exception:
                continue
            if target.name == pack.name:                                 # a blend of a domain with itself is sterile
                continue
            bc = conceptual_blend(pack, target)
            if bc is not None and bc.emergence >= blend_threshold:        # emergence gate: distant parents only
                cands.append(bc)
    frontier = _evaluate(cands, pack, repo, ledger, verify_fn, repo_signals, timeout, round_idx=0)

    # TRANSFORMATIONAL CREATIVITY (opt-in): when the fixed pack is a saturated space, GROW it — promote a
    # cross-domain anomaly to a genuinely new breakable AXIS (propose_transformation gates out a rebrand) and
    # generate candidates that break THAT axis, so ideas impossible in the original space become reachable.
    # This is the move past 'search a fixed conceptual space'; additive, so default-off preserves behavior.
    transformed_axis = None
    if expand_when_stuck:
        from .transformation import propose_transformation
        tr = propose_transformation(pack)
        if tr.status == "TRANSFORMATIONAL" and tr.expanded_pack is not None:
            transformed_axis = tr.new_axis
            grown = [c for c in generate_candidates(tr.expanded_pack) if tr.assumption_name in c.assumptions]
            frontier += _evaluate(grown, tr.expanded_pack, repo, ledger, verify_fn, repo_signals, timeout, round_idx=0)

    # REFLEXION LOOP — lose → mine → extend a pack copy → regenerate. Needs REAL settled losses (execute).
    working_pack, mined_total = pack, 0
    if reflect_rounds and verify_fn is not None:
        for r in range(1, reflect_rounds + 1):
            lost = [f for f in frontier if f["bet"].status == "LOST" and not f.get("_reflected")]
            if not lost:
                break                                                    # loop-until-dry
            mined = []
            for f in lost[:3]:                                           # bounded mined-per-round
                f["_reflected"] = True
                asm, meta = reflect(f["bet"], working_pack)
                mined.append((asm, meta.get("axis")))
            working_pack = _extend_pack(working_pack, mined)
            names = {a.name for a, _ in mined}
            learned = [c for c in generate_candidates(working_pack) if set(c.assumptions) & names]
            frontier += _evaluate(learned, working_pack, repo, ledger, verify_fn, repo_signals, timeout, round_idx=r)
            mined_total += len(mined)

    # PORTFOLIO: keep DISTINCT bets only, ranked.
    seen, deduped = set(), []
    for f in frontier:
        c = f["candidate"]
        key = (c.name, c.operator, tuple(c.breaks), tuple(c.assumptions), c.negation)
        if key not in seen:
            seen.add(key); deduped.append(f)
    frontier = sorted(deduped, key=lambda f: (-f["score"]["composite"], f["rebranding_risk"]))
    # T2.1 EARNED TASTE (opt-in): re-rank by a value LEARNED from settled outcomes (which past bets survived
    # falsification), not just box-distance — the calibrated 'nose' the engine otherwise lacks. `taste=True`
    # learns from THIS ledger's settled bets; an EarnedTaste (e.g. loaded from a prior session) carries the
    # cross-session track record. A cold/uninformative taste is a no-op (neutral 0.5) — safe by construction.
    tmodel = None
    if taste is not None and taste is not False:
        from .taste import EarnedTaste, earned_taste_from_ledger, taste_rerank
        tmodel = taste if isinstance(taste, EarnedTaste) else earned_taste_from_ledger(ledger)
        if tmodel.is_informative():
            frontier = taste_rerank(frontier, tmodel)
    # #10: a diversity-aware reorder so the head isn't 6 recombinations of the same farthest assumption.
    frontier = _diversify(frontier)

    # QUALITY-DIVERSITY: illuminate the idea space into a MAP of diverse elites (not just the ranked list),
    # seeded by the evaluated frontier so every cell keeps the best idea of its KIND. Backward-compatible:
    # the frontier/best() API is unchanged; the map is an ADDITIONAL, richer view (inv.archive / inv.qd_map()).
    archive = illuminate(pack, prompt, iterations=max(2 * beam, 10),
                         seed_pool=[f["candidate"] for f in frontier] or None, repo=repo)

    from .cascade import biggest_lever
    lever = biggest_lever(pack)
    auto = sum(1 for f in frontier if f["verifiability"] == "AUTO")
    note = (("Grounded in " + repo.root + f" (test: {repo.test_command})." if repo and repo.grounded
             else "NOT grounded — pass repo_path=<project> so the repo, not the engine, settles each bet.")
            + f" HONEST verifiability: {auto}/{len(frontier)} ideas are AUTO; the rest are HUMAN-only — NOT claimed verified."
            + (" Checks were EXECUTED and bets settled." if verify_fn is not None else
               " Pass execute=True to RUN the AUTO checks and settle the ledger.")
            + (f" Reflexion: {mined_total} failure(s) mined into new assumptions and regenerated." if mined_total else "")
            + (f" Transformational: grew a NEW axis '{transformed_axis}' and explored the expanded space." if transformed_axis else "")
            + (" Orthogonal germ: injected a new-basis candidate; accept it only with an external reducibility test and collapsing control."
               if orthogonal_germ_added else "")
            + (f" Biggest lever: breaking '{lever.seed}' cascades to reach {lever.reach}." if lever.reach else "")
            + " Use .dossier(i) for the full analysis of an idea, and .reflexion() to mine lost bets.")
    if ledger_path:
        ledger.save(ledger_path)
    # #7: record each SETTLED outcome so a future session composes on it (only real, settled bets — honest)
    if discovery_memory is not None:
        for f in frontier:
            bet = f["bet"]
            if bet.status in ("WON", "LOST"):
                for asm in f["candidate"].assumptions:
                    discovery_memory.record(asm, bet.axis, pack.name, confirmed=(bet.status == "WON"))
        if discovery_path is not None:
            discovery_memory.save(discovery_path)
    return Invention(prompt=prompt, box=pack.box_name, frontier=frontier, ledger=ledger, note=note,
                     pack=pack, repo=repo, archive=archive)


# exported under a clear name to avoid clashing with the module-level reflect()
invent_reflect = reflect
