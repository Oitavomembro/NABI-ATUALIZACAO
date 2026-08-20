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
    source_role: str = "EMITENTE"
    warnings: tuple[str, ...] = ()


class FiscalOnboardingService:
    """Prepara a configuração a partir de documento próprio, sem persistir dados."""

    CRT_REGIMES = {
        "1": "SIMPLES_NACIONAL",
        "2": "EXCESSO_SUBLIMITE",
        "4": "MEI",
    }

    def __init__(self, xml_service: Any) -> None:
        self.xml_service = xml_service

    @staticmethod
    def _document(value: Any) -> str:
        return "".join(character for character in str(value or "") if character.isdigit())

    def from_authorized_xml(
        self, path: str | Path, *, expected_cnpj: str = ""
    ) -> FiscalOnboardingDraft:
        document = self.xml_service.ler(path)
        if document.protocolo_status != "100":
            raise ValueError(
                "Selecione uma NF-e/NFC-e própria autorizada (protocolo cStat 100)."
            )
        if document.modelo not in {"55", "65"}:
            raise ValueError("O XML precisa ser uma NF-e 55 ou NFC-e 65.")
        expected = self._document(expected_cnpj)
        issuer_document = self._document(document.cnpj)
        recipient_document = self._document(document.destinatario_documento)
        if expected:
            if expected == issuer_document:
                source_role = "EMITENTE"
            elif expected == recipient_document:
                source_role = "DESTINATARIO"
            else:
                raise ValueError(
                    "O CNPJ da empresa não aparece como emitente nem destinatário deste XML."
                )
        elif issuer_document and not recipient_document:
            source_role = "EMITENTE"
            expected = issuer_document
        else:
            raise ValueError(
                "Informe primeiro o CNPJ da sua empresa. Assim o NabiCode distingue uma nota "
                "emitida de uma nota de compra e não copia os dados do fornecedor."
            )

        if len(expected) != 14:
            raise ValueError("O XML autorizado não permite identificar o CNPJ da empresa.")
        try:
            series = int(document.serie)
        except (TypeError, ValueError) as exc:
            raise ValueError("O XML não contém uma série fiscal válida.") from exc
        if not 0 <= series <= 999:
            raise ValueError("A série fiscal do XML está fora do intervalo permitido.")

        warnings: list[str] = []
        tax_regime = ""
        if source_role == "EMITENTE":
            company_name = document.fornecedor
            state = document.emitente_uf
            company_ie = document.emitente_ie
            address = {
                "city_code": document.emitente_codigo_municipio,
                "city": document.emitente_municipio,
                "street": document.emitente_logradouro,
                "number": document.emitente_numero,
                "district": document.emitente_bairro,
                "zip_code": document.emitente_cep,
            }
            tax_regime = self.CRT_REGIMES.get(document.emitente_crt, "")
        else:
            company_name = document.destinatario
            state = document.destinatario_uf
            company_ie = document.destinatario_ie
            address = {
                "city_code": document.destinatario_codigo_municipio,
                "city": document.destinatario_municipio,
                "street": document.destinatario_logradouro,
                "number": document.destinatario_numero,
                "district": document.destinatario_bairro,
                "zip_code": document.destinatario_cep,
            }
            warnings.append(
                "Nota de compra identificada: os dados vieram do destinatário. "
                "Confirme o regime tributário, pois ele não consta na ficha do destinatário."
            )
        if not company_name or not state:
            raise ValueError("O XML não contém nome e UF da sua empresa.")
        if source_role == "EMITENTE" and document.emitente_crt == "3":
            warnings.append(
                "CRT 3 não distingue Lucro Presumido de Lucro Real; confirme o regime com a contabilidade."
            )
        elif source_role == "EMITENTE" and not tax_regime:
            warnings.append("O regime tributário não pôde ser definido pelo CRT do XML.")
        return FiscalOnboardingDraft(
            cnpj=expected,
            state=state,
            tax_regime=tax_regime,
            model=document.modelo,
            series=series,
            issuer={
                "name": company_name,
                "trade_name": document.emitente_fantasia if source_role == "EMITENTE" else "",
                "state_registration": company_ie,
                **address,
            },
            source_role=source_role,
            warnings=tuple(warnings),
        )
