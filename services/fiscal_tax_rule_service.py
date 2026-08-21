from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping


@dataclass(frozen=True)
class FiscalTaxRule:
    id: int
    name: str
    issuer_state: str
    destination_state: str
    tax_regime: str
    ncm_prefix: str
    cest: str
    operation_kind: str
    icms_code: str
    icms_rate: str
    icms_base_reduction: str
    sn_credit_rate: str
    st_mva: str
    st_rate: str
    fcp_st_rate: str
    difal_internal_rate: str
    difal_interstate_rate: str
    difal_fcp_rate: str
    benefit_code: str
    approved_by: str
    approved_at: str


class FiscalTaxRuleService:
    """Matriz explícita: nunca deduz tributação apenas por NCM ou UF."""

    VALID_REGIMES = {"SIMPLES_NACIONAL", "LUCRO_PRESUMIDO", "LUCRO_REAL", "MEI"}
    VALID_ICMS_CODES = {
        "00", "40", "41", "50", "60",
        "102", "103", "201", "202", "203", "300", "400", "500",
    }
    VALID_OPERATION_KINDS = {"VENDA"}

    def __init__(self, connection_factory) -> None:
        self.connection_factory = connection_factory

    @classmethod
    def normalize(cls, values: Mapping[str, Any]) -> dict[str, Any]:
        digits = lambda value: "".join(ch for ch in str(value or "") if ch.isdigit())
        normalized = {
            "name": str(values.get("name") or "").strip(),
            "active": bool(values.get("active", True)),
            "issuer_state": str(values.get("issuer_state") or "BA").strip().upper(),
            "destination_state": str(values.get("destination_state") or "*").strip().upper(),
            "tax_regime": str(values.get("tax_regime") or "").strip().upper(),
            "ncm_prefix": digits(values.get("ncm_prefix")),
            "cest": digits(values.get("cest")),
            "operation_kind": str(values.get("operation_kind") or "VENDA").strip().upper(),
            "icms_code": digits(values.get("icms_code")),
            "benefit_code": str(values.get("benefit_code") or "").strip().upper(),
            "approved_by": str(values.get("approved_by") or "").strip(),
            "approved_at": str(values.get("approved_at") or "").strip(),
        }
        for field in (
            "icms_rate", "icms_base_reduction", "sn_credit_rate", "st_mva", "st_rate", "fcp_st_rate",
            "difal_internal_rate", "difal_interstate_rate", "difal_fcp_rate",
        ):
            try:
                rate = Decimal(str(values.get(field) or "0").replace(",", "."))
            except InvalidOperation as exc:
                raise ValueError(f"{field} deve ser numérico.") from exc
            if rate < 0 or rate > 100:
                raise ValueError(f"{field} deve ficar entre 0 e 100%.")
            normalized[field] = format(rate.normalize(), "f")
        if not normalized["name"]:
            raise ValueError("Informe um nome para a regra fiscal.")
        if normalized["issuer_state"] != "BA":
            raise ValueError("Esta versão aceita regras de emitente somente para a Bahia.")
        if normalized["tax_regime"] not in cls.VALID_REGIMES:
            raise ValueError("Regime tributário inválido para a regra fiscal.")
        if normalized["operation_kind"] not in cls.VALID_OPERATION_KINDS:
            raise ValueError("Esta versão aceita somente regras tributárias de venda.")
        if not 2 <= len(normalized["ncm_prefix"]) <= 8:
            raise ValueError("Informe um prefixo NCM entre 2 e 8 dígitos.")
        if normalized["cest"] and len(normalized["cest"]) != 7:
            raise ValueError("CEST da regra deve possuir 7 dígitos.")
        if normalized["icms_code"] not in cls.VALID_ICMS_CODES:
            raise ValueError("CST/CSOSN não suportado pela matriz fiscal.")
        benefit_code = normalized["benefit_code"]
        if benefit_code and benefit_code != "SEM CBENEF":
            if len(benefit_code) not in {8, 10} or any(
                character.isspace() or not 33 <= ord(character) <= 255
                for character in benefit_code
            ):
                raise ValueError(
                    "Código de benefício fiscal deve possuir 8 ou 10 caracteres sem espaços."
                )
        if not normalized["approved_by"] or not normalized["approved_at"]:
            raise ValueError("A regra exige responsável e data de aprovação contábil.")
        uses_st = normalized["icms_code"] in {"201", "202", "203"}
        if uses_st and not normalized["cest"]:
            raise ValueError("Regra com ICMS-ST exige CEST explícito.")
        return normalized

    def save(self, values: Mapping[str, Any], *, rule_id: int | None = None) -> FiscalTaxRule:
        data = self.normalize(values)
        now = datetime.now().astimezone().isoformat()
        connection = self.connection_factory()
        try:
            columns = tuple(data)
            if rule_id is None:
                cursor = connection.execute(
                    f"INSERT INTO fiscal_tax_rules ({','.join(columns)},created_at,updated_at) "
                    f"VALUES ({','.join('?' for _ in columns)},?,?)",
                    tuple(data[column] for column in columns) + (now, now),
                )
                rule_id = int(cursor.lastrowid)
            else:
                connection.execute(
                    f"UPDATE fiscal_tax_rules SET {','.join(f'{column}=?' for column in columns)},updated_at=? WHERE id=?",
                    tuple(data[column] for column in columns) + (now, int(rule_id)),
                )
            connection.commit()
            return self.get(int(rule_id), connection=connection)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get(self, rule_id: int, *, connection=None) -> FiscalTaxRule:
        own = connection is None
        connection = connection or self.connection_factory()
        try:
            cursor = connection.execute(
                "SELECT id,name,issuer_state,destination_state,tax_regime,ncm_prefix,cest,operation_kind,"
                "icms_code,icms_rate,icms_base_reduction,sn_credit_rate,st_mva,st_rate,fcp_st_rate,"
                "difal_internal_rate,difal_interstate_rate,difal_fcp_rate,benefit_code,approved_by,approved_at "
                "FROM fiscal_tax_rules WHERE id=?", (int(rule_id),),
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError("Regra fiscal não encontrada.")
            return FiscalTaxRule(*row)
        finally:
            if own:
                connection.close()

    def resolve(
        self, *, tax_regime: str, ncm: str, cest: str = "",
        destination_state: str, operation_kind: str = "VENDA",
    ) -> FiscalTaxRule | None:
        regime = str(tax_regime or "").strip().upper()
        ncm_digits = "".join(ch for ch in str(ncm or "") if ch.isdigit())
        cest_digits = "".join(ch for ch in str(cest or "") if ch.isdigit())
        destination = str(destination_state or "").strip().upper()
        operation = str(operation_kind or "").strip().upper()
        if operation not in self.VALID_OPERATION_KINDS:
            return None
        connection = self.connection_factory()
        try:
            cursor = connection.execute(
                "SELECT id,name,issuer_state,destination_state,tax_regime,ncm_prefix,cest,operation_kind,"
                "icms_code,icms_rate,icms_base_reduction,sn_credit_rate,st_mva,st_rate,fcp_st_rate,"
                "difal_internal_rate,difal_interstate_rate,difal_fcp_rate,benefit_code,approved_by,approved_at "
                "FROM fiscal_tax_rules WHERE active=1 AND issuer_state='BA' AND tax_regime=? AND operation_kind=? "
                "AND destination_state IN (?, '*') ORDER BY LENGTH(ncm_prefix) DESC, "
                "CASE WHEN destination_state=? THEN 0 ELSE 1 END, id DESC",
                (regime, operation, destination, destination),
            )
            for row in cursor.fetchall():
                rule = FiscalTaxRule(*row)
                if ncm_digits.startswith(rule.ncm_prefix) and (not rule.cest or rule.cest == cest_digits):
                    return rule
            return None
        finally:
            connection.close()

    def list_rules(self, *, include_inactive: bool = False) -> list[FiscalTaxRule]:
        connection = self.connection_factory()
        try:
            where = "" if include_inactive else " WHERE active=1"
            cursor = connection.execute(
                "SELECT id,name,issuer_state,destination_state,tax_regime,ncm_prefix,cest,operation_kind,"
                "icms_code,icms_rate,icms_base_reduction,sn_credit_rate,st_mva,st_rate,fcp_st_rate,"
                "difal_internal_rate,difal_interstate_rate,difal_fcp_rate,benefit_code,approved_by,approved_at "
                f"FROM fiscal_tax_rules{where} ORDER BY active DESC,name,id"
            )
            return [FiscalTaxRule(*row) for row in cursor.fetchall()]
        finally:
            connection.close()

    def deactivate(self, rule_id: int) -> None:
        connection = self.connection_factory()
        try:
            cursor = connection.execute(
                "UPDATE fiscal_tax_rules SET active=0,updated_at=? WHERE id=? AND active=1",
                (datetime.now().astimezone().isoformat(), int(rule_id)),
            )
            if cursor.rowcount != 1:
                raise ValueError("Regra fiscal ativa não encontrada.")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def as_dict(rule: FiscalTaxRule) -> dict[str, Any]:
        return asdict(rule)
