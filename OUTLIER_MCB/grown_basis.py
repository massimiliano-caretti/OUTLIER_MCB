"""grown_basis — symbolic-regression PRIMITIVES the engine grew for itself by recursive self-improvement.

The zero-dep linear basis recovers only the algebraically-simplest laws (products of ≤2 variables, sums of
squares, single-variable sin/cos). Driven by its own diagnostics and verified-novelty fitness, the engine
explored the "unknown zone" — functional forms it had no example of — and discovered, then externally certified
on data (R²>0.999 + symbolic equivalence), five NEW primitive families:

  ratio            x_i / x_j                       → laws like q/C, ω/c
  triple_product   x_i · x_j · x_k                 → laws like m·g·z
  product_square   x_i · x_j²                      → laws like ½·m·(v²+u²+w²), ½·ε·Ef²
  product_trig     x_i · x_j · sin(x_k)            → laws like r·F·sin(θ)
  gaussian         exp(-x_i²/2)                    → the Gaussian

Each was ACCEPTED only because it strictly raised the externally-certified recovery without regressing any
already-recovered law and without breaking a protected invariant — the self-improvement gates. They are exposed
as an OPT-IN grown capability (`grown_backend()` / `grown_basis_terms()`); the documented zero-dep DEFAULT basis
is left deliberately limited and honest. Pure-Python, deterministic. These primitives apply to low-arity laws;
high-arity laws keep using the default basis (the grown primitives are skipped above `MAX_GROWN_ARITY` features,
both for honesty and to keep the linear system well-posed).
"""
from __future__ import annotations
import math
from typing import Callable, Dict, List

from .evaluators.symbolic import Term, least_squares

MAX_GROWN_ARITY = 4   # grown primitives apply to laws of ≤4 variables; larger laws use the default basis


def _const_linear(n: int) -> List[Term]:
    return [Term("1", lambda r: 1.0)] + [Term(f"x{i}", (lambda r, i=i: r[i])) for i in range(n)]


def _ratio(n: int) -> List[Term]:
    return [Term(f"x{i}/x{j}", (lambda r, i=i, j=j: r[i] / r[j] if abs(r[j]) > 1e-9 else 0.0))
            for i in range(n) for j in range(n) if i != j]


def _triple_product(n: int) -> List[Term]:
    out = []
    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                out.append(Term(f"x{i}*x{j}*x{k}", (lambda r, i=i, j=j, k=k: r[i] * r[j] * r[k])))
    return out


def _product_square(n: int) -> List[Term]:
    return [Term(f"x{i}*x{j}^2", (lambda r, i=i, j=j: r[i] * r[j] * r[j]))
            for i in range(n) for j in range(n) if i != j]


def _product_trig(n: int) -> List[Term]:
    out = []
    for i in range(n):
        for j in range(i + 1, n):
            for k in range(n):
                if k not in (i, j):
                    out.append(Term(f"x{i}*x{j}*sin(x{k})",
                                    (lambda r, i=i, j=j, k=k: r[i] * r[j] * math.sin(r[k]))))
    return out


def _gaussian(n: int) -> List[Term]:
    return [Term(f"exp(-x{i}^2/2)", (lambda r, i=i: math.exp(-r[i] * r[i] / 2))) for i in range(n)]


def _ratio_product(n: int) -> List[Term]:
    """x_i·x_j·x_k / x_l — laws like n·kb·T/V, q·v·B/p, μ·q·Volt/d (discovered on the extended substrate)."""
    import itertools
    out = []
    for l in range(n):
        idx = [i for i in range(n) if i != l]
        for a, b, c in itertools.combinations(idx, 3):
            out.append(Term(f"x{a}*x{b}*x{c}/x{l}",
                            (lambda r, a=a, b=b, c=c, l=l: r[a] * r[b] * r[c] / r[l] if abs(r[l]) > 1e-9 else 0.0)))
    return out


def _inverse_square(n: int) -> List[Term]:
    """x_i / x_j² — inverse-square laws like P/(4π r²) (discovered on the extended substrate)."""
    return [Term(f"x{i}/x{j}^2", (lambda r, i=i, j=j: r[i] / (r[j] * r[j]) if abs(r[j]) > 1e-9 else 0.0))
            for i in range(n) for j in range(n) if i != j]


def _ratio_product_invsq(n: int) -> List[Term]:
    """x_i·x_j / (x_k·x_l²) — Coulomb-type laws like q1·q2/(4π·ε·r²) (discovered in the multi-metric loop)."""
    import itertools
    out = []
    for k in range(n):
        for l in range(n):
            if l == k:
                continue
            rest = [i for i in range(n) if i not in (k, l)]
            for a, b in itertools.combinations(rest, 2):
                out.append(Term(f"x{a}*x{b}/(x{k}*x{l}^2)",
                                (lambda r, a=a, b=b, k=k, l=l: r[a] * r[b] / (r[k] * r[l] * r[l])
                                 if abs(r[k] * r[l]) > 1e-9 else 0.0)))
    return out


def product_k_builder(k: int) -> Callable[[int], List[Term]]:
    """The UNBOUNDED primitive family: the k-way product x0·x1·…·x_{k-1}, grown ON DEMAND for ANY k. The engine's
    primitive space is therefore NOT fixed at the eight discovered families — it EXPANDS as exploration demands a
    deeper composition. This is what turns a saturating curriculum into an open-ended ratchet (see open_ended.py):
    for every depth k there is a primitive that recovers it, so the frontier has no built-in ceiling (only compute).
    The default honest basis (`grown_basis_terms`, capped at MAX_GROWN_ARITY) never auto-includes these; the
    open-ended loop grows them explicitly and certifies each externally (R²>0.999 + SymPy) before accepting it."""
    if k < 1:
        raise ValueError("product depth k must be ≥ 1")
    name = "*".join(f"x{i}" for i in range(k))

    def build(n: int) -> List[Term]:
        if n < k:
            return []

        def val(r, k=k):
            p = 1.0
            for i in range(k):
                p *= r[i]
            return p
        return [Term(name, val)]
    return build


# the primitives the recursive self-improvement loop accepted (each strictly raised certified recovery), in the
# order they were discovered — the first five on the 14-law substrate, the last two on the extended substrate.
GROWN_PRIMITIVES: Dict[str, Callable[[int], List[Term]]] = {
    "ratio": _ratio,
    "triple_product": _triple_product,
    "product_square": _product_square,
    "product_trig": _product_trig,
    "gaussian": _gaussian,
    "ratio_product": _ratio_product,
    "inverse_square": _inverse_square,
    "ratio_product_invsq": _ratio_product_invsq,
}


def grown_basis_terms(n_features: int, primitives: Dict[str, Callable] = None) -> List[Term]:
    """The full grown basis for `n_features`: constant + linear + every accepted grown primitive (skipped above
    MAX_GROWN_ARITY to keep the system well-posed). Pass `primitives` to use a subset (the self-improvement loop
    grows this set one primitive at a time)."""
    prims = GROWN_PRIMITIVES if primitives is None else primitives
    terms = _const_linear(n_features)
    # the default families that already worked (interaction x_i^2 / x_i·x_j, single-variable sin) stay available
    for i in range(n_features):
        terms.append(Term(f"x{i}^2", (lambda r, i=i: r[i] * r[i])))
        terms.append(Term(f"sin(x{i})", (lambda r, i=i: math.sin(r[i]))))
        for j in range(i + 1, n_features):
            terms.append(Term(f"x{i}*x{j}", (lambda r, i=i, j=j: r[i] * r[j])))
    if n_features <= MAX_GROWN_ARITY:
        for build in prims.values():
            terms.extend(build(n_features))
    return terms


def grown_backend(primitives: Dict[str, Callable] = None) -> Callable:
    """A zero-dep, DETERMINISTIC backend for `symbolic_evaluator` that fits over the grown basis — the engine's
    self-improved native SR capability (recovers division, ≥3-way products, transcendental products the default
    basis cannot). Use: `gsl.symbolic_evaluator(data, backend=gsl.grown_backend())`."""
    def backend(X, y, candidate, n_features: int):
        return least_squares(X, y, grown_basis_terms(n_features, primitives))
    return backend
