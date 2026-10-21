"""Async-purity panel check (issue #396).

Mechanism (Fluent Python 2e ch.21, "The All-or-Nothing Problem"): once a
codebase goes async, every I/O function on an async path must be an async
version or be delegated. A single blocking sync call (requests.get,
time.sleep, bare open()) silently blocks the whole event loop -- no
exception, just a loop that stops yielding.

Enforcement shape: deterministic AST check, hand-coded rules, zero LLM in
the hot path. Flags blocking sync calls inside `async def` bodies:

- requests.* (get/post/put/delete), time.sleep
- bare open() / file read-write without delegation

Exemptions (no false positives):
- calls routed through asyncio.to_thread / loop.run_in_executor
- allowlisted async facades (Motor-style: async API over a threaded core),
  allowlist by module name, explicit and reviewable
"""

import ast
import os

CHECK_ID = "async-purity"
PERSONA = "correctness"
SEVERITY = "medium"

# (module, attr) pairs for blocking sync calls.
BLOCKING_CALLS = {
    ("requests", "get"),
    ("requests", "post"),
    ("requests", "put"),
    ("requests", "delete"),
    ("requests", "patch"),
    ("requests", "head"),
    ("requests", "options"),
    ("time", "sleep"),
    ("os", "system"),
    ("subprocess", "run"),
    ("subprocess", "call"),
    ("subprocess", "check_output"),
    ("subprocess", "check_call"),
}

# Bare builtin calls that block.
BLOCKING_BUILTINS = {"open", "input"}

# Async facades: async API over a threaded/sync core. Calls into these
# modules are exempt. Explicit and reviewable -- add a module here only
# with a review noting why its API is non-blocking.
ALLOWLIST_MODULES = {
    "motor",  # Motor: async MongoDB driver over a threaded core (ch.21 p.797)
}

# Dotted names that delegate to a thread (blocking calls nested inside
# are exempt). The trailing-attribute form covers loop.run_in_executor
# and chained asyncio.get_event_loop().run_in_executor.
DELEGATING_DOTTED = {
    ("asyncio", "to_thread"),
    ("to_thread",),
}
DELEGATING_ATTRS = {"run_in_executor"}


def _dotted(func: ast.AST) -> str:
    """Full dotted name of a call target, or "" if unresolvable.

    requests.get -> "requests.get". c.parser.open -> "c.parser.open"
    (NOT collapsed to "open": a deep chain is not the builtin). Anything
    built on a call/subscript result is unresolvable -> "".
    """
    parts: list[str] = []
    while isinstance(func, ast.Attribute):
        parts.append(func.attr)
        func = func.value
    if isinstance(func, ast.Name):
        parts.append(func.id)
        return ".".join(reversed(parts))
    return ""


def _attr(func: ast.AST) -> str:
    """Bare attribute name of a call target, or ""."""
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _is_delegating(dotted: str, attr: str) -> bool:
    parts = tuple(dotted.split(".")) if dotted else ()
    return parts in DELEGATING_DOTTED or attr in DELEGATING_ATTRS


class _Visitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.in_async = 0
        self.in_delegated = 0
        # from X import Y  ->  Y (or asname): (X, Y). Resolves `from requests
        # import get` so bare `get(url)` is recognized as requests.get, and
        # `from requests import get as rget` as requests.get via rget.
        self.imported: dict[str, tuple[str, str]] = {}
        # Parameter names shadowing module names: `async def f(requests)`
        # means `requests.get` inside is not the module. Tracked per scope.
        self.shadowed: list[set[str]] = []
        self.findings: list[tuple[int, str]] = []

    # -- scope tracking -------------------------------------------------
    def _visit_function(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, is_async: bool
    ) -> None:
        params = {a.arg for a in node.args.args}
        params.update(a.arg for a in node.args.kwonlyargs)
        if node.args.vararg:
            params.add(node.args.vararg.arg)
        if node.args.kwarg:
            params.add(node.args.kwarg.arg)
        self.shadowed.append(params)
        if is_async:
            self.in_async += 1
        # Decorators and default values evaluate at def time, not on the
        # event loop: visit the body only.
        for stmt in node.body:
            self.visit(stmt)
        if is_async:
            self.in_async -= 1
        self.shadowed.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node, True)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node, False)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        params = {a.arg for a in node.args.args}
        self.shadowed.append(params)
        self.generic_visit(node)
        self.shadowed.pop()

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.asname:
                # import requests as rq -> rq: (requests, "").
                # The empty attr marks a module alias (vs from-import).
                self.imported[alias.asname] = (alias.name, "")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            for alias in node.names:
                self.imported[alias.asname or alias.name] = (
                    node.module,
                    alias.name,
                )
        self.generic_visit(node)

    # -- call checking ---------------------------------------------------
    def _resolve(self, dotted: str) -> tuple[str, str]:
        """Resolve a call target to (module, attr).

        Handles `requests.get` -> ("requests", "get") and, via import
        tracking, `from requests import get` + `get(url)` ->
        ("requests", "get") and `from requests import get as rget` ->
        ("requests", "get"). Returns ("", "") when unresolvable.
        """
        if not dotted:
            return "", ""
        parts = dotted.split(".")
        if len(parts) >= 2:
            mod, attr = parts[0], parts[-1]
            # Resolve `import requests as rq`: rq -> requests.
            alias = self.imported.get(mod)
            if alias and alias[1] == "":
                mod = alias[0]
            if not any(mod in scope for scope in self.shadowed):
                return mod, attr
            return "", ""
        # Bare name: resolve via from-imports.
        hit = self.imported.get(dotted)
        if hit and not any(dotted in scope for scope in self.shadowed):
            return hit
        return "", ""

    def _is_builtin_call(self, dotted: str) -> bool:
        return (
            "." not in dotted
            and dotted in BLOCKING_BUILTINS
            and not any(dotted in scope for scope in self.shadowed)
        )

    def visit_Call(self, node: ast.Call) -> None:
        dotted = _dotted(node.func)
        if _is_delegating(dotted, _attr(node.func)):
            self.in_delegated += 1
            self.generic_visit(node)
            self.in_delegated -= 1
            return
        if self.in_async and not self.in_delegated:
            mod, attr = self._resolve(dotted)
            if (
                mod
                and mod not in ALLOWLIST_MODULES
                and (mod, attr) in BLOCKING_CALLS
            ):
                self.findings.append((node.lineno, dotted or attr))
            elif self._is_builtin_call(dotted):
                self.findings.append((node.lineno, dotted))
        self.generic_visit(node)


def check_tree(tree: ast.AST) -> list[tuple[int, str]]:
    """Blocking sync calls inside async def bodies.

    Returns [(lineno, dotted_name)] sorted by line. Pure function of the
    AST; stdlib only.
    """
    visitor = _Visitor()
    visitor.visit(tree)
    return sorted(visitor.findings)


def check_source(source: str) -> list[tuple[int, str]]:
    """Parse source and run the check. Syntax errors yield no findings
    (a file that does not parse is not this check's problem)."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return []
    return check_tree(tree)


def config_fingerprint() -> str:
    """Hash of the check's behavior-defining tables. The decision-cache
    registry fingerprint includes this: editing BLOCKING_CALLS (or any
    table) expires memoized decisions.
    """
    import hashlib
    import json

    payload = {
        "blocking": sorted(BLOCKING_CALLS),
        "builtins": sorted(BLOCKING_BUILTINS),
        "allowlist": sorted(ALLOWLIST_MODULES),
        "delegating_dotted": sorted(DELEGATING_DOTTED),
        "delegating_attrs": sorted(DELEGATING_ATTRS),
    }
    return hashlib.sha256(json.dumps(payload).encode("utf-8")).hexdigest()[:16]


WHY = (
    "a blocking sync call inside an async def blocks the whole event "
    "loop with no exception -- use an async client or delegate with "
    "asyncio.to_thread"
)


def findings_for_diff(
    reviewable_lines: list[dict], project_root: str
) -> list[dict]:
    """Panel findings for added lines only.

    `reviewable_lines` are {file, line, text} dicts already filtered by the
    panel's exemption rules. Files are read from `project_root` (the working
    tree holds the change under review); only violations on added lines are
    reported, so pre-existing problems never block a new change.
    """
    added_by_file: dict[str, set[int]] = {}
    for ln in reviewable_lines:
        path = ln["file"]
        if not path.endswith((".py", ".pyi")):
            continue
        added_by_file.setdefault(path, set()).add(ln["line"])

    findings: list[dict] = []
    for rel_path, added_lines in sorted(added_by_file.items()):
        full = os.path.join(project_root, rel_path)
        try:
            with open(full, encoding="utf-8", errors="replace") as fh:
                source = fh.read()
        except OSError:
            continue
        src_lines = source.splitlines()
        for lineno, dotted in check_source(source):
            if lineno not in added_lines:
                continue
            snippet = (
                src_lines[lineno - 1].strip()[:160]
                if 0 < lineno <= len(src_lines)
                else dotted
            )
            findings.append(
                {
                    "persona": PERSONA,
                    "check": CHECK_ID,
                    "severity": SEVERITY,
                    "file": rel_path,
                    "line": lineno,
                    "why": WHY,
                    "snippet": snippet,
                    "source": "local",
                }
            )
    return findings
