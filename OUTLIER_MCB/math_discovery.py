"""math_discovery — honest mathematical discovery: conjecture → counterexample → empirical → proof.

theorem_sketch produces falsifiable conjectures, not theorems. This module takes the next honest step
WITHOUT overclaiming: a statement is only `FORMALLY_PROVED` when a real CAS/prover confirms it; otherwise
it is a `SKETCH`, killed by a `COUNTEREXAMPLE_FOUND`, or merely `EMPIRICALLY_SUPPORTED` (passed sampling —
evidence, never proof). The zero-dependency default does property/counterexample testing; SymPy (optional,
lazy) adds symbolic identity proof and lambdified sampling. No SymPy ⇒ the formal path reports
`TOOL_UNAVAILABLE` and the result honestly caps at `EMPIRICALLY_SUPPORTED`.

The rule the engine demanded of itself (see the `meta` pack): never call 'theorem' what is not proved.
"""
from __future__ import annotations
import ast
import math
import operator
import random
import re
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Callable, Dict, List, Optional, Tuple

MATH_STATES = ("SKETCH", "COUNTEREXAMPLE_FOUND", "EMPIRICALLY_SUPPORTED", "FORMALLY_PROVED",
               "FORMALLY_DISPROVED", "VACUOUS_DOMAIN", "LEAN_EMITTED", "TOOL_LIMIT_UNKNOWN", "TOOL_UNAVAILABLE")


@dataclass
class Conjecture:
    """A candidate proposition. Give it a numeric `predicate(**vars)->bool` (zero-dep), and/or `lhs`/`rhs`
    expression strings for the SymPy identity path, and/or — for the Z3 backend — a `claim_expr` (a Boolean
    relation like 'x**2 + y**2 >= 2*x*y') and `hypotheses` (preconditions like 'x > 0'). `variables` maps
    each name to a sampling range; `domain` is 'real' or 'int' for the solver."""
    statement: str
    lhs: str = ""
    rhs: str = ""
    variables: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    claim_expr: str = ""
    hypotheses: List[str] = field(default_factory=list)
    domain: str = "real"


@dataclass
class Counterexample:
    assignment: Dict[str, float]
    detail: str = ""


@dataclass
class ProofAttempt:
    method: str                  # 'sympy' | 'none' | a prover name
    status: str                  # FORMALLY_PROVED | TOOL_UNAVAILABLE | NOT_AN_IDENTITY | ATTEMPTED
    detail: str = ""


@dataclass
class MathDiscoveryResult:
    conjecture: Conjecture
    status: str                  # one of MATH_STATES
    counterexample: Optional[Counterexample] = None
    samples_passed: int = 0
    samples_total: int = 0
    proof: Optional[ProofAttempt] = None
    note: str = ""

    def markdown(self) -> str:
        L = [f"### Math discovery — {self.status}: «{self.conjecture.statement}»"]
        if self.counterexample is not None:
            L.append(f"- **counterexample:** {self.counterexample.assignment} — {self.counterexample.detail}")
        if self.samples_total:
            L.append(f"- **empirical:** {self.samples_passed}/{self.samples_total} random samples held "
                     f"(evidence, NOT proof)")
        if self.proof is not None:
            L.append(f"- **proof attempt ({self.proof.method}): {self.proof.status}** — {self.proof.detail}")
        if self.status == "EMPIRICALLY_SUPPORTED":
            L.append("- ⚠ EMPIRICALLY_SUPPORTED is not a theorem: a CAS/prover must confirm it to be FORMALLY_PROVED.")
        if self.note:
            L.append(f"- {self.note}")
        return "\n".join(L)


def _ranges(conj: Conjecture) -> Dict[str, Tuple[float, float]]:
    return conj.variables or {}


_SIMPLE_BOUND = re.compile(r"^\s*([A-Za-z_]\w*)\s*(<=|>=|<|>)\s*(-?\d+(?:/\d+)?(?:\.\d+)?)\s*$")


def _as_fraction(value) -> Optional[Fraction]:
    try:
        return Fraction(str(value))
    except Exception:
        return None


def hypothesis_domain_witness(conj: Conjecture) -> Optional[Dict[str, str]]:
    """Return a simple witness for univariate bound hypotheses, or None when they are contradictory.

    Unknown/non-bound hypotheses are ignored rather than rejected; the solver remains responsible for the
    full logic. This gate only catches the cheap dangerous case where the numeric box plus simple hypotheses
    are already empty, which would make any implication vacuously true.
    """
    if not conj.variables:
        return {}
    intervals = {}
    for name, bounds in conj.variables.items():
        lo = _as_fraction(bounds[0])
        hi = _as_fraction(bounds[1])
        if lo is None or hi is None:
            continue
        intervals[name] = [lo, False, hi, False]  # lower, lower_open, upper, upper_open
    saw_simple = False
    for hyp in conj.hypotheses or []:
        m = _SIMPLE_BOUND.match(str(hyp))
        if not m:
            continue
        var, op, raw = m.groups()
        if var not in intervals:
            continue
        val = _as_fraction(raw)
        if val is None:
            continue
        saw_simple = True
        lo, lo_open, hi, hi_open = intervals[var]
        if op in (">", ">="):
            open_bound = (op == ">")
            if val > lo or (val == lo and open_bound and not lo_open):
                lo, lo_open = val, open_bound
        else:
            open_bound = (op == "<")
            if val < hi or (val == hi and open_bound and not hi_open):
                hi, hi_open = val, open_bound
        if lo > hi or (lo == hi and (lo_open or hi_open)):
            return None
        intervals[var] = [lo, lo_open, hi, hi_open]
    if not saw_simple:
        return {}
    return {var: str((lo + hi) / 2 if lo != hi else lo) for var, (lo, _lo_open, hi, _hi_open) in intervals.items()}


def hypothesis_domain_vacuous(conj: Conjecture) -> bool:
    """True when the simple numeric part of the hypotheses has no witness."""
    return bool(conj.hypotheses) and hypothesis_domain_witness(conj) is None


def empirical_test(predicate: Callable, variables: Dict[str, Tuple[float, float]],
                   samples: int = 200, seed: int = 0) -> Tuple[Optional[Counterexample], int, int]:
    """Sample random assignments and look for a counterexample. Returns (counterexample|None, passed, total).
    A predicate that raises on an assignment is treated as 'not satisfied here' (a domain hint), not a pass."""
    rng = random.Random(seed)
    names = list(variables)
    passed = 0
    for _ in range(samples):
        assign = {n: rng.uniform(*variables[n]) for n in names}
        try:
            ok = bool(predicate(**assign))
        except Exception as exc:
            return Counterexample(assign, f"predicate undefined/raised: {exc}"), passed, samples
        if not ok:
            return Counterexample(assign, "predicate false here"), passed, samples
        passed += 1
    return None, passed, samples


def _sympy_prove(conj: Conjecture):
    """Try SymPy: (proof_attempt, lambdified_predicate|None). FORMALLY_PROVED iff simplify(lhs-rhs)==0."""
    try:
        import sympy
    except ImportError:
        return ProofAttempt("sympy", "TOOL_UNAVAILABLE", "SymPy not installed: `pip install sympy`."), None
    try:
        syms = {n: sympy.Symbol(n) for n in (conj.variables or {})}
        lhs = sympy.sympify(conj.lhs, locals=syms)
        rhs = sympy.sympify(conj.rhs, locals=syms)
        diff = sympy.simplify(lhs - rhs)
        free = sorted({s.name for s in (lhs.free_symbols | rhs.free_symbols)})
        pred = None
        if free:
            f = sympy.lambdify([sympy.Symbol(n) for n in free], lhs - rhs, "math")
            pred = lambda **kw: abs(f(*[kw[n] for n in free])) < 1e-9   # noqa: E731
        if diff == 0:
            return ProofAttempt("sympy", "FORMALLY_PROVED", f"simplify(lhs - rhs) = 0 over {free or 'constants'}."), pred
        return ProofAttempt("sympy", "NOT_AN_IDENTITY", f"simplify(lhs - rhs) = {diff} ≠ 0."), pred
    except Exception as exc:
        return ProofAttempt("sympy", "ATTEMPTED", f"SymPy could not decide: {exc}"), None


def z3_backend(timeout_ms: int = 5000):
    """An OPTIONAL prover backend (Z3 SMT solver). It DECIDES — proves or guarantees a counterexample for —
    statements in decidable theories (linear arithmetic, and Z3's nonlinear heuristics) that SymPy's identity
    check cannot: inequalities, statements under hypotheses, logical combinations. It proves ∀x.P(x) by
    showing ∃x.¬P(x) is unsatisfiable; a SAT result returns a GUARANTEED counterexample. Returns
    (status, counterexample|None, detail). Requires `pip install z3-solver`; absent ⇒ TOOL_UNAVAILABLE
    (never a crash). Honest about its frontier: transcendental/undecidable fragments ⇒ TOOL_LIMIT_UNKNOWN."""
    def prove(conj: Conjecture):
        try:
            import z3
        except ImportError:
            return "TOOL_UNAVAILABLE", None, "Z3 not installed: `pip install z3-solver`."
        names = list(conj.variables or {})
        mk = z3.Int if (conj.domain or "real") == "int" else z3.Real
        env = {n: mk(n) for n in names}
        env.update({"And": z3.And, "Or": z3.Or, "Not": z3.Not, "Implies": z3.Implies, "Abs": lambda e: z3.If(e >= 0, e, -e)})
        try:
            if conj.claim_expr:
                claim = eval(conj.claim_expr, {"__builtins__": {}}, env)   # noqa: S307 — math expr, no builtins
            else:
                claim = (eval(conj.lhs, {"__builtins__": {}}, env) == eval(conj.rhs, {"__builtins__": {}}, env))
            hyps = [eval(h, {"__builtins__": {}}, env) for h in (conj.hypotheses or [])]
        except Exception as exc:
            return "TOOL_LIMIT_UNKNOWN", None, f"could not parse the claim into Z3: {exc}"
        solver = z3.Solver()
        solver.set("timeout", timeout_ms)
        for h in hyps:
            solver.add(h)
        solver.add(z3.Not(claim))                          # prove hyps ⇒ claim  ⟺  UNSAT(hyps ∧ ¬claim)
        result = solver.check()
        if result == z3.unsat:
            return "FORMALLY_PROVED", None, "Z3: the negation is unsatisfiable under the hypotheses → proved."
        if result == z3.sat:
            model = solver.model()
            ce = {n: str(model.eval(env[n], model_completion=True)) for n in names}
            return "FORMALLY_DISPROVED", ce, f"Z3 found a guaranteed counterexample: {ce}"
        return "TOOL_LIMIT_UNKNOWN", None, "Z3 returned 'unknown' (likely a non-decidable / nonlinear fragment)."
    prove.backend_name = "z3"
    return prove


# ── Lean: emit a FORMAL statement (and optionally let Lean check a proof) ────────────────────────────
def _to_lean_expr(s: str) -> str:
    """Translate a Python-style relation into Lean 4 surface syntax (best-effort, for arithmetic relations)."""
    return (s.replace("**", "^").replace(">=", "≥").replace("<=", "≤").replace("!=", "≠").replace("==", "="))


def lean_emit(conjecture: Conjecture, proof: str = "sorry", name: str = "conjecture") -> str:
    """Emit the conjecture as a Lean 4 theorem. Pure, zero-dependency, ALWAYS available — it produces the
    FORMAL STATEMENT (a sketch with `sorry`, or with a tactic to try). Emission is NOT proof: a Lean
    `theorem ... := sorry` is a formal SKETCH a human (or Mathlib automation) must still close."""
    typ = "ℤ" if (conjecture.domain or "real") == "int" else "ℝ"
    names = list(conjecture.variables or {}) or ["x"]
    binders = f"({' '.join(names)} : {typ})"
    hyps = "".join(f" (h{i} : {_to_lean_expr(h)})" for i, h in enumerate(conjecture.hypotheses or []))
    claim = (_to_lean_expr(conjecture.claim_expr) if conjecture.claim_expr
             else f"{_to_lean_expr(conjecture.lhs)} = {_to_lean_expr(conjecture.rhs)}")
    body = proof if proof.strip().startswith(("sorry", "by")) else f"by {proof}"
    return (f"import Mathlib\n\n-- {conjecture.statement}\n"
            f"theorem {name} {binders}{hyps} : {claim} := {body}\n")


def lean_backend(tactic: str = "nlinarith", lean_cmd: str = "lean", timeout: int = 120):
    """An OPTIONAL backend that EMITS a Lean theorem and, if Lean is installed, tries to CHECK it with a
    tactic. Returns (status, None, detail) where detail carries the emitted source. Honest states:
      FORMALLY_PROVED — Lean accepted a `sorry`-free proof (the only real proof);
      LEAN_EMITTED    — the formal statement was produced but not machine-closed (a SKETCH, not a proof);
      TOOL_UNAVAILABLE— Lean is not installed (emission still returned in detail).
    Lean + Mathlib are heavy and project-bound, so without a configured environment this stays at emission."""
    import shutil

    def prove(conj: Conjecture):
        emitted_sketch = lean_emit(conj, proof="sorry")
        if shutil.which(lean_cmd) is None:
            return "TOOL_UNAVAILABLE", None, "Lean not installed (`lean`/`lake` not on PATH).\n" + emitted_sketch
        source = lean_emit(conj, proof=f"by {tactic}")
        import subprocess
        import tempfile
        import os
        path = ""
        try:
            with tempfile.NamedTemporaryFile("w", suffix=".lean", delete=False) as fh:
                fh.write(source)
                path = fh.name
            proc = subprocess.run([lean_cmd, path], capture_output=True, text=True, timeout=timeout)
            ok = proc.returncode == 0 and "sorry" not in proc.stdout.lower()
            tail = (proc.stdout + proc.stderr)[-400:]
            if ok:
                return "FORMALLY_PROVED", None, f"Lean checked the proof (`by {tactic}`).\n{source}"
            return "LEAN_EMITTED", None, f"Lean could not close it with `by {tactic}` — formal SKETCH only.\n{tail}\n{source}"
        except Exception as exc:
            return "LEAN_EMITTED", None, f"Lean run failed ({exc}); statement emitted as a SKETCH.\n{emitted_sketch}"
        finally:
            if path and os.path.exists(path):
                os.unlink(path)
    prove.backend_name = "lean"
    return prove


def investigate_conjecture(conjecture: Conjecture, predicate: Optional[Callable] = None,
                           samples: int = 200, seed: int = 0, use_sympy: bool = True,
                           backend: Optional[Callable] = None) -> MathDiscoveryResult:
    """Investigate a conjecture honestly. Order: (0) a `backend` solver (z3_backend) if given and the
    conjecture carries a claim — proved / guaranteed-counterexample is the strongest verdict; (1) SymPy
    identity proof if lhs/rhs; (2) otherwise sample for a COUNTEREXAMPLE (the given `predicate` or a
    SymPy-lambdified one). All samples holding ⇒ EMPIRICALLY_SUPPORTED (evidence, not proof). No predicate
    and no provable identity ⇒ SKETCH. A solver's TOOL_UNAVAILABLE / TOOL_LIMIT_UNKNOWN falls through here."""
    proof = None
    if hypothesis_domain_vacuous(conjecture):
        return MathDiscoveryResult(
            conjecture=conjecture, status="VACUOUS_DOMAIN",
            note="the stated hypotheses have no witness in the declared variable box; no theorem/proof credit.")
    # 0) the solver (strongest): decides inequalities / hypotheses / identities SymPy cannot
    if backend is not None and (conjecture.claim_expr or (conjecture.lhs and conjecture.rhs)):
        status, ce, detail = backend(conjecture)
        proof = ProofAttempt(getattr(backend, "backend_name", "solver"), status, detail)
        if status == "FORMALLY_PROVED":
            return MathDiscoveryResult(conjecture=conjecture, status="FORMALLY_PROVED", proof=proof,
                                       note="a solver decided the statement under its hypotheses.")
        if status == "FORMALLY_DISPROVED":
            return MathDiscoveryResult(conjecture=conjecture, status="FORMALLY_DISPROVED",
                                       counterexample=Counterexample(ce or {}, "a solver's guaranteed model"),
                                       proof=proof, note="a solver found a GUARANTEED counterexample (not sampled).")

    if use_sympy and conjecture.lhs and conjecture.rhs:
        sym_proof, sym_pred = _sympy_prove(conjecture)
        proof = proof if (proof and proof.status not in ("TOOL_UNAVAILABLE", "TOOL_LIMIT_UNKNOWN")) else sym_proof
        if sym_proof.status == "FORMALLY_PROVED":
            return MathDiscoveryResult(conjecture=conjecture, status="FORMALLY_PROVED", proof=sym_proof,
                                       note="a CAS confirmed the identity symbolically.")
        if predicate is None:
            predicate = sym_pred                              # fall back to the lambdified diff for sampling

    if predicate is None:
        # a Lean emission is a FORMAL sketch — more informative than a bare SKETCH (the statement exists).
        emitted = bool(proof and proof.status == "LEAN_EMITTED")
        return MathDiscoveryResult(conjecture=conjecture, status="LEAN_EMITTED" if emitted else "SKETCH",
                                   proof=proof,
                                   note=("a formal Lean statement was emitted but not machine-closed — a human "
                                         "or Mathlib automation must finish the proof." if emitted else
                                         "no predicate and no provable identity — give a predicate or lhs/rhs to test."))

    ce, passed, total = empirical_test(predicate, _ranges(conjecture) or {"x": (-5.0, 5.0)}, samples, seed)
    if ce is not None:
        return MathDiscoveryResult(conjecture=conjecture, status="COUNTEREXAMPLE_FOUND", counterexample=ce,
                                   samples_passed=passed, samples_total=total, proof=proof,
                                   note="a single counterexample refutes the conjecture.")
    note = "passed sampling; NOT a proof."
    if proof is not None and proof.status == "TOOL_UNAVAILABLE":
        note += " SymPy unavailable, so the formal path could not run — capped at EMPIRICALLY_SUPPORTED."
    return MathDiscoveryResult(conjecture=conjecture, status="EMPIRICALLY_SUPPORTED",
                               samples_passed=passed, samples_total=total, proof=proof, note=note)


# ── F4: settle a partial LEMMA externally (never the parent conjecture) ───────────────────────────────
# The win is not "prove the conjecture" — it is a formally/exhaustively settled LEMMA that advances the
# frontier. settle_lemma returns a certificate whose status is one of LEMMA_STATES; only LEMMA_CERTIFIED
# statuses count as a real certificate (so FrontierLedger accepts them). It NEVER returns PROVED on a
# parent problem — only on the decidable lemma it was handed.
LEMMA_CERTIFIED = ("LEAN_CHECKED", "ISABELLE_CHECKED", "Z3_PROVED", "CVC5_PROVED",
                   "VAMPIRE_PROVED", "E_PROVED", "NUMERIC_VERIFIED")
LEMMA_STATES = LEMMA_CERTIFIED + ("Z3_REFUTED", "NUMERIC_REFUTED", "UNKNOWN_TIMEOUT")

# backend_name → the positive-proof certificate it earns (settle_lemma maps FORMALLY_PROVED through this). A
# finite computational verification (PARI/GP) is a proof of a finite domain → NUMERIC_VERIFIED (per certificates).
_PROVED_CERT = {"lean": "LEAN_CHECKED", "isabelle": "ISABELLE_CHECKED", "z3": "Z3_PROVED", "cvc5": "CVC5_PROVED",
                "vampire": "VAMPIRE_PROVED", "e": "E_PROVED", "eprover": "E_PROVED",
                "pari": "NUMERIC_VERIFIED", "sage": "NUMERIC_VERIFIED", "portfolio": "Z3_PROVED"}
# backend_name → the refutation status when a GUARANTEED counterexample is found (a finite/model refutation).
_REFUTED_CERT = {"z3": "Z3_REFUTED", "cvc5": "Z3_REFUTED", "vampire": "Z3_REFUTED", "e": "Z3_REFUTED",
                 "eprover": "Z3_REFUTED", "isabelle": "Z3_REFUTED", "lean": "Z3_REFUTED",
                 "pari": "NUMERIC_REFUTED", "sage": "NUMERIC_REFUTED", "portfolio": "Z3_REFUTED"}


@dataclass
class LemmaCertificate:
    """The external settlement of a single lemma. `status` ∈ LEMMA_STATES; `certified` is True only for a real
    external proof (Lean/Z3) or an EXHAUSTIVE finite-domain numeric check — never for sampling, never for the
    parent conjecture. Carries a counterexample when refuted, for the next-assumption loop."""
    status: str
    detail: str = ""
    counterexample: Optional[Dict] = None
    method: str = ""

    @property
    def certified(self) -> bool:
        return self.status in LEMMA_CERTIFIED

    def markdown(self) -> str:
        head = f"### Lemma settlement — {self.status} (via {self.method or 'n/a'})"
        body = [f"- {self.detail}"]
        if self.counterexample is not None:
            body.append(f"- counterexample: {self.counterexample}")
        if self.certified:
            body.append("- this certifies the LEMMA only — the parent conjecture remains CONJECTURE.")
        return "\n".join([head] + body)


def _exhaustive_numeric(lemma: Conjecture, predicate: Optional[Callable],
                        max_points: int = 1_000_000) -> Optional[LemmaCertificate]:
    """Exhaustively check `predicate` over the FINITE integer box `lemma.variables`. Exhaustive over a finite
    domain is a real certificate (unlike sampling). Returns None if there is no numeric path (no predicate/vars);
    UNKNOWN_TIMEOUT if the box is empty or too large to enumerate."""
    import itertools
    import math as _math
    names = list(lemma.variables or {})
    if not names or predicate is None:
        return None
    ranges, total = [], 1
    for n in names:
        lo, hi = lemma.variables[n]
        lo, hi = int(_math.ceil(lo)), int(_math.floor(hi))
        if hi < lo:
            return LemmaCertificate("UNKNOWN_TIMEOUT", f"empty integer range for '{n}' → not settle-able", method="exhaustive_numeric")
        ranges.append((n, lo, hi))
        total *= (hi - lo + 1)
        if total > max_points:
            return LemmaCertificate("UNKNOWN_TIMEOUT",
                                    f"integer domain too large to settle exhaustively ({total} > {max_points})",
                                    method="exhaustive_numeric")
    witness_count = 0
    hypothesis_predicate = getattr(predicate, "_outlier_hypothesis_predicate", None)
    for combo in itertools.product(*[range(lo, hi + 1) for _, lo, hi in ranges]):
        assign = dict(zip(names, combo))
        try:
            if hypothesis_predicate is not None and not bool(hypothesis_predicate(**assign)):
                continue
            witness_count += 1
            ok = bool(predicate(**assign))
        except Exception as exc:
            return LemmaCertificate("NUMERIC_REFUTED", f"predicate raised at {assign}: {exc}",
                                    counterexample=assign, method="exhaustive_numeric")
        if not ok:
            return LemmaCertificate("NUMERIC_REFUTED", f"predicate false at {assign}",
                                    counterexample=assign, method="exhaustive_numeric")
    if hypothesis_predicate is not None and witness_count == 0:
        return LemmaCertificate("UNKNOWN_TIMEOUT", "hypotheses have no witness in the finite integer box",
                                method="exhaustive_numeric")
    checked = witness_count if hypothesis_predicate is not None else total
    return LemmaCertificate("NUMERIC_VERIFIED", f"exhaustive over {checked} relevant integer point(s) — all held",
                            method="exhaustive_numeric")


_BIN_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
            ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
            ast.Pow: operator.pow}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg, ast.Not: operator.not_}
_CMP_OPS = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt, ast.LtE: operator.le,
            ast.Gt: operator.gt, ast.GtE: operator.ge}
_SAFE_FUNCS = {"abs": abs, "min": min, "max": max, "sqrt": math.sqrt}


def _finite_integer_box(conj: Conjecture) -> bool:
    if not conj.variables:
        return False
    for lo, hi in conj.variables.values():
        if not (math.isfinite(float(lo)) and math.isfinite(float(hi))):
            return False
    return True


def _predicate_from_claim_expr(conj: Conjecture) -> Optional[Callable]:
    """Compile a small arithmetic Boolean claim into a predicate for exhaustive finite-box settlement.
    This is a fallback when external SMT tools are unavailable; it yields only NUMERIC_* certificates over the
    declared finite domain, never a universal proof."""
    if not conj.claim_expr or not _finite_integer_box(conj):
        return None
    expr = conj.claim_expr.replace("&&", " and ").replace("||", " or ")
    try:
        tree = ast.parse(expr, mode="eval")
        hyp_trees = [ast.parse(str(h).replace("&&", " and ").replace("||", " or "), mode="eval")
                     for h in (conj.hypotheses or [])]
    except SyntaxError:
        return None
    names = set(conj.variables)

    def ev(node, env):
        if isinstance(node, ast.Expression):
            return ev(node.body, env)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float, bool)):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in env:
                return env[node.id]
            raise ValueError(f"unknown symbol {node.id!r}")
        if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
            return _BIN_OPS[type(node.op)](ev(node.left, env), ev(node.right, env))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
            return _UNARY_OPS[type(node.op)](ev(node.operand, env))
        if isinstance(node, ast.BoolOp):
            vals = [bool(ev(v, env)) for v in node.values]
            if isinstance(node.op, ast.And):
                return all(vals)
            if isinstance(node.op, ast.Or):
                return any(vals)
        if isinstance(node, ast.Compare):
            left = ev(node.left, env)
            for op, comp in zip(node.ops, node.comparators):
                right = ev(comp, env)
                fn = _CMP_OPS.get(type(op))
                if fn is None or not fn(left, right):
                    return False
                left = right
            return True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _SAFE_FUNCS:
            return _SAFE_FUNCS[node.func.id](*[ev(a, env) for a in node.args])
        raise ValueError(f"unsupported expression node {type(node).__name__}")

    # Refuse expressions mentioning names outside the declared variables / safe functions.
    for parsed in [tree] + hyp_trees:
        for n in ast.walk(parsed):
            if isinstance(n, ast.Name) and n.id not in names and n.id not in _SAFE_FUNCS:
                return None

    def hypotheses_hold(**kw):
        return all(bool(ev(h, kw)) for h in hyp_trees)

    def pred(**kw):
        return (not hypotheses_hold(**kw)) or bool(ev(tree, kw))

    if hyp_trees:
        pred._outlier_hypothesis_predicate = hypotheses_hold

    return pred


def settle_lemma(lemma: Conjecture, predicate: Optional[Callable] = None, backend=None) -> LemmaCertificate:
    """Settle ONE lemma by an EXTERNAL resolver, never the parent conjecture. Order: a given `backend`
    (z3_backend()/lean_backend(), opt-in) first; on PROVED → Z3_PROVED/LEAN_CHECKED, on DISPROVED → Z3_REFUTED
    (+counterexample). If no backend or the backend can't decide, fall back to an EXHAUSTIVE numeric check over
    a finite integer domain (zero-dep, deterministic). Anything undecided ⇒ UNKNOWN_TIMEOUT. The status is the
    evidence FrontierLedger consumes; only LEMMA_CERTIFIED advances a frontier."""
    if hypothesis_domain_vacuous(lemma):
        return LemmaCertificate("UNKNOWN_TIMEOUT", "hypotheses have no witness in the declared variable box",
                                method="domain_witness")
    if backend is not None:
        status, ce, detail = backend(lemma)
        # a portfolio mutates its backend_name to the winning solver during the call, so the certificate carries
        # the REAL prover that decided it (CVC5_PROVED, ISABELLE_CHECKED, …), not a generic label.
        name = getattr(backend, "backend_name", "solver")
        if status == "FORMALLY_PROVED":
            return LemmaCertificate(_PROVED_CERT.get(name, "Z3_PROVED"), detail, method=name)
        if status == "FORMALLY_DISPROVED":
            return LemmaCertificate(_REFUTED_CERT.get(name, "Z3_REFUTED"), detail, counterexample=ce, method=name)
        # TOOL_UNAVAILABLE / TOOL_LIMIT_UNKNOWN → try the zero-dep numeric path below
    if predicate is None:
        predicate = _predicate_from_claim_expr(lemma)
    numeric = _exhaustive_numeric(lemma, predicate)
    if numeric is not None:
        return numeric
    return LemmaCertificate("UNKNOWN_TIMEOUT",
                            "no decidable path: provide a prover backend, or a finite integer domain + predicate",
                            method="none")
