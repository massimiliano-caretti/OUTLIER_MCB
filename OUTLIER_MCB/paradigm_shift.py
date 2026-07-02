"""paradigm_shift — force the seven paradigm-shift questions (domain-agnostic).

A paradigm shift is not a new mechanism; it is re-deciding what is signal vs noise. This module turns
an assumption (from a DomainPack) into the seven forced questions and fills them from the pack, so the
assistant must answer them BEFORE proposing anything.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict


SEVEN_QUESTIONS = [
    "Which obviousness are we treating as a law of nature?",
    "What happens if it is false?",
    "What does the OLD paradigm call noise?",
    "What does the NEW paradigm call signal?",
    "Which new OUTPUT becomes possible?",
    "Which new INFORMATION is required?",
    "Which minimal EXPERIMENT can decide?",
]


@dataclass
class ParadigmShift:
    assumption: str
    dimension: str
    answers: Dict[str, str]
    honest_verdict: str
    def markdown(self) -> str:
        L = [f"### Paradigm-shift (green star) — negate `{self.assumption}`  [axis {self.dimension}]"]
        for q in SEVEN_QUESTIONS:
            L.append(f"- **{q}** {self.answers.get(q, '—')}")
        L.append(f"- **Honest verdict for this axis:** {self.honest_verdict}")
        return "\n".join(L)


def paradigm_shift(assumption_name: str, pack, problem_text: str = "") -> ParadigmShift:
    """Fill the seven questions for `assumption_name` using the domain described by `pack`."""
    a = pack.by_name().get(assumption_name)
    axis = pack.dimension_of.get(assumption_name, "—")
    if a is None:
        from .errors import AssumptionNotFoundError
        raise AssumptionNotFoundError(
            f"assumption '{assumption_name}' is not in pack '{pack.name}'; "
            f"available: {sorted(pack.by_name())}")

    # data the break requires (from the pack's typed edges)
    from . import kernel
    g = kernel.graph_of(pack, problem_text)
    data_req = g.data_requirements().get(assumption_name, [])
    axis_verdict = pack.axes.get(axis, {}).get("verdict", "—")

    ans = {
        SEVEN_QUESTIONS[0]: f"'{a.description}' — assumed because: {a.why_obvious}",
        SEVEN_QUESTIONS[1]: a.if_false,
        SEVEN_QUESTIONS[2]: f"whatever the box [{pack.box_name}] discards as nuisance on the '{axis}' axis.",
        SEVEN_QUESTIONS[3]: f"the structure on the '{axis}' axis itself becomes the discriminative object.",
        SEVEN_QUESTIONS[4]: f"an output that only becomes possible once '{a.name}' is false: {a.if_false}",
        SEVEN_QUESTIONS[5]: (", ".join(data_req) if data_req else "none beyond the current information"),
        SEVEN_QUESTIONS[6]: a.falsifier or "construct the world where the box must fail and the broken-axis idea wins.",
    }
    return ParadigmShift(assumption_name, axis, ans, axis_verdict)
