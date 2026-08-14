from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .nabimig_import_service import NabiMigImportPreview, NabiMigImportResult


CATEGORY_LABELS = {
    "customers": "Clientes",
    "products": "Produtos",
    "stock": "Estoque",
    "suppliers": "Fornecedores",
    "sales": "Vendas históricas",
    "sale_items": "Itens das vendas",
    "credit_accounts": "Crediário/Contas a receber",
    "receipts": "Recebimentos",
}


def preview_text(preview: NabiMigImportPreview) -> str:
    lines = [
        f"Origem: {preview.source_system or 'Não informada'}",
        f"SHA-256: {preview.package_sha256}",
        "",
        "Conteúdo do pacote:",
    ]
    lines.extend(
        f"• {CATEGORY_LABELS.get(category, category)}: {count}"
        for category, count in preview.counts.items()
    )
    if preview.warnings:
        lines.extend(("", "Avisos:", *(f"• {warning}" for warning in preview.warnings)))
    if preview.errors:
        lines.extend(("", "Erros:", *(f"• {error}" for error in preview.errors)))
    return "\n".join(lines)


def final_report_text(
    preview: NabiMigImportPreview,
    result: NabiMigImportResult,
    database_path: str | Path,
    *,
    demos_requested_for_removal: bool,
) -> str:
    labels = lambda values: ", ".join(CATEGORY_LABELS.get(item, item) for item in values) or "Nenhuma"
    money = lambda value: f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    inserted = sum(result.inserted.values())
    updated = sum(result.updated.values())
    warnings = list(preview.warnings)
    if result.demo_customers_preserved:
        warnings.append(
            f"{result.demo_customers_preserved} cliente(s) demonstrativo(s) foram preservados por possuírem vínculos."
        )
    lines = [
        "RELATÓRIO DE IMPORTAÇÃO .NABIMIG",
        "Status: SUCESSO",
        f"Data/hora: {datetime.now():%d/%m/%Y %H:%M:%S}",
        f"Pacote: {preview.package}",
        f"SHA-256: {preview.package_sha256}",
        f"Sistema de origem: {preview.source_system or 'Não informado'}",
        f"Banco de destino: {Path(database_path).resolve()}",
        f"Backup: {result.backup}",
        f"Categorias selecionadas: {labels(result.selected_categories)}",
        f"Dependências automáticas: {labels(result.automatic_dependencies)}",
        f"Registros inseridos: {inserted}",
        f"Registros atualizados: {updated}",
        "Registros ignorados: 0",
        f"Clientes demonstrativos: {'remoção solicitada' if demos_requested_for_removal else 'preservados por opção'}",
        f"Demonstrativos removidos: {result.demo_customers_removed}",
        f"Demonstrativos preservados: {result.demo_customers_preserved}",
        f"Saldo aberto importado: R$ {money(result.open_balance)}",
        f"Verificação de chaves estrangeiras: {result.foreign_key_check}",
        "Avisos: " + (" | ".join(warnings) if warnings else "Nenhum"),
    ]
    return "\n".join(lines)
