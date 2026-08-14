from __future__ import annotations

import hashlib
import json
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


if __name__ == "__main__":
    unittest.main()
