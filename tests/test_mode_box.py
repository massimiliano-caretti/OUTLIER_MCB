"""mode_box — the model's own declared default answers become the box it must leave."""
from OUTLIER_MCB.mode_box import (declare_mode, mode_pack, mode_distance, mode_brief, anti_mode_protocol,
                                  MODE_ECHO, NEAR_MODE, TAIL, UNDECLARED)
from OUTLIER_MCB import kernel

PROMPT = "invent a new rate limiter"
ANSWERS = ["Use a token bucket per client stored in Redis",
           "A sliding window counter per client in Redis",
           "Leaky bucket per client with Redis TTL keys",
           "Fixed window counter per API key in Redis"]


def test_shared_features_are_mined_and_request_words_excluded():
    m = declare_mode(PROMPT, ANSWERS, [0.4, 0.3, 0.2, 0.1])
    feats = m.shared_surface()
    assert feats[0] == "redis"                       # shared by all four → most central
    assert "client" in feats and "bucket" in feats
    assert not any(w in feats for w in ("rate", "limiter"))     # the request's own words are given, not assumed
    assert "bucket client" not in feats              # 'bucket per client' is not an adjacent bigram


def test_mode_pack_is_valid_and_breaks_distinct_features():
    pack = mode_pack(declare_mode(PROMPT, ANSWERS))
    assert pack.validate() == []
    branches = kernel.branch_on_assumptions(PROMPT, pack, k=3)
    assert len({b["axis"] for b in branches}) == 3
    assert branches[0]["assumption"] == "relies_on_redis"   # every answer shares it → priority 3


def test_mode_distance_verdicts():
    m = declare_mode(PROMPT, ANSWERS)
    assert mode_distance(ANSWERS[0], m).verdict == MODE_ECHO
    # a component swap (redis → memcached) is a variant of the default, not an exit
    assert mode_distance("a sliding window per client stored in memcached", m).verdict == NEAR_MODE
    assert mode_distance("a token bucket per user kept in memcached", m).verdict == NEAR_MODE
    far = mode_distance("admission decided by the server queue delay itself: requests carry no identity, "
                        "the limiter shapes latency instead of counting", m)
    assert far.verdict == TAIL and "redis" in far.broken


def test_degenerate_inputs_do_not_crash():
    empty = declare_mode(PROMPT, [])
    assert empty.weak and mode_distance("anything", empty).verdict == UNDECLARED
    assert declare_mode("", [None, "", "  "]).answers == []
    single = declare_mode(PROMPT, ["token bucket in redis"])
    assert single.weak and single.warnings
    assert "re-declare" in mode_brief(PROMPT, ["a", "b"])


def test_italian_mode_and_protocol():
    m = declare_mode("inventa un nuovo modo di insegnare le frazioni",
                     ["dividere una pizza in fette uguali", "usare la retta numerica con le frazioni",
                      "dividere una torta e confrontare le fette"])
    assert "dividere" in m.shared_surface() and "fette" in m.shared_surface()
    assert "frazioni" not in m.shared_surface()
    p = anti_mode_protocol("inventa un nuovo modo di insegnare le frazioni")
    assert "EN:" in p and "IT:" in p


def test_brief_names_the_breaks():
    b = mode_brief(PROMPT, ANSWERS, [0.4, 0.3, 0.2, 0.1])
    assert "relies_on_redis" in b and "TAIL" in b


def test_judge_with_mode_gates_variants_and_maps_tail_ideas():
    import OUTLIER_MCB as m
    j = m.judge("a sliding window per client stored in memcached", prompt=PROMPT, mode=ANSWERS)
    assert j.verdict == "INSIDE_THE_BOX" and j.mode.verdict == NEAR_MODE
    j = m.judge("admission decided by the server queue delay itself: requests carry no identity, "
                "the limiter shapes latency instead of counting", prompt=PROMPT, mode=ANSWERS)
    assert j.verdict == "MUST_BE_AUDITED" and j.broken_assumption.startswith("relies_on_")
    assert "vs declared mode: TAIL" in j.markdown()
    assert m.judge("anything", prompt=PROMPT).mode is None          # opt-in: unchanged without mode=


def test_route_and_brief_point_to_the_anti_mode_step():
    import OUTLIER_MCB as m
    r = m.assistant_route("inventa un nuovo modo di insegnare le frazioni")
    assert r.activate and "mode_brief" in r.next_call and "PASSO 0" in r.brief
    assert "ANTI-MODE" in m.creative("inventa un nuovo modo di insegnare le frazioni")


def test_cli_mode(capsys):
    from OUTLIER_MCB.cli import main
    main(["mode", "--problem", PROMPT] + sum([["--answer", a] for a in ANSWERS], []))
    assert "relies_on_redis" in capsys.readouterr().out
    main(["mode", "--problem", PROMPT, "--idea", ANSWERS[0]] + sum([["--answer", a] for a in ANSWERS], []))
    assert capsys.readouterr().out.startswith("MODE_ECHO")
