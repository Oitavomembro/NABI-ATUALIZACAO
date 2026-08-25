from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import sqlite3
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from services.accounting_reconciliation_service import AccountingReconciliationService


@dataclass(frozen=True)
class AccountantPackageResult:
    path: str
    cnpj: str
    competence: str
    profile: str
    status: str
    files: int
    movements: int
    pendencies: int


class AccountantMonthlyPackageService:
    """Exporta fontes mensais existentes; não escritura nem apura tributos."""

    LAYOUT = "nabicode.accountant-monthly-package.v1"
    PROFILES = {"ESSENCIAL", "COMPLETO", "AUDITORIA"}
    SECTIONS = (
        "00_RESUMO_E_PENDENCIAS", "01_EMPRESA", "02_VENDAS_RECEBIMENTOS",
        "03_XML_SAIDAS", "04_XML_ENTRADAS", "05_CAIXA_BANCOS_CARTOES",
        "06_CONTAS", "07_COMPRAS_FORNECEDORES", "08_ESTOQUE_INVENTARIO",
        "09_TRIBUTOS_RETENCOES", "10_EXTERNOS_PENDENTES", "11_INTERCAMBIO_UNIVERSAL",
        "99_EVIDENCIAS",
    )
    ZIP_TIME = (1980, 1, 1, 0, 0, 0)

    def __init__(
        self, connection_factory: Callable[[], sqlite3.Connection], *,
        fiscal_service: Any | None = None,
        reconciliation_service: AccountingReconciliationService | None = None,
    ) -> None:
        self.connection_factory = connection_factory
        self.fiscal_service = fiscal_service
        self.reconciliation_service = reconciliation_service or AccountingReconciliationService(connection_factory)

    def export(self, *, cnpj: str, competence: str, profile: str, output_path: str | Path) -> AccountantPackageResult:
        document = re.sub(r"\D", "", str(cnpj or ""))
        from services.fiscal_service import FiscalService
        if not FiscalService._is_valid_cnpj(document):
            raise ValueError("Informe um CNPJ válido para identificar o pacote.")
        period_start, period_end = self._competence(competence)
        normalized_profile = str(profile or "").strip().upper()
        if normalized_profile not in self.PROFILES:
            raise ValueError("Perfil inválido. Use ESSENCIAL, COMPLETO ou AUDITORIA.")
        destination = Path(output_path).expanduser().resolve()
        if destination.suffix.casefold() != ".zip":
            raise ValueError("O pacote mensal deve ser gravado em arquivo ZIP.")
        destination.parent.mkdir(parents=True, exist_ok=True)

        connection = self.connection_factory()
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only=ON")
            company, company_pendencies = self._company(connection, document)
            datasets = self._datasets(connection, period_start, period_end, normalized_profile)
        finally:
            connection.close()
        reconciliation = self.reconciliation_service.reconcile(
            start_date=period_start.isoformat(), end_date=period_end.isoformat()
        )
        pendencies = list(company_pendencies)
        for entry in reconciliation.entries:
            if entry.classification in {"DIVERGENTE", "PENDENTE_DADO_EXTERNO", "LEGADO_NAO_PROVAVEL"}:
                pendencies.append({
                    "code": f"RECONCILIACAO_{entry.relation}_{entry.source_id}",
                    "status": entry.classification,
                    "impact": "Revisar antes de usar o pacote como suporte contábil.",
                    "responsible": "EMPRESA/CONTADOR",
                    "due_date": "",
                    "detail": entry.detail,
                })
        pendencies.extend(self._external_pendencies())

        files: dict[str, bytes] = {}
        section_counts: dict[str, int] = {section: 0 for section in self.SECTIONS}
        movement_count = 0

        self._put_json(files, "01_EMPRESA/cadastro_empresa.json", company)
        section_counts["01_EMPRESA"] = 1
        table_routes = {
            "movimentacoes": "02_VENDAS_RECEBIMENTOS/movimentacoes.csv",
            "parcelas": "02_VENDAS_RECEBIMENTOS/parcelas_crediario.csv",
            "cash_sessions": "05_CAIXA_BANCOS_CARTOES/sessoes_caixa.csv",
            "cash_movements": "05_CAIXA_BANCOS_CARTOES/movimentos_caixa.csv",
            "titulos_financeiros": "06_CONTAS/titulos_financeiros.csv",
            "pagamentos_titulos": "06_CONTAS/pagamentos_titulos.csv",
            "fornecedores": "07_COMPRAS_FORNECEDORES/fornecedores.csv",
            "pedidos_compra": "07_COMPRAS_FORNECEDORES/pedidos_compra.csv",
            "recebimentos_compra": "07_COMPRAS_FORNECEDORES/recebimentos_compra.csv",
            "recebimento_compra_itens": "07_COMPRAS_FORNECEDORES/itens_recebidos.csv",
            "produtos": "08_ESTOQUE_INVENTARIO/inventario_produtos.csv",
            "estoque_movimentacoes": "08_ESTOQUE_INVENTARIO/movimentos_estoque.csv",
        }
        for name, rows in datasets.items():
            if name == "auditoria":
                if normalized_profile == "AUDITORIA":
                    self._put_csv(files, "99_EVIDENCIAS/auditoria.csv", rows)
                    section_counts["99_EVIDENCIAS"] += 1
                continue
            route = table_routes[name]
            self._put_csv(files, route, rows)
            section = route.split("/", 1)[0]
            section_counts[section] += 1
            if name in {"movimentacoes", "pagamentos_titulos", "cash_movements", "recebimentos_compra", "estoque_movimentacoes"}:
                movement_count += len(rows)

        fiscal_summary = self._include_fiscal(files, document, period_start, period_end)
        section_counts["03_XML_SAIDAS"] += fiscal_summary["outputs"]
        section_counts["04_XML_ENTRADAS"] += fiscal_summary["inputs"]
        section_counts["99_EVIDENCIAS"] += fiscal_summary["evidence"]
        if not fiscal_summary["available"]:
            pendencies.append(self._pending(
                "FONTE_FISCAL_INDISPONIVEL", "PENDENTE_DADO_EXTERNO",
                "A fonte fiscal V2 não estava disponível para provar XMLs ou ausência de movimento.",
                "EMPRESA/CONTADOR", "ANTES_DO_ENVIO",
            ))

        reconciliation_rows = [
            {
                "relation": row.relation, "source_id": row.source_id, "target_id": row.target_id,
                "classification": row.classification, "competence_date": row.competence_date,
                "cash_date": row.cash_date, "competence_amount": format(row.competence_amount, ".2f"),
                "cash_amount": format(row.cash_amount, ".2f"), "detail": row.detail,
            }
            for row in reconciliation.entries
        ]
        self._put_csv(files, "99_EVIDENCIAS/reconciliacao_v1.csv", reconciliation_rows)
        section_counts["99_EVIDENCIAS"] += 1
        if normalized_profile in {"COMPLETO", "AUDITORIA"}:
            self._put_json(files, "99_EVIDENCIAS/reconciliacao_v1.json", {
                "layout": reconciliation.layout, "period_start": reconciliation.period_start,
                "period_end": reconciliation.period_end, "summary": self._json_safe(reconciliation.summary()),
                "limitations": reconciliation.limitations, "entries": reconciliation_rows,
            })
            section_counts["99_EVIDENCIAS"] += 1

        tributes = {
            "status": "CAPACIDADE_PENDENTE_INTEGRACAO",
            "declaration": "O NabiCode não apura imposto, EFD, PGDAS ou SPED neste pacote.",
            "action": "Contador deve apurar conforme regime, competência, documentos e legislação aplicável.",
        }
        self._put_json(files, "09_TRIBUTOS_RETENCOES/limitacao_tributaria.json", tributes)
        section_counts["09_TRIBUTOS_RETENCOES"] = 1
        self._put_json(files, "10_EXTERNOS_PENDENTES/pendencias_externas.json", self._external_pendencies())
        section_counts["10_EXTERNOS_PENDENTES"] = 1
        exchange = self._exchange_rows(document, competence, datasets)
        batch_id = hashlib.sha256(f"{document}|{competence}|{self.LAYOUT}".encode()).hexdigest()
        self._put_csv(files, "11_INTERCAMBIO_UNIVERSAL/movimentos.csv", exchange)
        self._put_json(files, "11_INTERCAMBIO_UNIVERSAL/layout.json", {
            "layout": "nabicode.accounting-exchange.v1", "batch_id": batch_id,
            "cnpj": document, "competence": competence, "encoding": "UTF-8-BOM",
            "delimiter": ";",
            "idempotency": "source_key identifica a fonte; row_hash detecta conteúdo; row_id identifica esta versão.",
            "columns": {
                "source_key": "Identidade estável SHA-256 por CNPJ/fonte/source_id.",
                "row_hash": "SHA-256 do conteúdo canônico; muda quando o registro muda.",
                "row_id": "Identidade SHA-256 da versão (source_key + row_hash + layout); não é lançamento contábil.",
                "source/source_id": "Origem canônica e ID no NabiCode.",
                "event_date": "Data original do fato disponível.",
                "competence_amount/cash_amount": "Valores separados, sem conta débito/crédito inferida.",
                "document/person/origin": "Referências existentes; vazias quando indisponíveis.",
            },
            "targets": ["Domínio", "Alterdata", "Contmatic", "Omie", "Nibo"],
            "warning": "CSV/JSON universal para mapeamento. Não contém plano de contas, débito/crédito ou lançamentos inventados.",
        })
        section_counts["11_INTERCAMBIO_UNIVERSAL"] = 2
        if normalized_profile in {"COMPLETO", "AUDITORIA"}:
            xlsx = self._xlsx(exchange)
            if xlsx is not None:
                files["11_INTERCAMBIO_UNIVERSAL/movimentos.xlsx"] = xlsx
                section_counts["11_INTERCAMBIO_UNIVERSAL"] += 1

        record_counts = {
            "02_VENDAS_RECEBIMENTOS": len(datasets["movimentacoes"]) + len(datasets["parcelas"]),
            "03_XML_SAIDAS": fiscal_summary["outputs"],
            "04_XML_ENTRADAS": fiscal_summary["inputs"],
            "05_CAIXA_BANCOS_CARTOES": len(datasets["cash_sessions"]) + len(datasets["cash_movements"]),
            "06_CONTAS": len(datasets["titulos_financeiros"]) + len(datasets["pagamentos_titulos"]),
            "07_COMPRAS_FORNECEDORES": len(datasets["pedidos_compra"]) + len(datasets["recebimentos_compra"]),
            "08_ESTOQUE_INVENTARIO": len(datasets["produtos"]) + len(datasets["estoque_movimentacoes"]),
            "11_INTERCAMBIO_UNIVERSAL": len(exchange),
        }
        for section, records in record_counts.items():
            if records == 0:
                files[f"{section}/SEM_MOVIMENTO_OU_DADO_NAO_DISPONIVEL.txt"] = (
                    "DECLARAÇÃO EXPLÍCITA: zero registros disponíveis nesta seção para a competência.\n"
                    "Isso não prova ausência econômica quando a fonte é externa ou indisponível.\n"
                ).encode("utf-8")

        for section in self.SECTIONS:
            if section_counts[section] == 0 and section not in {"00_RESUMO_E_PENDENCIAS"}:
                files[f"{section}/SEM_MOVIMENTO_OU_DADO_NAO_DISPONIVEL.txt"] = (
                    "DECLARAÇÃO EXPLÍCITA: nenhuma fonte disponível foi exportada nesta seção para a competência.\n"
                    "Isso não prova ausência econômica; confira as pendências e fontes externas.\n"
                ).encode("utf-8")

        status = "DIVERGENTE" if any(item["status"] == "DIVERGENTE" for item in pendencies) else (
            "PENDENTE" if pendencies else "CONCILIADO"
        )
        section_summary = self._section_summary(files, datasets, fiscal_summary)
        summary = {
            "layout": self.LAYOUT, "cnpj": document, "competence": competence,
            "profile": normalized_profile, "status": status,
            "sections": section_summary, "pendencies": pendencies,
            "reconciliation": self._json_safe(reconciliation.summary()),
            "warnings": [
                "Pacote de fontes; não é EFD, PGDAS, SPED ou DRE contábil.",
                "Competência e caixa são apresentados separadamente.",
                "Perfil altera anexos/evidências, nunca totais ou movimentações do resumo/manifesto.",
            ],
        }
        self._put_json(files, "00_RESUMO_E_PENDENCIAS/resumo.json", summary)
        self._put_csv(files, "00_RESUMO_E_PENDENCIAS/pendencias.csv", pendencies)
        human_summary = self._human_summary(summary).encode("utf-8")
        files["00_RESUMO_E_PENDENCIAS/LEIA-ME.txt"] = human_summary
        files["LEIA-ME_CONTADOR.txt"] = human_summary

        manifest = {
            "product": "NabiCode", "layout": self.LAYOUT, "version": 1,
            "cnpj": document, "competence": competence, "profile": normalized_profile,
            "status": status, "sections": section_summary,
            "totals_preserved_across_profiles": True,
            "batch_id": batch_id,
            "files": [
                {"file": name, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
                for name, data in sorted(files.items())
            ],
            "non_repudiation": False,
        }
        self._write_zip(destination, files, manifest)
        return AccountantPackageResult(
            str(destination), document, competence, normalized_profile, status,
            len(files), movement_count, len(pendencies),
        )

    @classmethod
    def validate(cls, archive_path: str | Path) -> dict[str, Any]:
        path = Path(archive_path)
        try:
            with zipfile.ZipFile(path) as archive:
                raw_names = archive.namelist()
                if len(raw_names) != len(set(raw_names)):
                    raise ValueError("Pacote contém caminho duplicado.")
                if "manifesto.json" not in raw_names:
                    raise ValueError("Pacote sem manifesto.")
                folded_names: set[str] = set()
                for name in raw_names:
                    normalized = name.replace("\\", "/")
                    if normalized.startswith("/") or ".." in normalized.split("/") or normalized.endswith("/"):
                        raise ValueError("Pacote contém caminho inseguro.")
                    if normalized.casefold() in folded_names:
                        raise ValueError("Pacote contém caminho ambíguo.")
                    folded_names.add(normalized.casefold())
                manifest = json.loads(archive.read("manifesto.json"))
                if manifest.get("layout") != cls.LAYOUT or manifest.get("version") != 1:
                    raise ValueError("Layout do pacote do contador incompatível.")
                from services.fiscal_service import FiscalService
                if not FiscalService._is_valid_cnpj(str(manifest.get("cnpj") or "")):
                    raise ValueError("CNPJ do manifesto é inválido.")
                cls._competence(str(manifest.get("competence") or ""))
                if manifest.get("profile") not in cls.PROFILES:
                    raise ValueError("Perfil do manifesto é inválido.")
                entries = manifest.get("files")
                if not isinstance(entries, list):
                    raise ValueError("Manifesto sem catálogo de arquivos.")
                catalog: dict[str, str] = {}
                for item in entries:
                    name = str(item.get("file") or "") if isinstance(item, dict) else ""
                    digest = str(item.get("sha256") or "") if isinstance(item, dict) else ""
                    size = item.get("size") if isinstance(item, dict) else None
                    if name in catalog or not re.fullmatch(r"[0-9a-f]{64}", digest):
                        raise ValueError("Catálogo do manifesto inconsistente.")
                    if not isinstance(size, int) or size < 0:
                        raise ValueError("Tamanho inválido no catálogo do manifesto.")
                    catalog[name] = digest
                if set(raw_names) != set(catalog) | {"manifesto.json"}:
                    raise ValueError("Conteúdo do ZIP diverge do manifesto.")
                for name, digest in catalog.items():
                    data = archive.read(name)
                    expected_size = next(item["size"] for item in entries if item["file"] == name)
                    if len(data) != expected_size or hashlib.sha256(data).hexdigest() != digest:
                        raise ValueError(f"Arquivo alterado ou corrompido: {name}")
        except (zipfile.BadZipFile, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError("Pacote do contador inválido.") from exc
        return {"valid": True, "layout": cls.LAYOUT, "files_checked": len(catalog), "status": manifest.get("status")}

    def _company(self, connection: sqlite3.Connection, expected_cnpj: str) -> tuple[dict[str, str], list[dict[str, str]]]:
        config = self._json_configuration(connection, "fiscal.config.v1")
        issuer = config.get("issuer") if isinstance(config.get("issuer"), dict) else {}
        values = {
            "razao_social_nome": str(issuer.get("name") or ""),
            "cnpj": re.sub(r"\D", "", str(config.get("cnpj") or "")),
            "inscricao_estadual": str(issuer.get("state_registration") or ""),
            "inscricao_municipal": str(issuer.get("municipal_registration") or ""),
            "uf": str(config.get("state") or ""),
            "municipio": str(issuer.get("city") or ""),
            "codigo_municipio": str(issuer.get("city_code") or ""),
            "logradouro": str(issuer.get("street") or ""),
            "numero": str(issuer.get("number") or ""),
            "bairro": str(issuer.get("district") or ""),
            "cep": str(issuer.get("zip_code") or ""),
            "regime": str(config.get("tax_regime") or ""),
            "crt": self._crt(str(config.get("tax_regime") or "")),
            "cnae": str(config.get("cnae") or ""),
        }
        pendencies: list[dict[str, str]] = []
        if values["cnpj"] and values["cnpj"] != expected_cnpj:
            pendencies.append(self._pending("CNPJ_DIVERGENTE", "DIVERGENTE", "Pacote solicitado para CNPJ diferente do cadastro fiscal.", "EMPRESA", "IMEDIATO"))
        required = {
            "razao_social_nome": "Razão social/nome", "cnpj": "CNPJ", "inscricao_estadual": "IE",
            "inscricao_municipal": "IM", "uf": "UF", "municipio": "Município",
            "logradouro": "Endereço", "regime": "Regime/CRT", "cnae": "CNAE",
        }
        for field, label in required.items():
            if not values[field]:
                pendencies.append(self._pending(f"EMPRESA_{field.upper()}_AUSENTE", "PENDENTE_DADO_EXTERNO", f"{label} não informado no cadastro disponível.", "EMPRESA", "ANTES_DO_ENVIO"))
        return values, pendencies

    def _datasets(self, connection: sqlite3.Connection, start: date, end: date, profile: str) -> dict[str, list[dict[str, Any]]]:
        period_tables = {
            "movimentacoes": ("data",), "parcelas": ("data_pagamento", "vencimento"),
            "cash_sessions": ("opened_at", "closed_at"), "cash_movements": ("created_at",),
            "titulos_financeiros": ("data_emissao", "criado_em"), "pagamentos_titulos": ("data_pagamento",),
            "pedidos_compra": ("criado_em", "atualizado_em"), "recebimentos_compra": ("data_recebimento",),
            "recebimento_compra_itens": (), "estoque_movimentacoes": ("data",), "auditoria": ("data",),
        }
        result: dict[str, list[dict[str, Any]]] = {}
        for table, dates in period_tables.items():
            rows = self._period_rows_sql(connection, table, dates, start, end) if dates else self._rows(connection, table)
            result[table] = rows
        result["fornecedores"] = self._rows(connection, "fornecedores")
        result["produtos"] = self._rows(connection, "produtos")
        receipt_ids = {str(row.get("id")) for row in result["recebimentos_compra"]}
        result["recebimento_compra_itens"] = [
            row for row in result["recebimento_compra_itens"]
            if str(row.get("recebimento_id")) in receipt_ids
        ]
        return result

    def _include_fiscal(self, files: dict[str, bytes], cnpj: str, start: date, end: date) -> dict[str, int]:
        summary = {"outputs": 0, "inputs": 0, "evidence": 0, "events": 0, "available": 0}
        if self.fiscal_service is None:
            return summary
        config = self.fiscal_service.load_config()
        configured = re.sub(r"\D", "", str(config.get("cnpj") or ""))
        if configured and configured != cnpj:
            return summary
        summary["available"] = 1
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / "fiscal.zip"
            self.fiscal_service.export_accounting_package(
                start_date=start.isoformat(), end_date=end.isoformat(), output_path=package,
            )
            validation = self.fiscal_service.validate_accounting_package(package)
            with zipfile.ZipFile(package) as archive:
                fiscal_manifest = json.loads(archive.read("manifesto.json"))
                fiscal_manifest.pop("generated_at", None)
                self._put_json(files, "99_EVIDENCIAS/manifesto_fiscal_v2.json", fiscal_manifest)
                self._put_json(files, "99_EVIDENCIAS/validacao_fiscal_v2.json", validation)
                summary["evidence"] += 2
                for name in archive.namelist():
                    if not name.endswith(".xml"):
                        continue
                    data = archive.read(name)
                    if name.startswith("entradas_DFe/"):
                        target = f"04_XML_ENTRADAS/{name.removeprefix('entradas_DFe/')}"
                        summary["inputs"] += 1
                    elif name.startswith("eventos/"):
                        target = f"99_EVIDENCIAS/eventos/{name.removeprefix('eventos/')}"
                        summary["events"] += 1
                        summary["evidence"] += 1
                    else:
                        target = f"03_XML_SAIDAS/{name}"
                        summary["outputs"] += 1
                    files[target] = data
        return summary

    @classmethod
    def _exchange_rows(
        cls, cnpj: str, competence: str, datasets: Mapping[str, Sequence[Mapping[str, Any]]]
    ) -> list[dict[str, str]]:
        specifications = {
            "movimentacoes": ("id", "data", "valor_decimal", "valor", "descricao", "cliente_id", "origem_sistema", "origem_id", "COMPETENCIA"),
            "pagamentos_titulos": ("id", "data_pagamento", "valor_decimal", "valor", "observacao", "titulo_id", "", "", "CAIXA"),
            "cash_movements": ("id", "created_at", "amount", "amount", "note", "cash_session_id", "source", "source_id", "CAIXA"),
            "recebimentos_compra": ("id", "data_recebimento", "", "", "observacao", "pedido_id", "RECEBIMENTO_COMPRA", "id", "COMPETENCIA"),
            "estoque_movimentacoes": ("id", "data", "", "", "motivo", "produto_id", "origem", "origem_id", "QUANTIDADE"),
        }
        output: list[dict[str, str]] = []
        for source, spec in specifications.items():
            identifier, date_field, canonical, legacy, document_field, person_field, origin_field, origin_id_field, basis = spec
            for row in datasets.get(source, ()):
                source_id = str(row.get(identifier) or "")
                event_date = str(row.get(date_field) or "")
                amount = cls._money(row.get(canonical) if canonical and row.get(canonical) not in (None, "") else row.get(legacy)) if canonical or legacy else Decimal("0")
                stable = json.dumps(cls._json_safe(dict(row)), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                source_key = hashlib.sha256(f"{cnpj}|{source}|{source_id}".encode()).hexdigest()
                row_hash = hashlib.sha256(stable.encode()).hexdigest()
                row_id = hashlib.sha256(
                    f"{source_key}|{row_hash}|nabicode.accounting-exchange.v1".encode()
                ).hexdigest()
                output.append({
                    "source_key": source_key, "row_hash": row_hash, "row_id": row_id,
                    "source": source, "source_id": source_id,
                    "event_date": event_date,
                    "competence_amount": format(amount if basis == "COMPETENCIA" else Decimal("0"), ".2f"),
                    "cash_amount": format(amount if basis == "CAIXA" else Decimal("0"), ".2f"),
                    "basis": basis, "document": str(row.get(document_field) or "") if document_field else "",
                    "person": str(row.get(person_field) or "") if person_field else "",
                    "origin": str(row.get(origin_field) or "") if origin_field else "",
                    "origin_id": str(row.get(origin_id_field) or "") if origin_id_field else "",
                    "account_debit": "", "account_credit": "", "cost_center": "",
                })
        output.sort(key=lambda row: (row["source"], row["source_id"], row["row_id"]))
        return output

    @staticmethod
    def _section_summary(files: Mapping[str, bytes], datasets: Mapping[str, Sequence[Mapping[str, Any]]], fiscal: Mapping[str, int]) -> dict[str, Any]:
        movement_rows = datasets.get("movimentacoes", ())
        return {
            "00_RESUMO_E_PENDENCIAS": {"declaration": "Comece por LEIA-ME_CONTADOR.txt, resumo.json e pendencias.csv."},
            "01_EMPRESA": {"records": 1, "declaration": "Campos ausentes aparecem como pendência explícita."},
            "02_VENDAS_RECEBIMENTOS": {
                "records": len(movement_rows),
                "competence_total": format(sum((AccountantMonthlyPackageService._money(row.get("valor_decimal", row.get("valor"))) for row in movement_rows), Decimal("0")), ".2f"),
            },
            "03_XML_SAIDAS": {"records": fiscal["outputs"]},
            "04_XML_ENTRADAS": {"records": fiscal["inputs"], "declaration": "RESUMO e XML_COMPLETO são identificados no manifesto fiscal V2."},
            "05_CAIXA_BANCOS_CARTOES": {"records": len(datasets.get("cash_movements", ())), "declaration": "Bancos e cartões externos não importados permanecem pendentes."},
            "06_CONTAS": {"titles": len(datasets.get("titulos_financeiros", ())), "payments": len(datasets.get("pagamentos_titulos", ()))},
            "07_COMPRAS_FORNECEDORES": {"orders": len(datasets.get("pedidos_compra", ())), "receipts": len(datasets.get("recebimentos_compra", ()))},
            "08_ESTOQUE_INVENTARIO": {"products": len(datasets.get("produtos", ())), "movements": len(datasets.get("estoque_movimentacoes", ()))},
            "09_TRIBUTOS_RETENCOES": {"status": "CAPACIDADE_PENDENTE_INTEGRACAO"},
            "10_EXTERNOS_PENDENTES": {"declaration": "Bancos, cartões, folha e contratos dependem de fontes externas."},
            "11_INTERCAMBIO_UNIVERSAL": {"records": sum(len(datasets.get(name, ())) for name in ("movimentacoes", "pagamentos_titulos", "cash_movements", "recebimentos_compra", "estoque_movimentacoes"))},
            "99_EVIDENCIAS": {"files": sum(1 for name in files if name.startswith("99_EVIDENCIAS/"))},
        }

    @staticmethod
    def _external_pendencies() -> list[dict[str, str]]:
        return [
            AccountantMonthlyPackageService._pending("EXTERNO_BANCOS", "PENDENTE_DADO_EXTERNO", "Extratos bancários não foram importados.", "EMPRESA/CONTADOR", "FECHAMENTO_MENSAL"),
            AccountantMonthlyPackageService._pending("EXTERNO_CARTOES", "PENDENTE_DADO_EXTERNO", "Extratos/adquirentes de cartões não foram importados.", "EMPRESA/CONTADOR", "FECHAMENTO_MENSAL"),
            AccountantMonthlyPackageService._pending("EXTERNO_FOLHA", "PENDENTE_DADO_EXTERNO", "Folha e encargos não pertencem às fontes importadas.", "CONTADOR", "FECHAMENTO_MENSAL"),
            AccountantMonthlyPackageService._pending("EXTERNO_CONTRATOS", "PENDENTE_DADO_EXTERNO", "Contratos e documentos externos não foram importados.", "EMPRESA", "FECHAMENTO_MENSAL"),
            AccountantMonthlyPackageService._pending("DESPESAS_ESTRUTURADAS", "CAPACIDADE_PENDENTE_INTEGRACAO", "Não há fonte canônica completa de despesas estruturadas nesta base.", "PRODUTO/CONTADOR", ""),
        ]

    @staticmethod
    def _pending(code: str, status: str, impact: str, responsible: str, due_date: str) -> dict[str, str]:
        return {"code": code, "status": status, "impact": impact, "responsible": responsible, "due_date": due_date, "detail": ""}

    @staticmethod
    def _rows(connection: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
        if not re.fullmatch(r"[a-z_]+", table):
            raise ValueError("Fonte inválida.")
        exists = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
        return [dict(row) for row in connection.execute(f"SELECT * FROM {table}").fetchall()] if exists else []

    @classmethod
    def _period_rows_sql(
        cls, connection: sqlite3.Connection, table: str, fields: Iterable[str],
        start: date, end: date,
    ) -> list[dict[str, Any]]:
        if not re.fullmatch(r"[a-z_]+", table):
            raise ValueError("Fonte inválida.")
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if not exists:
            return []
        columns = {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")}
        usable = [field for field in fields if field in columns]
        if not usable:
            return []
        end_exclusive = end + timedelta(days=1)
        found: dict[str, dict[str, Any]] = {}
        for field in usable:
            if not re.fullmatch(r"[a-z_]+", field):
                raise ValueError("Coluna de competência inválida.")
            # Datas ISO usam o caminho indexável. Datas DD/MM/AAAA são uma
            # consulta legada separada, ainda sem materializar todo o histórico.
            queries = (
                (
                    f"SELECT * FROM {table} WHERE instr(COALESCE({field},''),'/')=0 "
                    f"AND {field}>=? AND {field}<?",
                    (start.isoformat(), end_exclusive.isoformat()),
                ),
                (
                    f"SELECT * FROM {table} WHERE instr(COALESCE({field},''),'/')=3 "
                    f"AND (substr({field},7,4)||'-'||substr({field},4,2)||'-'||substr({field},1,2)) BETWEEN ? AND ?",
                    (start.isoformat(), end.isoformat()),
                ),
            )
            for sql, params in queries:
                for row in connection.execute(sql, params).fetchall():
                    data = dict(row)
                    identity = str(data.get("id") or json.dumps(cls._json_safe(data), sort_keys=True))
                    found[identity] = data
        def order_key(value: str) -> tuple[int, Any]:
            return (0, int(value)) if value.isdigit() else (1, value)
        return [found[key] for key in sorted(found, key=order_key)]

    @classmethod
    def _row_in_period(cls, row: Mapping[str, Any], fields: Iterable[str], start: date, end: date) -> bool:
        parsed_dates = [
            AccountingReconciliationService._try_date(row.get(field))
            for field in fields if row.get(field)
        ]
        return any(parsed is not None and start <= parsed <= end for parsed in parsed_dates)

    @staticmethod
    def _json_configuration(connection: sqlite3.Connection, key: str) -> dict[str, Any]:
        exists = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='configuracoes'").fetchone()
        if not exists:
            return {}
        row = connection.execute("SELECT valor FROM configuracoes WHERE chave=?", (key,)).fetchone()
        try:
            value = json.loads(row[0]) if row else {}
        except (TypeError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _competence(value: str) -> tuple[date, date]:
        try:
            start = datetime.strptime(str(value), "%Y-%m").date().replace(day=1)
        except ValueError as exc:
            raise ValueError("Competência inválida; use AAAA-MM.") from exc
        next_month = date(start.year + (start.month == 12), 1 if start.month == 12 else start.month + 1, 1)
        return start, date.fromordinal(next_month.toordinal() - 1)

    @staticmethod
    def _crt(regime: str) -> str:
        return {"SIMPLES_NACIONAL": "1", "SIMPLES_EXCESSO": "2", "REGIME_NORMAL": "3", "MEI": "4"}.get(regime.upper(), "")

    @staticmethod
    def _money(value: Any) -> Decimal:
        return Decimal(str(value or "0").replace(",", ".")).quantize(Decimal("0.01"))

    @staticmethod
    def _put_json(files: dict[str, bytes], name: str, value: Any) -> None:
        files[name] = json.dumps(AccountantMonthlyPackageService._json_safe(value), ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")

    @staticmethod
    def _json_safe(value: Any) -> Any:
        if isinstance(value, Decimal):
            return format(value, "f")
        if isinstance(value, Mapping):
            return {str(key): AccountantMonthlyPackageService._json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [AccountantMonthlyPackageService._json_safe(item) for item in value]
        return value

    @staticmethod
    def _put_csv(files: dict[str, bytes], name: str, rows: Sequence[Mapping[str, Any]]) -> None:
        columns = sorted({str(key) for row in rows for key in row})
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=columns, delimiter=";", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: AccountantMonthlyPackageService._json_safe(row.get(key, "")) for key in columns})
        files[name] = ("\ufeff" + stream.getvalue()).encode("utf-8")

    @classmethod
    def _xlsx(cls, rows: Sequence[Mapping[str, Any]]) -> bytes | None:
        try:
            from openpyxl import Workbook
        except ImportError:
            return None
        columns = sorted({str(key) for row in rows for key in row})
        workbook = Workbook(write_only=True)
        workbook.properties.created = datetime(1980, 1, 1)
        workbook.properties.modified = datetime(1980, 1, 1)
        sheet = workbook.create_sheet("Movimentos")
        sheet.append(columns)
        for row in rows:
            sheet.append([cls._json_safe(row.get(column, "")) for column in columns])
        raw = io.BytesIO()
        workbook.save(raw)
        normalized = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(raw.getvalue())) as source, zipfile.ZipFile(
            normalized, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as target:
            for name in sorted(source.namelist()):
                info = zipfile.ZipInfo(name, cls.ZIP_TIME)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o600 << 16
                target.writestr(info, source.read(name))
        return normalized.getvalue()

    @classmethod
    def _write_zip(cls, destination: Path, files: Mapping[str, bytes], manifest: Mapping[str, Any]) -> None:
        temporary = destination.with_name(f".{destination.name}.tmp")
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name, data in sorted(files.items()):
                info = zipfile.ZipInfo(name, cls.ZIP_TIME)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o600 << 16
                archive.writestr(info, data)
            info = zipfile.ZipInfo("manifesto.json", cls.ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8"))
        temporary.replace(destination)

    @staticmethod
    def _human_summary(summary: Mapping[str, Any]) -> str:
        sales = summary["sections"]["02_VENDAS_RECEBIMENTOS"]
        lines = [
            "PACOTE MENSAL DE FONTES NABICODE", f"CNPJ: {summary['cnpj']}",
            f"Competência: {summary['competence']}", f"Perfil: {summary['profile']}",
            f"Semáforo: {summary['status']}", "",
            "POR ONDE COMEÇAR: abra 00_RESUMO_E_PENDENCIAS/resumo.json e pendencias.csv.",
            "Semáforo CONCILIADO indica vínculos comprovados; PENDENTE exige fonte externa; DIVERGENTE exige correção/revisão.",
            "ESSENCIAL é curto; COMPLETO inclui JSON/XLSX auxiliares; AUDITORIA acrescenta trilha de auditoria.",
            f"Movimentações de vendas/recebimentos: {sales['records']}; total de competência: R$ {sales['competence_total']}.",
            "Este material não é EFD, PGDAS, SPED ou DRE contábil e não apura impostos.",
            f"Pendências: {len(summary['pendencies'])}. Consulte pendencias.csv.",
            "Seção sem dados contém declaração explícita; isso não prova ausência econômica.",
        ]
        return "\n".join(lines) + "\n"
