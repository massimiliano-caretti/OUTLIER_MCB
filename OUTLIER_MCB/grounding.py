"""grounding — probe the REAL environment so the engine stops reasoning against placeholders.

The recurring weakness: world-tests, routing, and scoring all ran on internal heuristics, never on the
actual repository. `probe(path)` inspects a real directory (read-only, stdlib-only, no execution) and
returns a `RepoContext`: the detected languages, the real test/type/build commands, sample source and
test files, and a few public symbols. Everything else in the grounding fix consumes this single source
of truth — repo_world derives executable world-tests from it, routing uses its signals, and the runtime
discounts ideas that cannot be tied to it.

Collaborators: repo_world (compiles world-tests from a RepoContext); pack.select_pack (repo-aware routing).
"""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

# file extension → language label
_LANGS = {".py": "python", ".js": "javascript", ".ts": "typescript", ".tsx": "typescript",
          ".go": "go", ".rs": "rust", ".java": "java", ".rb": "ruby", ".cpp": "c++", ".c": "c"}
# directories never worth walking
_SKIP = {".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build", ".mypy_cache",
         ".pytest_cache", "target", ".idea", ".vscode"}


@dataclass
class RepoContext:
    """A read-only snapshot of a real project — the engine's source of truth for grounding."""
    root: str
    languages: List[str] = field(default_factory=list)
    test_command: Optional[str] = None
    type_command: Optional[str] = None
    build_command: Optional[str] = None
    test_files: List[str] = field(default_factory=list)
    source_files: List[str] = field(default_factory=list)
    symbols: List[str] = field(default_factory=list)
    components: List[str] = field(default_factory=list)     # top-level packages/dirs that hold code
    public_api: List[str] = field(default_factory=list)     # exported contract (a package __all__), if any
    fragile: List[str] = field(default_factory=list)        # files carrying the most TODO/FIXME/HACK markers

    @property
    def grounded(self) -> bool:
        """True when a real toolchain was detected — i.e. world-tests can actually be run here."""
        return bool(self.test_command or self.type_command or self.build_command)

    def primary_language(self) -> Optional[str]:
        return self.languages[0] if self.languages else None

    def map(self) -> str:
        """A short map of the project FLOW (not a file listing): components, contract, fragility, tools."""
        return "\n".join([
            f"root: {self.root}  ·  languages: {', '.join(self.languages) or '—'}",
            f"components: {', '.join(self.components) or '—'}",
            f"public contract: {', '.join(self.public_api[:10]) or '—'}",
            f"fragile (most TODO/FIXME): {', '.join(self.fragile) or '—'}",
            f"tools: test=`{self.test_command or '—'}`  type=`{self.type_command or '—'}`  build=`{self.build_command or '—'}`",
        ])


def _detect_commands(root: Path, names: set) -> dict:
    """Map the marker files present in the project root to real toolchain commands."""
    text = lambda p: (root / p).read_text(errors="ignore") if (root / p).exists() else ""
    cmds = {}
    pyproject = text("pyproject.toml")
    if "test_" in "".join(names) or {"pytest.ini", "tox.ini", "conftest.py"} & names or "[tool.pytest" in pyproject:
        cmds["test"] = "pytest -q"
    if "mypy.ini" in names or "[tool.mypy]" in pyproject:
        cmds["type"] = "mypy ."
    if "package.json" in names:
        pkg = text("package.json")
        cmds["test"] = "npm test" if '"test"' in pkg else cmds.get("test")
        if "tsconfig.json" in names:
            cmds["type"] = "npx tsc --noEmit"
    if "go.mod" in names:
        cmds["test"] = "go test ./..."
    if "Cargo.toml" in names:
        cmds["test"] = "cargo test"
    if "Makefile" in names:
        mk = text("Makefile")
        if "\ntest:" in mk or mk.startswith("test:"):
            cmds.setdefault("test", "make test")
        if "\nbuild:" in mk or mk.startswith("build:"):
            cmds["build"] = "make build"
    return cmds


def _symbols(files: List[Path], limit: int = 12) -> List[str]:
    """Collect a few public def/class/function names from real source files (a cheap symbol sample)."""
    out: List[str] = []
    for f in files:
        for line in f.read_text(errors="ignore").splitlines():
            s = line.strip()
            for kw in ("def ", "class ", "function ", "func "):
                if s.startswith(kw):
                    name = s[len(kw):].split("(")[0].split(":")[0].split("{")[0].strip()
                    if name and not name.startswith("_") and name not in out:
                        out.append(name)
            if len(out) >= limit:
                return out
    return out


def probe(path: str = ".", max_files: int = 4000) -> RepoContext:
    """Inspect a real directory and return its RepoContext. Read-only and bounded; never executes code."""
    root = Path(path).resolve()
    if not root.is_dir():
        return RepoContext(root=str(root))
    langs: dict = {}
    sources: List[Path] = []
    tests: List[str] = []
    root_names: set = set()
    components: List[str] = []
    fragility: dict = {}                                      # relpath -> TODO/FIXME/HACK count
    seen = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP and not d.startswith(".")]
        if Path(dirpath) == root:
            root_names = set(filenames) | set(dirnames)
            components = [d for d in sorted(dirnames)
                          if any(f.endswith(tuple(_LANGS)) for f in os.listdir(Path(dirpath, d)))]
        for fn in filenames:
            seen += 1
            if seen > max_files:
                break
            ext = os.path.splitext(fn)[1]
            if ext in _LANGS:
                langs[_LANGS[ext]] = langs.get(_LANGS[ext], 0) + 1
                p = Path(dirpath, fn)
                rel = str(p.relative_to(root))
                if fn.startswith("test_") or fn.endswith("_test.py") or ("test" in fn.lower() and ext in (".py", ".js", ".ts")):
                    tests.append(rel)
                elif len(sources) < 8:
                    sources.append(p)
                marks = sum(p.read_text(errors="ignore").count(m) for m in ("TODO", "FIXME", "HACK"))
                if marks:
                    fragility[rel] = marks
        if seen > max_files:
            break
    cmds = _detect_commands(root, root_names)
    if "test" not in cmds and tests and "python" in langs:   # discovered test files anywhere ⇒ pytest
        cmds["test"] = "pytest -q"
    return RepoContext(
        root=str(root),
        languages=[l for l, _ in sorted(langs.items(), key=lambda kv: -kv[1])],
        test_command=cmds.get("test"), type_command=cmds.get("type"), build_command=cmds.get("build"),
        test_files=tests[:10], source_files=[str(p.relative_to(root)) for p in sources],
        symbols=_symbols(sources), components=components,
        public_api=_public_api(root, components),
        fragile=[rel for rel, _ in sorted(fragility.items(), key=lambda kv: -kv[1])[:5]],
    )


def _public_api(root: Path, components: List[str]) -> List[str]:
    """The exported contract: the `__all__` of the first component package that declares one (Python)."""
    import ast
    for comp in components:
        init = root / comp / "__init__.py"
        if not init.exists():
            continue
        try:
            tree = ast.parse(init.read_text(errors="ignore"))
        except SyntaxError:
            continue
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "__all__" for t in node.targets):
                if isinstance(node.value, (ast.List, ast.Tuple)):
                    return [e.value for e in node.value.elts if isinstance(e, ast.Constant)]
    return []
