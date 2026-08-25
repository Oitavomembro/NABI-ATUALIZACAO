from __future__ import annotations

import json
import hashlib
import re
import sqlite3
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from typing import Any, Callable, Mapping, Sequence

from services.fiscal_service import FiscalService


@dataclass(frozen=True)
class CompanyActivity:
    cnae: str
    description: str = ""
    primary: bool = False


@dataclass(frozen=True)
class CompanyProfileDraft:
    cnpj: str
    legal_name: str
    tax_regime: str
    business_classification: str
    activities: tuple[CompanyActivity, ...]
    state: str
    city: str
    state_registration: str = ""
    municipal_registration: str = ""
    operation_types: tuple[str, ...] = ()
    document_types: tuple[str, ...] = ()
    effective_from: str = ""
    source: str = ""
    source_date: str = ""
    confirmed: bool = False


@dataclass(frozen=True)
class CompanyProfileVersion:
    version: int
    cnpj: str
    legal_name: str
    tax_regime: str
    business_classification: str
    activities: tuple[CompanyActivity, ...]
    state: str
    city: str
    state_registration: str
    municipal_registration: str
    operation_types: tuple[str, ...]
    document_types: tuple[str, ...]
    effective_from: str
    effective_to: str
    source: str
    source_date: str
    confirmed_at: str
    confirmed_by: str
    change_reason: str
    supersedes_version: int | None
    previous_hash: str
    record_hash: str


@dataclass(frozen=True)
class CompanyProfileReadiness:
    status: str
    reference_date: str
    active_version: int | None
    missing_fields: tuple[str, ...]
    notices: tuple[str, ...]
    informational_only: bool = True
    enables_fiscal: bool = False


class CompanyProfileService:
    """Perfil empresarial confirmado, separado de licença, Fiscal e autorização."""

    CONFIG_KEY = "company_profile_history_v1"
    FORMAT_VERSION = 1
    TAX_REGIMES = {"MEI", "SIMPLES_NACIONAL", "LUCRO_PRESUMIDO", "LUCRO_REAL", "OUTRO"}
    CLASSIFICATIONS = {"MEI", "ME", "EPP", "OUTRO"}
    STATES = {
        "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
        "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
        "SP", "SE", "TO",
    }

    def __init__(
        self, connection_factory: Callable[[], sqlite3.Connection], *, security_service: Any,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.connection_factory = connection_factory
        self.security_service = security_service
        self.clock = clock or datetime.now

    def history(self) -> tuple[CompanyProfileVersion, ...]:
        self._require("view")
        state = self._load()
        return tuple(self._from_dict(row) for row in state["versions"])

    def active(self, *, on_date: str | date | None = None) -> CompanyProfileVersion | None:
        self._require("view")
        reference = self._date(on_date or self.clock().date(), "data de referência")
        candidates = [
            version for version in self.history()
            if self._date(version.effective_from, "vigência inicial") <= reference
            and (not version.effective_to or reference <= self._date(version.effective_to, "vigência final"))
        ]
        return candidates[-1] if candidates else None

    def confirm(
        self, draft: CompanyProfileDraft, *, change_reason: str,
        expected_current_version: int | None = None,
    ) -> CompanyProfileVersion:
        actor = self._require("edit")
        normalized = self._validate_draft(draft)
        reason = str(change_reason or "").strip()
        if len(reason) < 10:
            raise ValueError("Informe o motivo da confirmação ou mudança com ao menos 10 caracteres.")
        now = self.clock()
        effective = self._date(normalized.effective_from or now.date(), "vigência inicial")
        source_date = self._date(normalized.source_date, "data da fonte")
        if source_date > now.date():
            raise ValueError("A data da fonte não pode estar no futuro.")
        connection = self.connection_factory()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self._require_storage(connection)
            state = self._load_connection(connection)
            versions = list(state["versions"])
            current_number = int(versions[-1]["version"]) if versions else 0
            if expected_current_version is not None and int(expected_current_version) != current_number:
                raise RuntimeError("O perfil empresarial mudou desde a revisão; carregue novamente.")
            if versions:
                latest_start = self._date(versions[-1]["effective_from"], "vigência anterior")
                if effective <= latest_start:
                    raise ValueError("A nova vigência deve ser posterior à versão mais recente.")
                versions[-1] = {**versions[-1], "effective_to": (effective - timedelta(days=1)).isoformat()}
                versions[-1]["record_hash"] = self._record_hash(versions[-1])
            version_data = dict(
                version=current_number + 1, **self._draft_fields(normalized),
                effective_from=effective.isoformat(), effective_to="",
                source_date=source_date.isoformat(), confirmed_at=now.isoformat(timespec="seconds"),
                confirmed_by=actor, change_reason=reason,
                supersedes_version=current_number or None,
                previous_hash=str(versions[-1].get("record_hash") or "") if versions else "",
                record_hash="",
            )
            version_data["record_hash"] = self._record_hash(version_data)
            version = CompanyProfileVersion(**version_data)
            versions.append(self._to_dict(version))
            self._save_connection(connection, {"format": self.FORMAT_VERSION, "versions": versions})
            self._audit(connection, actor, "CONFIRMAR_PERFIL_EMPRESARIAL", version.version,
                        f"cnpj={version.cnpj}; vigencia={version.effective_from}; fonte={version.source}; motivo={reason}")
            connection.commit()
            return version
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def rollback_to(
        self, version: int, *, effective_from: str, reason: str,
        expected_current_version: int | None = None,
    ) -> CompanyProfileVersion:
        self._require("edit")
        versions = tuple(self._from_dict(row) for row in self._load()["versions"])
        target = next((item for item in versions if item.version == int(version)), None)
        if target is None:
            raise ValueError("Versão empresarial não encontrada.")
        draft = CompanyProfileDraft(
            cnpj=target.cnpj, legal_name=target.legal_name, tax_regime=target.tax_regime,
            business_classification=target.business_classification, activities=target.activities,
            state=target.state, city=target.city, state_registration=target.state_registration,
            municipal_registration=target.municipal_registration,
            operation_types=target.operation_types, document_types=target.document_types,
            effective_from=effective_from, source=f"ROLLBACK_DA_VERSAO_{target.version}",
            source_date=self.clock().date().isoformat(), confirmed=True,
        )
        return self.confirm(
            draft, change_reason=f"Rollback auditável: {str(reason or '').strip()}",
            expected_current_version=expected_current_version,
        )

    def readiness(self, *, on_date: str | date | None = None) -> CompanyProfileReadiness:
        self._require("view")
        reference = self._date(on_date or self.clock().date(), "data de referência")
        state = self._load()
        versions = tuple(self._from_dict(row) for row in state["versions"])
        active = next((row for row in reversed(versions)
                       if self._date(row.effective_from, "vigência") <= reference
                       and (not row.effective_to or reference <= self._date(row.effective_to, "vigência"))), None)
        if active is None:
            future = next((row for row in versions if self._date(row.effective_from, "vigência") > reference), None)
            return CompanyProfileReadiness(
                "AGENDADO" if future else "INCOMPLETO", reference.isoformat(), None,
                ("perfil_confirmado_vigente",),
                ((f"Versão {future.version} terá vigência em {future.effective_from}." if future else "Nenhum perfil confirmado vigente."),),
            )
        missing = tuple(name for name, value in {
            "cnpj": active.cnpj, "razao_social": active.legal_name, "regime": active.tax_regime,
            "enquadramento": active.business_classification, "uf": active.state,
            "municipio": active.city, "inscricao_estadual": active.state_registration,
            "inscricao_municipal": active.municipal_registration, "cnaes": active.activities,
            "tipos_operacao": active.operation_types, "tipos_documento": active.document_types,
        }.items() if not value)
        notices = [
            "Resultado informativo; não habilita Fiscal/SEFAZ nem define obrigação tributária.",
            "Obrigações devem ser confirmadas por fonte competente e profissional responsável.",
        ]
        return CompanyProfileReadiness(
            "INCOMPLETO" if missing else "PRONTO_INFORMATIVO", reference.isoformat(),
            active.version, missing, tuple(notices),
        )

    def prepare_legacy_migration(self) -> CompanyProfileDraft:
        """Converte configuração antiga em rascunho; nunca confirma ou persiste."""
        self._require("view")
        connection = self.connection_factory()
        try:
            fiscal = self._configuration(connection, "fiscal.config.v1")
            issuer = fiscal.get("issuer") if isinstance(fiscal.get("issuer"), dict) else {}
            basic = {key: self._raw_configuration(connection, key) for key in ("cnpj", "nome_loja")}
        finally:
            connection.close()
        regime = str(fiscal.get("tax_regime") or "OUTRO").upper()
        classification = "MEI" if regime == "MEI" else "OUTRO"
        return CompanyProfileDraft(
            cnpj=str(fiscal.get("cnpj") or basic["cnpj"] or ""),
            legal_name=str(issuer.get("name") or basic["nome_loja"] or ""),
            tax_regime=regime if regime in self.TAX_REGIMES else "OUTRO",
            business_classification=classification, activities=(),
            state=str(fiscal.get("state") or ""), city=str(issuer.get("city") or ""),
            state_registration=str(issuer.get("state_registration") or ""),
            municipal_registration=str(issuer.get("municipal_registration") or ""),
            operation_types=(), document_types=tuple(str(item) for item in fiscal.get("enabled_models") or ()),
            effective_from="", source="CONFIGURACAO_LEGADA_NABICODE",
            source_date=self.clock().date().isoformat(), confirmed=False,
        )

    def _require(self, action: str) -> str:
        if not self.security_service.require("configs", action):
            raise PermissionError("Sessão ativa com permissão de configuração empresarial é obrigatória.")
        session = self.security_service.session
        if session is None or not str(session.user.username or "").strip():
            raise PermissionError("A sessão não forneceu um ator confiável.")
        return str(session.user.username)

    @classmethod
    def _validate_draft(cls, draft: CompanyProfileDraft) -> CompanyProfileDraft:
        if not isinstance(draft, CompanyProfileDraft) or not draft.confirmed:
            raise ValueError("O perfil precisa de confirmação explícita.")
        cnpj = re.sub(r"\D", "", draft.cnpj)
        if not FiscalService._is_valid_cnpj(cnpj):
            raise ValueError("CNPJ empresarial inválido.")
        legal_name = str(draft.legal_name or "").strip()
        if not legal_name:
            raise ValueError("Informe a razão social confirmada.")
        regime = str(draft.tax_regime or "").strip().upper()
        classification = str(draft.business_classification or "").strip().upper()
        if regime not in cls.TAX_REGIMES or classification not in cls.CLASSIFICATIONS:
            raise ValueError("Regime ou enquadramento empresarial inválido.")
        state = str(draft.state or "").strip().upper()
        city = str(draft.city or "").strip()
        if state not in cls.STATES or not city:
            raise ValueError("Informe UF e município válidos.")
        source = str(draft.source or "").strip()
        if not source or not draft.source_date:
            raise ValueError("Informe a fonte e sua data; o sistema não pode inferi-las.")
        activities = []
        seen = set()
        for activity in draft.activities:
            cnae = re.sub(r"\D", "", activity.cnae)
            if len(cnae) != 7 or cnae in seen:
                raise ValueError("CNAE deve possuir sete dígitos e não pode se repetir.")
            seen.add(cnae)
            activities.append(CompanyActivity(cnae, str(activity.description or "").strip(), bool(activity.primary)))
        return CompanyProfileDraft(
            cnpj, legal_name, regime, classification, tuple(activities), state, city,
            cls._registration(draft.state_registration),
            cls._registration(draft.municipal_registration),
            cls._tokens(draft.operation_types), cls._tokens(draft.document_types),
            str(draft.effective_from or ""), source, str(draft.source_date), True,
        )

    @staticmethod
    def _tokens(values: Sequence[str]) -> tuple[str, ...]:
        normalized = tuple(dict.fromkeys(str(value or "").strip().upper() for value in values if str(value or "").strip()))
        if any(not re.fullmatch(r"[A-Z0-9_./-]{1,40}", value) for value in normalized):
            raise ValueError("Tipo de operação ou documento inválido.")
        return normalized

    @staticmethod
    def _registration(value: str) -> str:
        normalized = re.sub(r"[^A-Z0-9./-]", "", str(value or "").strip().upper())
        if len(normalized) > 30:
            raise ValueError("Inscrição empresarial excede o limite permitido.")
        return normalized

    @staticmethod
    def _draft_fields(draft: CompanyProfileDraft) -> dict[str, Any]:
        data = asdict(draft)
        data.pop("effective_from", None); data.pop("source_date", None); data.pop("confirmed", None)
        data["activities"] = tuple(draft.activities)
        return data

    @staticmethod
    def _to_dict(version: CompanyProfileVersion) -> dict[str, Any]:
        data = asdict(version)
        data["activities"] = [asdict(item) for item in version.activities]
        data["operation_types"] = list(version.operation_types)
        data["document_types"] = list(version.document_types)
        return data

    @staticmethod
    def _from_dict(data: Mapping[str, Any]) -> CompanyProfileVersion:
        return CompanyProfileVersion(
            **{key: value for key, value in data.items() if key not in {"activities", "operation_types", "document_types"}},
            activities=tuple(CompanyActivity(**item) for item in data.get("activities") or ()),
            operation_types=tuple(data.get("operation_types") or ()),
            document_types=tuple(data.get("document_types") or ()),
        )

    def _load(self) -> dict[str, Any]:
        connection = self.connection_factory()
        try:
            return self._load_connection(connection)
        finally:
            connection.close()

    def _load_connection(self, connection: sqlite3.Connection) -> dict[str, Any]:
        self._require_config_table(connection)
        row = connection.execute("SELECT valor FROM configuracoes WHERE chave=?", (self.CONFIG_KEY,)).fetchone()
        if not row:
            return {"format": self.FORMAT_VERSION, "versions": []}
        try:
            state = json.loads(row[0])
        except (TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Histórico empresarial corrompido; alteração bloqueada.") from exc
        if state.get("format") != self.FORMAT_VERSION or not isinstance(state.get("versions"), list):
            raise RuntimeError("Formato do histórico empresarial inválido; alteração bloqueada.")
        # Reabre cada DTO para falhar fechado diante de adulteração estrutural.
        previous_hash = ""
        for expected_version, raw in enumerate(state["versions"], 1):
            version = self._from_dict(raw)
            if (
                version.version != expected_version
                or version.previous_hash != previous_hash
                or version.record_hash != self._record_hash(raw)
                or version.supersedes_version != (expected_version - 1 or None)
            ):
                raise RuntimeError("Cadeia do histórico empresarial inconsistente; alteração bloqueada.")
            previous_hash = version.record_hash
        return state

    def _save_connection(self, connection: sqlite3.Connection, state: Mapping[str, Any]) -> None:
        connection.execute(
            "INSERT INTO configuracoes(chave,valor) VALUES(?,?) "
            "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor",
            (self.CONFIG_KEY, json.dumps(state, ensure_ascii=False, sort_keys=True)),
        )

    @staticmethod
    def _require_config_table(connection: sqlite3.Connection) -> None:
        if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='configuracoes'").fetchone() is None:
            raise RuntimeError("Armazenamento de configuração indisponível.")

    def _require_storage(self, connection: sqlite3.Connection) -> None:
        self._require_config_table(connection)
        if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='auditoria'").fetchone() is None:
            raise RuntimeError("Auditoria indisponível; alteração empresarial bloqueada.")

    @staticmethod
    def _audit(connection: sqlite3.Connection, actor: str, action: str, version: int, details: str) -> None:
        connection.execute(
            "INSERT INTO auditoria(data,usuario,modulo,acao,objeto,detalhes,resultado) VALUES(?,?,?,?,?,?,?)",
            (datetime.now().strftime("%d/%m/%Y %H:%M:%S"), actor, "PERFIL_EMPRESARIAL", action,
             str(version), details, "SUCESSO"),
        )

    @staticmethod
    def _raw_configuration(connection: sqlite3.Connection, key: str) -> str:
        row = connection.execute("SELECT valor FROM configuracoes WHERE chave=?", (key,)).fetchone()
        return str(row[0] or "") if row else ""

    @classmethod
    def _configuration(cls, connection: sqlite3.Connection, key: str) -> dict[str, Any]:
        raw = cls._raw_configuration(connection, key)
        try:
            value = json.loads(raw or "{}")
        except (TypeError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _date(value: str | date, field: str) -> date:
        if isinstance(value, date):
            return value
        try:
            return date.fromisoformat(str(value))
        except ValueError as exc:
            raise ValueError(f"{field.capitalize()} inválida; use AAAA-MM-DD.") from exc

    @staticmethod
    def _record_hash(data: Mapping[str, Any]) -> str:
        canonical = {str(key): value for key, value in data.items() if key != "record_hash"}
        return hashlib.sha256(
            json.dumps(
                canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                default=lambda value: asdict(value),
            ).encode("utf-8")
        ).hexdigest()
