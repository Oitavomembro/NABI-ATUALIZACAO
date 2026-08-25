from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import QEvent, QObject, QRunnable, Qt, QThreadPool, Signal, Slot
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QGridLayout, QHBoxLayout, QLabel, QMessageBox,
    QPlainTextEdit, QPushButton, QVBoxLayout,
)

from core.sensitive_data import sanitize_text
from services.help_center_service import DiagnosticResult, DiagnosticState


STYLE = """
QDialog{background:#0d1117;color:#f0f6fc;font-size:14px}
QLabel{color:#f0f6fc} QPlainTextEdit{background:#161b22;color:#f0f6fc;
border:1px solid #30363d;border-radius:8px;padding:8px}
QPushButton{background:#21262d;color:#f0f6fc;border:1px solid #30363d;
border-radius:9px;min-height:40px;padding:7px 12px;font-weight:800;text-align:left}
QPushButton:focus{border:2px solid #58a6ff}
"""

STATE_COLORS = {
    DiagnosticState.SAUDAVEL: "#2ea043",
    DiagnosticState.ALERTA: "#d29922",
    DiagnosticState.FALHA: "#f85149",
    DiagnosticState.INCONCLUSIVO: "#8b949e",
}


class _DiagnosticSignals(QObject):
    completed = Signal(int, object, object)


class DiagnosticWorker(QRunnable):
    def __init__(self, generation: int, service) -> None:
        super().__init__(); self.generation = generation; self.service = service
        self.signals = _DiagnosticSignals()

    @Slot()
    def run(self) -> None:
        try: results, error = self.service.run(), None
        except Exception as caught: results, error = None, caught
        self.signals.completed.emit(self.generation, results, error)


class HelpCenterDialog(QDialog):
    """Central de Socorro somente diagnóstica; não oferece reparo ou mutação."""

    def __init__(
        self, service, parent=None, *, worker_pool=None,
        notifier: Callable[[str, str], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.pool = worker_pool or QThreadPool.globalInstance()
        self._notifier = notifier or self._show_message
        self._generation = 0; self._running = False; self._workers = []
        self._navigation = ()
        self.results: tuple[DiagnosticResult, ...] = ()
        self.setWindowTitle("Central de Socorro NabiCode")
        self.resize(980, 720); self.setMinimumSize(760, 580); self.setStyleSheet(STYLE)
        root = QVBoxLayout(self)
        heading = QHBoxLayout()
        title = QLabel("CENTRAL DE SOCORRO")
        title.setStyleSheet("font-size:26px;font-weight:900;color:#58a6ff")
        self.progress = QLabel("Aguardando diagnóstico")
        self.progress.setStyleSheet("color:#8b949e;font-weight:700")
        heading.addWidget(title); heading.addStretch(); heading.addWidget(self.progress)
        root.addLayout(heading)
        warning = QLabel(
            "Somente diagnóstico. Esta tela não repara, não altera banco e não executa "
            "comandos. FALHA indica atenção técnica; não autoriza concluir causa ou correção."
        )
        warning.setWordWrap(True); warning.setStyleSheet(
            "background:#161b22;border-left:5px solid #d29922;padding:10px;font-weight:700"
        )
        root.addWidget(warning)
        grid = QGridLayout(); grid.setSpacing(10); self.cards = []
        for index in range(6):
            card = QPushButton("AGUARDANDO\nDiagnóstico ainda não executado")
            card.setAccessibleName(f"Diagnóstico {index + 1}")
            card.setMinimumHeight(92); card.clicked.connect(lambda _checked=False, row=index: self.show_detail(row))
            card.installEventFilter(self); grid.addWidget(card, index // 3, index % 3)
            self.cards.append(card)
        root.addLayout(grid)
        detail_title = QLabel("DETALHES SANITIZADOS")
        detail_title.setStyleSheet("font-size:17px;font-weight:900")
        root.addWidget(detail_title)
        self.details = QPlainTextEdit(); self.details.setReadOnly(True)
        self.details.setPlainText("Execute o diagnóstico para ver detalhes seguros.")
        self.details.installEventFilter(self); root.addWidget(self.details, 1)
        protected = QLabel(
            "PROTEGIDO E TESTADO: leitura isolada por portas; continuidade entre checks; "
            "redação de dados sensíveis; descarte de resposta atrasada; relatório atômico.\n"
            "NÃO TESTADO AQUI: homologação física, SEFAZ, impressora real, correção automática ou integridade jurídica."
        )
        protected.setWordWrap(True); protected.setStyleSheet("color:#8b949e;padding:6px")
        root.addWidget(protected)
        footer = QHBoxLayout()
        self.run_button = QPushButton("Executar diagnóstico [Enter]")
        self.report_button = QPushButton("Salvar relatório sanitizado")
        self.report_button.setEnabled(False)
        self.close_button = QPushButton("Fechar [Esc]")
        self.run_button.clicked.connect(self.reload)
        self.report_button.clicked.connect(self.export_report)
        self.close_button.clicked.connect(self.reject)
        footer.addWidget(self.run_button); footer.addWidget(self.report_button)
        footer.addStretch(); footer.addWidget(self.close_button); root.addLayout(footer)
        self._navigation = tuple(self.cards) + (self.details, self.run_button, self.report_button, self.close_button)
        for widget in (self.run_button, self.report_button, self.close_button): widget.installEventFilter(self)
        self.run_button.setFocus(Qt.FocusReason.OtherFocusReason)

    def _show_message(self, kind: str, message: str) -> None:
        method = QMessageBox.information if kind == "info" else QMessageBox.warning
        method(self, "Central de Socorro", message)

    def reload(self) -> bool:
        if self._running:
            return False
        self._generation += 1; generation = self._generation; self._running = True
        self.progress.setText("Verificando..."); self.run_button.setEnabled(False)
        self.report_button.setEnabled(False)
        worker = DiagnosticWorker(generation, self.service)
        worker.signals.completed.connect(self._loaded); self._workers.append(worker)
        self.pool.start(worker)
        return True

    def _loaded(self, generation: int, results, error) -> None:
        self._workers = [worker for worker in self._workers if worker.generation != generation]
        if generation != self._generation:
            return
        self._running = False; self.run_button.setEnabled(True)
        if error is not None:
            self.results = (); self.progress.setText("Diagnóstico inconclusivo")
            self._notifier("error", sanitize_text(f"Falha segura: {type(error).__name__}"))
            return
        self.results = tuple(results)
        self.progress.setText("Diagnóstico concluído")
        self.report_button.setEnabled(bool(self.results))
        for index, card in enumerate(self.cards):
            if index >= len(self.results):
                card.setText("INCONCLUSIVO\nResultado ausente"); continue
            result = self.results[index]; color = STATE_COLORS[result.state]
            card.setText(f"{result.state.value}\n{sanitize_text(result.entry.title)}")
            card.setAccessibleName(f"{result.entry.title}: {result.state.value}")
            card.setStyleSheet(
                f"border:2px solid {color};border-left:7px solid {color};"
                "font-size:15px;min-height:92px"
            )
        if self.results: self.show_detail(0)

    def show_detail(self, index: int) -> None:
        if not (0 <= index < len(self.results)):
            return
        result = self.results[index]
        technical = sanitize_text(result.technical_id) or "não fornecido"
        self.details.setPlainText(
            f"{sanitize_text(result.entry.title)}\n"
            f"Estado: {result.state.value}\n"
            f"Resultado: {sanitize_text(result.message)}\n"
            f"Identificador técnico: {technical}\n\n"
            "Este resultado é diagnóstico e não executou reparo."
        )

    def export_report(self, destination=None) -> Path | None:
        if not self.results:
            self._notifier("error", "Execute o diagnóstico antes de salvar o relatório.")
            return None
        if not destination:
            destination, _ = QFileDialog.getSaveFileName(
                self, "Salvar relatório sanitizado", "Relatorio_Socorro_NabiCode.json",
                "Relatório JSON (*.json)",
            )
        if not destination: return None
        try: path = self.service.save_report(destination, self.results)
        except Exception as error:
            self._notifier("error", sanitize_text(f"Não foi possível salvar: {type(error).__name__}"))
            return None
        self._notifier("info", f"Relatório sanitizado salvo em {sanitize_text(path)}")
        return path

    def eventFilter(self, watched, event) -> bool:
        if watched in self._navigation and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                event.accept()
                if not event.isAutoRepeat(): self.reject()
                return True
            if event.key() not in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
                return False
            event.accept()
            if event.isAutoRepeat(): return True
            flow = [widget for widget in self._navigation if widget.isVisible() and widget.isEnabled()]
            if watched not in flow: return True
            index = flow.index(watched)
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                flow[max(0, index - 1)].setFocus(Qt.FocusReason.BacktabFocusReason)
            elif watched in self.cards:
                self.show_detail(self.cards.index(watched))
                flow[min(index + 1, len(flow) - 1)].setFocus(Qt.FocusReason.TabFocusReason)
            elif watched is self.run_button: self.reload()
            elif watched is self.report_button: self.export_report()
            elif watched is self.close_button:
                self.reject()
            else:
                flow[min(index + 1, len(flow) - 1)].setFocus(Qt.FocusReason.TabFocusReason)
            return True
        return super().eventFilter(watched, event)

    def reject(self) -> None:
        self._generation += 1
        super().reject()
