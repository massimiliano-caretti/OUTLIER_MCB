"""orchestrator — the autonomous inventor loop: thread every creative mechanism + every memory into one.

Until now the cognitive mechanisms were reachable building blocks (health() flagged them "not orchestrated").
This wires them into a single recursive loop that behaves like an inventor working over time:

  1. PROBLEM-FINDING  — find_problems(pack, memory) proposes what is worth attacking (cross-domain blends
     included), priors shifted by the cumulative DiscoveryMemory.
  2. EPISODIC RECALL  — for each problem, EpisodicMemory says "this reminds me of…"; a near-identical
     REFUTED problem is SKIPPED (do not reinvent a dead end).
  3. GENERATE         — a blend problem materializes a conceptual blend; a single-axis problem an inversion.
  4. SETTLE           — an EXTERNAL evaluator scores it (structural by default; pass code/symbolic/causal
     for real settlement). Outcome is PROVISIONAL unless a real evaluator was supplied.
  5. TRANSFORM if stuck — if nothing clears the bar, transformational creativity invents a NEW axis and
     EXPANDS the pack, so the next round searches a space that did not exist before.
  6. COMPOUND         — every outcome is written back to DiscoveryMemory (assumption fertility),
     EpisodicMemory (the episode) and AnalogicalMemory (which domain pairing transferred).

Honest: with the default structural evaluator outcomes are PROVISIONAL (structure ≠ a real world-test);
supply a settling evaluator for `CONFIRMED`/`REFUTED` to mean what they say. No regression: this is a NEW
entrypoint; it touches no existing function.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, List, Optional


@dataclass
class InventionStep:
    problem: str
    domain: str
    seed: str
    score: float
    outcome: str                 # CONFIRMED | REFUTED | SKIPPED | OPEN
    note: str = ""
    surprise: float = 0.0        # how much the outcome violated the prior expectation [0,1]
    reward: float = 0.0          # the joy-of-discovery signal: surprise × confirmation
    round: int = 0               # which round produced this step (for rounds-to-discover measurements)


@dataclass
class InventionRun:
    pack_name: str
    steps: List[InventionStep] = field(default_factory=list)
    expanded_pack: object = None
    discovery_memory: object = None
    episodic: object = None
    analogical: object = None
    provisional: bool = True
    note: str = ""

    _DEAD = ("SKIPPED", "EVALUATOR_FAILED")

    def best(self) -> Optional[InventionStep]:
        live = [s for s in self.steps if s.outcome not in self._DEAD]
        return max(live, key=lambda s: s.score) if live else None

    @property
    def total_satisfaction(self) -> float:
        """The run's accumulated 'joy of discovery' — total reward from SURPRISING-and-CONFIRMED steps. A run
        that only re-confirmed the obvious scores near 0; one that found surprising truths scores high."""
        return round(sum(s.reward for s in self.steps), 3)

    @property
    def evaluator_failures(self) -> int:
        return sum(s.outcome == "EVALUATOR_FAILED" for s in self.steps)

    def most_delightful(self) -> Optional[InventionStep]:
        live = [s for s in self.steps if s.outcome not in self._DEAD]
        return max(live, key=lambda s: s.reward) if live else None

    def markdown(self) -> str:
        L = [f"## Autonomous inventor — «{self.pack_name}»  (satisfaction {self.total_satisfaction})"
             + (" (PROVISIONAL: structural evaluator, not a real world-test)" if self.provisional else "")]
        d = self.most_delightful()
        if d is not None and d.reward > 0:
            L.append(f"- ✨ most surprising-and-confirmed: {d.domain}:{d.seed} (surprise {d.surprise}, reward {d.reward})")
        for s in self.steps:
            L.append(f"- [{s.outcome}] score {s.score} · {s.domain}:{s.seed} — {s.problem[:80]}"
                     + (f"  ⟶ {s.note}" if s.note else ""))
        if self.expanded_pack is not None:
            new_axes = sorted(set(self.expanded_pack.axes))
            L.append(f"- ⊕ TRANSFORMED: expanded the space → axes {new_axes}")
        for mem in (self.discovery_memory, self.episodic, self.analogical):
            if mem is not None and hasattr(mem, "markdown"):
                L.append(mem.markdown())
        if self.note:
            L.append(self.note)
        return "\n".join(L)


def _score_of(evaluator, cand, provisional: bool):
    """(score, failed). A REAL evaluator that raises is a FAILURE, not a discovery — it returns failed=True
    so the caller marks EVALUATOR_FAILED. Only the default structural evaluator falls back to box_distance
    (it is already a proxy, and tagged blend candidates can legitimately miss its scoring path)."""
    try:
        out = evaluator(cand)
        return (float(out["score"]) if isinstance(out, dict) else float(out)), False
    except Exception:
        if provisional:
            from .invent import box_distance
            return round(min(1.0, box_distance(cand) / 8.0), 3), False
        return 0.0, True


def autonomous_inventor(pack=None, prompt: str = "", rounds: int = 1, evaluator: Optional[Callable] = None,
                        discovery_memory=None, episodic=None, analogical=None, blend_with: Optional[List] = None,
                        accept: float = 0.6, top_problems: int = 4, embedder=None,
                        curiosity: float = 0.3, consult_memory: bool = True) -> InventionRun:
    """Run the inventor loop, wiring problem-finding + episodic recall + blending + transformation + the three
    memories. Returns an InventionRun with the updated memories and (if it got stuck) an expanded pack."""
    from .pack import select_pack, get_pack
    from .creative_search import structural_evaluator
    from .problem_finding import find_problems
    from .generators import conceptual_blend, invert_assumption
    from .discovery_memory import DiscoveryMemory
    from .memory import EpisodicMemory, AnalogicalMemory, Episode
    from .transformation import transform_space
    from .affect import bayesian_surprise, discovery_reward

    if pack is None:
        pack, _ = select_pack(prompt)
    discovery_memory = discovery_memory if discovery_memory is not None else DiscoveryMemory()
    episodic = episodic if episodic is not None else EpisodicMemory()
    analogical = analogical if analogical is not None else AnalogicalMemory()
    evaluate = evaluator if evaluator is not None else structural_evaluator(pack)
    provisional = evaluator is None

    steps: List[InventionStep] = []
    expanded_pack = None

    for r in range(max(1, rounds)):
        round_cleared = False        # per-ROUND stuck detection: if THIS round clears nothing we expand the
                                     # space for the next one — a barren round after an early success still pivots
        # READ BACK the analogical memory (no longer write-only): once some pairings have transfer history,
        # prioritize the blend targets that transferred well before — past analogy success steers the next round.
        if consult_memory and blend_with and analogical.fertile():
            blend_with = sorted(blend_with, key=lambda t: -analogical.prior(pack.name, getattr(t, "name", str(t))))
        port = find_problems(pack=pack, prompt=prompt, k=top_problems, blend_with=blend_with,
                             memory=(discovery_memory if consult_memory else None),
                             curiosity=(curiosity if consult_memory else 0.0))
        for prob in port.problems:
            # 2. episodic recall — do not reinvent the EXACT dead end already refuted (identity, not text
            # similarity, so distinct-but-similarly-worded assumptions are still explored; the memoryless
            # baseline skips this guard entirely).
            if consult_memory and episodic.refuted_seed(prob.seed, pack.name):
                steps.append(InventionStep(prob.question, prob.domain, prob.seed, 0.0, "SKIPPED",
                                           note="near-identical problem already REFUTED (episodic recall)", round=r + 1))
                continue
            # 3. generate a candidate for the problem
            is_blend = prob.domain.startswith("blend:")
            if is_blend:
                target = prob.domain.split("⊕", 1)[1]
                cand = conceptual_blend(pack, get_pack(target), embedder=embedder)
            else:
                cand = invert_assumption(pack, prob.seed)
            if cand is None:
                continue
            # 4. settle (external evaluator; structural ⇒ provisional)
            score, failed = _score_of(evaluate, cand, provisional)
            if failed:                                   # a real evaluator error is NOT a discovery
                steps.append(InventionStep(prob.question, prob.domain, prob.seed, 0.0, "EVALUATOR_FAILED",
                                           note="the external evaluator raised — not scored, not a discovery", round=r + 1))
                continue
            outcome = "CONFIRMED" if score >= accept else "REFUTED"
            round_cleared = round_cleared or (outcome == "CONFIRMED")
            lesson = episodic.lessons(prob.question, embedder=embedder)
            # joy of discovery: how SURPRISING (vs the prior we held) and CONFIRMED was this result?
            seed_name = prob.seed.split("⊕")[0]
            seed_axis = prob.axis.split("·")[0]
            expected = discovery_memory.prior(seed_name, pack.name)
            surprise = bayesian_surprise(expected, 1.0 if outcome == "CONFIRMED" else 0.0)
            reward = discovery_reward(surprise, outcome == "CONFIRMED")
            steps.append(InventionStep(prob.question, prob.domain, prob.seed, round(score, 3), outcome,
                                       note=lesson, surprise=surprise, reward=reward, round=r + 1))
            # 6. compound — write back to every memory
            discovery_memory.record(seed_name, seed_axis, pack.name, confirmed=(outcome == "CONFIRMED"))
            episodic.record(Episode(problem=prob.question, assumption=prob.seed, axis=prob.axis,
                                    domain=pack.name, outcome=outcome, score=round(score, 3)))
            if is_blend:
                target = prob.domain.split("⊕", 1)[1]
                analogical.record(pack.name, target, transferred=(outcome == "CONFIRMED"),
                                  mapping=prob.seed, emergence=prob.components.get("emergence", 0.0))

        # 5. transform if stuck — invent a new axis, expand the space for the next round
        if not round_cleared and expanded_pack is None:
            best_blend = next((s for s in steps if s.domain.startswith("blend:")), None)
            anomaly = (best_blend.problem if best_blend else
                       "a residual the box discards as noise is itself structured signal")
            tr = transform_space(pack, anomaly=anomaly, new_axis="EMERGENT_REGIME", embedder=embedder)
            if tr.status == "TRANSFORMATIONAL":
                expanded_pack = tr.expanded_pack
                discovery_memory.promote(tr.assumption_name, tr.new_axis, pack.name, note="invented when stuck")
                pack = expanded_pack                         # next round searches the expanded space

    note = ("Settled by an EXTERNAL evaluator." if not provisional else
            "PROVISIONAL outcomes (structural evaluator) — pass evaluator=code/symbolic/causal for real settlement.")
    return InventionRun(pack_name=pack.name, steps=steps, expanded_pack=expanded_pack,
                        discovery_memory=discovery_memory, episodic=episodic, analogical=analogical,
                        provisional=provisional, note=note)
