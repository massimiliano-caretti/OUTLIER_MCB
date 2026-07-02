"""reviewer — the hostile-reviewer attack card (domain-agnostic).

For any idea, produce the card a skeptical reviewer would write BEFORE you can publish: the
"isn't this just X?" line, known relatives, likely collisions, the rejection sentence, the minimal
experiment that would defend it, and the strict claim envelope (max allowed / forbidden). All
domain content comes from the pack (known_families, failure_memory); nothing is hard-coded.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class AttackCard:
    idea: str
    is_this_just: str
    known_relatives: List[str]
    likely_collisions: List[str]
    reviewer_rejection: str
    minimal_defense_experiment: str
    max_claim_allowed: str
    forbidden_claim: str
    def as_dict(self) -> Dict: return self.__dict__
    def markdown(self) -> str:
        d = self.as_dict()
        L = [f"### Reviewer attack card — {self.idea}"]
        L += [f"- **\"Isn't this just…\":** {d['is_this_just']}",
              f"- **Known relatives:** {', '.join(d['known_relatives']) or '—'}",
              f"- **Likely collisions:** {', '.join(d['likely_collisions']) or '—'}",
              f"- **Reviewer rejection sentence:** \"{d['reviewer_rejection']}\"",
              f"- **Minimal defense experiment:** {d['minimal_defense_experiment']}",
              f"- **Maximum claim allowed:** {d['max_claim_allowed']}",
              f"- **Forbidden claim:** {d['forbidden_claim']}"]
        return "\n".join(L)


def _guess_family(idea: str, pack) -> str:
    t = (idea or "").lower()
    for f in pack.known_families:
        if f.lower() in t or f.lower().replace("_", " ") in t:
            return f
    return pack.known_families[0] if pack.known_families else "the standard approach"


def attack(idea: str, pack, family_guess: str = "", breaks: Optional[List[str]] = None,
           new_output: bool = False) -> AttackCard:
    """Build the reviewer's attack card for `idea` in the domain described by `pack`."""
    breaks = breaks or []
    fam = (family_guess or _guess_family(idea, pack))
    dead = [k for k, v in pack.failure_memory.items() if str(v.get("status", "")).startswith("DEAD")]
    box = pack.box_name

    just = (f"a re-parameterization of '{fam}' — still inside the box [{box}]")
    relatives = sorted(set(pack.known_families))[:6]
    collisions = sorted({d for d in dead})
    if not breaks:
        rej = (f"It breaks none of the domain's axes ({', '.join(pack.axes) or '—'}) — a new mechanism over the "
               f"same target is INSIDE THE BOX.")
    else:
        rej = (f"This is {just}; on a fair world-test a '{fam}' baseline matches it, and the controls do not "
               f"collapse — so the claimed novelty is naming, not mechanism.")
    defense = (f"Build the world where a '{fam}' baseline MUST fail while the idea wins (the box's variables matched "
               f"across classes), AND show the controls (shuffle the broken-axis structure) all collapse the gain"
               + ("; additionally show the NEW OUTPUT is faithful (perturbation-stable) and not reducible to a trivial baseline."
                  if new_output else "."))
    max_claim = (f"\"Breaks {', '.join(breaks)} and yields a verifiable new output no family in the box produces (local novelty).\""
                 if (breaks and new_output) else
                 f"\"A parsimonious re-formulation; ties the box baseline [{box}].\"")
    forbidden = ("\"A new paradigm / beats the state of the art / a never-before-seen design\" — "
                 "unless a separation is demonstrated on a world-test, not asserted.")
    return AttackCard(idea, just, relatives, collisions, rej, defense, max_claim, forbidden)
