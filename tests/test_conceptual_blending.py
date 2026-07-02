"""test_conceptual_blending — fuse two domains into an EMERGENT structure (toward human-level invention).

Conceptual blending (Fauconnier & Turner): not recombination within one pack, not a transport of one break
across packs, but a blend that lives in BOTH domains at once and seeks emergent structure. Deterministic
(lexical distance by default; an embedder is pluggable).
"""
import OUTLIER_MCB as gsl


def test_blend_fuses_two_domains():
    blend = gsl.conceptual_blend(gsl.get_pack("numeric"), gsl.get_pack("causal"))
    assert blend is not None and blend.operator == "blend"
    assert len(blend.assumptions) == 2                       # one parent break from EACH domain
    assert blend.assumptions[0].endswith("@numeric") and blend.assumptions[1].endswith("@causal")
    assert "numeric" in blend.negation and "causal" in blend.negation
    assert gsl.box_distance(blend) > 2                       # it is a real, far-from-box move


def test_emergence_is_zero_for_a_self_blend_and_high_for_distant_domains():
    assert gsl.blend_emergence("identical statement", "identical statement") == 0.0
    near = gsl.blend_emergence("the gradient is uninformative on rugged landscapes",
                               "the gradient is uninformative on rugged landscapes")
    far = gsl.blend_emergence("an irreducible interaction term couples the inputs",
                              "a hidden common cause confounds the observed association")
    assert near == 0.0 and far > 0.3                         # distant domains → more emergent potential


def test_blend_is_not_a_transport():
    # a transport borrows ONE domain's break; a blend names a parent from BOTH and a joint, emergent claim.
    blend = gsl.blend_domains("numeric", "causal")
    assert blend is not None
    packs_in_provenance = {a.split("@")[1] for a in blend.assumptions}
    assert packs_in_provenance == {"numeric", "causal"}
    assert "EMERGENT" in blend.negation and "emergence gate" in blend.discipline


def test_blend_with_explicit_assumptions():
    blend = gsl.conceptual_blend(gsl.get_pack("numeric"), gsl.get_pack("causal"),
                                 name_a="law_is_smooth", name_b="association_is_direct")
    assert "law_is_smooth@numeric" in blend.assumptions
    assert "association_is_direct@causal" in blend.assumptions


def test_pluggable_embedder_is_accepted():
    # the default is lexical; an injected embedder must be accepted without error and yield a [0,1] value.
    emb = gsl.LexicalEmbedder()
    e = gsl.blend_emergence("alpha beta gamma", "delta epsilon zeta", embedder=emb)
    assert 0.0 <= e <= 1.0


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
