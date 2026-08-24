from __future__ import annotations

import ast
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from ui_qt.administration.help_dialog import HelpDialog


APP = QApplication.instance() or QApplication([])


def _enter(*, repeat=False):
    return QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier, "", repeat, 1)


def test_abre_topico_global_com_tabela_pesquisavel():
    dialog = HelpDialog()
    assert dialog.table.rowCount() > 0
    dialog.search.setText("finalizar venda")
    assert dialog.table.rowCount() == 0
    index = dialog.topic.findData("vendas"); dialog.topic.setCurrentIndex(index)
    assert dialog.table.rowCount() == 1
    assert dialog.table.item(0, 0).text() == "F9"
    dialog.close()


def test_enter_na_tabela_inclusive_auto_repeat_nao_executa_acao():
    dialog = HelpDialog(context="impressao")
    for repeat in (False, True): assert dialog.eventFilter(dialog.table, _enter(repeat=repeat)) is True
    dialog.close()


def test_tela_e_somente_leitura_e_nao_importa_infraestrutura():
    source = Path(__file__).parents[1].joinpath("ui_qt/administration/help_dialog.py").read_text(encoding="utf-8")
    modules=[]
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import): modules.extend(alias.name.lower() for alias in node.names)
        elif isinstance(node, ast.ImportFrom): modules.append(str(node.module or "").lower())
    for forbidden in ("database", "repositories", "fiscal", "sefaz", "subprocess", "webbrowser"):
        assert not any(forbidden in module for module in modules)
