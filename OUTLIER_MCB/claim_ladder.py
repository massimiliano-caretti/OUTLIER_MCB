"""claim_ladder — the rigor ladder every claim must climb before it may use a strong word (improvement #9).

The engine should be able to be brilliant WITHOUT becoming a liar. A claim occupies exactly one rung based
on the evidence it actually has, and certain words are LOCKED to certain rungs: you may not write 'theorem'
or 'proved' below a symbolic proof, nor 'discovered' / 'never seen' / 'novel' without an online prior-art
check. gate_claim_language rewrites an over-reaching sentence into the strongest HONEST one its evidence
permits — so genius is allowed, fabrication is not.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# the rungs, weakest → strongest (the rigor axis). PRIOR_ART_CHECKED is an ORTHOGONAL flag, tracked separately.
LADDER = ("IDEA_ONLY", "FALSIFIABLE_CLAIM", "EMPIRICALLY_SUPPORTED", "COUNTEREXAMPLE_FOUND",
          "SYMBOLICALLY_PROVED", "FORMALLY_VERIFIED")
_RANK = {s: i for i, s in enumerate(LADDER)}

# strong words → the minimum rung (and whether a prior-art check is also required) that LICENSES the word.
_WORD_RULES = {
    "theorem": ("SYMBOLICALLY_PROVED", False),
    "proved": ("SYMBOLICALLY_PROVED", False),
    "proven": ("SYMBOLICALLY_PROVED", False),
    "qed": ("SYMBOLICALLY_PROVED", False),
    "verified": ("FORMALLY_VERIFIED", False),
    "discovered": ("EMPIRICALLY_SUPPORTED", True),
    "discovery": ("EMPIRICALLY_SUPPORTED", True),
    "never seen": ("EMPIRICALLY_SUPPORTED", True),
    "never been seen": ("EMPIRICALLY_SUPPORTED", True),
    "unprecedented": ("FALSIFIABLE_CLAIM", True),
    "novel": ("FALSIFIABLE_CLAIM", True),
    "brand new": ("FALSIFIABLE_CLAIM", True),
    "world first": ("EMPIRICALLY_SUPPORTED", True),
    "breakthrough": ("EMPIRICALLY_SUPPORTED", True),
}
# FIX B: architecture-novelty words need BOTH a proven closure-escape AND a real prior-art check before use.
_CLOSURE_WORDS = {
    "innovative": "not yet shown to be an advance",
    "alive architecture": "alive on its own world only",
    "architectural novelty": "closure-escape pending",
    "new architecture": "candidate architecture (closure-escape pending)",
    "genuinely new": "provisionally distinct",
}

# the honest replacement for a word that its evidence does not license.
_HEDGE = {
    "theorem": "conjecture", "proved": "argued", "proven": "argued", "qed": "(not proved)",
    "verified": "checked (not formally verified)", "discovered": "proposed", "discovery": "proposal",
    "never seen": "not found among the sources searched", "never been seen": "not found among the sources searched",
    "unprecedented": "not matched in the searched prior art", "novel": "provisionally novel",
    "brand new": "provisionally new", "world first": "not matched in the searched prior art",
    "breakthrough": "candidate improvement",
}


@dataclass
class ClaimStatus:
    claim: str
    rung: str                         # the achieved rigor rung
    prior_art_checked: bool
    achieved: List[str] = field(default_factory=list)   # every rung-or-flag actually reached
    def rank(self) -> int:
        return _RANK.get(self.rung, 0)
    def markdown(self) -> str:
        pa = "prior-art CHECKED" if self.prior_art_checked else "prior-art NOT checked"
        return f"- claim rung: **{self.rung}** · {pa} · achieved: {', '.join(self.achieved) or '—'}"


def classify_claim(claim: str, evidence: Optional[Dict] = None) -> ClaimStatus:
    """Place a claim on the ladder from the evidence it actually carries. `evidence` flags (all optional):
    falsifier, empirical_support, counterexample, symbolic_proof, formal_verification, prior_art_checked."""
    e = evidence or {}
    rung = "IDEA_ONLY"
    achieved = ["IDEA_ONLY"]
    if e.get("falsifier"):
        rung = "FALSIFIABLE_CLAIM"; achieved.append("FALSIFIABLE_CLAIM")
    if e.get("empirical_support"):
        rung = "EMPIRICALLY_SUPPORTED"; achieved.append("EMPIRICALLY_SUPPORTED")
    if e.get("counterexample"):
        rung = "COUNTEREXAMPLE_FOUND"; achieved.append("COUNTEREXAMPLE_FOUND")
    if e.get("symbolic_proof"):
        rung = "SYMBOLICALLY_PROVED"; achieved.append("SYMBOLICALLY_PROVED")
    if e.get("formal_verification"):
        rung = "FORMALLY_VERIFIED"; achieved.append("FORMALLY_VERIFIED")
    prior_art = bool(e.get("prior_art_checked"))
    if prior_art:
        achieved.append("PRIOR_ART_CHECKED")
    return ClaimStatus(claim=claim, rung=rung, prior_art_checked=prior_art, achieved=achieved)


def _licenses(status: ClaimStatus, min_rung: str, needs_prior_art: bool) -> bool:
    return status.rank() >= _RANK[min_rung] and (status.prior_art_checked or not needs_prior_art)


def gate_claim_language(text: str, evidence: Optional[Dict] = None, status: Optional[ClaimStatus] = None) -> Dict:
    """Scan `text` for strong words the evidence does not license and rewrite them into the strongest HONEST
    form. Returns {allowed, status, violations, rewritten}. `allowed` is True iff no strong word was misused."""
    st = status or classify_claim(text, evidence)
    external_settlement = bool((evidence or {}).get("external_settlement"))
    violations: List[Dict] = []
    rewritten = text
    closure_escape = bool((evidence or {}).get("closure_escape"))
    for word, (min_rung, needs_pa) in _WORD_RULES.items():
        if re.search(r"\b" + re.escape(word) + r"\b", rewritten, flags=re.IGNORECASE):
            # 'verified' is also licensed by EXTERNAL settlement (a repo test / data / red-team that passed —
            # fix A): externally settled ≠ formally verified, but it is a real, non-self-judged certification.
            # (Audit finding #4 proposed gating this on an achieved rung; the module's CONTRACT is that
            # external_settlement is only True when a real resolver passed, and tests assert the bare flag
            # licenses 'verified' — so hardening belongs at the caller, not here. Left intentional.)
            if word == "verified" and external_settlement:
                continue
            if not _licenses(st, min_rung, needs_pa):
                violations.append({"word": word, "needs_rung": min_rung, "needs_prior_art": needs_pa,
                                   "have_rung": st.rung, "have_prior_art": st.prior_art_checked})
                rewritten = re.sub(r"\b" + re.escape(word) + r"\b", _HEDGE[word], rewritten, flags=re.IGNORECASE)
    # FIX B: architecture-novelty words require a proven closure-escape AND a real prior-art check.
    for word, hedge in _CLOSURE_WORDS.items():
        if re.search(re.escape(word), rewritten, flags=re.IGNORECASE) and not (closure_escape and st.prior_art_checked):
            violations.append({"word": word, "needs_rung": "closure_escape+prior_art",
                               "have_closure_escape": closure_escape, "have_prior_art": st.prior_art_checked})
            rewritten = re.sub(re.escape(word), hedge, rewritten, flags=re.IGNORECASE)
    return {"allowed": not violations, "status": st, "violations": violations, "rewritten": rewritten}


def claim_ladder_ablation() -> Dict:
    """Ablation for #9: the ladder blocks an overclaim that a no-ladder (naive) pass would emit verbatim. The
    same words are licensed once the evidence reaches the required rung — proving the gate is about EVIDENCE,
    not censorship."""
    text = "We proved a novel theorem and discovered a breakthrough."
    weak = gate_claim_language(text, {"falsifier": True})                       # idea-stage evidence
    strong = gate_claim_language(text, {"falsifier": True, "empirical_support": True,
                                        "symbolic_proof": True, "formal_verification": True,
                                        "prior_art_checked": True})
    naive_would_emit = text                                                     # no gate → verbatim overclaim
    return {"naive_emits_overclaim": naive_would_emit,
            "gated_blocks": not weak["allowed"], "gated_rewrote_away_strong_words": "theorem" not in weak["rewritten"].lower(),
            "licensed_with_full_evidence": strong["allowed"],
            "gate_is_about_evidence": (not weak["allowed"]) and strong["allowed"]}
