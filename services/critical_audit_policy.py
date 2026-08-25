from __future__ import annotations


CRITICAL_EVENTS: dict[str, frozenset[str]] = {
    "SEGURANCA": frozenset({
        "CONFIGURACAO_INICIAL",
        "MIGRACAO_CREDENCIAL_LEGADA",
        "CRIAR_USUARIO",
        "ATUALIZAR_USUARIO",
        "SALVAR_PERFIL",
        "EXCLUIR_PERFIL",
        "ALTERAR_SENHA",
    }),
    "CAIXA": frozenset({"CAIXA_FECHADO", "SANGRIA", "SUPRIMENTO"}),
    "FINANCEIRO": frozenset({"CANCELAR_TITULO", "CANCELAR_TITULO_ORIGEM", "ESTORNAR_PAGAMENTO"}),
    "ESTOQUE": frozenset({"AJUSTE", "SAIDA"}),
    "COMPRAS": frozenset({"RECEBER"}),
    "SISTEMA": frozenset({"RESTAURAR", "RESET", "ATUALIZAR"}),
    "LICENCIAMENTO": frozenset({"EMITIR", "RENOVAR", "REVOGAR", "ATIVAR"}),
}

FISCAL_MUTATIONS = frozenset(
    {
        "CONFIGURAR",
        "SALVAR_CONFIGURACAO",
        "TRANSMITIR",
        "AUTORIZAR",
        "CANCELAR",
        "INUTILIZAR",
        "RECONCILIAR",
        "REENVIAR",
        "IMPORTAR",
        "ESTORNAR",
        "EXCLUIR",
        "MANIFESTAR",
        "FINALIZAR",
    }
)


def normalize_event(module: object, action: object) -> tuple[str, str]:
    return str(module or "").strip().upper(), str(action or "").strip().upper()


def is_critical_event(module: object, action: object) -> bool:
    normalized_module, normalized_action = normalize_event(module, action)
    if normalized_action in CRITICAL_EVENTS.get(normalized_module, frozenset()):
        return True
    return normalized_module.startswith("FISCAL") and normalized_action in FISCAL_MUTATIONS


def record_in_transaction(
    connection,
    module: object,
    action: object,
    *,
    user: object,
    object_id: object = "",
    details: object = "",
    result: object = "SUCESSO",
    occurred_at: object,
) -> None:
    """Auditoria estrita; a ausência da tabela ou falha SQL bloqueia a mutação."""
    if not is_critical_event(module, action):
        raise ValueError("record_in_transaction é exclusivo para eventos críticos catalogados.")
    connection.execute(
        """INSERT INTO auditoria(data,usuario,modulo,acao,objeto,detalhes,resultado)
           VALUES(?,?,?,?,?,?,?)""",
        (
            str(occurred_at),
            str(user),
            str(module),
            str(action),
            str(object_id),
            str(details),
            str(result),
        ),
    )
