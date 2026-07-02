"""semantic_grounding — the engine coins its OWN concepts to describe its own behavior (Point 2, endogenous
meaning). A creative mind compresses experience into private symbols ('this again' → a named idea). Here the
engine watches its own logs (e.g. DiagnosticMemory), finds a RECURRING non-trivial pattern, and GROUNDS a new
endogenous symbol for it — a self-created concept, not a human-given label.

Meaning is earned, not declared. The external metric is CONCEPTUAL COMPRESSION measured by Minimum Description
Length: a symbol pays for its dictionary entry once and saves a token at every occurrence, so a genuinely
recurring pattern yields a compression ratio > 1, while a pattern that occurs once (or is trivial) yields ≤ 1
(no gain) — that is the negative control. The protected invariant refuses an UNGROUNDED symbol (one that maps
to no real, non-trivial, observed pattern), so the engine can never inflate the metric with empty concepts.

(Correction to the plan's gzip proposal: gzip ALREADY exploits repetition, so 'substitute then gzip' would
double-count and show a phantom gain — theatre. MDL over the symbol dictionary is the honest measure of the
gain from NAMING structure, which is exactly what a concept is.) Deterministic, zero-dependency.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

Token = str


@dataclass
class EndogenousSymbol:
    """A self-coined concept: a unique name standing for a recurring pattern of primitive tokens."""
    name: str
    pattern: Tuple[Token, ...]
    support: int                       # how many non-overlapping times it was observed (its grounding evidence)

    @property
    def is_grounded(self) -> bool:
        """A symbol MEANS something only if it abstracts a non-trivial (len ≥ 2) pattern seen ≥ 2 times."""
        return len(self.pattern) >= 2 and self.support >= 2


@dataclass
class SymbolRegistry:
    symbols: Dict[str, EndogenousSymbol] = field(default_factory=dict)
    _counter: int = 0

    def _next_name(self) -> str:
        self._counter += 1
        return f"_CONCEPT_{self._counter:03d}"

    def all_grounded(self) -> bool:
        """The registry is honest iff EVERY symbol in it is grounded in a real pattern (the invariant's core)."""
        return all(s.is_grounded for s in self.symbols.values())


def _count_nonoverlapping(log: Sequence[Token], pattern: Tuple[Token, ...]) -> int:
    if not pattern:
        return 0
    n, m, i, c = len(log), len(pattern), 0, 0
    while i + m <= n:
        if tuple(log[i:i + m]) == pattern:
            c += 1
            i += m
        else:
            i += 1
    return c


def find_recurring_patterns(log: Sequence[Token], min_len: int = 2, max_len: int = 6,
                            min_support: int = 2) -> List[Tuple[Tuple[Token, ...], int]]:
    """Recurring, non-trivial contiguous patterns in `log`, most-compressing first (support × length). This is
    what the engine can meaningfully NAME — the raw material for an endogenous concept."""
    seen: Dict[Tuple[Token, ...], int] = {}
    n = len(log)
    for L in range(min_len, max_len + 1):
        for i in range(n - L + 1):
            pat = tuple(log[i:i + L])
            if pat not in seen:
                seen[pat] = _count_nonoverlapping(log, pat)
    good = [(p, c) for p, c in seen.items() if c >= min_support]
    return sorted(good, key=lambda pc: -(pc[1] * (len(pc[0]) - 1)))     # savings ≈ support × (len − 1)


def ground_new_symbol(pattern: Sequence[Token], log: Sequence[Token],
                      registry: Optional[SymbolRegistry] = None) -> Optional[EndogenousSymbol]:
    """Coin a new endogenous symbol for `pattern` — but ONLY if it is real: a non-trivial pattern actually
    observed ≥ 2 times in `log`. Returns None (refuses) for an ungrounded/empty pattern, so the metric can
    never be inflated by a symbol that means nothing. Honesty over coverage."""
    pat = tuple(pattern)
    support = _count_nonoverlapping(log, pat)
    sym = EndogenousSymbol(name="(candidate)", pattern=pat, support=support)
    if not sym.is_grounded:
        return None
    reg = registry if registry is not None else SymbolRegistry()
    sym.name = reg._next_name()
    reg.symbols[sym.name] = sym
    return sym


def verify_grounding(symbol: EndogenousSymbol, log: Sequence[Token], min_support: int = 2) -> bool:
    """RE-check a symbol against a real log — never trusting its stored `support` field. A symbol is grounded
    only if its non-trivial pattern actually occurs ≥ min_support times in the log. This is what the protected
    invariant uses to refuse an empty/self-declared concept."""
    return len(symbol.pattern) >= 2 and _count_nonoverlapping(log, symbol.pattern) >= min_support


def _rewrite(log: Sequence[Token], symbols: Sequence[EndogenousSymbol]) -> List[Token]:
    """Rewrite the log, replacing each grounded symbol's occurrences with its single name token (greedy, longest
    pattern first so a longer concept wins over a shorter sub-pattern)."""
    out = list(log)
    for sym in sorted(symbols, key=lambda s: -len(s.pattern)):
        pat, name, m = sym.pattern, sym.name, len(sym.pattern)
        i, res = 0, []
        while i < len(out):
            if tuple(out[i:i + m]) == pat:
                res.append(name)
                i += m
            else:
                res.append(out[i])
                i += 1
        out = res
    return out


def conceptual_compression(log: Sequence[Token], symbols: Sequence[EndogenousSymbol]) -> float:
    """Compression ratio from NAMING structure, by MDL: raw token count ÷ (dictionary cost + rewritten length),
    where the dictionary costs each symbol its pattern's tokens once. > 1 ⇒ the concepts genuinely compress the
    log; ≤ 1 ⇒ no gain (the negative control: a symbol that never occurs adds dictionary cost for no saving)."""
    grounded = [s for s in symbols if s.is_grounded]
    raw = len(log)
    if raw == 0:
        return 1.0
    rewritten_tokens = _rewrite(log, grounded)
    rewritten = len(rewritten_tokens)
    # BUGFIX: only charge the dictionary for symbols that ACTUALLY appear in the rewrite. A longer symbol can
    # shadow a shorter overlapping one, leaving it with zero rewrite savings — charging its full pattern cost
    # anyway understated the ratio. Now an unused (shadowed) symbol costs nothing.
    used = set(rewritten_tokens)
    dictionary = sum(len(s.pattern) for s in grounded if s.name in used)
    described = dictionary + rewritten
    return round(raw / described, 4) if described else 1.0


def grounding_controls_pass() -> bool:
    """The honesty gate for the conceptual-compression dimension (used by a protected invariant). TRUE iff:
      • a REAL recurring pattern grounds a symbol that compresses the log (ratio > 1); AND
      • an UNGROUNDED (ghost) symbol fails verification AND gives NO gain (ratio ≤ 1); AND
      • grounding a NON-recurring pattern is REFUSED (returns None).
    If any clause fails, the metric could be inflated by an empty concept → the dimension is dishonest."""
    log = ["settle", "timeout", "retry"] * 8 + ["ok"] + ["settle", "timeout", "retry"] * 4
    reg = SymbolRegistry()
    real = ground_new_symbol(("settle", "timeout", "retry"), log, reg)
    real_gain = real is not None and conceptual_compression(log, [real]) > 1.0
    ghost = EndogenousSymbol("_GHOST", ("never", "seen", "x"), support=99)
    ghost_blocked = (not verify_grounding(ghost, log)) and conceptual_compression(log, [ghost]) <= 1.0
    once_refused = ground_new_symbol(("ok",), log, reg) is None       # trivial/non-recurring → refused
    return bool(real_gain and ghost_blocked and once_refused)
