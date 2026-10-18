"""llm_divergence — a DIVERGENT → CONVERGENT generation phase for the LLM loop, built from techniques with
published evidence for widening what a language model proposes (each one is a separate, testable step):

  1. ANTI-MODE first (denial seed). The model is asked, cool, for the answers it would MOST LIKELY give; those
     become the declared mode (mode_box.declare_mode) that every later intent must leave. LLMs are measurably
     homogeneous on open-ended prompts — within and across model families (Jiang et al., "Artificial Hivemind",
     NeurIPS 2025, arXiv:2510.22954) — so the first job is to name the mode, not to sample more of it.
  2. INTENT FACTORISATION. Generation is split into a short "intent" (which assumption breaks + the one-sentence
     mechanism) sampled HOT, then the full candidate developed COOL (Ahmed et al., Intent Factored Generation,
     ICML 2025, arXiv:2506.09659).
  3. SEARCH OVER OBSERVATIONS / PLANS, not solutions. Each divergent call first writes observations about the
     problem, then intents built on them (Wang et al., PlanSearch, ICLR 2025, arXiv:2409.03733: search gains
     track idea diversity).
  4. INDEPENDENT CALLS WITH DISTANT PERSONAS. Every divergent call is a fresh context with a different
     discipline lens: LLMs fixate on their own earlier outputs, and personas partition the knowledge they draw on
     (Deng, Brucks & Toubia 2026, arXiv:2602.20408; Meincke, Mollick & Terwiesch 2024, arXiv:2402.01727).
  5. VERBALIZED SAMPLING. Each intent carries the model's own estimate of how typical it is, and the selection
     prefers the tail (Zhang et al., arXiv:2510.01171: 1.6–2.1× diversity in creative writing, training-free).
  6. DENIAL PROMPTING. Known families, the declared mode, ideas that already died (this run and the persistent
     failure memory) and archived elites are listed as explicit DO-NOT-USE constraints (Lu et al., NAACL 2025,
     arXiv:2407.09007), and the list grows every round as candidates die.
  7. NOVELTY REJECTION + NICHES. An intent too close to anything already known is discarded before a convergent
     call is spent on it (OMNI-EPIC, ICLR 2025, arXiv:2405.15568), and the survivors are picked round-robin across
     distinct broken assumptions, unoccupied archive niches first (MAP-Elites / QDAIF, ICLR 2024).

What this module deliberately does NOT do: decide what is novel or good. It only widens and filters what is
PROPOSED; every developed candidate still goes through the loop's prior-art gate, diversity gate and executable
RED→GREEN settlement. LLM judges are biased toward familiar, low-perplexity text (Wataoka et al.,
arXiv:2410.21819), so no step here asks a model whether an idea is creative.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from .embeddings import semantic_distance
from .llm import call_llm, sampler_controls, supports_roles, supports_sampling, _extract_json

# distant discipline lenses (Deng et al.: ordinary personas already partition knowledge; distance adds spread)
DEFAULT_PERSONAS: Tuple[str, ...] = (
    "a physicist who reasons from conservation laws, symmetries and limiting cases",
    "an evolutionary biologist who thinks in populations, variation, selection and niches",
    "an economist who thinks in incentives, prices, contracts and equilibria",
    "a pure mathematician who looks for the invariant, the dual formulation or the change of representation",
    "a hardware engineer who thinks in latency, energy, locality and physical layout",
    "an adversary who wants to break, game or exploit the system",
    "a historian of abandoned approaches who revives ideas that died for reasons that are no longer true",
    "an ecologist who thinks in feedback loops, resource flows and resilience",
    "a linguist who thinks in representations, grammars, compression and ambiguity",
    "an operations researcher who thinks in queues, flows, scheduling and bottlenecks",
)

# The sampler profile of the divergent phase where the provider exposes the controls. Sampling at T=1 from the full
# distribution degenerates through the unreliable tail, and nucleus truncation (top_p ≈ 0.9–0.95) keeps it coherent
# while a fixed top-k cut ignores the shape of the distribution (Holtzman et al., "The Curious Case of Neural Text
# Degeneration", ICLR 2020) — so the divergent phase samples the model's own distribution (T=1) with a nucleus cut
# and no top-k (Ollama's default top_k=40 is a chat-tuned cut). min_p / top_n_sigma stay opt-in: the evidence for
# min_p is disputed (arXiv:2506.13681), and top_n_sigma is not honoured by every server (Ollama ignores it).
AUTO_DIVERGE_SAMPLING: Dict = {"top_p": 0.95, "top_k": 0}

_DIVERGE_SYSTEM = ("Divergent phase. Generate genuinely different directions, not variations of the standard answer. "
                   "No code and no self-evaluation: only observations and intents in the requested line format.")
_MODE_SYSTEM = ("Be candid and conventional: state what you would actually answer by default, not what sounds "
                "original. Use the requested line format only.")

# rejection kinds (the status of a rejected intent is f"REJECTED_{kind}")
NEAR_KNOWN, MODE_ECHO_KIND, DUPLICATE = "NEAR_KNOWN", "MODE", "DUPLICATE"
SELECTED, SURPLUS = "SELECTED", "SURPLUS"


@dataclass
class DivergenceConfig:
    """Knobs of the divergent → convergent phase. Defaults follow the cited evidence where it exists and leave
    the server's sampler defaults alone where it is disputed (min_p): set `diverge_sampling` to opt in."""
    diverge_calls: int = 3                      # independent hot calls per round, one persona each
    intents_per_call: int = 5
    diverge_temperature: float = 1.0
    converge_temperature: float = 0.2
    diverge_sampling: Optional[Dict] = None     # None = AUTO_DIVERGE_SAMPLING ∩ what the provider honours;
    converge_sampling: Optional[Dict] = None    # an explicit dict (e.g. {"min_p": 0.05}) is forwarded as given
    novelty_min_distance: float = 0.25          # intents nearer than this to a known/denied text are discarded
    tail_probability: float = 0.35              # verbalized p above this = the model's own mode → ranked last
    auto_mode: bool = True                      # elicit the model's default answers when none are declared
    mode_answers: int = 5
    personas: Tuple[str, ...] = DEFAULT_PERSONAS
    seed: Optional[int] = 0                     # per-call seeds derive from it; None = unseeded sampling
    max_denials_in_prompt: int = 12

    def __post_init__(self):
        if self.diverge_calls < 1 or self.intents_per_call < 1:
            raise ValueError("diverge_calls and intents_per_call must be ≥ 1")
        if not self.personas:
            raise ValueError("at least one persona is required")
        if not 0.0 <= self.novelty_min_distance <= 1.0:
            raise ValueError("novelty_min_distance must be in [0, 1]")


def resolve_divergence(divergence: Union[None, bool, Mapping, DivergenceConfig], llm) -> Optional[DivergenceConfig]:
    """The config to run with, or None for the legacy single-call path. `None` = AUTO: on for the library's own
    providers, local or online (`supports_roles`), and for any provider declaring `supports_sampling` — the
    prompt-level techniques help every model, the sampler ones are applied only where honoured (see
    `resolve_sampling`). Duck-typed providers keep their exact previous behaviour. `True` forces the defaults,
    a mapping overrides them."""
    if isinstance(divergence, DivergenceConfig):
        return divergence
    if divergence is None:
        return DivergenceConfig() if (supports_roles(llm) or supports_sampling(llm)) else None
    if divergence is True:
        return DivergenceConfig()
    if divergence is False:
        return None
    if isinstance(divergence, Mapping):
        return DivergenceConfig(**dict(divergence))
    raise TypeError(f"divergence must be None, bool, a mapping or DivergenceConfig, got {type(divergence).__name__}")


def resolve_sampling(config: DivergenceConfig, llm) -> Tuple[DivergenceConfig, Dict]:
    """Fix the sampler options of each phase for THIS provider, and report which levers are real.

    AUTO (None) keeps only the AUTO_DIVERGE_SAMPLING controls the diverge-role provider honours (none for current
    Claude models, top_p for OpenAI, top_p+top_k for Ollama / llama.cpp); an explicit dict is forwarded unchanged
    (call_llm and the provider still drop and report what they cannot take). The report states, per phase, whether
    the provider honours temperature at all — online models that do not still get every prompt-level technique."""
    import dataclasses
    report: Dict = {}
    resolved: Dict = {}
    for phase, role, requested, auto, temperature in (
            ("diverge", "diverge", config.diverge_sampling, AUTO_DIVERGE_SAMPLING, config.diverge_temperature),
            ("converge", "converge", config.converge_sampling, {}, config.converge_temperature)):
        controls = sampler_controls(llm, role)
        if requested is None:
            options = {k: v for k, v in auto.items() if k in controls}
            dropped = sorted(set(auto) - set(options))
        else:
            options, dropped = dict(requested), []
        resolved[phase] = options
        report[phase] = {"temperature": temperature, "temperature_honoured": "temperature" in controls,
                         "options": dict(options), "not_honoured": dropped, "controls": sorted(controls)}
    return dataclasses.replace(config, diverge_sampling=resolved["diverge"],
                               converge_sampling=resolved["converge"]), report


@dataclass
class Intent:
    """One divergent direction: the assumption it breaks and the mechanism that breaking it makes possible."""
    assumption: str
    mechanism: str
    probability: Optional[float] = None         # the model's self-reported typicality (ordering signal only)
    persona: str = ""
    status: str = "PROPOSED"
    reason: str = ""
    novelty: Optional[float] = None             # distance to the nearest denied/known text

    def text(self) -> str:
        return f"{self.assumption} {self.mechanism}".strip()

    def as_dict(self) -> Dict:
        return dict(self.__dict__)


# ── parsing (tolerant: line format first-class, JSON accepted, garbage ignored) ──
_NUM = r"([0-9]*\.?[0-9]+)\s*(%?)"
_INTENT_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)])?\s*INTENT\s*[:\-]\s*(?P<a>.+?)\s*\|\|\s*(?P<m>.+?)"
                        r"(?:\s*\|\|\s*p\s*[=:≈~]?\s*" + _NUM + r")?\s*$", re.IGNORECASE)
_ANSWER_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)])?\s*ANSWER\s*[:\-]\s*(?P<m>.+?)"
                        r"(?:\s*\|\|\s*p\s*[=:≈~]?\s*" + _NUM + r")?\s*$", re.IGNORECASE)


def _probability(raw: Optional[str], percent: str = "") -> Optional[float]:
    """A verbalized probability in [0,1]; '5%' or a bare 5 (read as a percentage) → 0.05; nonsense → None."""
    if raw in (None, ""):
        return None
    try:
        p = float(raw)
    except ValueError:
        return None
    if percent or 1.0 < p <= 100.0:
        p /= 100.0
    return p if 0.0 <= p <= 1.0 else None


def _clean(text: str, limit: int = 300) -> str:
    return " ".join(str(text or "").split()).strip(" .;")[:limit]


def _unmark(line: str) -> str:
    """Drop markdown emphasis chat models wrap labels in (`**INTENT:**`, `__ANSWER__:`, backticks)."""
    return line.replace("**", "").replace("__", "").replace("`", "")


def _strip_reasoning(text: str) -> str:
    from .local_llm import strip_reasoning
    return strip_reasoning(text)


def parse_intents(text: str, persona: str = "", min_words: int = 3) -> List[Intent]:
    """Intents from one divergent completion. Accepts `INTENT: <assumption> || <mechanism> || p=<p>` lines (the
    requested format, optionally numbered/bulleted) or a JSON array of {assumption, mechanism|intent, p}. A
    mechanism shorter than `min_words` words is not a mechanism and is dropped; exact repeats are dropped."""
    body = _strip_reasoning(text)
    out: List[Intent] = []
    for line in body.splitlines():
        m = _INTENT_RE.match(_unmark(line))
        if m:
            out.append(Intent(assumption=_clean(m.group("a"), 120), mechanism=_clean(m.group("m")),
                              probability=_probability(m.group(3), m.group(4) or ""), persona=persona))
    if not out:
        data = _extract_json(body)
        items = data.get("intents", []) if isinstance(data, dict) else data
        for it in items if isinstance(items, list) else []:
            if not isinstance(it, dict):
                continue
            mech = it.get("mechanism") or it.get("intent") or it.get("claim") or ""
            out.append(Intent(assumption=_clean(it.get("assumption") or it.get("broken_assumption") or "", 120),
                              mechanism=_clean(mech), persona=persona,
                              probability=_probability(str(it.get("p", it.get("probability", ""))))))
    seen, kept = set(), []
    for it in out:
        key = it.text().lower()
        if len(it.mechanism.split()) >= min_words and key not in seen:
            seen.add(key)
            kept.append(it)
    return kept


def parse_mode_answers(text: str) -> Tuple[List[str], List[Optional[float]]]:
    """The model's declared default answers: `ANSWER: <mechanism> || p=<p>` lines (numbered/bulleted accepted)."""
    answers: List[str] = []
    probs: List[Optional[float]] = []
    for line in _strip_reasoning(text).splitlines():
        m = _ANSWER_RE.match(_unmark(line))
        mechanism = _clean(m.group("m")) if m else ""
        if mechanism and mechanism.lower() not in {a.lower() for a in answers}:
            answers.append(mechanism)
            probs.append(_probability(m.group(2), m.group(3) or ""))
    return answers, probs


# ── the denial set: everything an intent must be far from ──
@dataclass
class DenialSet:
    """Texts the divergent phase must leave, each with the reason it is denied. Insertion order is priority
    order for the prompt (the declared mode first, then what died, then what is merely known)."""
    items: List[Tuple[str, str]] = field(default_factory=list)       # (label, text)

    def add(self, label: str, texts: Union[str, Iterable[str]]) -> None:
        for text in ([texts] if isinstance(texts, str) else texts):
            t = _clean(text, 200)
            if t and all(t.lower() != x.lower() for _l, x in self.items):
                self.items.append((label, t))

    def prompt_lines(self, limit: int) -> List[str]:
        return [f"  - {t[:140]}  [{label}]" for label, t in self.items[:max(0, limit)]]

    def nearest(self, text: str, embedder=None) -> Tuple[float, str, str]:
        """(distance, label, denied text) of the closest denied item; (1.0, '', '') when nothing is denied."""
        best = (1.0, "", "")
        for label, t in self.items:
            d = float(semantic_distance(text, t, embedder=embedder))
            if d < best[0]:
                best = (d, label, t)
        return best


def build_denial_set(pack, *, mode_answers: Sequence[str] = (), dead: Sequence[str] = (),
                     remembered: Sequence[str] = (), elites: Sequence[str] = ()) -> DenialSet:
    denial = DenialSet()
    denial.add("your default answer", mode_answers)
    denial.add("died in this search", dead)
    denial.add("rejected before (failure memory)", remembered)
    denial.add("known family", list(getattr(pack, "known_families", []) or []))
    denial.add("already archived", elites)
    return denial


# ── prompts ──
def mode_prompt(problem: str, pack, k: int) -> str:
    return "\n".join([
        f"PROBLEM: {problem}",
        f"DOMAIN BOX: {getattr(pack, 'box_name', '') or '—'}",
        f"List the {k} answers you would MOST LIKELY give to this problem — the standard ones a typical expert "
        "proposes first. One concrete mechanism each, with your estimated probability of giving it.",
        "Format, one per line:",
        "ANSWER: <concrete mechanism> || p=<0..1>"])


def diverge_prompt(problem: str, pack, persona: str, denial: DenialSet, k: int, max_denials: int,
                   assumptions: Sequence[str] = ()) -> str:
    lines = [f"PROBLEM: {problem}",
             f"DOMAIN BOX: {getattr(pack, 'box_name', '') or '—'}",
             f"You are {persona}. Look at the problem only through that lens.",
             "FIRST write 3 short OBSERVATIONS about the problem that the standard solutions overlook "
             "(one line each, prefixed 'OBSERVATION:').",
             f"THEN propose {k} INTENTS built on those observations. Each intent breaks ONE hidden assumption and "
             "states, in one sentence, the concrete mechanism that becomes possible once it is broken.",
             f"ASSUMPTIONS YOU MAY BREAK (or name a NEW hidden one): {', '.join(assumptions) or '—'}"]
    denied = denial.prompt_lines(max_denials)
    if denied:
        lines.append("DO NOT USE any of these (already your default answer, already dead, or already known — an "
                     "intent close to any of them is discarded unread):")
        lines += denied
    lines += ["For each intent estimate p = the probability that a typical expert would propose it. Sample from the "
              "TAILS of what you would say: most intents should have p < 0.1.",
              "Format, one per line:",
              "INTENT: <assumption broken> || <mechanism in one sentence> || p=<0..1>",
              "",
              "OBSERVATION:"]
    return "\n".join(lines)


def converge_block(intent: Intent) -> str:
    """The instruction appended to the loop's prompt for one convergent call: develop THIS intent rigorously."""
    return "\n".join([
        "DEVELOP THIS INTENT from the divergent phase — keep its broken assumption, make it rigorous and testable:",
        f"  broken assumption: {intent.assumption or '(name it)'}",
        f"  mechanism: {intent.mechanism}"])


# ── the phase itself ──
def elicit_mode(problem: str, pack, llm, config: DivergenceConfig):
    """Anti-mode (STEP 0) done by the model itself: one cool call for its default answers → a ModeMap.
    Returns (ModeMap or None, calls_made)."""
    from .mode_box import declare_mode
    outs = call_llm(llm, mode_prompt(problem, pack, config.mode_answers), system=_MODE_SYSTEM,
                    temperature=config.converge_temperature, n=1, role="mode", seed=config.seed,
                    **(config.converge_sampling or {}))
    answers, probs = parse_mode_answers(outs[0] if outs else "")
    return (declare_mode(problem, answers, probs) if answers else None), 1


def calibrated_mode_near(mode_map, embedder=None, default: float = 0.55) -> float:
    """The distance under which an idea counts as a VARIANT of the declared mode, calibrated to the embedder.

    mode_box's fixed `near` was tuned for lexical distance, where unrelated sentences sit near 1.0. A semantic
    embedder compresses everything on one topic: measured with nomic-embed-text and bge-m3 on rate limiters,
    paraphrases and variants of the default answers sat at 0.25–0.40 from them and genuinely different mechanisms
    at 0.38–0.52, while the declared answers were 0.23–0.65 apart — so a fixed 0.55 branded every on-topic idea
    a variant. The declared answers give the scale: the two CLOSEST of them (two flavours of one standard mechanism) are
    canonical variants of each other, so an idea nearer to a default than that is at least as much a variant.
    The threshold is min(default, closest pair). Distance alone cannot separate a loose paraphrase from a new
    mechanism in the overlap band; mode_box's structural rules (shared features, component swap) and the later
    prior-art gate cover what it misses. Fewer than two answers → `default`."""
    answers = list(getattr(mode_map, "answers", []) or [])
    if len(answers) < 2:
        return default
    closest = min(float(semantic_distance(a, b, embedder=embedder))
                  for i, a in enumerate(answers) for b in answers[i + 1:])
    return round(min(default, closest), 4)


def niche_key(assumption: str, known: Sequence[str] = ()) -> str:
    """The archive niche an intent belongs to: the pack assumption it names (models write 'breaking
    <assumption> by …'), else its own normalised text — so phrasing does not split one niche into many."""
    text = " ".join(str(assumption or "").lower().split())
    for name in sorted(known, key=len, reverse=True):
        if name and name.lower() in text:
            return name.lower()
    return text


def select_intents(intents: Sequence[Intent], denial: DenialSet, k: int, *, min_distance: float = 0.25,
                   tail_probability: float = 0.35, mode_map=None, mode_near: Optional[float] = None,
                   occupied_assumptions: Iterable[str] = (), assumptions: Sequence[str] = (),
                   embedder=None) -> List[Intent]:
    """Filter and pick up to `k` intents; every intent gets a status. Rejected, judged on the mechanism: near a
    denied text (REJECTED_NEAR_KNOWN), an echo/variant of the declared mode (REJECTED_MODE, judged with
    `mode_near` — by default `calibrated_mode_near`), or a duplicate of an earlier survivor
    (REJECTED_DUPLICATE). Survivors are
    ranked tail-first (self-reported p ≤ `tail_probability`, lower p first, then farther from the denial set) and
    picked ROUND-ROBIN across distinct niches (`niche_key` over the pack `assumptions`), niches that do not yet own
    an archive cell first — breadth before depth."""
    from .mode_box import mode_distance, MODE_ECHO, NEAR_MODE
    if mode_map is not None and mode_near is None:
        mode_near = calibrated_mode_near(mode_map, embedder)
    survivors: List[Intent] = []
    # novelty and duplication are judged on the MECHANISM only: the assumption is the niche (handled by the
    # round-robin below), and a shared 'break <assumption> …' prefix made distinct mechanisms read as duplicates.
    for it in intents:
        d, label, near = denial.nearest(it.mechanism, embedder)
        it.novelty = round(d, 4)
        if d < min_distance:
            it.status, it.reason = f"REJECTED_{NEAR_KNOWN}", f"d={d:.2f} from {label} «{near[:60]}»"
            continue
        if mode_map is not None and mode_map.answers:
            md = mode_distance(it.mechanism, mode_map, embedder=embedder, near=mode_near)
            if md.verdict in (MODE_ECHO, NEAR_MODE):
                it.status, it.reason = f"REJECTED_{MODE_ECHO_KIND}", f"{md.verdict}: {md.reason}"
                continue
        twin = next((s for s in survivors
                     if float(semantic_distance(it.mechanism, s.mechanism, embedder=embedder)) < min_distance), None)
        if twin is not None:
            it.status, it.reason = f"REJECTED_{DUPLICATE}", f"duplicate of «{twin.mechanism[:60]}»"
            continue
        survivors.append(it)

    occupied = {niche_key(a, assumptions) for a in occupied_assumptions}

    def rank(it: Intent):
        p = it.probability if it.probability is not None else 0.5
        return (p > tail_probability, p, -(it.novelty or 0.0))
    by_assumption: Dict[str, List[Intent]] = {}
    for it in sorted(survivors, key=rank):
        by_assumption.setdefault(niche_key(it.assumption, assumptions), []).append(it)
    queues = sorted(by_assumption.items(), key=lambda kv: (kv[0] in occupied, rank(kv[1][0])))
    selected: List[Intent] = []
    while len(selected) < k and any(q for _a, q in queues):
        for _a, q in queues:
            if q and len(selected) < k:
                selected.append(q.pop(0))
    for it in survivors:
        it.status = SELECTED if it in selected else SURPLUS
    return selected


@dataclass
class DivergenceRound:
    intents: List[Intent] = field(default_factory=list)
    selected: List[Intent] = field(default_factory=list)
    calls: int = 0
    personas: List[str] = field(default_factory=list)


def diverge_round(problem: str, pack, llm, config: DivergenceConfig, denial: DenialSet, *, round_index: int,
                  k: int, mode_map=None, mode_near: Optional[float] = None, occupied_assumptions: Iterable[str] = (),
                  assumptions: Sequence[str] = (), embedder=None) -> DivergenceRound:
    """One divergent round: `config.diverge_calls` INDEPENDENT hot calls (fresh context, distinct persona,
    distinct seed), parsed into intents, then filtered and selected (see `select_intents`)."""
    out = DivergenceRound()
    n_personas = len(config.personas)
    for i in range(config.diverge_calls):
        persona = config.personas[(round_index * config.diverge_calls + i) % n_personas]
        seed = None if config.seed is None else config.seed + 1000 * (round_index + 1) + i
        prompt = diverge_prompt(problem, pack, persona, denial, config.intents_per_call,
                                config.max_denials_in_prompt, assumptions)
        outs = call_llm(llm, prompt, system=_DIVERGE_SYSTEM, temperature=config.diverge_temperature, n=1,
                        role="diverge", seed=seed, **(config.diverge_sampling or {}))
        out.calls += 1
        out.personas.append(persona)
        for comp in outs:
            out.intents += parse_intents(comp, persona=persona)
    out.selected = select_intents(out.intents, denial, k, min_distance=config.novelty_min_distance,
                                  tail_probability=config.tail_probability, mode_map=mode_map,
                                  mode_near=mode_near, occupied_assumptions=occupied_assumptions,
                                  assumptions=assumptions, embedder=embedder)
    return out


def mean_pairwise_distance(texts: Sequence[str], embedder=None) -> Optional[float]:
    """Mean semantic distance over all pairs — the spread of a set of ideas (None for fewer than two)."""
    texts = [t for t in texts if str(t or "").strip()]
    if len(texts) < 2:
        return None
    pairs = [(a, b) for i, a in enumerate(texts) for b in texts[i + 1:]]
    return round(sum(float(semantic_distance(a, b, embedder=embedder)) for a, b in pairs) / len(pairs), 4)
