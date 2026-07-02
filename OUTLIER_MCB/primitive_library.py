"""primitive_library — a SELF-EXPANDING alphabet of primitives; invention becomes a RATCHET, not a plateau (T2).

With a fixed operator set the inventor cannot even REPRESENT the objects where hard solutions live, so it saturates
and repeats. Here the engine COMPOSES primitives and ABSTRACTS a useful composition into a new named primitive
on-demand (DreamCoder-style), so the reachable space GROWS. A behavioural dimension — composition depth — lets the
QD archive keep the deepest inventions.

Substrate (concrete, deterministic): transforms on a finite integer sequence (shift / finite-difference / partial-
sum / negate). A target «the sequence becomes constant» is unreachable at depth 1 but reachable at depth 2 (two
finite differences flatten a quadratic); once the engine abstracts `diff∘diff`, it is reachable at depth 1 — the
alphabet grew by itself. Pure-Python, zero-dep.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

Seq = Tuple[int, ...]


@dataclass(frozen=True)
class Primitive:
    name: str
    fn: Callable[[Seq], Seq]
    depth: int = 1                            # 1 for a base primitive; a composite carries its composition depth

    def __call__(self, s: Seq) -> Seq:
        return self.fn(s)


def _shift(s: Seq) -> Seq:
    return s[1:]


def _diff(s: Seq) -> Seq:
    return tuple(s[i + 1] - s[i] for i in range(len(s) - 1))


def _psum(s: Seq) -> Seq:
    out, acc = [], 0
    for x in s:
        acc += x
        out.append(acc)
    return tuple(out)


def _neg(s: Seq) -> Seq:
    return tuple(-x for x in s)


BASE_PRIMITIVES = [
    Primitive("shift", _shift), Primitive("diff", _diff), Primitive("psum", _psum), Primitive("neg", _neg),
]


def compose(outer: Primitive, inner: Primitive) -> Primitive:
    """A new primitive outer∘inner; its depth is the sum (how many base steps it packs). Deterministic name."""
    return Primitive(f"{outer.name}∘{inner.name}", lambda s: outer.fn(inner.fn(s)), outer.depth + inner.depth)


@dataclass
class PrimitiveLibrary:
    """A growing alphabet. `primitives` starts at the base set; `abstract` adds a discovered composite (the ratchet).
    `search` finds a composition (up to `max_depth` base steps) whose result satisfies a predicate."""
    primitives: List[Primitive] = field(default_factory=lambda: list(BASE_PRIMITIVES))
    abstractions: List[str] = field(default_factory=list)

    @property
    def max_reachable_depth(self) -> int:
        return max((p.depth for p in self.primitives), default=0)

    def abstract(self, primitive: Primitive) -> Primitive:
        """ABSTRACT a composite into a first-class primitive — the alphabet grows (deeper objects become depth-1)."""
        base = Primitive(primitive.name.replace("∘", "_"), primitive.fn, 1)   # now a single named step
        if base.name not in {p.name for p in self.primitives}:
            self.primitives.append(base)
            self.abstractions.append(base.name)
        return base

    def search(self, seq: Seq, predicate: Callable[[Seq], bool], max_depth: int = 2) -> Optional[Primitive]:
        """Find a composition of ≤ max_depth base steps mapping `seq` to a value satisfying `predicate`. BFS over the
        current alphabet, shallowest first (deterministic). Returns the winning Primitive, or None."""
        from collections import deque
        seen = set()
        # frontier of (primitive-or-None, current_seq). None = identity (depth 0).
        start = (None, seq, 0)
        q = deque([start])
        seen.add(seq)
        if predicate(seq):
            return Primitive("identity", lambda s: s, 0)
        while q:
            prim, cur, depth = q.popleft()
            if depth >= max_depth:
                continue
            for p in sorted(self.primitives, key=lambda x: x.name):
                try:
                    nxt = p.fn(cur)
                except Exception:
                    continue
                if len(nxt) < 2 or nxt in seen:
                    continue
                combined = p if prim is None else compose(p, prim)
                if predicate(nxt):
                    return combined
                seen.add(nxt)
                q.append((combined, nxt, depth + p.depth))
        return None


def becomes_constant(s: Seq) -> bool:
    """The target predicate: the sequence is a non-trivial constant (structure fully flattened)."""
    return len(s) >= 2 and len(set(s)) == 1
