from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from pathlib import PurePosixPath


SECRET_FILE_PATTERNS = (
    re.compile(r"(^|/)\.env($|\.)", re.I),
    re.compile(r"\.(pem|key|p12|pfx)$", re.I),
    re.compile(r"(^|/)(id_rsa|id_ed25519|credentials\.json)$", re.I),
)

C2_READ_FORBIDDEN_PATHS = {
    "app.py",
    "render.yaml",
    "changying/production.py",
    "requirements.txt",
    "requirements-dev.txt",
}

C2_READ_FORBIDDEN_PREFIXES = (
    ".github/workflows/",
    "changying/migrations/",
    "migrations/",
)

C2_READ_RISKY_ADDED_LINE_PATTERNS = (
    re.compile(r"\bdb\.(add|add_all|delete|commit|flush|rollback)\s*\("),
    re.compile(r"@app\.(post|put|patch|delete)\s*\("),
    re.compile(r"\b(JWT_SECRET|PASSWORD_PEPPER|authenticated_user|current_user|hash_password|verify_password)\b"),
    re.compile(r"\b(ALTER\s+TABLE|CREATE\s+TABLE|DROP\s+TABLE)\b", re.I),
    re.compile(r"^class\s+\w+\s*\(Base\)\s*:"),
)


def run_git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def is_secret_path(path: str) -> bool:
    normalized = str(PurePosixPath(path))
    return any(pattern.search(normalized) for pattern in SECRET_FILE_PATTERNS)


def is_c2_read_side(branch: str, title: str, body: str) -> bool:
    if not branch.startswith("refactor/c2-"):
        return False
    text = f"{title}\n{body}".lower()
    markers = ("读侧", "纯读取", "只读", "read-side", "read side")
    return any(marker in text for marker in markers)


def changed_files(base: str, head: str) -> list[str]:
    output = run_git("diff", "--name-only", f"{base}...{head}")
    return [line for line in output.splitlines() if line.strip()]


def added_production_lines(base: str, head: str) -> list[tuple[str, str]]:
    output = run_git("diff", "--unified=0", "--no-ext-diff", f"{base}...{head}", "--", "app_v924.py", "changying")
    current_file = ""
    results: list[tuple[str, str]] = []
    for line in output.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:]
            continue
        if not current_file or current_file.startswith("tests/"):
            continue
        if line.startswith("+") and not line.startswith("+++"):
            results.append((current_file, line[1:].strip()))
    return results


WIRING_EXEMPT_MARKER = "wiring-exempt:"
WIRING_ROUTE_DECORATORS = re.compile(
    r"^(?:app|router|[A-Za-z_]\w*_router)\.(?:get|post|put|patch|delete|head|options|route|websocket|on_event|middleware)$"
)


def _is_runtime_python(path: str) -> bool:
    normalized = str(PurePosixPath(path))
    if not normalized.endswith(".py"):
        return False
    if normalized.startswith(("tests/", "scripts/", "docs/", "migrations/")):
        return False
    name = PurePosixPath(normalized).name
    return not (name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py")


def _top_level_symbols(source: str) -> dict[str, bool]:
    """Top-level function/class/CONSTANT names -> True when route/handler-decorated (live by construction)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    symbols: dict[str, bool] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            routed = any(WIRING_ROUTE_DECORATORS.match(ast.unparse(getattr(d, "func", d))) for d in node.decorator_list)
            symbols[node.name] = routed
        elif isinstance(node, ast.Assign) and isinstance(node.value, (ast.Constant, ast.List, ast.Tuple, ast.Dict, ast.Set, ast.JoinedStr)):
            for target in node.targets:
                if isinstance(target, ast.Name) and re.fullmatch(r"[A-Z_][A-Z0-9_]*", target.id):
                    symbols[target.id] = False
    return {name: routed for name, routed in symbols.items() if not (name.startswith("__") and name.endswith("__"))}


def _name_count(source: str, name: str) -> int:
    return len(re.findall(rf"(?<![\w$]){re.escape(name)}(?![\w$])", source))


def find_unwired_symbols(
    changed: list[str],
    read_head: "callable",
    read_base: "callable",
    runtime_files: list[str],
) -> list[str]:
    """New top-level symbols in changed runtime files that no runtime code references.

    A symbol is wired when it is route-decorated, or its name appears in runtime code
    other than its own definition (another file, or elsewhere in the same file).
    Tests do not count: a helper that only tests import is still a shell.
    """
    sources = {path: read_head(path) or "" for path in runtime_files if _is_runtime_python(path)}
    problems: list[str] = []
    for path in changed:
        if not _is_runtime_python(path):
            continue
        new_source = sources.get(path) or read_head(path) or ""
        old_symbols = _top_level_symbols(read_base(path) or "")
        for name, routed in _top_level_symbols(new_source).items():
            if name in old_symbols or routed:
                continue
            total = sum(_name_count(text, name) for text in sources.values())
            if total <= 1:  # the definition itself is the only occurrence
                problems.append(f"new symbol is not referenced by any runtime code: {path}:{name}")
    return problems


def evaluate(
    files: list[str],
    added_lines: list[tuple[str, str]],
    *,
    branch: str,
    title: str,
    body: str,
) -> list[str]:
    errors: list[str] = []

    for path in files:
        if is_secret_path(path):
            errors.append(f"secret/private-key-like file is not allowed: {path}")

    if not is_c2_read_side(branch, title, body):
        return errors

    for path in files:
        if path in C2_READ_FORBIDDEN_PATHS or path.startswith(C2_READ_FORBIDDEN_PREFIXES):
            errors.append(f"C2 read-side PR cannot change high-risk path: {path}")

    for path, line in added_lines:
        for pattern in C2_READ_RISKY_ADDED_LINE_PATTERNS:
            if pattern.search(line):
                errors.append(f"C2 read-side risky production addition in {path}: {line[:160]}")
                break

    return errors


def main() -> int:
    base = os.environ.get("HARNESS_BASE_SHA", "").strip()
    head = os.environ.get("HARNESS_HEAD_SHA", "").strip() or "HEAD"
    branch = os.environ.get("HARNESS_BRANCH", "").strip()
    title = os.environ.get("HARNESS_PR_TITLE", "")
    body = os.environ.get("HARNESS_PR_BODY", "")

    if not base:
        print("HARNESS_BASE_SHA is required", file=sys.stderr)
        return 2

    files = changed_files(base, head)
    added_lines = added_production_lines(base, head)
    profile = "c2-read" if is_c2_read_side(branch, title, body) else "general"

    print(f"Harness profile: {profile}")
    print("Changed files:")
    for path in files:
        print(f" - {path}")

    errors = evaluate(
        files,
        added_lines,
        branch=branch,
        title=title,
        body=body,
    )
    if WIRING_EXEMPT_MARKER not in body.lower():
        runtime_files = [
            path
            for path in run_git("ls-tree", "-r", "--name-only", head).splitlines()
            if _is_runtime_python(path)
        ]

        def read_at(ref: str):
            def read(path: str) -> str:
                try:
                    return run_git("show", f"{ref}:{path}")
                except subprocess.CalledProcessError:
                    return ""

            return read

        errors.extend(find_unwired_symbols(files, read_at(head), read_at(base), runtime_files))
    if errors:
        print("\nHarness guard blocked this PR:", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1

    print("\nHarness guard passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
