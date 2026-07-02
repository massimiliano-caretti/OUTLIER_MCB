"""repo_semantics — understand WHERE behavior lives, not just whether pytest runs (improvement #2).

Grounding used to mean 'I can execute commands'. To invent real technical changes the engine must read the
repository's structure: which functions/classes exist, who calls whom, which tests cover which modules, what
the public API is, and — crucially — where a candidate would actually land (its impact surface) and which
modules have NO test (a missing-evaluator opportunity). All by stdlib `ast`, offline, no dependencies.

The honesty payoff: a proposal that touches NO real behavior is NOT grounded, however plausible it sounds.
suggest_repo_falsifiers turns the impact surface into concrete, file-anchored RED tests — the falsifier names
a real function in a real module, so the idea is settled against the codebase, not a placeholder.
"""
from __future__ import annotations
import ast
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

_SKIP_DIRS = {"__pycache__", ".git", ".venv", "venv", "node_modules", ".mypy_cache", ".pytest_cache", "build", "dist"}


@dataclass
class ModuleInfo:
    module: str                       # dotted-ish module key (path relative to repo, no .py)
    path: str
    functions: List[str] = field(default_factory=list)     # qualified names (Class.method or func)
    classes: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)        # imported module names
    public_api: List[str] = field(default_factory=list)     # top-level non-underscore funcs/classes
    is_test: bool = False


@dataclass
class RepoModel:
    root: str
    modules: Dict[str, ModuleInfo] = field(default_factory=dict)
    symbol_to_module: Dict[str, str] = field(default_factory=dict)   # function/class name -> defining module
    call_graph: Dict[str, Set[str]] = field(default_factory=dict)    # module -> set of in-repo callee symbols
    test_map: Dict[str, List[str]] = field(default_factory=dict)     # test module -> modules it imports (in-repo)

    # ── queries ──
    def all_symbols(self) -> Set[str]:
        return set(self.symbol_to_module)

    def public_api(self) -> Dict[str, List[str]]:
        return {m: info.public_api for m, info in self.modules.items() if info.public_api and not info.is_test}

    def modules_without_tests(self) -> List[str]:
        tested: Set[str] = set()
        for _, mods in self.test_map.items():
            tested.update(mods)
        return sorted(m for m, info in self.modules.items()
                      if not info.is_test and info.public_api and m not in tested)

    def callers_of(self, symbol: str) -> List[str]:
        return sorted(mod for mod, callees in self.call_graph.items() if symbol in callees)

    def markdown(self) -> str:
        return (f"## Repo world model — {len([m for m in self.modules.values() if not m.is_test])} modules · "
                f"{len(self.symbol_to_module)} symbols · {len(self.test_map)} test files · "
                f"{len(self.modules_without_tests())} modules without tests")


def _iter_py(root: str):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fn in filenames:
            if fn.endswith(".py"):
                yield os.path.join(dirpath, fn)


def _module_key(root: str, path: str) -> str:
    rel = os.path.relpath(path, root)
    return rel[:-3].replace(os.sep, ".") if rel.endswith(".py") else rel


def _collect(tree: ast.AST):
    funcs: List[str] = []
    classes: List[str] = []
    imports: List[str] = []
    public: List[str] = []
    calls: Set[str] = set()

    class V(ast.NodeVisitor):
        def __init__(self):
            self.stack: List[str] = []

        def visit_ClassDef(self, node):
            classes.append(node.name)
            if not node.name.startswith("_"):
                public.append(node.name)
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()

        def _func(self, node):
            qn = ".".join(self.stack + [node.name])
            funcs.append(qn)
            if not self.stack and not node.name.startswith("_"):
                public.append(node.name)
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()

        visit_FunctionDef = _func
        visit_AsyncFunctionDef = _func

        def visit_Import(self, node):
            for a in node.names:
                imports.append(a.name)               # full dotted path, e.g. "pkg.core"
            self.generic_visit(node)

        def visit_ImportFrom(self, node):
            base = node.module or ""
            if base:
                imports.append(base)
            for a in node.names:                     # `from pkg import core` → also record "pkg.core"
                imports.append(f"{base}.{a.name}" if base else a.name)
            self.generic_visit(node)

        def visit_Call(self, node):
            f = node.func
            if isinstance(f, ast.Name):
                calls.add(f.id)
            elif isinstance(f, ast.Attribute):
                calls.add(f.attr)
            self.generic_visit(node)

    V().visit(tree)
    return funcs, classes, imports, public, calls


def analyze_repo_semantics(repo_path: str, max_files: int = 2000) -> RepoModel:
    """Parse every .py under `repo_path` (stdlib ast) into a RepoModel: functions, classes, imports, public
    API, an in-repo call graph, and a test→module map. Files that fail to parse are skipped, never fatal."""
    model = RepoModel(root=repo_path)
    raw_calls: Dict[str, Set[str]] = {}
    raw_imports: Dict[str, List[str]] = {}
    count = 0
    for path in _iter_py(repo_path):
        if count >= max_files:
            break
        count += 1
        try:
            tree = ast.parse(open(path, "r", encoding="utf-8", errors="ignore").read())
        except Exception:
            continue
        mod = _module_key(repo_path, path)
        funcs, classes, imports, public, calls = _collect(tree)
        is_test = "test" in os.path.basename(path).lower() or os.sep + "tests" + os.sep in path
        model.modules[mod] = ModuleInfo(module=mod, path=path, functions=funcs, classes=classes,
                                        imports=imports, public_api=public, is_test=is_test)
        raw_calls[mod] = calls
        raw_imports[mod] = imports
        base = (set(funcs) | set(classes) | {f.split(".")[-1] for f in funcs})
        for s in base:
            model.symbol_to_module.setdefault(s, mod)

    known = model.all_symbols()
    for mod, calls in raw_calls.items():
        in_repo = {c for c in calls if c in known and model.symbol_to_module.get(c) != mod}
        if in_repo:
            model.call_graph[mod] = in_repo

    repo_keys = [m for m, info in model.modules.items() if not info.is_test]

    def _resolve(imported_paths) -> List[str]:
        # match an import to a module by full/suffix path ONLY — never by bare leaf name (a shared leaf like
        # `base.py`/`core.py` in two packages must NOT cross-resolve, or missing-test detection is defeated).
        out: Set[str] = set()
        for imp in imported_paths:
            for k in repo_keys:
                if k == imp or k.endswith("." + imp) or imp.endswith("." + k):
                    out.add(k)
        return sorted(out)

    for mod, info in model.modules.items():
        if info.is_test:
            model.test_map[mod] = _resolve(raw_imports.get(mod, []))
    return model


def repo_world_model(repo_path: str) -> RepoModel:
    """The repo as a world model the engine can reason over (alias of analyze_repo_semantics, named for intent)."""
    return analyze_repo_semantics(repo_path)


def _cand_text(candidate) -> str:
    if isinstance(candidate, str):
        return candidate
    g = lambda k: getattr(candidate, k, "") if not isinstance(candidate, dict) else candidate.get(k, "")
    return " ".join(str(g(k)) for k in ("name", "negation", "claim", "discipline", "description") if g(k))


def _tokens(text: str) -> Set[str]:
    return {w for w in "".join(c if (c.isalnum() or c == "_") else " " for c in (text or "").lower()).split()
            if len(w) > 2}


def impact_surface(candidate, repo_model: RepoModel, expand_depth: int = 1) -> Dict:
    """Which real modules/functions a candidate would touch: match the candidate's identifiers to repo symbols,
    then expand by reverse call edges (the callers that a change would ripple to). A candidate that matches NO
    symbol has an EMPTY surface → it is not grounded in any behavior."""
    toks = _tokens(_cand_text(candidate))
    hit_symbols = {s for s in repo_model.all_symbols() if s.lower() in toks}
    touched_modules: Set[str] = {repo_model.symbol_to_module[s] for s in hit_symbols}
    frontier = set(hit_symbols)
    for _ in range(max(0, expand_depth)):
        callers: Set[str] = set()
        for s in frontier:
            for mod in repo_model.callers_of(s):
                callers.add(mod)
                touched_modules.add(mod)
        if not callers:
            break
        # next frontier: public symbols of the caller modules
        frontier = {sym for mod in callers for sym in repo_model.modules[mod].public_api}
    grounded = bool(hit_symbols)
    return {"grounded": grounded, "symbols": sorted(hit_symbols), "modules": sorted(touched_modules),
            "n_symbols": len(hit_symbols), "n_modules": len(touched_modules)}


def suggest_repo_falsifiers(candidate, repo_model: RepoModel, max_suggestions: int = 5) -> List[Dict]:
    """Turn the impact surface into CONCRETE, file-anchored falsifiers (a RED test naming a real function in a
    real module). For a touched module with no test, flag a missing-evaluator opportunity. Empty when the
    candidate is not grounded — there is nothing real to falsify."""
    surface = impact_surface(candidate, repo_model)
    if not surface["grounded"]:
        return []
    tested = set()
    for mods in repo_model.test_map.values():
        tested.update(mods)
    out: List[Dict] = []
    for sym in surface["symbols"][:max_suggestions]:
        mod = repo_model.symbol_to_module[sym]
        info = repo_model.modules.get(mod)
        has_test = mod in tested
        out.append({
            "symbol": sym, "module": mod, "file": info.path if info else "",
            "has_test": has_test,
            "falsifier": (f"add a test exercising `{sym}` in module `{mod}` that encodes the candidate's claimed "
                          f"behavior and currently FAILS (RED); the candidate is settled only when it turns GREEN "
                          f"without breaking the existing suite."),
            "opportunity": ("" if has_test else f"module `{mod}` has NO test — a falsifier here is net-new coverage")})
    return out


def is_grounded(candidate, repo_model: RepoModel) -> bool:
    """A proposal is grounded only if it touches real behavior (non-empty impact surface)."""
    return impact_surface(candidate, repo_model)["grounded"]


def repo_grounding_ablation(repo_model: RepoModel) -> Dict:
    """Ablation for #2: a candidate naming REAL repo symbols is grounded with a non-empty surface; a candidate
    of unrelated words is NOT grounded and yields no falsifiers. Proves the grounding actually discriminates."""
    syms = sorted(repo_model.all_symbols())
    real = " ".join(syms[:3]) if syms else ""
    decorative = "zzzqqq nonsense lorem ipsum unrelated gibberish tokenxyz"
    g_real = impact_surface(real, repo_model)
    g_dec = impact_surface(decorative, repo_model)
    return {"real_grounded": g_real["grounded"], "real_modules": g_real["n_modules"],
            "decorative_grounded": g_dec["grounded"], "decorative_modules": g_dec["n_modules"],
            "real_falsifiers": len(suggest_repo_falsifiers(real, repo_model)),
            "decorative_falsifiers": len(suggest_repo_falsifiers(decorative, repo_model)),
            "grounding_discriminates": (g_real["grounded"] and not g_dec["grounded"])}
