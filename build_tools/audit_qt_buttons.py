"""Inventory Qt buttons and reject controls without an explicit action contract.

This is intentionally static: it proves that every declared QPushButton is
wired or explicitly classified.  Behavioural correctness remains the job of
the referenced UI tests and must not be inferred from a signal connection.
"""

from __future__ import annotations

import ast
import csv
import tokenize
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "ui_qt"

# Controls that are deliberately non-operational must be named here, with a
# user-facing reason.  A silent button is never accepted.
EXEMPTIONS = {
    ("ui_qt/assistant_nabi/panel.py", "NabiAssistantPanel.__init__", "self.voice"):
        "Voz em preparação; controle permanece desabilitado e não promete ação.",
    ("ui_qt/administration/settings_dialog.py", "SettingsDialog._build_interface_tab", "self.preview_button"):
        "Amostra visual do tema; não é uma ação operacional.",
    ("ui_qt/commercial/report_dialog.py", "ReportDialog.__init__", "self.csv"):
        "Conectado no laço fechado de formatos CSV/XLSX/PDF; habilita somente após gerar relatório.",
    ("ui_qt/commercial/report_dialog.py", "ReportDialog.__init__", "self.xlsx"):
        "Conectado no laço fechado de formatos CSV/XLSX/PDF; habilita somente após gerar relatório.",
    ("ui_qt/commercial/report_dialog.py", "ReportDialog.__init__", "self.pdf"):
        "Conectado no laço fechado de formatos CSV/XLSX/PDF; habilita somente após gerar relatório.",
}


@dataclass(frozen=True)
class ButtonRecord:
    file: str
    scope: str
    target: str
    line: int
    label: str
    connected: bool
    exemption: str = ""

    @property
    def status(self) -> str:
        if self.connected:
            return "CONECTADO"
        if self.exemption:
            return "EXCECAO_DECLARADA"
        return "SEM_ACAO"


def _target_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return f"{node.value.id}.{node.attr}"
    return None


def _button_label(call: ast.Call) -> str:
    if call.args and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str):
        return call.args[0].value.replace("\n", " / ")
    for keyword in call.keywords:
        if keyword.arg == "text" and isinstance(keyword.value, ast.Constant):
            return str(keyword.value.value).replace("\n", " / ")
    return "<dinamico>"


class _ScopeVisitor(ast.NodeVisitor):
    def __init__(self, relative_file: str) -> None:
        self.relative_file = relative_file
        self.stack: list[str] = []
        self.buttons: list[tuple[str, str, int, str]] = []
        self.connections: set[tuple[str, str]] = set()

    def _scope(self) -> str:
        return ".".join(self.stack) or "<module>"

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.stack.append(node.name); self.generic_visit(node); self.stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.stack.append(node.name); self.generic_visit(node); self.stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Assign(self, node: ast.Assign) -> None:
        if isinstance(node.value, ast.Call) and _is_qpushbutton(node.value.func):
            for assigned in node.targets:
                target = _target_name(assigned)
                if target:
                    self.buttons.append((self._scope(), target, node.lineno, _button_label(node.value)))
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if isinstance(node.value, ast.Call) and _is_qpushbutton(node.value.func):
            target = _target_name(node.target)
            if target:
                self.buttons.append((self._scope(), target, node.lineno, _button_label(node.value)))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        function = node.func
        if (
            isinstance(function, ast.Attribute) and function.attr == "connect"
            and isinstance(function.value, ast.Attribute) and function.value.attr == "clicked"
        ):
            target = _target_name(function.value.value)
            if target:
                self.connections.add((self._scope(), target))
        self.generic_visit(node)


def _is_qpushbutton(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Name) and node.id == "QPushButton"
    ) or (
        isinstance(node, ast.Attribute) and node.attr == "QPushButton"
    )


def inventory() -> tuple[ButtonRecord, ...]:
    records: list[ButtonRecord] = []
    for path in sorted(UI_ROOT.rglob("*.py")):
        relative = path.relative_to(ROOT).as_posix()
        visitor = _ScopeVisitor(relative)
        # tokenize.open honours PEP 263 declarations used by a few legacy Qt
        # modules (for example cp1252) instead of assuming UTF-8.
        with tokenize.open(path) as stream:
            source = stream.read()
        visitor.visit(ast.parse(source, filename=str(path)))
        for scope, target, line, label in visitor.buttons:
            # self attributes can be connected by another method of the class;
            # locals must be connected inside their defining method.
            owner = scope.split(".", 1)[0] if target.startswith("self.") else scope
            connected = any(
                candidate_target == target
                and (candidate_scope.split(".", 1)[0] if target.startswith("self.") else candidate_scope) == owner
                for candidate_scope, candidate_target in visitor.connections
            )
            exemption = EXEMPTIONS.get((relative, scope, target), "")
            records.append(ButtonRecord(relative, scope, target, line, label, connected, exemption))
    return tuple(records)


def write_csv(path: Path, records: Iterable[ButtonRecord] | None = None) -> Path:
    rows = tuple(records or inventory())
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, delimiter=";")
        writer.writerow((
            "arquivo", "escopo", "controle", "linha", "rotulo", "estrutura",
            "abriu", "executou", "bloqueou_corretamente", "preservou_dados",
            "retornou_foco", "justificativa",
        ))
        for item in rows:
            # A ligação do sinal não autoriza inferir comportamento. As cinco
            # colunas operacionais começam honestamente como NÃO COMPROVADO e
            # são preenchidas apenas por contratos E2E específicos.
            operational = ("NAO_COMPROVADO",) * 5
            writer.writerow((
                item.file, item.scope, item.target, item.line, item.label,
                item.status, *operational, item.exemption,
            ))
    return path


def main() -> int:
    records = inventory()
    output = write_csv(ROOT / "build_output" / "audits" / "qt_button_matrix.csv", records)
    missing = tuple(item for item in records if item.status == "SEM_ACAO")
    print(f"Botoes inventariados: {len(records)}")
    print(f"Conectados: {sum(item.connected for item in records)}")
    print(f"Excecoes declaradas: {sum(bool(item.exemption) for item in records)}")
    print(f"Sem acao: {len(missing)}")
    print(f"Matriz: {output}")
    for item in missing:
        print(f"SEM_ACAO {item.file}:{item.line} {item.scope} {item.target} {item.label}")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
