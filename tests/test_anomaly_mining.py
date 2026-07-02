"""#3 World-coupled settlement — "what the old paradigm calls noise, the new calls signal".

paradigm_shift named the deepest lever: an anomaly the box discards as noise is exactly where the unseen
lives. `anomaly_to_assumption` existed but was reachable only behind a settled bet loss (execute=True). This
wires it into the headline runtime: `invent(..., anomalies=[...])` mines each residual into a provisional
assumption and generates candidates that BREAK it — offline, as a first-class source.

Ablation: the SAME invent call with vs without `anomalies` — only with it does an `anomaly_*` assumption
produce candidates (a clean keep/drop flip on the candidate set).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import OUTLIER_MCB as gsl


def _assumption_slugs(inv):
    out = set()
    for it in inv.frontier:
        cand = it["candidate"] if isinstance(it, dict) else it
        out.update(getattr(cand, "assumptions", []))
    return out


def test_anomaly_becomes_a_first_class_candidate_source():
    pack = gsl.get_pack("coding")
    anomaly = "requests cluster in micro-bursts the average model treats as random noise"

    base = _assumption_slugs(gsl.invent("a rate limiter", pack=pack, beam=5, rounds=2))
    mined = _assumption_slugs(gsl.invent("a rate limiter", pack=pack, beam=5, rounds=2, anomalies=[anomaly]))

    new_from_anomaly = {s for s in mined - base if s.startswith("anomaly_")}
    assert new_from_anomaly, "the anomaly should have produced at least one breaking candidate"
    assert not any(s.startswith("anomaly_") for s in base), "the baseline must mine nothing"


def test_empty_or_blank_anomalies_are_ignored():
    pack = gsl.get_pack("coding")
    a = _assumption_slugs(gsl.invent("a rate limiter", pack=pack, beam=4, rounds=1))
    b = _assumption_slugs(gsl.invent("a rate limiter", pack=pack, beam=4, rounds=1, anomalies=["", "   "]))
    assert not any(s.startswith("anomaly_") for s in (a | b))


def test_anomaly_axis_is_honored_when_valid():
    pack = gsl.get_pack("coding")
    axis = sorted(pack.axes)[0]
    inv = gsl.invent("a rate limiter", pack=pack, beam=4, rounds=1,
                     anomalies=["a structured residual"], anomaly_axis=axis)
    # the mined assumption must sit on the requested axis (it broke into the candidate set on that axis)
    broke_axes = {b for it in inv.frontier for b in getattr(it["candidate"], "breaks", [])}
    assert axis in broke_axes
