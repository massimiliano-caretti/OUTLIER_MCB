"""judge — discipline the LLM's OWN idea. The missing half of the thesis.

OUTLIER_MCB's thesis is "the spark is human, the rigor is the machine's" — but every other entrypoint
generates the engine's OWN candidates from a pack. There was no way to take the assistant's actual
free-text proposal and run the rigor on IT. `judge(idea, …)` closes the loop: it turns a free-text idea
into a Candidate, infers which assumption it breaks, then threads the existing machinery — the
no-solution gate, the full dossier (theorem · world-test · reviewer · lineage · maturity), grounding,
and the honest AUTO/HUMAN verifiability — into one verdict the assistant can act on.

Pairs with `creative()`: creative says "break THIS assumption"; judge says "here is MY idea — is it
genuinely new, and does it survive?". Together they are the human–machine loop.

Collaborators: pack (routing), kernel.no_solution_before_assumption, dossier, repo_world, verifier.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional

from .generators import Candidate

_NEW_OUTPUT_HINTS = ("output", "predict", "score", "detect", "verify", "rank", "flag", "estimate", "explain")
_STOP = {"the", "a", "an", "of", "to", "is", "are", "be", "by", "for", "on", "in", "and", "or", "as",
         "it", "this", "that", "with", "not", "can", "could", "should", "make", "new", "use", "via"}


def _rank_assumptions(idea: str, pack):
    """Rank the pack's assumptions by word overlap with the idea. Returns [(name, score)] best-first."""
    words = {w for w in "".join(c if c.isalnum() else " " for c in idea.lower()).split()
             if len(w) > 3 and w not in _STOP}
    scored = []
    for a in pack.assumptions:
        text = f"{a.name} {a.description} {a.if_false}".lower()
        scored.append((a.name, sum(1 for w in words if w in text)))
    return sorted(scored, key=lambda kv: -kv[1])


def _infer(idea: str, pack):
    """Infer the broken assumption WITH evidence: (name|None, confidence[0,1], ambiguous_names, ranking).
    Lexical overlap is fragile, so judge() must REFUSE to anchor when confidence is low or ambiguous."""
    ranked = _rank_assumptions(idea, pack)
    if not ranked or ranked[0][1] == 0:
        return None, 0.0, [], ranked
    top = ranked[0][1]
    second = ranked[1][1] if len(ranked) > 1 else 0
    # (Audit finding #13 proposed requiring a wider margin / >=3 word-matches before anchoring; but the eval
    # suite deliberately anchors legitimate AUDIT ideas whose top assumption wins by a single word — e.g.
    # judge_audit_002 (top=2, second=1) MUST map to a broken assumption. The dossier is provisional and the
    # ambiguity guard already fires on an exact tie, so the thin-overlap anchor is intentional. Left as-is.)
    confidence = round(top / (top + 2) * (1.0 if top > second else 0.5), 2)   # damped by a near-tie
    ambiguous = [n for n, s in ranked if s == top] if top == second else []
    return (ranked[0][0] if confidence >= 0.34 and not ambiguous else None), confidence, ambiguous, ranked


@dataclass
class Judgment:
    idea: str
    verdict: str                 # INSIDE_THE_BOX | MUST_BE_AUDITED | NEEDS_DISAMBIGUATION
    status: str                  # the maturity status (alive / suspended / dead)
    verifiability: str           # AUTO (engine can settle by running) | HUMAN (must be built/judged)
    broken_assumption: Optional[str]
    dossier: object
    gate: dict
    next_step: str
    confidence: float = 0.0          # how sure the assumption mapping is, in [0,1]
    ambiguous_assumptions: List[str] = None   # near-tied candidates when the mapping is unclear
    evidence: List = None            # the ranked (assumption, overlap) evidence behind the mapping
    evidence_terms: List = None      # the idea words that drove the mapping
    requires_human_confirmation: bool = False  # True when the mapping is too weak to trust unaided
    novelty: object = None           # a NoveltyVerdict from a real-world prior-art search (when a provider is given)
    first_principles: object = None  # a FirstPrinciplesCritique (only when first_principles=True is requested)
    testability_request: object = None  # a MissingInfoReport: the path OUT of SUSPENDED_BOLD (signal boost)
    repo_grounding: object = None    # #7: AST impact surface + file-anchored falsifiers (when repo_path given)
    closure: object = None           # FIX A: universal-closure membership when the pack declares closures
    barrier: object = None           # F2: a BarrierVerdict when a no-go theorem kills the idea's route (DEAD_BY_BARRIER)
    def markdown(self) -> str:
        head = [f"# Judgment — «{self.idea}»",
                f"**verdict: {self.verdict}** · maturity: {self.status} · verifiability: {self.verifiability}",
                f"breaks: {self.broken_assumption or '— (unmapped)'}  (confidence {self.confidence})",
                (f"ambiguous between: {', '.join(self.ambiguous_assumptions)}" if self.ambiguous_assumptions else ""),
                f"**next step:** {self.next_step}"]
        body = "\n".join(x for x in head if x) + "\n\n" + self.dossier.markdown()
        if self.testability_request is not None:
            body += "\n\n" + self.testability_request.markdown()
        if self.first_principles is not None:
            body += "\n\n" + self.first_principles.markdown()
        return body


def judge(idea: str, prompt: str = "", pack=None, repo_path: Optional[str] = None,
          assumption: str = "", breaks: Optional[List[str]] = None, provider=None,
          first_principles: bool = False) -> Judgment:
    """Run the full rigor on a free-text idea the assistant proposes. Returns a single, actionable verdict.

    `first_principles=True` additionally attaches a FirstPrinciplesCritique — falsifiable objections derived
    from the claim's own logic (universals, comparatives, scale, robustness), which the pack-bound reviewer
    cannot raise on an axis it does not model. Opt-in: off by default, so the standard verdict is unchanged."""
    from .pack import select_pack, get_pack
    from .kernel import no_solution_before_assumption
    from .dossier import dossier as build_dossier
    from .repo_world import compile_world_test
    from .verifier import verifiability_class

    the_pack = pack if pack is not None else (select_pack(prompt or idea)[0])
    if isinstance(the_pack, str):
        the_pack = get_pack(the_pack)

    inferred, confidence, ambiguous, ranking = _infer(idea, the_pack)
    asm = assumption or inferred or ""
    if assumption:
        confidence, ambiguous = 1.0, []          # caller override is certain
    axis = the_pack.dimension_of.get(asm, "") if asm else ""
    has_new_output = any(h in idea.lower() for h in _NEW_OUTPUT_HINTS)
    broke = [axis] if axis else (breaks or [])

    cand = Candidate(name=idea[:48], operator="proposed",
                     breaks=broke, assumptions=([asm] if asm else []),
                     negation=idea, needs=[], discipline="a human-proposed idea — the engine only disciplines it")

    # the gate: the transparent record of the SAME contract the verdict enforces — an idea is inside the box
    # unless it breaks an assumption OR yields a new output. We synthesize the answers to mirror that OR (a
    # broken assumption satisfies the world-test / new-output requirement), so the returned gate is consistent
    # with the verdict and never contradicts it (it previously could: asm present but no new-output hint).
    answers = {"breaks_assumption": asm, "family_that_cannot": (the_pack.known_families[0] if asm and the_pack.known_families else ""),
               "new_output": ("a verifiable new output" if (has_new_output or asm) else ""),
               "world_test": ("the constructed world where the box fails" if (asm or has_new_output) else "")}
    gate = no_solution_before_assumption(idea, answers=answers, pack=the_pack)

    repo = None
    repo_grounding = None
    if repo_path is not None:
        from .grounding import probe
        repo = probe(repo_path)
        # #7: a SEMANTIC repo model — where the idea would actually land + file-anchored RED falsifiers.
        try:
            import os
            from .repo_semantics import repo_world_model, impact_surface, suggest_repo_falsifiers
            if isinstance(repo_path, str) and os.path.isdir(repo_path):
                model = repo_world_model(repo_path)
                surface = impact_surface(idea, model)
                repo_grounding = {"grounded": surface["grounded"], "impact_surface": surface,
                                  "falsifiers": suggest_repo_falsifiers(idea, model),
                                  "untested_modules": model.modules_without_tests()[:10]}
        except Exception:
            repo_grounding = None
    doss = build_dossier(cand, the_pack, repo=repo)
    check = compile_world_test(idea, axis, repo=repo)
    vclass = verifiability_class(check)

    if not assumption and ambiguous:
        verdict = "NEEDS_DISAMBIGUATION"
        next_step = (f"your idea maps near-equally to: {', '.join(ambiguous)}. Re-run with assumption='<one of them>' "
                     "— the engine will NOT anchor a low-confidence guess and start the whole dossier wrong.")
    elif not broke:
        # breaks NO assumption → INSIDE_THE_BOX, regardless of an incidental output-verb in the text. A crude
        # keyword ('predict'/'score'/'detect'…) must NOT promote a no-break idea to MUST_BE_AUDITED — that would
        # contradict the contract ("name the assumption it breaks") and the internal no-solution gate.
        verdict = "INSIDE_THE_BOX"
        next_step = ("name the hidden assumption your idea breaks (or the new output it produces). "
                     "Without that it is a re-skin of the box — not yet an answer.")
    else:
        verdict = "MUST_BE_AUDITED"
        next_step = (f"build the world-test and run `{check.command}` — the repo settles it."
                     if vclass == "AUTO" else
                     "this is a HUMAN-class claim: BUILD the world its falsifier describes and judge it — "
                     "the engine will NOT claim to have verified it.")

    # FIX A: closure-membership gate — if the idea reduces to a declared universal closure, it is INSIDE_THE_BOX
    # no matter how different it looks from a single member (the MIL/DeepSets failure). Additive: a no-op unless
    # the pack declares `universal_closures`.
    closure = None
    if getattr(the_pack, "universal_closures", None):
        from .closures import closure_membership
        closure = closure_membership(idea, the_pack)
        if closure["verdict"] == "INSIDE_THE_BOX":
            verdict = "INSIDE_THE_BOX"
            next_step = (f"INSIDE the universal closure «{closure['inside_closure']}» — do NOT propose another "
                         f"member. Take an admissible EXIT instead: {', '.join(closure['exits'])}.")

    # F2: barrier gate — a no-go theorem (e.g. the parity problem) kills the idea's ROUTE as already-dead and
    # names the only admissible exits. Additive: fires only for packs a barrier declares it applies to.
    barrier = None
    from .barriers import barrier_membership, DEAD_BY_BARRIER
    barrier = barrier_membership(idea, the_pack)
    if barrier is not None and barrier.status == DEAD_BY_BARRIER:
        verdict = "DEAD_BY_BARRIER"
        next_step = (f"DEAD BY BARRIER «{barrier.barrier}» ({barrier.citation}): {barrier.reason} "
                     f"Do NOT pursue this route — take an admissible EXIT: {', '.join(barrier.exits)}.")

    terms = sorted({w for w in "".join(ch if ch.isalnum() else " " for ch in idea.lower()).split()
                    if len(w) > 3 and w not in _STOP})

    # real-world novelty check: does this already exist (renamed / recombined)? Only when a provider is given.
    novelty = None
    if provider is not None:
        from .novelty import prior_art_audit
        try:
            novelty = prior_art_audit(idea, provider, pack=the_pack)
            if novelty.status in ("RENAMED", "COLLAGE"):
                next_step = (f"prior art found — {novelty.why} Break a FURTHER assumption to escape it "
                             f"(or admit it is not new). " + next_step)
            elif novelty.status == "NO_PRIOR_ART_FOUND":
                scoped = novelty.scoped_verdict() if novelty.novelty_scope else (novelty.graded_verdict or novelty.status)
                scope = novelty.novelty_scope or "UNSCOPED_PROVIDER"
                if scoped in ("LOCAL_ONLY_NOVELTY", "PRIOR_ART_INCOMPLETE") or scope != "ONLINE_PRIOR_ART_CHECKED":
                    next_step = (next_step + f" (No close prior art found, but scope={scope}: "
                                 "treat as weak/provisional only; run real online sources before claiming novelty.)")
                else:
                    next_step = (next_step + f" (No prior art found — {scoped}, "
                                 "still provisional and bounded to checked sources.)")
        except Exception:
            novelty = None     # a failed search must not block the verdict

    # signal boost: a SUSPENDED_BOLD idea (breaks an axis but has no executable world-test yet) gets a
    # concrete path forward — the specific CRITICAL information that would make it falsifiable.
    testability = None
    if doss.maturity.status == "SUSPENDED_BOLD":
        from .missing_info import detect_missing_information
        mi = detect_missing_information(idea, the_pack)
        crit = mi.by_criticality("CRITICAL") or mi.needed_information
        if crit:
            names = ", ".join(d["kind"] for d in crit[:3])
            # signal boost: replace the generic 'build a world-test' note with the SPECIFIC data to gather.
            doss.maturity.what_would_make_it_testable = f"gather the CRITICAL information: {names} — {crit[0]['why']}"
            next_step = next_step + f" · SIGNAL-BOOST: to make it falsifiable, gather {names}."
            testability = mi

    fp = None
    if first_principles:
        from .first_principles_reviewer import first_principles_attack
        fp = first_principles_attack(idea, claim=idea, breaks=broke)

    return Judgment(idea=idea, verdict=verdict, status=doss.maturity.status, verifiability=vclass,
                    broken_assumption=(asm or None), dossier=doss, gate=gate, next_step=next_step,
                    confidence=confidence, ambiguous_assumptions=ambiguous, evidence=ranking[:5],
                    evidence_terms=terms[:8],
                    requires_human_confirmation=bool(not assumption and (confidence < 0.34 or ambiguous)),
                    novelty=novelty, first_principles=fp, testability_request=testability,
                    repo_grounding=repo_grounding, closure=closure, barrier=barrier)
