from __future__ import annotations

import csv
import json
import sqlite3
from decimal import Decimal

import pytest

from services.accounting_reconciliation_service import AccountingReconciliationService


SCHEMA = """
CREATE TABLE configuracoes(chave TEXT PRIMARY KEY, valor TEXT);
CREATE TABLE movimentacoes(id INTEGER PRIMARY KEY, tipo TEXT, valor REAL, valor_decimal TEXT,
 data TEXT, status_pagamento TEXT, valor_aberto REAL, valor_aberto_decimal TEXT, forma_pagamento TEXT);
CREATE TABLE parcelas(id INTEGER PRIMARY KEY, movimentacao_id INTEGER, valor_parcela REAL,
 valor_parcela_decimal TEXT, status TEXT, valor_pago REAL, data_pagamento TEXT);
CREATE TABLE titulos_financeiros(id INTEGER PRIMARY KEY, tipo TEXT, origem TEXT, origem_id TEXT,
 data_emissao TEXT, criado_em TEXT, valor_original REAL, valor_original_decimal TEXT,
 valor_pago REAL, status TEXT);
CREATE TABLE pagamentos_titulos(id INTEGER PRIMARY KEY, titulo_id INTEGER, valor REAL,
 valor_decimal TEXT, data_pagamento TEXT);
CREATE TABLE fiscal_sale_documents(id INTEGER PRIMARY KEY, sale_id INTEGER, access_key TEXT,
 status TEXT, created_at TEXT);
CREATE TABLE pedidos_compra(id INTEGER PRIMARY KEY, status TEXT, criado_em TEXT);
CREATE TABLE recebimentos_compra(id INTEGER PRIMARY KEY, pedido_id INTEGER, data_recebimento TEXT);
CREATE TABLE recebimento_compra_itens(id INTEGER PRIMARY KEY, recebimento_id INTEGER,
 pedido_item_id INTEGER, produto_id INTEGER, valor_total REAL);
CREATE TABLE estoque_movimentacoes(id INTEGER PRIMARY KEY, produto_id INTEGER, origem TEXT,
 origem_id TEXT, tipo TEXT, data TEXT);
CREATE TABLE nfe_importacoes(id INTEGER PRIMARY KEY, chave TEXT, valor_total TEXT, data_importacao TEXT);
"""


@pytest.fixture
def reconciliation(tmp_path):
    database = tmp_path / "reconciliation.db"
    connection = sqlite3.connect(database)
    connection.executescript(SCHEMA)
    connection.execute("INSERT INTO movimentacoes VALUES(1,'COMPRA',100,'100.00','12/08/2026 10:00','PENDENTE',40,'40.00','PIX R$ 60.00 + CREDIARIO R$ 40.00')")
    connection.execute("INSERT INTO parcelas VALUES(1,1,40,'40.00','PENDENTE',0,'')")
    connection.execute("INSERT INTO titulos_financeiros VALUES(1,'RECEBER','VENDA','1','2026-08-12','2026-08-12',40,'40.00',0,'ABERTO')")
    connection.execute("INSERT INTO fiscal_sale_documents VALUES(1,1,?,'AUTORIZADO','2026-08-12')", ("1" * 44,))
    connection.execute("INSERT INTO configuracoes VALUES(?,?)", (
        "pdv_pagamentos_venda_1",
        json.dumps({"total": "100.00", "recebido": "100.00", "troco": "0.00", "pagamentos": [
            {"forma": "PIX", "valor": "60.00"}, {"forma": "CREDIARIO", "valor": "40.00"},
        ]}),
    ))
    connection.execute("INSERT INTO movimentacoes VALUES(2,'VENDA',25,'25.00','2026-08-13','PAGO',0,'0.00','DINHEIRO R$ 25.00')")
    connection.execute("INSERT INTO fiscal_sale_documents VALUES(2,999,?,'AUTORIZADO','2026-08-13')", ("2" * 44,))
    connection.execute("INSERT INTO pedidos_compra VALUES(10,'PARCIAL','2026-08-10')")
    connection.execute("INSERT INTO recebimentos_compra VALUES(20,10,'2026-08-14')")
    connection.execute("INSERT INTO recebimento_compra_itens VALUES(1,20,100,5,30)")
    connection.execute("INSERT INTO estoque_movimentacoes VALUES(1,5,'COMPRA','10:100:0','ENTRADA','2026-08-14')")
    connection.execute("INSERT INTO titulos_financeiros VALUES(2,'PAGAR','RECEBIMENTO_COMPRA','20','2026-08-14','2026-08-14',30,'30.00',0,'ABERTO')")
    connection.execute("INSERT INTO pagamentos_titulos VALUES(1,2,10,'10.00','2026-08-20')")
    connection.execute("INSERT INTO pagamentos_titulos VALUES(2,999,5,'5.00','2026-08-20')")
    connection.execute("INSERT INTO nfe_importacoes VALUES(1,?,'30.00','2026-08-14')", ("3" * 44,))
    connection.execute("INSERT INTO titulos_financeiros VALUES(3,'RECEBER','VENDA','','2026-08-15','2026-08-15',10,'10.00',0,'ABERTO')")
    connection.commit()
    connection.close()

    def connect():
        return sqlite3.connect(database)

    return database, AccountingReconciliationService(connect)


def _row(result, relation, source):
    return next(row for row in result.entries if row.relation == relation and row.source_id == str(source))


def test_reconcilia_fontes_reais_sem_mutar_banco(reconciliation):
    database, service = reconciliation
    before = database.read_bytes()
    result = service.reconcile(start_date="2026-08-01", end_date="2026-08-31")
    after = database.read_bytes()
    assert before == after
    assert _row(result, "VENDA_FISCAL", 1).classification == "CONCILIADO"
    assert _row(result, "VENDA_PAGAMENTOS", 1).classification == "CONCILIADO"
    assert _row(result, "VENDA_TITULO_PARCELAS", 1).classification == "CONCILIADO"
    assert _row(result, "VENDA_FISCAL", 2).classification == "PENDENTE_DADO_EXTERNO"
    assert _row(result, "VENDA_PAGAMENTOS", 2).classification == "LEGADO_NAO_PROVAVEL"
    assert _row(result, "DOCUMENTO_FISCAL_VENDA", 2).classification == "DIVERGENTE"
    assert _row(result, "COMPRA_RECEBIMENTO_ESTOQUE", 10).classification == "CONCILIADO"
    assert _row(result, "PEDIDO_RECEBIMENTO", 10).classification == "CONCILIADO"
    assert _row(result, "RECEBIMENTO_COMPRA_TITULO", 20).classification == "CONCILIADO"
    assert _row(result, "PAGAMENTO_TITULO", 2).classification == "DIVERGENTE"
    assert _row(result, "DFE_COMPRA", 1).classification == "LEGADO_NAO_PROVAVEL"
    assert _row(result, "TITULO_ORIGEM", 3).classification == "DIVERGENTE"


def test_competencia_e_caixa_ficam_separados_e_limitacoes_explicitas(reconciliation):
    _, service = reconciliation
    result = service.reconcile(start_date="01/08/2026", end_date="31/08/2026")
    sale = _row(result, "VENDA_PAGAMENTOS", 1)
    assert sale.competence_amount == Decimal("100.00")
    assert sale.cash_amount == Decimal("100.00")
    inferred = _row(result, "VENDA_CAIXA_INFERIDO", 1)
    assert inferred.classification == "PENDENTE_DADO_EXTERNO"
    assert any("cash_session_id" in text for text in result.limitations)
    assert any("JSON" in text for text in result.limitations)
    assert any("itens canônicos" in text for text in result.limitations)


def test_pagamento_json_invalido_e_duplicidade_de_titulo_sao_divergentes(reconciliation):
    database, service = reconciliation
    connection = sqlite3.connect(database)
    connection.execute("UPDATE configuracoes SET valor='nao-json' WHERE chave='pdv_pagamentos_venda_1'")
    connection.execute("INSERT INTO titulos_financeiros VALUES(4,'RECEBER','VENDA','1','2026-08-12','2026-08-12',40,'40.00',0,'ABERTO')")
    connection.commit(); connection.close()
    result = service.reconcile(start_date="2026-08-01", end_date="2026-08-31")
    assert _row(result, "VENDA_PAGAMENTOS", 1).classification == "DIVERGENTE"
    assert _row(result, "VENDA_TITULO_PARCELAS", 1).classification == "DIVERGENTE"


def test_cancelamento_exige_estorno_e_estado_fiscal_coerente(reconciliation):
    database, service = reconciliation
    connection = sqlite3.connect(database)
    connection.execute("INSERT INTO movimentacoes VALUES(3,'COMPRA',50,'50.00','2026-08-16','CANCELADO',0,'0.00','DINHEIRO R$ 50.00')")
    connection.execute("INSERT INTO fiscal_sale_documents VALUES(3,3,?,'CANCELADO','2026-08-16')", ("4" * 44,))
    connection.execute("INSERT INTO estoque_movimentacoes VALUES(2,5,'ESTORNO_VENDA','3','ENTRADA','2026-08-16')")
    connection.commit(); connection.close()
    result = service.reconcile(start_date="2026-08-01", end_date="2026-08-31")
    assert _row(result, "VENDA_CANCELAMENTO_ESTORNO", 3).classification == "CONCILIADO"


def test_exporta_csv_versionado_com_resumo_deterministico(reconciliation, tmp_path):
    _, service = reconciliation
    result = service.reconcile(start_date="2026-08-01", end_date="2026-08-31")
    destination = service.export_csv(result, tmp_path / "reconciliacao.csv")
    rows = list(csv.reader(destination.open(encoding="utf-8-sig"), delimiter=";"))
    assert rows[0] == ["layout", "nabicode.accounting-reconciliation.v1"]
    assert [row.relation for row in result.entries] == sorted(row.relation for row in result.entries)
    summary = result.summary()
    assert summary["entries"] == len(result.entries)
    assert sum(summary["counts"].values()) == len(result.entries)


def test_nao_trunca_quantidade_de_vendas_silenciosamente(tmp_path):
    database = tmp_path / "many.db"
    connection = sqlite3.connect(database)
    connection.executescript(SCHEMA)
    connection.executemany(
        "INSERT INTO movimentacoes(id,tipo,valor,data,status_pagamento,forma_pagamento) VALUES(?,'VENDA',1,'2026-08-10','PAGO','DINHEIRO')",
        ((number,) for number in range(1, 1002)),
    )
    connection.commit(); connection.close()
    service = AccountingReconciliationService(lambda: sqlite3.connect(database))
    result = service.reconcile(start_date="2026-08-01", end_date="2026-08-31")
    assert len([row for row in result.entries if row.relation == "VENDA_FISCAL"]) == 1001


def test_periodo_invertido_e_origem_ambigua_nao_sao_aceitos(reconciliation):
    _, service = reconciliation
    with pytest.raises(ValueError, match="data inicial"):
        service.reconcile(start_date="2026-09-01", end_date="2026-08-01")
    result = service.reconcile(start_date="2026-08-01", end_date="2026-08-31")
    dfe = _row(result, "DFE_COMPRA", 1)
    assert dfe.target_id == ""
    assert "não é aceita" in dfe.detail


def test_origens_invalidas_e_pedido_sem_recebimento_sao_expostos(reconciliation):
    database, service = reconciliation
    connection = sqlite3.connect(database)
    connection.execute("INSERT INTO pedidos_compra VALUES(11,'ABERTO','2026-08-18')")
    connection.execute("INSERT INTO estoque_movimentacoes VALUES(8,5,'COMPRA','ABC','ENTRADA','2026-08-18')")
    connection.execute("INSERT INTO titulos_financeiros VALUES(8,'PAGAR','ORIGEM_DESCONHECIDA','77','2026-08-18','2026-08-18',1,'1.00',0,'ABERTO')")
    connection.execute("INSERT INTO configuracoes VALUES('pdv_pagamentos_venda_999','{}')")
    connection.commit(); connection.close()
    result = service.reconcile(start_date="2026-08-01", end_date="2026-08-31")
    assert _row(result, "PEDIDO_RECEBIMENTO", 11).classification == "PENDENTE_DADO_EXTERNO"
    assert _row(result, "ESTOQUE_COMPRA_ORIGEM", 8).classification == "DIVERGENTE"
    assert _row(result, "TITULO_ORIGEM", 8).classification == "DIVERGENTE"
    assert _row(result, "PAGAMENTO_CONFIG_VENDA", "pdv_pagamentos_venda_999").classification == "DIVERGENTE"
