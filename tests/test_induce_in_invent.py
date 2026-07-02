"""#6 Autonomous conceptual space — induce a pack when none maps, instead of the bland generic fallback.

The engine's reach was bounded by which domains a human hand-wrote a pack for. `infer_domain_pack` builds a
provisional pack from the problem's own words (first-principles schemas + concrete falsifiers), but it was
opt-in and disconnected. `invent(..., induce_pack=True)` wires it into the runtime: when routing finds NO
confident pack, the engine induces one and reasons in it — so it can be creative in a domain it has never
seen. Competitors are tied to a fixed benchmark / training distribution.

Ablation: the SAME unmatched prompt routes to `generic` by default, but to a prompt-specific induced pack
with `induce_pack=True`.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import OUTLIER_MCB as gsl
from OUTLIER_MCB.pack import select_pack

_UNKNOWN = "invent a zylphor quux for the baz wibble of a frobnicator"


def test_unknown_prompt_has_no_confident_pack():
    _, score = select_pack(_UNKNOWN)
    assert score == 0                                  # precondition: nothing maps → fallback territory


def test_default_falls_back_to_generic():
    inv = gsl.invent(_UNKNOWN, beam=4, rounds=1)
    assert inv.pack.name == "generic"


def test_induce_pack_builds_a_provisional_pack_for_the_unknown_domain():
    inv = gsl.invent(_UNKNOWN, beam=4, rounds=1, induce_pack=True)
    induced = gsl.infer_domain_pack(_UNKNOWN)
    assert inv.pack.name == induced.name              # used the induced pack, not generic
    assert inv.pack.name.startswith("inferred:")
    assert inv.pack.box_name == induced.box_name      # its box is the prompt-specific induced one
    # and the induced assumptions are first-principles, falsifiable (each carries a concrete falsifier)
    assert inv.pack.assumptions and all(a.falsifier for a in inv.pack.assumptions)


def test_induce_pack_does_not_override_a_matched_domain():
    """Induction only fires on a no-match; a routable prompt still uses its real pack."""
    inv = gsl.invent("a rate limiter for an API gateway", beam=4, rounds=1, induce_pack=True)
    assert inv.pack.name == "coding"
