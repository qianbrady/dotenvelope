"""Scan a source tree for environment-variable reads.

Python files are parsed with the stdlib :mod:`ast`, so comments, docstrings
and string literals are never misreported, and default arguments are seen
directly. If a file fails to parse we fall back to a line-based regex scan.

Node/JS files are scanned with line-based regexes; `//` and `/* ... */`
comments are blanked out first (string literals that happen to contain
``process.env.X`` text are a documented false-positive source).

Dynamic access (``os.environ.get(os.environ["A"])``, spread of ``process.env``,
``os.environ[var_name]``, ``import os as x``) is invisible to this scanner by
design; such code should keep its variables in the example file anyway.
"""

from __future__ import annotations

import ast
import os
import re
from dataclasses import dataclass
from pathlib import Path

PY_EXTENSIONS = frozenset({".py", ".pyw", ".pyi"})
JS_EXTENSIONS = frozenset({".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx"})
SOURCE_EXTENSIONS = PY_EXTENSIONS | JS_EXTENSIONS

# Directories that never contain first-party source worth auditing.
SKIP_DIRS = frozenset({
    "node_modules", ".venv", "venv", "env", "__pycache__", ".git",
    ".hg", ".svn", ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    ".mypy", "dist", "build", ".idea", ".vscode", ".direnv",
    "site-packages", ".venv_", "venv_", "eggs",
})

_PY_RE = {
    "os.environ.get": re.compile(
        r"""os\.environ\.get\(\s*['"]([A-Za-z_][A-Za-z0-9_]*)['"](\s*,\s*[^)]*)?\s*\)"""
    ),
    "os.getenv": re.compile(
        r"""os\.getenv\(\s*['"]([A-Za-z_][A-Za-z0-9_]*)['"](\s*,\s*[^)]*)?\s*\)"""
    ),
    "os.environ[...]": re.compile(
        r"""os\.environ\[\s*['"]([A-Za-z_][A-Za-z0-9_]*)['"]\s*\]"""
    ),
}

_JS_RE = {
    "process.env.X": re.compile(r"""process\.env\.([A-Za-z_$][A-Za-z0-9_$]*)"""),
    "process.env['X']": re.compile(
        r"""process\.env\[\s*['"]([A-Za-z_$][A-Za-z0-9_$]*)['"]\s*\]"""
    ),
}

_FALLBACK_RE = re.compile(r"""\s*(\?\?|\|\|)""")


def _blank_js_comments(text: str) -> str:
    """Blank ``//`` and ``/* */`` comments (keeping newlines) so regexes never
    match comment text. Fallback on pathological input: return raw text."""
    chars = list(text)
    n = len(chars)
    i = 0
    while i < n:
        if chars[i] == "/" and i + 1 < n:
            if chars[i + 1] == "/":  # line comment
                chars[i] = chars[i + 1] = " "
                i += 2
                while i < n and chars[i] not in ("\n", "\r"):
                    chars[i] = " "
                    i += 1
            elif chars[i + 1] == "*":  # block comment
                chars[i] = chars[i + 1] = " "
                i += 2
                while i < n:
                    if chars[i] == "*" and i + 1 < n and chars[i + 1] == "/":
                        chars[i] = chars[i + 1] = " "
                        i += 2
                        break
                    if chars[i] not in ("\n", "\r"):
                        chars[i] = " "
                    i += 1
            else:
                i += 1
        else:
            i += 1
    return "".join(chars)


@dataclass(frozen=True)
class Occ:
    """One read site of one environment variable."""

    file: str  # POSIX-joined path relative to the scanned root
    line: int  # 1-based
    pattern: str  # human name of the matched syntax
    has_default: bool  # a fallback is supplied at this read site


@dataclass
class ScanResult:
    """Deterministic scan outcome: every list below is insertion-ordered."""

    files_scanned: int
    dirs_skipped: int
    by_var: dict[str, list[Occ]]  # var -> occurrences, insertion order

    def variables(self) -> list[str]:
        return sorted(self.by_var)

    def occurrences(self, var: str) -> list[Occ]:
        return self.by_var.get(var, [])

    def all_defaults(self, var: str) -> bool:
        """True when every read site of *var* supplies a fallback."""
        occs = self.by_var.get(var)
        if occs is None:
            return True
        return all(o.has_default for o in occs)


def _line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def _node_has_default(text: str, end: int) -> bool:
    return _FALLBACK_RE.match(text, end) is not None


def _is_os_attr(node: ast.AST, names: tuple[str, ...]) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "os"
        and node.attr in names
    )


def _string_literal(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _scan_python_ast(
    masked: str, rel: str, by_var: dict[str, list[Occ]]
) -> bool:
    """AST-based python scan; returns False when the file does not parse."""
    try:
        tree = ast.parse(masked)
    except SyntaxError:
        return False

    found: list[tuple[int, str, str, bool]] = []  # (line, var, pattern, has_default)
    for node in ast.walk(tree):
        # os.environ.get("X") / os.environ.get("X", default)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and _is_os_attr(node.func.value, ("environ",))
            and node.func.attr == "get"
        ):
            var = _string_literal(node.args[0]) if node.args else None
            if var is not None:
                found.append((node.lineno, var, "os.environ.get", len(node.args) >= 2))

        # os.getenv("X") / os.getenv("X", default)
        elif (
            isinstance(node, ast.Call)
            and _is_os_attr(node.func, ("getenv",))
        ):
            var = _string_literal(node.args[0]) if node.args else None
            if var is not None:
                found.append((node.lineno, var, "os.getenv", len(node.args) >= 2))

        # os.environ["X"] -> never has a default
        elif (
            isinstance(node, ast.Subscript)
            and _is_os_attr(node.value, ("environ",))
        ):
            var = _string_literal(node.slice)
            if var is not None:
                found.append((node.lineno, var, "os.environ[...]", False))

    for line, var, pattern, has_default in sorted(found):
        by_var.setdefault(var, []).append(Occ(rel, line, pattern, has_default))
    return True


def _scan_text(
    text: str, suffix: str, rel: str, by_var: dict[str, list[Occ]]
) -> None:
    """Scan one file's content, appending occurrences. *text* is raw decoded."""
    if suffix in PY_EXTENSIONS:
        if _scan_python_ast(text, rel, by_var):
            return
        # syntax error -> fall back to the line-based scan
    patterns = _PY_RE if suffix in PY_EXTENSIONS else _JS_RE
    text = _blank_js_comments(text) if suffix in JS_EXTENSIONS else text
    for pattern, occs in patterns.items():
        for m in occs.finditer(text):
            var = m.group(1)
            if suffix not in PY_EXTENSIONS:
                has_default = _node_has_default(text, m.end())
            else:  # python fallback regexes: "os.environ[...]" has no group 2
                has_default = pattern != "os.environ[...]" and m.group(2) is not None
            by_var.setdefault(var, []).append(
                Occ(rel, _line_of(text, m.start()), pattern, has_default)
            )


def scan_tree(root: Path) -> ScanResult:
    """Walk *root* (deterministically, sorted) and collect every read site."""
    by_var: dict[str, list[Occ]] = {}
    files_scanned = 0
    dirs_skipped = 0

    for dirpath, dirnames, filenames in os.walk(root):
        kept = []
        for name in sorted(dirnames):
            if name in SKIP_DIRS or name.startswith("."):
                dirs_skipped += 1
            else:
                kept.append(name)
        dirnames[:] = kept

        for name in sorted(filenames):
            path = Path(dirpath) / name
            if path.suffix not in SOURCE_EXTENSIONS:
                continue  # non-source files are ignored silently
            try:
                raw = path.read_bytes()
            except OSError:
                continue
            text = raw.decode("utf-8", errors="replace")
            rel = path.relative_to(root).as_posix()
            files_scanned += 1
            _scan_text(text, path.suffix, rel, by_var)

    return ScanResult(files_scanned=files_scanned, dirs_skipped=dirs_skipped, by_var=by_var)