from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class FiscalOnboardingDraft:
    cnpj: str
    state: str
    tax_regime: str
    model: str
    series: int
    issuer: dict[str, Any]
    warnings: tuple[str, ...] = ()


class FiscalOnboardingService:
    """Prepara a configuração a partir de documento próprio, sem persistir dados."""

    CRT_REGIMES = {
        "1": "SIMPLES_NACIONAL",
        "2": "SIMPLES_EXCESSO_SUBLIMITE",
        "4": "MEI",
    }

    def __init__(self, xml_service: Any) -> None:
        self.xml_service = xml_service

    def from_authorized_xml(self, path: str | Path) -> FiscalOnboardingDraft:
        document = self.xml_service.ler(path)
        if document.protocolo_status != "100":
            raise ValueError(
                "Selecione uma NF-e/NFC-e própria autorizada (protocolo cStat 100)."
            )
        if document.modelo not in {"55", "65"}:
            raise ValueError("O XML precisa ser uma NF-e 55 ou NFC-e 65.")
        if len(document.cnpj) != 14:
            raise ValueError("O XML autorizado não contém CNPJ válido do emitente.")
        if not document.fornecedor or not document.emitente_uf:
            raise ValueError("O XML não contém os dados mínimos do emitente.")
        try:
            series = int(document.serie)
        except (TypeError, ValueError) as exc:
            raise ValueError("O XML não contém uma série fiscal válida.") from exc
        if not 0 <= series <= 999:
            raise ValueError("A série fiscal do XML está fora do intervalo permitido.")

        warnings: list[str] = []
        tax_regime = self.CRT_REGIMES.get(document.emitente_crt, "")
        if document.emitente_crt == "3":
            warnings.append(
                "CRT 3 não distingue Lucro Presumido de Lucro Real; confirme o regime com a contabilidade."
            )
        elif not tax_regime:
            warnings.append("O regime tributário não pôde ser definido pelo CRT do XML.")
        return FiscalOnboardingDraft(
            cnpj=document.cnpj,
            state=document.emitente_uf,
            tax_regime=tax_regime,
            model=document.modelo,
            series=series,
            issuer={
                "name": document.fornecedor,
                "trade_name": document.emitente_fantasia,
                "state_registration": document.emitente_ie,
                "city_code": document.emitente_codigo_municipio,
                "city": document.emitente_municipio,
                "street": document.emitente_logradouro,
                "number": document.emitente_numero,
                "district": document.emitente_bairro,
                "zip_code": document.emitente_cep,
            },
            warnings=tuple(warnings),
        )
