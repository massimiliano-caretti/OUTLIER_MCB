"""test_capabilities — the self-describing index that lets an LLM drive the WHOLE engine automatically, and
the composed autonomous() reaching the four creativity inventors. Deterministic and offline.
"""
import OUTLIER_MCB as gsl


def test_every_capability_names_a_real_exported_symbol():
    # the index can never advertise a capability that isn't actually there
    for cap in gsl.capabilities():
        assert hasattr(gsl, cap.entry), f"capability '{cap.name}' points at missing entry '{cap.entry}'"


def test_index_covers_the_four_creativity_frontier_capabilities():
    entries = {c.entry for c in gsl.capabilities()}
    for e in ("propose_new_physics", "ground_new_symbol", "invent_new_language", "elegance_score", "autonomous"):
        assert e in entries
    md = gsl.capabilities_markdown()
    assert "capability index" in md.lower() and "proof-of-concept" in md.lower()


def test_frontier_capabilities_are_marked_proof_of_concept_honestly():
    poc = {c.entry for c in gsl.capabilities() if c.maturity != "mature"}
    assert {"propose_new_physics", "ground_new_symbol", "invent_new_language", "elegance_score"} <= poc


# ── the ONE composed executor reaches all four inventors when given their inputs ───────────────────────
def test_autonomous_reaches_the_creativity_inventors():
    res = gsl.autonomous(
        "invent broadly",
        invent_physics=True,
        language_family=[[(x, 2 * (x + k)) for x in range(4)] for k in (1, 2, 3)],
        ground_log=["settle", "timeout", "retry"] * 6 + ["ok"],
        aesthetic_artifact="m*c**2",
        beam=3, rounds=1)
    used = set(res.used_capabilities)
    assert {"invent_physics", "invent_language", "ground_symbols", "aesthetics"} <= used
    assert res.physics is not None and res.language["macros"]
    assert res.meaning and res.aesthetics["elegance"] >= 0.0


def test_autonomous_frontier_tracks_are_optional():
    res = gsl.autonomous("just ideas", beam=3, rounds=1)          # no frontier inputs → not run, not faked
    used = set(res.used_capabilities)
    assert not ({"invent_physics", "invent_language", "ground_symbols", "aesthetics"} & used)
    assert res.physics is None and res.language is None


# ── the continuous per-turn router: fires on a trigger, stays quiet otherwise (bilingual) ─────────────
def test_assistant_route_activates_on_trigger_and_is_quiet_otherwise():
    on = gsl.assistant_route("inventa un modo nuovo di fare X")   # Italian trigger
    assert on.activate is True and on.entrypoint and on.as_dict()["activate"] is True
    off = gsl.assistant_route("what time is it")
    assert off.activate is False and off.action == "answer_directly"


def test_capability_index_entries_are_all_public():
    # everything the index advertises is in the public API surface (importable by users)
    for cap in gsl.capabilities():
        assert cap.entry in dir(gsl)


def test_version_is_exposed_and_sane():
    v = gsl.__version__
    assert isinstance(v, str) and v.count(".") == 2 and all(p.isdigit() for p in v.split("."))
