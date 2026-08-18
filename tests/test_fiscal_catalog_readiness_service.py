import sqlite3

from services.fiscal_catalog_readiness_service import FiscalCatalogReadinessService


def create_database(path):
    connection = sqlite3.connect(path)
    connection.execute(
        """CREATE TABLE produtos(
            id INTEGER PRIMARY KEY,codigo TEXT,nome TEXT,ncm TEXT,cest TEXT,cfop TEXT,
            fiscal_origin TEXT,fiscal_csosn TEXT,fiscal_icms_cst TEXT,fiscal_icms_rate TEXT,
            fiscal_pis_cst TEXT,fiscal_pis_rate TEXT,fiscal_cofins_cst TEXT,fiscal_cofins_rate TEXT,
            fiscal_profile_source TEXT,ibs_cbs_cst TEXT,ibs_cbs_class TEXT,
            ibs_uf_rate TEXT,ibs_city_rate TEXT,cbs_rate TEXT,
            ativo INTEGER,participa_xml INTEGER,tipo_produto TEXT)"""
    )
    return connection


def product_row(product_id, code, name, **changes):
    values = {
        "id": product_id, "codigo": code, "nome": name, "ncm": "94036000", "cest": "",
        "cfop": "5102", "fiscal_origin": "0", "fiscal_csosn": "102",
        "fiscal_icms_cst": "", "fiscal_icms_rate": "0", "fiscal_pis_cst": "07",
        "fiscal_pis_rate": "0", "fiscal_cofins_cst": "07", "fiscal_cofins_rate": "0",
        "fiscal_profile_source": "MANUAL", "ibs_cbs_cst": "000",
        "ibs_cbs_class": "000001", "ibs_uf_rate": "0.1", "ibs_city_rate": "0",
        "cbs_rate": "0.9", "ativo": 1, "participa_xml": 1, "tipo_produto": "MERCADORIA",
    }
    values.update(changes)
    return values


def insert_product(connection, values):
    columns = list(values)
    connection.execute(
        f"INSERT INTO produtos({','.join(columns)}) VALUES({','.join('?' for _ in columns)})",
        tuple(values[column] for column in columns),
    )


def service_for(path):
    return FiscalCatalogReadinessService(lambda: sqlite3.connect(path))


def test_audita_catalogo_pronto_sem_alterar_dados(tmp_path):
    path = tmp_path / "catalog.db"
    connection = create_database(path)
    insert_product(connection, product_row(1, "P1", "Produto pronto"))
    connection.commit(); connection.close()
    report = service_for(path).audit(crt=1)
    assert (report.total, report.ready, report.blocked, report.is_ready) == (1, 1, 0, True)


def test_lista_um_problema_por_produto_e_exclui_servicos(tmp_path):
    path = tmp_path / "catalog.db"
    connection = create_database(path)
    insert_product(connection, product_row(1, "SEM-NCM", "Produto incompleto", ncm=""))
    insert_product(connection, product_row(2, "ST", "Produto ST", cfop="5405", cest="0100100", fiscal_csosn="500"))
    insert_product(connection, product_row(3, "SERV", "Serviço", tipo_produto="SERVICO", ncm=""))
    insert_product(connection, product_row(4, "INAT", "Inativo", ativo=0, ncm=""))
    connection.commit(); connection.close()
    report = service_for(path).audit(crt=1)
    assert report.total == 2
    assert report.ready == 1
    assert report.blocked == 1
    assert report.issues[0].code == "SEM-NCM"
    assert "NCM" in report.issues[0].message


def test_mei_detecta_produto_fora_da_regra_permitida(tmp_path):
    path = tmp_path / "catalog.db"
    connection = create_database(path)
    insert_product(connection, product_row(1, "MEI-ST", "Produto MEI ST", cfop="5405", cest="0100100", fiscal_csosn="400"))
    connection.commit(); connection.close()
    report = service_for(path).audit(crt=4)
    assert report.blocked == 1
    assert "MEI" in report.issues[0].message


def test_catalogo_vazio_nao_e_declarado_pronto(tmp_path):
    path = tmp_path / "catalog.db"
    connection = create_database(path); connection.close()
    report = service_for(path).audit(crt=1)
    assert report.total == 0
    assert report.is_ready is False
