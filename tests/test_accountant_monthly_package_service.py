from __future__ import annotations

import csv
import io
import json
import sqlite3
import zipfile

import pytest

from services.accountant_monthly_package_service import AccountantMonthlyPackageService


SCHEMA = """
CREATE TABLE configuracoes(chave TEXT PRIMARY KEY, valor TEXT);
CREATE TABLE movimentacoes(id INTEGER PRIMARY KEY, cliente_id INTEGER, tipo TEXT, descricao TEXT,
 valor REAL, valor_decimal TEXT, data TEXT, status_pagamento TEXT, valor_aberto REAL,
 valor_aberto_decimal TEXT, forma_pagamento TEXT, origem_sistema TEXT, origem_id TEXT);
CREATE TABLE parcelas(id INTEGER PRIMARY KEY, movimentacao_id INTEGER, valor_parcela REAL,
 vencimento TEXT, data_pagamento TEXT);
CREATE TABLE titulos_financeiros(id INTEGER PRIMARY KEY, tipo TEXT, origem TEXT, origem_id TEXT,
 pessoa_id INTEGER, documento TEXT, descricao TEXT, data_emissao TEXT, valor_original REAL,
 valor_pago REAL, status TEXT, criado_em TEXT);
CREATE TABLE pagamentos_titulos(id INTEGER PRIMARY KEY, titulo_id INTEGER, valor REAL,
 valor_decimal TEXT, forma_pagamento TEXT, observacao TEXT, data_pagamento TEXT);
CREATE TABLE fornecedores(id INTEGER PRIMARY KEY, razao_social TEXT, nome_fantasia TEXT, cnpj TEXT);
CREATE TABLE pedidos_compra(id INTEGER PRIMARY KEY, fornecedor_id INTEGER, status TEXT,
 observacao TEXT, criado_em TEXT, atualizado_em TEXT);
CREATE TABLE recebimentos_compra(id INTEGER PRIMARY KEY, pedido_id INTEGER, documento TEXT,
 observacao TEXT, data_recebimento TEXT);
CREATE TABLE recebimento_compra_itens(id INTEGER PRIMARY KEY, recebimento_id INTEGER,
 pedido_item_id INTEGER, produto_id INTEGER, valor_total REAL);
CREATE TABLE produtos(id INTEGER PRIMARY KEY, codigo TEXT, nome TEXT, estoque_atual REAL);
CREATE TABLE estoque_movimentacoes(id INTEGER PRIMARY KEY, produto_id INTEGER, tipo TEXT,
 quantidade REAL, origem TEXT, origem_id TEXT, motivo TEXT, data TEXT);
CREATE TABLE cash_sessions(id INTEGER PRIMARY KEY, opened_at TEXT, closed_at TEXT, status TEXT);
CREATE TABLE cash_movements(id INTEGER PRIMARY KEY, cash_session_id INTEGER, type TEXT,
 amount TEXT, source TEXT, source_id TEXT, note TEXT, created_at TEXT);
CREATE TABLE fiscal_sale_documents(id INTEGER PRIMARY KEY, sale_id INTEGER, access_key TEXT,
 status TEXT, created_at TEXT);
CREATE TABLE nfe_importacoes(id INTEGER PRIMARY KEY, chave TEXT, valor_total TEXT, data_importacao TEXT);
CREATE TABLE auditoria(id INTEGER PRIMARY KEY, data TEXT, usuario TEXT, modulo TEXT,
 acao TEXT, detalhes TEXT, resultado TEXT);
"""


class FiscalStub:
    def __init__(self, cnpj="12345678000195"):
        self.cnpj = cnpj

    def load_config(self):
        return {"cnpj": self.cnpj}

    def export_accounting_package(self, *, start_date, end_date, output_path):
        manifest = {
            "version": 2, "layout": "nabicode.accounting-package.v2",
            "received_documents": [
                {"file": "entradas_DFe/2026-08/resumo.xml", "content": "RESUMO"},
                {"file": "entradas_DFe/2026-08/completo.xml", "content": "XML_COMPLETO"},
            ],
        }
        with zipfile.ZipFile(output_path, "w") as archive:
            archive.writestr("producao/NFe/NFe1.xml", b"<NFe/>")
            archive.writestr("entradas_DFe/2026-08/resumo.xml", b"<resNFe/>")
            archive.writestr("entradas_DFe/2026-08/completo.xml", b"<nfeProc/>")
            archive.writestr("eventos/1/cancelamento.xml", b"<evento/>")
            archive.writestr("manifesto.json", json.dumps(manifest))

    def validate_accounting_package(self, path):
        return {"valid": True, "layout": "V2", "non_repudiation": False}


@pytest.fixture
def package_service(tmp_path):
    database = tmp_path / "data.db"
    connection = sqlite3.connect(database)
    connection.executescript(SCHEMA)
    fiscal_config = {
        "cnpj": "12345678000195", "state": "BA", "tax_regime": "SIMPLES_NACIONAL",
        "cnae": "4711302", "certificate_path": "SEGREDO/certificado.pfx",
        "certificate_password": "NAO_EXPORTAR", "endpoints": {"PRODUCAO": {"x": "secreto"}},
        "issuer": {
            "name": "EMPRESA TESTE LTDA", "state_registration": "123", "municipal_registration": "456",
            "city": "JUAZEIRO", "city_code": "2918407", "street": "RUA A", "number": "10",
            "district": "CENTRO", "zip_code": "48900000",
        },
    }
    connection.execute("INSERT INTO configuracoes VALUES('fiscal.config.v1',?)", (json.dumps(fiscal_config),))
    connection.execute("INSERT INTO movimentacoes VALUES(1,7,'COMPRA','Venda',100,'100.00','2026-08-10','PAGO',0,'0.00','PIX','PDV','1')")
    connection.execute("INSERT INTO parcelas VALUES(1,1,100,'2026-08-10','2026-08-10')")
    connection.execute("INSERT INTO titulos_financeiros VALUES(1,'RECEBER','VENDA','1',7,'V1','Venda','2026-08-10',100,100,'PAGO','2026-08-10')")
    connection.execute("INSERT INTO pagamentos_titulos VALUES(1,1,100,'100.00','PIX','','2026-08-10')")
    connection.execute("INSERT INTO fornecedores VALUES(1,'FORNECEDOR LTDA','FORNECEDOR','11111111000191')")
    connection.execute("INSERT INTO pedidos_compra VALUES(1,1,'RECEBIDO','', '2026-08-05','2026-08-06')")
    connection.execute("INSERT INTO recebimentos_compra VALUES(1,1,'NF1','', '2026-08-06')")
    connection.execute("INSERT INTO recebimento_compra_itens VALUES(1,1,1,1,30)")
    connection.execute("INSERT INTO produtos VALUES(1,'P1','PRODUTO',5)")
    connection.execute("INSERT INTO estoque_movimentacoes VALUES(1,1,'ENTRADA',5,'COMPRA','1:1:0','', '2026-08-06')")
    connection.execute("INSERT INTO cash_sessions VALUES(1,'2026-08-01','','ABERTO')")
    connection.execute("INSERT INTO cash_movements VALUES(1,1,'SUPRIMENTO','20.00','CAIXA','','', '2026-08-02')")
    connection.execute("INSERT INTO fiscal_sale_documents VALUES(1,1,?,'AUTORIZADO','2026-08-10')", ("1" * 44,))
    connection.execute("INSERT INTO auditoria VALUES(1,'2026-08-10','admin','Venda','CRIAR','ok','SUCESSO')")
    connection.commit(); connection.close()
    return database, AccountantMonthlyPackageService(
        lambda: sqlite3.connect(database), fiscal_service=FiscalStub()
    )


def _manifest(path):
    with zipfile.ZipFile(path) as archive:
        return json.loads(archive.read("manifesto.json")), set(archive.namelist())


@pytest.mark.parametrize("profile", ["ESSENCIAL", "COMPLETO", "AUDITORIA"])
def test_perfis_preservam_totais_e_movimentacoes(package_service, tmp_path, profile):
    _, service = package_service
    output = tmp_path / f"{profile}.zip"
    result = service.export(cnpj="12.345.678/0001-95", competence="2026-08", profile=profile, output_path=output)
    manifest, names = _manifest(output)
    assert result.movements == 5
    assert manifest["sections"]["02_VENDAS_RECEBIMENTOS"]["records"] == 1
    assert manifest["sections"]["02_VENDAS_RECEBIMENTOS"]["competence_total"] == "100.00"
    assert manifest["totals_preserved_across_profiles"] is True
    assert "LEIA-ME_CONTADOR.txt" in names
    assert set(manifest["sections"]) == set(service.SECTIONS)
    assert "11_INTERCAMBIO_UNIVERSAL/layout.json" in names
    assert "11_INTERCAMBIO_UNIVERSAL/movimentos.csv" in names
    assert ("11_INTERCAMBIO_UNIVERSAL/movimentos.xlsx" in names) is (profile != "ESSENCIAL")
    assert ("99_EVIDENCIAS/auditoria.csv" in names) is (profile == "AUDITORIA")
    assert ("99_EVIDENCIAS/reconciliacao_v1.json" in names) is (profile != "ESSENCIAL")
    assert service.validate(output)["valid"] is True


def test_empresa_completa_e_segredos_nao_sao_exportados(package_service, tmp_path):
    _, service = package_service
    output = tmp_path / "privacy.zip"
    service.export(cnpj="12345678000195", competence="2026-08", profile="COMPLETO", output_path=output)
    with zipfile.ZipFile(output) as archive:
        company = json.loads(archive.read("01_EMPRESA/cadastro_empresa.json"))
        all_bytes = b"\n".join(archive.read(name) for name in archive.namelist())
    assert company["razao_social_nome"] == "EMPRESA TESTE LTDA"
    assert company["inscricao_estadual"] == "123" and company["cnae"] == "4711302"
    assert b"certificado.pfx" not in all_bytes and b"NAO_EXPORTAR" not in all_bytes
    assert b'"endpoints"' not in all_bytes


def test_xml_saida_entrada_resumo_completo_e_evento_preservados(package_service, tmp_path):
    _, service = package_service
    output = tmp_path / "xml.zip"
    service.export(cnpj="12345678000195", competence="2026-08", profile="COMPLETO", output_path=output)
    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
        fiscal_manifest = json.loads(archive.read("99_EVIDENCIAS/manifesto_fiscal_v2.json"))
    assert "03_XML_SAIDAS/producao/NFe/NFe1.xml" in names
    assert "04_XML_ENTRADAS/2026-08/resumo.xml" in names
    assert "04_XML_ENTRADAS/2026-08/completo.xml" in names
    assert "99_EVIDENCIAS/eventos/1/cancelamento.xml" in names
    assert {row["content"] for row in fiscal_manifest["received_documents"]} == {"RESUMO", "XML_COMPLETO"}


def test_intercambio_tem_ids_idempotentes_e_nao_inventa_contas(package_service, tmp_path):
    _, service = package_service
    output = tmp_path / "exchange.zip"
    service.export(cnpj="12345678000195", competence="2026-08", profile="ESSENCIAL", output_path=output)
    with zipfile.ZipFile(output) as archive:
        layout = json.loads(archive.read("11_INTERCAMBIO_UNIVERSAL/layout.json"))
        rows = list(csv.DictReader(io.StringIO(archive.read("11_INTERCAMBIO_UNIVERSAL/movimentos.csv").decode("utf-8-sig")), delimiter=";"))
    assert layout["layout"] == "nabicode.accounting-exchange.v1"
    assert all(len(row["row_id"]) == 64 for row in rows)
    assert all(row["account_debit"] == row["account_credit"] == "" for row in rows)
    assert len({row["row_id"] for row in rows}) == len(rows)


def test_pacote_deterministico_com_mesmos_dados(package_service, tmp_path):
    _, service = package_service
    first, second = tmp_path / "a.zip", tmp_path / "b.zip"
    service.export(cnpj="12345678000195", competence="2026-08", profile="COMPLETO", output_path=first)
    service.export(cnpj="12345678000195", competence="2026-08", profile="COMPLETO", output_path=second)
    assert first.read_bytes() == second.read_bytes()


def test_sem_movimento_e_dados_ausentes_sao_declarados(tmp_path):
    database = tmp_path / "empty.db"
    connection = sqlite3.connect(database); connection.executescript(SCHEMA); connection.commit(); connection.close()
    service = AccountantMonthlyPackageService(lambda: sqlite3.connect(database))
    output = tmp_path / "empty.zip"
    result = service.export(cnpj="12345678000195", competence="2026-08", profile="ESSENCIAL", output_path=output)
    manifest, names = _manifest(output)
    assert result.pendencies > 5 and result.status == "PENDENTE"
    assert "03_XML_SAIDAS/SEM_MOVIMENTO_OU_DADO_NAO_DISPONIVEL.txt" in names
    assert "04_XML_ENTRADAS/SEM_MOVIMENTO_OU_DADO_NAO_DISPONIVEL.txt" in names
    assert manifest["sections"]["02_VENDAS_RECEBIMENTOS"]["records"] == 0


def test_cnpj_divergente_e_competencia_invalida(package_service, tmp_path):
    _, service = package_service
    output = tmp_path / "wrong.zip"
    result = service.export(cnpj="99999999000199", competence="2026-08", profile="ESSENCIAL", output_path=output)
    assert result.status == "DIVERGENTE"
    with pytest.raises(ValueError, match="Competência"):
        service.export(cnpj="12345678000195", competence="08/2026", profile="ESSENCIAL", output_path=output)


def test_validador_rejeita_tamper_e_extra(package_service, tmp_path):
    _, service = package_service
    output = tmp_path / "valid.zip"
    service.export(cnpj="12345678000195", competence="2026-08", profile="ESSENCIAL", output_path=output)
    with zipfile.ZipFile(output) as archive:
        entries = [(info.filename, archive.read(info.filename)) for info in archive.infolist()]
    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(tampered, "w") as archive:
        for name, data in entries:
            archive.writestr(name, data + b"x" if name.endswith("movimentacoes.csv") else data)
    with pytest.raises(ValueError, match="alterado ou corrompido"):
        service.validate(tampered)
    extra = tmp_path / "extra.zip"
    with zipfile.ZipFile(extra, "w") as archive:
        for name, data in entries:
            archive.writestr(name, data)
        archive.writestr("extra.txt", "x")
    with pytest.raises(ValueError, match="diverge do manifesto"):
        service.validate(extra)


def test_mais_de_mil_registros_sem_truncamento(package_service, tmp_path):
    database, service = package_service
    connection = sqlite3.connect(database)
    connection.executemany(
        "INSERT INTO movimentacoes(id,tipo,valor,valor_decimal,data,status_pagamento) VALUES(?,'VENDA',1,'1.00','2026-08-20','PAGO')",
        ((number,) for number in range(2, 1003)),
    )
    connection.commit(); connection.close()
    output = tmp_path / "many.zip"
    service.export(cnpj="12345678000195", competence="2026-08", profile="ESSENCIAL", output_path=output)
    manifest, _ = _manifest(output)
    assert manifest["sections"]["02_VENDAS_RECEBIMENTOS"]["records"] == 1002
    assert manifest["sections"]["02_VENDAS_RECEBIMENTOS"]["competence_total"] == "1101.00"
