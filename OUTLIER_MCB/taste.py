"""taste — an EARNED value over UNVERIFIED ideas (Tier-2, gap #1: 'the machine has no taste').

The deepest thing missing from every creativity system — this library included, and the big paid ones —
is TASTE: a *learned*, calibrated sense of which UNPROVEN direction will pay off, before the expensive
world-test is run. Today the engine ranks by `box_distance` (which rewards the STRANGE) while an LLM ranks
by likelihood (which rewards the AVERAGE); neither is calibrated on whether an idea actually SURVIVES
falsification. A genius is neither maximally weird nor maximally average — they have a nose for the fertile
few, tuned by a track record. (It is one learned metric replacing hand-weights — the opposite of the
more-metrics-is-better reflex.)

`EarnedTaste` learns that nose from the engine's OWN settled outcomes — WON/LOST bets in a `Ledger`, or
verified/refuted `EvolutionRecord`s. Crucially the labels come ONLY from external resolvers (a repo test, a
proof, data), never from the model's self-judgment, so maximizing taste cannot be gamed the way self-scoring
can. It is ONE learned metric, not another hand-weighted one:

  • features of a candidate: its operator, each broken axis, a break-count bucket, whether it needs NEW
    information — the structural signature of *how* an idea departs from the box;
  • per feature it keeps a Beta-Bernoulli posterior mean  (wins + 1) / (wins + losses + 2)  — Laplace-
    smoothed, so an UNTRAINED model returns a neutral 0.5 and can never hurt ranking (safe cold start);
  • taste_value(candidate) aggregates the candidate's feature posteriors: 'history says ideas shaped like
    this tend to survive'. It is a PRIOR over unverified ideas, disciplined later by real falsification —
    never a substitute for it.

Deterministic, zero-dependency. Fit from a Ledger or from records; use to re-rank a frontier (opt-in in
invent(taste=...)). `calibration()` reports a Brier score on the training labels so the taste can itself be
audited (a taste that does not separate survivors from failures is decorative, and says so).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple


def _bucket(n: int) -> str:
    """A coarse break-count bucket — how many axes an idea breaks at once (0, 1, 2, 3+)."""
    return f"breaks:{n}" if n < 3 else "breaks:3+"


def candidate_features(candidate) -> List[str]:
    """The structural signature taste learns over: operator · each broken axis · break-count bucket ·
    requires-new-information. Duck-typed over a generator Candidate (or any object with these attributes)."""
    g = lambda k, d=None: getattr(candidate, k, d) if not isinstance(candidate, dict) else candidate.get(k, d)
    feats: List[str] = []
    op = g("operator")
    if op:
        feats.append(f"op:{op}")
    breaks = list(g("breaks", []) or [])
    for axis in breaks:
        feats.append(f"axis:{axis}")
    feats.append(_bucket(len(breaks)))
    if g("needs", []) or g("needs_new_information", False):
        feats.append("needs_info")
    return feats


@dataclass
class EarnedTaste:
    """A learned value over unverified ideas: per-feature Beta-Bernoulli posteriors from settled outcomes."""
    wins: Dict[str, int] = field(default_factory=dict)
    losses: Dict[str, int] = field(default_factory=dict)
    n_observations: int = 0

    # ── learning ──────────────────────────────────────────────────────────────────────────────────────
    def observe(self, features: Sequence[str], survived: bool) -> None:
        """Record one SETTLED outcome (survived = passed an EXTERNAL resolver) against a feature set."""
        book = self.wins if survived else self.losses
        for f in features:
            book[f] = book.get(f, 0) + 1
        self.n_observations += 1

    def observe_candidate(self, candidate, survived: bool) -> None:
        self.observe(candidate_features(candidate), survived)

    def feature_value(self, feature: str) -> float:
        """The posterior mean P(survives | feature): Laplace-smoothed, so an unseen feature is a neutral 0.5."""
        w, l = self.wins.get(feature, 0), self.losses.get(feature, 0)
        return (w + 1) / (w + l + 2)

    def value(self, candidate) -> float:
        """Taste for one UNVERIFIED candidate in [0,1]: the mean of its feature posteriors. Neutral (0.5)
        when the model has learned nothing relevant — so a cold model never distorts a ranking."""
        feats = candidate_features(candidate)
        if not feats:
            return 0.5
        # BUGFIX: average over ALL features (an unseen feature scores the neutral 0.5 via feature_value's Laplace
        # prior), NOT only the seen ones. Otherwise a candidate could be inflated to a single high-posterior
        # feature's value while breaking many UNPROVEN axes — feature-stuffing. Now breadth of unproven breaks
        # pulls the score toward neutral, and a cold model (all-unseen) still returns exactly 0.5.
        return round(sum(self.feature_value(f) for f in feats) / len(feats), 4)

    # ── honesty: a taste that does not separate survivors from failures is decorative, and must say so ──
    def calibration(self, labelled: Sequence[Tuple[object, bool]]) -> Dict:
        """Brier score + separation on (candidate, survived) pairs: mean (value - label)^2 (lower is better)
        and mean value on survivors minus mean value on failures (higher is better). Lets the taste be audited
        instead of trusted — the same discipline the library applies to every other claim."""
        if not labelled:
            return {"brier": None, "separation": None, "n": 0}
        surv, fail, sq = [], [], 0.0
        for cand, survived in labelled:
            v = self.value(cand)
            sq += (v - (1.0 if survived else 0.0)) ** 2
            (surv if survived else fail).append(v)
        sep = (sum(surv) / len(surv) if surv else 0.0) - (sum(fail) / len(fail) if fail else 0.0)
        return {"brier": round(sq / len(labelled), 4), "separation": round(sep, 4), "n": len(labelled)}

    def is_informative(self) -> bool:
        """True once the model has enough settled evidence to be worth consulting (not a cold prior)."""
        return self.n_observations >= 4 and bool(self.wins or self.losses)


def earned_taste_from_ledger(ledger) -> EarnedTaste:
    """Learn taste from a Ledger's SETTLED bets. Each bet carries an (axis, operator) and a WON/LOST status —
    the outcome of a real external resolver. OPEN bets are ignored (no label yet)."""
    t = EarnedTaste()
    for bet in getattr(ledger, "bets", []):
        status = getattr(bet, "status", "OPEN")
        if status not in ("WON", "LOST"):
            continue
        feats = []
        if getattr(bet, "operator", ""):
            feats.append(f"op:{bet.operator}")
        if getattr(bet, "axis", ""):
            feats.append(f"axis:{bet.axis}")
        if feats:
            t.observe(feats, survived=(status == "WON"))
    return t


def earned_taste_from_records(records: Sequence) -> EarnedTaste:
    """Learn taste from EvolutionRecord-like objects: features from broken_assumptions/operator, label from
    `verified` (or `externally_settled`). Only records with a real settled label are used."""
    t = EarnedTaste()
    for r in records:
        survived = getattr(r, "verified", None)
        if survived is None:
            survived = getattr(r, "externally_settled", None)
        if survived is None:
            continue
        feats = []
        op = getattr(r, "operator", "") or ""
        if op:
            feats.append(f"op:{op}")
        for axis in (getattr(r, "broken_assumptions", None) or []):
            feats.append(f"axis:{axis}")
        feats.append(_bucket(len(getattr(r, "broken_assumptions", None) or [])))
        if feats:
            t.observe(feats, survived=bool(survived))
    return t


def taste_rerank(frontier: List[Dict], taste: EarnedTaste, weight: float = 0.3) -> List[Dict]:
    """Re-rank a scored invent()-style frontier by blending composite with learned taste:
        blended = (1 - weight) * composite + weight * taste_value.
    Writes `taste` and `taste_blended` into each item's score dict (transparent, auditable) and returns the
    list sorted by the blend. A cold/uninformative taste leaves the order essentially unchanged (values 0.5)."""
    for f in frontier:
        v = taste.value(f["candidate"])
        comp = float(f["score"].get("composite", 0.0))
        f["score"]["taste"] = v
        f["score"]["taste_blended"] = round((1.0 - weight) * comp + weight * v, 4)
    return sorted(frontier, key=lambda f: -f["score"]["taste_blended"])
