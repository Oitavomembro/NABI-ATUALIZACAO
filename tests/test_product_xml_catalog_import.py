from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
import ast
from pathlib import Path
import socket
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from administration.product_management_service import ProductManagementService
from administration.product_xml_import_service import (
    ProductXMLCatalogImportService, ProductXMLDecision,
)
from commercial.application.product_dto import ProductCreateCommand
from commercial.infrastructure.runtime import create_commercial_container
from database import DatabaseManager
from database.schema_initializer import initialize_database


def xml(*, ncm="94036000", second="", protocol=True):
    protocol_xml = (
        "<protNFe><infProt><cStat>100</cStat><nProt>PROTOCOLO-IGNORADO</nProt>"
        "</infProt></protNFe>"
        if protocol else ""
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">
  <NFe><infNFe Id="NFe{'1' * 44}"><ide><nNF>7</nNF></ide>
    <emit><CNPJ>12345678000199</CNPJ><xNome>Fornecedor não persistido</xNome></emit>
    <det nItem="1"><prod><cProd>ABC1</cProd><xProd>Mesa do XML</xProd>
      <qCom>2</qCom><uCom>UN</uCom><vUnCom>12.34</vUnCom><vProd>24.68</vProd>
      <NCM>{ncm}</NCM><CEST>0100100</CEST><cEAN>7890000000000</cEAN>
    </prod></det>{second}
  </infNFe></NFe>{protocol_xml}
</nfeProc>"""


class Products:
    def __init__(self, catalog=()):
        self.catalog = tuple(catalog)
        self.created_batches = []

    def search_products(self, term, *, limit=200):
        key = str(term).casefold()
        return tuple(
            product for product in self.catalog
            if key in str(product.code).casefold()
            or key in str(product.barcode).casefold()
        )[:limit]

    def create_products_from_xml(self, commands, **context):
        self.created_batches.append((tuple(commands), dict(context)))
        return tuple(
            SimpleNamespace(product_id=100 + index)
            for index, _command in enumerate(commands, start=1)
        )


def product(product_id, code, barcode, description):
    return SimpleNamespace(
        product_id=product_id, code=code, barcode=barcode, description=description,
    )


def write_xml(tmp_path, content=None):
    path = tmp_path / "fornecedor-local.xml"
    path.write_text(content or xml(), encoding="utf-8")
    return path


def create_decision(item, **changes):
    values = dict(
        source_item=item.source_item, action="CREATE", code=item.code,
        description=item.description, barcode=item.barcode, ncm=item.ncm,
        cest=item.cest, unit=item.unit, cost_price=item.cost_price,
        sale_price=Decimal("20.00"),
    )
    values.update(changes)
    return ProductXMLDecision(**values)


def test_prepara_xml_local_com_fonte_alertas_sem_rede_ou_efeito(tmp_path):
    products = Products()
    service = ProductXMLCatalogImportService(products)
    path = write_xml(tmp_path)
    with patch.object(socket, "socket", side_effect=AssertionError("rede proibida")):
        draft = service.prepare(path, actor="maria")

    assert draft.prepared_by == "maria"
    assert draft.source_name == path.name
    assert len(draft.source_sha256) == 64 and len(draft.fingerprint) == 64
    assert len(draft.items) == 1
    item = draft.items[0]
    assert (item.description, item.code, item.barcode) == (
        "Mesa do XML", "ABC1", "7890000000000",
    )
    assert (item.ncm, item.cest, item.unit, item.cost_price) == (
        "94036000", "0100100", "UN", Decimal("12.34"),
    )
    assert item.state == "NOVO"
    assert any("Protocolo" in warning and "ignorado" in warning for warning in draft.warnings)
    assert products.created_batches == []


@pytest.mark.parametrize("content,message", (
    ("<!DOCTYPE foo [<!ENTITY xxe SYSTEM 'file:///c:/secret'>]><foo>&xxe;</foo>", "DTD"),
    ("<root/>", "exatamente uma NF-e"),
    ("<root><infNFe/><infNFe/></root>", "exatamente uma NF-e"),
))
def test_rejeita_xml_hostil_ou_fora_da_fronteira(tmp_path, content, message):
    path = write_xml(tmp_path, content)
    with pytest.raises(ValueError, match=message):
        ProductXMLCatalogImportService(Products()).prepare(path, actor="maria")


def test_rejeita_caminho_de_rede_antes_de_ler():
    with pytest.raises(ValueError, match="local"):
        ProductXMLCatalogImportService(Products()).prepare(
            r"\\servidor\documentos\nota.xml", actor="maria",
        )


def test_ncm_ausente_ou_invalido_fica_vazio_sem_adivinhacao(tmp_path):
    for value in ("", "1234ABCD"):
        path = write_xml(tmp_path, xml(ncm=value))
        draft = ProductXMLCatalogImportService(Products()).prepare(path, actor="maria")
        assert draft.items[0].ncm == ""
        assert any("NCM" in warning for warning in draft.items[0].warnings)


def test_codigo_e_barras_apontando_produtos_distintos_exigem_escolha(tmp_path):
    products = Products((
        product(7, "ABC1", "11111111", "Mesa antiga"),
        product(9, "OUTRO", "7890000000000", "Mesa por barras"),
    ))
    service = ProductXMLCatalogImportService(products)
    draft = service.prepare(write_xml(tmp_path), actor="maria")
    item = draft.items[0]
    assert item.state == "AMBIGUO"
    assert {match.product_id for match in item.matches} == {7, 9}

    with pytest.raises(ValueError, match="escolha explicitamente"):
        service.commit(
            draft, (create_decision(item, action="SKIP"),),
            actor="maria", confirmed=True,
        )
    result = service.commit(
        draft,
        (create_decision(item, action="USE_EXISTING", existing_product_id=9),),
        actor="maria", confirmed=True,
    )
    assert result.created_product_ids == ()
    assert result.existing_product_ids == (9,)
    assert products.created_batches[0][0] == ()


def test_repeticao_no_mesmo_xml_e_deduplicada_sem_criar_segunda_ficha(tmp_path):
    second = """<det nItem="2"><prod><cProd>ABC1</cProd><xProd>Mesa repetida</xProd>
      <qCom>1</qCom><uCom>UN</uCom><vUnCom>10</vUnCom><vProd>10</vProd>
      <NCM>94036000</NCM><cEAN>7890000000000</cEAN></prod></det>"""
    products = Products()
    service = ProductXMLCatalogImportService(products)
    draft = service.prepare(write_xml(tmp_path, xml(second=second)), actor="maria")
    assert [item.state for item in draft.items] == ["NOVO", "DUPLICADO_NO_XML"]
    decisions = (
        create_decision(draft.items[0]),
        create_decision(draft.items[1], action="SKIP"),
    )
    result = service.commit(draft, decisions, actor="maria", confirmed=True)
    assert result.created_product_ids == (101,)
    assert result.skipped_source_items == (2,)
    command = products.created_batches[0][0][0]
    assert command.current_stock == Decimal("0.0000")
    assert command.ncm == "94036000" and command.unit_code == "UN"


def test_numero_de_item_repetido_ou_invalido_falha_antes_da_revisao(tmp_path):
    repeated = """<det nItem="1"><prod><cProd>ABC2</cProd><xProd>Cadeira</xProd>
      <qCom>1</qCom><uCom>UN</uCom><vUnCom>10</vUnCom><vProd>10</vProd>
      <NCM>94036000</NCM></prod></det>"""
    for second in (repeated, repeated.replace('nItem="1"', 'nItem="-2"')):
        path = write_xml(tmp_path, xml(second=second))
        with pytest.raises(ValueError, match="numeração de itens"):
            ProductXMLCatalogImportService(Products()).prepare(path, actor="maria")


def test_confirmacao_sessao_fingerprint_e_mudanca_do_catalogo_falham_fechado(tmp_path):
    products = Products()
    service = ProductXMLCatalogImportService(products)
    draft = service.prepare(write_xml(tmp_path), actor="maria")
    decision = create_decision(draft.items[0])
    with pytest.raises(PermissionError, match="Confirmação humana"):
        service.commit(draft, (decision,), actor="maria", confirmed=False)
    with pytest.raises(PermissionError, match="outra sessão"):
        service.commit(draft, (decision,), actor="joao", confirmed=True)
    with pytest.raises(ValueError, match="alterado"):
        service.commit(
            replace(draft, fingerprint="0" * 64), (decision,),
            actor="maria", confirmed=True,
        )
    products.catalog = (product(7, "ABC1", "", "Cadastro concorrente"),)
    with pytest.raises(RuntimeError, match="catálogo mudou"):
        service.commit(draft, (decision,), actor="maria", confirmed=True)
    assert products.created_batches == []


def test_porta_administrativa_exige_produtos_create_antes_de_abrir_xml():
    products = Mock()
    stock = Mock()
    security = Mock()
    security.session = SimpleNamespace(user=SimpleNamespace(username="maria"))
    security.is_expired.return_value = False
    security.require.return_value = False
    importer = Mock()
    service = ProductManagementService(
        products, stock, security, xml_catalog_import=importer,
    )
    with pytest.raises(PermissionError):
        service.prepare_xml("nao-deve-ser-lido.xml")
    importer.prepare.assert_not_called()
    security.require.assert_called_once_with("produtos", "create")


def test_porta_revalida_sessao_no_commit_e_nao_aceita_ator_da_tela():
    products = Mock()
    security = Mock()
    security.session = SimpleNamespace(user=SimpleNamespace(username="maria"))
    security.is_expired.return_value = False
    security.require.return_value = True
    importer = Mock()
    service = ProductManagementService(
        products, Mock(), security, xml_catalog_import=importer,
    )
    service.commit_xml("draft", ("decision",), confirmed=True)
    importer.commit.assert_called_once_with(
        "draft", ("decision",), actor="maria", confirmed=True,
    )
    security.session = None
    with pytest.raises(PermissionError):
        service.commit_xml("draft", (), confirmed=True)
    assert importer.commit.call_count == 1


def test_fronteira_cadastral_nao_importa_fiscal_operacional_rede_estoque_ou_financeiro():
    path = Path(__file__).parents[1] / "administration" / "product_xml_import_service.py"
    modules = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            modules.extend(alias.name.casefold() for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.append(str(node.module or "").casefold())
    for forbidden in (
        "fiscal_service", "nfe_import_service", "estoque", "financeiro",
        "requests", "urllib", "http.client", "socket", "sqlite",
    ):
        assert not any(forbidden in module for module in modules)


def database_at(tmp_path):
    path = tmp_path / "nabicode.db"
    database = DatabaseManager(path)
    initialize_database(
        db_name=str(path), backup_dir=str(tmp_path / "backups"),
        pdf_dir=str(tmp_path / "pdfs"), schema_version=21,
        last_database_update={
            "executada": False, "de": 0, "para": 21, "backup": "",
        },
        network_mode=False, network_role="local", connect=database.connect,
        read_existing_version=lambda: 0,
        backup_before_update=lambda _source, _target: "",
    )
    return database


def count(database, table):
    return int(database.fetch_one(f"SELECT COUNT(*) AS total FROM {table}")["total"])


def test_gateway_real_cria_so_produtos_com_ids_e_auditoria_atomica(tmp_path):
    database = database_at(tmp_path)
    application = create_commercial_container(database).product_application
    before = {
        table: count(database, table)
        for table in ("produtos", "estoque_movimentacoes", "titulos_financeiros", "nfe_importacoes")
    }
    created = application.create_products_from_xml(
        (ProductCreateCommand(
            "XML-1", "MESA XML", Decimal("20.00"), barcode="7890000000000",
            cost_price=Decimal("12.34"), current_stock=Decimal("0"),
            ncm="94036000", cest="0100100", unit_code="UN",
        ),),
        actor="maria", source_sha256="a" * 64, draft_fingerprint="b" * 64,
        resolved_existing_ids=(), skipped_source_items=(),
    )
    assert len(created) == 1 and created[0].product_id > 0
    row = database.fetch_one(
        "SELECT codigo,codigo_barras,ncm,cest,estoque_atual,preco_custo_decimal "
        "FROM produtos WHERE id=?", (created[0].product_id,),
    )
    assert tuple(row) == (
        "XML-1", "7890000000000", "94036000", "0100100", 0.0, "12.34",
    )
    assert count(database, "produtos") == before["produtos"] + 1
    for table in ("estoque_movimentacoes", "titulos_financeiros", "nfe_importacoes"):
        assert count(database, table) == before[table]
    audit = database.fetch_one(
        "SELECT usuario,modulo,acao,detalhes FROM auditoria "
        "WHERE acao='CADASTRAR_POR_XML' ORDER BY rowid DESC LIMIT 1"
    )
    assert (audit["usuario"], audit["modulo"], audit["acao"]) == (
        "maria", "PRODUTOS", "CADASTRAR_POR_XML",
    )
    assert '"stock_moved":false' in audit["detalhes"]
    assert "Fornecedor não persistido" not in audit["detalhes"]


def test_falha_da_auditoria_reverte_todo_lote_real(tmp_path):
    database = database_at(tmp_path)
    application = create_commercial_container(database).product_application
    with database.session(write=True) as connection:
        connection.execute(
            """CREATE TRIGGER bloquear_auditoria_xml BEFORE INSERT ON auditoria
               WHEN NEW.acao='CADASTRAR_POR_XML'
               BEGIN SELECT RAISE(ABORT, 'auditoria indisponivel'); END"""
        )
    before = count(database, "produtos")
    with pytest.raises(Exception, match="auditoria indisponivel"):
        application.create_products_from_xml(
            (
                ProductCreateCommand("XML-A", "ITEM A", Decimal("1")),
                ProductCreateCommand("XML-B", "ITEM B", Decimal("2")),
            ),
            actor="maria", source_sha256="a" * 64,
            draft_fingerprint="b" * 64,
        )
    assert count(database, "produtos") == before
    assert database.fetch_one(
        "SELECT 1 FROM produtos WHERE codigo IN ('XML-A','XML-B') LIMIT 1"
    ) is None
