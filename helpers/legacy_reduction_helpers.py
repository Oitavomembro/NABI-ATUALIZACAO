"""Pure helpers extracted from ``nabicode_legacy`` without UI behavior."""
from __future__ import annotations


def parse_nonnegative_number(value, field_name: str, *, greater_than_zero: bool = False) -> float:
    original = str(value or "").strip()
    normalized = original.replace(".", "").replace(",", ".")
    if "," not in original and original.count(".") <= 1:
        normalized = original
    try:
        result = float(normalized)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} inválido.") from exc
    if greater_than_zero and result <= 0:
        raise ValueError(f"{field_name} deve ser maior que zero.")
    if result < 0:
        raise ValueError(f"{field_name} não pode ser negativo.")
    return result


def format_number_br(value, decimals: int = 4) -> str:
    return f"{float(value):.{decimals}f}".rstrip("0").rstrip(".").replace(".", ",")


def database_report_text(report) -> str:
    return (
        f"Integridade: {report.integrity}\n"
        f"Chaves estrangeiras: {len(report.foreign_key_errors)} erro(s)\n"
        f"Schema: {report.schema_version} / esperado {report.expected_schema_version}\n"
        f"Tabelas ausentes: {', '.join(report.missing_tables) or 'nenhuma'}\n"
        f"Páginas livres: {report.freelist_count} de {report.page_count}\n"
        f"Status: {'VÁLIDO' if report.valid else 'REQUER ATENÇÃO'}"
    )


def mysql_migration_report_text(report: dict) -> str:
    lines = [
        "RELATÓRIO DE SIMULAÇÃO — NENHUM DADO FOI GRAVADO",
        "=" * 62,
        f"Arquivo: {report['arquivo']}",
        f"Tamanho: {report['tamanho'] / (1024 * 1024):.2f} MB",
        f"Tabelas encontradas: {len(report['tabelas'])}",
        "",
        "REGISTROS POR TABELA",
    ]
    for table in report["tabelas"]:
        lines.append(f"  {table:.<28} {report['contagens'].get(table, 0):>10}")
    lines += [
        "",
        "VALIDAÇÃO DE CLIENTES",
        f"  Clientes encontrados........ {report['clientes']}",
        f"  CPF duplicado (excedentes)... {report['duplicados_cpf']}",
        f"  Fichas duplicadas............ {report['duplicados_ficha']}",
        f"  Códigos duplicados........... {report['duplicados_codigo']}",
        f"  Clientes sem nome............ {report['sem_nome']}",
        f"  Datas inválidas/sentinela.... {report['datas_invalidas']}",
        f"  Telefones fora do padrão..... {report['telefones_invalidos']}",
        "",
        "STATUS: SIMULAÇÃO CONCLUÍDA",
    ]
    return "\n".join(lines)
