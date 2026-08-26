from __future__ import annotations

from decimal import Decimal, InvalidOperation

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDateEdit, QDialog, QFormLayout,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)


STYLE="""QDialog{background:#0d1117;color:#f0f6fc;font-size:14px} QLabel{color:#f0f6fc} QLineEdit,QComboBox,QDateEdit,QTableWidget{background:#161b22;color:#f0f6fc;border:1px solid #30363d;border-radius:6px;min-height:38px} QPushButton{background:#30363d;color:#f0f6fc;border:0;border-radius:6px;min-height:40px;padding:0 13px;font-weight:800} QPushButton#primary{background:#238636} QHeaderView::section{background:#21262d;color:#f0f6fc;padding:9px;border:0;border-right:1px solid #30363d;font-weight:800}"""


def _decimal(text, field):
    try: return Decimal(str(text or "0").strip().replace(".","").replace(",","."))
    except InvalidOperation as error: raise ValueError(f"{field} inválido.") from error


def _money(value): return f"R$ {Decimal(str(value)):,.2f}".replace(",","X").replace(".",",").replace("X",".")


class SupplierDialog(QDialog):
    def __init__(self, app, parent=None):
        super().__init__(parent); self.app=app; self.saved=False; self.setWindowTitle("Novo fornecedor"); self.setMinimumWidth(520); self.setStyleSheet(STYLE)
        root=QVBoxLayout(self); form=QFormLayout(); self.name=QLineEdit(); self.legal=QLineEdit(); self.document=QLineEdit()
        for label,field in (("Nome fantasia*",self.name),("Razão social",self.legal),("CNPJ/Documento",self.document)): form.addRow(label,field)
        root.addLayout(form); self.save=QPushButton("Salvar fornecedor  [Enter]"); self.save.setObjectName("primary"); root.addWidget(self.save); self.save.clicked.connect(self._save)
        self.fields=(self.name,self.legal,self.document,self.save)
        for field in self.fields: field.installEventFilter(self)
        QShortcut(QKeySequence("Esc"),self,activated=self.reject).setAutoRepeat(False); self.name.setFocus()
    def eventFilter(self,w,e):
        if e.type()==QEvent.Type.KeyPress and e.key() in {Qt.Key.Key_Return,Qt.Key.Key_Enter}:
            e.accept()
            if e.isAutoRepeat(): return True
            i=self.fields.index(w)
            if e.modifiers()&Qt.KeyboardModifier.ShiftModifier:self.fields[max(0,i-1)].setFocus()
            elif w is self.save:self._save()
            else:self.fields[i+1].setFocus()
            return True
        return super().eventFilter(w,e)
    def _save(self):
        try:self.app.create_supplier(self.name.text(),legal_name=self.legal.text(),document=self.document.text())
        except Exception as error: QMessageBox.warning(self,"Fornecedores",str(error));self.name.setFocus();return
        self.saved=True;self.accept()


class NewOrderDialog(QDialog):
    def __init__(self,app,parent=None):
        super().__init__(parent);self.app=app;self.items=[];self.setWindowTitle("Novo pedido de compra");self.resize(900,650);self.setStyleSheet(STYLE);root=QVBoxLayout(self)
        self.suppliers=app.list_suppliers();self.products=app.list_products();form=QFormLayout();self.supplier=QComboBox();self.product=QComboBox()
        for item in self.suppliers:self.supplier.addItem(f"{item.supplier_id} - {item.name}",item.supplier_id)
        for item in self.products:self.product.addItem(f"{item.code} - {item.description}",item.product_id)
        self.quantity=QLineEdit("1");self.cost=QLineEdit("0,00");self.notes=QLineEdit();form.addRow("Fornecedor",self.supplier);form.addRow("Produto",self.product);form.addRow("Quantidade",self.quantity);form.addRow("Custo unitário",self.cost);root.addLayout(form)
        self.add=QPushButton("Adicionar item  [Enter]");self.add.clicked.connect(self.add_item);root.addWidget(self.add);self.table=QTableWidget(0,4);self.table.setHorizontalHeaderLabels(("Produto","Quantidade","Custo","Total"));self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch);root.addWidget(self.table,1);root.addWidget(QLabel("Observação"));root.addWidget(self.notes)
        self.save=QPushButton("Salvar pedido");self.save.setObjectName("primary");self.save.clicked.connect(self.save_order);root.addWidget(self.save);QShortcut(QKeySequence("Esc"),self,activated=self.reject).setAutoRepeat(False)
        self.fields=(self.supplier,self.product,self.quantity,self.cost,self.add,self.notes,self.save)
        for field in self.fields:field.installEventFilter(self)
    def eventFilter(self,w,e):
        if w in self.fields and e.type()==QEvent.Type.KeyPress and e.key() in {Qt.Key.Key_Return,Qt.Key.Key_Enter}:
            e.accept()
            if e.isAutoRepeat():return True
            i=self.fields.index(w)
            if e.modifiers()&Qt.KeyboardModifier.ShiftModifier:self.fields[max(0,i-1)].setFocus()
            elif w is self.add:self.add_item()
            elif w is self.save:self.save_order()
            else:self.fields[min(i+1,len(self.fields)-1)].setFocus()
            return True
        return super().eventFilter(w,e)
    def add_item(self):
        try:
            product_id=int(self.product.currentData());q=_decimal(self.quantity.text(),"Quantidade");cost=_decimal(self.cost.text(),"Custo")
            if q<=0 or cost<0:raise ValueError("Quantidade deve ser positiva e custo não pode ser negativo.")
        except Exception as error:QMessageBox.warning(self,"Compras",str(error));self.quantity.setFocus();return
        self.items.append({"produto_id":product_id,"quantidade":q,"custo_unitario":cost});row=self.table.rowCount();self.table.insertRow(row)
        for c,v in enumerate((self.product.currentText(),str(q),_money(cost),_money(q*cost))):self.table.setItem(row,c,QTableWidgetItem(v))
        self.quantity.setFocus()
    def save_order(self):
        try:
            if not self.items:raise ValueError("Adicione ao menos um item.")
            self.app.create_order(int(self.supplier.currentData()),tuple(self.items),notes=self.notes.text())
        except Exception as error:QMessageBox.warning(self,"Compras",str(error));return
        self.accept()


class ReceiveOrderDialog(QDialog):
    def __init__(self,app,order,parent=None):
        super().__init__(parent);self.app=app;self.order=order;self.setWindowTitle("Receber pedido");self.resize(850,620);self.setStyleSheet(STYLE);root=QVBoxLayout(self)
        root.addWidget(QLabel(f"PEDIDO #{order['id']} — {order.get('fornecedor_nome','')}"));self.table=QTableWidget(0,4);self.table.setHorizontalHeaderLabels(("Produto","Pendente","Receber","Custo"));self.pending=[]
        for item in order["itens"]:
            if Decimal(str(item["quantidade_pendente"]))<=0:continue
            row=self.table.rowCount();self.table.insertRow(row);q=QLineEdit(str(item["quantidade_pendente"]));cost=QLineEdit(str(item["custo_unitario"]));self.pending.append((item,q,cost));self.table.setItem(row,0,QTableWidgetItem(f"{item['codigo']} - {item['nome']}"));self.table.setItem(row,1,QTableWidgetItem(str(item["quantidade_pendente"])));self.table.setCellWidget(row,2,q);self.table.setCellWidget(row,3,cost)
        root.addWidget(self.table,1);form=QFormLayout();self.document=QLineEdit();self.notes=QLineEdit();self.payable=QCheckBox("Gerar conta a pagar");self.due=QDateEdit();self.due.setCalendarPopup(True);self.due.setDisplayFormat("dd/MM/yyyy");form.addRow("Documento/NF",self.document);form.addRow("Observação",self.notes);form.addRow("",self.payable);form.addRow("Vencimento",self.due);root.addLayout(form);self.confirm=QPushButton("Revisar e confirmar recebimento");self.confirm.setObjectName("primary");self.confirm.clicked.connect(self.receive);root.addWidget(self.confirm);QShortcut(QKeySequence("Esc"),self,activated=self.reject).setAutoRepeat(False)
        self.fields=tuple(field for _item,q,cost in self.pending for field in (q,cost))+(self.document,self.notes,self.payable,self.due,self.confirm)
        for field in self.fields:field.installEventFilter(self)
    def eventFilter(self,w,e):
        if w in self.fields and e.type()==QEvent.Type.KeyPress and e.key() in {Qt.Key.Key_Return,Qt.Key.Key_Enter}:
            e.accept()
            if e.isAutoRepeat():return True
            i=self.fields.index(w)
            if e.modifiers()&Qt.KeyboardModifier.ShiftModifier:self.fields[max(0,i-1)].setFocus()
            elif w is self.confirm:self.receive()
            else:self.fields[min(i+1,len(self.fields)-1)].setFocus()
            return True
        return super().eventFilter(w,e)
    def receive(self):
        try:
            items=[]
            for item,q,cost in self.pending:
                amount=_decimal(q.text(),"Quantidade");unit=_decimal(cost.text(),"Custo")
                if amount>0:items.append({"pedido_item_id":item["id"],"quantidade":amount,"custo_unitario":unit})
            if not items:raise ValueError("Informe ao menos um item para recebimento.")
        except Exception as error:QMessageBox.warning(self,"Compras",str(error));return
        if QMessageBox.question(self,"Confirmar recebimento",f"Receber {len(items)} item(ns) do pedido #{self.order['id']}?",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
        qdate=self.due.date();due=f"{qdate.year():04d}-{qdate.month():02d}-{qdate.day():02d}" if self.payable.isChecked() else None
        try:self.app.receive_order(self.order["id"],tuple(items),document=self.document.text(),notes=self.notes.text(),create_payable=self.payable.isChecked(),due_date=due)
        except Exception as error:QMessageBox.warning(self,"Compras",str(error));return
        self.accept()


class PurchaseDialog(QDialog):
    def __init__(self,app,parent=None):
        super().__init__(parent);self.app=app;self.setWindowTitle("Compras");self.resize(1150,720);self.setStyleSheet(STYLE);root=QVBoxLayout(self);title=QLabel("COMPRAS");title.setStyleSheet("font-size:25px;font-weight:900");root.addWidget(title)
        row=QHBoxLayout();self.status=QComboBox();self.status.addItems(("TODOS","ABERTO","PARCIAL","RECEBIDO"));refresh=QPushButton("Atualizar [F5]");refresh.clicked.connect(self.reload);row.addWidget(QLabel("Status"));row.addWidget(self.status);row.addWidget(refresh);row.addStretch();root.addLayout(row)
        self.table=QTableWidget(0,7);self.table.setHorizontalHeaderLabels(("ID","Status","Fornecedor","Criado em","Valor","Qtd. pendente","Usuário"));self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);self.table.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.Stretch);self.table.installEventFilter(self);root.addWidget(self.table,1)
        buttons=QHBoxLayout();new=QPushButton("Novo pedido [F3]");supplier=QPushButton("Fornecedores [F4]");receive=QPushButton("Receber [F8]");details=QPushButton("Detalhes [Enter]");close=QPushButton("Fechar [Esc]");new.clicked.connect(self.new_order);supplier.clicked.connect(self.new_supplier);receive.clicked.connect(self.receive);details.clicked.connect(self.details);close.clicked.connect(self.reject)
        for b in (new,supplier,receive,details):buttons.addWidget(b)
        buttons.addStretch();buttons.addWidget(close);root.addLayout(buttons)
        self._shortcuts=[]
        for key,cb in (("F3",self.new_order),("F4",self.new_supplier),("F5",self.reload),("F8",self.receive),("Esc",self.reject)):
            s=QShortcut(QKeySequence(key),self);s.setAutoRepeat(False);s.activated.connect(cb);self._shortcuts.append(s)
        self.reload()
    def eventFilter(self,w,e):
        if w is self.table and e.type()==QEvent.Type.KeyPress and e.key() in {Qt.Key.Key_Return,Qt.Key.Key_Enter}:
            e.accept()
            if not e.isAutoRepeat() and not e.modifiers()&Qt.KeyboardModifier.ShiftModifier:self.details()
            return True
        return super().eventFilter(w,e)
    def selected_id(self):
        r=self.table.currentRow();return self.table.item(r,0).data(Qt.ItemDataRole.UserRole) if r>=0 and self.table.item(r,0) else None
    def reload(self):
        try:orders=self.app.list_orders(self.status.currentText(),limit=200)
        except Exception as error:QMessageBox.warning(self,"Compras",str(error));return
        self.table.setRowCount(0)
        for order in orders:
            r=self.table.rowCount();self.table.insertRow(r);vals=(order.order_id,order.status,order.supplier_name,order.created_at,_money(order.total),str(order.pending_quantity),order.user)
            for c,v in enumerate(vals):item=QTableWidgetItem(str(v));item.setData(Qt.ItemDataRole.UserRole,order.order_id) if c==0 else None;self.table.setItem(r,c,item)
        if self.table.rowCount():self.table.selectRow(0)
    def new_supplier(self):
        if SupplierDialog(self.app,self).exec()==QDialog.DialogCode.Accepted:self.reload()
    def new_order(self):
        try:dialog=NewOrderDialog(self.app,self)
        except Exception as error:QMessageBox.warning(self,"Compras",str(error));return
        if dialog.exec()==QDialog.DialogCode.Accepted:self.reload()
    def receive(self):
        oid=self.selected_id()
        if oid is None:return
        try:order=self.app.get_order(oid)
        except Exception as error:QMessageBox.warning(self,"Compras",str(error));return
        if ReceiveOrderDialog(self.app,order,self).exec()==QDialog.DialogCode.Accepted:self.reload()
    def details(self):
        oid=self.selected_id()
        if oid is None:return
        try:order=self.app.get_order(oid)
        except Exception as error:QMessageBox.warning(self,"Compras",str(error));return
        lines=[f"Pedido #{order['id']} | {order['status']}",f"Fornecedor: {order.get('fornecedor_nome','')}"]+[f"{i['codigo']} - {i['nome']} | pendente {i['quantidade_pendente']} | custo {_money(i['custo_unitario'])}" for i in order['itens']]
        QMessageBox.information(self,"Detalhes da compra","\n".join(lines))
