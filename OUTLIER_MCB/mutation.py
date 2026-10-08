"""mutation — does the test actually test the implementation? Measured by killing mutants, not by keywords.

`llm_loop.test_quality_evidence` scores a test by how it LOOKS (asserts, imports, no tautology) — gameable: a test
can look specific and still pass whatever the implementation does. The classic external check is mutation
testing: perturb the code the idea changed (return None, flip a comparison, shift a constant, swap and/or, negate
a condition) and require the test to go RED. A test that survives its own idea's mutants does not pin the idea.

Mutants are restricted to the lines the implementation patch CHANGED (unrelated code is not the claim), bounded
in number (each one is a full test run), deterministic (AST walk order), and every mutated file is restored
byte-exactly in a `finally`. Pure stdlib; Python 3.9 (`ast.unparse`).
"""
from __future__ import annotations
import ast
import copy
import difflib
import os
from typing import Dict, List, Optional, Set, Tuple

_FLIP = {ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.Lt: ast.GtE, ast.GtE: ast.Lt, ast.Gt: ast.LtE, ast.LtE: ast.Gt,
         ast.In: ast.NotIn, ast.NotIn: ast.In, ast.Is: ast.IsNot, ast.IsNot: ast.Is}
_KINDS = ("return_none", "flip_compare", "shift_constant", "swap_boolop", "negate_condition")


def changed_lines(before: str, after: str) -> Set[int]:
    """1-based line numbers of `after` that were inserted or replaced relative to `before`."""
    sm = difflib.SequenceMatcher(a=(before or "").splitlines(), b=(after or "").splitlines(), autojunk=False)
    out: Set[int] = set()
    for tag, _i1, _i2, j1, j2 in sm.get_opcodes():
        if tag in ("replace", "insert"):
            out.update(range(j1 + 1, j2 + 1))
    return out


def _kind(node) -> Optional[str]:
    if isinstance(node, ast.Return) and node.value is not None and not (
            isinstance(node.value, ast.Constant) and node.value.value is None):
        return "return_none"
    if isinstance(node, ast.Compare) and len(node.ops) == 1 and type(node.ops[0]) in _FLIP:
        return "flip_compare"
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return "shift_constant"
    if isinstance(node, ast.BoolOp):
        return "swap_boolop"
    if isinstance(node, (ast.If, ast.While)):
        return "negate_condition"
    return None


def _sites(tree, lines: Optional[Set[int]]) -> List[Tuple[int, str]]:
    sites = []
    for i, node in enumerate(ast.walk(tree)):
        k = _kind(node)
        if k and (lines is None or getattr(node, "lineno", None) in lines):
            sites.append((i, k))
    return sites


def _apply(node, kind: str) -> None:
    if kind == "return_none":
        node.value = ast.Constant(value=None)
    elif kind == "flip_compare":
        node.ops = [_FLIP[type(node.ops[0])]()]
    elif kind == "shift_constant":
        node.value = node.value + 1
    elif kind == "swap_boolop":
        node.op = ast.Or() if isinstance(node.op, ast.And) else ast.And()
    elif kind == "negate_condition":
        node.test = ast.UnaryOp(op=ast.Not(), operand=node.test)


def mutants(source: str, lines: Optional[Set[int]] = None, max_mutants: int = 6) -> List[Tuple[str, str]]:
    """Up to `max_mutants` (description, mutated_source) pairs, round-robin over mutation kinds so a small budget
    still covers different kinds of fault. [] if the source does not parse or nothing is mutable on `lines`."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return []
    original = ast.unparse(tree)
    by_kind: Dict[str, List[int]] = {k: [] for k in _KINDS}
    for idx, k in _sites(tree, lines):
        by_kind[k].append(idx)
    order: List[Tuple[int, str]] = []
    while any(by_kind.values()):
        for k in _KINDS:
            if by_kind[k]:
                order.append((by_kind[k].pop(0), k))
    out: List[Tuple[str, str]] = []
    for idx, k in order:
        if len(out) >= max(0, max_mutants):
            break
        t = copy.deepcopy(tree)
        node = next(n for i, n in enumerate(ast.walk(t)) if i == idx)
        _apply(node, k)
        try:
            src = ast.unparse(ast.fix_missing_locations(t))
        except Exception:
            continue
        if src != original:
            out.append((f"{k}@L{getattr(node, 'lineno', '?')}", src))
    return out


def mutation_check(repo_root: str, before: Dict[str, Optional[str]], cmd, *, runner, timeout: int, env=None,
                   max_mutants: int = 4) -> Dict:
    """Mutate the lines the implementation changed in each `.py` file of `before` ({rel_path: text before the
    implementation, None if new}), run the test once per mutant, and restore the file. Returns
    {mutants, killed, score (None if nothing was mutable), survivors}. A mutant is KILLED when the test is no longer
    GREEN (assertion, collection error or timeout all count — the test noticed)."""
    from .llm_loop import classify_test_outcome
    plans: List[Tuple[str, str, str]] = []                    # (abs path, description, mutated source)
    for rel, old in before.items():
        if not rel.endswith(".py"):
            continue
        path = os.path.join(repo_root, rel)
        try:
            with open(path, encoding="utf-8") as fh:
                cur = fh.read()
        except OSError:
            continue
        lines = changed_lines(old or "", cur)
        if lines:
            plans += [(path, d, s) for d, s in mutants(cur, lines, max_mutants)]
    plans = plans[:max(0, max_mutants)]
    killed, survivors = 0, []
    for path, desc, src in plans:
        with open(path, "rb") as fh:
            original = fh.read()
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(src)
            outcome = classify_test_outcome(runner.run(cmd, cwd=repo_root, timeout=timeout, env=env))
        finally:
            with open(path, "wb") as fh:
                fh.write(original)
        if outcome == "GREEN":
            survivors.append(f"{os.path.relpath(path, repo_root)}:{desc}")
        else:
            killed += 1
    n = len(plans)
    return {"mutants": n, "killed": killed, "score": (round(killed / n, 3) if n else None), "survivors": survivors}
