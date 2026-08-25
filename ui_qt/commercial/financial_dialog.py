from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, QEvent, QObject, QRunnable, QThreadPool, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDateEdit, QDialog, QFormLayout, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton, QTabWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from commercial.application.action_dto import ActionContext, ActionOrigin
from commercial.application.financial_dto import CreateFinancialTitleCommand, SettleFinancialTitleCommand
from .widgets.money_edit import MoneyEdit


STYLE = """QDialog{background:#0d1117;color:#f0f6fc} QLabel{color:#f0f6fc}
QLineEdit,QDateEdit,QComboBox,QTableWidget{background:#161b22;color:#f0f6fc;border:1px solid #30363d;border-radius:6px}
QLineEdit,QDateEdit,QComboBox{min-height:38px;padding:0 8px} QPushButton{background:#30363d;color:#f0f6fc;border:0;border-radius:6px;min-height:38px;padding:0 13px;font-weight:700}
QPushButton#primary{background:#1f6feb} QHeaderView::section{background:#21262d;color:#f0f6fc;padding:8px;border:0;border-right:1px solid #30363d;font-weight:700}"""


def money(value):
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class _LoadSignals(QObject):
    done = Signal(int, object)
    failed = Signal(int, str)


class _FinancialLoad(QRunnable):
    def __init__(self, generation, query, limit, offsets):
        super().__init__(); self.generation=generation; self.query=query; self.limit=limit; self.offsets=offsets; self.signals=_LoadSignals()
    def run(self):
        try:
            today=date.today()
            result=(
                self.query.receivables_page(limit=self.limit,offset=self.offsets[0]),
                self.query.payables_page(limit=self.limit,offset=self.offsets[1]),
                self.query.financial_summary(today,today),
            )
            self.signals.done.emit(self.generation,result)
        except Exception as error:
            self.signals.failed.emit(self.generation,str(error))


class TitleEditorDialog(QDialog):
    def __init__(self, kind, submit, parent=None):
        super().__init__(parent); self.kind=kind; self.submit=submit; self.completed=False
        self.setWindowTitle("Nova conta a receber" if kind=="RECEBER" else "Nova conta a pagar")
        self.setMinimumWidth(520); self.setStyleSheet(STYLE); layout=QVBoxLayout(self); form=QFormLayout()
        self.party=QLineEdit(); self.document=QLineEdit(); self.description=QLineEdit(); self.notes=QLineEdit()
        self.amount=MoneyEdit(); self.due=QDateEdit(QDate.currentDate()); self.due.setCalendarPopup(True); self.due.setDisplayFormat("dd/MM/yyyy")
        for label,widget in (("Pessoa",self.party),("Documento",self.document),("Descrição",self.description),("Valor",self.amount),("Vencimento",self.due),("Observações",self.notes)): form.addRow(label,widget)
        layout.addLayout(form); row=QHBoxLayout(); row.addStretch(); cancel=QPushButton("Cancelar [Esc]"); self.confirm=QPushButton("Revisar e confirmar"); self.confirm.setObjectName("primary"); row.addWidget(cancel); row.addWidget(self.confirm); layout.addLayout(row)
        cancel.clicked.connect(self.reject); self.confirm.clicked.connect(self._confirm)
        self._fields=(self.party,self.document,self.description,self.amount,self.due,self.notes,self.confirm)
        for field in self._fields: field.installEventFilter(self)
        self.party.setFocus()

    def eventFilter(self,watched,event):
        if event.type()==QEvent.Type.KeyPress and event.key() in {Qt.Key.Key_Return,Qt.Key.Key_Enter}:
            if event.isAutoRepeat(): event.accept(); return True
            index=self._fields.index(watched)
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier: self._fields[max(0,index-1)].setFocus()
            elif watched is self.confirm: self._confirm()
            else: self._fields[index+1].setFocus()
            event.accept(); return True
        return super().eventFilter(watched,event)

    def _confirm(self):
        command=CreateFinancialTitleCommand(self.amount.value(),date(self.due.date().year(),self.due.date().month(),self.due.date().day()),party_name=self.party.text(),document=self.document.text(),description=self.description.text(),notes=self.notes.text())
        answer=QMessageBox.question(self,"Confirmar",f"Criar {self.kind.lower()} de {money(command.amount)} com vencimento em {command.due_date:%d/%m/%Y}?")
        if answer!=QMessageBox.StandardButton.Yes: return
        result=self.submit(command)
        if not result.committed: QMessageBox.warning(self,"Financeiro",result.message); return
        self.completed=True; self.accept()


class SettlementDialog(QDialog):
    def __init__(self,title,kind,submit,parent=None):
        super().__init__(parent); self.title=title; self.kind=kind; self.submit=submit
        self.setWindowTitle("Baixar título"); self.setMinimumWidth(480); self.setStyleSheet(STYLE); layout=QVBoxLayout(self); form=QFormLayout()
        self.amount=MoneyEdit(); self.amount.set_value(title.open_amount); self.method=QComboBox(); self.method.addItems(["DINHEIRO","PIX","CARTÃO","TRANSFERÊNCIA","OUTRO"]); self.payment_date=QDateEdit(QDate.currentDate()); self.payment_date.setCalendarPopup(True); self.notes=QLineEdit()
        for label,widget in (("Valor",self.amount),("Forma",self.method),("Data",self.payment_date),("Observação",self.notes)): form.addRow(label,widget)
        layout.addLayout(form); self.confirm=QPushButton("Confirmar baixa"); self.confirm.setObjectName("primary"); layout.addWidget(self.confirm); self.confirm.clicked.connect(self._confirm)
        QShortcut(QKeySequence("Esc"),self,activated=self.reject).setAutoRepeat(False)

    def _confirm(self):
        qdate=self.payment_date.date(); command=SettleFinancialTitleCommand(self.title.title_id,self.amount.value(),self.method.currentText(),date(qdate.year(),qdate.month(),qdate.day()),self.notes.text())
        if QMessageBox.question(self,"Confirmar",f"Registrar baixa de {money(command.amount)}?")!=QMessageBox.StandardButton.Yes:return
        result=self.submit(command)
        if not result.committed: QMessageBox.warning(self,"Financeiro",result.message); return
        self.accept()


class FinancialDialog(QDialog):
    def __init__(self,query,actions,*,user,parent=None,page_size=100,thread_pool=None):
        super().__init__(parent); self.query=query; self.actions=actions; self.context=ActionContext(user,ActionOrigin.UI)
        self.page_size=min(max(int(page_size),25),500); self._offsets=[0,0]; self._generation=0; self._pool=thread_pool or QThreadPool.globalInstance(); self.receivables=(); self.payables=()
        self.setWindowTitle("Financeiro"); self.resize(1150,720); self.setMinimumSize(880,580); self.setStyleSheet(STYLE)
        layout=QVBoxLayout(self); title=QLabel("FINANCEIRO"); title.setStyleSheet("font-size:24px;font-weight:800;color:#00d084"); layout.addWidget(title)
        self.summary=QLabel(); self.summary.setStyleSheet("background:#161b22;padding:12px;font-size:14px;font-weight:700"); layout.addWidget(self.summary)
        self.load_state=QLabel("Carregando…"); layout.addWidget(self.load_state)
        self.tabs=QTabWidget(); layout.addWidget(self.tabs,1); self.receivable_table=self._table(); self.payable_table=self._table()
        for name,table in (("Contas a receber",self.receivable_table),("Contas a pagar",self.payable_table)):
            page=QWidget(); box=QVBoxLayout(page); box.addWidget(table); nav=QHBoxLayout(); previous=QPushButton("Página anterior [PgUp]"); following=QPushButton("Próxima página [PgDown]"); label=QLabel(); nav.addWidget(previous); nav.addWidget(label); nav.addWidget(following); nav.addStretch(); box.addLayout(nav); self.tabs.addTab(page,name)
            index=self.tabs.count()-1; previous.clicked.connect(lambda _=False,i=index:self.change_page(i,-1)); following.clicked.connect(lambda _=False,i=index:self.change_page(i,1));
            if not hasattr(self,"_page_labels"): self._page_labels=[]; self._previous=[]; self._following=[]
            self._page_labels.append(label); self._previous.append(previous); self._following.append(following)
        row=QHBoxLayout(); self.new_button=QPushButton("Novo título [F3]"); self.settle_button=QPushButton("Baixar selecionado [Enter]"); refresh=QPushButton("Atualizar [F5]"); close=QPushButton("Fechar [Esc]"); self.new_button.setObjectName("primary")
        self.new_button.clicked.connect(self.new_title); self.settle_button.clicked.connect(self.settle); refresh.clicked.connect(self.reload); close.clicked.connect(self.reject)
        for b in (self.new_button,self.settle_button,refresh):row.addWidget(b)
        row.addStretch(); row.addWidget(close); layout.addLayout(row)
        self._shortcuts=[]
        for key,callback in (("F3",self.new_title),("F5",self.reload),("PgUp",lambda:self.change_page(self.tabs.currentIndex(),-1)),("PgDown",lambda:self.change_page(self.tabs.currentIndex(),1)),("Esc",self.reject)):
            shortcut=QShortcut(QKeySequence(key),self); shortcut.setAutoRepeat(False); shortcut.activated.connect(callback); self._shortcuts.append(shortcut)
        for table in (self.receivable_table,self.payable_table):table.installEventFilter(self)
        self.reload()

    @staticmethod
    def _table():
        table=QTableWidget(0,7); table.setHorizontalHeaderLabels(["ID","Pessoa","Documento","Descrição","Vencimento","Em aberto","Situação"]); table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection); table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); table.verticalHeader().setVisible(False); table.horizontalHeader().setSectionResizeMode(3,QHeaderView.ResizeMode.Stretch); return table

    def eventFilter(self,watched,event):
        if watched in (self.receivable_table,self.payable_table) and event.type()==QEvent.Type.KeyPress and event.key() in {Qt.Key.Key_Return,Qt.Key.Key_Enter}:
            if not event.isAutoRepeat(): self.settle()
            event.accept(); return True
        return super().eventFilter(watched,event)

    def reload(self):
        self._generation+=1; generation=self._generation; self.load_state.setText("Carregando…"); self.settle_button.setEnabled(False)
        worker=_FinancialLoad(generation,self.query,self.page_size,tuple(self._offsets)); worker.signals.done.connect(self._loaded); worker.signals.failed.connect(self._failed); self._pool.start(worker)

    def _loaded(self,generation,result):
        if generation!=self._generation:return
        receivable_page,payable_page,summary=result; self.receivables=tuple(receivable_page.items); self.payables=tuple(payable_page.items); self._fill(self.receivable_table,self.receivables); self._fill(self.payable_table,self.payables)
        self.summary.setText(f"A RECEBER: {money(summary.receivable_open)}  •  VENCIDO: {money(summary.receivable_overdue)}  •  A PAGAR: {money(summary.payable_open)}  •  VENCE HOJE: {money(summary.payable_due_today)}")
        for index,page in enumerate((receivable_page,payable_page)):
            current=(page.offset//page.limit)+1; pages=max(1,(page.total_records+page.limit-1)//page.limit); self._page_labels[index].setText(f"Página {current} de {pages} — {page.total_records} registros"); self._previous[index].setEnabled(page.offset>0); self._following[index].setEnabled(page.offset+page.limit<page.total_records)
        self.load_state.setText("Sem resultados." if not self.receivables and not self.payables else "Dados atualizados."); self.settle_button.setEnabled(True)

    def _failed(self,generation,message):
        if generation!=self._generation:return
        self.load_state.setText(f"Não foi possível carregar: {message}"); self.settle_button.setEnabled(False)

    def change_page(self,index,direction):
        if direction<0:self._offsets[index]=max(0,self._offsets[index]-self.page_size)
        else:self._offsets[index]+=self.page_size
        self.reload()

    def closeEvent(self,event):
        self._generation+=1; super().closeEvent(event)

    @staticmethod
    def _fill(table,rows):
        table.setRowCount(0)
        for item in rows:
            row=table.rowCount(); table.insertRow(row); party=getattr(item,"customer_name",getattr(item,"beneficiary_name","")); values=(item.title_id,party,item.document,item.description,item.due_date.strftime("%d/%m/%Y"),money(item.open_amount),item.status)
            for col,value in enumerate(values):
                cell=QTableWidgetItem(str(value));
                if col==0:cell.setData(Qt.ItemDataRole.UserRole,item.title_id)
                table.setItem(row,col,cell)
        if table.rowCount():table.selectRow(0)

    def _kind(self): return "RECEBER" if self.tabs.currentIndex()==0 else "PAGAR"
    def _rows(self): return self.receivables if self._kind()=="RECEBER" else self.payables
    def _selected(self):
        table=self.receivable_table if self._kind()=="RECEBER" else self.payable_table; row=table.currentRow(); return self._rows()[row] if 0<=row<len(self._rows()) else None

    def new_title(self):
        kind=self._kind(); method=self.actions.create_receivable if kind=="RECEBER" else self.actions.create_payable
        dialog=TitleEditorDialog(kind,lambda command:method(command,context=self.context,confirmed=True),self)
        if dialog.exec()==QDialog.DialogCode.Accepted:self.reload()

    def settle(self):
        title=self._selected()
        if title is None: QMessageBox.information(self,"Financeiro","Selecione um título."); return
        kind=self._kind(); method=self.actions.settle_receivable if kind=="RECEBER" else self.actions.settle_payable
        dialog=SettlementDialog(title,kind,lambda command:method(command,context=self.context,confirmed=True),self)
        if dialog.exec()==QDialog.DialogCode.Accepted:self.reload()
