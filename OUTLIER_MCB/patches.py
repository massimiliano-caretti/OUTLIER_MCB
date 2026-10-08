"""patches — parse, SECURITY-VALIDATE, and apply unified-diff patches an LLM proposes.

The whole point of the LLM loop is to MATERIALIZE artifacts (a failing test, then a fix) into the real repo
and run them — not to grade prose. That means taking untrusted LLM text and writing files, so the security
gate is not optional: `validate_patch_paths` refuses absolute paths, `..` traversal, and anything resolving
outside the repo root BEFORE a single byte is written. Pure stdlib, no `git`/`patch` dependency.

A pragmatic unified-diff applier: it supports new-file creation (`--- /dev/null`), deletion (`+++ /dev/null`),
and hunk application to existing files by locating each hunk's old-side block (context + removed lines) and
replacing it with the new-side block (context + added lines). Good for the minimal patches a model writes in
this loop; it reports a clear error instead of corrupting a file when a hunk does not match.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class Hunk:
    old_lines: List[str] = field(default_factory=list)   # context + removed (what must currently be present)
    new_lines: List[str] = field(default_factory=list)   # context + added (what replaces it)
    n_removed: int = 0                                     # how many '-' lines (removals) the hunk carries


@dataclass
class FilePatch:
    path: str
    is_new: bool = False
    is_delete: bool = False
    hunks: List[Hunk] = field(default_factory=list)
    new_content: Optional[str] = None    # for a whole new file


@dataclass
class PatchPlan:
    files: List[FilePatch] = field(default_factory=list)
    parse_errors: List[str] = field(default_factory=list)
    def paths(self) -> List[str]:
        return [f.path for f in self.files]


def _strip_prefix(p: str) -> str:
    p = p.split("\t", 1)[0].strip()            # drop a trailing "\t<timestamp>" (GNU diff headers)
    if len(p) >= 2 and p[0] == p[-1] == '"':     # git quotes paths with unusual characters
        p = p[1:-1]
    if p.startswith(("a/", "b/")):
        return p[2:]
    return p


_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
# framing lines that are NEVER hunk content: a hunk ends when one appears (git header of the next file, or the
# closing fence of a ```diff block an LLM wrapped the patch in)
_HUNK_TERMINATORS = ("diff --git ", "```")


def _is_file_header(lines: List[str], i: int) -> bool:
    """A '--- ' line is a file header only when the NEXT line is '+++ ' — a removed line whose content starts
    with '-- ' (an SQL/Lua comment, a Markdown rule) also renders as '--- …' and must stay hunk content."""
    return lines[i].startswith("--- ") and i + 1 < len(lines) and lines[i + 1].startswith("+++ ")


def parse_unified_diff(text: str) -> PatchPlan:
    """Parse unified-diff `text` into a PatchPlan. Tolerant of leading prose / code fences around the diff,
    git extended headers (`diff --git`, `index …`), and hunk headers with or without line counts. When the
    `@@ -a,b +c,d @@` counts are present the hunk ends once both are consumed (only further '+'/'-' lines extend
    an under-counted hunk), so trailing prose or a closing ``` fence is never mistaken for context."""
    plan = PatchPlan()
    lines = (text or "").splitlines()
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        if line.startswith("--- "):
            if not _is_file_header(lines, i):
                plan.parse_errors.append(f"'---' without a following '+++' at line {i}")
                i += 1
                continue
            old = _strip_prefix(line[4:])
            new = _strip_prefix(lines[i + 1][4:])
            i += 2
            is_new = old in ("/dev/null", "a//dev/null", "dev/null")
            is_delete = new in ("/dev/null", "b//dev/null", "dev/null")
            path = new if not is_delete else old
            fp = FilePatch(path=path, is_new=is_new, is_delete=is_delete)
            added: List[str] = []
            # read hunks until the next file header or EOF
            while i < n and not _is_file_header(lines, i) and not lines[i].startswith("diff --git "):
                m = _HUNK_RE.match(lines[i]) if lines[i].startswith("@@") else None
                if not lines[i].startswith("@@"):
                    i += 1
                    continue
                i += 1
                hunk = Hunk()
                old_left = (int(m.group(2)) if m.group(2) is not None else 1) if m else None
                new_left = (int(m.group(4)) if m.group(4) is not None else 1) if m else None
                while i < n:
                    h = lines[i]
                    if old_left is not None and old_left <= 0 and new_left <= 0 and not h[:1] in ("+", "-"):
                        # counts exhausted → the hunk is complete. (A '+'/'-' line right after is still taken:
                        # LLMs under-count headers, and silently DROPPING an added line would be worse than a
                        # hunk that fails to match.)
                        break
                    if h.startswith("@@") or _is_file_header(lines, i) or h.startswith(_HUNK_TERMINATORS):
                        break
                    tag, body = (h[:1], h[1:]) if h else (" ", "")
                    if tag == "+":
                        hunk.new_lines.append(body); added.append(body)
                        if new_left is not None:
                            new_left -= 1
                    elif tag == "-":
                        hunk.old_lines.append(body); hunk.n_removed += 1
                        if old_left is not None:
                            old_left -= 1
                    elif tag == "\\":         # "\ No newline at end of file" — ignore
                        pass
                    elif tag == " " or not h:  # context (space) or a blank line whose leading space was lost
                        hunk.old_lines.append(body); hunk.new_lines.append(body)
                        if old_left is not None:
                            old_left -= 1; new_left -= 1
                    else:                      # prose / framing after the diff: the hunk ended
                        break
                    i += 1
                if old_left is None:           # count-less '@@': trailing blank lines are separators, not context
                    while (len(hunk.old_lines) > 1 and len(hunk.new_lines) > 1
                           and hunk.old_lines[-1] == "" and hunk.new_lines[-1] == ""):
                        hunk.old_lines.pop(); hunk.new_lines.pop()
                fp.hunks.append(hunk)
            if is_new:
                fp.new_content = "\n".join(added) + ("\n" if added else "")
            plan.files.append(fp)
        else:
            i += 1
    if not plan.files and not plan.parse_errors:
        plan.parse_errors.append("no unified-diff file headers ('--- ' / '+++ ') found")
    return plan


# path components a patch may never write into: VCS metadata (a write to `.git/hooks/*` or `.git/config` is
# arbitrary code execution on the user's next git command) — checked case-insensitively for case-folding FSs.
_FORBIDDEN_COMPONENTS = {".git", ".hg", ".svn"}


def validate_patch_paths(plan: PatchPlan, repo_root) -> Tuple[bool, List[str]]:
    """SECURITY gate: every target must be a relative path that resolves INSIDE repo_root. Rejects absolute
    paths, `..` traversal, symlink escapes, the repo root itself, and VCS metadata (`.git/…`). Returns
    (ok, errors)."""
    root = Path(repo_root).resolve()
    errors: List[str] = []
    for fp in plan.files:
        p = fp.path
        if not p or not p.strip():
            errors.append("empty target path"); continue
        if "\x00" in p:
            errors.append(f"NUL byte in path rejected: {p!r}"); continue
        if Path(p).is_absolute() or p.startswith(("/", "~", "\\")) or re.match(r"^[A-Za-z]:", p):
            errors.append(f"absolute path rejected: {p}"); continue
        parts = Path(p.replace("\\", "/")).parts
        if ".." in parts:
            errors.append(f"path traversal ('..') rejected: {p}"); continue
        if any(part.lower() in _FORBIDDEN_COMPONENTS for part in parts):
            errors.append(f"VCS metadata path rejected: {p}"); continue
        try:
            resolved = (root / p).resolve()
        except (OSError, ValueError, RuntimeError):
            errors.append(f"unresolvable path: {p}"); continue
        if resolved == root:
            errors.append(f"target is the repo root itself: {p}"); continue
        if root not in resolved.parents:
            errors.append(f"path escapes repo root: {p}"); continue
    return (not errors), errors


def _apply_hunks(content: str, hunks: List[Hunk]) -> Tuple[Optional[str], Optional[str]]:
    """Apply hunks to `content` by locating each old-side block and replacing it. Hunks are applied in order,
    each searched AFTER the previous one first (so a block that repeats in the file is patched at the right
    occurrence), then anywhere. The file's newline style (LF / CRLF) is preserved. Returns (new_content, error)."""
    eol = "\r\n" if "\r\n" in content else "\n"
    lines = content.splitlines()
    pos = 0
    for h in hunks:
        old, new = list(h.old_lines), list(h.new_lines)
        if not old:                                  # pure insertion with no anchor → append
            lines.extend(new)
            pos = len(lines)
            continue
        # find the contiguous old block in lines (exact, then whitespace-insensitive)
        idx = _find_block(lines, old, pos)
        if idx is None:
            idx = _find_block(lines, old, 0)
        if idx is None:
            stripped = [l.rstrip() for l in lines]
            idx = _find_block(stripped, [l.rstrip() for l in old], pos)
            if idx is None:
                idx = _find_block(stripped, [l.rstrip() for l in old], 0)
        if idx is None:
            return None, f"hunk did not match the file (looking for {old[:2]}…)"
        lines[idx:idx + len(old)] = new
        pos = idx + len(new)
    return eol.join(lines) + eol, None


def _find_block(haystack: List[str], needle: List[str], start: int = 0) -> Optional[int]:
    if not needle:
        return None
    first = needle[0]
    for i in range(max(0, start), len(haystack) - len(needle) + 1):
        if haystack[i] == first and haystack[i:i + len(needle)] == needle:
            return i
    return None


def _read_text(target: Path) -> str:
    """Read a text file as UTF-8 WITHOUT newline translation (so CRLF survives a round trip)."""
    with open(target, "r", encoding="utf-8", newline="") as fh:
        return fh.read()


def _write_text(target: Path, content: str) -> None:
    with open(target, "w", encoding="utf-8", newline="") as fh:
        fh.write(content)


def apply_patch_plan(plan: PatchPlan, repo_root, dry_run: bool = False) -> dict:
    """Apply a validated PatchPlan to repo_root. ALWAYS validate paths first (callers must not skip it; this
    re-checks). Returns {applied, errors, files}. dry_run=True checks applicability without writing.

    All-or-nothing: every file's new content is computed in memory FIRST; if any file fails (a hunk that does
    not match, a non-text or directory target, a hunk with removals against a missing file) NOTHING is
    written, so a half-applied multi-file patch can never be left in the repo."""
    ok, perrs = validate_patch_paths(plan, repo_root)
    if not ok:
        return {"applied": False, "errors": perrs, "files": []}
    root = Path(repo_root)
    errors = list(plan.parse_errors)
    staged: Dict[str, Optional[str]] = {}         # rel path → final content (None ⇒ delete), in plan order
    for fp in plan.files:
        target = root / fp.path
        if target.is_dir():
            errors.append(f"{fp.path}: target is a directory"); continue
        if fp.is_delete:
            staged[fp.path] = None; continue
        if fp.path in staged:                     # a second patch for the same file chains on the staged text
            current = staged[fp.path]
        elif target.exists():
            try:
                current = _read_text(target)
            except (UnicodeDecodeError, OSError) as exc:
                errors.append(f"{fp.path}: not a readable UTF-8 text file ({type(exc).__name__})"); continue
        else:
            current = None
        if fp.is_new or current is None:
            if current is None and not fp.is_new and any(h.n_removed for h in fp.hunks):
                errors.append(f"{fp.path}: file does not exist, but the patch removes/changes lines in it"); continue
            content = fp.new_content if fp.new_content is not None else "\n".join(
                l for h in fp.hunks for l in h.new_lines) + "\n"
            staged[fp.path] = content; continue
        new_content, err = _apply_hunks(current, fp.hunks)
        if err:
            errors.append(f"{fp.path}: {err}"); continue
        staged[fp.path] = new_content
    if errors:
        return {"applied": False, "errors": errors, "files": []}
    if not dry_run:
        for rel, content in staged.items():
            target = root / rel
            if content is None:
                if target.exists() or target.is_symlink():
                    target.unlink()
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                _write_text(target, content)
    applied = list(staged)
    return {"applied": len(applied) > 0, "errors": [], "files": applied}


# ── transactional application (§2: snapshot → apply test → RED → apply impl → GREEN → rollback on failure) ──
def is_test_path(path: str) -> bool:
    """True for a test file path (so substance scoring can tell test files from source files)."""
    p = (path or "").lower()
    name = Path(p).name
    return ("test" in name) or ("/tests/" in p) or p.startswith("tests/") or "/test/" in p


_UNREADABLE = object()          # snapshot sentinel: the file existed but its bytes could not be read


class PatchTransaction:
    """A best-effort transaction over a set of unified-diff applications. Snapshots every file BEFORE it is
    written, so the whole sequence (apply test_patch → run RED → apply impl_patch → run GREEN) can be rolled
    back to the exact prior bytes if any step fails — the user's repo is never left dirty unless kept on purpose.

    Not a database: it relies on snapshots of file CONTENT, so concurrent external writers are out of scope.
    Usage:
        with PatchTransaction(repo) as tx:
            tx.apply_test_patch(test_plan); ... ; tx.apply_impl_patch(impl_plan)
            tx.commit()                  # keep changes; without commit the context manager rolls back
    """
    def __init__(self, repo_root: str):
        self.repo_root = repo_root
        # rel_path → original BYTES (byte-exact restore: CRLF, encoding, binary all survive), None if it did not
        # exist, or _UNREADABLE when it existed but could not be read (then rollback must NOT delete it).
        self._snapshots: Dict[str, object] = {}
        self.touched: List[str] = []
        self.committed = False

    def _snapshot(self, rel_path: str) -> None:
        if rel_path in self._snapshots:
            return
        target = Path(self.repo_root) / rel_path
        if not (target.exists() or target.is_symlink()):
            self._snapshots[rel_path] = None
            return
        try:
            self._snapshots[rel_path] = target.read_bytes() if target.is_file() else _UNREADABLE
        except OSError:
            self._snapshots[rel_path] = _UNREADABLE

    def apply(self, plan: PatchPlan, dry_run: bool = False) -> dict:
        """Validate, snapshot every targeted file, then apply. Snapshots are taken even on a failed apply so a
        partial write can still be rolled back."""
        ok, perrs = validate_patch_paths(plan, self.repo_root)
        if not ok:
            return {"applied": False, "errors": perrs, "files": []}
        for fp in plan.files:
            self._snapshot(fp.path)
        res = apply_patch_plan(plan, self.repo_root, dry_run=dry_run)
        for f in res.get("files", []):
            if f not in self.touched:
                self.touched.append(f)
        return res

    def apply_test_patch(self, plan: PatchPlan, dry_run: bool = False) -> dict:
        return self.apply(plan, dry_run=dry_run)

    def apply_impl_patch(self, plan: PatchPlan, dry_run: bool = False) -> dict:
        return self.apply(plan, dry_run=dry_run)

    def rollback(self) -> List[str]:
        """Restore every snapshotted file to its original bytes (deleting files that did not exist before).
        Returns the list of restored paths. Idempotent; clears the transaction."""
        restored = []
        for rel, original in self._snapshots.items():
            target = Path(self.repo_root) / rel
            try:
                if original is _UNREADABLE:
                    continue                      # existed but unreadable → never delete what we cannot restore
                if original is None:
                    if target.exists() and not target.is_dir():
                        target.unlink()
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(original)
                restored.append(rel)
            except OSError:
                pass
        self._snapshots.clear()
        self.touched.clear()
        return restored

    def commit(self) -> None:
        """Keep all changes; the context manager will not roll back."""
        self.committed = True
        self._snapshots.clear()

    def __enter__(self) -> "PatchTransaction":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if not self.committed:
            self.rollback()
        return False


# ── substance scoring (§9: a patch must change real source code, not cheat the test) ──
_COSMETIC_PREFIXES = ("#", '"', "'", "//", "/*", "*")
_TEST_WEAKENERS = ("pytest.skip", "pytest.mark.skip", "pytest.mark.xfail", "unittest.skip",
                   "skipif", "@skip", "raises(", "xfail")


def _added(patch: str) -> List[str]:
    return [l[1:] for l in (patch or "").splitlines() if l.startswith("+") and not l.startswith("+++")]


def _is_cosmetic_lines(added: List[str]) -> bool:
    code = [l.strip() for l in added if l.strip() and not l.strip().startswith(_COSMETIC_PREFIXES)]
    return bool(added) and not code


def patch_substance_evidence(test_patch: str, impl_patch: str) -> Dict:
    """Diagnose how SUBSTANTIVE an implementation patch is (does it change real source, or cheat the test?).

    Returns flags the loop turns into a penalty: a patch that only edits the test, adds a skip/xfail, or
    flips an expected value to make the test pass — rather than changing non-test source — must not win."""
    impl = parse_unified_diff(impl_patch) if (impl_patch or "").strip() else PatchPlan()
    src_files = [f for f in impl.files if not is_test_path(f.path)]
    test_files = [f for f in impl.files if is_test_path(f.path)]
    added = _added(impl_patch)
    src_added = _added("\n".join(  # only the added lines that land in non-test files
        l for f in src_files for h in f.hunks for l in (["+" + x for x in h.new_lines])))
    has_impl = bool((impl_patch or "").strip())
    touches_source = bool(src_files) and any(
        l.strip() and not l.strip().startswith(_COSMETIC_PREFIXES)
        for f in src_files for h in f.hunks for l in h.new_lines)
    only_test_changed = has_impl and bool(test_files) and not src_files
    skips_test = any(any(w in l for w in _TEST_WEAKENERS) for l in added)
    # weakens an assertion: the impl patch edits a test file and removes/replaces an `assert` line
    weakens_test = any(
        ("assert" in l) for f in test_files for h in f.hunks for l in h.old_lines) and bool(test_files)
    removes_test = any(f.is_delete and is_test_path(f.path) for f in impl.files)
    only_cosmetic = _is_cosmetic_lines(added)
    reasons = []
    score = 1.0
    if not has_impl:
        score = 0.0; reasons.append("no implementation patch")
    if only_cosmetic:
        score = min(score, 0.1); reasons.append("implementation adds only comments/blank lines")
    if only_test_changed:
        score = 0.0; reasons.append("implementation modifies only the test, not source")
    if skips_test:
        score = 0.0; reasons.append("implementation skips/xfails the test instead of fixing it")
    if removes_test:
        score = 0.0; reasons.append("implementation deletes the test")
    if weakens_test:
        score = min(score, 0.1); reasons.append("implementation weakens an assertion in the test")
    if has_impl and not touches_source and not only_test_changed and not only_cosmetic:
        score = min(score, 0.3); reasons.append("no real change to a non-test source file")
    return {"score": round(max(0.0, min(1.0, score)), 3), "reasons": reasons,
            "touches_source": touches_source, "only_test_changed": only_test_changed,
            "skips_test": skips_test, "weakens_test": weakens_test, "removes_test": removes_test,
            "only_cosmetic": only_cosmetic, "source_files": [f.path for f in src_files],
            "test_files": [f.path for f in test_files], "added_source_lines": len(src_added)}


def patch_substance_score(test_patch: str, impl_patch: str) -> float:
    """A scalar in [0,1]: high only when the implementation patch changes real, non-test source code.
    Penalises cosmetic-only, test-only, skip/xfail, assertion-weakening and test-deleting 'fixes'."""
    return patch_substance_evidence(test_patch, impl_patch)["score"]
