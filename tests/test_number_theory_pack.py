"""F1 world-test — a real number-theory DomainPack the guard routes to.

RED→GREEN: before this pack, 'infinite coppie di primi con gap limitato' routed to generic ("no keyword
matched"); now it routes to `number_theory`. Negative control: an unrelated prompt must NOT route here.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import OUTLIER_MCB as gsl
from OUTLIER_MCB.pack import select_pack


def test_pack_exists_and_is_well_formed():
    p = gsl.get_pack("number_theory")
    assert p.name == "number_theory"
    assert len(p.assumptions) >= 5
    # every assumption sits on a declared, non-empty axis
    for a in p.assumptions:
        ax = p.dimension_of.get(a.name, "")
        assert ax and ax in p.axes, f"{a.name} has no valid axis"
    assert p.validate() == []                          # schema-valid


def test_guard_routes_prime_gap_prompts_here_italian_and_english():
    for prompt in ["infinite coppie di primi con gap limitato",
                   "bounded gaps between primes via a sieve",
                   "twin primes conjecture"]:
        pack, score = select_pack(prompt)
        assert pack.name == "number_theory" and score > 0, prompt


def test_creative_engages_the_pack_not_no_match():
    brief = gsl.creative("infinite coppie di primi con gap limitato")
    assert isinstance(brief, str) and brief
    # the routed brief must mention this domain's box, not a generic 'no keyword matched'
    assert "sieve" in brief.lower() or "prime" in brief.lower() or "gap" in brief.lower()


def test_negative_control_unrelated_prompt_does_not_route_here():
    pack, _ = select_pack("design a CSS flexbox layout for a navbar")
    assert pack.name != "number_theory"
