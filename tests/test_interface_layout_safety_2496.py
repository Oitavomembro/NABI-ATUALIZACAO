from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ui.layout_manager import LayoutManager

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {"tests", "build", "dist", ".venv", "__pycache__", ".pytest_cache"}
GEOMETRY_MANAGERS = {"pack", "grid"}
WIDGET_NAMES = {
    "Frame", "LabelFrame", "Canvas", "Treeview", "Scrollbar", "Label", "Button",
    "Entry", "Text", "Combobox", "Checkbutton", "Radiobutton", "Scale",
}


def _qualified_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parts: list[str] = []
        current: ast.AST = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
            return ".".join(reversed(parts))
    return None


def _constructor_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _is_widget_constructor(call: ast.Call) -> bool:
    name = _constructor_name(call.func)
    return bool(name and (name.startswith("CTk") or name in WIDGET_NAMES))


def _iter_function_scopes(tree: ast.AST):
    yield from (
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    )


def _scope_nodes(scope: ast.AST):
    stack = list(getattr(scope, "body", ()))
    while stack:
        node = stack.pop()
        yield node
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        stack.extend(ast.iter_child_nodes(node))


def _mixed_geometry_parents(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"), filename=str(path))
    violations: list[str] = []

    for scope in _iter_function_scopes(tree):
        child_parent: dict[str, str] = {}
        parent_managers: dict[str, set[str]] = {}

        for node in _scope_nodes(scope):
            if isinstance(node, ast.Assign):
                targets = node.targets
                value = node.value
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
                value = node.value
            else:
                targets = []
                value = None

            if isinstance(value, ast.Call) and value.args and _is_widget_constructor(value):
                parent = _qualified_name(value.args[0])
                if parent:
                    for target in targets:
                        child = _qualified_name(target)
                        if child:
                            child_parent[child] = parent

            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in GEOMETRY_MANAGERS
            ):
                child = _qualified_name(node.func.value)
                parent = child_parent.get(child or "")
                if parent:
                    parent_managers.setdefault(parent, set()).add(node.func.attr)

        for parent, managers in parent_managers.items():
            if managers == GEOMETRY_MANAGERS:
                scope_name = getattr(scope, "name", "<module>")
                scope_line = getattr(scope, "lineno", 1)
                violations.append(f"{path.relative_to(PROJECT_ROOT)}:{scope_line}:{scope_name}:{parent}")

    return violations


def test_no_same_parent_has_pack_and_grid_children():
    """Regressão global: um parent não pode ter filhos simultaneamente em pack e grid."""
    violations: list[str] = []
    for path in PROJECT_ROOT.rglob("*.py"):
        if any(part in EXCLUDED_PARTS for part in path.parts):
            continue
        violations.extend(_mixed_geometry_parents(path))
    assert violations == [], "Mistura pack/grid detectada:\n" + "\n".join(violations)


@pytest.mark.parametrize(
    ("width", "height"),
    [(1024, 768), (1280, 720), (1366, 768), (1600, 900), (1920, 1080)],
)
def test_required_resolutions_have_safe_geometry(width: int, height: int):
    geometry, minimum = LayoutManager.window_geometry(width, height)
    geo_width, geo_height = map(int, geometry.split("x"))
    min_width, min_height = minimum

    assert 0 < min_width <= geo_width <= width
    assert 0 < min_height <= geo_height <= height
    assert geo_width <= int(width * 0.94)
    assert geo_height <= int(height * 0.90)


def test_required_resolutions_are_declared_supported():
    required = {(1024, 768), (1280, 720), (1366, 768), (1600, 900), (1920, 1080)}
    assert required.issubset(set(LayoutManager.SUPPORTED_RESOLUTIONS))
