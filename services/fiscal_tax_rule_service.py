from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
from typing import Any, Callable, Mapping


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
    """Matriz explícita com histórico técnico local, sem não repúdio jurídico."""

    VALID_REGIMES = {"SIMPLES_NACIONAL", "LUCRO_PRESUMIDO", "LUCRO_REAL", "MEI"}
    VALID_ICMS_CODES = {
        "00", "40", "41", "50", "60",
        "102", "103", "201", "202", "203", "300", "400", "500",
    }
    VALID_OPERATION_KINDS = {"VENDA"}

    def __init__(
        self,
        connection_factory,
        *,
        actor_provider: Callable[[], str | None] | None = None,
    ) -> None:
        self.connection_factory = connection_factory
        self._actor_provider = actor_provider

    def _authenticated_actor(self) -> str:
        if self._actor_provider is None:
            raise PermissionError(
                "Uma sessão autenticada é obrigatória para alterar regras fiscais."
            )
        try:
            actor = str(self._actor_provider() or "").strip()
        except PermissionError:
            raise
        except Exception as exc:
            raise PermissionError(
                "Não foi possível confirmar a sessão autenticada para a operação fiscal."
            ) from exc
        if not actor:
            raise PermissionError(
                "Uma sessão autenticada é obrigatória para alterar regras fiscais."
            )
        return actor

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

    REVISION_PAYLOAD_COLUMNS = (
        "id", "name", "active", "issuer_state", "destination_state", "tax_regime",
        "ncm_prefix", "cest", "operation_kind", "icms_code", "icms_rate",
        "icms_base_reduction", "sn_credit_rate", "st_mva", "st_rate", "fcp_st_rate",
        "difal_internal_rate", "difal_interstate_rate", "difal_fcp_rate",
        "benefit_code", "approved_by", "approved_at", "created_at", "updated_at",
    )

    @staticmethod
    def revision_hash(
        *, rule_id: int, revision_number: int, event_kind: str, payload_json: str,
        previous_hash: str, actor: str, change_reason: str, recorded_at: str,
    ) -> str:
        envelope = {
            "actor": actor, "change_reason": change_reason, "event_kind": event_kind,
            "payload_json": payload_json, "previous_hash": previous_hash,
            "recorded_at": recorded_at, "revision_number": int(revision_number),
            "rule_id": int(rule_id),
        }
        canonical = json.dumps(
            envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest().upper()

    def save(
        self, values: Mapping[str, Any], *, rule_id: int | None = None,
        change_reason: str = "",
    ) -> FiscalTaxRule:
        actor = self._authenticated_actor()
        data = self.normalize(values)
        now = datetime.now().astimezone().isoformat()
        connection = self.connection_factory()
        try:
            connection.execute("BEGIN IMMEDIATE")
            is_create = rule_id is None
            if data["active"]:
                self._reject_active_conflict(
                    connection, data, exclude_rule_id=rule_id
                )
            columns = tuple(data)
            if rule_id is None:
                cursor = connection.execute(
                    f"INSERT INTO fiscal_tax_rules ({','.join(columns)},created_at,updated_at) "
                    f"VALUES ({','.join('?' for _ in columns)},?,?)",
                    tuple(data[column] for column in columns) + (now, now),
                )
                rule_id = int(cursor.lastrowid)
            else:
                cursor = connection.execute(
                    f"UPDATE fiscal_tax_rules SET {','.join(f'{column}=?' for column in columns)},updated_at=? WHERE id=?",
                    tuple(data[column] for column in columns) + (now, int(rule_id)),
                )
                if cursor.rowcount != 1:
                    raise ValueError("Regra fiscal não encontrada.")
            self._append_revision(
                connection, int(rule_id),
                event_kind="CREATED" if is_create else "UPDATED",
                actor=actor, change_reason=change_reason, recorded_at=now,
            )
            connection.commit()
            return self.get(int(rule_id), connection=connection)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _append_revision(
        self, connection, rule_id: int, *, event_kind: str, actor: str,
        change_reason: str, recorded_at: str,
    ) -> None:
        row = connection.execute(
            f"SELECT {','.join(self.REVISION_PAYLOAD_COLUMNS)} FROM fiscal_tax_rules WHERE id=?",
            (rule_id,),
        ).fetchone()
        if row is None:
            raise ValueError("Regra fiscal não encontrada para registrar revisão.")
        payload = dict(zip(self.REVISION_PAYLOAD_COLUMNS, row))
        payload["active"] = bool(payload["active"])
        payload_json = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        previous = connection.execute(
            "SELECT revision_number,current_hash FROM fiscal_tax_rule_revisions "
            "WHERE rule_id=? ORDER BY revision_number DESC LIMIT 1", (rule_id,),
        ).fetchone()
        revision_number = int(previous[0]) + 1 if previous else 1
        previous_hash = str(previous[1]) if previous else ""
        normalized_actor = str(actor or "").strip() or "NAO_INFORMADO"
        normalized_reason = str(change_reason or "").strip()
        current_hash = self.revision_hash(
            rule_id=rule_id, revision_number=revision_number, event_kind=event_kind,
            payload_json=payload_json, previous_hash=previous_hash,
            actor=normalized_actor, change_reason=normalized_reason, recorded_at=recorded_at,
        )
        connection.execute(
            "INSERT INTO fiscal_tax_rule_revisions "
            "(rule_id,revision_number,event_kind,payload_json,previous_hash,current_hash,actor,change_reason,recorded_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (rule_id, revision_number, event_kind, payload_json, previous_hash,
             current_hash, normalized_actor, normalized_reason, recorded_at),
        )

    @staticmethod
    def _cest_scopes_overlap(first: str, second: str) -> bool:
        return not first or not second or first == second

    def _reject_active_conflict(
        self,
        connection,
        data: Mapping[str, Any],
        *,
        exclude_rule_id: int | None = None,
    ) -> None:
        parameters: list[Any] = [
            data["issuer_state"], data["destination_state"], data["tax_regime"],
            data["ncm_prefix"], data["operation_kind"],
        ]
        exclusion = ""
        if exclude_rule_id is not None:
            exclusion = " AND id!=?"
            parameters.append(int(exclude_rule_id))
        rows = connection.execute(
            "SELECT id,cest FROM fiscal_tax_rules WHERE active=1 "
            "AND issuer_state=? AND destination_state=? AND tax_regime=? "
            "AND ncm_prefix=? AND operation_kind=?" + exclusion,
            tuple(parameters),
        ).fetchall()
        conflicting_ids = sorted(
            int(row[0]) for row in rows
            if self._cest_scopes_overlap(str(data["cest"]), str(row[1] or ""))
        )
        if conflicting_ids:
            identifiers = ", ".join(str(identifier) for identifier in conflicting_ids)
            raise ValueError(
                "Conflito auditável na matriz fiscal: regra ativa de mesma precedência "
                f"já existe para este escopo (IDs: {identifiers}). Desative a regra "
                "anterior ou torne o escopo inequívoco."
            )

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
                "CASE WHEN destination_state=? THEN 0 ELSE 1 END, id",
                (regime, operation, destination, destination),
            )
            matches: list[tuple[tuple[int, int], FiscalTaxRule]] = []
            for row in cursor.fetchall():
                rule = FiscalTaxRule(*row)
                if ncm_digits.startswith(rule.ncm_prefix) and (not rule.cest or rule.cest == cest_digits):
                    precedence = (
                        len(rule.ncm_prefix),
                        1 if rule.destination_state == destination else 0,
                    )
                    matches.append((precedence, rule))
            if not matches:
                return None
            best_precedence = max(precedence for precedence, _rule in matches)
            best_rules = [rule for precedence, rule in matches if precedence == best_precedence]
            if len(best_rules) > 1:
                identifiers = ", ".join(str(rule.id) for rule in sorted(best_rules, key=lambda item: item.id))
                raise ValueError(
                    "Conflito auditável na matriz fiscal: múltiplas regras ativas de "
                    f"mesma precedência são aplicáveis (IDs: {identifiers})."
                )
            return best_rules[0]
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

    def deactivate(
        self, rule_id: int, *, change_reason: str = ""
    ) -> None:
        actor = self._authenticated_actor()
        connection = self.connection_factory()
        try:
            connection.execute("BEGIN IMMEDIATE")
            now = datetime.now().astimezone().isoformat()
            cursor = connection.execute(
                "UPDATE fiscal_tax_rules SET active=0,updated_at=? WHERE id=? AND active=1",
                (now, int(rule_id)),
            )
            if cursor.rowcount != 1:
                raise ValueError("Regra fiscal ativa não encontrada.")
            self._append_revision(
                connection, int(rule_id), event_kind="DEACTIVATED", actor=actor,
                change_reason=change_reason, recorded_at=now,
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def as_dict(rule: FiscalTaxRule) -> dict[str, Any]:
        return asdict(rule)

    def list_revisions(self, rule_id: int) -> list[dict[str, Any]]:
        connection = self.connection_factory()
        try:
            cursor = connection.execute(
                "SELECT id,rule_id,revision_number,event_kind,payload_json,previous_hash,"
                "current_hash,actor,change_reason,recorded_at "
                "FROM fiscal_tax_rule_revisions WHERE rule_id=? ORDER BY revision_number",
                (int(rule_id),),
            )
            columns = [column[0] for column in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        finally:
            connection.close()

    def verify_revision_chain(self, rule_id: int) -> dict[str, Any]:
        revisions = self.list_revisions(rule_id)
        previous_hash = ""
        for expected_number, revision in enumerate(revisions, 1):
            expected_hash = self.revision_hash(
                rule_id=int(revision["rule_id"]), revision_number=expected_number,
                event_kind=str(revision["event_kind"]), payload_json=str(revision["payload_json"]),
                previous_hash=previous_hash, actor=str(revision["actor"]),
                change_reason=str(revision["change_reason"]), recorded_at=str(revision["recorded_at"]),
            )
            if (
                int(revision["revision_number"]) != expected_number
                or str(revision["previous_hash"]) != previous_hash
                or str(revision["current_hash"]) != expected_hash
            ):
                return {"valid": False, "rule_id": int(rule_id), "failed_revision": expected_number}
            previous_hash = expected_hash
        return {"valid": True, "rule_id": int(rule_id), "revision_count": len(revisions)}
