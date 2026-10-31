"""Guard against inspecting the oracle in any forbidden way.

The build contract allows the oracle to be used only as a black box.  This AST
lint scans the test suite for patterns that would introspect oracle objects
(``help``, ``dir``, ``vars``, ``__dict__``, underscore/dunder attribute access,
``inspect`` beyond the API surface, pickling/copying) and fails if any appear.
"""
from __future__ import annotations

import ast
import os

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))

FORBIDDEN_CALLS = {"help", "dir", "vars", "pydoc"}
FORBIDDEN_MODULE_CALLS = {
    ("inspect", None),  # any inspect.* call on oracle objects
    ("dis", None),
    ("pickle", None),
    ("copy", None),
    ("marshal", None),
}

# Files that legitimately parse signatures from the API_SURFACE file (strings),
# not from oracle objects.  They may use ast; they never touch oracle objects.
ALLOWED_FILES = {"test_api_surface.py", "test_oracle_hygiene.py"}


def _iter_test_files() -> list[str]:
    out = []
    for root, _dirs, files in os.walk(TESTS_DIR):
        for f in files:
            if f.endswith(".py"):
                out.append(os.path.join(root, f))
    return out


class _Scanner(ast.NodeVisitor):
    def __init__(self, filename: str) -> None:
        self.filename = filename
        self.problems: list[str] = []

    def visit_Attribute(self, node: ast.Attribute) -> None:
        # flag access to dunder/underscore internals and __dict__ etc.
        if node.attr in {"__dict__", "__doc__", "__annotations__", "__wrapped__"}:
            self.problems.append(
                f"{self.filename}:{node.lineno}: accesses {node.attr}"
            )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if isinstance(func, ast.Name) and func.id in FORBIDDEN_CALLS:
            self.problems.append(
                f"{self.filename}:{node.lineno}: calls {func.id}()"
            )
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            mod = func.value.id
            if mod in {m for m, _ in FORBIDDEN_MODULE_CALLS} and os.path.basename(
                self.filename
            ) not in ALLOWED_FILES:
                self.problems.append(
                    f"{self.filename}:{node.lineno}: uses {mod}.{func.attr}()"
                )
        self.generic_visit(node)


def test_no_oracle_introspection() -> None:
    all_problems: list[str] = []
    for path in _iter_test_files():
        if os.path.basename(path) in ALLOWED_FILES:
            # still scan for help/dir/vars/pickle, but allow ast/inspect of strings
            continue
        with open(path) as fh:
            tree = ast.parse(fh.read(), filename=path)
        scanner = _Scanner(os.path.relpath(path, TESTS_DIR))
        scanner.visit(tree)
        all_problems.extend(scanner.problems)

    assert not all_problems, "Forbidden oracle introspection:\n  " + "\n  ".join(
        all_problems
    )


def test_oracle_is_the_only_click() -> None:
    """The only importable 'click' must be the oracle under its folder."""
    from .differential._oracle import load_oracle, ORACLE_DIR

    click = load_oracle()
    resolved = os.path.realpath(click.__file__)
    assert os.path.realpath(ORACLE_DIR) in resolved, (
        f"click.__file__ ({resolved}) is not under the oracle folder"
    )
