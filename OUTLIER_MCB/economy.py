"""economy — the novelty market. The unit of output is a priced BET, not a scored idea.

Surfaced by applying the engine to the external audit's own box. The audit asked for "real pruning",
"a multi-objective filter", and "richer failure memory". Those are the average answer (internal
scoring). The non-average move the engine recommended instead:

  ideas_are_the_unit   → an idea is free; a BET (a claim + the test that settles it + what you'd stake)
                         is what carries information. We output bets, not scored ideas.
  failure_is_a_blacklist → failure is PRICED by (axis × operator), not denylisted. An axis exhausted by
                         NEGATION stays cheap for an untried operator (unify/instrument/dissolve) — the
                         engine never goes blind where it once failed.
  exploration_is_one_shot → the Ledger is a PERSISTENT portfolio: bets stay open and accrue evidence
                         across the session; their expected value ranks what to pursue next.

This is not internal scoring: a bet is settled by an EXTERNAL resolver (see repo_world.py). The market
only PRICES the move; the world still decides who was right.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class Bet:
    claim: str
    world_test: str                 # what would settle it
    resolver: str                   # WHO settles it: 'repo:tests' | 'repo:types' | 'outcome' | 'human'
    axis: str = ""
    operator: str = "negate"        # which generative operator produced it
    family: str = ""                # the known family it risks reducing to
    stake: float = 0.5              # how much you'd commit, in [0,1] — confidence AS commitment
    price: float = 1.0              # set by the Ledger when posted (cost of this axis×operator)
    grounded: bool = False          # True ⇒ settled by a real, runnable repo check (not a placeholder)
    status: str = "OPEN"            # OPEN | WON | LOST
    @property
    def expected_value(self) -> float:
        """Cheap-to-proposes you'd stake on rank highest. EV = stake / price."""
        return round(self.stake / self.price, 3) if self.price else float("inf")
    def markdown(self) -> str:
        return (f"- **bet** ({self.status}, EV {self.expected_value}) on «{self.claim}»\n"
                f"    - settled by {self.resolver}: {self.world_test}\n"
                f"    - axis×operator: {self.axis}×{self.operator}  · stake {self.stake} · price {self.price}")


@dataclass
class Ledger:
    """A persistent portfolio of bets + an (axis×operator)-indexed price book."""
    bets: List[Bet] = field(default_factory=list)
    _losses: Dict[Tuple[str, str], int] = field(default_factory=dict)
    _wins: Dict[Tuple[str, str], int] = field(default_factory=dict)

    def price(self, axis: str, operator: str) -> float:
        """Cost to propose on (axis×operator). Rises with losses, falls with wins. An operator NEVER
        tried on this axis gets an exploration discount — this is the REOPEN rule: an axis killed under
        one operator is cheap again under another."""
        key = (axis, operator)
        l, w = self._losses.get(key, 0), self._wins.get(key, 0)
        tried_on_axis = any(a == axis for (a, _o) in {**self._losses, **self._wins})
        base = (1.0 + l) / (1.0 + w)
        if l == 0 and w == 0:                       # untried pair
            base *= 0.5 if tried_on_axis else 0.75  # extra discount if the axis is 'exhausted' under other ops
        return round(base, 3)

    def post(self, bet: Bet) -> Bet:
        bet.price = self.price(bet.axis, bet.operator)
        self.bets.append(bet)
        return bet

    def settle(self, bet: Bet, won: bool) -> Bet:
        bet.status = "WON" if won else "LOST"
        book = self._wins if won else self._losses
        book[(bet.axis, bet.operator)] = book.get((bet.axis, bet.operator), 0) + 1
        return bet

    def reopen_operators(self, axis: str, all_operators: List[str]) -> List[str]:
        """Operators worth (re)trying on a (possibly exhausted) axis: untried, or net-winning, = price ≤ 1."""
        return sorted([op for op in all_operators if self.price(axis, op) <= 1.0])

    def portfolio(self, only_open: bool = True) -> List[Bet]:
        """Live bets ranked by expected value — the standing exploration queue (TIME break)."""
        xs = [b for b in self.bets if (b.status == "OPEN" or not only_open)]
        return sorted(xs, key=lambda b: -b.expected_value)

    def policy(self) -> Dict[str, float]:
        """Turn the win/loss record into a GENERATION POLICY: a weight per (axis×operator) that the
        generator should consult so losses actually change behaviour (not just sit in a log). Weight =
        1/price, so winning moves are favoured and losing ones are damped. Untried pairs are absent
        (weight 1.0 by convention) — exploration is never forbidden, only re-weighted."""
        keys = set(self._losses) | set(self._wins)
        return {f"{axis}×{op}": round(1.0 / self.price(axis, op), 3) for axis, op in keys}

    def weight_of(self, axis: str, operator: str) -> float:
        """The policy weight a generator can multiply a candidate's score by (1.0 for an untried move)."""
        return round(1.0 / self.price(axis, operator), 3)

    def save(self, path: str) -> None:
        """Persist the portfolio + price book to JSON, so learning survives the session."""
        import json
        data = {"bets": [b.__dict__ for b in self.bets],
                "losses": {f"{a}|{o}": n for (a, o), n in self._losses.items()},
                "wins": {f"{a}|{o}": n for (a, o), n in self._wins.items()}}
        with open(path, "w") as fh:
            json.dump(data, fh, indent=2)

    @classmethod
    def load(cls, path: str) -> "Ledger":
        """Reload a persisted ledger; missing file ⇒ a fresh one (never crashes a first run)."""
        import json, os
        led = cls()
        if not os.path.exists(path):
            return led
        data = json.load(open(path))
        led.bets = [Bet(**b) for b in data.get("bets", [])]
        led._losses = {tuple(k.split("|", 1)): n for k, n in data.get("losses", {}).items()}
        led._wins = {tuple(k.split("|", 1)): n for k, n in data.get("wins", {}).items()}
        return led

    def summary(self) -> Dict:
        return {"open": sum(b.status == "OPEN" for b in self.bets),
                "won": sum(b.status == "WON" for b in self.bets),
                "lost": sum(b.status == "LOST" for b in self.bets),
                "priciest_axis_op": max(((k, self.price(*k)) for k in
                                         set(self._losses) | set(self._wins)),
                                        key=lambda kv: kv[1], default=(None, 0.0))}


def bet_from_candidate(candidate, resolver: str = "repo:tests", stake: float = 0.5,
                       family: str = "") -> Bet:
    """Turn a generator Candidate into a falsifiable bet (it still must be settled by the resolver)."""
    axis = candidate.breaks[0] if candidate.breaks else ""
    return Bet(claim=candidate.negation, world_test=candidate.discipline, resolver=resolver,
               axis=axis, operator=candidate.operator, family=family, stake=stake)


def forge_bet(candidate, ledger: Optional["Ledger"] = None, repo=None,
              repo_signals: Optional[Dict] = None, stake: float = 0.5, family: str = ""):
    """End-to-end: compile a Candidate into a bet whose resolver is a repo check, and post it to the
    ledger (priced by axis×operator). Pass a real `repo` (grounding.RepoContext) to make the check
    executable and the bet `grounded`. Returns (bet, repo_check)."""
    from .repo_world import compile_world_test
    axis = candidate.breaks[0] if candidate.breaks else ""
    check = compile_world_test(candidate.negation, axis, repo=repo, repo_signals=repo_signals)
    bet = Bet(claim=candidate.negation, world_test=check.command, resolver=f"repo:{check.kind}",
              axis=axis, operator=candidate.operator, family=family, stake=stake, grounded=check.grounded)
    if ledger is not None:
        ledger.post(bet)
    else:
        bet.price = 1.0
    return bet, check
