from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_external_connection_methods_do_not_finish_callers_transaction():
    violations = []
    for folder in ("repositories", "services"):
        for path in (ROOT / folder).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            for function in ast.walk(tree):
                if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                arguments = {argument.arg for argument in function.args.args}
                external_names = arguments & {"connection", "conn"}
                if not external_names:
                    continue
                for call in ast.walk(function):
                    if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute):
                        continue
                    if call.func.attr not in {"commit", "rollback", "close"}:
                        continue
                    if isinstance(call.func.value, ast.Name) and call.func.value.id in external_names:
                        violations.append(
                            f"{path.relative_to(ROOT)}:{call.lineno}:{function.name}:{call.func.attr}"
                        )
    assert violations == []
