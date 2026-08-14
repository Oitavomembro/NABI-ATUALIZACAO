from __future__ import annotations

import hashlib
import json
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SUPPORTED_PROTOCOL = 1
REQUIRED_COMPONENTS = frozenset({
    "manifest.json", "selection.json", "reports/summary.json", "checksums/SHA256SUMS.txt",
})
REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "customers": ("name",),
    "products": ("name", "sale_price"),
    "stock": ("product_id", "quantity"),
    "sales": ("date", "total"),
    "sale_items": ("sale_id", "product_id", "quantity", "sale_price", "total"),
    "credit_accounts": ("customer_id", "date", "total"),
    "receipts": ("customer_id", "date", "total"),
}
REFERENCES: dict[str, tuple[tuple[str, str], ...]] = {
    "stock": (("product_id", "products"),),
    "sales": (("customer_id", "customers"),),
    "sale_items": (("sale_id", "sales"), ("product_id", "products")),
    "credit_accounts": (("customer_id", "customers"),),
    "receipts": (("customer_id", "customers"),),
}


@dataclass(frozen=True)
class NabiMigImportPreview:
    package: str
    package_sha256: str
    source_system: str
    source_sha256: str
    counts: dict[str, int]
    warnings: tuple[str, ...]
    errors: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return not self.errors


class NabiMigImportService:
    """Porta de entrada offline para pacotes .nabimig; não executa SQL arbitrário."""

    @staticmethod
    def _sha256(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def preview(self, package: str | Path) -> NabiMigImportPreview:
        path = Path(package).expanduser().resolve()
        if path.suffix.lower() != ".nabimig" or not path.is_file() or path.stat().st_size == 0:
            raise ValueError("Selecione um pacote .nabimig valido.")
        package_sha256 = self._sha256(path.read_bytes())
        with zipfile.ZipFile(path) as archive:
            records, manifest = self._read_validated(archive)
        errors, warnings = self._validate_records(records)
        source = manifest.get("source", {})
        return NabiMigImportPreview(
            package=str(path),
            package_sha256=package_sha256,
            source_system=str(source.get("system") or ""),
            source_sha256=str(source.get("sha256") or ""),
            counts=dict(manifest["counts"]),
            warnings=tuple(warnings),
            errors=tuple(errors),
        )

    def _read_validated(self, archive: zipfile.ZipFile) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
        listed = archive.namelist()
        names = set(listed)
        if len(listed) != len(names):
            raise ValueError("Pacote possui componentes repetidos.")
        missing = REQUIRED_COMPONENTS - names
        if missing:
            raise ValueError("Pacote incompleto: " + ", ".join(sorted(missing)))
        if any(name.startswith(("/", "\\")) or ".." in Path(name).parts for name in names):
            raise ValueError("Pacote possui caminho interno inseguro.")

        checked: set[str] = set()
        for line in archive.read("checksums/SHA256SUMS.txt").decode("ascii").splitlines():
            try:
                digest, name = line.split("  ", 1)
            except ValueError as exc:
                raise ValueError("Lista de integridade malformada.") from exc
            if name in checked or name not in names or self._sha256(archive.read(name)) != digest:
                raise ValueError(f"Integridade invalida: {name}")
            checked.add(name)
        if checked != names - {"checksums/SHA256SUMS.txt"}:
            raise ValueError("Nem todos os componentes possuem SHA-256 valido.")

        manifest = json.loads(archive.read("manifest.json"))
        if manifest.get("protocol_version") != SUPPORTED_PROTOCOL or manifest.get("status") != "SUCCESS":
            raise ValueError("Versao ou estado do pacote incompativel.")
        categories = manifest.get("categories")
        counts = manifest.get("counts")
        if not isinstance(categories, list) or not isinstance(counts, dict) or categories != sorted(counts):
            raise ValueError("Manifesto inconsistente.")
        expected_data = {f"data/{category}.jsonl" for category in categories}
        actual_data = {name for name in names if name.startswith("data/") and name.endswith(".jsonl")}
        if expected_data != actual_data:
            raise ValueError("Arquivos de dados nao correspondem ao manifesto.")

        records: dict[str, list[dict[str, Any]]] = {}
        for category in categories:
            rows = [json.loads(line) for line in archive.read(f"data/{category}.jsonl").splitlines() if line.strip()]
            if len(rows) != counts[category]:
                raise ValueError(f"Contagem divergente em {category}.")
            if any(row.get("entity") != category or not str(row.get("source_id") or "").strip() for row in rows):
                raise ValueError(f"Registro canonico invalido em {category}.")
            records[category] = rows
        summary = json.loads(archive.read("reports/summary.json"))
        selection = json.loads(archive.read("selection.json"))
        if summary.get("status") != "SUCCESS" or summary.get("counts") != counts:
            raise ValueError("Resumo divergente do manifesto.")
        if set(selection.get("categories") or ()) != set(categories):
            raise ValueError("Selecao divergente do manifesto.")
        return records, manifest

    def _validate_records(self, records: dict[str, list[dict[str, Any]]]) -> tuple[list[str], list[str]]:
        errors: list[str] = []
        warnings: list[str] = []
        ids: dict[str, set[str]] = {}
        for category, rows in records.items():
            source_ids = [str(row["source_id"]) for row in rows]
            repeated = sum(1 for count in Counter(source_ids).values() if count > 1)
            if repeated:
                errors.append(f"{category}: {repeated} identificador(es) duplicado(s).")
            ids[category] = set(source_ids)
            invalid = sum(
                1 for row in rows
                if any(row.get("data", {}).get(field) in (None, "") for field in REQUIRED_FIELDS.get(category, ()))
            )
            if invalid:
                errors.append(f"{category}: {invalid} registro(s) incompleto(s).")
            if category == "suppliers":
                unnamed = sum(1 for row in rows if not str(row.get("data", {}).get("name") or "").strip())
                if unnamed:
                    warnings.append(f"{unnamed} fornecedor(es) receberao identificacao tecnica unica.")

        for category, links in REFERENCES.items():
            if category not in records:
                continue
            for field, target in links:
                if target not in ids:
                    errors.append(f"{category}: dependencia {target} ausente.")
                    continue
                broken = 0
                for row in records[category]:
                    value = row.get("data", {}).get(field)
                    if field == "customer_id" and value in (None, "", 0, "0"):
                        continue
                    if str(value) not in ids[target]:
                        broken += 1
                if broken:
                    errors.append(f"{category}: {broken} vinculo(s) {field} quebrado(s).")
        return errors, warnings
