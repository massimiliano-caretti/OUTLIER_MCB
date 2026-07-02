"""test_closure_recognition — the robust closure recogniser generalises over diverse phrasings where the
keyword detector abstains, stays consistent on canonical cases, and is deterministic. Offline, zero-dep.
"""
import OUTLIER_MCB as gsl
from OUTLIER_MCB.closures import reduces_to_closure
from OUTLIER_MCB.closure_recognition import robust_closure_verdict


def test_agrees_with_keyword_detector_on_canonical_inside():
    for t in ["R = mean(e) over the bag", "sum-pool then a readout", "log-sum-exp over the bag"]:
        assert reduces_to_closure(t, "DEEPSETS") == "INSIDE"
        assert robust_closure_verdict(t) == "INSIDE"


def test_generalises_to_synonyms_the_keyword_detector_misses():
    # aggregation synonyms the keyword detector does not key on
    for t in ["combine of the encoding phi(x_i)", "accumulate of pointwise embeddings",
              "merge the per-item encodings", "gather features computed for each element alone"]:
        assert robust_closure_verdict(t) == "INSIDE"


def test_recognises_set_conditioning_as_a_true_escape():
    # set-conditioned encoders phrased diversely — must be OUTSIDE (a genuine escape), not a false INSIDE
    for t in ["sum-pool of features from an induced set-attention block over the bag",
              "the mean of representations produced by self-attention across all elements",
              "elements exchange information then sum"]:
        assert robust_closure_verdict(t) == "OUTSIDE"


def test_explicit_per_instance_overrides_incidental_mention():
    # a per-instance encoder stays INSIDE even if it mentions interaction incidentally
    assert robust_closure_verdict("mean-pool the per-instance features with a soft inter-instance note") == "INSIDE"


def test_is_deterministic():
    t = "aggregate the individually-encoded elements"
    assert robust_closure_verdict(t) == robust_closure_verdict(t)


def test_semantic_verdict_parses_a_wired_llm():
    # the LLM-backed detector uses a wired LLMProvider; test the contract with a mock (no external model)
    from OUTLIER_MCB import CallableLLMProvider, semantic_closure_verdict
    inside_llm = CallableLLMProvider(lambda p, system="", temperature=0.0, n=1: ["INSIDE"])
    outside_llm = CallableLLMProvider(lambda p, system="", temperature=0.0, n=1: ["OUTSIDE"])
    unclear_llm = CallableLLMProvider(lambda p, system="", temperature=0.0, n=1: ["maybe, hard to say"])
    assert semantic_closure_verdict("anything", inside_llm) == "INSIDE"
    assert semantic_closure_verdict("anything", outside_llm) == "OUTSIDE"
    assert semantic_closure_verdict("anything", unclear_llm) == "UNKNOWN"   # no clear answer -> honest UNKNOWN


def test_combined_verdict_is_falsification_conservative():
    # INSIDE dominates: if EITHER tier sees a reduction to the closure, the novelty claim is vetoed.
    from OUTLIER_MCB import CallableLLMProvider, combined_closure_verdict
    outside_llm = CallableLLMProvider(lambda p, system="", temperature=0.0, n=1: ["OUTSIDE"])
    inside_llm = CallableLLMProvider(lambda p, system="", temperature=0.0, n=1: ["INSIDE"])
    # deterministic tier says INSIDE (explicit per-instance marker) while a fooled LLM says OUTSIDE ->
    # the conservative combination must NOT certify a false escape.
    dressed = "a rich all-to-all readout that is in fact the mean of a function of each element alone"
    assert combined_closure_verdict(dressed, outside_llm) == "INSIDE"
    # a genuine escape: no tier detects a reduction -> OUTSIDE is asserted
    escape = "the mean of representations produced by self-attention across all elements"
    assert combined_closure_verdict(escape, outside_llm) == "OUTSIDE"
    # any INSIDE vote vetoes, regardless of the other tier
    assert combined_closure_verdict(escape, inside_llm) == "INSIDE"
