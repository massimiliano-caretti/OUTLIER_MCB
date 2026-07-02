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
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class Hunk:
    old_lines: List[str] = field(default_factory=list)   # context + removed (what must currently be present)
    new_lines: List[str] = field(default_factory=list)   # context + added (what replaces it)


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
    p = p.strip()
    if p.startswith(("a/", "b/")):
        return p[2:]
    return p


def parse_unified_diff(text: str) -> PatchPlan:
    """Parse unified-diff `text` into a PatchPlan. Tolerant of leading prose / code fences around the diff."""
    plan = PatchPlan()
    lines = (text or "").splitlines()
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        if line.startswith("--- "):
            old = line[4:].strip()
            if i + 1 >= n or not lines[i + 1].startswith("+++ "):
                plan.parse_errors.append(f"'---' without a following '+++' at line {i}")
                i += 1
                continue
            new = lines[i + 1][4:].strip()
            i += 2
            is_new = old in ("/dev/null", "a//dev/null")
            is_delete = new in ("/dev/null", "b//dev/null")
            path = _strip_prefix(new if not is_delete else old)
            fp = FilePatch(path=path, is_new=is_new, is_delete=is_delete)
            added: List[str] = []
            # read hunks until the next file header or EOF
            while i < n and not lines[i].startswith("--- "):
                if lines[i].startswith("@@"):
                    i += 1
                    hunk = Hunk()
                    while i < n and not lines[i].startswith(("@@", "--- ")):
                        h = lines[i]
                        tag, body = (h[:1], h[1:]) if h else (" ", "")
                        if tag == "+":
                            hunk.new_lines.append(body); added.append(body)
                        elif tag == "-":
                            hunk.old_lines.append(body)
                        elif tag == "\\":         # "\ No newline at end of file" — ignore
                            pass
                        else:                      # context (space) or blank
                            hunk.old_lines.append(body); hunk.new_lines.append(body)
                        i += 1
                    fp.hunks.append(hunk)
                else:
                    i += 1
            if is_new:
                fp.new_content = "\n".join(added) + ("\n" if added else "")
            plan.files.append(fp)
        else:
            i += 1
    if not plan.files and not plan.parse_errors:
        plan.parse_errors.append("no unified-diff file headers ('--- ' / '+++ ') found")
    return plan


def validate_patch_paths(plan: PatchPlan, repo_root) -> Tuple[bool, List[str]]:
    """SECURITY gate: every target must be a relative path that resolves INSIDE repo_root. Rejects absolute
    paths, `..` traversal, and symlink escapes. Returns (ok, errors)."""
    root = Path(repo_root).resolve()
    errors: List[str] = []
    for fp in plan.files:
        p = fp.path
        if not p:
            errors.append("empty target path"); continue
        if Path(p).is_absolute() or p.startswith(("/", "~")):
            errors.append(f"absolute path rejected: {p}"); continue
        if ".." in Path(p).parts:
            errors.append(f"path traversal ('..') rejected: {p}"); continue
        try:
            resolved = (root / p).resolve()
        except (OSError, ValueError):
            errors.append(f"unresolvable path: {p}"); continue
        if root != resolved and root not in resolved.parents:
            errors.append(f"path escapes repo root: {p}"); continue
    return (not errors), errors


def _apply_hunks(content: str, hunks: List[Hunk]) -> Tuple[Optional[str], Optional[str]]:
    """Apply hunks to `content` by locating each old-side block and replacing it. Returns (new_content, error)."""
    lines = content.splitlines()
    for h in hunks:
        old, new = [l for l in h.old_lines], [l for l in h.new_lines]
        if not old:                                  # pure insertion with no anchor → append
            lines.extend(new)
            continue
        # find the contiguous old block in lines (exact, then whitespace-insensitive)
        idx = _find_block(lines, old)
        if idx is None:
            idx = _find_block([l.rstrip() for l in lines], [l.rstrip() for l in old])
        if idx is None:
            return None, f"hunk did not match the file (looking for {old[:2]}…)"
        lines[idx:idx + len(old)] = new
    return "\n".join(lines) + "\n", None


def _find_block(haystack: List[str], needle: List[str]) -> Optional[int]:
    if not needle:
        return None
    for i in range(0, len(haystack) - len(needle) + 1):
        if haystack[i:i + len(needle)] == needle:
            return i
    return None


def apply_patch_plan(plan: PatchPlan, repo_root, dry_run: bool = False) -> dict:
    """Apply a validated PatchPlan to repo_root. ALWAYS validate paths first (callers must not skip it; this
    re-checks). Returns {applied, errors, files}. dry_run=True checks applicability without writing."""
    ok, perrs = validate_patch_paths(plan, repo_root)
    if not ok:
        return {"applied": False, "errors": perrs, "files": []}
    root = Path(repo_root)
    applied, errors = [], list(plan.parse_errors)
    for fp in plan.files:
        target = root / fp.path
        if fp.is_delete:
            if not dry_run and target.exists():
                target.unlink()
            applied.append(fp.path); continue
        if fp.is_new or not target.exists():
            content = fp.new_content if fp.new_content is not None else "\n".join(
                l for h in fp.hunks for l in h.new_lines) + "\n"
            if not dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content)
            applied.append(fp.path); continue
        new_content, err = _apply_hunks(target.read_text(), fp.hunks)
        if err:
            errors.append(f"{fp.path}: {err}"); continue
        if not dry_run:
            target.write_text(new_content)
        applied.append(fp.path)
    return {"applied": len(applied) > 0 and not errors, "errors": errors, "files": applied}


# ── transactional application (§2: snapshot → apply test → RED → apply impl → GREEN → rollback on failure) ──
def is_test_path(path: str) -> bool:
    """True for a test file path (so substance scoring can tell test files from source files)."""
    p = (path or "").lower()
    name = Path(p).name
    return ("test" in name) or ("/tests/" in p) or p.startswith("tests/") or "/test/" in p


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
        self._snapshots: Dict[str, Optional[str]] = {}   # rel_path → original text, or None if it did not exist
        self.touched: List[str] = []
        self.committed = False

    def _snapshot(self, rel_path: str) -> None:
        if rel_path in self._snapshots:
            return
        target = Path(self.repo_root) / rel_path
        try:
            self._snapshots[rel_path] = target.read_text() if target.is_file() else None
        except OSError:
            self._snapshots[rel_path] = None

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
                if original is None:
                    if target.exists():
                        target.unlink()
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(original)
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
