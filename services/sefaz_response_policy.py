from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SefazAction(str, Enum):
    AUTHORIZED = "AUTHORIZED"
    WAIT_AND_RETRY = "WAIT_AND_RETRY"
    QUERY_BEFORE_RETRY = "QUERY_BEFORE_RETRY"
    CORRECT_AND_RETRY = "CORRECT_AND_RETRY"
    TERMINAL_DENIAL = "TERMINAL_DENIAL"
    MANUAL_REVIEW = "MANUAL_REVIEW"


@dataclass(frozen=True, slots=True)
class SefazResponseDecision:
    action: SefazAction
    operator_message: str
    allows_resend: bool = False


class SefazResponsePolicy:
    """Política fail-closed para respostas de autorização NF-e/NFC-e.

    A SEFAZ pode acrescentar códigos sem atualização do aplicativo. Por isso a
    ausência no catálogo nunca autoriza retransmissão: códigos desconhecidos
    exigem análise/consulta oficial.
    """

    AUTHORIZED = frozenset({"100", "150"})
    TEMPORARY = frozenset({"108", "109"})
    QUERY_FIRST = frozenset({"105", "204", "539"})
    SAFE_CORRECTIONS = frozenset({"217", "297", "719"})
    DENIED = frozenset({"110", "301", "302", "303"})

    @classmethod
    def decide(cls, code: str | int | None) -> SefazResponseDecision:
        normalized = "".join(character for character in str(code or "") if character.isdigit())[:3]
        if normalized in cls.AUTHORIZED:
            return SefazResponseDecision(SefazAction.AUTHORIZED, "Documento autorizado.")
        if normalized in cls.TEMPORARY:
            return SefazResponseDecision(
                SefazAction.WAIT_AND_RETRY,
                "Serviço SEFAZ temporariamente indisponível; aguarde antes de tentar novamente.",
                True,
            )
        if normalized in cls.QUERY_FIRST:
            return SefazResponseDecision(
                SefazAction.QUERY_BEFORE_RETRY,
                "Consulte a chave/recibo na SEFAZ antes de qualquer retransmissão.",
            )
        if normalized in cls.SAFE_CORRECTIONS:
            return SefazResponseDecision(
                SefazAction.CORRECT_AND_RETRY,
                "Corrija a rejeição preservando venda, chave e numeração antes de reenviar.",
                True,
            )
        if normalized in cls.DENIED:
            return SefazResponseDecision(
                SefazAction.TERMINAL_DENIAL,
                "Uso denegado: não reenviar, cancelar nem reutilizar esta numeração.",
            )
        return SefazResponseDecision(
            SefazAction.MANUAL_REVIEW,
            "Retorno sem recuperação automática conhecida; consulte a orientação oficial.",
        )
