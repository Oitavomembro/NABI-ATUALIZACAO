from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path

from services.nabimig_import_service import NabiMigImportService


def encoded(value) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def build_package(path: Path, records: dict[str, list[dict]]) -> None:
    counts = {name: len(rows) for name, rows in records.items()}
    contents = {
        "manifest.json": encoded({
            "protocol_version": 1, "status": "SUCCESS", "categories": sorted(records), "counts": counts,
            "source": {"system": "TEST", "type": "synthetic", "sha256": "a" * 64},
        }),
        "selection.json": encoded({"mode": "custom", "categories": sorted(records)}),
        "reports/summary.json": encoded({"status": "SUCCESS", "counts": counts}),
    }
    for category, rows in records.items():
        contents[f"data/{category}.jsonl"] = b"".join(encoded(row) for row in rows)
    contents["checksums/SHA256SUMS.txt"] = "".join(
        f"{hashlib.sha256(contents[name]).hexdigest()}  {name}\n" for name in sorted(contents)
    ).encode("ascii")
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in contents.items():
            archive.writestr(name, content)


def row(entity: str, source_id: str, data: dict) -> dict:
    return {"entity": entity, "source_id": source_id, "data": data, "source_trace": {"table": entity, "primary_key": "id", "primary_value": source_id}}


class NabiMigImportServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "teste.nabimig"

    def tearDown(self):
        self.temp.cleanup()

    def test_preview_accepts_valid_package_and_anonymous_sale(self):
        build_package(self.path, {
            "customers": [row("customers", "c1", {"name": "Cliente"})],
            "products": [row("products", "p1", {"name": "Produto", "sale_price": 10})],
            "sales": [row("sales", "s1", {"customer_id": 0, "date": "2026-01-01", "total": 10})],
            "sale_items": [row("sale_items", "i1", {"sale_id": "s1", "product_id": "p1", "quantity": 1, "sale_price": 10, "total": 10})],
        })
        preview = NabiMigImportService().preview(self.path)
        self.assertTrue(preview.ready)
        self.assertEqual(preview.counts["sales"], 1)

    def test_preview_rejects_broken_reference(self):
        build_package(self.path, {
            "customers": [row("customers", "c1", {"name": "Cliente"})],
            "sales": [row("sales", "s1", {"customer_id": "missing", "date": "2026-01-01", "total": 10})],
        })
        preview = NabiMigImportService().preview(self.path)
        self.assertFalse(preview.ready)
        self.assertTrue(any("customer_id" in error for error in preview.errors))

    def test_preview_rejects_unchecked_component(self):
        build_package(self.path, {"customers": [row("customers", "c1", {"name": "Cliente"})]})
        with zipfile.ZipFile(self.path, "a") as archive:
            archive.writestr("extra.txt", "nao autorizado")
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            NabiMigImportService().preview(self.path)

    def create_target(self) -> Path:
        target = Path(self.temp.name) / "nabicode.db"
        connection = sqlite3.connect(target)
        connection.executescript("""
            PRAGMA foreign_keys=ON;
            CREATE TABLE clientes(id INTEGER PRIMARY KEY, codigo TEXT UNIQUE, nome TEXT, cpf TEXT, telefone TEXT, origem_migracao TEXT, ficticio INTEGER DEFAULT 0);
            CREATE TABLE fornecedores(id INTEGER PRIMARY KEY, razao_social TEXT, nome_fantasia TEXT UNIQUE COLLATE NOCASE, cnpj TEXT, telefone TEXT, email TEXT, ativo INTEGER, criado_em TEXT, atualizado_em TEXT);
            CREATE TABLE produtos(id INTEGER PRIMARY KEY, codigo TEXT UNIQUE COLLATE NOCASE, nome TEXT, preco_venda REAL, preco_custo REAL, tipo_produto TEXT, controla_estoque INTEGER, participa_xml INTEGER, ativo INTEGER, criado_em TEXT, atualizado_em TEXT, estoque_atual REAL DEFAULT 0);
            CREATE TABLE estoque_movimentacoes(id INTEGER PRIMARY KEY, produto_id INTEGER REFERENCES produtos(id), tipo TEXT, quantidade REAL, saldo_anterior REAL, saldo_atual REAL, origem TEXT, origem_id TEXT, motivo TEXT, usuario TEXT, data TEXT, UNIQUE(origem,origem_id,produto_id));
            CREATE TABLE migracoes_execucoes(id INTEGER PRIMARY KEY, data TEXT, arquivo TEXT, hash_arquivo TEXT, clientes_importados INTEGER, movimentacoes_importadas INTEGER, saldo_total REAL, status TEXT, detalhes TEXT);
            CREATE TABLE migracao_nabimig_ids(id INTEGER PRIMARY KEY, source_system TEXT, entity TEXT, source_id TEXT, target_table TEXT, target_id INTEGER, UNIQUE(source_system,entity,source_id), UNIQUE(target_table,target_id));
        """)
        connection.commit(); connection.close()
        return target

    @staticmethod
    def catalog_records() -> dict[str, list[dict]]:
        return {
            "customers": [row("customers", "c1", {"name": "Cliente", "document": "123", "phone": "999"})],
            "suppliers": [row("suppliers", "f1", {"name": "", "document": "456", "phone": "888", "email": "x@y"})],
            "products": [row("products", "p1", {"name": "Produto", "sale_price": 10, "cost_price": 5})],
            "stock": [row("stock", "p1", {"product_id": "p1", "quantity": 7})],
        }

    def test_catalog_import_creates_backup_and_is_idempotent(self):
        build_package(self.path, self.catalog_records())
        target = self.create_target(); backups = Path(self.temp.name) / "backups"
        connect = lambda: sqlite3.connect(target)
        backup = lambda source, destination: shutil.copy2(source, destination)
        service = NabiMigImportService()
        first = service.execute_catalog(self.path, database_path=target, backup_dir=backups, connect=connect, backup_database=backup)
        second = service.execute_catalog(self.path, database_path=target, backup_dir=backups, connect=connect, backup_database=backup)
        self.assertTrue(Path(first.backup).is_file())
        self.assertEqual(first.inserted, {"customers": 1, "suppliers": 1, "products": 1, "stock": 1})
        self.assertEqual(second.updated, {"customers": 1, "suppliers": 1, "products": 1, "stock": 1})
        connection = sqlite3.connect(target)
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM clientes").fetchone()[0], 1)
        self.assertEqual(connection.execute("SELECT estoque_atual FROM produtos").fetchone()[0], 7)
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM estoque_movimentacoes").fetchone()[0], 1)
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM migracoes_execucoes").fetchone()[0], 2)
        connection.close()

    def test_catalog_import_rolls_back_all_changes_on_failure(self):
        records = self.catalog_records()
        records["stock"][0]["data"]["product_id"] = "missing"
        build_package(self.path, records)
        target = self.create_target(); backups = Path(self.temp.name) / "backups"
        with self.assertRaises(ValueError):
            NabiMigImportService().execute_catalog(
                self.path, database_path=target, backup_dir=backups,
                connect=lambda: sqlite3.connect(target), backup_database=lambda source, destination: shutil.copy2(source, destination),
            )
        connection = sqlite3.connect(target)
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM clientes").fetchone()[0], 0)
        connection.close()

    def test_catalog_import_blocks_financial_category(self):
        build_package(self.path, self.catalog_records())
        with self.assertRaisesRegex(ValueError, "ainda nao liberadas"):
            NabiMigImportService().execute_catalog(
                self.path, database_path=self.create_target(), backup_dir=Path(self.temp.name) / "backups",
                connect=lambda: None, backup_database=lambda *_: None, categories=("credit_accounts",),
            )


if __name__ == "__main__":
    unittest.main()
