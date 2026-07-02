"""oracle_miner — the oracle as a SOURCE OF SPARKS, not only a refuter (T1). Breaks the assumption that
evaluation is a fixed, one-way gate (that a value oracle can only KILL candidates, never inspire them).

An exact-value oracle (a callable n→value, or a list of terms) is a MINE of structure: a discoverer reads it for
holonomic recurrences, algebraic/differential equations of the generating function, modular patterns, asymptotic
ratios. Using it only to KILL candidates throws away its most creative part — telling you WHERE there is order.
So this module EXTRACTS candidate invariants and returns them as IDEAS to explore (each with an external check),
turning the judge into an inventor's spark.

Honesty (what keeps a discovery real): every mined invariant is VERIFIED on held-out terms the fit never saw; a
sequence with no low-order structure (e.g. the primes) yields NO invariant rather than a hallucinated one. Real
sparks only. Pure-Python (Fraction), deterministic.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Callable, Dict, List, Optional, Tuple, Union

Oracle = Union[Callable[[int], int], List[int]]


def _terms(oracle: Oracle, n: int) -> List[int]:
    if callable(oracle):
        return [int(oracle(i)) for i in range(n)]
    return [int(x) for x in oracle[:n]]


def _nullspace_vec(rows: List[List[Fraction]]) -> Optional[List[Fraction]]:
    """A nonzero rational vector in the right nullspace of `rows` (reduced row echelon), or None if trivial.
    Deterministic: fixed pivoting, the FIRST free column is set to 1."""
    A = [list(r) for r in rows]
    m = len(A)
    n = len(A[0]) if A else 0
    piv = {}
    r = 0
    for c in range(n):
        pr = next((i for i in range(r, m) if A[i][c] != 0), None)
        if pr is None:
            continue
        A[r], A[pr] = A[pr], A[r]
        inv = A[r][c]
        A[r] = [x / inv for x in A[r]]
        for i in range(m):
            if i != r and A[i][c] != 0:
                f = A[i][c]
                A[i] = [a - f * b for a, b in zip(A[i], A[r])]
        piv[c] = r
        r += 1
        if r == m:
            break
    free = [c for c in range(n) if c not in piv]
    if not free:
        return None
    fc = free[0]
    vec = [Fraction(0)] * n
    vec[fc] = Fraction(1)
    for c, row in piv.items():
        vec[c] = -A[row][fc]
    return vec


def _solve_square(A: List[List[Fraction]], b: List[Fraction]) -> Optional[List[Fraction]]:
    """Solve the square rational system A·x = b exactly (Gaussian elimination). None if singular. Deterministic."""
    n = len(A)
    M = [list(A[i]) + [b[i]] for i in range(n)]
    for c in range(n):
        pr = next((i for i in range(c, n) if M[i][c] != 0), None)
        if pr is None:
            return None
        M[c], M[pr] = M[pr], M[c]
        inv = M[c][c]
        M[c] = [x / inv for x in M[c]]
        for i in range(n):
            if i != c and M[i][c] != 0:
                f = M[i][c]
                M[i] = [a - f * d for a, d in zip(M[i], M[c])]
    return [M[i][n] for i in range(n)]


@dataclass
class PolynomialClosedForm:
    """The MOST desired form: a(n) is an explicit polynomial in n, a(n) = Σ_d coeffs[d]·n^d. Detected by fitting a
    degree-d polynomial to the first d+1 terms and VERIFYING it reproduces every later term exactly (held-out)."""
    degree: int
    coeffs: List[Fraction]                    # low → high powers of n
    verified_on: int

    def eval(self, n: int) -> Fraction:
        return sum(self.coeffs[d] * Fraction(n) ** d for d in range(self.degree + 1))

    def as_text(self) -> str:
        parts = []
        for d, c in enumerate(self.coeffs):
            if c == 0:
                continue
            mag = abs(c)
            mono = f"{mag}·n^{d}" if d else f"{mag}"
            parts.append(f"{'-' if c < 0 else ('+' if parts else '')} {mono}".strip())
        return f"a(n) = {' '.join(parts) or '0'}"


def guess_polynomial_closed_form(oracle: Oracle, max_degree: int = 6, n_terms: int = 16) -> Optional[PolynomialClosedForm]:
    """Search for an explicit polynomial closed form a(n) = poly(n) — the CLOSED_FORM top of the solution lattice.
    Fits a degree-d polynomial to the first d+1 terms and VERIFIES it on every remaining term; returns the smallest
    such d, or None (a non-polynomial sequence — Catalan, primes — yields no false closed form). Deterministic."""
    terms = _terms(oracle, n_terms)
    if len(terms) < 4:
        return None
    top = min(max_degree, len(terms) - 3)                 # keep ≥3 terms strictly held-out for verification
    for d in range(0, top + 1):
        A = [[Fraction(x) ** k for k in range(d + 1)] for x in range(d + 1)]
        coeffs = _solve_square(A, [Fraction(terms[x]) for x in range(d + 1)])
        if coeffs is None:
            continue
        checked = 0
        ok = True
        for n in range(d + 1, len(terms)):
            if sum(coeffs[k] * Fraction(n) ** k for k in range(d + 1)) != Fraction(terms[n]):
                ok = False
                break
            checked += 1
        if ok and checked > 0:
            return PolynomialClosedForm(d, coeffs, checked)
    return None


@dataclass
class HolonomicRecurrence:
    """A P-recursive relation Σ_{k=0..order} p_k(n)·a(n+k) = 0, with p_k a polynomial of degree ≤ `degree`.
    `coeffs[k]` are the polynomial coefficients (low→high) of p_k, as Fractions. VERIFIED on held-out terms."""
    order: int
    degree: int
    coeffs: List[List[Fraction]]
    verified_on: int                          # how many held-out terms it was checked against (0 ⇒ not held-out-verified)

    def as_text(self) -> str:
        def poly(cs):
            terms = []
            for d, c in enumerate(cs):
                if c == 0:
                    continue
                mag = abs(c)
                mono = f"{mag}·n^{d}" if d else f"{mag}"
                sign = "-" if c < 0 else ("+" if terms else "")
                terms.append(f"{sign} {mono}".strip())
            return " ".join(terms) or "0"
        return "  +  ".join(f"({poly(self.coeffs[k])})·a(n+{k})" for k in range(self.order + 1)) + "  =  0"

    def predict_next(self, terms: List[int]) -> Optional[Fraction]:
        """Use the recurrence to predict a(n+order) from earlier terms (leading poly must be nonzero)."""
        n = len(terms) - self.order
        if n < 0:
            return None
        lead = sum(self.coeffs[self.order][d] * Fraction(n) ** d for d in range(self.degree + 1))
        if lead == 0:
            return None
        s = Fraction(0)
        for k in range(self.order):
            pk = sum(self.coeffs[k][d] * Fraction(n) ** d for d in range(self.degree + 1))
            s += pk * Fraction(terms[n + k])
        return -s / lead


def guess_holonomic(oracle: Oracle, max_order: int = 3, max_degree: int = 2,
                    n_terms: int = 16) -> Optional[HolonomicRecurrence]:
    """Search (smallest order, then degree) for a P-recursive recurrence that fits the first terms AND VERIFIES on
    held-out terms. Returns None if none does — a non-holonomic sequence yields no (false) recurrence. Deterministic."""
    terms = _terms(oracle, n_terms)
    if len(terms) < 6:
        return None
    for order in range(1, max_order + 1):
        for degree in range(0, max_degree + 1):
            ncoef = (order + 1) * (degree + 1)
            fit_rows_needed = ncoef + 2                       # a couple extra rows to pin a low-dim nullspace
            usable = len(terms) - order
            if usable < fit_rows_needed + 2:                  # keep ≥2 terms strictly held-out for verification
                continue
            fit_n = usable - 2
            rows = []
            for n in range(fit_n):
                row = []
                for k in range(order + 1):
                    for d in range(degree + 1):
                        row.append(Fraction(n) ** d * Fraction(terms[n + k]))
                rows.append(row)
            vec = _nullspace_vec(rows)
            if vec is None or all(v == 0 for v in vec):
                continue
            coeffs = [[vec[k * (degree + 1) + d] for d in range(degree + 1)] for k in range(order + 1)]
            rec = HolonomicRecurrence(order, degree, coeffs, verified_on=0)
            held = _verify_recurrence(rec, terms, start=fit_n)
            if held > 0:                                      # must hold on terms the fit never saw
                rec.verified_on = held
                return rec
    return None


def _verify_recurrence(rec: HolonomicRecurrence, terms: List[int], start: int) -> int:
    """Count held-out terms (index ≥ start) on which the recurrence holds EXACTLY; 0 if it ever fails."""
    checked = 0
    for n in range(start, len(terms) - rec.order):
        s = Fraction(0)
        for k in range(rec.order + 1):
            pk = sum(rec.coeffs[k][d] * Fraction(n) ** d for d in range(rec.degree + 1))
            s += pk * Fraction(terms[n + k])
        if s != 0:
            return 0
        checked += 1
    return checked


@dataclass
class PolynomialRecurrence:
    """A NON-LINEAR (polynomial) recurrence: sum_i coeff_i * mono_i = 0, where each mono_i is a product of
    window terms a(n),...,a(n+order) (total degree >= 2) times a power of n. Captures Somos-like / quadratic
    laws that linear (holonomic) guessing cannot -- the 'apparently empty' non-linear space."""
    order: int
    total_degree: int
    n_degree: int
    monomials: List[Tuple[Tuple[int, ...], int]]     # (exponents over window k=0..order, power of n)
    coeffs: List[Fraction]
    verified_on: int = 0

    @property
    def is_generative(self) -> bool:
        """True iff the relation is LINEAR in the leading term a(n+order) with a nonzero coefficient — then it
        determines a(n+order) uniquely (a GENERATIVE recurrence, like Somos). If the leading term appears with
        exponent ≥2 (or not at all), the relation is a structural INVARIANT (a real law, but not a solution)."""
        lead_exps = [exps[self.order] for (exps, _), c in zip(self.monomials, self.coeffs) if c != 0]
        return bool(lead_exps) and max(lead_exps) == 1

    def as_text(self) -> str:
        parts = []
        for (exps, p), c in zip(self.monomials, self.coeffs):
            if c == 0:
                continue
            term = [] if p == 0 else [f"n^{p}"]
            for k, e in enumerate(exps):
                if e:
                    term.append(f"a(n+{k})^{e}" if e > 1 else f"a(n+{k})")
            parts.append(f"({c})*" + "*".join(term) if term else f"({c})")
        return " + ".join(parts) + " = 0"


def _poly_monomials(order: int, total_degree: int, n_degree: int):
    from itertools import combinations_with_replacement
    idx = list(range(order + 1))
    monos = []
    for deg in range(0, total_degree + 1):
        for combo in combinations_with_replacement(idx, deg):
            exps = [0] * (order + 1)
            for c in combo:
                exps[c] += 1
            for p in range(n_degree + 1):
                monos.append((tuple(exps), p))
    return monos


def _verify_poly_rec(rec: "PolynomialRecurrence", terms: List[int], start: int) -> int:
    checked = 0
    for n in range(start, len(terms) - rec.order):
        window = [Fraction(terms[n + k]) for k in range(rec.order + 1)]
        s = Fraction(0)
        for (exps, p), c in zip(rec.monomials, rec.coeffs):
            if c == 0:
                continue
            val = Fraction(n) ** p
            for k, e in enumerate(exps):
                if e:
                    val *= window[k] ** e
            s += c * val
        if s != 0:
            return 0
        checked += 1
    return checked


def guess_polynomial_recurrence(oracle: Oracle, max_order: int = 3, max_total_degree: int = 2,
                                max_n_degree: int = 1, n_terms: int = 20) -> Optional[PolynomialRecurrence]:
    """Search the NON-LINEAR space: a polynomial relation among a(n)..a(n+order) of total degree >= 2 (with
    n-polynomial coefficients) that fits AND verifies on held-out terms. Finds Somos/quadratic laws that
    holonomic guessing structurally cannot; returns None (no hallucinated law) when the space is genuinely
    empty. Deterministic. The break out of the linear/holonomic box -- exploring apparently-empty structure."""
    terms = _terms(oracle, n_terms)
    if len(terms) < 8:
        return None
    for order in range(1, max_order + 1):
        for total_degree in range(2, max_total_degree + 1):          # >=2: linear is guess_holonomic's job
            for n_degree in range(0, max_n_degree + 1):
                monos = _poly_monomials(order, total_degree, n_degree)
                ncoef = len(monos)
                usable = len(terms) - order
                held_out = 4                                          # ≥4 strictly held-out terms → spurious fits are rejected
                if usable < ncoef + held_out + 2:                    # need overdetermination + the held-out margin
                    continue
                fit_n = usable - held_out
                rows = []
                for n in range(fit_n):
                    window = [Fraction(terms[n + k]) for k in range(order + 1)]
                    row = []
                    for (exps, p) in monos:
                        val = Fraction(n) ** p
                        for k, e in enumerate(exps):
                            if e:
                                val *= window[k] ** e
                        row.append(val)
                    rows.append(row)
                vec = _nullspace_vec(rows)
                if vec is None or all(v == 0 for v in vec):
                    continue
                rec = PolynomialRecurrence(order, total_degree, n_degree, monos, vec)
                # HONESTY: a relation that couples only ONE window position (e.g. a(n)²=a(n) — merely 'the values
                # are in a finite set') is a DEGENERATE range constraint, not a relation between terms. Require it
                # to involve ≥2 distinct window indices to count as real structure.
                touched = {k for (exps, _), c in zip(monos, vec) if c != 0 for k, e in enumerate(exps) if e}
                if len(touched) < 2:
                    continue
                held = _verify_poly_rec(rec, terms, start=fit_n)
                if held > 0:
                    rec.verified_on = held
                    return rec
    return None


@dataclass
class AlgebraicGF:
    """The generating function y=sum a(n)x^n satisfies a polynomial equation P(x,y)=sum c_ij x^i y^j = 0.
    Algebraic functions are a class ORTHOGONAL to holonomic linear recurrences (many algebraic GFs are also
    holonomic, but the search axis is different) and to non-linear term recurrences. Held-out verified."""
    gf_degree: int
    x_degree: int
    monomials: List[Tuple[int, int]]                  # (power of x, power of y)
    coeffs: List[Fraction]
    verified_on: int = 0

    def as_text(self) -> str:
        parts = []
        for (i, j), c in zip(self.monomials, self.coeffs):
            if c == 0:
                continue
            t = [] if i == 0 else [f"x^{i}"]
            if j:
                t.append(f"y^{j}" if j > 1 else "y")
            parts.append(f"({c})*" + "*".join(t) if t else f"({c})")
        return " + ".join(parts) + " = 0"


def _series_pow(series: List[Fraction], j: int, M: int) -> List[Fraction]:
    out = [Fraction(1)] + [Fraction(0)] * M
    for _ in range(j):
        nxt = [Fraction(0)] * (M + 1)
        for a in range(M + 1):
            if out[a] == 0:
                continue
            for b in range(M + 1 - a):
                nxt[a + b] += out[a] * series[b]
        out = nxt
    return out


def guess_algebraic_gf(oracle: Oracle, max_gf_degree: int = 3, max_x_degree: int = 4,
                       n_terms: int = 20) -> Optional[AlgebraicGF]:
    """Search whether the ordinary generating function is ALGEBRAIC of low degree: P(x,y)=0. Fits on the first
    orders and VERIFIES on held-out orders (so a spurious fit is rejected). Returns None when the GF is not
    low-degree algebraic -- no hallucinated equation. Deterministic. A search axis holonomic guessing misses."""
    terms = _terms(oracle, n_terms)
    M = len(terms) - 1
    if M < 8:
        return None
    y = [Fraction(0)] + [Fraction(t) for t in terms]      # y_0=0 offset so a(n) is coeff of x^n (n>=1)
    y = y[:M + 1]
    for gf_degree in range(2, max_gf_degree + 1):
        for x_degree in range(1, max_x_degree + 1):
            monos = [(i, j) for j in range(gf_degree + 1) for i in range(x_degree + 1)]
            ncoef = len(monos)
            if M + 1 < ncoef + 6:                          # overdetermination + a 4-order held-out margin
                continue
            ypows = {j: _series_pow(y, j, M) for j in range(gf_degree + 1)}
            fit = M - 4                                    # hold out the last 4 orders (reject spurious algebraic fits)
            rows = []
            for k in range(fit + 1):
                row = [(ypows[j][k - i] if k - i >= 0 else Fraction(0)) for (i, j) in monos]
                rows.append(row)
            vec = _nullspace_vec(rows)
            if vec is None or all(v == 0 for v in vec):
                continue
            # verify on held-out orders fit+1..M
            ok = True
            for k in range(fit + 1, M + 1):
                s = sum(vec[t] * (ypows[j][k - i] if k - i >= 0 else Fraction(0)) for t, (i, j) in enumerate(monos))
                if s != 0:
                    ok = False
                    break
            if ok:
                return AlgebraicGF(gf_degree, x_degree, monos, vec, verified_on=M - fit)
    return None


@dataclass
class ModularPattern:
    modulus: int
    residues: List[int]                       # the eventually-periodic residues a(n) mod modulus
    verified_on: int


def guess_modular_pattern(oracle: Oracle, moduli=(2, 3, 4, 5, 6, 7, 8, 9), n_terms: int = 24) -> Optional[ModularPattern]:
    """Find a modulus for which a(n) mod m is PURELY PERIODIC with a short period, verified on held-out terms."""
    terms = _terms(oracle, n_terms)
    if len(terms) < 12:
        return None
    for m in moduli:
        res = [t % m for t in terms]
        for period in range(1, len(res) // 3 + 1):
            if all(res[i] == res[i % period] for i in range(len(res))):
                if len(set(res[:period])) > 1:                # a non-constant genuine pattern
                    return ModularPattern(m, res[:period], verified_on=len(res) - period)
    return None


# ── AXIS 1: MULTIPLICATIVE / number-theoretic — a(m·n)=a(m)·a(n) (orthogonal to additive recurrences) ─────────
@dataclass
class MultiplicativeStructure:
    """The sequence is a MULTIPLICATIVE function: a(m·n)=a(m)·a(n) for coprime m,n (φ, σ, d, μ, …) — so it is
    DETERMINED by its values on prime powers. `completely` ⇒ it holds for ALL m,n (a completely multiplicative
    function). A whole axis the additive recurrence miners cannot represent."""
    completely: bool
    verified_pairs: int

    def as_text(self) -> str:
        kind = "completely multiplicative" if self.completely else "multiplicative"
        return f"a(m·n) = a(m)·a(n) [{kind}] — determined by its values on prime powers"


def guess_multiplicative(oracle: Oracle, n_terms: int = 48) -> Optional[MultiplicativeStructure]:
    """Read the oracle 1-indexed (a(k)=terms[k-1]) and detect a MULTIPLICATIVE function: a(m·n)=a(m)·a(n) for
    coprime m,n, verified across MANY pairs. Requires a(1)=1 (the multiplicative identity) and a non-constant,
    non-linear sequence (constants/a(n)=n are caught earlier as closed forms). None for non-multiplicative input
    (primes, Fibonacci). Deterministic."""
    import math as _m
    terms = _terms(oracle, n_terms)
    N = len(terms)
    if N < 16 or terms[0] != 1:                        # a(1) must be 1
        return None
    if len(set(terms)) <= 2:                           # degenerate (near-constant) — not a genuine multiplicative law
        return None

    def a(k):
        return terms[k - 1]
    coprime = [(x, y) for x in range(2, N + 1) for y in range(x, N + 1) if x * y <= N and _m.gcd(x, y) == 1]
    if len(coprime) < 6:                               # need enough independent evidence
        return None
    if any(a(x * y) != a(x) * a(y) for (x, y) in coprime):
        return None
    allp = [(x, y) for x in range(2, N + 1) for y in range(x, N + 1) if x * y <= N]
    completely = all(a(x * y) == a(x) * a(y) for (x, y) in allp)
    return MultiplicativeStructure(completely, len(coprime))


# ── AXIS 2: ASYMPTOTIC with a CERTIFIED BAND — a real law where exact structure is absent (primes, partitions) ──
@dataclass
class AsymptoticLaw:
    form: str
    band_lo: float
    band_hi: float
    verified_on: int

    def as_text(self) -> str:
        return f"a(n) ~ {self.form} — ratio a(n)/model ∈ [{self.band_lo:.3f}, {self.band_hi:.3f}] on held-out (a band, NOT an exact law)"


def _lin_slope(xs, ys):
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    den = sum((x - mx) ** 2 for x in xs)
    return (sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den) if den else 0.0


def guess_asymptotic(oracle: Oracle, n_terms: int = 40, band_tol: float = 0.15) -> Optional[AsymptoticLaw]:
    """Fit a growth model and CERTIFY a band: the ratio a(n)/model(n) stays within a TIGHT [lo,hi] on held-out
    terms. Tries n^α, n·log n, r^n, exp(c·√n). Returns the tightest law that passes `band_tol`, or None (bounded /
    irregular growth). Approximate by nature — an ASYMPTOTIC lead with a band, honestly NOT exact. Deterministic."""
    import math
    terms = _terms(oracle, n_terms)
    pts = [(i, terms[i]) for i in range(2, len(terms)) if terms[i] > 0]
    if len(pts) < 16:
        return None
    hold = 6
    fit, held = pts[:-hold], pts[-hold:]
    models = []
    la = [math.log(v) for _, v in fit]
    # power law  a(n) ~ C·n^α
    al = _lin_slope([math.log(i) for i, _ in fit], la)
    models.append(("%.3f·n^%.3f" % (math.exp(sum(la[k] - al * math.log(fit[k][0]) for k in range(len(fit))) / len(fit)), al),
                   lambda i, al=al: i ** al))
    # n·log n
    models.append(("C·n·log n", lambda i: i * math.log(i)))
    # exponential  a(n) ~ C·r^n
    rl = _lin_slope([i for i, _ in fit], la)
    models.append(("C·%.4f^n" % math.exp(rl), lambda i, rl=rl: math.exp(rl * i)))
    # stretched exp  exp(c·√n)
    cl = _lin_slope([math.sqrt(i) for i, _ in fit], la)
    models.append(("exp(%.3f·√n)" % cl, lambda i, cl=cl: math.exp(cl * math.sqrt(i))))
    best = None
    for name, g in models:
        try:
            cfit = sum(v / g(i) for i, v in fit) / len(fit)
            if cfit <= 0:
                continue
            ratios = [v / (cfit * g(i)) for i, v in held]
        except (ValueError, ZeroDivisionError, OverflowError):
            continue
        lo, hi = min(ratios), max(ratios)
        if lo > 0 and hi / lo - 1 <= band_tol:
            spread = hi / lo
            if best is None or spread < best[0]:
                best = (spread, AsymptoticLaw(name, lo, hi, len(held)))
    return best[1] if best else None


# ── AXIS 3: k-AUTOMATIC / digit axis — a finite automaton on the base-k digits of n (Thue-Morse, paper-folding) ──
@dataclass
class KAutomatic:
    base: int
    maps: Dict[int, Dict[int, int]]                    # r → {a(n) : a(k·n+r)}
    verified_on: int

    def as_text(self) -> str:
        return f"{self.base}-automatic: a({self.base}·n+r) = f_r(a(n)) with transition tables {self.maps}"


def guess_k_automatic(oracle: Oracle, bases=(2, 3), n_terms: int = 64) -> Optional[KAutomatic]:
    """Detect a k-AUTOMATIC sequence: for each residue r, a(k·n+r) is a consistent FUNCTION of a(n) (a small,
    finite value alphabet), verified on held-out n. Captures self-similar sequences (Thue-Morse: a(2n)=a(n),
    a(2n+1)=1−a(n)) that no recurrence miner represents. None for a large-alphabet / non-automatic sequence.
    Rejects the trivial all-identity map (that is mere periodicity). Deterministic."""
    terms = _terms(oracle, n_terms)
    N = len(terms)
    alphabet = set(terms)
    if N < 24 or not (2 <= len(alphabet) <= 6):        # finitely (few)-valued and non-constant
        return None
    for k in bases:
        fit = (N // k) - 2
        if fit < 8:
            continue
        maps, good = {}, True
        for r in range(k):
            table = {}
            for n in range(fit):
                idx = k * n + r
                if idx >= N:
                    break
                key, val = terms[n], terms[idx]
                if table.get(key, val) != val:
                    good = False
                    break
                table[key] = val
            if not good or not table:
                good = False
                break
            maps[r] = table
        if not good:
            continue
        if all(all(kk == vv for kk, vv in t.items()) for t in maps.values()):
            continue                                   # all-identity ⇒ mere periodicity, not interesting automaticity
        held, okh = 0, True
        for n in range(fit, N):
            for r in range(k):
                idx = k * n + r
                if idx >= N:
                    break
                if terms[n] in maps[r]:
                    if maps[r][terms[n]] != terms[idx]:
                        okh = False
                        break
                    held += 1
            if not okh:
                break
        if okh and held > 0:
            return KAutomatic(k, maps, held)
    return None


@dataclass
class MinedSparks:
    """The candidate invariants an oracle suggests — each a REAL, held-out-verified idea to explore, never a guess."""
    holonomic: Optional[HolonomicRecurrence] = None
    modular: Optional[ModularPattern] = None
    polynomial: Optional["PolynomialRecurrence"] = None   # non-linear (Somos-like) law, if any
    algebraic: Optional["AlgebraicGF"] = None             # algebraic generating-function equation, if any
    closed_form: Optional["PolynomialClosedForm"] = None  # an explicit polynomial a(n)=poly(n), if any (the TOP form)
    multiplicative: Optional["MultiplicativeStructure"] = None   # a(m·n)=a(m)·a(n) — number-theoretic axis
    k_automatic: Optional["KAutomatic"] = None            # a finite automaton on base-k digits of n — digit axis
    asymptotic: Optional["AsymptoticLaw"] = None          # a(n) ~ model with a certified band — the growth axis
    growth_ratio: Optional[float] = None      # a(n+1)/a(n) → limit estimate (an asymptotic spark, not a certificate)
    sparks: List[str] = field(default_factory=list)

    @property
    def found_structure(self) -> bool:
        return any(x is not None for x in (self.closed_form, self.holonomic, self.modular, self.polynomial,
                                           self.algebraic, self.multiplicative, self.k_automatic, self.asymptotic))

    @property
    def exact_structure_found(self) -> bool:
        """Exact / generative structure only. Approximate growth bands are useful discoveries, but they are not
        closed forms, recurrences, automata, multiplicative laws, or algebraic equations."""
        return any(x is not None for x in (self.closed_form, self.holonomic, self.modular, self.polynomial,
                                           self.algebraic, self.multiplicative, self.k_automatic))

    @property
    def weak_structure_found(self) -> bool:
        """A non-exact but still externally checked structure, e.g. an asymptotic band."""
        return self.asymptotic is not None and not self.exact_structure_found

    @property
    def discovery_rung(self) -> str:
        if self.closed_form:
            return "EXACT_CLOSED_FORM"
        if self.holonomic or self.polynomial:
            return "EXACT_RECURRENCE"
        if self.algebraic:
            return "EXACT_GENERATING_FUNCTION"
        if self.multiplicative:
            return "EXACT_MULTIPLICATIVE"
        if self.k_automatic:
            return "EXACT_AUTOMATON"
        if self.modular:
            return "EXACT_MODULAR_PATTERN"
        if self.asymptotic:
            return "WEAK_ASYMPTOTIC_BAND"
        return "NO_STRUCTURE"

    def markdown(self) -> str:
        L = ["## Oracle sparks — structure the values suggest (each verified on held-out terms)"]
        if self.closed_form:
            L.append(f"- **polynomial closed form** (degree {self.closed_form.degree}, verified on "
                     f"{self.closed_form.verified_on} held-out): {self.closed_form.as_text()}")
        if self.holonomic:
            L.append(f"- **holonomic recurrence** (order {self.holonomic.order}, deg {self.holonomic.degree}, "
                     f"verified on {self.holonomic.verified_on} held-out): {self.holonomic.as_text()}")
        if self.modular:
            L.append(f"- **modular pattern**: a(n) mod {self.modular.modulus} is periodic {self.modular.residues}")
        if self.polynomial:
            L.append(f"- **non-linear law** (order {self.polynomial.order}, degree {self.polynomial.total_degree}, "
                     f"verified on {self.polynomial.verified_on} held-out): {self.polynomial.as_text()}")
        if self.algebraic:
            L.append(f"- **algebraic generating function** (y-deg {self.algebraic.gf_degree}, x-deg "
                     f"{self.algebraic.x_degree}): {self.algebraic.as_text()}")
        if self.multiplicative:
            L.append(f"- **multiplicative structure** (verified on {self.multiplicative.verified_pairs} coprime "
                     f"pairs): {self.multiplicative.as_text()}")
        if self.k_automatic:
            L.append(f"- **{self.k_automatic.base}-automatic** (verified on {self.k_automatic.verified_on} held-out): "
                     f"{self.k_automatic.as_text()}")
        if self.asymptotic:
            L.append(f"- **asymptotic law** (verified on {self.asymptotic.verified_on} held-out): {self.asymptotic.as_text()}")
        if self.growth_ratio is not None and not self.asymptotic:
            L.append(f"- **asymptotic spark**: a(n+1)/a(n) → ≈ {self.growth_ratio:.4f} (a lead, not a proof)")
        if not self.found_structure:
            L.append("- no low-order structure found — the sequence looks NON-holonomic here; an honest miner "
                     "invents no false recurrence (pivot the solution type instead).")
        return "\n".join(L)


def mine_invariants(oracle: Oracle, n_terms: int = 20, max_order: int = 3, max_degree: int = 2) -> MinedSparks:
    """READ the oracle for structure and return candidate invariants as sparks to explore. Honest: only held-out-
    verified structure is reported; a structureless sequence yields no invariant. This is the judge/oracle turned
    into a SOURCE for the inventor (it breaks the assumption that evaluation can only judge, never inspire)."""
    terms = _terms(oracle, n_terms)
    # the NON-LINEAR / ALGEBRAIC spaces need MORE data than the linear one (their coefficient space is larger and
    # the useful orders are higher) — so pull extra terms when the oracle can supply them. This is what makes the
    # discoverer actually FIND Somos/algebraic laws by default, not only under a hand-tuned call.
    nl_n = max(n_terms, 40)
    closed = guess_polynomial_closed_form(oracle, n_terms=n_terms)          # the MOST desired form — try first
    holo = None if closed else guess_holonomic(oracle, max_order, max_degree, n_terms)
    modu = guess_modular_pattern(oracle, n_terms=n_terms)
    mult = None if (closed or holo) else guess_multiplicative(oracle, n_terms=nl_n)       # AXIS 1: multiplicative
    kaut = None if (closed or holo or mult) else guess_k_automatic(oracle, n_terms=max(nl_n, 64))  # AXIS 3: k-automatic
    exact = closed or holo or mult or kaut
    # non-linear (Somos, order ≤ 4) and algebraic-GF, only when no exact structure explains it yet
    poly = None if exact else guess_polynomial_recurrence(oracle, max_order=4, max_n_degree=1, n_terms=nl_n)
    alg = None if exact else guess_algebraic_gf(oracle, n_terms=nl_n)
    # AXIS 2: asymptotic band — LAST, only when no exact structure at all (a real law where exactness is absent)
    asym = None if (exact or poly or alg) else guess_asymptotic(oracle, n_terms=nl_n)
    ratio = None
    if len(terms) >= 4 and all(terms[i] != 0 for i in range(len(terms) - 3, len(terms))):
        ratio = terms[-1] / terms[-2]
    sparks = []
    if closed:
        sparks.append(f"a(n) is an explicit degree-{closed.degree} polynomial in n — a closed form is in hand")
    if holo:
        sparks.append(f"a holonomic recurrence of order {holo.order} governs the sequence — try to solve/close it")
    if mult:
        sparks.append("the sequence is MULTIPLICATIVE — determined by its values on prime powers (number theory)")
    if kaut:
        sparks.append(f"the sequence is {kaut.base}-AUTOMATIC — generated by an automaton on base-{kaut.base} digits of n")
    if modu:
        sparks.append(f"a(n) mod {modu.modulus} is periodic — a congruence structure to exploit")
    if poly:
        sparks.append(f"a non-linear (Somos-like) law of order {poly.order} governs the sequence — a closed structure to exploit")
    if alg:
        sparks.append(f"the generating function is algebraic (degree {alg.gf_degree}) — solve the polynomial equation for a closed form")
    if asym:
        sparks.append(f"an asymptotic law {asym.form} fits with a certified band — a real growth law where exactness is absent")
    if ratio and not any((closed, holo, mult, kaut, poly, alg, asym)):
        sparks.append(f"the ratio a(n+1)/a(n) ≈ {ratio:.3f} suggests an exponential/asymptotic form to pursue")
    return MinedSparks(holonomic=holo, modular=modu, polynomial=poly, algebraic=alg, closed_form=closed,
                       multiplicative=mult, k_automatic=kaut, asymptotic=asym, growth_ratio=ratio, sparks=sparks)
