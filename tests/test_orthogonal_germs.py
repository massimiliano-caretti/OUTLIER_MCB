"""test_orthogonal_germs -- new latent-basis creativity, externally gated.

The score is not self-referential: a fixed solver, external instances/labels and a control decide whether the
new basis is useful. The orchestration tests make sure the capability is actually reached by invent(),
autonomous(), the LLM prompt builder and the deterministic agent panel.
"""
import OUTLIER_MCB as gsl


_INSTANCES = list(range(30))
_LABELS = [n % 3 == 0 for n in _INSTANCES]


def _zero_solver(encoded):
    return encoded == 0


def test_orthogonal_germ_reduces_external_task_and_control_collapses():
    pack = gsl.get_pack("generic")
    cand = gsl.propose_orthogonal_germ(pack, "decide triadic divisibility by an unseen residue coordinate")
    germ = gsl.OrthogonalLatentGerm(
        name="triadic_residue_phase",
        encode=lambda n: n % 3,
        description="triadic residue phase coordinate",
        candidate=cand,
    )

    verdict = gsl.evaluate_orthogonal_germ(germ, _zero_solver, _INSTANCES, _LABELS, pack=pack)

    assert verdict.accepted
    assert verdict.status == "ORTHOGONAL_REDUCES"
    assert verdict.accuracy == 1.0
    assert verdict.reducibility >= 0.15
    assert verdict.control_gap >= 0.15
    assert verdict.external_yield > 0.0


def test_orthogonal_germ_rejects_basis_with_no_external_gain():
    germ = gsl.OrthogonalLatentGerm(
        name="decorative_phase",
        encode=lambda n: n,
        description="decorative phase coordinate",
    )

    verdict = gsl.evaluate_orthogonal_germ(germ, _zero_solver, _INSTANCES, _LABELS, pack=gsl.get_pack("generic"))

    assert not verdict.accepted
    assert verdict.status in {"NO_EXTERNAL_GAIN", "DECORATIVE", "IN_BOX_BASIS"}


def test_invent_injects_orthogonal_germ_candidate():
    inv = gsl.invent("invent a new solver representation", beam=4, rounds=1)

    assert any(f["candidate"].operator == "orthogonal_germ" for f in inv.frontier)
    assert "Orthogonal germ" in inv.note


def test_autonomous_records_orthogonal_germ_capability():
    res = gsl.autonomous("invent a new solver representation", beam=4, rounds=1)

    assert "orthogonal_germs" in res.used_capabilities


def test_llm_prompt_forces_orthogonal_germ_move():
    from OUTLIER_MCB.llm_loop import _build_prompt

    class _Archive:
        def elites(self):
            return []

    prompt = _build_prompt("invent a new solver representation", gsl.get_pack("generic"), _Archive(),
                           [], "", "", set(), 2)

    assert "ORTHOGONAL LATENT GERM" in prompt
    assert "misaligned" in prompt


def test_orthogonal_germ_relevance_is_conditional():
    pack = gsl.get_pack("generic")
    # representation-flavoured requests -> the new-basis move is on-topic
    assert gsl.orthogonal_germ_relevant(pack, "invent a new solver representation")
    assert gsl.orthogonal_germ_relevant(pack, "find a better encoding for graphs")
    assert gsl.orthogonal_germ_relevant(pack, "invent a new latent basis coordinate")
    # unrelated requests -> the move must NOT fire (no fixed always-on noise)
    assert not gsl.orthogonal_germ_relevant(pack, "invent a new sorting algorithm")
    assert not gsl.orthogonal_germ_relevant(pack, "rethink the objective function we optimize")
    assert not gsl.orthogonal_germ_relevant(pack, "design a faster cache")


def test_invent_omits_orthogonal_germ_when_off_topic():
    inv = gsl.invent("invent a faster in-memory cache eviction policy", beam=4, rounds=1)

    assert not any(f["candidate"].operator == "orthogonal_germ" for f in inv.frontier)
    assert "Orthogonal germ" not in inv.note


def test_invent_can_force_orthogonal_germ_off():
    inv = gsl.invent("invent a new solver representation", beam=4, rounds=1, use_orthogonal_germs=False)

    assert not any(f["candidate"].operator == "orthogonal_germ" for f in inv.frontier)


def test_llm_prompt_omits_orthogonal_germ_when_off_topic():
    from OUTLIER_MCB.llm_loop import _build_prompt

    class _Archive:
        def elites(self):
            return []

    prompt = _build_prompt("design a faster cache", gsl.get_pack("generic"), _Archive(),
                           [], "", "", set(), 2)

    assert "ORTHOGONAL LATENT GERM" not in prompt


def test_cognitive_panel_has_orthogonalist_role():
    report = gsl.CognitivePanel(gsl.get_pack("generic")).deliberate("invent a new solver representation")
    ev = report.by_role("Orthogonalist")

    assert ev is not None
    assert ev.evidence["candidate"]["operator"] == "orthogonal_germ"
    assert "control" in ev.evidence["discipline"].lower()
