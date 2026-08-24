import os
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from PySide6.QtCore import QEvent,Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication,QMessageBox
from ui_qt.commercial.purchase_dialog import PurchaseDialog,NewOrderDialog,ReceiveOrderDialog,SupplierDialog

class App:
    def __init__(self):self.created=[];self.received=[];self.suppliers=[]
    def list_orders(self,status,limit=200):return (SimpleNamespace(order_id=7,status="ABERTO",supplier_name="NABI",created_at="2026",total=Decimal("20"),pending_quantity=Decimal("2"),user="maria"),)
    def list_suppliers(self):return (SimpleNamespace(supplier_id=3,name="NABI"),)
    def list_products(self):return (SimpleNamespace(product_id=5,code="P5",description="MESA"),)
    def create_order(self,supplier,items,notes=""):self.created.append((supplier,items,notes));return 7
    def create_supplier(self,name,legal_name="",document=""):self.suppliers.append((name,legal_name,document));return 3
    def get_order(self,oid):return {"id":oid,"status":"ABERTO","fornecedor_nome":"NABI","itens":[{"id":11,"codigo":"P5","nome":"MESA","quantidade_pendente":Decimal("2"),"custo_unitario":Decimal("10")}]}
    def receive_order(self,oid,items,**kwargs):self.received.append((oid,items,kwargs));return object()

def setup_module():
    global QT;QT=QApplication.instance() or QApplication([])

def test_lista_preserva_id_e_colunas_legacy():
    d=PurchaseDialog(App());assert d.selected_id()==7;assert d.table.horizontalHeaderItem(2).text()=="Fornecedor";d.close()

def test_auto_repeat_na_tabela_nao_abre_detalhes():
    d=PurchaseDialog(App());e=QKeyEvent(QEvent.Type.KeyPress,Qt.Key.Key_Return,Qt.KeyboardModifier.NoModifier,"",True,1)
    with patch.object(d,"details") as details:assert d.eventFilter(d.table,e) is True
    details.assert_not_called();d.close()

def test_novo_pedido_transporta_ids_reais_e_decimal():
    app=App();d=NewOrderDialog(app);d.quantity.setText("2,5");d.cost.setText("10,00");d.add_item();d.save_order()
    supplier,items,_=app.created[0];assert supplier==3;assert items[0]["produto_id"]==5;assert items[0]["quantidade"]==Decimal("2.5");d.close()

def test_enter_auto_repeat_no_adicionar_nao_duplica_item():
    app=App();d=NewOrderDialog(app);e=QKeyEvent(QEvent.Type.KeyPress,Qt.Key.Key_Return,Qt.KeyboardModifier.NoModifier,"",True,1)
    assert d.eventFilter(d.add,e) is True;assert d.items==[];d.close()

def test_enter_simples_no_adicionar_inclui_exatamente_um():
    app=App();d=NewOrderDialog(app);e=QKeyEvent(QEvent.Type.KeyPress,Qt.Key.Key_Return,Qt.KeyboardModifier.NoModifier,"",False,1)
    assert d.eventFilter(d.add,e) is True;assert len(d.items)==1;d.close()

def test_recebimento_revisa_e_chama_fachada_uma_vez():
    app=App();order=app.get_order(7);d=ReceiveOrderDialog(app,order)
    with patch.object(QMessageBox,"question",return_value=QMessageBox.StandardButton.Yes):d.receive()
    assert len(app.received)==1;assert app.received[0][0]==7;assert app.received[0][1][0]["pedido_item_id"]==11;d.close()

def test_cancelar_revisao_nao_recebe():
    app=App();d=ReceiveOrderDialog(app,app.get_order(7))
    with patch.object(QMessageBox,"question",return_value=QMessageBox.StandardButton.No):d.receive()
    assert app.received==[];d.close()

def test_auto_repeat_na_confirmacao_nao_recebe():
    app=App();d=ReceiveOrderDialog(app,app.get_order(7));e=QKeyEvent(QEvent.Type.KeyPress,Qt.Key.Key_Return,Qt.KeyboardModifier.NoModifier,"",True,1)
    assert d.eventFilter(d.confirm,e) is True;assert app.received==[];d.close()

def test_fornecedor_valida_e_salva_pela_fachada():
    app=App();d=SupplierDialog(app);d.name.setText("Fornecedor A");d._save();assert app.suppliers[0][0]=="Fornecedor A";d.close()
