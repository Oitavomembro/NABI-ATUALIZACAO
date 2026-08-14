from __future__ import annotations

import hashlib
import json
import zipfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


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
    "credit_accounts": ("customer_id", "date", "due_date", "total", "status"),
    "receipts": ("customer_id", "date", "value"),
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


@dataclass(frozen=True)
class NabiMigImportResult:
    backup: str
    inserted: dict[str, int]
    updated: dict[str, int]
    package_sha256: str


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

    def execute_catalog(
        self,
        package: str | Path,
        **kwargs: Any,
    ) -> NabiMigImportResult:
        kwargs["categories"] = kwargs.get("categories", ("customers", "suppliers", "products", "stock"))
        return self.execute(package, **kwargs)

    def execute(
        self,
        package: str | Path,
        *,
        database_path: str | Path,
        backup_dir: str | Path,
        connect: Callable[[], Any],
        backup_database: Callable[..., Any],
        categories: tuple[str, ...] = ("customers", "suppliers", "products", "stock"),
    ) -> NabiMigImportResult:
        """Importa as categorias escolhidas numa única transação auditável."""
        allowed = {"customers", "suppliers", "products", "stock", "sales", "sale_items", "credit_accounts", "receipts"}
        selected = tuple(dict.fromkeys(categories))
        unknown = set(selected) - allowed
        if unknown:
            raise ValueError("Categorias ainda nao liberadas para escrita: " + ", ".join(sorted(unknown)))
        preview = self.preview(package)
        if not preview.ready:
            raise ValueError("Pacote reprovado: " + "; ".join(preview.errors))
        missing = set(selected) - set(preview.counts)
        if missing:
            raise ValueError("Categorias ausentes do pacote: " + ", ".join(sorted(missing)))

        path = Path(package).expanduser().resolve()
        with zipfile.ZipFile(path) as archive:
            records, manifest = self._read_validated(archive)
        source_system = str(manifest.get("source", {}).get("system") or "NABIMIG")
        backup_path = Path(backup_dir).expanduser().resolve() / f"antes_nabimig_{datetime.now():%Y%m%d_%H%M%S_%f}.db"
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        backup_database(database_path, backup_path)
        if not backup_path.is_file() or backup_path.stat().st_size == 0:
            raise RuntimeError("O backup obrigatorio nao foi criado; importacao cancelada.")

        connection = connect()
        inserted = Counter()
        updated = Counter()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self._require_target_schema(connection)
            target_ids: dict[str, dict[str, int]] = {}
            if "customers" in selected:
                target_ids["customers"] = self._import_customers(connection, records["customers"], source_system, inserted, updated)
            if "suppliers" in selected:
                target_ids["suppliers"] = self._import_suppliers(connection, records["suppliers"], source_system, inserted, updated)
            if "products" in selected:
                target_ids["products"] = self._import_products(connection, records["products"], source_system, inserted, updated)
            if "stock" in selected:
                product_ids = target_ids.get("products") or self._load_target_ids(connection, source_system, "products")
                self._import_stock(connection, records["stock"], product_ids, source_system, inserted, updated)
            customer_ids = target_ids.get("customers") or self._load_target_ids(connection, source_system, "customers")
            product_ids = target_ids.get("products") or self._load_target_ids(connection, source_system, "products")
            if "sales" in selected:
                target_ids["sales"] = self._import_sales(connection, records["sales"], customer_ids, source_system, inserted, updated)
            if "sale_items" in selected:
                sale_ids = target_ids.get("sales") or self._load_target_ids(connection, source_system, "sales")
                self._import_sale_items(connection, records["sale_items"], sale_ids, product_ids, source_system, inserted, updated)
            if "credit_accounts" in selected:
                self._import_credit_accounts(connection, records["credit_accounts"], customer_ids, source_system, inserted, updated)
                self._refresh_customer_balances(connection, customer_ids, source_system)
            if "receipts" in selected:
                self._import_receipts(connection, records["receipts"], customer_ids, source_system, inserted, updated)
            violations = connection.execute("PRAGMA foreign_key_check").fetchall()
            if violations:
                raise RuntimeError(f"Integridade relacional invalida apos importacao: {violations[0]}")
            connection.execute(
                """INSERT INTO migracoes_execucoes
                   (data,arquivo,hash_arquivo,clientes_importados,movimentacoes_importadas,saldo_total,status,detalhes)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (datetime.now().strftime("%d/%m/%Y %H:%M:%S"), str(path), preview.package_sha256,
                 inserted["customers"] + updated["customers"],
                 inserted["sales"] + updated["sales"] + inserted["credit_accounts"] + updated["credit_accounts"],
                 self._imported_open_balance(connection, source_system), "SUCESSO",
                 "NABIMIG: " + ",".join(selected)),
            )
            connection.commit()
            return NabiMigImportResult(str(backup_path), dict(inserted), dict(updated), preview.package_sha256)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _require_target_schema(connection: Any) -> None:
        required = {"clientes", "fornecedores", "produtos", "estoque_movimentacoes", "movimentacoes", "parcelas", "migracoes_execucoes", "migracao_nabimig_ids", "migracao_nabimig_itens_venda"}
        available = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        missing = required - available
        if missing:
            raise RuntimeError("Banco NabiCode incompativel: " + ", ".join(sorted(missing)))

    @staticmethod
    def _mapping(connection: Any, source_system: str, entity: str, source_id: str) -> int | None:
        row = connection.execute(
            "SELECT target_id FROM migracao_nabimig_ids WHERE source_system=? AND entity=? AND source_id=?",
            (source_system, entity, source_id),
        ).fetchone()
        return int(row[0]) if row else None

    @staticmethod
    def _save_mapping(connection: Any, source_system: str, entity: str, source_id: str, table: str, target_id: int) -> None:
        connection.execute(
            """INSERT INTO migracao_nabimig_ids(source_system,entity,source_id,target_table,target_id)
               VALUES(?,?,?,?,?)""", (source_system, entity, source_id, table, target_id),
        )

    def _load_target_ids(self, connection: Any, source_system: str, entity: str) -> dict[str, int]:
        return {str(row[0]): int(row[1]) for row in connection.execute(
            "SELECT source_id,target_id FROM migracao_nabimig_ids WHERE source_system=? AND entity=?",
            (source_system, entity),
        )}

    def _import_customers(self, connection: Any, rows: list[dict[str, Any]], source_system: str, inserted: Counter, updated: Counter) -> dict[str, int]:
        result = {}
        for row in rows:
            sid, data = str(row["source_id"]), row["data"]
            target = self._mapping(connection, source_system, "customers", sid)
            values = (str(data.get("name") or "").strip(), str(data.get("document") or ""), str(data.get("phone") or ""), source_system)
            if target is None:
                code = f"HOST:{sid}"
                connection.execute("INSERT INTO clientes(codigo,nome,cpf,telefone,origem_migracao,ficticio) VALUES(?,?,?,?,?,0)", (code,) + values)
                target = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
                self._save_mapping(connection, source_system, "customers", sid, "clientes", target)
                inserted["customers"] += 1
            else:
                connection.execute("UPDATE clientes SET nome=?,cpf=?,telefone=?,origem_migracao=?,ficticio=0 WHERE id=?", values + (target,))
                updated["customers"] += 1
            result[sid] = target
        return result

    def _import_suppliers(self, connection: Any, rows: list[dict[str, Any]], source_system: str, inserted: Counter, updated: Counter) -> dict[str, int]:
        result = {}; now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for row in rows:
            sid, data = str(row["source_id"]), row["data"]
            target = self._mapping(connection, source_system, "suppliers", sid)
            name = str(data.get("name") or "").strip() or f"Fornecedor migrado HOST-{sid}"
            if target is None:
                candidate = name
                if connection.execute("SELECT 1 FROM fornecedores WHERE nome_fantasia=? COLLATE NOCASE", (candidate,)).fetchone():
                    candidate = f"{name} (HOST-{sid})"
                connection.execute("""INSERT INTO fornecedores(razao_social,nome_fantasia,cnpj,telefone,email,ativo,criado_em,atualizado_em)
                    VALUES(?,?,?,?,?,1,?,?)""", (name, candidate, str(data.get("document") or ""), str(data.get("phone") or ""), str(data.get("email") or ""), now, now))
                target = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
                self._save_mapping(connection, source_system, "suppliers", sid, "fornecedores", target); inserted["suppliers"] += 1
            else:
                connection.execute("UPDATE fornecedores SET razao_social=?,cnpj=?,telefone=?,email=?,atualizado_em=? WHERE id=?", (name, str(data.get("document") or ""), str(data.get("phone") or ""), str(data.get("email") or ""), now, target)); updated["suppliers"] += 1
            result[sid] = target
        return result

    def _import_products(self, connection: Any, rows: list[dict[str, Any]], source_system: str, inserted: Counter, updated: Counter) -> dict[str, int]:
        result = {}; now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for row in rows:
            sid, data = str(row["source_id"]), row["data"]
            target = self._mapping(connection, source_system, "products", sid)
            values = (str(data.get("name") or "").strip(), float(data.get("sale_price") or 0), float(data.get("cost_price") or 0), now)
            if target is None:
                connection.execute("""INSERT INTO produtos(codigo,nome,preco_venda,preco_custo,tipo_produto,controla_estoque,participa_xml,ativo,criado_em,atualizado_em)
                    VALUES(?,?,?,?, 'MERCADORIA',1,1,1,?,?)""", (f"HOST:{sid}", values[0], values[1], values[2], now, now))
                target = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
                self._save_mapping(connection, source_system, "products", sid, "produtos", target); inserted["products"] += 1
            else:
                connection.execute("UPDATE produtos SET nome=?,preco_venda=?,preco_custo=?,atualizado_em=? WHERE id=?", values + (target,)); updated["products"] += 1
            result[sid] = target
        return result

    @staticmethod
    def _import_stock(connection: Any, rows: list[dict[str, Any]], product_ids: dict[str, int], source_system: str, inserted: Counter, updated: Counter) -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for row in rows:
            sid, data = str(row["source_id"]), row["data"]
            product_id = product_ids[str(data["product_id"])]
            quantity = float(data.get("quantity") or 0)
            previous = float(connection.execute("SELECT COALESCE(estoque_atual,0) FROM produtos WHERE id=?", (product_id,)).fetchone()[0])
            connection.execute("UPDATE produtos SET estoque_atual=? WHERE id=?", (quantity, product_id))
            existing = connection.execute("SELECT id FROM estoque_movimentacoes WHERE origem=? AND origem_id=? AND produto_id=?", (source_system, sid, product_id)).fetchone()
            if existing:
                connection.execute("UPDATE estoque_movimentacoes SET quantidade=?,saldo_anterior=?,saldo_atual=?,data=? WHERE id=?", (quantity - previous, previous, quantity, now, existing[0])); updated["stock"] += 1
            else:
                connection.execute("""INSERT INTO estoque_movimentacoes(produto_id,tipo,quantidade,saldo_anterior,saldo_atual,origem,origem_id,motivo,usuario,data)
                    VALUES(?,'AJUSTE',?,?,?,?,?,'Estoque inicial migrado','Migracao',?)""", (product_id, quantity - previous, previous, quantity, source_system, sid, now)); inserted["stock"] += 1

    def _import_sales(self, connection, rows, customer_ids, source_system, inserted, updated):
        result = {}
        for row in rows:
            sid, data = str(row["source_id"]), row["data"]
            target = self._mapping(connection, source_system, "sales", sid)
            customer_ref = data.get("customer_id")
            customer_id = None if customer_ref in (None, "", 0, "0") else customer_ids[str(customer_ref)]
            values = (customer_id, "VENDA_HISTORICA", f"Venda Host #{sid}", float(data.get("total") or 0), str(data.get("date") or ""), "PAGO", 0.0, source_system, f"VENDA:{sid}")
            if target is None:
                connection.execute("INSERT INTO movimentacoes(cliente_id,tipo,descricao,valor,data,status_pagamento,valor_aberto,origem_sistema,origem_id) VALUES(?,?,?,?,?,?,?,?,?)", values)
                target = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
                self._save_mapping(connection, source_system, "sales", sid, "movimentacoes", target); inserted["sales"] += 1
            else:
                connection.execute("UPDATE movimentacoes SET cliente_id=?,tipo=?,descricao=?,valor=?,data=?,status_pagamento=?,valor_aberto=?,origem_sistema=?,origem_id=? WHERE id=?", values + (target,)); updated["sales"] += 1
            result[sid] = target
        return result

    @staticmethod
    def _import_sale_items(connection, rows, sale_ids, product_ids, source_system, inserted, updated):
        for row in rows:
            sid, data = str(row["source_id"]), row["data"]
            sale_ref, product_ref = str(data["sale_id"]), str(data["product_id"])
            if sale_ref not in sale_ids or product_ref not in product_ids:
                raise RuntimeError(f"Item {sid} perdeu vinculo durante a importacao.")
            values = (sale_ref, product_ids[product_ref], float(data.get("quantity") or 0), float(data.get("sale_price") or 0), float(data.get("total") or 0))
            existing = connection.execute("SELECT id FROM migracao_nabimig_itens_venda WHERE source_system=? AND source_id=?", (source_system, sid)).fetchone()
            if existing:
                connection.execute("UPDATE migracao_nabimig_itens_venda SET sale_source_id=?,product_id=?,quantidade=?,valor_unitario=?,valor_total=? WHERE id=?", values + (existing[0],)); updated["sale_items"] += 1
            else:
                connection.execute("INSERT INTO migracao_nabimig_itens_venda(source_system,source_id,sale_source_id,product_id,quantidade,valor_unitario,valor_total) VALUES(?,?,?,?,?,?,?)", (source_system, sid) + values); inserted["sale_items"] += 1

    def _import_credit_accounts(self, connection, rows, customer_ids, source_system, inserted, updated):
        for row in rows:
            sid, data = str(row["source_id"]), row["data"]
            customer_id = customer_ids[str(data["customer_id"])]
            total = float(data.get("total") or 0)
            paid = float(data.get("partial_paid") or 0) + float(data.get("paid_total") or 0)
            source_status = str(data.get("status") or "").strip().upper()
            cancelled = "CANCEL" in source_status
            settled = source_status in {"PAGO", "PAGA", "QUITADO", "QUITADA", "BAIXADO", "BAIXADA"}
            open_value = 0.0 if cancelled or settled else max(0.0, round(total - paid, 2))
            status = "CANCELADO" if cancelled else ("PAGO" if open_value <= 0.005 else ("PARCIAL" if paid > 0 else "PENDENTE"))
            target = self._mapping(connection, source_system, "credit_accounts", sid)
            values = (customer_id, "COMPRA", f"Conta a receber Host #{sid}", total, str(data.get("date") or ""), str(data.get("due_date") or ""), status, open_value, source_system, f"CONTA:{sid}")
            if target is None:
                connection.execute("INSERT INTO movimentacoes(cliente_id,tipo,descricao,valor,data,vencimento,status_pagamento,valor_aberto,origem_sistema,origem_id) VALUES(?,?,?,?,?,?,?,?,?,?)", values)
                target = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
                self._save_mapping(connection, source_system, "credit_accounts", sid, "movimentacoes", target); inserted["credit_accounts"] += 1
            else:
                connection.execute("UPDATE movimentacoes SET cliente_id=?,tipo=?,descricao=?,valor=?,data=?,vencimento=?,status_pagamento=?,valor_aberto=?,origem_sistema=?,origem_id=? WHERE id=?", values + (target,)); updated["credit_accounts"] += 1
            parcel_values = (total, str(data.get("due_date") or ""), status, max(0.0, total - open_value), str(data.get("paid_date") or ""))
            parcel = connection.execute("SELECT id FROM parcelas WHERE movimentacao_id=? AND numero_parcela=1", (target,)).fetchone()
            if parcel:
                connection.execute("UPDATE parcelas SET valor_parcela=?,vencimento=?,status=?,valor_pago=?,data_pagamento=?,dados_confiaveis=1 WHERE id=?", parcel_values + (parcel[0],))
            else:
                connection.execute("INSERT INTO parcelas(movimentacao_id,numero_parcela,valor_parcela,vencimento,status,valor_pago,data_pagamento,dados_confiaveis) VALUES(?,1,?,?,?,?,?,1)", (target,) + parcel_values)

    def _import_receipts(self, connection, rows, customer_ids, source_system, inserted, updated):
        for row in rows:
            sid, data = str(row["source_id"]), row["data"]
            target = self._mapping(connection, source_system, "receipts", sid)
            values = (customer_ids[str(data["customer_id"])], "PAGAMENTO", f"Recebimento Host #{sid}", float(data.get("value") or 0), str(data.get("date") or ""), "PAGO", 0.0, source_system, f"RECEBIMENTO:{sid}")
            if target is None:
                connection.execute("INSERT INTO movimentacoes(cliente_id,tipo,descricao,valor,data,status_pagamento,valor_aberto,origem_sistema,origem_id) VALUES(?,?,?,?,?,?,?,?,?)", values)
                target = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
                self._save_mapping(connection, source_system, "receipts", sid, "movimentacoes", target); inserted["receipts"] += 1
            else:
                connection.execute("UPDATE movimentacoes SET cliente_id=?,tipo=?,descricao=?,valor=?,data=?,status_pagamento=?,valor_aberto=?,origem_sistema=?,origem_id=? WHERE id=?", values + (target,)); updated["receipts"] += 1

    @staticmethod
    def _refresh_customer_balances(connection, customer_ids, source_system):
        for customer_id in customer_ids.values():
            balance = connection.execute("SELECT COALESCE(SUM(valor_aberto),0) FROM movimentacoes WHERE cliente_id=? AND origem_sistema=? AND origem_id LIKE 'CONTA:%' AND status_pagamento<>'CANCELADO'", (customer_id, source_system)).fetchone()[0]
            connection.execute("UPDATE clientes SET saldo_devedor=? WHERE id=?", (float(balance or 0), customer_id))

    @staticmethod
    def _imported_open_balance(connection, source_system):
        row = connection.execute("SELECT COALESCE(SUM(valor_aberto),0) FROM movimentacoes WHERE origem_sistema=? AND origem_id LIKE 'CONTA:%' AND status_pagamento<>'CANCELADO'", (source_system,)).fetchone()
        return float(row[0] or 0)

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
            rows = [self._decode(json.loads(line)) for line in archive.read(f"data/{category}.jsonl").splitlines() if line.strip()]
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

    @classmethod
    def _decode(cls, value: Any) -> Any:
        if isinstance(value, list):
            return [cls._decode(item) for item in value]
        if not isinstance(value, dict):
            return value
        if value.get("$type") in {"decimal", "date", "datetime", "time"}:
            return value.get("value")
        return {str(key): cls._decode(item) for key, item in value.items()}

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
