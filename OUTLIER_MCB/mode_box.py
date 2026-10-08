"""mode_box — make the model's OWN average answer the box it must leave.

Every other entrypoint names the box abstractly ("the most-probable solution from training memory"). For a
request outside the built-in packs that box is the SAME for every prompt (the generic pack's four axes), so the
brief cannot tell "a new way to teach fractions" from "a new sorting algorithm". But the box is not abstract: it
is whatever the assistant would answer if left alone — and the assistant can simply SAY it.

The anti-mode protocol:
  1. the model writes its K most-likely answers to the request, each with a verbalized probability
     (Verbalized Sampling, Zhang et al. 2025, arXiv:2510.01171 — verbalizing the distribution exposes the mode);
  2. `declare_mode` mines the features those typical answers SHARE (terms recurring across a quorum of them,
     minus the words of the request itself — those are given, not assumed). Shared features are the hidden
     assumptions of THIS request's box, request-specific instead of generic;
  3. `mode_pack` turns them into a DomainPack (one axis per feature, priority = how central to the mode), so the
     whole kernel — preflight, divergence, judge — now breaks THIS box rather than a generic one;
  4. `mode_distance` gates any later idea: an idea that keeps every central shared feature, or sits close to a
     declared typical answer, is a MODE_ECHO (INSIDE_THE_BOX) however novel its wording.

Honesty: this is an integration of known parts (verbalized sampling + de Bono assumption reversal + a distance
gate), not a new method. The verbalized probabilities are the model's self-report and are NOT evidence of novelty;
leaving the mode is necessary, never sufficient — the world-test and the prior-art audit still decide.
"""
from __future__ import annotations
import math
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from .core import Assumption
from .embeddings import _stem, default_embedder

# EN + IT function words: never a feature of a solution (the public contract is bilingual).
_STOP = set("""
a an the of to in on for and or but with without by from as at is are be been being was were it its this that
these those there their they them we you your our can could should would will may might must do does done using
use used via into over under than then so such each every any all some more most less very just also not no
new novel better best way ways approach approaches method methods solution solutions idea ideas based make
il lo la i gli le un uno una di del della dei degli delle da dal dalla in nel nella con su per tra fra e ed o
che chi cui non si sono è era essere ha hanno come più meno molto anche ogni tutto tutti questo questa quello
quella nuovo nuova nuovi nuove modo metodo soluzione idea usare usando migliore
""".split())
_WORD = re.compile(r"[^\W_]+", re.UNICODE)

MODE_ECHO, NEAR_MODE, TAIL, UNDECLARED = "MODE_ECHO", "NEAR_MODE", "TAIL", "MODE_UNDECLARED"
MODE_VERDICTS = (MODE_ECHO, NEAR_MODE, TAIL, UNDECLARED)


def _content(text: str) -> List[str]:
    """Content words of a text, lower-cased, stop-words and very short tokens removed (order kept)."""
    return [w for w in _WORD.findall(str(text or "").lower()) if len(w) > 2 and w not in _STOP and not w.isdigit()]


def _features(text: str) -> Dict[str, str]:
    """stem → surface form, for unigrams and for bigrams of words ADJACENT in the original text ('token bucket'
    is one idea; 'bucket per client' does not make 'bucket client' a feature)."""
    raw = [w for w in _WORD.findall(str(text or "").lower())]
    ok = [len(w) > 2 and w not in _STOP and not w.isdigit() for w in raw]
    out: Dict[str, str] = {}
    for w, good in zip(raw, ok):
        if good:
            out.setdefault(_stem(w), w)
    for i in range(len(raw) - 1):
        if ok[i] and ok[i + 1]:
            out.setdefault(_stem(raw[i]) + "_" + _stem(raw[i + 1]), f"{raw[i]} {raw[i + 1]}")
    return out


def _slug(stem: str) -> str:
    return re.sub(r"\W+", "_", stem).strip("_") or "feature"


@dataclass
class ModeMap:
    """The declared mode of the model's distribution for one request, and the box it implies."""
    prompt: str
    answers: List[str]
    probabilities: List[Optional[float]]
    support: Dict[str, int]                     # feature stem → how many typical answers contain it
    surface: Dict[str, str]                     # feature stem → a readable surface form
    shared: List[str]                           # stems shared by a quorum of answers, most central first
    quorum: int
    weak: bool = False                          # True when < 2 answers were declared (no real 'sharing' to mine)
    warnings: List[str] = field(default_factory=list)

    def shared_surface(self) -> List[str]:
        return [self.surface[s] for s in self.shared]

    def as_dict(self) -> Dict:
        return {"prompt": self.prompt, "answers": list(self.answers), "probabilities": list(self.probabilities),
                "shared_features": self.shared_surface(), "support": {self.surface[s]: self.support[s] for s in self.shared},
                "quorum": self.quorum, "weak": self.weak, "warnings": list(self.warnings)}

    def markdown(self) -> str:
        lines = [f"# Declared mode — «{self.prompt}»",
                 f"{len(self.answers)} typical answers declared · quorum {self.quorum}" + (" · WEAK (declare ≥3)" if self.weak else "")]
        for i, a in enumerate(self.answers):
            p = self.probabilities[i] if i < len(self.probabilities) else None
            lines.append(f"  {i + 1}. {a}" + (f"  (p≈{p:.2f})" if isinstance(p, (int, float)) else ""))
        lines.append("**the box (features the typical answers share):** "
                     + (", ".join(f"{self.surface[s]}×{self.support[s]}" for s in self.shared) or "— none shared"))
        lines += [f"- ⚠ {w}" for w in self.warnings]
        return "\n".join(lines)


def declare_mode(prompt: str, answers: Sequence[str], probabilities: Optional[Sequence[Optional[float]]] = None,
                 quorum: float = 0.5, max_features: int = 8) -> ModeMap:
    """Mine the box from the model's own typical answers. A feature is SHARED when at least
    max(2, ceil(quorum·K)) of the K answers contain it; words of the request itself are excluded (they are the
    problem, not an assumption about its solution). Ranked by support, then bigrams before unigrams (more
    specific), then alphabetically — deterministic."""
    answers = [str(a).strip() for a in (answers or []) if str(a or "").strip()]
    probs = list(probabilities or [])
    n = len(answers)
    warnings: List[str] = []
    prompt_stems = {_stem(w) for w in _content(prompt)}
    support: Dict[str, int] = {}
    surface: Dict[str, str] = {}
    for a in answers:
        for st, sf in _features(a).items():
            if any(part in prompt_stems for part in st.split("_")) and "_" not in st:
                continue                                   # a request word is given, not assumed
            support[st] = support.get(st, 0) + 1
            surface.setdefault(st, sf)
    weak = n < 2
    need = 1 if weak else max(2, math.ceil(quorum * n))
    shared = sorted((s for s, c in support.items() if c >= need),
                    key=lambda s: (-support[s], 0 if "_" in s else 1, s))
    # a bigram subsumes its unigrams at equal support: keep 'token bucket', drop the redundant 'token'/'bucket'
    keep: List[str] = []
    for s in shared:
        if "_" not in s and any(s in b.split("_") and support[b] == support[s] for b in shared if "_" in b):
            continue
        keep.append(s)
    shared = keep[:max_features]
    if weak:
        warnings.append("fewer than 2 typical answers: nothing is 'shared' — the box is just one answer's words.")
    if n >= 2 and not shared:
        warnings.append("the typical answers share no feature — either the mode is already diverse, or the answers "
                        "are too short; restate each as one concrete mechanism.")
    numeric = [p for p in probs if isinstance(p, (int, float))]
    if numeric and any(p < 0 or p > 1 for p in numeric):
        warnings.append("verbalized probabilities outside [0,1] — they are a self-report, treated as ordering only.")
    if n >= 2 and numeric and max(numeric) < 0.15:
        warnings.append("every declared answer has low probability: these may not be the mode — state what you "
                        "would answer by DEFAULT, not what sounds original.")
    return ModeMap(prompt=prompt or "", answers=answers, probabilities=probs, support=support, surface=surface,
                   shared=shared, quorum=need, weak=weak, warnings=warnings)


def mode_pack(mode: ModeMap, name: Optional[str] = None, base_pack=None):
    """A request-specific DomainPack whose assumptions are the mode's shared features, one axis each (priority 3 for
    a feature every answer shares, 2 for a majority, 1 otherwise), so the kernel's distinct-axis divergence proposes
    breaks of DIFFERENT features. The typical answers become the known families to collide against. When a
    `base_pack` is given its assumptions/axes are kept too (the mode only adds request-specific ones)."""
    from .pack import DomainPack
    n = max(1, len(mode.answers))
    assumptions, dim, axes = [], {}, {}
    for s in mode.shared:
        f, c = mode.surface[s], mode.support[s]
        aname, axis = f"relies_on_{_slug(f)}", f"MODE:{_slug(f).upper()}"
        assumptions.append(Assumption(
            aname, f"The solution relies on '{f}' ({c}/{n} typical answers do).",
            "it is what the model answers by default — the mode of its distribution.",
            f"a solution that works with NO '{f}' — remove it, invert it, or make it the output instead of the means.",
            list(mode.answers[:3]),
            f"a typical answer and the new idea differ ONLY in '{f}', and the new idea wins on the world-test."))
        dim[aname] = axis
        axes[axis] = {"priority": 3 if c >= n else (2 if c * 2 > n else 1),
                      "verdict": f"'{f}' is shared by {c}/{n} of the model's default answers."}
    families = [a[:80] for a in mode.answers]
    if base_pack is not None:
        assumptions = list(base_pack.assumptions) + assumptions
        dim = {**base_pack.dimension_of, **dim}
        axes = {**base_pack.axes, **axes}
        families = list(base_pack.known_families) + families
    return DomainPack(
        name=name or "mode:" + (_slug("_".join(_content(mode.prompt)[:4])) or "request"),
        keywords=[], box_name="the model's own declared default answers: " + "; ".join(a[:60] for a in mode.answers[:3]),
        assumptions=assumptions, relations=list(getattr(base_pack, "relations", []) or []),
        dimension_of=dim, box_assumptions=set(dim), axes=axes, known_families=families,
        info_kinds=dict(getattr(base_pack, "info_kinds", {}) or {}) or
        {"new_observable": "a quantity none of the typical answers measures."},
        failure_memory=dict(getattr(base_pack, "failure_memory", {}) or {}),
        universal_closures=list(getattr(base_pack, "universal_closures", []) or []))


@dataclass
class ModeDistance:
    idea: str
    verdict: str                     # MODE_ECHO | NEAR_MODE | TAIL | MODE_UNDECLARED
    nearest_answer: str
    min_distance: float              # semantic distance to the nearest declared typical answer, in [0,1]
    kept: List[str]                  # shared features the idea still relies on
    broken: List[str]                # shared features the idea drops
    reason: str

    def as_dict(self) -> Dict:
        return dict(self.__dict__)


def mode_distance(idea: str, mode: ModeMap, embedder=None, near: float = 0.55) -> ModeDistance:
    """Is `idea` a way out of the declared mode, or an echo of it?

    MODE_ECHO — it keeps EVERY central shared feature (or is near-identical to a typical answer): inside the box,
                however it is phrased. NEAR_MODE — it drops some feature but stays within `near` of a typical answer
                (a variant of the default). TAIL — it breaks ≥1 shared feature AND is far from every typical answer.
    TAIL is a precondition for novelty, never a certificate of it."""
    emb = embedder if embedder is not None else default_embedder()
    feats = _features(idea)
    stems = {p for s in feats for p in s.split("_")}
    has = {s: all(p in stems for p in s.split("_")) for s in mode.shared}   # 'bucket of tokens' keeps 'token bucket'
    kept = [mode.surface[s] for s in mode.shared if has[s]]
    broken = [mode.surface[s] for s in mode.shared if not has[s]]
    if mode.answers:
        dists = [(round(float(emb.distance(idea, a)), 4), a) for a in mode.answers]
        d, nearest = min(dists, key=lambda t: t[0])
    else:
        d, nearest = 1.0, ""
    # a COMPONENT SWAP of one typical answer (redis→memcached, client→user) fools a lexical distance; catch it
    # structurally: the idea reuses a typical answer's named mechanism (an adjacent bigram) or at least half of its words.
    swap = ""
    for a in mode.answers:
        fa = _features(a)
        uni = {x for x in fa if "_" not in x}
        reused = [fa[x] for x in fa if "_" in x and x in feats]
        frac = len(uni & set(feats)) / len(uni) if uni else 0.0
        if reused or frac >= 0.5:
            swap = (f"reuses «{reused[0]}» of «{a[:50]}»" if reused else
                    f"shares {round(frac * 100)}% of the words of «{a[:50]}»")
            break
    if not mode.answers:
        verdict, why = UNDECLARED, "no typical answer declared — nothing to be far FROM; declare the mode first (anti_mode_protocol)"
    elif d <= 0.15 or (mode.shared and not broken):
        verdict = MODE_ECHO
        why = ("near-identical to a declared typical answer" if d <= 0.15 else
               f"still relies on every shared feature of the mode ({', '.join(kept)})")
    elif d < near or swap:
        verdict = NEAR_MODE
        why = (f"drops {', '.join(broken) or 'nothing'} but " +
               (f"is a component swap: it {swap}" if swap else f"stays close (d={d}) to «{nearest[:60]}»"))
    else:
        verdict = TAIL
        why = f"breaks {', '.join(broken)} and is far (d={d}) from every typical answer"
    return ModeDistance(idea=idea, verdict=verdict, nearest_answer=nearest, min_distance=d,
                        kept=kept, broken=broken, reason=why)


def anti_mode_protocol(prompt: str, k: int = 5) -> str:
    """Step 1 of the protocol, to paste in front of the model BEFORE it answers: verbalize the mode first."""
    return "\n".join([
        "[OUTLIER_MCB anti-mode — step 1: make your default answer EXPLICIT before trying to leave it]",
        f"EN: Write the {k} answers you would most likely give to the request below, each ONE concrete mechanism in",
        "    one line, with your honest probability of giving it by default (Verbalized Sampling). Do NOT try to be",
        "    original here — this is the box, and you can only leave a box you have named.",
        f"IT: Scrivi le {k} risposte che daresti più probabilmente, ciascuna UN meccanismo concreto in una riga, con la",
        "    probabilità onesta di darla di default. NON cercare l'originalità qui: questa è la scatola da cui uscire.",
        f"request: {prompt}",
        "then: print(m.mode_brief(request, [answer_1, ...], [p_1, ...]))",
    ])


def mode_brief(prompt: str, answers: Sequence[str], probabilities: Optional[Sequence[Optional[float]]] = None,
               k: int = 3, base_pack=None) -> str:
    """Step 2: the request-specific brief. The box = the model's declared mode; the breaks = its shared features,
    one per axis; the gate = `mode_distance` (every final idea must be TAIL, then survive a world-test)."""
    from . import kernel
    mode = declare_mode(prompt, answers, probabilities)
    out = [mode.markdown(), ""]
    if not mode.shared:
        out.append("No shared feature to break — re-declare the mode with ≥3 one-line concrete mechanisms, or fall "
                   "back to m.creative(request).")
        return "\n".join(out)
    pack = mode_pack(mode, base_pack=base_pack)
    out.append("[anti-mode breaks — each removes a DIFFERENT feature your default answers rely on]")
    for b in kernel.branch_on_assumptions(prompt, pack, k=k):
        out.append(f"  [{b['stance']:11s}] {b['assumption']} → {b['negation']}")
    out += ["",
            "[rules]",
            "  1. Every idea you finally propose must be TAIL: m.mode_distance(idea, m.declare_mode(request, answers)).",
            "     MODE_ECHO / NEAR_MODE = a variant of your default answer → INSIDE_THE_BOX, not an answer.",
            "  2. For each TAIL idea name the feature it drops and the world-test where the typical answer FAILS and",
            "     the idea wins; then run m.judge(idea, prompt=request, mode=answers) and m.novelty_audit(...).",
            "  3. A low verbalized probability is not novelty — only the world-test and prior art decide.",
            "  4. If every break is impossible, say which NEW information would make one possible."]
    return "\n".join(out)
