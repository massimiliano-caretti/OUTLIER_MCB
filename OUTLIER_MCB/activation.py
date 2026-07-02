"""activation — make using OUTLIER_MCB a DEFAULT ROUTINE for any AI coding assistant (Claude / ChatGPT /
Gemini / Cursor / …), not an option.

The idea: once the user asks to use the library, every later request for something NEW / NOVEL / INVENTED /
DISCOVERED must flow through it. This module gives two provider-agnostic primitives:
  • assistant_brief(prompt) — a one-call STANDING BRIEF the model obeys before answering a creativity request;
  • activation_snippet()    — the text to drop into AGENTS.md / CLAUDE.md / .cursorrules so the routine auto-loads.

It owns no creativity logic — it routes to the existing entrypoints (creative / explore) and pins the
non-negotiable honesty rules so the assistant cannot drift back to answering from memory.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# The public assistant contract is bilingual: English + Italian. Keep JSON keys stable in English, but make the
# human-facing compact brief understandable in both languages.
SUPPORTED_ASSISTANT_LANGUAGES = ("en", "it")

# words that should trigger the routine in English and Italian.
TRIGGERS = ("new", "novel", "invent", "discover", "original", "never seen", "breakthrough", "from scratch",
            "rethink", "a better way", "improve", "improvement", "better", "different way",
            "nuovo", "inventa", "scopri", "originale", "mai visto", "fuori dagli schemi",
            "migliora", "migliorare", "miglioramento", "migliore", "modo migliore",
            "ripensa", "da zero", "innovare", "innovazione", "invenzione", "scoperta")

STANDING_RULES = """\
[OUTLIER_MCB — STANDING ROUTINE: once asked to use it, EVERY later 'new / novel / invent / discover'
 request goes through the library FIRST. Do not answer such a request from memory.]
1. Get the brief, then obey it:
     python -c "import OUTLIER_MCB as m; print(m.creative('<the request>'))"
   or run the full loop (generate → settle externally → audit → one honest report):
     m.explore('<request>', evaluator=<objective>, prior_art_provider=<online>, llm=<your model>)
2. Break a HIDDEN ASSUMPTION and name it. An idea that breaks none is INSIDE_THE_BOX — not an answer.
3. SETTLE EXTERNALLY — data / repo tests / z3 / lean — never by your own judgment (the engine never self-certifies).
4. Check prior art ONLINE when you claim novelty; always report novelty_scope:
     LOCAL_ONLY · INCOMPLETE_ONLINE_SEARCH · ONLINE_PRIOR_ART_CHECKED.
5. NEVER say 'absolute novelty' / 'new theorem' / 'never seen before' without a formal proof + an online
   prior-art check + a passing verifier. Use the graded verdicts (RENAMED / COLLAGE / WEAKLY / PROVISIONALLY
   NOVEL ON CHECKED SOURCES / VERIFIED USEFUL NOVELTY).
6. For MATH/THEOREMS: m.explore(q, math_claim='...', math_variables={...}) → z3/lean DECIDES (FORMALLY_PROVED
   / FORMALLY_DISPROVED with a guaranteed counterexample / TOOL_UNAVAILABLE). No proof ⇒ it stays a conjecture.
7. DISCOVER THE WHOLE ENGINE from one place: m.capabilities_markdown() lists every entry point (invent · judge ·
   explore · autonomous · autonomous_discover · novelty_audit · math_frontier · run_active_experiments · incubate ·
   and the creativity frontier: propose_new_physics / ground_new_symbol / invent_new_language / elegance_score).
   The single COMPOSED executor is m.autonomous('<request>', ...) — each argument gates a track; it runs only
   what its inputs allow.
The spark is yours; the rigor is the machine's — and it must be able to DIE on a world-test."""


def should_activate(prompt: str) -> bool:
    """True when the prompt asks for something new/novel/invented (any language) — the routine should fire."""
    t = (prompt or "").lower()
    return any(w in t for w in TRIGGERS)


@dataclass
class AssistantRoute:
    """Compact per-turn decision for assistants that call the library continuously."""
    prompt: str
    activate: bool
    action: str
    entrypoint: str
    reason: str
    next_call: str = ""
    pack: str = ""
    break_assumption: str = ""
    break_axis: str = ""
    novelty_scope_required: bool = False
    languages: tuple = SUPPORTED_ASSISTANT_LANGUAGES
    must_report: List[str] = field(default_factory=list)
    brief: str = ""
    preflight: Optional[Dict] = None

    def as_dict(self) -> Dict:
        return {
            "prompt": self.prompt,
            "activate": self.activate,
            "action": self.action,
            "entrypoint": self.entrypoint,
            "reason": self.reason,
            "next_call": self.next_call,
            "pack": self.pack,
            "break_assumption": self.break_assumption,
            "break_axis": self.break_axis,
            "novelty_scope_required": self.novelty_scope_required,
            "languages": list(self.languages),
            "must_report": list(self.must_report),
            "brief": self.brief,
        }

    def markdown(self) -> str:
        if not self.activate:
            return "\n".join([
                "# OUTLIER_MCB route — not activated",
                f"- action: {self.action}",
                f"- reason: {self.reason}",
                "- EN: answer normally.",
                "- IT: rispondi normalmente.",
            ])
        lines = [
            "# OUTLIER_MCB route — activated",
            f"- action: {self.action}",
            f"- entrypoint: `{self.entrypoint}`",
            f"- next call: `{self.next_call}`",
            f"- pack: {self.pack or '—'}",
        ]
        if self.break_assumption:
            lines.append(f"- break: {self.break_assumption} on {self.break_axis}")
        lines.append(f"- reason: {self.reason}")
        lines.append("- languages: English + Italian / inglese + italiano")
        if self.must_report:
            lines.append("- must report: " + "; ".join(self.must_report))
        if self.brief:
            lines.append("\n" + self.brief)
        return "\n".join(lines)


def assistant_route(prompt: str, pack=None, provider=None, full_brief: bool = False) -> AssistantRoute:
    """Per-turn router for an LLM that uses OUTLIER_MCB continuously.

    `assistant_brief()` is intentionally exhaustive and good for first activation. This function is the compact
    loop primitive: call it every turn, follow `activate/action/entrypoint`, and only request the long brief when
    `full_brief=True`.
    """
    if not should_activate(prompt):
        return AssistantRoute(
            prompt=prompt or "",
            activate=False,
            action="answer_directly",
            entrypoint="",
            reason="no novelty/invention/discovery trigger matched",
        )

    from .preflight import preflight_creative_request
    pf = preflight_creative_request(prompt, pack=pack)
    rec = pf.get("recommended_direction") or {}
    missing = pf.get("missing_information") or {}
    elicitation = bool(pf.get("elicitation_required"))
    action = "elicit_pack_or_green_star" if elicitation else "creative_brief_then_answer"
    entrypoint = "elicit_pack|green_star" if elicitation else "creative"
    next_call = (
        "elicit_pack(prompt) or green_star(prompt)"
        if elicitation else
        "creative(prompt)"
    )
    must_report = [
        "broken_assumption",
        "world_test_or_death_gate",
        "claim_ladder_status",
        "novelty_scope",
    ]
    if missing.get("data_insufficient"):
        must_report.append(f"missing_information:{missing.get('recommended_first')}")
    compact = "\n".join([
        "[compact routine]",
        "EN: Do not answer from memory. Break the named assumption, state the world-test, and hedge novelty to evidence.",
        "IT: Non rispondere a memoria. Rompi l'assunzione indicata, dichiara il world-test e limita la novità alle prove.",
        f"Recommended break: {rec.get('assumption', '—')} on {rec.get('dimension', '—')}.",
        f"Death-gate: {pf.get('death_gate', '—')}",
    ])
    return AssistantRoute(
        prompt=prompt or "",
        activate=True,
        action=action,
        entrypoint=entrypoint,
        reason=(pf.get("domain_guard") or {}).get("reason", "novelty trigger matched"),
        next_call=next_call,
        pack=pf.get("pack", ""),
        break_assumption=rec.get("assumption", ""),
        break_axis=rec.get("dimension", ""),
        novelty_scope_required=True,
        must_report=must_report,
        brief=assistant_brief(prompt, pack=pack, provider=provider) if full_brief else compact,
        preflight=pf,
    )


def assistant_brief(prompt: str, pack=None, provider=None) -> str:
    """The one-call standing brief: the non-negotiable rules + the engine's preflight for THIS request (which
    assumption to break, the death-gate, the forbidden families). Paste-and-obey for any LLM assistant."""
    from .preflight import creative
    return STANDING_RULES + "\n\n" + creative(prompt, pack=pack, provider=provider)


def activation_snippet() -> str:
    """The provider-agnostic block to drop into AGENTS.md / CLAUDE.md / .cursorrules so the routine auto-loads
    for any assistant. Plain, tool-neutral, copy-paste."""
    return f"""\
# Using OUTLIER_MCB (standing routine for AI coding assistants)

This project uses **OUTLIER_MCB**, an assumption-negation + falsification engine for rigorous, honest
invention and discovery. It works with ANY assistant (Claude, ChatGPT, Gemini, Cursor, …).

**When the user asks for something new / novel / invented / discovered in English or Italian, you MUST use it —
this is a routine, not an option.**

**Quando l'utente chiede qualcosa di nuovo / originale / inventato / scoperto in inglese o italiano, devi usare
la libreria: è una routine, non un'opzione.** Run the brief first, then obey it:

```bash
python -c "import OUTLIER_MCB as m; print(m.assistant_brief('''<the user request>'''))"
```

For continuous use after the first activation, route every turn through the compact decision API:

```bash
python -m OUTLIER_MCB route --problem "<the user request>" --json
```

If `activate` is false, answer normally. If true, follow `entrypoint`, `next_call`, and always report the
broken assumption, world-test/death-gate, claim-ladder status, and `novelty_scope`.

For the full loop (generate → settle by an external resolver → audit → one honest report):

```python
import OUTLIER_MCB as m
m.explore("<request>", evaluator=<objective>, prior_art_provider=<online>, llm=<your model>)   # invention
m.explore("<claim>", math_claim="x**2+y**2>=2*x*y", math_variables={{"x":(-5,5),"y":(-5,5)}})  # theorems → z3/lean
```

{STANDING_RULES}
"""
