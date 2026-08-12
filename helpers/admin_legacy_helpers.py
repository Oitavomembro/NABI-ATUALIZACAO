from __future__ import annotations


def migration_phase2_preview_text(data: dict) -> str:
    return "\n".join([
        "PRÉVIA DA MIGRAÇÃO RESUMIDA — FASE 2", "=" * 62,
        f"Clientes a importar/atualizar...... {len(data['clientes'])}",
        f"Transações selecionadas (máx. 12).. {data['movimentacoes_selecionadas']}",
        f"Saldo devedor líquido total........ R$ {data['saldo_total']:,.2f}",
        f"Clientes com saldo credor.......... {data['clientes_com_credito']}", "",
        "Cálculo do saldo: vendas menos entradas e recebimentos; estornos somam novamente à dívida.",
        "Datas sentinela serão deixadas em branco.",
        "Nenhum dado foi gravado nesta prévia.", "", "STATUS: PRONTO PARA IMPORTAR"
    ])


def migration_phase2_result_text(result: dict) -> str:
    return "\n".join([
        "MIGRAÇÃO FASE 2 CONCLUÍDA", "=" * 62,
        f"Clientes novos..................... {result['novos']}",
        f"Clientes atualizados............... {result['atualizados']}",
        f"Movimentações resumidas............ {result['movimentacoes']}",
        f"Saldo total importado............... R$ {result['saldo_total']:,.2f}",
        f"Backup de segurança................. {result['backup']}", "", "STATUS: SUCESSO"
    ])


def parse_profile_permissions(text: str) -> dict[str, list[str]]:
    permissions: dict[str, list[str]] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        module, actions = line.split(":", 1)
        permissions[module.strip()] = [action.strip() for action in actions.split(",") if action.strip()]
    return permissions
