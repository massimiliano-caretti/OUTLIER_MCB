"""aesthetics — non-homeostatic intrinsic motivation: drive creativity toward BEAUTY, measured OBJECTIVELY on
the artifact's formal structure, never by a self-declared 'I like it' (Point 4).

A genius is pulled not only by correctness but by elegance — symmetry, simplicity, surprise. To let that guide
the engine WITHOUT letting it lie to itself, every aesthetic score here is a PURE FUNCTION of the artifact's
abstract syntax tree (Python-expression AST): deterministic, reproducible, grounded in measurable structure.
  • measure_symmetry   — numerical invariance under swapping pairs of variables (a+b is symmetric, a−b is not);
  • measure_simplicity — minimum description length: fewer AST nodes ⇒ simpler ⇒ higher;
  • measure_surprise   — structural distance from a CONTEXT corpus (an artifact that reuses only familiar
                          structure is unsurprising; a genuinely new operator/shape is surprising).
elegance_score returns the vector AND a scalar mean. A protected invariant locks their OBJECTIVITY (same input →
same score; more nodes ⇒ not-more-simple; a symmetric form scores higher symmetry than an asymmetric one).

CRUCIAL (and a deliberate correction to the plan): elegance is added as ANOTHER Pareto dimension — it is NOT a
licence to loosen pareto_improves. A change is still accepted only if it regresses NO dimension (hard OR
aesthetic) and improves at least one. Beauty never buys a performance regression — that would break the
non-negotiable 'never regress'. Deterministic, zero-dependency (Python's `ast`).
"""
from __future__ import annotations
import ast
from typing import Dict, List, Optional, Sequence


def _parse(expr: str) -> ast.AST:
    return ast.parse(expr, mode="eval")


def _nodes(tree: ast.AST) -> int:
    return sum(1 for _ in ast.walk(tree))


def _variables(tree: ast.AST) -> List[str]:
    return sorted({n.id for n in ast.walk(tree) if isinstance(n, ast.Name)})


def _operators(tree: ast.AST) -> List[str]:
    # BUGFIX: the operator KIND lives in n.op (Add/Sub/Mult/Div/Pow/Mod/USub…), not in type(n).__name__ (which
    # is always 'BinOp'/'UnaryOp'). The old code made every binary expression share the operator set {'BinOp'},
    # so measure_surprise was blind to which operators differed. Now it reads the real operator.
    return sorted(type(n.op).__name__ for n in ast.walk(tree) if isinstance(n, (ast.BinOp, ast.UnaryOp)))


_SAFE = {"__builtins__": {}}


def _eval(expr: str, env: Dict[str, float]) -> Optional[float]:
    try:
        return eval(compile(_parse(expr), "<expr>", "eval"), _SAFE, env)   # arithmetic only, no builtins
    except Exception:
        return None


class _Swap(ast.NodeTransformer):
    def __init__(self, a: str, b: str):
        self.a, self.b = a, b

    def visit_Name(self, node: ast.Name):
        if node.id == self.a:
            node.id = self.b
        elif node.id == self.b:
            node.id = self.a
        return node


def measure_symmetry(expr: str, samples: int = 8) -> float:
    """[0,1] fraction of variable PAIRS whose swap leaves the expression numerically unchanged on seeded inputs.
    a+b → 1.0 (symmetric), a−b → 0.0. Constant/one-variable expressions have no pair to test → 1.0 (vacuous)."""
    tree = _parse(expr)
    vs = _variables(tree)
    if len(vs) < 2:
        return 1.0
    pairs = [(vs[i], vs[j]) for i in range(len(vs)) for j in range(i + 1, len(vs))]
    symmetric = 0
    for a, b in pairs:
        swapped = ast.unparse(_Swap(a, b).visit(_parse(expr)))
        ok = True
        for s in range(samples):
            env = {v: 1.0 + ((s * 7 + k * 3) % 5) for k, v in enumerate(vs)}   # deterministic, distinct values
            o1, o2 = _eval(expr, dict(env)), _eval(swapped, dict(env))
            if o1 is None or o2 is None or abs(o1 - o2) > 1e-9:
                ok = False
                break
        symmetric += int(ok)
    return round(symmetric / len(pairs), 4)


def measure_simplicity(expr: str) -> float:
    """[0,1] minimum-description-length simplicity: fewer AST nodes ⇒ simpler. 1/(1+nodes) normalised so a
    small formula scores high and a verbose one low — a pure function of structure, not taste."""
    n = _nodes(_parse(expr))
    return round(1.0 / (1.0 + max(0, n - 2)), 4)          # −2: subtract the Expression+top wrapper baseline


def measure_surprise(expr: str, corpus: Sequence[str]) -> float:
    """[0,1] structural distance from a CONTEXT corpus: 1 − (max operator-set overlap with any corpus item). An
    artifact whose operators are all already common in the corpus is unsurprising; a new shape is surprising."""
    ops = set(_operators(_parse(expr)))
    if not corpus:
        return 1.0
    best = 0.0
    for other in corpus:
        oo = set(_operators(_parse(other)))
        union = ops | oo
        overlap = (len(ops & oo) / len(union)) if union else 1.0
        best = max(best, overlap)
    return round(1.0 - best, 4)


def elegance_score(expr: str, corpus: Optional[Sequence[str]] = None) -> Dict:
    """The aesthetic vector {symmetry, simplicity, surprise} plus a scalar `elegance`. BEAUTY (elegance) is
    SIMPLICITY + SYMMETRY (Occam + invariance) — the classical account. SURPRISE is reported in the vector but
    kept OUT of the elegance scalar ON PURPOSE: surprise measures NOVELTY, a different drive — a surprising
    artifact is not thereby beautiful, and (crucially) padding a formula with redundant terms inflates operator-
    variety 'surprise' while making it uglier. Folding surprise into elegance would let a clumsy padded formula
    out-score its terse core. So: elegance = 0.6·simplicity + 0.4·symmetry; surprise stays a separate axis."""
    sym = measure_symmetry(expr)
    simp = measure_simplicity(expr)
    sur = measure_surprise(expr, corpus or [])
    return {"symmetry": sym, "simplicity": simp, "surprise": sur,
            "elegance": round(0.6 * simp + 0.4 * sym, 4)}


def aesthetics_objectivity_pass() -> bool:
    """The honesty gate for the elegance dimension (used by a protected invariant). TRUE iff the metrics are
    OBJECTIVE, not arbitrary:
      • deterministic — the same artifact scores identically twice (no hidden state / randomness);
      • grounded in the AST — a MORE verbose formula is never scored MORE simple than a terse equivalent;
      • symmetry is real — a symmetric form (a+b) scores higher symmetry than an asymmetric one (a−b);
      • a canonical 'beautiful' formula scores higher overall elegance than a clumsy but equivalent one.
    If any clause fails, elegance is a taste the engine could assert at will → the dimension is dishonest."""
    deterministic = elegance_score("m*c**2") == elegance_score("m*c**2")
    simpler = measure_simplicity("m*c**2") > measure_simplicity("m*c*c + 0*m + m - m")
    symmetry = measure_symmetry("a + b") > measure_symmetry("a - b")
    # BUGFIX: the gate must also certify SURPRISE — an unfamiliar operator (Pow) must be more surprising than a
    # familiar one (Add) given a +/* corpus. Without this clause the gate passed vacuously while surprise was
    # broken (it returned 0 for every expression). Now the dimension it certifies is actually tested.
    surprising = measure_surprise("a ** b", ["a + b", "a * b"]) > measure_surprise("a + b", ["a + b", "a * b"])
    beautiful = elegance_score("m*c**2")["elegance"] > elegance_score("m*c*c + 0*m + m - m + c - c")["elegance"]
    return bool(deterministic and simpler and symmetry and surprising and beautiful)
