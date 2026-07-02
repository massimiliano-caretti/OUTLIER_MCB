"""language_inventor — invent a new FORMAL LANGUAGE when the existing ones express a class of solutions too
verbosely (Point 3). Not a full EBNF+compiler generated from thin air (that is a research programme, and an
offline version would be theatre) — the honest, buildable CORE: invent a compact PRIMITIVE SET (a mini-DSL)
with a REAL interpreter, by ABSTRACTING a recurring sub-computation shared across the solutions of a problem
family into a new named primitive (DreamCoder-style library learning). A new word in the language earns its
place only if it shortens real solutions AND the interpreter stays SOUND.

The external Pareto dimension is EXPRESSIVE_POWER: the ratio of the total solution length in the baseline
language to the total solution length in the invented one, on a fixed problem family (> 1 ⇒ a real expressive
gain). Controls: a language that merely renames the baseline scores 1 (no gain); a language that cannot solve a
problem scores 0. The protected invariant is SOUNDNESS: the interpreter must run test programs and match
precomputed expected outputs — the engine cannot invent a language that does not actually compute.

Deterministic, zero-dependency. A 'program' is a pipeline of primitive names applied left-to-right to an input.
"""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

Program = Tuple[str, ...]


@dataclass
class FormalLanguage:
    """A mini-DSL: named primitive operations + a real interpreter (run_program). Its grammar is 'a pipeline of
    primitives'; its compiler is the fold below — small, but genuinely executable and checkable."""
    name: str
    primitives: Dict[str, Callable]
    macros: Dict[str, Program] = field(default_factory=dict)   # invented words → their expansion in base primitives

    def run(self, program: Sequence[str], x):
        """Interpret a program on input x, left-to-right. An invented macro expands to its base primitives."""
        val = x
        for tok in program:
            if tok in self.macros:
                val = self.run(self.macros[tok], val)
            elif tok in self.primitives:
                val = self.primitives[tok](val)
            else:
                raise KeyError(f"unknown primitive '{tok}' in language '{self.name}'")
        return val

    def vocabulary(self) -> List[str]:
        return sorted(list(self.primitives) + list(self.macros))


def _solves(language: FormalLanguage, program: Program, cases: Sequence[Tuple]) -> bool:
    try:
        return all(language.run(program, x) == y for x, y in cases)
    except Exception:
        return False


def shortest_program(language: FormalLanguage, cases: Sequence[Tuple], max_len: int = 5) -> Optional[Program]:
    """BFS for the SHORTEST program (fewest tokens) that maps every case input→output. Deterministic (vocabulary
    sorted). Returns None if none exists within max_len — that is how a language 'cannot solve' (score 0)."""
    # BUGFIX: a clean level-order BFS. It checks EVERY program of length `depth` (starting at 0 — the empty
    # identity pipeline) before growing to depth+1, and stops after depth == max_len, so it (a) returns the truly
    # shortest solution, (b) can return the empty program, and (c) never overshoots the documented max_len bound.
    vocab = language.vocabulary()
    frontier: List[Program] = [()]
    for _depth in range(max_len + 1):
        for prog in frontier:
            if _solves(language, prog, cases):
                return prog
        frontier = [prog + (tok,) for prog in frontier for tok in vocab]
    return None


def invent_new_language(baseline: FormalLanguage, problems: Sequence[Sequence[Tuple]],
                        max_len: int = 5, name: str = "invented") -> FormalLanguage:
    """Invent a richer language by ABSTRACTING the most common contiguous sub-program across the baseline
    solutions of `problems` into a new named primitive (a macro). The new word is added ONLY if it recurs — a
    language whose extra word is never reused is just the baseline. Deterministic."""
    sols = [shortest_program(baseline, p, max_len) for p in problems]
    sols = [s for s in sols if s]
    sub: Counter = Counter()
    for s in sols:
        for L in range(2, len(s) + 1):
            for i in range(len(s) - L + 1):
                sub[tuple(s[i:i + L])] += 1
    # the most valuable macro: recurs across solutions and saves the most (support × (len − 1))
    candidates = [(seg, c) for seg, c in sub.items() if c >= 2]
    lang = FormalLanguage(name=name, primitives=dict(baseline.primitives), macros=dict(baseline.macros))
    if candidates:
        seg, _c = max(candidates, key=lambda sc: sc[1] * (len(sc[0]) - 1))
        macro_name = f"m{len(lang.macros)}"
        lang.macros[macro_name] = tuple(seg)
    return lang


def expressive_power(language: FormalLanguage, baseline: FormalLanguage,
                     problems: Sequence[Sequence[Tuple]], max_len: int = 6) -> float:
    """[0, ∞) external expressive gain: total baseline solution length ÷ total language solution length on the
    same problem family. > 1 ⇒ the invented language expresses these solutions more compactly; 1 ⇒ no gain (a
    rename); 0 ⇒ the language could not solve a problem the baseline could."""
    base_len = lang_len = 0
    for p in problems:
        b = shortest_program(baseline, p, max_len)
        l = shortest_program(language, p, max_len)
        if b is None:
            continue                                   # baseline can't solve it either → not a fair comparison
        if l is None:
            return 0.0                                 # the invented language FAILS a solvable problem → 0
        base_len += len(b)
        lang_len += len(l)
    if lang_len == 0:
        return 1.0
    return round(base_len / lang_len, 4)


def is_sound(language: FormalLanguage, checks: Sequence[Tuple[Program, object, object]]) -> bool:
    """Soundness: for each (program, input, expected), the interpreter runs it and matches the PRECOMPUTED
    expected output. A language that miscomputes (or crashes) is not sound — the honesty gate for Point 3."""
    for program, x, expected in checks:
        try:
            if language.run(program, x) != expected:
                return False
        except Exception:
            return False
    return True


# ── a reproducible baseline + problem family for the benchmark / invariant (integer pipelines) ──────────
def integer_baseline() -> FormalLanguage:
    return FormalLanguage(name="base", primitives={"inc": lambda x: x + 1, "double": lambda x: x * 2})


def _affine_problems() -> List[List[Tuple]]:
    """A family 2·(x+k) for k=1,2,3 — each needs an inc-run then a double in the baseline (lengths 2,3,4); an
    invented macro for the common tail shortens them all."""
    fams = []
    for k in (1, 2, 3):
        fams.append([(x, 2 * (x + k)) for x in range(4)])
    return fams


def soundness_controls_pass() -> bool:
    """The honesty gate for the expressive_power dimension (used by a protected invariant). TRUE iff:
      • the invented language is SOUND (interpreter matches precomputed outputs); AND
      • it gives a REAL expressive gain (power > 1) on the family; AND
      • the baseline compared to itself scores exactly 1 (a rename is no gain — the control)."""
    base = integer_baseline()
    problems = _affine_problems()
    lang = invent_new_language(base, problems)
    checks = [(("inc", "double"), 3, 8), (("double", "inc"), 3, 7), (("inc", "inc", "double"), 1, 6)]
    sound = is_sound(lang, checks)
    gain = expressive_power(lang, base, problems) > 1.0
    rename_is_one = expressive_power(base, base, problems) == 1.0
    return bool(sound and gain and rename_is_one)
