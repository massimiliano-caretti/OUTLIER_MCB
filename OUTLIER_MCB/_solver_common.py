"""_solver_common — shared, SAFE plumbing for external prover/CAS backends (opt-in, degrade gracefully).

Every external backend (cvc5, isabelle, pari, vampire, E) follows the SAME contract as z3_backend/lean_backend
(see math_discovery): a callable returning (status, counterexample|None, detail), with .backend_name. This module
holds the parts they share so each stays small and identical in behaviour:

  • `which(name)`      — detect a binary WITHOUT importing anything (shutil.which); absent ⇒ the backend returns
                         TOOL_UNAVAILABLE, never crashes and never force-imports a runtime dependency.
  • `run_tool(argv…)`  — run a tool DETERMINISTICALLY and safely: argv as a LIST (no shell=True, no injection),
                         a hard timeout, captured output. Never raises for a missing binary or a timeout.
  • `ast_to_smtlib`    — compile a Python-infix arithmetic claim ('x**2 + y**2 >= 2*x*y') to an SMT-LIB assertion
                         via the `ast` module (real prefix translation, deterministic). Shared by the SMT backends.

Pure-Python, zero runtime deps. The translation is unit-tested WITHOUT any external binary, so the engineering is
verifiable even where the tool is not installed.
"""
from __future__ import annotations
import ast
import shutil
import subprocess
from typing import Dict, List, Optional, Tuple


def which(name: str) -> Optional[str]:
    """Absolute path of an external binary, or None if it is not on PATH. The single detection point — a backend
    that gets None returns TOOL_UNAVAILABLE (never a crash, never a forced import)."""
    return shutil.which(name)


def run_tool(argv: List[str], stdin_text: Optional[str] = None, timeout_s: float = 30.0) -> Tuple[Optional[int], str, str, bool]:
    """Run `argv` (a LIST — never a shell string) with a hard timeout and captured output. Deterministic and safe:
    no shell, no injection. Returns (returncode|None, stdout, stderr, timed_out). Never raises for a missing binary
    (returncode None) or a timeout (timed_out True)."""
    try:
        p = subprocess.run(argv, input=stdin_text, capture_output=True, text=True, timeout=timeout_s)
        return p.returncode, p.stdout or "", p.stderr or "", False
    except subprocess.TimeoutExpired as e:
        return None, (e.stdout or "" if isinstance(e.stdout, str) else ""), \
               (e.stderr or "" if isinstance(e.stderr, str) else ""), True
    except (FileNotFoundError, OSError) as e:
        return None, "", f"could not execute {argv[:1]}: {e}", False


# ── arithmetic-fragment compiler: Python infix (the same fragment z3_backend evals) → SMT-LIB prefix ──────────
_CMP = {ast.Gt: ">", ast.GtE: ">=", ast.Lt: "<", ast.LtE: "<=", ast.Eq: "=", ast.NotEq: "distinct"}


class _SmtCompiler(ast.NodeVisitor):
    def __init__(self, variables):
        self.vars = set(variables or [])

    def visit(self, node):  # noqa: C901 — a small, explicit dispatch
        if isinstance(node, ast.Expression):
            return self.visit(node.body)
        if isinstance(node, ast.BoolOp):
            op = "and" if isinstance(node.op, ast.And) else "or"
            return f"({op} {' '.join(self.visit(v) for v in node.values)})"
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return f"(not {self.visit(node.operand)})"
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return f"(- {self.visit(node.operand)})"
        if isinstance(node, ast.Compare):
            if len(node.ops) != 1:
                raise ValueError("chained comparisons are not supported")
            op = _CMP.get(type(node.ops[0]))
            if op is None:
                raise ValueError(f"unsupported comparison {type(node.ops[0]).__name__}")
            return f"({op} {self.visit(node.left)} {self.visit(node.comparators[0])})"
        if isinstance(node, ast.BinOp):
            return self._binop(node)
        if isinstance(node, ast.Call):
            fn = getattr(node.func, "id", "")
            args = [self.visit(a) for a in node.args]
            if fn == "And":
                return f"(and {' '.join(args)})"
            if fn == "Or":
                return f"(or {' '.join(args)})"
            if fn == "Not":
                return f"(not {args[0]})"
            if fn == "Implies":
                return f"(=> {args[0]} {args[1]})"
            if fn == "Abs":
                return f"(abs {args[0]})"
            raise ValueError(f"unsupported function {fn!r}")
        if isinstance(node, ast.Name):
            if node.id not in self.vars:
                raise ValueError(f"unknown variable {node.id!r}")
            return node.id
        if isinstance(node, (ast.Constant,)) and isinstance(node.value, bool):
            return "true" if node.value else "false"
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return self._num(node.value)
        if isinstance(node, ast.Num):  # pragma: no cover — py<3.8 compat
            return self._num(node.n)
        raise ValueError(f"unsupported syntax node {type(node).__name__}")

    def _num(self, v):
        if isinstance(v, int) or (isinstance(v, float) and v.is_integer()):
            iv = int(v)
            return f"(- {abs(iv)})" if iv < 0 else str(iv)
        return f"(- {abs(v)})" if v < 0 else repr(v)

    def _binop(self, node):
        l, r = self.visit(node.left), self.visit(node.right)
        if isinstance(node.op, ast.Add):
            return f"(+ {l} {r})"
        if isinstance(node.op, ast.Sub):
            return f"(- {l} {r})"
        if isinstance(node.op, ast.Mult):
            return f"(* {l} {r})"
        if isinstance(node.op, ast.Div):
            return f"(/ {l} {r})"
        if isinstance(node.op, ast.Pow):
            if not (isinstance(node.right, ast.Constant) and isinstance(node.right.value, int) and node.right.value >= 0):
                raise ValueError("only non-negative integer powers are supported")
            k = node.right.value
            if k == 0:
                return "1"
            return "(* " * (k - 1) + " ".join([l] * k) + ")" * (k - 1)
        raise ValueError(f"unsupported operator {type(node.op).__name__}")


def compile_expr_smtlib(expr: str, variables) -> str:
    """Compile ONE Python-infix boolean/arithmetic expression to an SMT-LIB term. Deterministic; raises ValueError
    on anything outside the supported fragment (so a backend degrades to TOOL_LIMIT_UNKNOWN, never a silent wrong term)."""
    tree = ast.parse(expr, mode="eval")
    return _SmtCompiler(variables).visit(tree)


def ast_to_smtlib(claim_expr: str, lhs: str, rhs: str, hypotheses, variables: Dict, domain: str) -> str:
    """Full SMT-LIB script for 'hyps ⇒ claim': declare each variable, assert the hypotheses and the NEGATED claim,
    then (check-sat). unsat ⇒ the claim is proved (∀); sat ⇒ a guaranteed counterexample; unknown ⇒ tool limit.
    Mirrors z3_backend's ¬claim strategy so the SMT backends agree by construction."""
    sort = "Int" if (domain or "real") == "int" else "Real"
    names = list(variables or [])
    decls = "\n".join(f"(declare-const {n} {sort})" for n in names)
    claim = compile_expr_smtlib(claim_expr, names) if claim_expr else \
        f"(= {compile_expr_smtlib(lhs, names)} {compile_expr_smtlib(rhs, names)})"
    asserts = "\n".join(f"(assert {compile_expr_smtlib(h, names)})" for h in (hypotheses or []))
    logic = "QF_NIA" if sort == "Int" else "QF_NRA"
    return (f"(set-logic {logic})\n{decls}\n{asserts}\n(assert (not {claim}))\n(check-sat)\n(get-model)\n").replace("\n\n", "\n")


# ── arithmetic-fragment compiler: Python infix → TPTP TFF (typed first-order with arithmetic; Vampire/E) ──────
_TFF_CMP = {ast.Gt: "$greater", ast.GtE: "$greatereq", ast.Lt: "$less", ast.LtE: "$lesseq"}


class _TffCompiler(ast.NodeVisitor):
    def __init__(self, variables):
        self.map = {n: "V_" + n.upper() for n in (variables or [])}   # TPTP variables are uppercase

    def visit(self, node):  # noqa: C901
        if isinstance(node, ast.Expression):
            return self.visit(node.body)
        if isinstance(node, ast.BoolOp):
            op = " & " if isinstance(node.op, ast.And) else " | "
            return "(" + op.join(self.visit(v) for v in node.values) + ")"
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return f"(~ {self.visit(node.operand)})"
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return f"$uminus({self.visit(node.operand)})"
        if isinstance(node, ast.Compare):
            if len(node.ops) != 1:
                raise ValueError("chained comparisons are not supported")
            op = type(node.ops[0])
            l, r = self.visit(node.left), self.visit(node.comparators[0])
            if op is ast.Eq:
                return f"({l} = {r})"
            if op is ast.NotEq:
                return f"({l} != {r})"
            fn = _TFF_CMP.get(op)
            if fn is None:
                raise ValueError(f"unsupported comparison {op.__name__}")
            return f"{fn}({l},{r})"
        if isinstance(node, ast.BinOp):
            return self._binop(node)
        if isinstance(node, ast.Call):
            fn = getattr(node.func, "id", "")
            a = [self.visit(x) for x in node.args]
            if fn == "And":
                return "(" + " & ".join(a) + ")"
            if fn == "Or":
                return "(" + " | ".join(a) + ")"
            if fn == "Not":
                return f"(~ {a[0]})"
            if fn == "Implies":
                return f"({a[0]} => {a[1]})"
            raise ValueError(f"unsupported function {fn!r} in TPTP")
        if isinstance(node, ast.Name):
            if node.id not in self.map:
                raise ValueError(f"unknown variable {node.id!r}")
            return self.map[node.id]
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            v = node.value
            iv = int(v) if (isinstance(v, int) or float(v).is_integer()) else v
            return f"$uminus({abs(iv)})" if (isinstance(iv, int) and iv < 0) else str(iv)
        raise ValueError(f"unsupported syntax node {type(node).__name__} in TPTP")

    def _binop(self, node):
        l, r = self.visit(node.left), self.visit(node.right)
        if isinstance(node.op, ast.Add):
            return f"$sum({l},{r})"
        if isinstance(node.op, ast.Sub):
            return f"$difference({l},{r})"
        if isinstance(node.op, ast.Mult):
            return f"$product({l},{r})"
        if isinstance(node.op, ast.Div):
            return f"$quotient({l},{r})"
        if isinstance(node.op, ast.Pow):
            if not (isinstance(node.right, ast.Constant) and isinstance(node.right.value, int) and node.right.value >= 1):
                raise ValueError("only positive integer powers are supported")
            out = l
            for _ in range(node.right.value - 1):
                out = f"$product({out},{l})"
            return out
        raise ValueError(f"unsupported operator {type(node.op).__name__} in TPTP")


def ast_to_tptp(claim_expr: str, lhs: str, rhs: str, hypotheses, variables: Dict, domain: str) -> str:
    """A TPTP TFF conjecture for '∀vars. hyps ⇒ claim' (arithmetic via $int/$real; Vampire/E decide it). Typed so
    arithmetic is real, unlike plain FOF. Deterministic; raises ValueError outside the supported fragment."""
    typ = "$int" if (domain or "real") == "int" else "$real"
    names = list(variables or [])
    comp = _TffCompiler(names)
    binders = ",".join(f"{comp.map[n]}:{typ}" for n in names) or "X:$int"
    claim = comp.visit(ast.parse(claim_expr, mode="eval")) if claim_expr else \
        f"({comp.visit(ast.parse(lhs, mode='eval'))} = {comp.visit(ast.parse(rhs, mode='eval'))})"
    hyp_terms = [comp.visit(ast.parse(h, mode="eval")) for h in (hypotheses or [])]
    body = f"({' & '.join(hyp_terms)} => {claim})" if hyp_terms else claim
    return f"tff(goal, conjecture, ! [{binders}]: {body})."


# ── arithmetic + number-theory compiler: Python infix → PARI/GP infix (passes CAS functions THROUGH) ──────────
_GP_CMP = {ast.Gt: ">", ast.GtE: ">=", ast.Lt: "<", ast.LtE: "<=", ast.Eq: "==", ast.NotEq: "!="}


class _GpCompiler(ast.NodeVisitor):
    """Unlike the SMT/TPTP compilers, this PASSES arbitrary function calls THROUGH (isprime, nextprime, moebius,
    sigma, …) — that is the whole point of a number-theory CAS backend. Variables are used verbatim."""
    def visit(self, node):  # noqa: C901
        if isinstance(node, ast.Expression):
            return self.visit(node.body)
        if isinstance(node, ast.BoolOp):
            op = " && " if isinstance(node.op, ast.And) else " || "
            return "(" + op.join(self.visit(v) for v in node.values) + ")"
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return f"(!{self.visit(node.operand)})"
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return f"(-{self.visit(node.operand)})"
        if isinstance(node, ast.Compare):
            if len(node.ops) != 1:
                raise ValueError("chained comparisons are not supported")
            op = _GP_CMP.get(type(node.ops[0]))
            if op is None:
                raise ValueError(f"unsupported comparison {type(node.ops[0]).__name__}")
            return f"({self.visit(node.left)} {op} {self.visit(node.comparators[0])})"
        if isinstance(node, ast.BinOp):
            l, r = self.visit(node.left), self.visit(node.right)
            sym = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/", ast.Pow: "^", ast.Mod: "%"}.get(type(node.op))
            if sym is None:
                raise ValueError(f"unsupported operator {type(node.op).__name__}")
            return f"({l} {sym} {r})"
        if isinstance(node, ast.Call):
            fn = getattr(node.func, "id", "")
            args = ", ".join(self.visit(a) for a in node.args)
            if fn == "And":
                return "(" + " && ".join(self.visit(a) for a in node.args) + ")"
            if fn == "Or":
                return "(" + " || ".join(self.visit(a) for a in node.args) + ")"
            if fn == "Not":
                return f"(!{self.visit(node.args[0])})"
            if fn == "Abs":
                return f"abs({self.visit(node.args[0])})"
            if not fn.isidentifier():
                raise ValueError("only named function calls are allowed")
            return f"{fn}({args})"                              # isprime(...), nextprime(...), … pass through to GP
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return repr(node.value)
        raise ValueError(f"unsupported syntax node {type(node).__name__} in GP")


def compile_expr_gp(expr: str) -> str:
    """Compile ONE Python-infix expression to PARI/GP, passing number-theory functions through. Deterministic;
    raises ValueError outside the supported fragment."""
    return _GpCompiler().visit(ast.parse(expr, mode="eval"))
