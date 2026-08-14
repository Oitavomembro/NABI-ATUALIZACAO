from __future__ import annotations

import os
import shutil
import sqlite3
from pathlib import Path

import pytest

from database.schema_initializer import initialize_database
from services.nabimig_import_service import NabiMigImportService


REAL_PACKAGE = os.environ.get("NABICODE_NABIMIG_REAL_PACKAGE", "")


@pytest.mark.skipif(not REAL_PACKAGE, reason="pacote real não informado")
def test_real_package_twice_in_temporary_database(tmp_path):
    package = Path(REAL_PACKAGE)
    database = tmp_path / "nabicode-teste.db"
    backup_dir = tmp_path / "backups"

    def connect():
        connection = sqlite3.connect(database)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    initialize_database(
        db_name=str(database), backup_dir=str(backup_dir), pdf_dir=str(tmp_path / "pdfs"),
        schema_version=32,
        last_database_update={"executada": False, "de": 0, "para": 32, "backup": ""},
        network_mode=False, network_role="local",
        connect=connect, read_existing_version=lambda: 0, backup_before_update=lambda *_: "",
    )
    service = NabiMigImportService()
    preview = service.preview(package)
    assert preview.ready
    assert preview.counts == {
        "credit_accounts": 32, "customers": 87, "products": 198,
        "sale_items": 317, "sales": 277, "stock": 198, "suppliers": 12,
    }
    categories = tuple(preview.counts)
    arguments = dict(
        database_path=database, backup_dir=backup_dir, connect=connect,
        backup_database=lambda source, destination: shutil.copy2(source, destination),
        categories=categories, remove_demo_customers=True,
    )
    first = service.execute(package, **arguments)
    second = service.execute(package, **arguments)
    assert first.open_balance == pytest.approx(10171.0)
    assert second.open_balance == pytest.approx(10171.0)
    assert sum(second.inserted.values()) == 0
    connection = connect()
    try:
        assert connection.execute("SELECT COUNT(*) FROM clientes WHERE origem_migracao='HOST_FIREBIRD_2_5'").fetchone()[0] == 87
        assert connection.execute("SELECT COUNT(*) FROM produtos WHERE codigo LIKE 'HOST:%'").fetchone()[0] == 198
        assert connection.execute("SELECT COUNT(*) FROM fornecedores").fetchone()[0] == 12
        assert connection.execute("SELECT COUNT(*) FROM movimentacoes WHERE tipo='VENDA_HISTORICA'").fetchone()[0] == 277
        assert connection.execute("SELECT COUNT(*) FROM migracao_nabimig_itens_venda").fetchone()[0] == 317
        assert connection.execute("SELECT COUNT(*) FROM movimentacoes WHERE origem_id LIKE 'CONTA:%'").fetchone()[0] == 32
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        connection.close()
    assert len(list(backup_dir.glob("antes_nabimig_*.db"))) == 2
