from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QDate, QEvent, QObject, QRunnable, QThreadPool, Qt, Signal, Slot
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox, QDateEdit, QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QVBoxLayout, QWidget,
)


STYLE = """
QDialog{background:#101419;color:#eef3f8;font-size:14px} QLabel{color:#eef3f8}
QLineEdit,QDateEdit{background:#171d24;color:#eef3f8;border:1px solid #59636f;border-radius:7px;min-height:38px;padding:0 9px}
QPushButton{background:#303842;color:#eef3f8;border:1px solid #68737f;border-radius:8px;min-height:42px;padding:0 15px;font-weight:800}
QPushButton:focus,QLineEdit:focus,QDateEdit:focus{border:2px solid #4ec9e8}
QPushButton#profile:checked{background:#46515d;border:2px solid #aeb8c2}
QPushButton#primary{background:#1f6f8f;border:1px solid #62c9e8}
QPushButton#primary:disabled{background:#29313a;color:#7d8792;border-color:#3b444e}
QWidget#card{background:#171d24;border:1px solid #4b5662;border-radius:10px}
"""


class _Signals(QObject):
    completed = Signal(int, object, object)


class AccountantPackageWorker(QRunnable):
    def __init__(self, generation: int, application, plan) -> None:
        super().__init__(); self.generation=generation; self.application=application; self.plan=plan; self.signals=_Signals()

    @Slot()
    def run(self) -> None:
        try: result,error=self.application.generate(self.plan),None
        except Exception as caught: result,error=None,caught
        self.signals.completed.emit(self.generation,result,error)


class AccountantCenterDialog(QDialog):
    """Preparação/exportação mensal; não cria lançamentos nem apura tributos."""

    def __init__(self, application, parent=None, *, worker_pool=None, delivery_application=None) -> None:
        super().__init__(parent); self.application=application; self.delivery_application=delivery_application; self.pool=worker_pool or QThreadPool.globalInstance()
        self._generation=0; self._busy=False; self._workers=[]; self._plan=None; self._outcome=None; self._delivery_dialog=None
        self.setWindowTitle("Central do Contador"); self.resize(980,720); self.setMinimumSize(820,620); self.setStyleSheet(STYLE)
        root=QVBoxLayout(self); title=QLabel("CENTRAL DO CONTADOR"); title.setStyleSheet("font-size:27px;font-weight:900;color:#d7e0e8")
        subtitle=QLabel("Prepare fontes do mês sem esconder movimentos, inventar lançamentos ou apurar tributos."); subtitle.setWordWrap(True)
        root.addWidget(title); root.addWidget(subtitle)
        form=QHBoxLayout(); self.competence=QDateEdit(QDate.currentDate()); self.competence.setDisplayFormat("MM/yyyy"); self.competence.setCalendarPopup(True)
        self.cnpj=QLineEdit(); self.cnpj.setPlaceholderText("CNPJ confirmado da empresa")
        self.cnpj_confirmed=QCheckBox("Confirmei o CNPJ da empresa")
        form.addWidget(QLabel("Competência")); form.addWidget(self.competence); form.addWidget(QLabel("CNPJ")); form.addWidget(self.cnpj,1); form.addWidget(self.cnpj_confirmed); root.addLayout(form)
        destination=QHBoxLayout(); self.output=QLineEdit(); self.output.setPlaceholderText("Destino do pacote .zip"); self.choose=QPushButton("Escolher destino"); self.choose.clicked.connect(self._choose_destination); destination.addWidget(self.output,1); destination.addWidget(self.choose); root.addLayout(destination)
        profiles=QHBoxLayout(); self.essential=self._profile_button("PACOTE ESSENCIAL","Entrega curta com resumo, fontes e intercâmbio universal.","ESSENCIAL"); self.complete=self._profile_button("PACOTE COMPLETO","Acrescenta JSON/XLSX auxiliares sem alterar totais.","COMPLETO"); profiles.addWidget(self.essential); profiles.addWidget(self.complete); root.addLayout(profiles)
        self.advanced=QCheckBox("Mostrar opção avançada de Auditoria"); self.audit=self._profile_button("PACOTE DE AUDITORIA","Acrescenta a trilha existente para conferência técnica.","AUDITORIA"); self.audit.setVisible(False); self.advanced.toggled.connect(self.audit.setVisible); root.addWidget(self.advanced); root.addWidget(self.audit)
        self.explanation=QLabel("Essencial e Completo preservam todos os totais e movimentos. Auditoria apenas acrescenta evidências.\nPendências externas como bancos, cartões, folha e contratos permanecem declaradas."); self.explanation.setWordWrap(True); self.explanation.setStyleSheet("background:#171d24;border:1px solid #4b5662;border-radius:8px;padding:12px;color:#c8d1da"); root.addWidget(self.explanation)
        self.review=QPushButton("REVISAR PACOTE"); self.generate_button=QPushButton("GERAR PACOTE REVISADO"); self.generate_button.setObjectName("primary"); self.generate_button.setEnabled(False); self.delivery_button=QPushButton("ENTREGAR AO CONTADOR…"); self.delivery_button.setEnabled(False); root.addWidget(self.review); root.addWidget(self.generate_button); root.addWidget(self.delivery_button)
        self.semaphore=QLabel("PENDENTE — revise os dados antes de gerar"); self.semaphore.setStyleSheet("font-size:18px;font-weight:900;color:#d6b95f"); self.details=QLabel("Nenhum arquivo foi gerado."); self.details.setWordWrap(True); root.addWidget(self.semaphore); root.addWidget(self.details)
        footer=QHBoxLayout(); footer.addStretch(); close=QPushButton("Fechar [Esc]"); close.clicked.connect(self.reject); footer.addWidget(close); root.addLayout(footer)
        self.review.clicked.connect(self._review); self.generate_button.clicked.connect(self._generate); self.delivery_button.clicked.connect(self._open_delivery)
        self._fields=(self.competence,self.cnpj,self.cnpj_confirmed,self.output,self.choose,self.essential,self.complete,self.advanced,self.audit,self.review,self.generate_button,self.delivery_button)
        for field in self._fields: field.installEventFilter(self)
        for field in (self.competence,self.cnpj,self.cnpj_confirmed,self.output):
            signal=getattr(field,"textChanged",None) or getattr(field,"dateChanged",None) or getattr(field,"toggled",None)
            if signal: signal.connect(self._invalidate_review)
        self._escape=QShortcut(QKeySequence("Esc"),self); self._escape.setAutoRepeat(False); self._escape.activated.connect(self.reject)
        self.essential.setChecked(True); self.competence.setFocus(Qt.FocusReason.OtherFocusReason)

    def _profile_button(self,title,description,profile):
        button=QPushButton(f"{title}\n{description}"); button.setObjectName("profile"); button.setCheckable(True); button.setProperty("profile",profile); button.setMinimumHeight(82); button.clicked.connect(lambda _=False,b=button:self._select_profile(b)); return button

    def _select_profile(self,selected):
        for button in (self.essential,self.complete,self.audit): button.setChecked(button is selected)
        self._invalidate_review()

    def _selected_profile(self):
        return next((str(button.property("profile")) for button in (self.essential,self.complete,self.audit) if button.isChecked()),"")

    def _choose_destination(self):
        suggested=f"pacote_contador_{self.competence.date().toString('yyyy_MM')}.zip"
        path,_=QFileDialog.getSaveFileName(self,"Salvar pacote",suggested,"Pacote ZIP (*.zip)")
        if path:self.output.setText(str(Path(path).with_suffix(".zip")))

    def _invalidate_review(self,*_):
        self._plan=None; self._outcome=None; self.generate_button.setEnabled(False); self.delivery_button.setEnabled(False); self.semaphore.setText("PENDENTE — revise os dados antes de gerar"); self.semaphore.setStyleSheet("font-size:18px;font-weight:900;color:#d6b95f")

    def _review(self):
        if self._busy:return
        try:self._plan=self.application.review(cnpj=self.cnpj.text(),competence=self.competence.date().toString("yyyy-MM"),profile=self._selected_profile(),output_path=self.output.text(),cnpj_confirmed=self.cnpj_confirmed.isChecked())
        except Exception as error: QMessageBox.warning(self,"Central do Contador",str(error)); return
        self.generate_button.setEnabled(True); self.semaphore.setText("PENDENTE — revisão concluída; geração ainda não executada"); self.details.setText(f"CNPJ: {self._plan.cnpj} • Competência: {self._plan.competence} • Perfil: {self._plan.profile}\nDestino: {self._plan.output_path}\nRevise: o pacote incluirá todos os movimentos disponíveis e declarará as pendências externas."); self.generate_button.setFocus(Qt.FocusReason.OtherFocusReason)

    def _generate(self):
        if self._busy or self._plan is None:return
        self._busy=True; self._generation+=1; generation=self._generation; self.generate_button.setEnabled(False); self.semaphore.setText("PENDENTE — gerando e validando o pacote…")
        worker=AccountantPackageWorker(generation,self.application,self._plan); worker.signals.completed.connect(self._completed); self._workers.append(worker); self.pool.start(worker)

    def _completed(self,generation,result,error):
        self._workers=[worker for worker in self._workers if worker.generation!=generation]
        if generation!=self._generation:return
        self._busy=False
        if error is not None:
            self._outcome=None; self.delivery_button.setEnabled(False); self.semaphore.setText("DIVERGENTE — pacote não gerado"); self.semaphore.setStyleSheet("font-size:18px;font-weight:900;color:#ef6b73"); self.details.setText(str(error)); self.generate_button.setEnabled(self._plan is not None); return
        self._outcome=result
        color={"CONCILIADO":"#62d394","PENDENTE":"#d6b95f","DIVERGENTE":"#ef6b73"}.get(result.status,"#d6b95f")
        self.semaphore.setText(f"{result.status} — pacote gerado e validado"); self.semaphore.setStyleSheet(f"font-size:18px;font-weight:900;color:{color}"); self.details.setText(f"Arquivo: {result.path}\nPerfil: {result.profile} • Movimentos: {result.movements} • Arquivos: {result.files} • Pendências: {result.pendencies}\nO semáforo não substitui a revisão do contador nem representa apuração tributária.")
        self.delivery_button.setEnabled(self.delivery_application is not None and bool(getattr(result,"package_sha256","")))

    def _open_delivery(self):
        if self._busy or self.delivery_application is None or self._outcome is None:
            return
        from .accountant_delivery_dialog import AccountantDeliveryDialog
        dialog=AccountantDeliveryDialog(self.delivery_application,self._outcome,self,worker_pool=self.pool)
        self._delivery_dialog=dialog
        dialog.exec()

    def eventFilter(self,watched,event):
        if event.type()==QEvent.Type.KeyPress and event.key() in {Qt.Key.Key_Return,Qt.Key.Key_Enter} and watched in self._fields:
            if event.isAutoRepeat():event.accept();return True
            visible=[field for field in self._fields if not field.isHidden() and field.isEnabled()]
            index=visible.index(watched)
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier: visible[max(0,index-1)].setFocus(Qt.FocusReason.BacktabFocusReason)
            elif watched is self.review:self._review()
            elif watched is self.generate_button:self._generate()
            elif watched in (self.essential,self.complete,self.audit):self._select_profile(watched)
            else:visible[min(index+1,len(visible)-1)].setFocus(Qt.FocusReason.TabFocusReason)
            event.accept();return True
        return super().eventFilter(watched,event)

    def closeEvent(self,event):
        self._generation+=1; self._busy=False; super().closeEvent(event)
