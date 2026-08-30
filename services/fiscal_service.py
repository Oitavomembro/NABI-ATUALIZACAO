from __future__ import annotations

import base64
import binascii
import csv
import hashlib
import json
import os
import re
import ssl
import sys
import tempfile
import uuid
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlsplit

from services.fiscal_state_catalog import FISCAL_STATE_PROFILES, STATE_CODES, state_profile
from services.fiscal_outbox_service import FiscalOutboxService
from services.fiscal_readiness_gate import FiscalReadinessGate
from services.fiscal_product_profile import FiscalProductProfile
from services.fiscal_operation_resolver import FiscalOperationResolver
from services.fiscal_rtc_resolver import FiscalRtcResolver
from services.fiscal_icp_trust_service import (
    FiscalICPTrustService,
    ICPRevocationReport,
    ICPTrustReport,
)
from services.windows_data_protector import WindowsDataProtector

try:
    import requests
except ModuleNotFoundError:  # O módulo fiscal é opcional no uso comum.
    requests = None  # type: ignore[assignment]

try:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.serialization import pkcs12
except ModuleNotFoundError:  # Não deve impedir o uso não fiscal do sistema.
    x509 = hashes = serialization = padding = pkcs12 = None  # type: ignore[assignment]

try:
    from lxml import etree
except ModuleNotFoundError:  # Não deve impedir o uso não fiscal do sistema.
    etree = None  # type: ignore[assignment]

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.graphics import renderPDF
    from reportlab.graphics.barcode import qr
    from reportlab.graphics.shapes import Drawing
except ModuleNotFoundError:  # DANFE é opcional no uso comum.
    A4 = mm = canvas = renderPDF = qr = Drawing = None  # type: ignore[assignment]

try:
    from brazilfiscalreport.danfe import Danfe as OfficialDanfe
except ModuleNotFoundError:  # O DANFE oficial é opcional no uso não fiscal.
    OfficialDanfe = None  # type: ignore[assignment,misc]


@dataclass(frozen=True)
class FiscalCertificateInfo:
    subject: str
    issuer: str
    serial_number: str
    valid_from: str
    valid_until: str
    document: str
    expired: bool
    company_name: str = ""
    expires_in_days: int = 0
    expiring_soon: bool = False


class InvalidCertificatePasswordError(ValueError):
    """Senha incorreta ou conteúdo PKCS#12 que não pôde ser aberto com segurança."""


class FiscalTransmissionUnknownError(RuntimeError):
    """A requisição pode ter chegado à SEFAZ, mas não houve resposta conclusiva."""


@dataclass(frozen=True)
class FiscalResponse:
    success: bool
    status_code: str
    message: str
    protocol: str = ""
    receipt: str = ""
    access_key: str = ""
    raw_xml: str = ""


@dataclass(frozen=True)
class FiscalServiceStatus:
    available: bool
    status_code: str
    message: str
    model: str
    environment: str


class FiscalService:
    """Infraestrutura fiscal opcional sem alterar o schema existente.

    A configuração fica em ``configuracoes``. O certificado e a senha não são
    obrigatórios para o uso geral do sistema e a senha nunca é persistida.
    """

    CONFIG_KEY = "fiscal.config.v1"
    DOCUMENT_INDEX_KEY = "fiscal.documentos.v1"
    EVENT_INDEX_KEY = "fiscal.eventos.v1"
    REJECTION_INDEX_KEY = "fiscal.rejeicoes.v1"
    NUMBERING_KEY = "fiscal.numeracao.v1"
    TRANSMISSION_QUEUE_KEY = "fiscal.fila_transmissao.v1"
    AUTHORIZED_STATUS = {"100", "150"}
    EVENT_ACCEPTED_STATUS = {"128", "135", "136", "155"}
    INUTILIZATION_ACCEPTED_STATUS = {"102"}
    ACCEPTED_STATUS = AUTHORIZED_STATUS | EVENT_ACCEPTED_STATUS | INUTILIZATION_ACCEPTED_STATUS
    VALID_ENVIRONMENTS = {"HOMOLOGACAO", "PRODUCAO"}
    HOMOLOGATION_RECIPIENT_NAME = (
        "NF-E EMITIDA EM AMBIENTE DE HOMOLOGACAO - SEM VALOR FISCAL"
    )
    HOMOLOGATION_RECIPIENT_CNPJ = "99999999000191"
    VALID_MODELS = {"55", "65"}
    VALID_EVENTS = {"CANCELAMENTO", "CCE"}
    STATE_CODES = STATE_CODES
    TAX_REGIME_CODES = {
        "MEI": 4,
        "SIMPLES": 1,
        "SIMPLES_NACIONAL": 1,
        "EXCESSO_SUBLIMITE": 2,
        "LUCRO_PRESUMIDO": 3,
        "LUCRO_REAL": 3,
        "REGIME_NORMAL": 3,
        "NORMAL": 3,
    }
    TAX_REGIME_LABELS = {
        "MEI": "MEI",
        "SIMPLES_NACIONAL": "Simples Nacional",
        "EXCESSO_SUBLIMITE": "Simples Nacional — excesso de sublimite",
        "LUCRO_PRESUMIDO": "Lucro Presumido",
        "LUCRO_REAL": "Lucro Real",
    }
    MODEL_LABELS = {"55": "NF-e — modelo 55", "65": "NFC-e — modelo 65"}
    DS_NS = "http://www.w3.org/2000/09/xmldsig#"

    @staticmethod
    def state_profile(uf: str) -> dict[str, Any]:
        """Retorna o perfil nacional sem liberar UFs ainda não homologadas."""
        return dict(state_profile(uf))

    @staticmethod
    def state_catalog() -> list[dict[str, Any]]:
        return [dict(FISCAL_STATE_PROFILES[uf]) for uf in sorted(FISCAL_STATE_PROFILES)]

    def __init__(
        self,
        connection_factory: Callable[[], Any],
        *,
        storage_dir: str | Path | None = None,
        schema_dir: str | Path | None = None,
        http_post: Callable[..., Any] | None = None,
        secret_protector: Any | None = None,
        actor_provider: Callable[[], str | None] | None = None,
        authorization_provider: Callable[[str], bool] | None = None,
    ) -> None:
        self.connection_factory = connection_factory
        self.storage_dir = Path(storage_dir or (Path.home() / ".nabicode" / "fiscal"))
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        runtime_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
        self.runtime_root = runtime_root
        self.schema_dir = Path(
            schema_dir or runtime_root / "resources" / "fiscal" / "schemas"
        )
        if http_post is not None:
            self.http_post = http_post
        elif requests is not None:
            self.http_post = requests.post
        else:
            self.http_post = None
        self._session_certificate_password: str | None = None
        self.secret_protector = secret_protector or WindowsDataProtector()
        self._actor_provider = actor_provider
        self._authorization_provider = authorization_provider
        self._readiness_gate: FiscalReadinessGate | None = None
        self._readiness_enforced = False
        self._managed_certificate_dir = self.storage_dir / "certificate"
        self._managed_certificate_path = self._managed_certificate_dir / "active.pfx"
        self._managed_secret_path = self._managed_certificate_dir / "active.secret"

    def bind_readiness_catalog(self, catalog_service: Any) -> None:
        """Liga o auditor oficial do catálogo ao mesmo portão fiscal."""
        self._readiness_gate = FiscalReadinessGate(self, catalog_service)
        self._readiness_enforced = True

    def require_operational_readiness(
        self, *, operation: str, model: str, password: str,
        permission: str, series: int | None = None,
        require_catalog: bool = False, require_numbering: bool = False,
        check_revocation: bool = True,
    ) -> str:
        if not self._readiness_enforced or self._readiness_gate is None:
            raise PermissionError(
                "O portão de prontidão fiscal não foi configurado e validado; "
                "nenhuma operação Fiscal/SEFAZ pode ser iniciada."
            )
        actor = self._authenticated_fiscal_actor(
            permission, operation=f"executar {operation} fiscal"
        )
        self._readiness_gate.require(
            operation=operation, model=model, password=password,
            series=series, require_catalog=require_catalog,
            require_numbering=require_numbering,
            check_revocation=check_revocation,
        )
        return actor

    def validate_certificate_trust(
        self, pfx_path: str | Path, password: str
    ) -> ICPTrustReport:
        """Confirma que o A1 termina em uma raiz do catálogo oficial do ITI."""
        return FiscalICPTrustService.from_runtime(self.runtime_root).validate_pkcs12(
            pfx_path, password
        )

    def check_certificate_revocation(
        self, pfx_path: str | Path, password: str
    ) -> ICPRevocationReport:
        """Consulta CRLs oficiais informadas pela própria cadeia do A1."""
        return FiscalICPTrustService.from_runtime(self.runtime_root).check_pkcs12_revocation(
            pfx_path, password
        )

    def cache_certificate_password(self, password: str) -> FiscalCertificateInfo:
        config = self.load_config()
        secret = str(password or "")
        info = self.inspect_certificate(config.get("certificate_path", ""), secret)
        if info.expired:
            raise ValueError("O certificado A1 está fora da validade.")
        self._session_certificate_password = secret
        return info

    def session_certificate_password(self) -> str | None:
        if self._session_certificate_password is None:
            try:
                self._session_certificate_password = self.load_managed_certificate_password()
            except (OSError, RuntimeError, UnicodeError, ValueError):
                return None
        return self._session_certificate_password

    def clear_session_certificate_password(self) -> None:
        self._session_certificate_password = None

    def install_certificate_securely(
        self, pfx_path: str | Path, password: str
    ) -> FiscalCertificateInfo:
        """Valida e instala o A1 sem modificar ou remover o arquivo escolhido."""
        source = Path(pfx_path)
        info = self.inspect_certificate(source, password)
        if info.expired:
            raise ValueError("O certificado A1 está expirado ou ainda não é válido.")
        config = self.load_config()
        configured_cnpj = self._normalize_cnpj(config.get("cnpj"))
        if configured_cnpj and info.document and configured_cnpj != info.document:
            raise ValueError("O CNPJ do certificado não corresponde ao emitente configurado.")
        protected_password = self.secret_protector.protect(str(password).encode("utf-8"))
        self._managed_certificate_dir.mkdir(parents=True, exist_ok=True)
        self._atomic_write_bytes(self._managed_certificate_path, source.read_bytes())
        try:
            self._atomic_write_bytes(self._managed_secret_path, protected_password)
        except Exception:
            self._secure_delete_file(self._managed_certificate_path)
            raise
        config["certificate_path"] = str(self._managed_certificate_path.resolve())
        config["certificate_info"] = asdict(info)
        config["certificate_managed"] = True
        self._set_setting(self.CONFIG_KEY, json.dumps(config, ensure_ascii=False, sort_keys=True))
        self._session_certificate_password = str(password)
        return info

    def load_managed_certificate_password(self) -> str:
        config = self.load_config()
        if not config.get("certificate_managed"):
            raise ValueError("O certificado configurado não está no cofre seguro.")
        configured = Path(str(config.get("certificate_path") or ""))
        if configured.resolve() != self._managed_certificate_path.resolve():
            raise ValueError("O caminho do certificado gerenciado é inconsistente.")
        protected = self._managed_secret_path.read_bytes()
        secret = self.secret_protector.unprotect(protected).decode("utf-8")
        self.inspect_certificate(self._managed_certificate_path, secret)
        return secret

    def remove_managed_certificate(self) -> None:
        config = self.load_config()
        if config.get("certificate_managed"):
            self._secure_delete_file(self._managed_certificate_path)
            self._secure_delete_file(self._managed_secret_path)
        config["certificate_path"] = ""
        config["certificate_info"] = {}
        config["certificate_managed"] = False
        self._set_setting(self.CONFIG_KEY, json.dumps(config, ensure_ascii=False, sort_keys=True))
        self.clear_session_certificate_password()

    @staticmethod
    def _require_dependency(name: str) -> None:
        available = {
            "requests": requests is not None,
            "cryptography": pkcs12 is not None,
            "lxml": etree is not None,
            "reportlab": canvas is not None,
            "brazilfiscalreport": OfficialDanfe is not None,
        }
        if not available.get(name, False):
            raise RuntimeError(
                f"A dependência '{name}' não está disponível. "
                "Execute ATUALIZAR_DEPENDENCIAS.bat e gere novamente o executável."
            )

    def load_config(self) -> dict[str, Any]:
        default = {
            "enabled": False,
            "environment": "HOMOLOGACAO",
            "cnpj": "",
            "state": "BA",
            "tax_regime": "SIMPLES_NACIONAL",
            "enabled_models": ["55", "65"],
            "default_model": "65",
            "sale_series_55": 1,
            "sale_series_65": 1,
            "certificate_path": "",
            "certificate_info": {},
            "certificate_managed": False,
            "issuer": {
                "name": "", "state_registration": "", "city_code": "",
                "city": "", "street": "", "number": "", "district": "",
                "zip_code": "", "municipal_registration": "", "return_series": 1,
            },
            "endpoints": {"HOMOLOGACAO": {}, "PRODUCAO": {}},
        }
        value = self._get_setting(self.CONFIG_KEY)
        if not value:
            return default
        try:
            loaded = json.loads(value)
        except (TypeError, ValueError):
            return default
        if not isinstance(loaded, dict):
            return default
        result = dict(default)
        result.update(loaded)
        result["endpoints"] = dict(default["endpoints"]) | dict(loaded.get("endpoints") or {})
        result["issuer"] = dict(default["issuer"]) | dict(loaded.get("issuer") or {})
        models = [str(model) for model in loaded.get("enabled_models", default["enabled_models"]) if str(model) in self.VALID_MODELS]
        result["enabled_models"] = models or list(default["enabled_models"])
        default_model = str(loaded.get("default_model", default["default_model"]))
        result["default_model"] = default_model if default_model in result["enabled_models"] else result["enabled_models"][0]
        for model in self.VALID_MODELS:
            key = f"sale_series_{model}"
            try:
                series = int(result.get(key, 1))
            except (TypeError, ValueError):
                series = 1
            result[key] = series if 0 <= series <= 999 else 1
        return result

    def save_config(self, config: Mapping[str, Any]) -> dict[str, Any]:
        current = self.load_config()
        environment = str(config.get("environment", current["environment"])).strip().upper()
        if environment not in self.VALID_ENVIRONMENTS:
            raise ValueError("Ambiente fiscal inválido.")
        state = str(config.get("state", current["state"])).strip().upper()
        tax_regime = str(config.get("tax_regime", current["tax_regime"])).strip().upper()
        if state and state not in self.STATE_CODES:
            raise ValueError("UF fiscal inválida.")
        if tax_regime and tax_regime not in self.TAX_REGIME_CODES:
            raise ValueError("Regime tributário fiscal inválido.")
        enabled_models = [str(model) for model in config.get("enabled_models", current.get("enabled_models", ["55", "65"]))]
        enabled_models = list(dict.fromkeys(model for model in enabled_models if model in self.VALID_MODELS))
        if not enabled_models:
            raise ValueError("Selecione NF-e 55, NFC-e 65 ou ambas.")
        default_model = str(config.get("default_model", current.get("default_model", "65")))
        if default_model not in enabled_models:
            raise ValueError("O modelo fiscal padrão precisa estar entre os modelos habilitados.")
        sale_series: dict[str, int] = {}
        for model in self.VALID_MODELS:
            key = f"sale_series_{model}"
            try:
                series = int(config.get(key, current.get(key, 1)) or 0)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Série fiscal do modelo {model} inválida.") from exc
            if series < 0 or series > 999:
                raise ValueError(f"Série fiscal do modelo {model} deve estar entre 0 e 999.")
            sale_series[key] = series
        current.update({
            "enabled": bool(config.get("enabled", current["enabled"])),
            "environment": environment,
            "cnpj": self._normalize_cnpj(config.get("cnpj", current["cnpj"])),
            "state": state,
            "tax_regime": tax_regime,
            "enabled_models": enabled_models,
            "default_model": default_model,
            **sale_series,
            "certificate_path": str(config.get("certificate_path", current["certificate_path"])).strip(),
        })
        if "issuer" in config:
            issuer = dict(current.get("issuer") or {})
            issuer.update({str(k): v for k, v in dict(config.get("issuer") or {}).items()})
            issuer["name"] = str(issuer.get("name") or "").strip()
            issuer["state_registration"] = self._digits(issuer.get("state_registration"))
            issuer["municipal_registration"] = self._digits(issuer.get("municipal_registration"))
            issuer["city_code"] = self._digits(issuer.get("city_code"))
            issuer["zip_code"] = self._digits(issuer.get("zip_code"))
            issuer["city"] = str(issuer.get("city") or "").strip()
            issuer["street"] = str(issuer.get("street") or "").strip()
            issuer["number"] = str(issuer.get("number") or "").strip()
            issuer["district"] = str(issuer.get("district") or "").strip()
            series = int(issuer.get("return_series") or 1)
            if series < 0 or series > 999:
                raise ValueError("Série fiscal de devolução inválida.")
            issuer["return_series"] = series
            current["issuer"] = issuer
        if "endpoints" in config:
            endpoints = config.get("endpoints") or {}
            validated_endpoints: dict[str, dict[str, str]] = {}
            for env in self.VALID_ENVIRONMENTS:
                validated_endpoints[env] = {}
                for operation, value in dict(endpoints.get(env, {})).items():
                    url = str(value).strip()
                    if not url:
                        continue
                    validated_endpoints[env][str(operation)] = self._validate_endpoint_url(url)
            current["endpoints"] = validated_endpoints
        self._set_setting(self.CONFIG_KEY, json.dumps(current, ensure_ascii=False, sort_keys=True))
        return current

    def is_enabled(self) -> bool:
        return bool(self.load_config().get("enabled"))

    def numbering_status(self, *, model: str | None = None, series: int | None = None, environment: str | None = None) -> list[dict[str, Any]]:
        data = self._load_numbering()
        records = list(data.get("records", {}).values())
        result: list[dict[str, Any]] = []
        for record in records:
            if model is not None and str(record.get("model")) != str(model):
                continue
            if series is not None and int(record.get("series", -1)) != int(series):
                continue
            if environment is not None and str(record.get("environment", "")).upper() != str(environment).upper():
                continue
            result.append(dict(record))
        return sorted(result, key=lambda item: (str(item.get("environment")), str(item.get("model")), int(item.get("series", 0)), int(item.get("number", 0))))

    def numbering_scope(
        self, *, model: str, series: int, environment: str | None = None
    ) -> dict[str, Any]:
        model = str(model)
        series = int(series)
        environment = str(
            environment or self.load_config().get("environment") or "HOMOLOGACAO"
        ).upper()
        scope = f"{environment}:{model}:{series}"
        data = self._load_numbering()
        initialized = scope in data.get("scopes", {})
        last_number = int(data.get("scopes", {}).get(scope, 0))
        return {
            "scope": scope, "model": model, "series": series,
            "environment": environment, "initialized": initialized,
            "last_number": last_number, "next_number": last_number + 1,
        }

    def initialize_numbering(
        self, *, model: str, series: int, next_number: int,
        environment: str | None = None,
    ) -> dict[str, Any]:
        actor = self._authenticated_fiscal_actor(
            "configure", operation="configurar a numeração fiscal"
        )
        model = str(model)
        if model not in self.VALID_MODELS:
            raise ValueError("Modelo fiscal deve ser 55 ou 65.")
        series = int(series)
        if not 0 <= series <= 999:
            raise ValueError("Série fiscal deve estar entre 0 e 999.")
        next_number = int(next_number)
        if not 1 <= next_number <= 999_999_999:
            raise ValueError("Próximo número fiscal deve estar entre 1 e 999999999.")
        environment = str(
            environment or self.load_config().get("environment") or "HOMOLOGACAO"
        ).upper()
        if environment not in self.VALID_ENVIRONMENTS:
            raise ValueError("Ambiente fiscal inválido.")
        now = datetime.now(timezone.utc)
        scope = f"{environment}:{model}:{series}"
        conn = self.connection_factory()
        try:
            conn.execute("BEGIN IMMEDIATE")
            data = self._load_numbering_conn(conn)
            if scope in data.setdefault("scopes", {}):
                raise ValueError(
                    "A numeração deste modelo/série já foi iniciada. Use inutilização para tratar lacunas."
                )
            if any(record.get("scope") == scope for record in data.get("records", {}).values()):
                raise ValueError("Já existem registros para esta numeração fiscal.")
            data["scopes"][scope] = next_number - 1
            audit = {
                "scope": scope, "model": model, "series": series,
                "environment": environment, "next_number": next_number,
                "actor": str(actor or "").strip() or "Sistema",
                "created_at": now.isoformat(),
            }
            data.setdefault("initializations", []).append(audit)
            self._save_numbering_conn(conn, data)
            conn.commit()
            return dict(audit)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def reserve_number(
        self,
        *,
        model: str,
        series: int,
        environment: str | None = None,
        ttl_minutes: int = 30,
    ) -> dict[str, Any]:
        actor = self._authenticated_outbox_actor("transmit")
        model = str(model).strip()
        if model not in self.VALID_MODELS:
            raise ValueError("Modelo fiscal deve ser 55 ou 65.")
        series = int(series)
        if series < 0 or series > 999:
            raise ValueError("Série fiscal inválida.")
        environment = str(environment or self.load_config().get("environment", "HOMOLOGACAO")).upper()
        if environment not in self.VALID_ENVIRONMENTS:
            raise ValueError("Ambiente fiscal inválido.")
        ttl_minutes = max(1, int(ttl_minutes))
        now = datetime.now(timezone.utc)
        conn = self.connection_factory()
        try:
            conn.execute("BEGIN IMMEDIATE")
            data = self._load_numbering_conn(conn)
            self._recover_expired_reservations(data, now=now, connection=conn)
            scope = f"{environment}:{model}:{series}"
            scopes = data.setdefault("scopes", {})
            last_number = int(scopes.get(scope, 0))
            used = {
                int(item.get("number", 0))
                for item in data.get("records", {}).values()
                if item.get("scope") == scope and item.get("status") in {"RESERVADO", "CONFIRMADO"}
            }
            number = last_number + 1
            while number in used:
                number += 1
            reservation_id = f"{scope}:{number}"
            record = {
                "id": reservation_id,
                "scope": scope,
                "environment": environment,
                "model": model,
                "series": series,
                "number": number,
                "status": "RESERVADO",
                "actor": str(actor or "").strip(),
                "reserved_at": now.isoformat(),
                "expires_at": (now + timedelta(minutes=ttl_minutes)).isoformat(),
                "confirmed_at": "",
                "released_at": "",
                "access_key": "",
            }
            data.setdefault("records", {})[reservation_id] = record
            scopes[scope] = number
            self._save_numbering_conn(conn, data)
            conn.commit()
            return dict(record)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def confirm_number(self, reservation_id: str, *, access_key: str) -> dict[str, Any]:
        key = self._normalize_access_key(access_key)
        if len(key) != 44:
            raise ValueError("Chave de acesso inválida para confirmar numeração.")
        conn = self.connection_factory()
        try:
            conn.execute("BEGIN IMMEDIATE")
            data = self._load_numbering_conn(conn)
            record = data.get("records", {}).get(str(reservation_id))
            if not record:
                raise ValueError("Reserva de numeração não encontrada.")
            if record.get("status") == "CONFIRMADO":
                if record.get("access_key") != key:
                    raise ValueError("A numeração já foi confirmada para outra chave de acesso.")
                conn.commit()
                return dict(record)
            if record.get("status") != "RESERVADO":
                raise ValueError("A numeração não está disponível para confirmação.")
            reserved_by = str(record.get("actor") or "").strip()
            if not reserved_by:
                raise PermissionError(
                    "A reserva fiscal não possui uma identidade autenticada de origem."
                )
            expected_model = key[20:22]
            expected_series = int(key[22:25])
            expected_number = int(key[25:34])
            if expected_model != str(record.get("model")) or expected_series != int(record.get("series")) or expected_number != int(record.get("number")):
                raise ValueError("A chave de acesso não corresponde à numeração reservada.")
            record.update({
                "status": "CONFIRMADO",
                "access_key": key,
                "confirmed_at": datetime.now(timezone.utc).isoformat(),
                "confirmed_by": reserved_by,
            })
            self._save_numbering_conn(conn, data)
            conn.commit()
            return dict(record)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def release_number(self, reservation_id: str, *, reason: str) -> dict[str, Any]:
        if not str(reason).strip():
            raise ValueError("Motivo da liberação da numeração é obrigatório.")
        actor = self._authenticated_fiscal_actor(
            "transmit", operation="liberar a numeração fiscal"
        )
        conn = self.connection_factory()
        try:
            conn.execute("BEGIN IMMEDIATE")
            data = self._load_numbering_conn(conn)
            record = data.get("records", {}).get(str(reservation_id))
            if not record:
                raise ValueError("Reserva de numeração não encontrada.")
            if record.get("status") == "CONFIRMADO":
                raise ValueError("Numeração confirmada não pode ser liberada.")
            if record.get("status") == "LIBERADO":
                conn.commit()
                return dict(record)
            if self._reservation_has_transmission_risk(conn, str(reservation_id)):
                raise ValueError(
                    "A numeração está vinculada a uma transmissão iniciada ou de resposta "
                    "desconhecida. Consulte a SEFAZ antes de qualquer liberação."
                )
            record.update({
                "status": "LIBERADO",
                "released_at": datetime.now(timezone.utc).isoformat(),
                "released_by": str(actor or "").strip(),
                "release_reason": str(reason).strip(),
            })
            self._save_numbering_conn(conn, data)
            conn.commit()
            return dict(record)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def validate_ready(self, *, operation: str, model: str = "55") -> list[str]:
        config = self.load_config()
        if not config.get("enabled"):
            return ["O módulo fiscal não está habilitado."]
        model = str(model).strip()
        problems: list[str] = []
        if str(config.get("environment", "HOMOLOGACAO")).upper() == "PRODUCAO":
            problems.append(
                "Emissão em produção bloqueada nesta versão: configure e homologue "
                "IBS/CBS conforme as Notas Técnicas vigentes antes de liberar documentos reais."
            )
        if model not in self.VALID_MODELS:
            problems.append("Modelo fiscal deve ser 55 (NF-e) ou 65 (NFC-e).")
        elif model not in {str(item) for item in config.get("enabled_models", self.VALID_MODELS)}:
            problems.append(f"O modelo fiscal {model} não está habilitado para esta empresa.")
        if not self._is_valid_cnpj(config.get("cnpj")):
            problems.append("CNPJ do emitente não configurado.")
        state = str(config.get("state", "")).upper()
        if state not in self.STATE_CODES:
            problems.append("UF do emitente não configurada ou inválida.")
        elif state_profile(state)["status"] != "VALIDADO":
            problems.append(
                f"UF {state} preparada, mas ainda não homologada no NabiCode. "
                "Valide o perfil estadual antes de emitir documentos."
            )
        tax_regime = str(config.get("tax_regime", "")).upper()
        if tax_regime not in self.TAX_REGIME_CODES:
            problems.append("Regime tributário não configurado ou inválido.")
        certificate_path = str(config.get("certificate_path", "")).strip()
        if not certificate_path or not Path(certificate_path).is_file():
            problems.append("Certificado A1 não configurado ou arquivo inexistente.")
        endpoint = self.endpoint(operation, model=model)
        if not endpoint:
            problems.append(f"Endpoint SEFAZ não configurado para {operation}.")
        return problems

    def inspect_certificate(self, pfx_path: str | Path, password: str) -> FiscalCertificateInfo:
        self._require_dependency("cryptography")
        path = Path(pfx_path)
        if not path.is_file():
            raise ValueError("Arquivo do certificado A1 não encontrado.")
        if path.suffix.lower() not in {".pfx", ".p12"}:
            raise ValueError("O certificado A1 deve usar a extensão .pfx ou .p12.")
        raw = path.read_bytes()
        if not raw or len(raw) > 10 * 1024 * 1024:
            raise ValueError("O arquivo do certificado A1 está vazio ou excede 10 MB.")
        try:
            key, cert, _chain = pkcs12.load_key_and_certificates(
                raw, str(password).encode("utf-8")
            )
        except ValueError as exc:
            raise InvalidCertificatePasswordError(
                "Senha incorreta ou arquivo PKCS#12 inválido. Confira o A1 selecionado."
            ) from exc
        if key is None or cert is None:
            raise ValueError("O arquivo não contém chave privada e certificado válidos.")
        now = datetime.now(timezone.utc)
        valid_from = self._cert_datetime(cert, "not_valid_before_utc", "not_valid_before")
        valid_until = self._cert_datetime(cert, "not_valid_after_utc", "not_valid_after")
        subject = cert.subject.rfc4514_string()
        document = self._document_from_certificate(cert)
        common_name = next(
            (
                str(attribute.value).strip()
                for attribute in cert.subject
                if attribute.oid.dotted_string == "2.5.4.3"
            ),
            "",
        )
        company_name = common_name
        if document and self._normalize_cnpj(common_name[-len(document):]) == document:
            company_name = common_name[:-len(document)].rstrip(" :-")
        expires_in_days = (valid_until.date() - now.date()).days
        return FiscalCertificateInfo(
            subject=subject,
            issuer=cert.issuer.rfc4514_string(),
            serial_number=f"{cert.serial_number:X}",
            valid_from=valid_from.isoformat(),
            valid_until=valid_until.isoformat(),
            document=document,
            expired=not (valid_from <= now <= valid_until),
            company_name=company_name,
            expires_in_days=expires_in_days,
            expiring_soon=0 <= expires_in_days <= 30,
        )

    def configure_certificate(self, pfx_path: str | Path, password: str) -> FiscalCertificateInfo:
        info = self.inspect_certificate(pfx_path, password)
        if info.expired:
            raise ValueError("O certificado A1 está expirado ou ainda não é válido.")
        config = self.load_config()
        configured_cnpj = self._normalize_cnpj(config.get("cnpj"))
        if configured_cnpj and info.document and configured_cnpj != info.document:
            raise ValueError("O CNPJ do certificado não corresponde ao emitente configurado.")
        config["certificate_path"] = str(Path(pfx_path).resolve())
        config["certificate_info"] = asdict(info)
        self._set_setting(self.CONFIG_KEY, json.dumps(config, ensure_ascii=False, sort_keys=True))
        return info

    def endpoint(self, operation: str, *, model: str | None = None) -> str:
        config = self.load_config()
        environment = str(config.get("environment", "HOMOLOGACAO")).upper()
        model = str(model or config.get("default_model") or "65")
        if model not in self.VALID_MODELS:
            raise ValueError("Modelo fiscal deve ser 55 ou 65 para selecionar o endpoint.")
        endpoints = (config.get("endpoints") or {}).get(environment, {})
        operation = str(operation)
        if operation == "recibo":
            custom = endpoints.get("recibo") or endpoints.get("consulta_recibo")
        else:
            custom = endpoints.get(operation)
        if custom:
            return self._validate_endpoint_url(str(custom).strip())
        state = str(config.get("state") or "").upper()
        if state not in self.STATE_CODES:
            return ""
        profile = state_profile(state)
        return str(
            profile.get("endpoints", {}).get(model, {}).get(environment, {}).get(operation, "")
        ).strip()

    @staticmethod
    def _validate_endpoint_url(value: str) -> str:
        url = str(value or "").strip()
        try:
            parsed = urlsplit(url)
            port = parsed.port
        except ValueError as exc:
            raise ValueError("Endpoint fiscal inválido.") from exc
        hostname = str(parsed.hostname or "").rstrip(".").casefold()
        if parsed.scheme.casefold() != "https":
            raise ValueError("Endpoint fiscal deve usar HTTPS.")
        if not hostname or parsed.username is not None or parsed.password is not None:
            raise ValueError("Endpoint fiscal não pode conter credenciais na URL.")
        if port not in {None, 443}:
            raise ValueError("Endpoint fiscal deve usar a porta HTTPS padrão 443.")
        if parsed.query or parsed.fragment:
            raise ValueError("Endpoint fiscal não pode conter consulta ou fragmento na URL.")
        if not (hostname.endswith(".gov.br") or hostname.endswith(".invalid")):
            raise ValueError("Endpoint fiscal deve pertencer a um domínio governamental oficial.")
        return url

    def sign_xml(self, xml: bytes | str, *, reference_id: str, pfx_path: str | Path, password: str) -> bytes:
        self._require_dependency("cryptography")
        self._require_dependency("lxml")
        key, cert, _chain = pkcs12.load_key_and_certificates(
            Path(pfx_path).read_bytes(), str(password).encode("utf-8")
        )
        if key is None or cert is None:
            raise ValueError("Certificado A1 inválido para assinatura.")
        parser = etree.XMLParser(remove_blank_text=True, resolve_entities=False, no_network=True)
        root = etree.fromstring(xml.encode("utf-8") if isinstance(xml, str) else xml, parser=parser)
        matches = root.xpath(f'//*[@Id="{reference_id}"]')
        if len(matches) != 1:
            raise ValueError("Elemento fiscal com Id informado não foi localizado de forma única.")
        target = matches[0]
        digest = hashes.Hash(hashes.SHA1())
        digest.update(etree.tostring(target, method="c14n", exclusive=False, with_comments=False))
        digest_value = base64.b64encode(digest.finalize()).decode("ascii")

        signature = etree.Element(etree.QName(self.DS_NS, "Signature"), nsmap={None: self.DS_NS})
        signed_info = etree.SubElement(signature, etree.QName(self.DS_NS, "SignedInfo"))
        etree.SubElement(signed_info, etree.QName(self.DS_NS, "CanonicalizationMethod"), Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315")
        etree.SubElement(signed_info, etree.QName(self.DS_NS, "SignatureMethod"), Algorithm="http://www.w3.org/2000/09/xmldsig#rsa-sha1")
        reference = etree.SubElement(signed_info, etree.QName(self.DS_NS, "Reference"), URI=f"#{reference_id}")
        transforms = etree.SubElement(reference, etree.QName(self.DS_NS, "Transforms"))
        etree.SubElement(transforms, etree.QName(self.DS_NS, "Transform"), Algorithm="http://www.w3.org/2000/09/xmldsig#enveloped-signature")
        etree.SubElement(transforms, etree.QName(self.DS_NS, "Transform"), Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315")
        etree.SubElement(reference, etree.QName(self.DS_NS, "DigestMethod"), Algorithm="http://www.w3.org/2000/09/xmldsig#sha1")
        etree.SubElement(reference, etree.QName(self.DS_NS, "DigestValue")).text = digest_value

        signed_info_c14n = etree.tostring(signed_info, method="c14n", exclusive=False, with_comments=False)
        signature_value = key.sign(signed_info_c14n, padding.PKCS1v15(), hashes.SHA1())
        etree.SubElement(signature, etree.QName(self.DS_NS, "SignatureValue")).text = base64.b64encode(signature_value).decode("ascii")
        key_info = etree.SubElement(signature, etree.QName(self.DS_NS, "KeyInfo"))
        x509_data = etree.SubElement(key_info, etree.QName(self.DS_NS, "X509Data"))
        etree.SubElement(x509_data, etree.QName(self.DS_NS, "X509Certificate")).text = base64.b64encode(cert.public_bytes(serialization.Encoding.DER)).decode("ascii")
        next_node = target.getnext()
        if next_node is not None and etree.QName(next_node).localname == "infNFeSupl":
            next_node.addnext(signature)
        else:
            target.addnext(signature)
        return etree.tostring(root, xml_declaration=True, encoding="utf-8", standalone=False)

    def verify_xml_signature(self, xml: bytes | str) -> dict[str, Any]:
        """Valida a assinatura XMLDSig incorporada ao documento fiscal.

        A validação cobre a referência, o digest do elemento fiscal, o
        certificado embutido e a assinatura de ``SignedInfo``. Ela não
        substitui a validação da cadeia ICP-Brasil, que depende de uma cadeia
        de confiança atualizada no ambiente de implantação.
        """
        self._require_dependency("cryptography")
        self._require_dependency("lxml")
        raw = xml.encode("utf-8") if isinstance(xml, str) else bytes(xml)
        parser = etree.XMLParser(remove_blank_text=True, resolve_entities=False, no_network=True)
        root = etree.fromstring(raw, parser=parser)
        signatures = root.xpath("//*[local-name()='Signature' and namespace-uri()=$ns]", ns=self.DS_NS)
        if len(signatures) != 1:
            raise ValueError("XML fiscal deve possuir exatamente uma assinatura XMLDSig.")
        signature = signatures[0]
        references = signature.xpath("./*[local-name()='SignedInfo']/*[local-name()='Reference']")
        if len(references) != 1:
            raise ValueError("Assinatura fiscal deve possuir exatamente uma referência.")
        reference = references[0]
        uri = str(reference.get("URI") or "")
        if not uri.startswith("#") or len(uri) < 2:
            raise ValueError("Referência da assinatura fiscal é inválida.")
        reference_id = uri[1:]
        targets = root.xpath('//*[@Id=$reference_id]', reference_id=reference_id)
        if len(targets) != 1:
            raise ValueError("Elemento referenciado pela assinatura não foi localizado de forma única.")
        target = targets[0]
        digest_text = str(reference.xpath("string(./*[local-name()='DigestValue'])") or "").strip()
        if not digest_text:
            raise ValueError("Assinatura fiscal não contém DigestValue.")
        digest = hashes.Hash(hashes.SHA1())
        digest.update(etree.tostring(target, method="c14n", exclusive=False, with_comments=False))
        calculated_digest = base64.b64encode(digest.finalize()).decode("ascii")
        if calculated_digest != digest_text:
            raise ValueError("Digest da assinatura fiscal não corresponde ao conteúdo do XML.")

        certificate_text = str(signature.xpath("string(.//*[local-name()='X509Certificate'])") or "").strip()
        signature_text = str(signature.xpath("string(./*[local-name()='SignatureValue'])") or "").strip()
        signed_info_nodes = signature.xpath("./*[local-name()='SignedInfo']")
        if not certificate_text or not signature_text or len(signed_info_nodes) != 1:
            raise ValueError("Assinatura fiscal não contém certificado ou valor de assinatura válido.")
        try:
            cert = x509.load_der_x509_certificate(base64.b64decode(certificate_text, validate=True))
            signature_value = base64.b64decode(signature_text, validate=True)
        except Exception as exc:
            raise ValueError("Certificado ou assinatura XMLDSig possui codificação inválida.") from exc
        signed_info_c14n = etree.tostring(
            signed_info_nodes[0], method="c14n", exclusive=False, with_comments=False
        )
        try:
            cert.public_key().verify(signature_value, signed_info_c14n, padding.PKCS1v15(), hashes.SHA1())
        except Exception as exc:
            raise ValueError("Assinatura criptográfica do XML fiscal é inválida.") from exc
        valid_from = self._cert_datetime(cert, "not_valid_before_utc", "not_valid_before")
        valid_until = self._cert_datetime(cert, "not_valid_after_utc", "not_valid_after")
        return {
            "valid": True,
            "reference_id": reference_id,
            "certificate_subject": cert.subject.rfc4514_string(),
            "certificate_serial": f"{cert.serial_number:X}",
            "certificate_valid_from": valid_from.isoformat(),
            "certificate_valid_until": valid_until.isoformat(),
            "certificate_expired_now": not (valid_from <= datetime.now(timezone.utc) <= valid_until),
        }

    def validate_authorized_xml(self, xml: bytes | str, *, require_signature: bool = True) -> dict[str, Any]:
        """Valida chave, protocolo e assinatura de um XML autorizado importado."""
        raw = xml.encode("utf-8") if isinstance(xml, str) else bytes(xml)
        parser = etree.XMLParser(remove_blank_text=True, resolve_entities=False, no_network=True)
        root = etree.fromstring(raw, parser=parser)
        inf_nodes = root.xpath("//*[local-name()='NFe']/*[local-name()='infNFe']")
        protocol_nodes = root.xpath("//*[local-name()='protNFe']/*[local-name()='infProt']")
        if len(inf_nodes) != 1 or len(protocol_nodes) != 1:
            raise ValueError("XML autorizado deve conter uma NF-e e um protocolo completos.")
        inf = inf_nodes[0]
        protocol = protocol_nodes[0]
        identifier = str(inf.get("Id") or "")
        access_key = self._normalize_access_key(identifier[3:] if identifier.startswith("NFe") else identifier)
        protocol_key = self._normalize_access_key(protocol.xpath("string(./*[local-name()='chNFe'])"))
        protocol_number = str(protocol.xpath("string(./*[local-name()='nProt'])") or "").strip()
        status_code = str(protocol.xpath("string(./*[local-name()='cStat'])") or "").strip()
        model = str(inf.xpath("string(.//*[local-name()='ide']/*[local-name()='mod'])") or "").zfill(2)
        environment_code = str(protocol.xpath("string(./*[local-name()='tpAmb'])") or "").strip()
        environment = "PRODUCAO" if environment_code == "1" else "HOMOLOGACAO"
        if not self._is_valid_access_key(access_key):
            raise ValueError("Chave de acesso do XML autorizado é inválida.")
        if protocol_key != access_key:
            raise ValueError("O protocolo pertence a outra chave de acesso.")
        if status_code not in self.AUTHORIZED_STATUS or not protocol_number:
            raise ValueError("XML não possui autorização e protocolo válidos.")
        if model not in self.VALID_MODELS:
            raise ValueError("Modelo fiscal do XML autorizado é inválido.")
        signature = self.verify_xml_signature(raw) if require_signature else {"valid": False}
        if require_signature and signature.get("reference_id") != str(inf.get("Id") or ""):
            raise ValueError("A assinatura não referencia o infNFe autorizado.")
        return {
            "valid": True,
            "access_key": access_key,
            "protocol": protocol_number,
            "status_code": status_code,
            "model": model,
            "environment": environment,
            "signature": signature,
        }

    def authorized_recipient_email(self, xml: bytes | str) -> str:
        """Lê o e-mail do destinatário somente após validar o XML autorizado."""
        raw = xml.encode("utf-8") if isinstance(xml, str) else bytes(xml)
        self.validate_authorized_xml(raw, require_signature=True)
        root = etree.fromstring(
            raw, parser=etree.XMLParser(resolve_entities=False, no_network=True)
        )
        return str(
            root.xpath("string(//*[local-name()='dest']/*[local-name()='email'][1])") or ""
        ).strip()

    def duplicate_authorized_to_pdv_draft(
        self, *, access_key: str, pdv_service: Any
    ) -> Any:
        """Cria pré-venda editável usando produtos atuais, sem copiar identidade fiscal."""
        key = self._normalize_access_key(access_key)
        document = next(
            (
                row for row in reversed(self.list_documents())
                if row.get("access_key") == key and row.get("status") == "AUTORIZADO"
            ),
            None,
        )
        if not document:
            raise ValueError("Documento fiscal autorizado não encontrado.")
        source = Path(str(document.get("processed_path") or ""))
        if not source.is_file():
            raise ValueError("XML processado do documento autorizado não foi localizado.")
        raw = source.read_bytes()
        self.validate_authorized_xml(raw, require_signature=True)
        if any(
            any(item.get("origem_nfe") == key for item in draft.itens)
            for draft in pdv_service.listar_documentos("PRE_VENDA")
        ):
            raise ValueError("Esta nota já possui uma pré-venda duplicada em aberto.")
        root = etree.fromstring(raw, parser=etree.XMLParser(resolve_entities=False, no_network=True))
        extracted = []
        for detail in root.xpath("//*[local-name()='infNFe']/*[local-name()='det']"):
            code = str(detail.xpath("string(./*[local-name()='prod']/*[local-name()='cProd'])") or "").strip()
            quantity = str(detail.xpath("string(./*[local-name()='prod']/*[local-name()='qCom'])") or "").strip()
            if not code or not quantity:
                raise ValueError("A nota original possui item sem código ou quantidade comercial.")
            extracted.append((code, Decimal(quantity)))
        if not extracted:
            raise ValueError("A nota original não possui itens para duplicar.")
        connection = self.connection_factory()
        try:
            products = {}
            for code, _quantity in extracted:
                row = connection.execute(
                    "SELECT id,codigo,nome,preco_venda,ativo,controla_estoque FROM produtos "
                    "WHERE codigo=? COLLATE NOCASE",
                    (code,),
                ).fetchone()
                if not row or not int(row[4] or 0):
                    raise ValueError(f"Produto {code} não existe ou está inativo no cadastro atual.")
                products[code.casefold()] = row
            recipient = self._normalize_tax_document(str(
                root.xpath("string(//*[local-name()='dest']/*[local-name()='CNPJ' or local-name()='CPF'][1])") or ""
            ))
            customer_id = None
            customer_name = str(root.xpath("string(//*[local-name()='dest']/*[local-name()='xNome'][1])") or "").strip()
            if recipient:
                for row in connection.execute("SELECT id,nome,cpf FROM clientes"):
                    if self._normalize_tax_document(row[2]) == recipient:
                        customer_id, customer_name = int(row[0]), str(row[1] or customer_name)
                        break
        finally:
            connection.close()
        items = []
        for code, quantity in extracted:
            product = products[code.casefold()]
            price = Decimal(str(product[3] or 0)).quantize(Decimal("0.01"))
            items.append({
                "produto_id": int(product[0]), "item": str(product[2]),
                "qtd": quantity, "preco": price, "subtotal": quantity * price,
                "item_avulso": False, "controla_estoque": bool(product[5]),
                "estoque_override": False, "origem_nfe": key,
            })
        return pdv_service.salvar_documento(
            "PRE_VENDA", items, cliente_id=customer_id, cliente_nome=customer_name
        )

    def import_authorized_xml(
        self, xml: bytes | str, *, require_signature: bool = True
    ) -> dict[str, Any]:
        """Importa um XML autorizado externo após validações de integridade fiscal."""
        actor = self._authenticated_outbox_actor("transmit")
        raw = xml.encode("utf-8") if isinstance(xml, str) else bytes(xml)
        validation = self.validate_authorized_xml(raw, require_signature=require_signature)
        key = validation["access_key"]
        environment = validation["environment"]
        model = validation["model"]
        folder = self.storage_dir / environment.lower() / model / key
        folder.mkdir(parents=True, exist_ok=True)
        processed_path = folder / "processado_importado.xml"
        processed_path.write_bytes(raw)
        record = {
            "access_key": key,
            "model": model,
            "environment": environment,
            "status": "AUTORIZADO",
            "protocol": validation["protocol"],
            "response_access_key": key,
            "status_code": validation["status_code"],
            "message": "XML autorizado importado e validado.",
            "actor": actor,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source": "IMPORTADO",
            "request_path": "",
            "response_path": "",
            "processed_path": str(processed_path),
            "request_sha256": "",
            "response_sha256": "",
            "processed_sha256": hashlib.sha256(raw).hexdigest(),
            "signature": validation["signature"],
        }
        index = [
            row for row in self.list_documents()
            if row.get("access_key") != key or row.get("environment") != environment
        ]
        index.append(record)
        self._set_setting(self.DOCUMENT_INDEX_KEY, json.dumps(index, ensure_ascii=False, sort_keys=True))
        return record

    def transmit(
        self,
        *,
        operation: str,
        model: str | None = None,
        xml: bytes | str,
        pfx_path: str | Path,
        password: str,
        timeout: int = 45,
        headers: Mapping[str, str] | None = None,
    ) -> FiscalResponse:
        environment = str(
            self.load_config().get("environment") or "HOMOLOGACAO"
        ).upper()
        if environment == "PRODUCAO":
            raise ValueError("Produção fiscal permanece bloqueada nesta versão.")
        self._require_dependency("requests")
        self._require_dependency("cryptography")
        endpoint = self.endpoint(operation, model=model)
        if not endpoint:
            raise ValueError(f"Endpoint SEFAZ não configurado para {operation}.")
        if self.http_post is None:
            raise RuntimeError(
                "A dependência 'requests' não está instalada. Execute "
                "ATUALIZAR_DEPENDENCIAS.bat antes de usar a transmissão fiscal."
            )
        pem_cert, pem_key = self._temporary_pem_files(pfx_path, password)
        server_ca_bundle = ""
        try:
            server_ca_bundle = self._temporary_server_ca_bundle()
            request_xml, soap_action = self._soap_request(operation=operation, xml=xml)
            content_type = (
                'application/soap+xml; charset=utf-8; '
                f'action="{soap_action}"'
            )
            request_headers = dict(headers or {})
            # Estes cabeçalhos fazem parte do contrato SOAP fiscal. Um chamador
            # não pode degradar silenciosamente a requisição para XML puro ou
            # anunciar um tipo de resposta incompatível com o parser seguro.
            request_headers.update({
                "Content-Type": content_type,
                "Accept": "application/soap+xml; charset=utf-8",
            })
            response = self.http_post(
                endpoint,
                data=request_xml,
                headers=request_headers,
                cert=(pem_cert, pem_key),
                verify=server_ca_bundle,
                timeout=int(timeout),
            )
            response.raise_for_status()
            return self.parse_response(response.content)
        except Exception as exc:
            if requests is not None and isinstance(exc, requests.RequestException):
                detail = self._soap_fault_detail(
                    getattr(getattr(exc, "response", None), "content", b"")
                )
                message = f"Falha de comunicação com a SEFAZ: {detail or exc}"
                if str(operation).lower() in {"autorizacao", "evento", "inutilizacao"}:
                    raise FiscalTransmissionUnknownError(message) from exc
                raise RuntimeError(message) from exc
            raise
        finally:
            for temp_path in (pem_cert, pem_key, server_ca_bundle):
                if temp_path:
                    self._secure_delete_file(temp_path)

    @staticmethod
    def _soap_fault_detail(xml: bytes | str | None) -> str:
        """Extrai somente o texto seguro de um SOAP Fault, sem ecoar o XML."""
        if not xml:
            return ""
        raw = xml.encode("utf-8") if isinstance(xml, str) else bytes(xml)
        try:
            root = etree.fromstring(
                raw, parser=etree.XMLParser(resolve_entities=False, no_network=True)
            )
        except (etree.XMLSyntaxError, TypeError, ValueError):
            return ""
        faults = root.xpath("//*[local-name()='Fault'][1]")
        if not faults:
            return ""
        fault = faults[0]
        detail = str(
            fault.xpath("string(.//*[local-name()='Reason']/*[local-name()='Text'][1])")
            or fault.xpath("string(.//*[local-name()='faultstring'][1])")
            or "Falha SOAP retornada pela SEFAZ."
        ).strip()
        return " ".join(detail.split())[:500]

    @staticmethod
    def _soap_request(*, operation: str, xml: bytes | str) -> tuple[bytes, str]:
        """Encapsula a mensagem fiscal no contrato SOAP 1.2 dos WS NF-e 4.00."""
        contracts = {
            "autorizacao": ("NFeAutorizacao4", "nfeAutorizacaoLote"),
            "recibo": ("NFeRetAutorizacao4", "nfeRetAutorizacaoLote"),
            "consulta": ("NFeConsultaProtocolo4", "nfeConsultaNF"),
            "status": ("NFeStatusServico4", "nfeStatusServicoNF"),
            "evento": ("NFeRecepcaoEvento4", "nfeRecepcaoEvento"),
            "inutilizacao": ("NFeInutilizacao4", "nfeInutilizacaoNF"),
        }
        normalized = str(operation or "").strip().lower()
        try:
            service_name, method_name = contracts[normalized]
        except KeyError as exc:
            raise ValueError(f"Operação SOAP fiscal não suportada: {operation}.") from exc
        raw = xml.encode("utf-8") if isinstance(xml, str) else bytes(xml)
        parser = etree.XMLParser(resolve_entities=False, no_network=True)
        payload = etree.fromstring(raw, parser=parser)
        if etree.QName(payload).localname == "Envelope":
            return raw, f"http://www.portalfiscal.inf.br/nfe/wsdl/{service_name}/{method_name}"
        soap = "http://www.w3.org/2003/05/soap-envelope"
        wsdl = f"http://www.portalfiscal.inf.br/nfe/wsdl/{service_name}"
        # A NF-e declara C14N inclusiva. Prefixos de namespace introduzidos
        # somente pelo envelope SOAP tornam-se ancestrais de ``infNFe`` e
        # alteram o DigestValue/SignatureValue no documento efetivamente
        # recebido pela SEFAZ. Use namespaces padrão em cada camada: o payload
        # NF-e redefine o namespace padrão e não herda prefixos estranhos à
        # assinatura. Prefixos XML são sintaxe, não fazem parte do contrato.
        envelope = etree.Element(etree.QName(soap, "Envelope"), nsmap={None: soap})
        body = etree.SubElement(envelope, etree.QName(soap, "Body"))
        data = etree.SubElement(
            body,
            etree.QName(wsdl, "nfeDadosMsg"),
            nsmap={None: wsdl},
        )
        data.append(payload)
        action = f"{wsdl}/{method_name}"
        return etree.tostring(envelope, xml_declaration=True, encoding="utf-8"), action

    def parse_response(self, xml: bytes | str) -> FiscalResponse:
        self._require_dependency("lxml")
        raw = xml.decode("utf-8", errors="replace") if isinstance(xml, bytes) else str(xml)
        try:
            root = etree.fromstring(
                raw.encode("utf-8"),
                parser=etree.XMLParser(resolve_entities=False, no_network=True),
            )
        except etree.XMLSyntaxError as exc:
            raise ValueError("Resposta da SEFAZ não contém XML válido.") from exc

        def value(node: Any, name: str) -> str:
            return str(node.xpath(f"string(.//*[local-name()='{name}'][1])") or "").strip()

        # A SEFAZ normalmente devolve um status do lote e outro do documento/evento.
        # O status interno é o que define autorização, registro do evento ou rejeição.
        candidates = (
            root.xpath("//*[local-name()='protNFe']/*[local-name()='infProt'][1]"),
            root.xpath("//*[local-name()='retEvento']/*[local-name()='infEvento'][1]"),
            root.xpath("//*[local-name()='retInutNFe']/*[local-name()='infInut'][1]"),
            root.xpath("//*[local-name()='infProt'][1]"),
            root.xpath("//*[local-name()='infEvento'][1]"),
            root.xpath("//*[local-name()='infInut'][1]"),
        )
        detail = next((nodes[0] for nodes in candidates if nodes), root)
        status = value(detail, "cStat") or value(root, "cStat")
        protocol = value(detail, "nProt") or value(root, "nProt")
        message = value(detail, "xMotivo") or value(root, "xMotivo") or "Resposta recebida"
        receipt = value(root, "nRec")
        access_key = self._normalize_access_key(value(detail, "chNFe") or value(root, "chNFe"))

        # 128 apenas informa que o lote de eventos foi processado; sem um retorno
        # interno aceito ele não representa sucesso fiscal por si só.
        success = status in self.ACCEPTED_STATUS and (
            bool(protocol) or status in self.INUTILIZATION_ACCEPTED_STATUS
        )
        return FiscalResponse(success, status, message, protocol, receipt, access_key, raw)

    def check_service_status(self, *, model: str, password: str) -> FiscalServiceStatus:
        """Consulta o serviço da SEFAZ sem emitir, reservar ou persistir documento."""
        self._require_dependency("lxml")
        config = self.load_config()
        model = str(model)
        self.require_operational_readiness(
            operation="status", model=model, password=password,
            permission="view",
        )
        if model not in self.VALID_MODELS:
            raise ValueError("Modelo fiscal deve ser 55 ou 65.")
        if model not in {str(item) for item in config.get("enabled_models", ())}:
            raise ValueError(f"O modelo fiscal {model} não está habilitado.")
        state = str(config.get("state") or "").upper()
        state_code = self.STATE_CODES.get(state)
        if not state_code:
            raise ValueError("UF do emitente não configurada.")
        certificate_path = str(config.get("certificate_path") or "")
        info = self.inspect_certificate(certificate_path, password)
        configured_cnpj = self._normalize_cnpj(config.get("cnpj"))
        if configured_cnpj and info.document and configured_cnpj != info.document:
            raise ValueError("O CNPJ do certificado não corresponde ao emitente configurado.")
        environment = str(config.get("environment") or "HOMOLOGACAO").upper()
        root = etree.Element(
            etree.QName("http://www.portalfiscal.inf.br/nfe", "consStatServ"),
            versao="4.00",
            nsmap={None: "http://www.portalfiscal.inf.br/nfe"},
        )
        etree.SubElement(root, etree.QName(root.nsmap[None], "tpAmb")).text = (
            "2" if environment == "HOMOLOGACAO" else "1"
        )
        etree.SubElement(root, etree.QName(root.nsmap[None], "cUF")).text = state_code
        etree.SubElement(root, etree.QName(root.nsmap[None], "xServ")).text = "STATUS"
        response = self.transmit(
            operation="status", model=model,
            xml=etree.tostring(root, xml_declaration=True, encoding="utf-8"),
            pfx_path=certificate_path, password=password,
        )
        return FiscalServiceStatus(
            available=response.status_code == "107",
            status_code=response.status_code,
            message=response.message,
            model=model,
            environment=environment,
        )



    def validate_xml_schema(self, xml: bytes | str, xsd_path: str | Path) -> list[str]:
        """Valida um XML usando parser local, sem rede ou entidades externas."""
        self._require_dependency("lxml")
        path = Path(xsd_path)
        if not path.is_file():
            raise ValueError("Arquivo XSD não encontrado.")
        parser = etree.XMLParser(resolve_entities=False, no_network=True)
        try:
            schema_doc = etree.parse(str(path), parser)
            schema = etree.XMLSchema(schema_doc)
            document = etree.fromstring(xml.encode("utf-8") if isinstance(xml, str) else xml, parser)
        except (etree.XMLSyntaxError, etree.XMLSchemaParseError) as exc:
            raise ValueError(f"Schema ou XML inválido: {exc}") from exc
        if schema.validate(document):
            return []
        return [str(error) for error in schema.error_log]

    def official_schema_path(self, document_type: str) -> Path:
        paths = {
            "nfe": self.schema_dir / "nfe_010e_v1.02" / "nfe_v4.00.xsd",
            "evento": self.schema_dir / "eventos_010d_v1.03" / "envEvento_v1.00.xsd",
            "inutilizacao": self.schema_dir / "servicos_010d_v1.03" / "nabicode_inutNFe_v4.00.xsd",
            "consulta": self.schema_dir / "servicos_010d_v1.03" / "consSitNFe_v4.00.xsd",
        }
        kind = str(document_type or "").strip().casefold()
        if kind not in paths:
            raise ValueError("Tipo de schema fiscal oficial desconhecido.")
        path = paths[kind]
        if not path.is_file():
            raise RuntimeError(
                f"Schema fiscal oficial ausente: {path.name}. Repare a instalação do NabiCode."
            )
        return path

    def validate_official_xml(self, xml: bytes | str, *, document_type: str) -> None:
        errors = self.validate_xml_schema(xml, self.official_schema_path(document_type))
        if errors:
            summary = "; ".join(errors[:5])
            extra = len(errors) - 5
            if extra > 0:
                summary += f"; e mais {extra} erro(s)"
            raise ValueError(f"XML fiscal reprovado pelo schema oficial: {summary}")

    def validate_fiscal_profile(self, *, issuer: Mapping[str, Any], model: str) -> list[str]:
        problems: list[str] = []
        model = str(model).zfill(2)
        if model not in self.VALID_MODELS:
            problems.append("Modelo fiscal deve ser 55 ou 65.")
        cnpj = self._normalize_cnpj(issuer.get("cnpj"))
        if not self._is_valid_cnpj(cnpj):
            problems.append("CNPJ do emitente é inválido.")
        state = str(issuer.get("state", "")).upper()
        if state not in self.STATE_CODES:
            problems.append("UF do emitente é inválida.")
        regime_code = int(issuer.get("tax_regime_code", 0) or 0)
        if regime_code not in {1, 2, 3, 4}:
            problems.append("CRT do emitente deve ser 1, 2, 3 ou 4.")
        if len(self._digits(issuer.get("city_code"))) != 7:
            problems.append("Código IBGE do município do emitente deve possuir 7 dígitos.")
        if not self._digits(issuer.get("state_registration")):
            problems.append("Inscrição estadual do emitente é obrigatória para emissão fiscal.")
        return problems

    def register_rejection(self, *, operation: str, response: FiscalResponse, access_key: str = "", actor: str = "") -> dict[str, Any]:
        record = {
            "operation": str(operation).upper(),
            "access_key": self._normalize_access_key(access_key) or self._normalize_access_key(response.access_key),
            "status_code": response.status_code,
            "message": response.message,
            "protocol": response.protocol,
            "actor": str(actor or "Sistema"),
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        rows = self.list_rejections()
        rows.append(record)
        self._set_setting(self.REJECTION_INDEX_KEY, json.dumps(rows[-2000:], ensure_ascii=False, sort_keys=True))
        return record

    def list_rejections(self, *, operation: str = "", access_key: str = "") -> list[dict[str, Any]]:
        raw = self._get_setting(self.REJECTION_INDEX_KEY)
        try:
            rows = json.loads(raw) if raw else []
        except (TypeError, ValueError):
            rows = []
        result = [dict(row) for row in rows if isinstance(row, dict)]
        if operation:
            wanted = str(operation).upper()
            result = [row for row in result if row.get("operation") == wanted]
        if access_key:
            wanted_key = self._normalize_access_key(access_key)
            result = [row for row in result if row.get("access_key") == wanted_key]
        return result

    def merge_authorization_protocol(self, request_xml: bytes | str, response_xml: bytes | str) -> bytes:
        request_root = etree.fromstring(request_xml.encode() if isinstance(request_xml, str) else request_xml, parser=etree.XMLParser(resolve_entities=False, no_network=True))
        response_root = etree.fromstring(response_xml.encode() if isinstance(response_xml, str) else response_xml, parser=etree.XMLParser(resolve_entities=False, no_network=True))
        nfe_nodes = request_root.xpath("self::*[local-name()='NFe'] | .//*[local-name()='NFe'][1]")
        protocol_nodes = response_root.xpath("//*[local-name()='protNFe'][1]")
        if not nfe_nodes or not protocol_nodes:
            raise ValueError("XML de autorização não contém NF-e e protocolo completos.")
        request_key = self._normalize_access_key(str(nfe_nodes[0].xpath("string(.//*[local-name()='infNFe'][1]/@Id)") or "").replace("NFe", ""))
        protocol_key = self._normalize_access_key(str(protocol_nodes[0].xpath("string(.//*[local-name()='chNFe'][1])") or ""))
        if request_key and protocol_key and request_key != protocol_key:
            raise ValueError("O protocolo retornado pertence a outra chave de acesso.")
        ns = "http://www.portalfiscal.inf.br/nfe"
        proc = etree.Element(etree.QName(ns, "nfeProc"), nsmap={None: ns}, versao="4.00")
        proc.append(etree.fromstring(etree.tostring(nfe_nodes[0])))
        proc.append(etree.fromstring(etree.tostring(protocol_nodes[0])))
        return etree.tostring(proc, xml_declaration=True, encoding="utf-8")

    def store_document(
        self,
        *,
        access_key: str,
        model: str,
        environment: str,
        request_xml: bytes | str,
        response: FiscalResponse,
        actor: str,
    ) -> dict[str, Any]:
        key = self._normalize_access_key(access_key)
        if len(key) != 44:
            raise ValueError("Chave de acesso deve possuir 44 caracteres válidos.")
        model = str(model).strip()
        if model not in self.VALID_MODELS:
            raise ValueError("Modelo fiscal inválido.")
        environment = str(environment).strip().upper()
        if environment not in self.VALID_ENVIRONMENTS:
            raise ValueError("Ambiente fiscal inválido.")
        if response.access_key and response.access_key != key:
            raise ValueError("A resposta da SEFAZ pertence a outra chave de acesso.")
        authorized = response.status_code in self.AUTHORIZED_STATUS and bool(response.protocol)
        if response.status_code in self.AUTHORIZED_STATUS and not response.protocol:
            raise ValueError("Documento não pode ser autorizado sem protocolo válido.")
        status = "AUTORIZADO" if authorized else "REJEITADO"
        folder = self.storage_dir / environment.lower() / model / key
        folder.mkdir(parents=True, exist_ok=True)
        request_path = folder / "envio.xml"
        response_path = folder / "retorno.xml"
        processed_path = folder / "processado.xml"
        request_bytes = request_xml.encode("utf-8") if isinstance(request_xml, str) else bytes(request_xml)
        response_bytes = response.raw_xml.encode("utf-8")
        processed_bytes: bytes | None = None
        if authorized:
            # Um documento autorizado só pode ser indexado depois que o XML
            # processado (NFe + protNFe) for construído e validado. Engolir a
            # falha aqui criava um registro AUTORIZADO sem arquivo fiscal legal.
            processed_bytes = self.merge_authorization_protocol(request_bytes, response_bytes)

        written_paths: list[Path] = []
        try:
            self._atomic_write_bytes(request_path, request_bytes)
            written_paths.append(request_path)
            self._atomic_write_bytes(response_path, response_bytes)
            written_paths.append(response_path)
            if processed_bytes is not None:
                self._atomic_write_bytes(processed_path, processed_bytes)
                written_paths.append(processed_path)
        except Exception:
            for written_path in reversed(written_paths):
                try:
                    written_path.unlink(missing_ok=True)
                except OSError:
                    pass
            raise

        processed_value = str(processed_path) if processed_bytes is not None else ""
        processed_hash = hashlib.sha256(processed_bytes).hexdigest() if processed_bytes is not None else ""
        record = {
            "access_key": key,
            "model": model,
            "environment": environment,
            "status": status,
            "protocol": response.protocol,
            "response_access_key": response.access_key,
            "status_code": response.status_code,
            "message": response.message,
            "actor": str(actor or "Sistema"),
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "request_path": str(request_path),
            "response_path": str(response_path),
            "processed_path": processed_value,
            "request_sha256": hashlib.sha256(request_bytes).hexdigest(),
            "response_sha256": hashlib.sha256(response_bytes).hexdigest(),
            "processed_sha256": processed_hash,
        }
        index = self.list_documents()
        index = [row for row in index if row.get("access_key") != key or row.get("environment") != environment]
        index.append(record)
        self._set_setting(self.DOCUMENT_INDEX_KEY, json.dumps(index, ensure_ascii=False, sort_keys=True))
        if not authorized:
            self.register_rejection(operation="AUTORIZACAO", response=response, access_key=key, actor=actor)
        return record


    def verify_document_integrity(self, *, access_key: str, environment: str = "") -> dict[str, Any]:
        key = self._normalize_access_key(access_key)
        if len(key) != 44:
            raise ValueError("Chave de acesso deve possuir 44 caracteres válidos.")
        wanted_environment = str(environment or "").strip().upper()
        records = [
            row for row in self.list_documents()
            if row.get("access_key") == key
            and (not wanted_environment or row.get("environment") == wanted_environment)
        ]
        if not records:
            raise ValueError("Documento fiscal não encontrado no índice.")
        record = records[-1]
        checks: dict[str, Any] = {}
        ok = True
        for name in ("request", "response", "processed"):
            path_value = str(record.get(f"{name}_path") or "").strip()
            expected = str(record.get(f"{name}_sha256") or "").strip().lower()
            if not path_value:
                checks[name] = {"exists": False, "expected": expected, "actual": "", "valid": not expected}
                ok = ok and not expected
                continue
            path = Path(path_value)
            exists = path.is_file()
            actual = hashlib.sha256(path.read_bytes()).hexdigest() if exists else ""
            valid = exists and bool(expected) and actual == expected
            checks[name] = {"exists": exists, "expected": expected, "actual": actual, "valid": valid}
            ok = ok and valid
        return {"access_key": key, "environment": record.get("environment"), "valid": ok, "checks": checks}

    def export_accounting_package(
        self, *, start_date: str | datetime, end_date: str | datetime,
        output_path: str | Path, include_homologation: bool = False,
        received_documents: Sequence[Mapping[str, Any]] = (),
    ) -> dict[str, Any]:
        """Exporta saídas, entradas DF-e e eventos íntegros para a contabilidade."""
        self._require_dependency("lxml")
        def as_date(value: str | datetime):
            return value.date() if isinstance(value, datetime) else datetime.fromisoformat(str(value).strip()).date()

        start, end = as_date(start_date), as_date(end_date)
        if start > end:
            raise ValueError("A data inicial não pode ser posterior à data final.")
        destination = Path(output_path)
        if destination.suffix.lower() != ".zip":
            destination = destination.with_suffix(".zip")
        destination.parent.mkdir(parents=True, exist_ok=True)
        def issued_date(path_value: Any, fallback: Any = ""):
            path = Path(str(path_value or ""))
            if path.is_file():
                root = etree.fromstring(
                    path.read_bytes(), parser=etree.XMLParser(resolve_entities=False, no_network=True)
                )
                issued = str(root.xpath(
                    "string((//*[local-name()='ide']/*[local-name()='dhEmi'] | "
                    "//*[local-name()='ide']/*[local-name()='dEmi'] | "
                    "//*[local-name()='dhEmi'])[1])"
                ) or "").strip()
                if issued:
                    return datetime.fromisoformat(issued.replace("Z", "+00:00")).date()
            return datetime.fromisoformat(str(fallback or "").strip()).date()

        documents: list[dict[str, Any]] = []
        for row in self.list_documents():
            if str(row.get("status") or "").upper() not in {"AUTORIZADO", "CANCELADO"}:
                continue
            environment = str(row.get("environment") or "").upper()
            if environment != "PRODUCAO" and not include_homologation:
                continue
            try:
                created = issued_date(row.get("processed_path"), row.get("created_at"))
            except (OSError, ValueError, etree.XMLSyntaxError):
                continue
            if not start <= created <= end:
                continue
            integrity = self.verify_document_integrity(
                access_key=str(row.get("access_key") or ""), environment=environment,
            )
            if not integrity["valid"] or not str(row.get("processed_path") or ""):
                raise ValueError(f"XML fiscal {row.get('access_key', '')} falhou na verificação de integridade.")
            documents.append(dict(row))

        document_environment = {
            str(row.get("access_key") or ""): str(row.get("environment") or "").upper()
            for row in self.list_documents()
            if str(row.get("status") or "").upper() == "AUTORIZADO"
        }
        selected_keys = {str(row.get("access_key") or "") for row in documents}
        events: list[dict[str, Any]] = []
        for row in self.list_events():
            key = str(row.get("access_key") or "")
            environment = str(row.get("environment") or document_environment.get(key, "")).upper()
            if str(row.get("status_code") or "") not in self.EVENT_ACCEPTED_STATUS:
                continue
            if environment != "PRODUCAO" and not include_homologation:
                continue
            try:
                created = datetime.fromisoformat(str(row.get("created_at") or "")).date()
            except ValueError:
                continue
            if start <= created <= end or key in selected_keys:
                events.append(dict(row))
        accounting_config = self.load_config()
        manifest: dict[str, Any] = {
            "product": "NabiCode", "purpose": "Pacote fiscal para contabilidade",
            "version": 2,
            "layout": "nabicode.accounting-package.v2",
            "integrity": {
                "algorithm": "SHA-256",
                "scope": "Todos os arquivos do ZIP, exceto o próprio manifesto",
                "non_repudiation": False,
            },
            "issuer": {
                "cnpj": str(accounting_config.get("cnpj") or ""),
                "name": str((accounting_config.get("issuer") or {}).get("name") or ""),
                "state": str(accounting_config.get("state") or ""),
            },
            "period": {"start": start.isoformat(), "end": end.isoformat()},
            "includes_homologation": bool(include_homologation),
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "documents": [], "received_documents": [], "events": [], "files": [],
        }
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                prefix=f".{destination.stem}_", suffix=".tmp", dir=destination.parent, delete=False
            ) as temporary:
                temp_path = Path(temporary.name)
            with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for row in documents:
                    key, model = str(row["access_key"]), str(row["model"])
                    label = "NFCe" if model == "65" else "NFe"
                    name = f"{str(row['environment']).lower()}/{label}/{label}{key}.xml"
                    data = Path(str(row["processed_path"])).read_bytes()
                    archive.writestr(name, data)
                    digest = hashlib.sha256(data).hexdigest()
                    manifest["files"].append({"file": name, "sha256": digest, "kind": "SAIDA_FISCAL"})
                    manifest["documents"].append({
                        "access_key": key, "model": model, "environment": row["environment"],
                        "status": row.get("status", ""),
                        "protocol": row.get("protocol", ""), "created_at": row.get("created_at", ""),
                        "file": name, "sha256": digest,
                    })
                for index, row in enumerate(received_documents, 1):
                    path = Path(str(row.get("path") or ""))
                    if not path.is_file():
                        continue
                    data = path.read_bytes()
                    expected = str(row.get("sha256") or "").lower()
                    digest = hashlib.sha256(data).hexdigest()
                    if expected and digest != expected:
                        raise ValueError(
                            f"DF-e recebido NSU {row.get('nsu', '')} falhou na verificação de integridade."
                        )
                    try:
                        received_date = issued_date(path, row.get("issued_at"))
                    except (OSError, ValueError, etree.XMLSyntaxError):
                        continue
                    if not start <= received_date <= end:
                        continue
                    schema = str(row.get("schema") or "documento").removesuffix(".xsd")
                    is_summary = schema.casefold().startswith("resnfe")
                    key = str(row.get("access_key") or "sem_chave")
                    name = f"entradas_DFe/{received_date:%Y-%m}/{index:04d}_{schema}_{key}.xml"
                    archive.writestr(name, data)
                    manifest["files"].append({"file": name, "sha256": digest, "kind": "ENTRADA_DFE"})
                    manifest["received_documents"].append({
                        "nsu": str(row.get("nsu") or ""), "access_key": key,
                        "schema": str(row.get("schema") or ""),
                        "content": "RESUMO" if is_summary else "XML_COMPLETO",
                        "issued_at": str(row.get("issued_at") or ""),
                        "file": name, "sha256": digest,
                    })
                for index, row in enumerate(events, 1):
                    key = str(row["access_key"])
                    kind = str(row.get("event_type") or "EVENTO").upper()
                    base = f"eventos/{key}/{index:03d}_{kind}"
                    exported: list[dict[str, str]] = []
                    for suffix, field in (("envio", "request_path"), ("retorno", "response_path")):
                        path = Path(str(row.get(field) or ""))
                        if path.is_file():
                            data = path.read_bytes()
                            expected = str(row.get(f"{suffix.replace('envio', 'request').replace('retorno', 'response')}_sha256") or "").lower()
                            if not expected or hashlib.sha256(data).hexdigest() != expected:
                                raise ValueError(f"Evento fiscal {kind} da chave {key} falhou na verificação de integridade.")
                            name = f"{base}_{suffix}.xml"
                            archive.writestr(name, data)
                            digest = hashlib.sha256(data).hexdigest()
                            exported.append({"role": suffix.upper(), "file": name, "sha256": digest})
                            manifest["files"].append({"file": name, "sha256": digest, "kind": "EVENTO_FISCAL"})
                    manifest["events"].append({
                        "access_key": key, "type": kind, "protocol": row.get("protocol", ""),
                        "status_code": row.get("status_code", ""), "created_at": row.get("created_at", ""),
                        "files": exported,
                    })
                readme = (
                    "PACOTE FISCAL NABICODE PARA CONTABILIDADE\n\n"
                    f"Período: {start.isoformat()} a {end.isoformat()}\n"
                    "producao/NFe e producao/NFCe: documentos de saída.\n"
                    "entradas_DFe: documentos recebidos da SEFAZ; consulte o manifesto para saber "
                    "se o conteúdo é XML_COMPLETO ou apenas RESUMO.\n"
                    "eventos: cancelamentos, cartas de correção e inutilizações aceitos.\n"
                    "manifesto.json: relação completa de arquivos e hashes SHA-256 para validação.\n"
                    "LIMITAÇÃO: o manifesto v2 não possui assinatura digital. Os hashes detectam "
                    "corrupção e divergências, mas não fornecem não-repúdio nem provam autoria.\n\n"
                    "Este pacote de XMLs não substitui a EFD ICMS/IPI nem outras declarações "
                    "exigidas conforme o regime e a UF da empresa.\n"
                )
                readme_data = readme.encode("utf-8")
                archive.writestr("LEIA-ME.txt", readme_data)
                manifest["files"].append({
                    "file": "LEIA-ME.txt", "sha256": hashlib.sha256(readme_data).hexdigest(),
                    "kind": "INSTRUCOES",
                })
                archive.writestr("manifesto.json", json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
            os.replace(temp_path, destination)
            temp_path = None
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
        return {
            "path": str(destination), "documents": len(documents), "events": len(events),
            "received_documents": len(manifest["received_documents"]),
            "received_summaries": sum(
                1 for row in manifest["received_documents"] if row.get("content") == "RESUMO"
            ),
            "period_start": start.isoformat(), "period_end": end.isoformat(),
        }

    def validate_accounting_package(self, archive_path: str | Path) -> dict[str, Any]:
        """Valida estrutura, conteúdo e SHA-256 do pacote contábil v2."""
        path = Path(archive_path)
        if not path.is_file() or path.suffix.casefold() != ".zip":
            raise ValueError("Selecione um pacote contábil ZIP gerado pelo NabiCode.")
        if path.stat().st_size > 2 * 1024 * 1024 * 1024:
            raise ValueError("O pacote contábil excede o limite seguro de 2 GB.")
        try:
            with zipfile.ZipFile(path) as archive:
                raw_names = archive.namelist()
                names = set(raw_names)
                if len(raw_names) != len(names):
                    raise ValueError("Pacote contém caminho duplicado.")
                if "manifesto.json" not in names:
                    raise ValueError("Pacote sem manifesto fiscal.")
                infos = archive.infolist()
                if any(info.file_size > 100 * 1024 * 1024 for info in infos):
                    raise ValueError("Pacote contém arquivo interno acima do limite seguro.")
                if sum(info.file_size for info in infos) > 4 * 1024 * 1024 * 1024:
                    raise ValueError("Conteúdo descompactado do pacote excede o limite seguro.")
                normalized_names: set[str] = set()
                for name in names:
                    normalized = name.replace("\\", "/")
                    if (
                        normalized.startswith("/") or ".." in normalized.split("/")
                        or not normalized or normalized.endswith("/")
                    ):
                        raise ValueError("Pacote contém caminho interno inseguro.")
                    folded = normalized.casefold()
                    if folded in normalized_names:
                        raise ValueError("Pacote contém caminho repetido ou ambíguo.")
                    normalized_names.add(folded)
                try:
                    manifest = json.loads(archive.read("manifesto.json").decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise ValueError("Manifesto fiscal inválido.") from exc
                if manifest.get("product") != "NabiCode":
                    raise ValueError("Pacote contábil incompatível com esta versão do NabiCode.")
                if manifest.get("version") == 1:
                    raise ValueError(
                        "Pacote LEGADO: o manifesto v1 não prova a integridade de todos os arquivos. "
                        "Gere novamente no layout v2."
                    )
                if (
                    manifest.get("version") != 2
                    or manifest.get("layout") != "nabicode.accounting-package.v2"
                    or (manifest.get("integrity") or {}).get("algorithm") != "SHA-256"
                ):
                    raise ValueError("Manifesto contábil v2 incompatível ou inconsistente.")
                period = manifest.get("period")
                issuer = manifest.get("issuer")
                if not isinstance(period, dict) or not isinstance(issuer, dict):
                    raise ValueError("Manifesto contábil v2 não informa período ou emitente válidos.")
                try:
                    period_start = datetime.fromisoformat(str(period.get("start") or "")).date()
                    period_end = datetime.fromisoformat(str(period.get("end") or "")).date()
                except ValueError as exc:
                    raise ValueError("Período do manifesto contábil é inválido.") from exc
                if period_start > period_end:
                    raise ValueError("Período do manifesto contábil está invertido.")

                file_entries = manifest.get("files")
                if not isinstance(file_entries, list):
                    raise ValueError("Manifesto v2 não contém catálogo de arquivos.")
                by_name: dict[str, str] = {}
                for item in file_entries:
                    if not isinstance(item, dict):
                        raise ValueError("Catálogo de arquivos do manifesto é inválido.")
                    name = str(item.get("file") or "")
                    expected = str(item.get("sha256") or "").casefold()
                    if not re.fullmatch(r"[0-9a-f]{64}", expected):
                        raise ValueError(f"Hash ausente ou inválido no manifesto: {name or '<sem caminho>'}")
                    if name in by_name:
                        raise ValueError(f"Manifesto contém caminho duplicado: {name}")
                    by_name[name] = expected
                expected_names = set(by_name) | {"manifesto.json"}
                if names != expected_names:
                    missing = sorted(expected_names - names)
                    extra = sorted(names - expected_names)
                    detail = f" ausentes={missing}" if missing else ""
                    detail += f" extras={extra}" if extra else ""
                    raise ValueError(f"Conteúdo do pacote diverge do manifesto.{detail}")
                for name, expected in by_name.items():
                    if name not in names:
                        raise ValueError(f"Arquivo fiscal ausente no pacote: {name}")
                    data = archive.read(name)
                    if hashlib.sha256(data).hexdigest() != expected:
                        raise ValueError(f"Arquivo fiscal alterado ou corrompido: {name}")
                references: dict[str, tuple[str, dict[str, Any]]] = {}
                for section in ("documents", "received_documents"):
                    rows = manifest.get(section)
                    if not isinstance(rows, list):
                        raise ValueError(f"Seção {section} do manifesto é inválida.")
                    for item in rows:
                        if not isinstance(item, dict):
                            raise ValueError(f"Registro inválido na seção {section}.")
                        name = str(item.get("file") or "")
                        self._accounting_reference(references, name, section, item, by_name)
                        if str(item.get("sha256") or "").casefold() != by_name.get(name):
                            raise ValueError(f"Hash divergente entre seções do manifesto: {name}")
                events = manifest.get("events")
                if not isinstance(events, list):
                    raise ValueError("Seção events do manifesto é inválida.")
                for event in events:
                    if not isinstance(event, dict) or not isinstance(event.get("files"), list):
                        raise ValueError("Registro de evento do manifesto é inválido.")
                    for item in event["files"]:
                        if not isinstance(item, dict) or item.get("role") not in {"ENVIO", "RETORNO"}:
                            raise ValueError("Arquivo de evento não informa função válida.")
                        name = str(item.get("file") or "")
                        self._accounting_reference(references, name, "events", event, by_name)
                        if str(item.get("sha256") or "").casefold() != by_name.get(name):
                            raise ValueError(f"Hash de evento diverge do catálogo: {name}")
                unreferenced = set(by_name) - set(references) - {"LEIA-ME.txt"}
                if unreferenced:
                    raise ValueError(f"Manifesto contém arquivo fiscal sem vínculo: {sorted(unreferenced)}")
                if "LEIA-ME.txt" not in by_name:
                    raise ValueError("Pacote v2 não contém instruções íntegras.")

                for name, (section, item) in references.items():
                    data = archive.read(name)
                    self._validate_accounting_xml_semantics(
                        data, section=section, item=item, issuer=issuer,
                        period_start=period_start, period_end=period_end,
                    )
        except zipfile.BadZipFile as exc:
            raise ValueError("O arquivo não é um pacote ZIP válido.") from exc
        return {
            "valid": True, "layout": "V2", "integrity": "SHA256_COMPLETA_SEM_ASSINATURA",
            "non_repudiation": False, "files_checked": len(by_name),
            "period_start": str(period_start), "period_end": str(period_end),
        }

    @staticmethod
    def _accounting_reference(
        references: dict[str, tuple[str, dict[str, Any]]], name: str,
        section: str, item: dict[str, Any], catalog: Mapping[str, str],
    ) -> None:
        if not name or name not in catalog:
            raise ValueError(f"Arquivo listado fora do catálogo v2: {name or '<sem caminho>'}")
        if name in references:
            raise ValueError(f"Arquivo fiscal possui vínculo duplicado: {name}")
        references[name] = (section, item)

    @classmethod
    def _validate_accounting_xml_semantics(
        cls, data: bytes, *, section: str, item: Mapping[str, Any],
        issuer: Mapping[str, Any], period_start: Any, period_end: Any,
    ) -> None:
        if etree is None:
            raise RuntimeError("A validação semântica do pacote exige lxml.")
        try:
            root = etree.fromstring(data, parser=etree.XMLParser(resolve_entities=False, no_network=True))
        except etree.XMLSyntaxError as exc:
            raise ValueError("Pacote contém XML fiscal inválido.") from exc
        text = lambda path: str(root.xpath(f"string({path})") or "").strip()
        xml_key = cls._normalize_access_key(
            text("(//*[local-name()='chNFe'])[1]")
            or text("(//*[local-name()='infNFe'])[1]/@Id").removeprefix("NFe")
        )
        expected_key = cls._normalize_access_key(item.get("access_key"))
        # Respostas de evento podem omitir chNFe; quando a chave existir no XML,
        # contudo, ela precisa coincidir com a referência do manifesto.
        if len(expected_key) == 44 and (
            (section != "events" and xml_key != expected_key)
            or (section == "events" and bool(xml_key) and xml_key != expected_key)
        ):
            raise ValueError(f"Chave do XML diverge do manifesto: {expected_key}")
        if section == "documents":
            status = str(item.get("status") or "").upper()
            if status not in {"AUTORIZADO", "CANCELADO"}:
                raise ValueError("Status de documento fiscal inválido no manifesto.")
            model = text("(//*[local-name()='ide']/*[local-name()='mod'])[1]")
            if model and model != str(item.get("model") or ""):
                raise ValueError(f"Modelo fiscal diverge do manifesto: {expected_key}")
            protocol = text("(//*[local-name()='protNFe']//*[local-name()='nProt'])[1]")
            if protocol != str(item.get("protocol") or ""):
                raise ValueError(f"Protocolo fiscal diverge do manifesto: {expected_key}")
            configured_cnpj = cls._normalize_cnpj(issuer.get("cnpj"))
            xml_cnpj = cls._normalize_cnpj(text("(//*[local-name()='emit']/*[local-name()='CNPJ'])[1]"))
            if configured_cnpj and xml_cnpj and configured_cnpj != xml_cnpj:
                raise ValueError(f"CNPJ emitente diverge do manifesto: {expected_key}")
        if section in {"documents", "received_documents"}:
            issued = text(
                "(//*[local-name()='ide']/*[local-name()='dhEmi'] | "
                "//*[local-name()='ide']/*[local-name()='dEmi'] | //*[local-name()='dhEmi'])[1]"
            )
            if issued:
                try:
                    issued_date = datetime.fromisoformat(issued.replace("Z", "+00:00")).date()
                except ValueError as exc:
                    raise ValueError(f"Data de emissão inválida no XML: {expected_key}") from exc
                if not period_start <= issued_date <= period_end:
                    raise ValueError(f"XML fora do período declarado: {expected_key}")
        if section == "events":
            protocol = text("(//*[local-name()='nProt'])[1]")
            expected_protocol = str(item.get("protocol") or "")
            if protocol and expected_protocol and protocol != expected_protocol:
                raise ValueError(f"Protocolo de evento diverge do manifesto: {expected_key}")
            status_code = text("(//*[local-name()='cStat'])[1]")
            expected_status = str(item.get("status_code") or "")
            if status_code and expected_status and status_code != expected_status:
                raise ValueError(f"Status de evento diverge do manifesto: {expected_key}")

    def export_fiscal_report_csv(
        self, *, start_date: str | datetime, end_date: str | datetime,
        output_path: str | Path, include_homologation: bool = False,
        statuses: Sequence[str] = ("AUTORIZADO", "CANCELADO", "INUTILIZADO"),
    ) -> dict[str, Any]:
        """Exporta relatório legível pelo Excel derivado dos XMLs e eventos persistidos."""
        self._require_dependency("lxml")

        def as_date(value: str | datetime):
            return value.date() if isinstance(value, datetime) else datetime.fromisoformat(str(value)).date()

        start, end = as_date(start_date), as_date(end_date)
        if start > end:
            raise ValueError("A data inicial não pode ser posterior à data final.")
        wanted = {str(status).strip().upper() for status in statuses}
        rows: list[dict[str, str]] = []

        def xml_text(root: Any, path: str) -> str:
            return str(root.xpath(f"string({path})") or "").strip()

        for document in self.list_documents():
            status = str(document.get("status") or "").upper()
            if status not in wanted or status not in {"AUTORIZADO", "CANCELADO"}:
                continue
            environment = str(document.get("environment") or "").upper()
            if environment != "PRODUCAO" and not include_homologation:
                continue
            path = Path(str(document.get("processed_path") or ""))
            if not path.is_file():
                raise ValueError(f"XML fiscal {document.get('access_key', '')} não foi localizado.")
            integrity = self.verify_document_integrity(
                access_key=str(document.get("access_key") or ""), environment=environment
            )
            if not integrity["valid"]:
                raise ValueError(f"XML fiscal {document.get('access_key', '')} falhou na integridade.")
            root = etree.fromstring(
                path.read_bytes(), parser=etree.XMLParser(resolve_entities=False, no_network=True)
            )
            issued = xml_text(root, "//*[local-name()='ide']/*[local-name()='dhEmi'][1]") or xml_text(
                root, "//*[local-name()='ide']/*[local-name()='dEmi'][1]"
            )
            try:
                issued_date = datetime.fromisoformat(issued.replace("Z", "+00:00")).date()
            except ValueError:
                issued_date = datetime.fromisoformat(str(document.get("created_at") or "")).date()
            if not start <= issued_date <= end:
                continue
            rows.append({
                "status": status,
                "modelo": str(document.get("model") or ""),
                "numero": xml_text(root, "//*[local-name()='ide']/*[local-name()='nNF'][1]"),
                "serie": xml_text(root, "//*[local-name()='ide']/*[local-name()='serie'][1]"),
                "data_emissao": issued_date.isoformat(),
                "chave": str(document.get("access_key") or ""),
                "cnpj_cliente": xml_text(root, "//*[local-name()='dest']/*[local-name()='CNPJ'][1]"),
                "cpf_cliente": xml_text(root, "//*[local-name()='dest']/*[local-name()='CPF'][1]"),
                "valor_bruto": xml_text(root, "//*[local-name()='ICMSTot']/*[local-name()='vNF'][1]"),
                "base_icms": xml_text(root, "//*[local-name()='ICMSTot']/*[local-name()='vBC'][1]"),
                "valor_icms": xml_text(root, "//*[local-name()='ICMSTot']/*[local-name()='vICMS'][1]"),
                "valor_ipi": xml_text(root, "//*[local-name()='ICMSTot']/*[local-name()='vIPI'][1]"),
                "valor_pis": xml_text(root, "//*[local-name()='ICMSTot']/*[local-name()='vPIS'][1]"),
                "valor_cofins": xml_text(root, "//*[local-name()='ICMSTot']/*[local-name()='vCOFINS'][1]"),
                "valor_ibs": xml_text(root, "//*[local-name()='IBSCBSTot']/*[local-name()='vIBS'][1]"),
                "valor_cbs": xml_text(root, "//*[local-name()='IBSCBSTot']/*[local-name()='vCBS'][1]"),
                "protocolo": str(document.get("protocol") or ""),
            })
        if "INUTILIZADO" in wanted:
            for event in self.list_events():
                if str(event.get("event_type") or "").upper() != "INUTILIZACAO" or not event.get("success"):
                    continue
                environment = str(event.get("environment") or "").upper()
                if environment != "PRODUCAO" and not include_homologation:
                    continue
                created = datetime.fromisoformat(str(event.get("created_at") or "")).date()
                if start <= created <= end:
                    rows.append({
                        "status": "INUTILIZADO", "modelo": str(event.get("model") or ""),
                        "numero": f"{event.get('start_number', '')}-{event.get('end_number', '')}",
                        "serie": str(event.get("series") or ""), "data_emissao": created.isoformat(),
                        "chave": "", "cnpj_cliente": "", "cpf_cliente": "",
                        "valor_bruto": "", "base_icms": "", "valor_icms": "",
                        "valor_ipi": "", "valor_pis": "", "valor_cofins": "",
                        "valor_ibs": "", "valor_cbs": "", "protocolo": str(event.get("protocol") or ""),
                    })
        columns = (
            "status", "modelo", "numero", "serie", "data_emissao", "chave",
            "cnpj_cliente", "cpf_cliente", "valor_bruto", "base_icms", "valor_icms",
            "valor_ipi", "valor_pis", "valor_cofins", "valor_ibs", "valor_cbs", "protocolo",
        )
        destination = Path(output_path)
        if destination.suffix.lower() != ".csv":
            destination = destination.with_suffix(".csv")
        destination.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=columns, delimiter=";")
                writer.writeheader()
                writer.writerows(rows)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, destination)
        except Exception:
            Path(temp_name).unlink(missing_ok=True)
            raise
        return {"path": str(destination), "rows": len(rows)}

    def list_documents(self) -> list[dict[str, Any]]:
        value = self._get_setting(self.DOCUMENT_INDEX_KEY)
        if not value:
            return []
        try:
            rows = json.loads(value)
        except (TypeError, ValueError):
            return []
        return [dict(row) for row in rows if isinstance(row, dict)]


    @staticmethod
    def calculate_access_key_digit(base43: str) -> str:
        normalized = FiscalService._normalize_access_key(base43)
        if len(normalized) != 43 or not re.fullmatch(r"[0-9]{6}[A-Z0-9]{12}[0-9]{25}", normalized):
            raise ValueError("A base da chave de acesso possui formato inválido.")
        weights = [2, 3, 4, 5, 6, 7, 8, 9]
        total = sum((ord(ch) - 48) * weights[i % len(weights)] for i, ch in enumerate(reversed(normalized)))
        remainder = total % 11
        digit = 11 - remainder
        return "0" if digit in (10, 11) else str(digit)

    def build_access_key(
        self, *, state_code: str, issued_at: datetime, cnpj: str, model: str,
        series: int, number: int, emission_type: int = 1, numeric_code: str | int = "00000000"
    ) -> str:
        model = str(model).zfill(2)
        if model not in self.VALID_MODELS:
            raise ValueError("Modelo fiscal inválido.")
        normalized_cnpj = self._normalize_cnpj(cnpj)
        if not self._is_valid_cnpj(normalized_cnpj):
            raise ValueError("CNPJ inválido para gerar a chave de acesso.")
        state = self._digits(state_code).zfill(2)
        if len(state) != 2:
            raise ValueError("Código numérico da UF inválido.")
        code = self._digits(numeric_code).zfill(8)[-8:]
        base = (
            f"{state}{issued_at:%y%m}{normalized_cnpj}{model}{int(series):03d}"
            f"{int(number):09d}{int(emission_type)}{code}"
        )
        return base + self.calculate_access_key_digit(base)


    def validate_document_rules(
        self, *, issuer: Mapping[str, Any], recipient: Mapping[str, Any],
        items: Sequence[Mapping[str, Any]], document: Mapping[str, Any]
    ) -> list[str]:
        problems: list[str] = []
        model = str(document.get("model", "55")).zfill(2)
        crt = int(issuer.get("tax_regime_code", self.TAX_REGIME_CODES.get(str(issuer.get("tax_regime", "SIMPLES")).upper(), 1)))
        if model not in self.VALID_MODELS:
            problems.append("Modelo fiscal deve ser 55 ou 65.")
        if crt not in {1, 2, 3, 4}:
            problems.append("CRT do emitente deve ser 1, 2, 3 ou 4.")
        state = str(issuer.get("state", "")).strip().upper()
        expected_state_code = self.STATE_CODES.get(state, "")
        informed_state_code = self._digits(document.get("state_code"))
        if expected_state_code and informed_state_code and expected_state_code != informed_state_code.zfill(2):
            problems.append("Código da UF do documento não corresponde à UF do emitente.")
        operation_type = int(document.get("operation_type", 1))
        destination = int(document.get("destination", 1))
        strict_tax_profile = bool(document.get("strict_tax_profile"))
        if operation_type not in {0, 1}:
            problems.append("Tipo de operação deve ser 0 (entrada) ou 1 (saída).")
        if destination not in {1, 2, 3}:
            problems.append("Destino da operação deve ser 1, 2 ou 3.")
        if destination == 3 and not str(recipient.get("foreign_id") or "").strip():
            problems.append("Operação com exterior exige identificação estrangeira do destinatário.")
        if model == "65":
            if int(document.get("final_consumer", 1)) != 1:
                problems.append("NFC-e exige consumidor final.")
            if int(document.get("presence", 1)) not in {1, 2, 3, 4, 5, 9}:
                problems.append("Indicador de presença inválido para NFC-e.")
            if operation_type != 1:
                problems.append("NFC-e somente pode representar operação de saída.")
        recipient_document = self._normalize_tax_document(recipient.get("document"))
        if recipient_document and len(recipient_document) not in {11, 14}:
            problems.append("Documento do destinatário deve ser CPF ou CNPJ válido em tamanho.")
        for index, item in enumerate(items, 1):
            prefix = f"Item {index}"
            if not str(item.get("code", "")).strip():
                problems.append(f"{prefix}: código é obrigatório.")
            if not str(item.get("description", "")).strip():
                problems.append(f"{prefix}: descrição é obrigatória.")
            ncm = self._digits(item.get("ncm"))
            if len(ncm) != 8 or ncm == "00000000":
                problems.append(f"{prefix}: NCM deve possuir 8 dígitos e não pode ser genérico.")
            cfop = self._digits(item.get("cfop"))
            if len(cfop) != 4 or cfop[0] not in "123567":
                problems.append(f"{prefix}: CFOP inválido.")
            if operation_type == 1 and cfop and cfop[0] not in "567":
                problems.append(f"{prefix}: CFOP de saída deve iniciar por 5, 6 ou 7.")
            if operation_type == 0 and cfop and cfop[0] not in "123":
                problems.append(f"{prefix}: CFOP de entrada deve iniciar por 1, 2 ou 3.")
            if not str(item.get("unit", "")).strip():
                problems.append(f"{prefix}: unidade é obrigatória.")
            try:
                quantity = Decimal(str(item.get("quantity", 0)))
                unit_price = Decimal(str(item.get("unit_price", 0)))
            except Exception:
                problems.append(f"{prefix}: quantidade ou preço não é numérico.")
                continue
            if quantity <= 0:
                problems.append(f"{prefix}: quantidade deve ser maior que zero.")
            if unit_price < 0:
                problems.append(f"{prefix}: preço não pode ser negativo.")
            origin = self._digits(item.get("origin"))
            if strict_tax_profile and origin not in set("012345678"):
                problems.append(f"{prefix}: origem da mercadoria deve ficar entre 0 e 8.")
            if crt in {1, 2, 4}:
                csosn = self._digits(item.get("csosn") or ("" if strict_tax_profile else "102"))
                if csosn not in FiscalProductProfile.SIMPLE_CSOSN:
                    problems.append(f"{prefix}: CSOSN suportado deve ser 102, 103, 300, 400 ou 500.")
            else:
                cst = self._digits(item.get("cst"))
                if cst not in FiscalProductProfile.NORMAL_ICMS_CST:
                    problems.append(f"{prefix}: CST suportado deve ser 00, 40, 41, 50 ou 60.")
                if cst == "00":
                    try:
                        rate = Decimal(str(item.get("icms_rate", "0")))
                    except Exception:
                        rate = Decimal("-1")
                    if rate < 0 or rate > 100:
                        problems.append(f"{prefix}: alíquota de ICMS inválida.")
            contribution_codes = (
                FiscalProductProfile.CONTRIBUTION_TAXED
                | FiscalProductProfile.CONTRIBUTION_UNTAXED
                | FiscalProductProfile.CONTRIBUTION_OTHER
            )
            for field, label in (("pis_cst", "PIS"), ("cofins_cst", "COFINS")):
                if strict_tax_profile and self._digits(item.get(field)) not in contribution_codes:
                    problems.append(f"{prefix}: CST {label} inválido ou ausente.")
        purpose = int(document.get("purpose", 1) or 1)
        referenced = [self._normalize_access_key(value) for value in document.get("referenced_access_keys", []) or []]
        if purpose == 4:
            if model != "55":
                problems.append("NF-e de devolução deve utilizar o modelo 55.")
            if not referenced:
                problems.append("NF-e de devolução deve referenciar a chave da nota original.")
        for key in referenced:
            if len(key) != 44:
                problems.append("Chave de NF-e referenciada deve possuir 44 dígitos.")
        payment_code = self._digits(document.get("payment_code", "01")).zfill(2)
        if len(payment_code) != 2:
            problems.append("Código de pagamento inválido.")
        return problems

    def build_document_xml(
        self, *, issuer: Mapping[str, Any], recipient: Mapping[str, Any],
        items: Sequence[Mapping[str, Any]], document: Mapping[str, Any]
    ) -> tuple[bytes, str]:
        """Gera um rascunho XML NF-e/NFC-e sem transmitir.

        A validação oficial depende dos XSD e regras vigentes da SEFAZ; este método
        produz a estrutura de trabalho e nunca marca o documento como autorizado.
        """
        model = str(document.get("model", "55")).zfill(2)
        if model not in self.VALID_MODELS:
            raise ValueError("Modelo fiscal deve ser 55 ou 65.")
        if not items:
            raise ValueError("Documento fiscal precisa possuir ao menos um item.")
        profile_problems = self.validate_fiscal_profile(issuer=issuer, model=model)
        rule_problems = self.validate_document_rules(issuer=issuer, recipient=recipient, items=items, document=document)
        problems = profile_problems + rule_problems
        if problems:
            raise ValueError("; ".join(problems))
        cnpj = self._normalize_cnpj(issuer.get("cnpj"))
        issued_at = document.get("issued_at") or datetime.now().astimezone()
        if not isinstance(issued_at, datetime):
            issued_at = datetime.fromisoformat(str(issued_at))
        key = str(document.get("access_key") or "")
        if not key:
            key = self.build_access_key(
                state_code=str(document.get("state_code", "29")), issued_at=issued_at, cnpj=cnpj,
                model=model, series=int(document.get("series", 1)), number=int(document.get("number", 1)),
                emission_type=int(document.get("emission_type", 1)), numeric_code=document.get("numeric_code", "00000000")
            )
        if len(self._normalize_access_key(key)) != 44:
            raise ValueError("Chave de acesso inválida.")
        ns = "http://www.portalfiscal.inf.br/nfe"
        root = etree.Element(etree.QName(ns, "NFe"), nsmap={None: ns})
        inf = etree.SubElement(root, etree.QName(ns, "infNFe"), Id=f"NFe{key}", versao="4.00")
        ide = etree.SubElement(inf, etree.QName(ns, "ide"))
        def el(parent, name, value):
            node = etree.SubElement(parent, etree.QName(ns, name)); node.text = str(value); return node
        el(ide, "cUF", str(document.get("state_code", "29")).zfill(2))
        el(ide, "cNF", self._digits(document.get("numeric_code", key[35:43])).zfill(8)[-8:])
        el(ide, "natOp", document.get("nature", "VENDA"))
        el(ide, "mod", model); el(ide, "serie", int(document.get("series", 1)))
        el(ide, "nNF", int(document.get("number", 1)))
        el(ide, "dhEmi", issued_at.astimezone().isoformat(timespec="seconds"))
        el(ide, "tpNF", int(document.get("operation_type", 1)))
        el(ide, "idDest", int(document.get("destination", 1)))
        el(ide, "cMunFG", self._digits(issuer.get("city_code")))
        el(ide, "tpImp", 4 if model == "65" else 1)
        el(ide, "tpEmis", int(document.get("emission_type", 1)))
        el(ide, "cDV", key[-1]); el(ide, "tpAmb", 2 if str(document.get("environment", "HOMOLOGACAO")).upper()=="HOMOLOGACAO" else 1)
        el(ide, "finNFe", int(document.get("purpose", 1))); el(ide, "indFinal", int(document.get("final_consumer", 1)))
        el(ide, "indPres", int(document.get("presence", 1))); el(ide, "procEmi", 0); el(ide, "verProc", document.get("app_version", "NabiCode"))
        for referenced_key in document.get("referenced_access_keys", []) or []:
            digits = self._normalize_access_key(referenced_key)
            if len(digits) != 44:
                raise ValueError("Chave de NF-e referenciada deve possuir 44 dígitos.")
            nfref = etree.SubElement(ide, etree.QName(ns, "NFref"))
            el(nfref, "refNFe", digits)
        emit = etree.SubElement(inf, etree.QName(ns, "emit")); el(emit, "CNPJ", cnpj); el(emit, "xNome", issuer.get("name", ""))
        ender = etree.SubElement(emit, etree.QName(ns, "enderEmit"))
        for name, key_name in (("xLgr","street"),("nro","number"),("xBairro","district"),("cMun","city_code"),("xMun","city"),("UF","state"),("CEP","zip_code")):
            value=issuer.get(key_name);
            if value not in (None, ""): el(ender, name, self._digits(value) if name in {"cMun","CEP"} else value)
        el(emit, "IE", self._digits(issuer.get("state_registration"))); el(emit, "CRT", int(issuer.get("tax_regime_code", 1)))
        doc_rec = self._normalize_tax_document(recipient.get("document"))
        foreign_id = str(recipient.get("foreign_id") or "").strip()
        has_recipient = len(doc_rec) in {11, 14} or bool(foreign_id)
        is_homologation = (
            str(document.get("environment") or "HOMOLOGACAO").upper()
            == "HOMOLOGACAO"
        )
        if has_recipient and is_homologation:
            doc_rec = self.HOMOLOGATION_RECIPIENT_CNPJ
            foreign_id = ""
        if has_recipient:
            dest = etree.SubElement(inf, etree.QName(ns, "dest"))
            if len(doc_rec)==14: el(dest, "CNPJ", doc_rec)
            elif len(doc_rec)==11: el(dest, "CPF", doc_rec)
            else: el(dest, "idEstrangeiro", foreign_id)
            recipient_name = str(recipient.get("name") or "").strip()
            if is_homologation:
                recipient_name = self.HOMOLOGATION_RECIPIENT_NAME
            if recipient_name:
                el(dest, "xNome", recipient_name)
            if not is_homologation and any(
                recipient.get(key) for key in ("street", "city_code", "state", "zip_code")
            ):
                address = etree.SubElement(dest, etree.QName(ns, "enderDest"))
                for name, key_name in (("xLgr","street"),("nro","number"),("xBairro","district"),("cMun","city_code"),("xMun","city"),("UF","state"),("CEP","zip_code")):
                    value = recipient.get(key_name)
                    if value not in (None, ""):
                        el(address, name, self._digits(value) if name in {"cMun", "CEP"} else value)
            recipient_ie = "" if is_homologation else self._digits(
                recipient.get("state_registration")
            )
            taxpayer_indicator = 9 if is_homologation else recipient.get(
                "state_taxpayer_indicator"
            )
            if taxpayer_indicator in (None, ""):
                taxpayer_indicator = 1 if recipient_ie else 2 if recipient.get("icms_exempt") else 9
            taxpayer_indicator = int(taxpayer_indicator)
            if taxpayer_indicator not in {1, 2, 9}:
                raise ValueError("Indicador de inscrição estadual do destinatário deve ser 1, 2 ou 9.")
            if taxpayer_indicator == 1 and not recipient_ie:
                raise ValueError("Destinatário contribuinte de ICMS exige inscrição estadual.")
            el(dest, "indIEDest", taxpayer_indicator)
            if recipient_ie:
                el(dest, "IE", recipient_ie)
            if not is_homologation and recipient.get("email"):
                el(dest, "email", str(recipient.get("email")).strip())
        total_products = Decimal("0")
        total_icms_base = Decimal("0")
        total_icms = Decimal("0")
        total_st_base = Decimal("0")
        total_st = Decimal("0")
        total_fcp_st = Decimal("0")
        total_difal_destination = Decimal("0")
        total_difal_origin = Decimal("0")
        total_fcp_destination = Decimal("0")
        total_pis = Decimal("0")
        total_cofins = Decimal("0")
        total_ipi = Decimal("0")
        total_ipi_return = Decimal("0")
        total_ibs_cbs_base = Decimal("0")
        total_ibs_uf = Decimal("0")
        total_ibs_city = Decimal("0")
        total_cbs = Decimal("0")
        for index, item in enumerate(items, 1):
            qty=Decimal(str(item.get("quantity", 0))); unit=Decimal(str(item.get("unit_price", 0)))
            if qty <= 0 or unit < 0: raise ValueError(f"Item {index}: quantidade/preço inválidos.")
            value=(qty*unit).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP); total_products += value
            det=etree.SubElement(inf, etree.QName(ns,"det"), nItem=str(index)); prod=etree.SubElement(det, etree.QName(ns,"prod"))
            el(prod,"cProd",item.get("code",index)); el(prod,"cEAN",item.get("ean") or "SEM GTIN"); el(prod,"xProd",str(item.get("description","")).upper())
            el(prod,"NCM",self._digits(item.get("ncm")) or "00000000")
            cest = self._digits(item.get("cest"))
            if cest:
                el(prod, "CEST", cest)
            benefit_code = str(item.get("benefit_code") or "").strip().upper()
            if benefit_code:
                if benefit_code != "SEM CBENEF" and (
                    len(benefit_code) not in {8, 10}
                    or any(character.isspace() or not 33 <= ord(character) <= 255 for character in benefit_code)
                ):
                    raise ValueError(
                        f"Item {index}: código de benefício fiscal deve possuir 8 ou 10 caracteres sem espaços."
                    )
                el(prod, "cBenef", benefit_code)
            el(prod,"CFOP",item.get("cfop") or "5102"); el(prod,"uCom",str(item.get("unit","UN")).upper())
            el(prod,"qCom",f"{qty:.4f}"); el(prod,"vUnCom",f"{unit:.10f}"); el(prod,"vProd",f"{value:.2f}"); el(prod,"cEANTrib",item.get("ean") or "SEM GTIN")
            el(prod,"uTrib",str(item.get("unit","UN")).upper()); el(prod,"qTrib",f"{qty:.4f}"); el(prod,"vUnTrib",f"{unit:.10f}"); el(prod,"indTot",1)
            imposto=etree.SubElement(det, etree.QName(ns,"imposto")); icms=etree.SubElement(imposto, etree.QName(ns,"ICMS"))
            crt = int(issuer.get("tax_regime_code", 1))
            explicit_icms_base = Decimal(str(item.get("icms_base", 0))).quantize(Decimal("0.01"))
            explicit_icms_value = Decimal(str(item.get("icms_value", 0))).quantize(Decimal("0.01"))
            if crt in {1, 2, 4}:
                csosn = self._digits(item.get("csosn") or "102")
                if csosn in {"102", "103", "300", "400"}:
                    icmssn=etree.SubElement(icms, etree.QName(ns,"ICMSSN102")); el(icmssn,"orig",int(item.get("origin",0) or 0)); el(icmssn,"CSOSN",csosn)
                elif csosn == "500":
                    icmssn=etree.SubElement(icms, etree.QName(ns,"ICMSSN500")); el(icmssn,"orig",int(item.get("origin",0) or 0)); el(icmssn,"CSOSN",csosn)
                elif csosn in {"201", "202", "203"}:
                    mva = Decimal(str(item.get("st_mva", 0))).quantize(Decimal("0.01"))
                    reduction = Decimal(str(item.get("icms_base_reduction", 0))).quantize(Decimal("0.01"))
                    st_rate = Decimal(str(item.get("st_rate", 0))).quantize(Decimal("0.01"))
                    fcp_rate = Decimal(str(item.get("fcp_st_rate", 0))).quantize(Decimal("0.01"))
                    if any(rate < 0 or rate > 100 for rate in (mva, reduction, st_rate, fcp_rate)):
                        raise ValueError(f"Item {index}: parâmetros de ICMS-ST devem ficar entre 0 e 100%.")
                    reduced = value * (Decimal("1") - reduction / Decimal("100"))
                    st_base = (reduced * (Decimal("1") + mva / Decimal("100"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    st_value = (st_base * st_rate / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    fcp_value = (st_base * fcp_rate / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    group_name = "ICMSSN201" if csosn == "201" else "ICMSSN202"
                    icmssn=etree.SubElement(icms, etree.QName(ns,group_name)); el(icmssn,"orig",int(item.get("origin",0) or 0)); el(icmssn,"CSOSN",csosn)
                    el(icmssn,"modBCST",4); el(icmssn,"pMVAST",f"{mva:.2f}")
                    if reduction > 0: el(icmssn,"pRedBCST",f"{reduction:.2f}")
                    el(icmssn,"vBCST",f"{st_base:.2f}"); el(icmssn,"pICMSST",f"{st_rate:.2f}"); el(icmssn,"vICMSST",f"{st_value:.2f}")
                    if fcp_rate > 0:
                        el(icmssn,"vBCFCPST",f"{st_base:.2f}"); el(icmssn,"pFCPST",f"{fcp_rate:.2f}"); el(icmssn,"vFCPST",f"{fcp_value:.2f}")
                    if csosn == "201":
                        credit_rate = Decimal(str(item.get("sn_credit_rate", 0))).quantize(Decimal("0.01"))
                        if credit_rate < 0 or credit_rate > 100:
                            raise ValueError(f"Item {index}: crédito do Simples deve ficar entre 0 e 100%.")
                        credit_value = (value * credit_rate / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                        el(icmssn,"pCredSN",f"{credit_rate:.2f}"); el(icmssn,"vCredICMSSN",f"{credit_value:.2f}")
                    total_st_base += st_base; total_st += st_value; total_fcp_st += fcp_value
                else:
                    raise ValueError(f"Item {index}: CSOSN {csosn or 'não informado'} não possui gerador XML homologado.")
            else:
                cst = self._digits(item.get("cst"))
                if cst == "00":
                    rate = Decimal(str(item.get("icms_rate", "0"))).quantize(Decimal("0.01"))
                    tax_base = explicit_icms_base if explicit_icms_base > 0 else value
                    tax_value = explicit_icms_value if explicit_icms_value > 0 else (tax_base * rate / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    total_icms_base += tax_base; total_icms += tax_value
                    icms00=etree.SubElement(icms, etree.QName(ns,"ICMS00")); el(icms00,"orig",int(item.get("origin",0))); el(icms00,"CST","00")
                    el(icms00,"modBC",int(item.get("bc_mode",3))); el(icms00,"vBC",f"{tax_base:.2f}"); el(icms00,"pICMS",f"{rate:.2f}"); el(icms00,"vICMS",f"{tax_value:.2f}")
                elif cst in {"40", "41", "50"}:
                    icms40=etree.SubElement(icms, etree.QName(ns,"ICMS40")); el(icms40,"orig",int(item.get("origin",0))); el(icms40,"CST",cst)
                elif cst == "60":
                    icms60=etree.SubElement(icms, etree.QName(ns,"ICMS60")); el(icms60,"orig",int(item.get("origin",0))); el(icms60,"CST","60")
                else:
                    raise ValueError(f"Item {index}: CST ICMS {cst or 'não informado'} não possui gerador XML homologado.")

            ipi_cst = self._digits(item.get("ipi_cst"))
            if ipi_cst:
                if ipi_cst not in FiscalProductProfile.IPI_TAXED | FiscalProductProfile.IPI_UNTAXED:
                    raise ValueError(f"Item {index}: CST IPI de saída não suportado.")
                ipi_enq = self._digits(item.get("ipi_enq"))
                if len(ipi_enq) != 3:
                    raise ValueError(f"Item {index}: código de enquadramento do IPI deve possuir 3 dígitos.")
                ipi = etree.SubElement(imposto, etree.QName(ns, "IPI"))
                el(ipi, "cEnq", ipi_enq)
                if ipi_cst in FiscalProductProfile.IPI_TAXED:
                    ipi_rate = Decimal(str(item.get("ipi_rate", 0))).quantize(Decimal("0.01"))
                    if ipi_rate < 0 or ipi_rate > 100:
                        raise ValueError(f"Item {index}: alíquota de IPI deve ficar entre 0 e 100%.")
                    ipi_base = Decimal(str(item.get("ipi_base", value))).quantize(Decimal("0.01"))
                    ipi_value = Decimal(str(item.get(
                        "ipi_value", ipi_base * ipi_rate / Decimal("100")
                    ))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    if ipi_base < 0 or ipi_value < 0:
                        raise ValueError(f"Item {index}: base ou valor de IPI inválido.")
                    ipi_trib = etree.SubElement(ipi, etree.QName(ns, "IPITrib"))
                    el(ipi_trib, "CST", ipi_cst); el(ipi_trib, "vBC", f"{ipi_base:.2f}")
                    el(ipi_trib, "pIPI", f"{ipi_rate:.2f}"); el(ipi_trib, "vIPI", f"{ipi_value:.2f}")
                    total_ipi += ipi_value
                else:
                    ipi_nt = etree.SubElement(ipi, etree.QName(ns, "IPINT"))
                    el(ipi_nt, "CST", ipi_cst)

            pis_has_values = any(Decimal(str(item.get(field, 0) or 0)) > 0 for field in ("pis_value", "pis_base", "pis_rate"))
            pis_cst = self._digits(item.get("pis_cst") or ("49" if pis_has_values else "07"))
            pis_rate = Decimal(str(item.get("pis_rate", 0))).quantize(Decimal("0.01"))
            pis_base = Decimal(str(item.get("pis_base", value if pis_cst in FiscalProductProfile.CONTRIBUTION_TAXED | FiscalProductProfile.CONTRIBUTION_OTHER else 0))).quantize(Decimal("0.01"))
            pis_value = Decimal(str(item.get("pis_value", pis_base * pis_rate / Decimal("100")))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            pis=etree.SubElement(imposto, etree.QName(ns,"PIS"))
            if pis_cst in FiscalProductProfile.CONTRIBUTION_TAXED:
                pis_out=etree.SubElement(pis, etree.QName(ns,"PISAliq")); el(pis_out,"CST",pis_cst)
                el(pis_out,"vBC",f"{pis_base:.2f}"); el(pis_out,"pPIS",f"{pis_rate:.2f}"); el(pis_out,"vPIS",f"{pis_value:.2f}")
                total_pis += pis_value
            elif pis_cst in FiscalProductProfile.CONTRIBUTION_UNTAXED:
                pisnt=etree.SubElement(pis, etree.QName(ns,"PISNT")); el(pisnt,"CST",pis_cst)
            else:
                pis_out=etree.SubElement(pis, etree.QName(ns,"PISOutr")); el(pis_out,"CST",pis_cst)
                el(pis_out,"vBC",f"{pis_base:.2f}"); el(pis_out,"pPIS",f"{pis_rate:.2f}"); el(pis_out,"vPIS",f"{pis_value:.2f}")
                total_pis += pis_value

            cofins_has_values = any(Decimal(str(item.get(field, 0) or 0)) > 0 for field in ("cofins_value", "cofins_base", "cofins_rate"))
            cofins_cst = self._digits(item.get("cofins_cst") or ("49" if cofins_has_values else "07"))
            cofins_rate = Decimal(str(item.get("cofins_rate", 0))).quantize(Decimal("0.01"))
            cofins_base = Decimal(str(item.get("cofins_base", value if cofins_cst in FiscalProductProfile.CONTRIBUTION_TAXED | FiscalProductProfile.CONTRIBUTION_OTHER else 0))).quantize(Decimal("0.01"))
            cofins_value = Decimal(str(item.get("cofins_value", cofins_base * cofins_rate / Decimal("100")))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            cof=etree.SubElement(imposto, etree.QName(ns,"COFINS"))
            if cofins_cst in FiscalProductProfile.CONTRIBUTION_TAXED:
                cof_out=etree.SubElement(cof, etree.QName(ns,"COFINSAliq")); el(cof_out,"CST",cofins_cst)
                el(cof_out,"vBC",f"{cofins_base:.2f}"); el(cof_out,"pCOFINS",f"{cofins_rate:.2f}"); el(cof_out,"vCOFINS",f"{cofins_value:.2f}")
                total_cofins += cofins_value
            elif cofins_cst in FiscalProductProfile.CONTRIBUTION_UNTAXED:
                cofnt=etree.SubElement(cof, etree.QName(ns,"COFINSNT")); el(cofnt,"CST",cofins_cst)
            else:
                cof_out=etree.SubElement(cof, etree.QName(ns,"COFINSOutr")); el(cof_out,"CST",cofins_cst)
                el(cof_out,"vBC",f"{cofins_base:.2f}"); el(cof_out,"pCOFINS",f"{cofins_rate:.2f}"); el(cof_out,"vCOFINS",f"{cofins_value:.2f}")
                total_cofins += cofins_value

            difal_internal = Decimal(str(item.get("difal_internal_rate", 0))).quantize(Decimal("0.01"))
            difal_interstate = Decimal(str(item.get("difal_interstate_rate", 0))).quantize(Decimal("0.01"))
            difal_fcp = Decimal(str(item.get("difal_fcp_rate", 0))).quantize(Decimal("0.01"))
            if any(rate > 0 for rate in (difal_internal, difal_interstate, difal_fcp)):
                if int(document.get("destination", 1)) != 2 or int(document.get("final_consumer", 0)) != 1:
                    raise ValueError(f"Item {index}: DIFAL só pode ser aplicado em venda interestadual a consumidor final.")
                if any(rate < 0 or rate > 100 for rate in (difal_internal, difal_interstate, difal_fcp)) or difal_internal < difal_interstate:
                    raise ValueError(f"Item {index}: alíquotas de DIFAL/FCP inválidas.")
                destination_value = (value * (difal_internal - difal_interstate) / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                fcp_destination = (value * difal_fcp / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                difal = etree.SubElement(imposto, etree.QName(ns, "ICMSUFDest"))
                el(difal,"vBCUFDest",f"{value:.2f}"); el(difal,"vBCFCPUFDest",f"{value:.2f}")
                el(difal,"pFCPUFDest",f"{difal_fcp:.2f}"); el(difal,"pICMSUFDest",f"{difal_internal:.2f}")
                el(difal,"pICMSInter",f"{difal_interstate:.2f}"); el(difal,"pICMSInterPart","100.00")
                el(difal,"vFCPUFDest",f"{fcp_destination:.2f}"); el(difal,"vICMSUFDest",f"{destination_value:.2f}"); el(difal,"vICMSUFRemet","0.00")
                total_difal_destination += destination_value; total_fcp_destination += fcp_destination

            rtc_cst = self._digits(item.get("ibs_cbs_cst"))
            if rtc_cst:
                rtc_class = self._digits(item.get("ibs_cbs_class"))
                if rtc_cst not in {"000", "410"} or len(rtc_class) != 6:
                    raise ValueError(
                        f"Item {index}: CST ou classificação IBS/CBS não pertence à matriz suportada."
                    )
                if rtc_cst == "410":
                    if rtc_class != FiscalRtcResolver.EXPORT_CLASSIFICATION:
                        raise ValueError(
                            f"Item {index}: CST 410 de exportação exige classificação 410004."
                        )
                    rtc = etree.SubElement(imposto, etree.QName(ns, "IBSCBS"))
                    el(rtc, "CST", rtc_cst); el(rtc, "cClassTrib", rtc_class)
                else:
                    if rtc_class != FiscalRtcResolver.REGULAR_CLASSIFICATION:
                        raise ValueError(
                            f"Item {index}: CST 000 de venda regular exige classificação 000001."
                        )
                    rtc_base = Decimal(str(item.get("ibs_cbs_base", value))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    ibs_uf_rate = Decimal(str(item.get("ibs_uf_rate", 0))).quantize(Decimal("0.0001"))
                    ibs_city_rate = Decimal(str(item.get("ibs_city_rate", 0))).quantize(Decimal("0.0001"))
                    cbs_rate = Decimal(str(item.get("cbs_rate", 0))).quantize(Decimal("0.0001"))
                    if rtc_base < 0 or any(rate < 0 or rate > 100 for rate in (ibs_uf_rate, ibs_city_rate, cbs_rate)):
                        raise ValueError(f"Item {index}: base ou alíquota IBS/CBS inválida.")
                    ibs_uf_value = (rtc_base * ibs_uf_rate / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    ibs_city_value = (rtc_base * ibs_city_rate / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    cbs_value = (rtc_base * cbs_rate / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    rtc = etree.SubElement(imposto, etree.QName(ns, "IBSCBS"))
                    el(rtc, "CST", rtc_cst); el(rtc, "cClassTrib", rtc_class)
                    group = etree.SubElement(rtc, etree.QName(ns, "gIBSCBS")); el(group, "vBC", f"{rtc_base:.2f}")
                    ibs_uf = etree.SubElement(group, etree.QName(ns, "gIBSUF")); el(ibs_uf, "pIBSUF", f"{ibs_uf_rate:.4f}"); el(ibs_uf, "vIBSUF", f"{ibs_uf_value:.2f}")
                    ibs_city = etree.SubElement(group, etree.QName(ns, "gIBSMun")); el(ibs_city, "pIBSMun", f"{ibs_city_rate:.4f}"); el(ibs_city, "vIBSMun", f"{ibs_city_value:.2f}")
                    el(group, "vIBS", f"{ibs_uf_value + ibs_city_value:.2f}")
                    cbs = etree.SubElement(group, etree.QName(ns, "gCBS")); el(cbs, "pCBS", f"{cbs_rate:.4f}"); el(cbs, "vCBS", f"{cbs_value:.2f}")
                    total_ibs_cbs_base += rtc_base
                    total_ibs_uf += ibs_uf_value
                    total_ibs_city += ibs_city_value
                    total_cbs += cbs_value

            ipi_return = Decimal(str(item.get("ipi_return_value", 0))).quantize(Decimal("0.01"))
            if ipi_return > 0:
                percent = Decimal(str(item.get("devolution_percent", 100))).quantize(Decimal("0.01"))
                imposto_devol = etree.SubElement(det, etree.QName(ns,"impostoDevol"))
                el(imposto_devol,"pDevol",f"{percent:.2f}")
                ipi = etree.SubElement(imposto_devol, etree.QName(ns,"IPI")); el(ipi,"vIPIDevol",f"{ipi_return:.2f}")
                total_ipi_return += ipi_return

        total=etree.SubElement(inf, etree.QName(ns,"total")); icmstot=etree.SubElement(total, etree.QName(ns,"ICMSTot"))
        total_nf = total_products + total_ipi + total_ipi_return
        for name,val in (("vBC",total_icms_base),("vICMS",total_icms),("vICMSDeson",0),("vFCPUFDest",total_fcp_destination),("vICMSUFDest",total_difal_destination),("vICMSUFRemet",total_difal_origin),("vFCP",0),("vBCST",total_st_base),("vST",total_st),("vFCPST",total_fcp_st),("vFCPSTRet",0),("vProd",total_products),("vFrete",0),("vSeg",0),("vDesc",0),("vII",0),("vIPI",total_ipi),("vIPIDevol",total_ipi_return),("vPIS",total_pis),("vCOFINS",total_cofins),("vOutro",0),("vNF",total_nf)):
            el(icmstot,name,f"{Decimal(str(val)):.2f}")
        total_with_rtc = total_nf
        if total_ibs_cbs_base > 0:
            rtc_tot = etree.SubElement(total, etree.QName(ns, "IBSCBSTot")); el(rtc_tot, "vBCIBSCBS", f"{total_ibs_cbs_base:.2f}")
            ibs_tot = etree.SubElement(rtc_tot, etree.QName(ns, "gIBS"))
            ibs_uf_tot = etree.SubElement(ibs_tot, etree.QName(ns, "gIBSUF")); el(ibs_uf_tot, "vDif", "0.00"); el(ibs_uf_tot, "vDevTrib", "0.00"); el(ibs_uf_tot, "vIBSUF", f"{total_ibs_uf:.2f}")
            ibs_city_tot = etree.SubElement(ibs_tot, etree.QName(ns, "gIBSMun")); el(ibs_city_tot, "vDif", "0.00"); el(ibs_city_tot, "vDevTrib", "0.00"); el(ibs_city_tot, "vIBSMun", f"{total_ibs_city:.2f}")
            el(ibs_tot, "vIBS", f"{total_ibs_uf + total_ibs_city:.2f}")
            el(ibs_tot, "vCredPres", "0.00"); el(ibs_tot, "vCredPresCondSus", "0.00")
            cbs_tot = etree.SubElement(rtc_tot, etree.QName(ns, "gCBS")); el(cbs_tot, "vDif", "0.00"); el(cbs_tot, "vDevTrib", "0.00"); el(cbs_tot, "vCBS", f"{total_cbs:.2f}")
            el(cbs_tot, "vCredPres", "0.00"); el(cbs_tot, "vCredPresCondSus", "0.00")
            total_with_rtc += total_ibs_uf + total_ibs_city + total_cbs
            el(total, "vNFTot", f"{total_with_rtc:.2f}")
        transp=etree.SubElement(inf, etree.QName(ns,"transp")); el(transp,"modFrete",9)
        pag = etree.SubElement(inf, etree.QName(ns, "pag"))
        payment_rows = list(document.get("payments") or [])
        if not payment_rows:
            fallback_code = str(document.get("payment_code", "01"))
            payment_rows = [{
                "code": fallback_code,
                "amount": Decimal("0.00") if fallback_code == "90" else total_with_rtc,
                **dict(document.get("payment_detail") or {}),
            }]
        payment_total = Decimal("0.00")
        payment_codes: list[str] = []
        for payment_row in payment_rows:
            payment_code = str(payment_row.get("code", "99"))
            if len(self._digits(payment_code)) != 2:
                raise ValueError("Código de pagamento fiscal inválido.")
            try:
                payment_amount = Decimal(str(payment_row.get("amount", 0))).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
            except Exception as exc:
                raise ValueError("Valor de pagamento fiscal inválido.") from exc
            if payment_amount < 0 or (payment_amount == 0 and payment_code != "90"):
                raise ValueError("Cada pagamento fiscal deve possuir valor maior que zero.")
            if payment_code == "90" and payment_amount != 0:
                raise ValueError("Pagamento 90 — sem pagamento deve possuir valor zero.")
            payment_codes.append(payment_code)
            payment_total += payment_amount
            detpag = etree.SubElement(pag, etree.QName(ns, "detPag"))
            el(detpag, "tPag", payment_code); el(detpag, "vPag", f"{payment_amount:.2f}")
            if payment_code in {"03", "04"}:
                card = etree.SubElement(detpag, etree.QName(ns, "card"))
                integration = int(payment_row.get("integration", 2) or 2)
                if integration not in {1, 2}:
                    raise ValueError("Tipo de integração do cartão inválido.")
                el(card, "tpIntegra", integration)
                authorization = str(payment_row.get("authorization") or "").strip()
                if authorization:
                    if len(authorization) > 20:
                        raise ValueError("Autorização do cartão deve possuir no máximo 20 caracteres.")
                    el(card, "cAut", authorization)
        if "90" in payment_codes and len(payment_codes) != 1:
            raise ValueError("Sem pagamento não pode ser combinado com outra forma de pagamento.")
        if payment_codes != ["90"] and payment_total < total_with_rtc:
            raise ValueError("A soma dos pagamentos fiscais não pode ser menor que o total do documento.")
        change = (payment_total - total_with_rtc).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if change > 0:
            el(pag, "vTroco", f"{change:.2f}")
        if document.get("additional_info"):
            infad=etree.SubElement(inf, etree.QName(ns,"infAdic")); el(infad,"infCpl",document.get("additional_info"))
        if model == "65" and int(document.get("emission_type", 1)) == 1:
            self._set_nfce_supplement(
                root,
                qr_code=self.build_nfce_qr_code_v3(
                    access_key=key,
                    environment=str(document.get("environment", "HOMOLOGACAO")),
                ),
                environment=str(document.get("environment", "HOMOLOGACAO")),
            )
        return etree.tostring(root, xml_declaration=True, encoding="utf-8"), key

    def prepare_sale_items(
        self, cart_items: Sequence[Mapping[str, Any]], *, destination: int = 1,
        require_rtc: bool = True, crt: int = 1, destination_state: str = "",
        tax_regime: str = "",
    ) -> list[dict[str, Any]]:
        """Transforma o carrinho em itens fiscais usando uma única ficha por produto."""
        if destination not in {1, 2, 3}:
            raise ValueError("Destino fiscal da venda deve ser interno, interestadual ou exterior.")
        product_ids = [int(item.get("produto_id") or 0) for item in cart_items]
        if not product_ids or any(product_id <= 0 for product_id in product_ids):
            raise ValueError("Venda fiscal exige que todos os itens estejam cadastrados.")
        unique_ids = sorted(set(product_ids))
        placeholders = ",".join("?" for _ in unique_ids)
        conn = self.connection_factory()
        try:
            product_columns = {
                str(row[1]) for row in conn.execute("PRAGMA table_info(produtos)").fetchall()
            }
            ipi_select = ",".join(
                field if field in product_columns else f"'{default}' AS {field}"
                for field, default in (
                    ("fiscal_ipi_cst", ""), ("fiscal_ipi_rate", "0"),
                    ("fiscal_ipi_enq", ""),
                )
            )
            cursor = conn.execute(
                f"""SELECT id,codigo,nome,ncm,cest,cfop,
                           fiscal_origin,fiscal_csosn,fiscal_icms_cst,fiscal_icms_rate,
                           fiscal_pis_cst,fiscal_pis_rate,fiscal_cofins_cst,fiscal_cofins_rate,
                           {ipi_select},
                           fiscal_profile_source,
                           ibs_cbs_cst,ibs_cbs_class,ibs_uf_rate,ibs_city_rate,cbs_rate
                    FROM produtos WHERE id IN ({placeholders})""",
                tuple(unique_ids),
            )
            columns = [column[0] for column in cursor.description]
            products = {int(row[0]): dict(zip(columns, row)) for row in cursor.fetchall()}
        finally:
            conn.close()
        result: list[dict[str, Any]] = []
        for index, cart_item in enumerate(cart_items, 1):
            product_id = int(cart_item.get("produto_id") or 0)
            product = products.get(product_id)
            if not product:
                raise ValueError(f"Item {index}: produto cadastrado não foi encontrado.")
            try:
                profile = FiscalProductProfile.validate_for_regime(
                    product, crt=int(crt), require_rtc=False
                )
            except ValueError as exc:
                raise ValueError(
                    f"Item {index} ({product.get('nome') or product.get('codigo')}): "
                    f"{exc} Importe a NF-e de compra ou revise o cadastro."
                ) from exc
            ncm = profile["ncm"]
            operation = FiscalOperationResolver.resolve_sale(
                profile["cfop"], destination=destination, crt=int(crt),
                csosn=profile["fiscal_csosn"], icms_cst=profile["fiscal_icms_cst"],
            )
            rtc_rule = FiscalRtcResolver.resolve(profile, destination=destination) if require_rtc else None
            configured_rule = None
            tax_rule_service = getattr(self, "tax_rule_service", None)
            if tax_rule_service is not None and destination_state and tax_regime:
                configured_rule = tax_rule_service.resolve(
                    tax_regime=tax_regime, ncm=ncm, cest=profile["cest"],
                    destination_state=destination_state, operation_kind="VENDA",
                )
            fiscal_item = {
                "product_id": product_id,
                "code": product.get("codigo") or product_id,
                "description": product.get("nome") or cart_item.get("item") or "PRODUTO",
                "quantity": cart_item.get("qtd"),
                "unit_price": cart_item.get("preco"),
                "unit": "UN",
                "ncm": ncm,
                "cest": profile["cest"],
                "cfop": operation.cfop,
                "origin": profile["fiscal_origin"],
                "csosn": profile["fiscal_csosn"],
                "cst": profile["fiscal_icms_cst"],
                "icms_rate": profile["fiscal_icms_rate"],
                "pis_cst": profile["fiscal_pis_cst"],
                "pis_rate": profile["fiscal_pis_rate"],
                "cofins_cst": profile["fiscal_cofins_cst"],
                "cofins_rate": profile["fiscal_cofins_rate"],
                "ipi_cst": profile["fiscal_ipi_cst"],
                "ipi_rate": profile["fiscal_ipi_rate"],
                "ipi_enq": profile["fiscal_ipi_enq"],
            }
            if configured_rule is not None:
                code = configured_rule.icms_code
                fiscal_item.update({
                    "tax_rule_id": configured_rule.id,
                    "csosn": code if len(code) == 3 else fiscal_item["csosn"],
                    "cst": code if len(code) == 2 else fiscal_item["cst"],
                    "icms_rate": configured_rule.icms_rate,
                    "icms_base_reduction": configured_rule.icms_base_reduction,
                    "sn_credit_rate": configured_rule.sn_credit_rate,
                    "st_mva": configured_rule.st_mva,
                    "st_rate": configured_rule.st_rate,
                    "fcp_st_rate": configured_rule.fcp_st_rate,
                    "difal_internal_rate": configured_rule.difal_internal_rate,
                    "difal_interstate_rate": configured_rule.difal_interstate_rate,
                    "difal_fcp_rate": configured_rule.difal_fcp_rate,
                    "benefit_code": configured_rule.benefit_code,
                })
            if require_rtc:
                fiscal_item.update({
                    "ibs_cbs_cst": rtc_rule.cst,
                    "ibs_cbs_class": rtc_rule.classification,
                    "ibs_uf_rate": rtc_rule.ibs_uf_rate,
                    "ibs_city_rate": rtc_rule.ibs_city_rate,
                    "cbs_rate": rtc_rule.cbs_rate,
                })
            result.append(fiscal_item)
        return result

    def build_nfce_qr_code_v3(
        self, *, access_key: str, environment: str,
        issued_at: datetime | str | None = None,
        total: Decimal | str | float | None = None,
        recipient_document: str = "", recipient_foreign_id: str = "",
        pfx_path: str | Path = "", password: str = "",
    ) -> str:
        """Monta o QR Code 3.00 oficial da NFC-e, sem CSC."""
        key = self._normalize_access_key(access_key)
        if len(key) != 44 or key[20:22] != "65":
            raise ValueError("QR Code NFC-e exige chave válida do modelo 65.")
        env_name = str(environment or "").strip().upper()
        if env_name not in self.VALID_ENVIRONMENTS:
            raise ValueError("Ambiente fiscal inválido para QR Code NFC-e.")
        parts = [key, "3", "2" if env_name == "HOMOLOGACAO" else "1"]
        if int(key[34]) != 1:
            if issued_at is None or total is None:
                raise ValueError("QR Code offline exige data de emissão e valor total.")
            when = issued_at if isinstance(issued_at, datetime) else datetime.fromisoformat(str(issued_at))
            amount = Decimal(str(total)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            document = self._normalize_tax_document(recipient_document)
            foreign_id = str(recipient_foreign_id or "").strip()
            if len(document) == 14:
                recipient_type, recipient_id = "1", document
            elif len(document) == 11:
                recipient_type, recipient_id = "2", document
            elif foreign_id:
                recipient_type, recipient_id = "3", ""
            else:
                recipient_type = recipient_id = ""
            parts.extend([f"{when.day:02d}", f"{amount:.2f}", recipient_type, recipient_id])
            self._require_dependency("cryptography")
            path = Path(pfx_path)
            if not path.is_file():
                raise ValueError("Certificado A1 é obrigatório para assinar o QR Code offline.")
            private_key, _cert, _chain = pkcs12.load_key_and_certificates(
                path.read_bytes(), str(password).encode("utf-8")
            )
            if private_key is None:
                raise ValueError("O certificado A1 não contém chave privada.")
            signature = private_key.sign(
                "|".join(parts).encode("utf-8"), padding.PKCS1v15(), hashes.SHA1()
            )
            parts.append(base64.b64encode(signature).decode("ascii"))
        state_code = key[:2]
        uf = next((name for name, code in self.STATE_CODES.items() if code == state_code), "")
        profile = state_profile(uf)
        base_url = str(profile.get("nfce_urls", {}).get(env_name, {}).get("qr_code", ""))
        if not base_url:
            raise ValueError(f"QR Code da NFC-e ainda não homologado para a UF {uf}.")
        return f"{base_url}?p={'|'.join(parts)}"

    def _set_nfce_supplement(self, root: Any, *, qr_code: str, environment: str) -> None:
        ns = "http://www.portalfiscal.inf.br/nfe"
        for node in root.xpath("./*[local-name()='infNFeSupl']"):
            root.remove(node)
        supplement = etree.SubElement(root, etree.QName(ns, "infNFeSupl"))
        qr_node = etree.SubElement(supplement, etree.QName(ns, "qrCode"))
        qr_node.text = qr_code
        key_node = etree.SubElement(supplement, etree.QName(ns, "urlChave"))
        key = str(root.xpath("string(./*[local-name()='infNFe'][1]/@Id)")).removeprefix("NFe")
        state_code = key[:2]
        uf = next((name for name, code in self.STATE_CODES.items() if code == state_code), "")
        profile = state_profile(uf)
        key_url = str(
            profile.get("nfce_urls", {})
            .get(str(environment).strip().upper(), {})
            .get("consulta_chave", "")
        )
        if not key_url:
            raise ValueError(f"Consulta da NFC-e ainda não homologada para a UF {uf}.")
        key_node.text = key_url

    def add_nfce_qr_code_v3(
        self, xml: bytes | str, *, pfx_path: str | Path = "", password: str = ""
    ) -> bytes:
        self._require_dependency("lxml")
        root = etree.fromstring(xml.encode("utf-8") if isinstance(xml, str) else bytes(xml))
        model = str(root.xpath("string(//*[local-name()='ide']/*[local-name()='mod'][1])"))
        if model != "65":
            return etree.tostring(root, xml_declaration=True, encoding="utf-8")
        key = str(root.xpath("string(//*[local-name()='infNFe'][1]/@Id)")).removeprefix("NFe")
        environment_code = str(root.xpath("string(//*[local-name()='ide']/*[local-name()='tpAmb'][1])"))
        environment = "HOMOLOGACAO" if environment_code == "2" else "PRODUCAO"
        issued_at = str(root.xpath("string(//*[local-name()='ide']/*[local-name()='dhEmi'][1])"))
        total = str(root.xpath("string(//*[local-name()='ICMSTot']/*[local-name()='vNF'][1])"))
        recipient_document = str(root.xpath("string(//*[local-name()='dest']/*[local-name()='CNPJ' or local-name()='CPF'][1])"))
        foreign_id = str(root.xpath("string(//*[local-name()='dest']/*[local-name()='idEstrangeiro'][1])"))
        qr_code = self.build_nfce_qr_code_v3(
            access_key=key, environment=environment, issued_at=issued_at, total=total,
            recipient_document=recipient_document, recipient_foreign_id=foreign_id,
            pfx_path=pfx_path, password=password,
        )
        self._set_nfce_supplement(root, qr_code=qr_code, environment=environment)
        return etree.tostring(root, xml_declaration=True, encoding="utf-8")

    def build_event_xml(
        self, *, event_type: str, access_key: str, sequence: int, actor_document: str,
        protocol: str = "", justification: str = "", correction: str = "", environment: str = "HOMOLOGACAO"
    ) -> tuple[bytes, str]:
        event_type = str(event_type).strip().upper()
        if event_type not in self.VALID_EVENTS:
            raise ValueError("Evento fiscal suportado: CANCELAMENTO ou CCE.")
        key=self._normalize_access_key(access_key); actor=self._normalize_tax_document(actor_document)
        if len(key)!=44 or len(actor) not in {11,14}: raise ValueError("Chave ou documento do autor inválido.")
        if event_type=="CANCELAMENTO":
            if not protocol: raise ValueError("Protocolo de autorização é obrigatório para cancelamento.")
            if len(str(justification).strip()) < 15: raise ValueError("Justificativa de cancelamento deve possuir ao menos 15 caracteres.")
            code, desc, detail = "110111", "Cancelamento", {"nProt":protocol,"xJust":str(justification).strip()}
        else:
            if len(str(correction).strip()) < 15: raise ValueError("Correção deve possuir ao menos 15 caracteres.")
            code, desc, detail = "110110", "Carta de Correcao", {"xCorrecao":str(correction).strip(),"xCondUso":"A Carta de Correcao e disciplinada pelo paragrafo 1o-A do art. 7o do Convenio S/N, de 15 de dezembro de 1970."}
        ns="http://www.portalfiscal.inf.br/nfe"; env=2 if str(environment).upper()=="HOMOLOGACAO" else 1
        event_id=f"ID{code}{key}{int(sequence):02d}"
        root=etree.Element(etree.QName(ns,"evento"), nsmap={None:ns}, versao="1.00"); inf=etree.SubElement(root,etree.QName(ns,"infEvento"),Id=event_id)
        def el(parent,name,value): node=etree.SubElement(parent,etree.QName(ns,name)); node.text=str(value); return node
        el(inf,"cOrgao",key[:2]); el(inf,"tpAmb",env); el(inf,"CNPJ" if len(actor)==14 else "CPF",actor); el(inf,"chNFe",key); el(inf,"dhEvento",datetime.now().astimezone().isoformat(timespec="seconds")); el(inf,"tpEvento",code); el(inf,"nSeqEvento",int(sequence)); el(inf,"verEvento","1.00")
        det=etree.SubElement(inf,etree.QName(ns,"detEvento"),versao="1.00"); el(det,"descEvento",desc)
        for n,v in detail.items(): el(det,n,v)
        return etree.tostring(root,xml_declaration=True,encoding="utf-8"), event_id

    def build_inutilization_xml(self, *, state_code: str, year: int, cnpj: str, model: str, series: int, start_number: int, end_number: int, justification: str, environment: str="HOMOLOGACAO") -> tuple[bytes,str]:
        cnpj=self._normalize_cnpj(cnpj); model=str(model).zfill(2)
        if not self._is_valid_cnpj(cnpj) or model not in self.VALID_MODELS: raise ValueError("Dados da inutilização inválidos.")
        if int(start_number)>int(end_number): raise ValueError("Faixa de inutilização inválida.")
        if len(str(justification).strip())<15: raise ValueError("Justificativa deve possuir ao menos 15 caracteres.")
        identifier=f"ID{str(state_code).zfill(2)}{int(year)%100:02d}{cnpj}{model}{int(series):03d}{int(start_number):09d}{int(end_number):09d}"
        ns="http://www.portalfiscal.inf.br/nfe"; root=etree.Element(etree.QName(ns,"inutNFe"),nsmap={None:ns},versao="4.00"); inf=etree.SubElement(root,etree.QName(ns,"infInut"),Id=identifier)
        def el(n,v): node=etree.SubElement(inf,etree.QName(ns,n)); node.text=str(v)
        el("tpAmb",2 if str(environment).upper()=="HOMOLOGACAO" else 1); el("xServ","INUTILIZAR"); el("cUF",str(state_code).zfill(2)); el("ano",f"{int(year)%100:02d}"); el("CNPJ",cnpj); el("mod",model); el("serie",int(series)); el("nNFIni",int(start_number)); el("nNFFin",int(end_number)); el("xJust",str(justification).strip())
        return etree.tostring(root,xml_declaration=True,encoding="utf-8"),identifier

    def build_query_xml(self, *, access_key: str, environment: str="HOMOLOGACAO") -> bytes:
        key=self._normalize_access_key(access_key)
        if len(key)!=44: raise ValueError("Chave de acesso inválida para consulta.")
        ns="http://www.portalfiscal.inf.br/nfe"; root=etree.Element(etree.QName(ns,"consSitNFe"),nsmap={None:ns},versao="4.00")
        for name,value in (("tpAmb",2 if str(environment).upper()=="HOMOLOGACAO" else 1),("xServ","CONSULTAR"),("chNFe",key)):
            node=etree.SubElement(root,etree.QName(ns,name)); node.text=str(value)
        return etree.tostring(root,xml_declaration=True,encoding="utf-8")

    def build_receipt_query_xml(self, *, receipt: str, environment: str = "HOMOLOGACAO") -> bytes:
        receipt_number = self._digits(receipt)
        if not receipt_number:
            raise ValueError("Número do recibo da SEFAZ é obrigatório.")
        ns = "http://www.portalfiscal.inf.br/nfe"
        root = etree.Element(etree.QName(ns, "consReciNFe"), nsmap={None: ns}, versao="4.00")
        for name, value in (
            ("tpAmb", 2 if str(environment).upper() == "HOMOLOGACAO" else 1),
            ("nRec", receipt_number),
        ):
            node = etree.SubElement(root, etree.QName(ns, name))
            node.text = str(value)
        return etree.tostring(root, xml_declaration=True, encoding="utf-8")

    def validate_event_eligibility(
        self,
        *,
        access_key: str,
        event_type: str,
        sequence: int,
        protocol: str = "",
    ) -> dict[str, Any]:
        key = self._normalize_access_key(access_key)
        if len(key) != 44:
            raise ValueError("Chave de acesso inválida.")
        kind = str(event_type or "").strip().upper()
        if kind not in self.VALID_EVENTS:
            raise ValueError("Tipo de evento fiscal inválido.")
        seq = int(sequence)
        if seq < 1 or seq > 20:
            raise ValueError("Sequência do evento deve estar entre 1 e 20.")

        documents = [
            row for row in self.list_documents()
            if row.get("access_key") == key
        ]
        if not documents:
            raise ValueError("Evento fiscal exige documento autorizado armazenado.")
        document = documents[-1]
        document_status = str(document.get("status") or "").upper()
        if document_status == "CANCELADO":
            if kind == "CCE":
                raise ValueError("Carta de correção não pode ser enviada após cancelamento aceito.")
            raise ValueError("Documento fiscal já possui cancelamento aceito.")
        if document_status != "AUTORIZADO":
            raise ValueError("Evento fiscal exige documento autorizado armazenado.")
        integrity = self.verify_document_integrity(
            access_key=key, environment=str(document.get("environment") or "")
        )
        if not integrity.get("valid"):
            raise ValueError("Documento autorizado falhou na verificação de integridade.")

        if kind == "CANCELAMENTO":
            informed_protocol = str(protocol or "").strip()
            stored_protocol = str(document.get("protocol") or "").strip()
            if not informed_protocol or informed_protocol != stored_protocol:
                raise ValueError("Cancelamento exige o protocolo de autorização do documento.")

        accepted = [
            row for row in self.list_events(key)
            if row.get("success")
            and str(row.get("event_type") or "").upper() == kind
        ]
        if kind == "CANCELAMENTO" and accepted:
            raise ValueError("Documento fiscal já possui cancelamento aceito.")
        if any(int(row.get("sequence") or 0) == seq for row in accepted):
            raise ValueError("Sequência de evento já utilizada para este documento.")
        if kind == "CCE" and any(str(row.get("event_type") or "").upper() == "CANCELAMENTO" for row in self.list_events(key) if row.get("success")):
            raise ValueError("Carta de correção não pode ser enviada após cancelamento aceito.")
        return dict(document)

    def register_event(self, *, access_key: str, event_type: str, response: FiscalResponse, request_xml: bytes|str, actor: str, metadata: Mapping[str, Any] | None = None) -> dict[str,Any]:
        key=self._normalize_access_key(access_key)
        if len(key)!=44: raise ValueError("Chave de acesso inválida.")
        folder=self.storage_dir/"eventos"/key; folder.mkdir(parents=True,exist_ok=True)
        stamp=datetime.now().strftime("%Y%m%d_%H%M%S_%f"); request_path=folder/f"{stamp}_{event_type.lower()}_envio.xml"; response_path=folder/f"{stamp}_{event_type.lower()}_retorno.xml"
        request_path.write_bytes(request_xml.encode() if isinstance(request_xml,str) else request_xml); response_path.write_text(response.raw_xml,encoding="utf-8")
        try:
            request_root = etree.fromstring(request_xml.encode() if isinstance(request_xml, str) else bytes(request_xml), parser=etree.XMLParser(resolve_entities=False, no_network=True))
            sequence = int(str(request_root.xpath("string(//*[local-name()='nSeqEvento'][1])") or "0"))
            environment_code = str(request_root.xpath("string(//*[local-name()='tpAmb'][1])") or "")
            event_environment = "HOMOLOGACAO" if environment_code == "2" else "PRODUCAO" if environment_code == "1" else ""
        except (ValueError, TypeError, etree.XMLSyntaxError):
            sequence = 0
            event_environment = ""
        request_bytes = request_xml.encode() if isinstance(request_xml, str) else bytes(request_xml)
        response_bytes = response.raw_xml.encode("utf-8")
        record={
            "access_key":key,
            "event_type":str(event_type).upper(),
            "environment":event_environment,
            "sequence":sequence,
            "status_code":response.status_code,
            "message":response.message,
            "protocol":response.protocol,
            "success":response.success,
            "actor":actor or "Sistema",
            "created_at":datetime.now().isoformat(timespec="seconds"),
            "request_path":str(request_path),
            "response_path":str(response_path),
            "request_sha256":hashlib.sha256(request_bytes).hexdigest(),
            "response_sha256":hashlib.sha256(response_bytes).hexdigest(),
        }
        if metadata:
            record.update({str(key): value for key, value in metadata.items()})
        rows=self.list_events(); rows.append(record); self._set_setting(self.EVENT_INDEX_KEY,json.dumps(rows,ensure_ascii=False,sort_keys=True))
        if response.success and str(event_type).upper() == "CANCELAMENTO":
            self._mark_document_cancelled(
                access_key=key,
                event_protocol=response.protocol,
                actor=actor,
                event_record=record,
            )
        if not response.success:
            self.register_rejection(
                operation=str(event_type).upper(),
                response=response,
                access_key=key,
                actor=actor,
            )
        return record


    def _mark_document_cancelled(
        self, *, access_key: str, event_protocol: str, actor: str, event_record: Mapping[str, Any]
    ) -> dict[str, Any]:
        key = self._normalize_access_key(access_key)
        if len(key) != 44:
            raise ValueError("Chave de acesso inválida para cancelamento.")
        rows = self.list_documents()
        matched = None
        for row in reversed(rows):
            if row.get("access_key") == key:
                matched = row
                break
        if not matched:
            raise ValueError("Documento fiscal autorizado não encontrado para registrar cancelamento.")
        if matched.get("status") not in {"AUTORIZADO", "CANCELADO"}:
            raise ValueError("Somente documento autorizado pode ser marcado como cancelado.")
        if matched.get("status") == "CANCELADO":
            if str(matched.get("cancellation_protocol") or "") != str(event_protocol or ""):
                raise ValueError("Documento já foi cancelado com outro protocolo.")
            return dict(matched)
        matched.update({
            "status": "CANCELADO",
            "cancelled_at": datetime.now().isoformat(timespec="seconds"),
            "cancelled_by": str(actor or "Sistema"),
            "cancellation_protocol": str(event_protocol or ""),
            "cancellation_status_code": str(event_record.get("status_code") or ""),
            "cancellation_message": str(event_record.get("message") or ""),
            "cancellation_request_path": str(event_record.get("request_path") or ""),
            "cancellation_response_path": str(event_record.get("response_path") or ""),
            "cancellation_request_sha256": str(event_record.get("request_sha256") or ""),
            "cancellation_response_sha256": str(event_record.get("response_sha256") or ""),
        })
        self._set_setting(self.DOCUMENT_INDEX_KEY, json.dumps(rows, ensure_ascii=False, sort_keys=True))
        return dict(matched)

    def list_events(self, access_key: str="") -> list[dict[str,Any]]:
        raw=self._get_setting(self.EVENT_INDEX_KEY)
        try: rows=json.loads(raw) if raw else []
        except (TypeError,ValueError): rows=[]
        key=self._normalize_access_key(access_key)
        result=[dict(r) for r in rows if isinstance(r,dict)]
        return [r for r in result if r.get("access_key")==key] if key else result

    def generate_fiscal_mirror_pdf(self, *, authorized_xml: bytes|str, output_path: str|Path) -> Path:
        """Gera um espelho interno; não substitui o DANFE de leiaute oficial."""
        self._require_dependency("lxml")
        self._require_dependency("reportlab")
        raw=authorized_xml.encode() if isinstance(authorized_xml,str) else authorized_xml
        root=etree.fromstring(raw,parser=etree.XMLParser(resolve_entities=False,no_network=True))
        text=lambda n: str(root.xpath(f"string(//*[local-name()='{n}'][1])") or "").strip()
        protocol=text("nProt"); status=text("cStat")
        if not protocol or status not in self.AUTHORIZED_STATUS:
            raise ValueError("Espelho fiscal só pode ser gerado para documento autorizado com protocolo válido.")
        key=text("chNFe") or str(root.xpath("string(//*[local-name()='infNFe'][1]/@Id)")).replace("NFe","")
        output=Path(output_path); output.parent.mkdir(parents=True,exist_ok=True)
        document_record = next((row for row in reversed(self.list_documents()) if row.get("access_key") == key), {})
        cancelled = str(document_record.get("status") or "").upper() == "CANCELADO"
        c=canvas.Canvas(str(output),pagesize=A4); width,height=A4
        c.setFont("Helvetica-Bold",14); c.drawString(15*mm,height-18*mm,"ESPELHO FISCAL — NÃO É DANFE")
        if cancelled:
            c.saveState()
            c.setFont("Helvetica-Bold", 42)
            c.setFillGray(0.80)
            c.translate(width / 2, height / 2)
            c.rotate(35)
            c.drawCentredString(0, 0, "CANCELADO")
            c.restoreState()
        c.setFont("Helvetica",9); y=height-28*mm
        lines=[f"Chave de acesso: {key}",f"Protocolo: {protocol}",f"Número: {text('nNF')}  Série: {text('serie')}  Modelo: {text('mod')}",f"Emitente: {text('xNome')}  CNPJ: {text('CNPJ')}",f"Destinatário: {str(root.xpath("string(//*[local-name()='dest']/*[local-name()='xNome'][1])") or '').strip()}",f"Valor total: R$ {text('vNF')}"]
        if cancelled:
            lines.insert(2, f"CANCELADO — protocolo: {document_record.get('cancellation_protocol', '')}")
        for line in lines: c.drawString(15*mm,y,line); y-=6*mm
        c.line(15*mm,y,width-15*mm,y); y-=7*mm; c.setFont("Helvetica-Bold",8); c.drawString(15*mm,y,"ITEM  CÓDIGO  DESCRIÇÃO  QTD  UN  V.UNIT  V.TOTAL"); y-=5*mm; c.setFont("Helvetica",7)
        dets=root.xpath("//*[local-name()='det']")
        for det in dets:
            get=lambda n: str(det.xpath(f"string(.//*[local-name()='{n}'][1])") or "").strip()
            line=f"{det.get('nItem','')}  {get('cProd')[:12]}  {get('xProd')[:42]}  {get('qCom')}  {get('uCom')}  {get('vUnCom')}  {get('vProd')}"
            c.drawString(15*mm,y,line); y-=4.5*mm
            if y<20*mm: c.showPage(); y=height-20*mm; c.setFont("Helvetica",7)
        c.setFont("Helvetica-Oblique",7); c.drawString(15*mm,12*mm,"Espelho interno para conferência. Não substitui o DANFE de leiaute oficial.")
        c.save(); return output

    def generate_official_danfe_pdf(
        self, *, authorized_xml: bytes | str, output_path: str | Path,
    ) -> Path:
        """Gera o DANFE modelo 55 por motor dedicado, após validar XML e assinatura."""
        self._require_dependency("brazilfiscalreport")
        raw = authorized_xml.encode("utf-8") if isinstance(authorized_xml, str) else bytes(authorized_xml)
        validation = self.validate_authorized_xml(raw, require_signature=True)
        if str(validation.get("model") or "") != "55":
            raise ValueError("Este gerador de DANFE oficial aceita somente NF-e modelo 55.")
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary_name = tempfile.mkstemp(
            prefix=f".{output.stem}_", suffix=".pdf.tmp", dir=str(output.parent)
        )
        os.close(handle)
        temporary = Path(temporary_name)
        temporary.unlink(missing_ok=True)
        try:
            document = OfficialDanfe(xml=raw.decode("utf-8"))
            document.output(str(temporary))
            if not temporary.is_file() or temporary.stat().st_size < 500:
                raise RuntimeError("O motor de DANFE não produziu um PDF válido.")
            with temporary.open("rb") as stream:
                if stream.read(5) != b"%PDF-":
                    raise RuntimeError("O arquivo produzido pelo motor de DANFE não é PDF.")
            temporary.replace(output)
            return output
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    def generate_nfce_auxiliary_pdf(
        self, *, fiscal_xml: bytes | str, output_path: str | Path,
    ) -> Path:
        """Gera DANFE NFC-e 80 mm para XML autorizado ou contingência offline assinada."""
        self._require_dependency("reportlab")
        self._require_dependency("lxml")
        raw = fiscal_xml.encode("utf-8") if isinstance(fiscal_xml, str) else bytes(fiscal_xml)
        root = etree.fromstring(raw, parser=etree.XMLParser(resolve_entities=False, no_network=True))
        value = lambda expression: str(root.xpath(f"string({expression})") or "").strip()
        model = value("//*[local-name()='ide']/*[local-name()='mod'][1]")
        if model != "65":
            raise ValueError("DANFE NFC-e aceita somente documento modelo 65.")
        identifier = value("//*[local-name()='infNFe'][1]/@Id")
        key = self._normalize_access_key(identifier.removeprefix("NFe"))
        if not self._is_valid_access_key(key):
            raise ValueError("A NFC-e não possui chave de acesso válida.")
        status = value("//*[local-name()='protNFe']/*[local-name()='infProt']/*[local-name()='cStat'][1]")
        protocol = value("//*[local-name()='protNFe']/*[local-name()='infProt']/*[local-name()='nProt'][1]")
        authorized = status in self.AUTHORIZED_STATUS and bool(protocol)
        emission_type = value("//*[local-name()='ide']/*[local-name()='tpEmis'][1]") or "1"
        if authorized:
            validation = self.validate_authorized_xml(raw, require_signature=True)
            if validation["model"] != "65":
                raise ValueError("O protocolo não pertence a uma NFC-e modelo 65.")
        else:
            if emission_type != "9":
                raise ValueError("NFC-e sem autorização só pode gerar DANFE em contingência offline.")
            signature = self.verify_xml_signature(raw)
            if signature.get("reference_id") != identifier:
                raise ValueError("A assinatura não referencia a NFC-e em contingência.")
            if not value("//*[local-name()='ide']/*[local-name()='dhCont'][1]"):
                raise ValueError("NFC-e em contingência não informa o início da contingência.")
            if len(value("//*[local-name()='ide']/*[local-name()='xJust'][1]")) < 15:
                raise ValueError("NFC-e em contingência não possui justificativa válida.")
        qr_code = value("//*[local-name()='infNFeSupl']/*[local-name()='qrCode'][1]")
        if not qr_code:
            raise ValueError("NFC-e não possui QR Code para o DANFE.")
        items = root.xpath("//*[local-name()='det']")
        payments = root.xpath("//*[local-name()='pag']/*[local-name()='detPag']")
        height = max(180.0, 135.0 + len(items) * 11.0 + len(payments) * 5.0) * mm
        width = 80 * mm
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary_name = tempfile.mkstemp(
            prefix=f".{output.stem}_", suffix=".pdf.tmp", dir=str(output.parent)
        )
        os.close(handle)
        temporary = Path(temporary_name)
        try:
            pdf = canvas.Canvas(str(temporary), pagesize=(width, height))
            y = height - 5 * mm

            def centered(text: str, size: float = 8, bold: bool = False, gap: float = 4.2) -> None:
                nonlocal y
                pdf.setFont("Helvetica-Bold" if bold else "Helvetica", size)
                pdf.drawCentredString(width / 2, y, str(text)[:70])
                y -= gap * mm

            def left(text: str, size: float = 7, gap: float = 3.6) -> None:
                nonlocal y
                pdf.setFont("Helvetica", size)
                pdf.drawString(3 * mm, y, str(text)[:58])
                y -= gap * mm

            centered(value("//*[local-name()='emit']/*[local-name()='xNome'][1]"), 10, True, 4.8)
            centered(f"CNPJ {value('//*[local-name()=\'emit\']/*[local-name()=\'CNPJ\'][1]')}", 7)
            centered("DOCUMENTO AUXILIAR DA NOTA FISCAL", 7, True)
            centered("DE CONSUMIDOR ELETRÔNICA", 7, True, 5)
            pdf.line(3 * mm, y, width - 3 * mm, y); y -= 4 * mm
            left("CÓDIGO  DESCRIÇÃO")
            left("QTD x VL UNIT.                         VL TOTAL")
            for item in items:
                item_value = lambda name: str(item.xpath(f"string(.//*[local-name()='{name}'][1])") or "").strip()
                left(f"{item_value('cProd')[:10]}  {item_value('xProd')[:42]}", 6.5, 3.2)
                left(
                    f"{item_value('qCom')} {item_value('uCom')} x {item_value('vUnCom')}"
                    f"                         {item_value('vProd')}", 6.5, 3.8,
                )
            pdf.line(3 * mm, y, width - 3 * mm, y); y -= 4 * mm
            left(f"Qtd. total de itens: {len(items)}", 7)
            left(f"Valor total R$: {value('//*[local-name()=\'ICMSTot\']/*[local-name()=\'vNF\'][1]')}", 9, 4.5)
            payment_names = {"01": "Dinheiro", "03": "Cartão de crédito", "04": "Cartão de débito", "05": "Crédito loja", "17": "PIX", "90": "Sem pagamento", "99": "Outros"}
            for payment in payments:
                code = str(payment.xpath("string(./*[local-name()='tPag'][1])") or "").strip()
                amount = str(payment.xpath("string(./*[local-name()='vPag'][1])") or "").strip()
                left(f"{payment_names.get(code, code)}: R$ {amount}", 7)
            change = value("//*[local-name()='pag']/*[local-name()='vTroco'][1]")
            if change:
                left(f"Troco: R$ {change}", 7)
            pdf.line(3 * mm, y, width - 3 * mm, y); y -= 4 * mm
            recipient = value("//*[local-name()='dest']/*[local-name()='xNome'][1]") or "CONSUMIDOR NÃO IDENTIFICADO"
            centered(recipient, 7, True)
            centered(f"NFC-e nº {value('//*[local-name()=\'ide\']/*[local-name()=\'nNF\'][1]')}  Série {value('//*[local-name()=\'ide\']/*[local-name()=\'serie\'][1]')}", 7)
            centered("Consulte pela chave de acesso", 7)
            for start in range(0, 44, 22):
                centered(" ".join(key[start:start + 22][index:index + 4] for index in range(0, len(key[start:start + 22]), 4)), 6.5)
            drawing = Drawing(30 * mm, 30 * mm)
            widget = qr.QrCodeWidget(qr_code)
            bounds = widget.getBounds()
            scale = min((30 * mm) / (bounds[2] - bounds[0]), (30 * mm) / (bounds[3] - bounds[1]))
            widget.barWidth = (bounds[2] - bounds[0]) * scale
            widget.barHeight = (bounds[3] - bounds[1]) * scale
            drawing.add(widget)
            renderPDF.draw(drawing, pdf, (width - 30 * mm) / 2, y - 31 * mm)
            y -= 33 * mm
            if authorized:
                centered(f"Protocolo: {protocol}", 6.5)
            else:
                centered("EMITIDA EM CONTINGÊNCIA", 8, True)
                centered("Pendente de autorização", 7)
            if value("//*[local-name()='ide']/*[local-name()='tpAmb'][1]") == "2":
                centered("EMITIDA EM AMBIENTE DE HOMOLOGAÇÃO", 7, True)
                centered("SEM VALOR FISCAL", 8, True)
            pdf.save()
            if temporary.stat().st_size < 1_000 or temporary.read_bytes()[:5] != b"%PDF-":
                raise RuntimeError("O DANFE NFC-e produzido não é um PDF válido.")
            temporary.replace(output)
            return output
        except Exception:
            temporary.unlink(missing_ok=True)
            raise


    def apply_contingency(self, xml: bytes | str, *, reason: str, emission_type: int = 9, started_at: datetime | None = None) -> bytes:
        emission_type = int(emission_type)
        if emission_type not in {2, 4, 5, 6, 7, 9}:
            raise ValueError("Tipo de emissão em contingência inválido.")
        if len(str(reason).strip()) < 15:
            raise ValueError("Justificativa da contingência deve possuir ao menos 15 caracteres.")
        root = etree.fromstring(
            xml.encode() if isinstance(xml, str) else xml,
            parser=etree.XMLParser(resolve_entities=False, no_network=True),
        )
        ide_nodes = root.xpath("//*[local-name()='ide'][1]")
        inf_nodes = root.xpath("//*[local-name()='infNFe'][1]")
        if not ide_nodes or not inf_nodes:
            raise ValueError("XML não possui grupos ide e infNFe para aplicar contingência.")
        ide = ide_nodes[0]
        inf_nfe = inf_nodes[0]
        ns = "http://www.portalfiscal.inf.br/nfe"

        def text(name: str, *, context=ide) -> str:
            return str(context.xpath(f"string(./*[local-name()='{name}'][1])") or "").strip()

        tp_nodes = ide.xpath("./*[local-name()='tpEmis'][1]")
        tp_node = tp_nodes[0] if tp_nodes else etree.SubElement(ide, etree.QName(ns, "tpEmis"))
        tp_node.text = str(emission_type)
        for node in ide.xpath("./*[local-name()='dhCont' or local-name()='xJust']"):
            ide.remove(node)
        dh = etree.SubElement(ide, etree.QName(ns, "dhCont"))
        dh.text = (started_at or datetime.now().astimezone()).astimezone().isoformat(timespec="seconds")
        xj = etree.SubElement(ide, etree.QName(ns, "xJust"))
        xj.text = str(reason).strip()

        issued_text = text("dhEmi") or text("dEmi")
        try:
            issued_at = datetime.fromisoformat(issued_text.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            raise ValueError("Data de emissão inválida ou ausente para recalcular a chave de contingência.")
        cnpj = str(root.xpath("string(//*[local-name()='emit']/*[local-name()='CNPJ'][1])") or "").strip()
        required = {
            "cUF": text("cUF"), "mod": text("mod"), "serie": text("serie"),
            "nNF": text("nNF"), "cNF": text("cNF"), "CNPJ": cnpj,
        }
        missing = [name for name, value in required.items() if not self._digits(value)]
        if missing:
            raise ValueError("Dados insuficientes para recalcular a chave de contingência: " + ", ".join(missing))
        access_key = self.build_access_key(
            state_code=required["cUF"], issued_at=issued_at, cnpj=required["CNPJ"],
            model=required["mod"], series=int(required["serie"]), number=int(required["nNF"]),
            emission_type=emission_type, numeric_code=required["cNF"],
        )
        inf_nfe.set("Id", f"NFe{access_key}")
        cdv_nodes = ide.xpath("./*[local-name()='cDV'][1]")
        cdv_node = cdv_nodes[0] if cdv_nodes else etree.SubElement(ide, etree.QName(ns, "cDV"))
        cdv_node.text = access_key[-1]
        return etree.tostring(root, xml_declaration=True, encoding="utf-8")

    def list_transmission_queue(self, *, status: str = "") -> list[dict[str, Any]]:
        return FiscalOutboxService(self.connection_factory).list_items(status=status)

    def _save_transmission_queue(self, rows: list[Mapping[str, Any]]) -> None:
        FiscalOutboxService(self.connection_factory).save_records(rows)

    @staticmethod
    def _xml_emission_type(xml: bytes | str) -> int:
        raw = xml.encode("utf-8") if isinstance(xml, str) else bytes(xml)
        try:
            root = etree.fromstring(
                raw, parser=etree.XMLParser(resolve_entities=False, no_network=True)
            )
            value = str(root.xpath("string(//*[local-name()='ide']/*[local-name()='tpEmis'][1])"))
            return int(value or 1)
        except (etree.XMLSyntaxError, TypeError, ValueError):
            return 1

    def enqueue_transmission(
        self,
        *,
        operation: str,
        xml: bytes | str,
        access_key: str = "",
        model: str = "55",
        reservation_id: str = "",
        max_attempts: int = 5,
        retry_minutes: int = 5,
    ) -> dict[str, Any]:
        actor = self._authenticated_fiscal_actor(
            "transmit", operation="enfileirar uma transmissão fiscal"
        )
        operation = str(operation or "").strip().lower()
        if operation not in {"autorizacao", "consulta", "recibo", "evento", "inutilizacao"}:
            raise ValueError("Operação fiscal inválida para a fila de transmissão.")
        model = str(model or "55").strip()
        if model not in self.VALID_MODELS:
            raise ValueError("Modelo fiscal deve ser 55 ou 65.")
        raw_xml = xml.encode("utf-8") if isinstance(xml, str) else bytes(xml)
        if not raw_xml.strip():
            raise ValueError("XML fiscal é obrigatório para enfileirar transmissão.")
        supplied_key = self._normalize_access_key(access_key)
        embedded_key = self._extract_access_key_from_xml(raw_xml)
        if supplied_key and embedded_key and supplied_key != embedded_key:
            raise ValueError("A chave informada não corresponde ao XML enfileirado.")
        resolved_key = supplied_key or embedded_key
        if operation == "autorizacao" and len(resolved_key) != 44:
            raise ValueError("Autorização enfileirada exige uma chave de acesso válida no XML ou no parâmetro access_key.")
        now = datetime.now(timezone.utc)
        is_contingency = self._xml_emission_type(raw_xml) != 1
        rows = self.list_transmission_queue()
        if operation == "autorizacao" and resolved_key:
            existing = next(
                (row for row in rows
                 if str(row.get("operation")) in {"autorizacao", "recibo"}
                 and self._normalize_access_key(row.get("access_key")) == resolved_key
                 and str(row.get("status")) != "FALHA"),
                None,
            )
            if existing is not None:
                return dict(existing)
        record = {
            "id": f"{now.strftime('%Y%m%d%H%M%S%f')}-{len(rows)+1}",
            "operation": operation,
            "access_key": resolved_key,
            "model": model,
            "reservation_id": str(reservation_id or ""),
            "xml_b64": base64.b64encode(raw_xml).decode("ascii"),
            "original_xml_b64": base64.b64encode(raw_xml).decode("ascii") if operation == "autorizacao" else "",
            "receipt": "",
            "actor": str(actor or "").strip(),
            "status": "PENDENTE",
            "attempts": 0,
            "max_attempts": max(1, int(max_attempts)),
            "retry_minutes": max(1, int(retry_minutes)),
            "created_at": now.isoformat(),
            "next_attempt_at": now.isoformat(),
            "last_error": "",
            "last_status_code": "",
            "last_message": "",
            "contingency": is_contingency,
            "contingency_deadline_at": (
                (now + timedelta(hours=24)).isoformat() if is_contingency and model == "65" else ""
            ),
            "contingency_overdue": False,
        }
        return FiscalOutboxService(self.connection_factory).enqueue_record(record)

    def process_transmission_queue(
        self,
        *,
        password: str,
        limit: int = 20,
        now: datetime | None = None,
        queue_ids: Sequence[str] | None = None,
        claimed_worker_id: str | None = None,
    ) -> list[dict[str, Any]]:
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        rows = self.list_transmission_queue()
        processed: list[dict[str, Any]] = []
        count = 0
        outbox = FiscalOutboxService(self.connection_factory)
        worker_id = str(claimed_worker_id or f"central-{uuid.uuid4().hex}")
        selected_ids = {str(value) for value in queue_ids or () if str(value)}
        for snapshot in rows:
            if count >= max(1, int(limit)):
                break
            if selected_ids and str(snapshot.get("id") or "") not in selected_ids:
                continue
            if claimed_worker_id:
                if (
                    snapshot.get("status") != "PROCESSANDO"
                    or str(snapshot.get("worker_id") or "") != worker_id
                ):
                    continue
                record = dict(snapshot)
            else:
                if snapshot.get("status") not in {"PENDENTE", "ERRO"}:
                    continue
                claimed = outbox.claim_item(
                    int(snapshot["id"]), worker_id=worker_id, lease_seconds=180, now=current
                )
                if claimed is None:
                    continue
                record = claimed
            if record.get("transmission_started_at") and not record.get("reconciliation_for"):
                record["status"] = "RESPOSTA_DESCONHECIDA"
                record["unknown_since"] = str(record.get("transmission_started_at"))
                record["last_error"] = (
                    "O processo foi interrompido após iniciar a comunicação com a SEFAZ. "
                    "Consulte o resultado antes de reenviar."
                )
                record["next_attempt_at"] = ""
                self._sync_sale_document(
                    record, status="RESPOSTA_DESCONHECIDA", error=record["last_error"]
                )
                processed.append(dict(record))
                continue
            deadline_text = str(record.get("contingency_deadline_at") or "")
            if deadline_text:
                try:
                    deadline = datetime.fromisoformat(deadline_text)
                    if deadline.tzinfo is None:
                        deadline = deadline.replace(tzinfo=timezone.utc)
                    record["contingency_overdue"] = current > deadline
                except ValueError:
                    record["contingency_overdue"] = True
            try:
                next_attempt = datetime.fromisoformat(str(record.get("next_attempt_at") or record.get("created_at")))
                if next_attempt.tzinfo is None:
                    next_attempt = next_attempt.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                next_attempt = current
            if next_attempt > current:
                continue
            count += 1
            record["last_attempt_at"] = current.isoformat()
            try:
                config = self.load_config()
                xml = base64.b64decode(str(record.get("xml_b64", "")))
                operation = str(record.get("operation", "")).lower()
                if operation in {"autorizacao", "recibo"} and self._sale_document_cancelled(
                    record.get("access_key", "")
                ):
                    record["status"] = "CANCELADO"
                    record["cancelled_at"] = current.isoformat()
                    record["last_error"] = "Venda cancelada antes da autorização fiscal."
                    processed.append(dict(record))
                    continue
                if operation in {"autorizacao", "recibo"}:
                    readiness = self.validate_ready(
                        operation=operation,
                        model=str(record.get("model") or config.get("default_model") or "65"),
                    )
                    if readiness:
                        raise ValueError("; ".join(readiness))
                if operation == "autorizacao":
                    try:
                        root = etree.fromstring(xml, parser=etree.XMLParser(resolve_entities=False, no_network=True))
                        is_draft = etree.QName(root).localname == "NFe"
                    except (etree.XMLSyntaxError, ValueError, TypeError):
                        is_draft = False
                    if is_draft:
                        model = str(record.get("model") or config.get("default_model") or "65")
                        queued_key = self._normalize_access_key(record.get("access_key", ""))
                        xml_key = self._extract_access_key_from_xml(xml)
                        if xml_key != queued_key:
                            raise ValueError("A chave do XML não corresponde ao item da fila fiscal.")
                        already_signed = bool(root.xpath(".//*[local-name()='Signature']"))
                        if already_signed:
                            signature = self.verify_xml_signature(xml)
                            if signature.get("reference_id") != f"NFe{queued_key}":
                                raise ValueError("A assinatura da contingência não referencia a chave enfileirada.")
                            signed = xml
                        else:
                            if model == "65":
                                xml = self.add_nfce_qr_code_v3(
                                    xml, pfx_path=config.get("certificate_path", ""), password=password
                                )
                            signed = self.sign_xml(
                                xml, reference_id=f"NFe{queued_key}",
                                pfx_path=config.get("certificate_path", ""), password=password,
                            )
                        self.validate_official_xml(signed, document_type="nfe")
                        record["original_xml_b64"] = base64.b64encode(signed).decode("ascii")
                        xml = self._authorization_envelope(
                            signed, environment=str(config.get("environment", "HOMOLOGACAO"))
                        )
                if operation in {"autorizacao", "evento", "inutilizacao"}:
                    record["transmission_started_at"] = datetime.now(timezone.utc).isoformat()
                    # Persistir antes da chamada de rede é intencional: se o processo cair,
                    # a próxima abertura sabe que não pode retransmitir cegamente.
                    outbox.save_claimed_record(record, worker_id=worker_id, finish=False)
                response = self.transmit(
                    operation=operation,
                    model=str(record.get("model") or config.get("default_model") or "65"),
                    xml=xml,
                    pfx_path=config.get("certificate_path", ""),
                    password=password,
                )
                record.pop("transmission_started_at", None)
                record["transmission_resolved_at"] = datetime.now(timezone.utc).isoformat()
                record["last_status_code"] = response.status_code
                record["last_message"] = response.message
                record["last_error"] = ""
                queued_key = self._normalize_access_key(record.get("access_key", ""))
                if operation == "autorizacao" and response.status_code == "103" and response.receipt:
                    record["operation"] = "recibo"
                    record["receipt"] = self._digits(response.receipt)
                    record["xml_b64"] = base64.b64encode(
                        self.build_receipt_query_xml(
                            receipt=record["receipt"],
                            environment=str(config.get("environment", "HOMOLOGACAO")),
                        )
                    ).decode("ascii")
                    record["status"] = "PENDENTE"
                    retry = max(1, int(record.get("retry_minutes", 5)))
                    record["next_attempt_at"] = (current + timedelta(minutes=retry)).isoformat()
                    record["last_error"] = ""
                elif operation == "recibo" and response.status_code == "105":
                    record["status"] = "PENDENTE"
                    retry = max(1, int(record.get("retry_minutes", 5)))
                    record["next_attempt_at"] = (current + timedelta(minutes=retry)).isoformat()
                    record["last_error"] = ""
                elif (
                    operation == "consulta"
                    and str(record.get("reconciliation_for") or "") == "evento_cancelamento"
                    and response.status_code in {"101", "151", "155"}
                ):
                    original_xml = base64.b64decode(
                        str(record.get("original_xml_b64") or "")
                    )
                    reconciled = FiscalResponse(
                        True, response.status_code, response.message,
                        response.protocol, response.receipt, queued_key, response.raw_xml,
                    )
                    event_record = self.register_event(
                        access_key=queued_key, event_type="CANCELAMENTO",
                        response=reconciled, request_xml=original_xml,
                        actor=str(record.get("actor") or "Sistema"),
                        metadata={"reconciled": True},
                    )
                    record["event_record"] = event_record
                    record["event_success"] = True
                    record["status"] = "CONCLUIDO"
                    record["completed_at"] = current.isoformat()
                    self._sync_sale_document(record, status="CANCELADO_FISCAL")
                elif (
                    operation == "consulta"
                    and str(record.get("reconciliation_for") or "") == "evento_cancelamento"
                    and response.status_code in self.AUTHORIZED_STATUS
                ):
                    record["event_success"] = False
                    record["status"] = "FALHA"
                    record["failed_at"] = current.isoformat()
                    record["last_error"] = (
                        "Consulta confirmou que o documento permanece autorizado; "
                        "cancelamento não confirmado."
                    )
                    self._sync_sale_document(
                        record, status="AUTORIZADO", error=record["last_error"]
                    )
                elif response.success:
                    is_authorization_result = operation in {"autorizacao", "recibo"} or (
                        operation == "consulta"
                        and str(record.get("reconciliation_for") or "") == "autorizacao"
                    )
                    if is_authorization_result:
                        response_key = self._normalize_access_key(response.access_key)
                        if len(queued_key) != 44:
                            raise ValueError("Item de autorização sem chave de acesso válida.")
                        if response_key != queued_key:
                            raise ValueError("A resposta SEFAZ não corresponde à chave enfileirada.")
                        original_b64 = str(record.get("original_xml_b64") or record.get("xml_b64", ""))
                        original_xml = base64.b64decode(original_b64)
                        nfe_xml = self._extract_nfe_xml(original_xml)
                        stored = self.store_document(
                            access_key=queued_key,
                            model=str(record.get("model", "55")),
                            environment=str(config.get("environment", "HOMOLOGACAO")),
                            request_xml=nfe_xml,
                            response=response,
                            actor=str(record.get("actor", "")),
                        )
                        record["document_record"] = {
                            "request_path": stored.get("request_path", ""),
                            "response_path": stored.get("response_path", ""),
                            "processed_path": stored.get("processed_path", ""),
                            "protocol": stored.get("protocol", ""),
                        }
                        reservation_id = str(record.get("reservation_id") or "")
                        if reservation_id:
                            self.confirm_number(
                                reservation_id, access_key=queued_key,
                            )
                    elif operation == "evento":
                        event_type = str(record.get("event_type") or "EVENTO").upper()
                        event_record = self.register_event(
                            access_key=queued_key,
                            event_type=event_type,
                            response=response,
                            request_xml=xml,
                            actor=str(record.get("actor") or "Sistema"),
                            metadata={
                                "justification": str(record.get("justification") or ""),
                                "no_circulation_confirmed": bool(
                                    record.get("no_circulation_confirmed")
                                ),
                                "requested_at": str(record.get("requested_at") or ""),
                            },
                        )
                        record["event_record"] = event_record
                        record["event_success"] = True
                        if event_type == "CANCELAMENTO":
                            self._sync_sale_document(
                                record, status="CANCELADO_FISCAL",
                            )
                    record["status"] = "CONCLUIDO"
                    record["completed_at"] = current.isoformat()
                    if is_authorization_result:
                        self._sync_sale_document(
                            record, status="AUTORIZADO", protocol=response.protocol
                        )
                else:
                    record["status"] = "FALHA"
                    record["failed_at"] = current.isoformat()
                    record["last_error"] = f"{response.status_code}: {response.message}"
                    if operation == "evento" and str(record.get("event_type") or "").upper() == "CANCELAMENTO":
                        event_record = self.register_event(
                            access_key=queued_key, event_type="CANCELAMENTO",
                            response=response, request_xml=xml,
                            actor=str(record.get("actor") or "Sistema"),
                            metadata={"justification": str(record.get("justification") or "")},
                        )
                        record["event_record"] = event_record
                        record["event_success"] = False
                        self._sync_sale_document(
                            record, status="AUTORIZADO", protocol="",
                            error=record["last_error"],
                        )
                    else:
                        self._sync_sale_document(record, status="FALHA", error=record["last_error"])
            except FiscalTransmissionUnknownError as exc:
                record["status"] = "RESPOSTA_DESCONHECIDA"
                record["unknown_since"] = current.isoformat()
                record["last_error"] = str(exc)
                record["next_attempt_at"] = ""
                self._sync_sale_document(
                    record, status="RESPOSTA_DESCONHECIDA", error=str(exc)
                )
            except Exception as exc:
                record["last_error"] = str(exc)
                if record.get("transmission_started_at") and not record.get("reconciliation_for"):
                    record["status"] = "RESPOSTA_DESCONHECIDA"
                    record["unknown_since"] = current.isoformat()
                    record["next_attempt_at"] = ""
                    self._sync_sale_document(
                        record, status="RESPOSTA_DESCONHECIDA", error=str(exc)
                    )
                    processed.append(dict(record))
                    continue
                if record.get("reconciliation_for"):
                    record["status"] = "RESPOSTA_DESCONHECIDA"
                    retry = min(60, max(1, int(record.get("retry_minutes", 5))) * 2 ** min(4, int(record.get("attempts", 1)) - 1))
                    record["next_attempt_at"] = (current + timedelta(minutes=retry)).isoformat()
                    record["last_reconciliation_at"] = current.isoformat()
                    self._sync_sale_document(
                        record, status="RESPOSTA_DESCONHECIDA", error=str(exc)
                    )
                    processed.append(dict(record))
                    continue
                if int(record["attempts"]) >= int(record.get("max_attempts", 1)):
                    record["status"] = "FALHA"
                    record["failed_at"] = current.isoformat()
                    self._sync_sale_document(record, status="FALHA", error=str(exc))
                else:
                    record["status"] = "ERRO"
                    retry = min(60, max(1, int(record.get("retry_minutes", 5))) * 2 ** min(4, int(record.get("attempts", 1)) - 1))
                    record["next_attempt_at"] = (current + timedelta(minutes=retry)).isoformat()
                    self._sync_sale_document(record, status="PENDENTE", error=str(exc))
            processed.append(dict(record))
        for record in processed:
            outbox.save_claimed_record(record, worker_id=worker_id, finish=True)
        return processed

    def prepare_claimed_reconciliation(
        self, record: Mapping[str, Any], *, worker_id: str
    ) -> dict[str, Any]:
        """Transforma claim desconhecido em consulta segura, preservando sua propriedade."""
        target = dict(record)
        if target.get("status") != "PROCESSANDO" or str(target.get("worker_id") or "") != str(worker_id):
            raise ValueError("A resposta desconhecida não pertence a este worker.")
        key = self._normalize_access_key(target.get("access_key", ""))
        receipt = self._digits(target.get("receipt", ""))
        environment = str(target.get("environment") or "HOMOLOGACAO")
        original_operation = str(target.get("operation") or "").lower()
        event_type = str(target.get("event_type") or "").upper()
        if original_operation == "evento" and event_type == "CANCELAMENTO" and len(key) == 44:
            target["operation"] = "consulta"
            query_xml = self.build_query_xml(access_key=key, environment=environment)
            target["reconciliation_for"] = "evento_cancelamento"
        elif receipt:
            target["operation"] = "recibo"
            query_xml = self.build_receipt_query_xml(receipt=receipt, environment=environment)
        elif len(key) == 44:
            target["operation"] = "consulta"
            query_xml = self.build_query_xml(access_key=key, environment=environment)
        else:
            raise ValueError("Não há recibo nem chave válida para reconciliar o documento.")
        target["xml_b64"] = base64.b64encode(query_xml).decode("ascii")
        if not target.get("reconciliation_for"):
            target["reconciliation_for"] = "autorizacao"
        target["reconciliation_started_at"] = datetime.now(timezone.utc).isoformat()
        FiscalOutboxService(self.connection_factory).save_claimed_record(
            target, worker_id=worker_id, finish=False
        )
        return target

    def _sale_document_cancelled(self, access_key: Any) -> bool:
        key = self._normalize_access_key(access_key)
        if len(key) != 44:
            return False
        conn = self.connection_factory()
        try:
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='fiscal_sale_documents'"
            ).fetchone()
            if not exists:
                return False
            row = conn.execute(
                "SELECT status FROM fiscal_sale_documents WHERE access_key=?", (key,)
            ).fetchone()
            return bool(row and str(row[0]).upper() in {"CANCELADO_LOCAL", "CANCELADO"})
        finally:
            conn.close()

    def _sync_sale_document(
        self, record: Mapping[str, Any], *, status: str, protocol: str = "", error: str = ""
    ) -> None:
        """Sincroniza o vínculo do PDV quando o schema 15 já estiver disponível."""
        access_key = self._normalize_access_key(record.get("access_key", ""))
        if len(access_key) != 44:
            return
        conn = self.connection_factory()
        try:
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='fiscal_sale_documents'"
            ).fetchone()
            if not exists:
                return
            conn.execute(
                """UPDATE fiscal_sale_documents
                      SET status=?,protocol=CASE WHEN ?='' THEN protocol ELSE ? END,
                          last_error=?,updated_at=? WHERE access_key=?""",
                (
                    status, str(protocol or ""), str(protocol or ""), str(error or ""),
                    datetime.now(timezone.utc).isoformat(), access_key,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def retry_transmission(self, queue_id: str) -> dict[str, Any]:
        actor = self._authenticated_outbox_actor("transmit")
        rows = self.list_transmission_queue()
        target = None
        for record in rows:
            if str(record.get("id")) == str(queue_id):
                target = record
                break
        if target is None:
            raise ValueError("Item da fila fiscal não encontrado.")
        if target.get("status") in {"CONCLUIDO", "CANCELADO"}:
            raise ValueError("Transmissão concluída ou cancelada não pode ser reenviada.")
        if target.get("status") == "RESPOSTA_DESCONHECIDA" or target.get("transmission_started_at"):
            raise ValueError(
                "O resultado da transmissão precisa ser consultado na SEFAZ antes de reenviar."
            )
        if str(target.get("status") or "").upper() not in {"FALHA", "ERRO"}:
            raise ValueError("Somente uma transmissão fiscal com falha definida pode ser reenviada.")
        operation = str(target.get("operation") or "").lower()
        if operation in {"consulta", "recibo"}:
            status_code = str(target.get("last_status_code") or "").strip()
            reconciliation = str(target.get("reconciliation_for") or "").strip()
            if status_code != "217" or reconciliation != "autorizacao":
                raise ValueError(
                    "A consulta fiscal não confirmou ausência da NF-e; reenvio permanece bloqueado."
                )
            original_b64 = str(target.get("original_xml_b64") or "").strip()
            try:
                original_xml = base64.b64decode(original_b64, validate=True)
            except (ValueError, TypeError, binascii.Error) as exc:
                raise ValueError("XML original da NF-e não está disponível para reenvio seguro.") from exc
            queued_key = self._normalize_access_key(target.get("access_key", ""))
            if len(queued_key) != 44 or self._extract_access_key_from_xml(original_xml) != queued_key:
                raise ValueError("XML original não corresponde à chave fiscal enfileirada.")
            target["operation"] = "autorizacao"
            target["xml_b64"] = original_b64
            target.pop("reconciliation_for", None)
            target.pop("reconciliation_started_at", None)
        target.update({
            "status": "PENDENTE",
            "next_attempt_at": datetime.now(timezone.utc).isoformat(),
            "retried_by": str(actor or "").strip(),
            "retried_at": datetime.now(timezone.utc).isoformat(),
            "last_error": "",
        })
        self._save_transmission_queue(rows)
        self._sync_sale_document(target, status="PENDENTE")
        return dict(target)

    def force_receipt_check(self, queue_id: str) -> dict[str, Any]:
        """Agenda consulta imediata de recibo já existente sem reenviar a NF-e/NFC-e."""
        actor = self._authenticated_outbox_actor("transmit")
        rows = self.list_transmission_queue()
        target = next((row for row in rows if str(row.get("id")) == str(queue_id)), None)
        if target is None:
            raise ValueError("Item da fila fiscal não encontrado.")
        if str(target.get("operation") or "").lower() != "recibo" or not self._digits(target.get("receipt")):
            raise ValueError("O documento selecionado ainda não possui recibo da SEFAZ para consulta.")
        if target.get("status") in {"CONCLUIDO", "CANCELADO"}:
            raise ValueError("Documento concluído ou cancelado não exige consulta de recibo.")
        now = datetime.now(timezone.utc).isoformat()
        target.update({
            "status": "PENDENTE", "next_attempt_at": now,
            "receipt_check_requested_by": str(actor or "").strip(),
            "receipt_check_requested_at": now, "last_error": "",
        })
        self._save_transmission_queue(rows)
        return dict(target)

    def _authenticated_fiscal_actor(self, action: str, *, operation: str) -> str:
        if self._authorization_provider is None or not self._authorization_provider(action):
            raise PermissionError(
                f"Uma sessão autenticada com permissão fiscal é obrigatória para {operation}."
            )
        if self._actor_provider is None:
            raise PermissionError(
                f"Uma sessão autenticada é obrigatória para {operation}."
            )
        try:
            actor = str(self._actor_provider() or "").strip()
        except PermissionError:
            raise
        except Exception as exc:
            raise PermissionError(
                f"Não foi possível confirmar a identidade autenticada para {operation}."
            ) from exc
        if not actor:
            raise PermissionError(
                "A sessão autenticada não possui uma identidade válida."
            )
        return actor

    def require_authenticated_actor(self, action: str, *, operation: str) -> str:
        """Expõe a mesma autoridade de sessão a efeitos locais fiscais coordenados."""
        return self._authenticated_fiscal_actor(action, operation=operation)

    def _authenticated_outbox_actor(self, action: str) -> str:
        return self._authenticated_fiscal_actor(
            action, operation="alterar a fila fiscal"
        )

    def reconcile_unknown(self, queue_id: str) -> dict[str, Any]:
        """Agenda somente consulta por recibo/chave; nunca retransmite a autorização."""
        actor = self._authenticated_outbox_actor("transmit")
        rows = self.list_transmission_queue()
        target = next((row for row in rows if str(row.get("id")) == str(queue_id)), None)
        if target is None:
            raise ValueError("Item da fila fiscal não encontrado.")
        if str(target.get("status") or "").upper() != "RESPOSTA_DESCONHECIDA":
            raise ValueError("Somente respostas desconhecidas exigem reconciliação segura.")
        key = self._normalize_access_key(target.get("access_key", ""))
        receipt = self._digits(target.get("receipt", ""))
        environment = str(target.get("environment") or "HOMOLOGACAO")
        if receipt:
            target["operation"] = "recibo"
            query_xml = self.build_receipt_query_xml(receipt=receipt, environment=environment)
        elif len(key) == 44:
            target["operation"] = "consulta"
            query_xml = self.build_query_xml(access_key=key, environment=environment)
        else:
            raise ValueError("Não há recibo nem chave válida para consultar a SEFAZ.")
        now = datetime.now(timezone.utc).isoformat()
        target.update({
            "status": "PENDENTE", "next_attempt_at": now,
            "xml_b64": base64.b64encode(query_xml).decode("ascii"),
            "reconciliation_for": "autorizacao",
            "reconciliation_requested_by": str(actor or "").strip(),
            "reconciliation_requested_at": now, "last_error": "",
        })
        self._save_transmission_queue(rows)
        return dict(target)

    def retry_contingency_batch(self) -> dict[str, Any]:
        """Reagenda em lote somente documentos NFC-e emitidos em contingência."""
        actor = self._authenticated_outbox_actor("transmit")
        rows = self.list_transmission_queue()
        now = datetime.now(timezone.utc).isoformat()
        selected: list[str] = []
        for target in rows:
            if str(target.get("model") or "") != "65":
                continue
            if target.get("status") in {"CONCLUIDO", "CANCELADO", "RESPOSTA_DESCONHECIDA"}:
                continue
            if target.get("transmission_started_at"):
                continue
            if str(target.get("operation") or "").lower() not in {"autorizacao", "recibo"}:
                continue
            try:
                original_xml = base64.b64decode(
                    str(target.get("original_xml_b64") or target.get("xml_b64") or "")
                )
            except (ValueError, TypeError):
                continue
            is_contingency = bool(target.get("contingency")) or self._xml_emission_type(original_xml) != 1
            if not is_contingency:
                continue
            target.update({
                "contingency": True, "status": "PENDENTE", "next_attempt_at": now,
                "contingency_batch_requested_by": str(actor or "").strip(),
                "contingency_batch_requested_at": now, "last_error": "",
            })
            selected.append(str(target.get("id") or ""))
        if selected:
            self._save_transmission_queue(rows)
        return {"scheduled": len(selected), "queue_ids": selected, "requested_at": now}

    def cancel_transmission(self, queue_id: str, *, reason: str) -> dict[str, Any]:
        actor = self._authenticated_outbox_actor("transmit")
        rows = self.list_transmission_queue()
        target = next((record for record in rows if str(record.get("id")) == str(queue_id)), None)
        if target is None:
            raise ValueError("Item da fila fiscal não encontrado.")
        if target.get("status") == "CONCLUIDO":
            raise ValueError("Transmissão concluída não pode ser cancelada localmente.")
        if target.get("status") == "RESPOSTA_DESCONHECIDA" or target.get("transmission_started_at"):
            raise ValueError(
                "Transmissão com resultado desconhecido não pode ser cancelada localmente. "
                "Consulte a SEFAZ primeiro."
            )
        target.update({
            "status": "CANCELADO", "cancelled_by": str(actor or "").strip(),
            "cancelled_at": datetime.now(timezone.utc).isoformat(),
            "cancel_reason": str(reason or "").strip(), "next_attempt_at": "",
        })
        self._save_transmission_queue(rows)
        return dict(target)

    def authorize_document(
        self,
        *,
        xml: bytes | str,
        access_key: str,
        password: str,
        model: str = "55",
        reservation_id: str = "",
    ) -> tuple[FiscalResponse, dict[str, Any]]:
        key = self._normalize_access_key(access_key)
        if len(key) != 44:
            raise ValueError("Chave de acesso inválida para autorização.")
        actor = self.require_operational_readiness(
            operation="autorizacao", model=model, password=password,
            permission="transmit", series=int(key[22:25]),
            require_catalog=True, require_numbering=True,
        )
        config = self.load_config()

        reservation_id = str(reservation_id or "").strip()
        if not reservation_id:
            raise ValueError("Uma reserva de numeração é obrigatória para autorizar o documento.")
        reservation = next(
            (item for item in self.numbering_status() if item.get("id") == reservation_id),
            None,
        )
        if not reservation:
            raise ValueError("Reserva de numeração não encontrada.")
        if reservation.get("status") != "RESERVADO":
            raise ValueError("A numeração não está reservada para autorização.")
        if str(reservation.get("environment", "")).upper() != str(config["environment"]).upper():
            raise ValueError("A reserva pertence a outro ambiente fiscal.")
        if str(reservation.get("model")) != str(model):
            raise ValueError("A reserva pertence a outro modelo fiscal.")
        expected_series = int(key[22:25])
        expected_number = int(key[25:34])
        if expected_series != int(reservation.get("series", -1)) or expected_number != int(reservation.get("number", -1)):
            raise ValueError("A chave de acesso não corresponde à numeração reservada.")

        xml_key = self._extract_access_key_from_xml(xml)
        if xml_key and xml_key != key:
            raise ValueError("A chave informada não corresponde ao XML fiscal.")

        if str(model) == "65":
            xml = self.add_nfce_qr_code_v3(
                xml, pfx_path=config["certificate_path"], password=password
            )
        signed = self.sign_xml(xml, reference_id=f"NFe{key}", pfx_path=config["certificate_path"], password=password)
        self.validate_official_xml(signed, document_type="nfe")
        envelope = self._authorization_envelope(signed, environment=config["environment"])
        response = self.transmit(operation="autorizacao", model=model, xml=envelope, pfx_path=config["certificate_path"], password=password)
        record = self.store_document(
            access_key=key,
            model=model,
            environment=config["environment"],
            request_xml=signed,
            response=response,
            actor=actor,
        )
        if response.success:
            numbering = self.confirm_number(reservation_id, access_key=key)
            record = dict(record)
            record["numbering"] = numbering
        return response, record

    def consult_document(self, *, access_key: str, password: str) -> FiscalResponse:
        key = self._normalize_access_key(access_key)
        model = key[20:22] if len(key) == 44 else str(self.load_config().get("default_model") or "65")
        self.require_operational_readiness(
            operation="consulta", model=model, password=password,
            permission="view",
        )
        config = self.load_config()
        xml = self.build_query_xml(access_key=access_key, environment=config["environment"])
        self.validate_official_xml(xml, document_type="consulta")
        return self.transmit(operation="consulta", model=model, xml=xml, pfx_path=config["certificate_path"], password=password)

    def send_event(self, *, event_type: str, access_key: str, sequence: int, password: str, protocol: str = "", justification: str = "", correction: str = "") -> tuple[FiscalResponse, dict[str, Any]]:
        key = self._normalize_access_key(access_key)
        model = key[20:22] if len(key) == 44 else str(self.load_config().get("default_model") or "65")
        actor = self.require_operational_readiness(
            operation="evento", model=model, password=password,
            permission="transmit",
        )
        config = self.load_config()
        self.validate_event_eligibility(
            access_key=access_key, event_type=event_type, sequence=sequence, protocol=protocol
        )
        xml, event_id = self.build_event_xml(event_type=event_type, access_key=access_key, sequence=sequence, actor_document=config["cnpj"], protocol=protocol, justification=justification, correction=correction, environment=config["environment"])
        signed = self.sign_xml(xml, reference_id=event_id, pfx_path=config["certificate_path"], password=password)
        envelope = self._event_envelope(signed)
        self.validate_official_xml(envelope, document_type="evento")
        response = self.transmit(operation="evento", model=model, xml=envelope, pfx_path=config["certificate_path"], password=password)
        record = self.register_event(access_key=access_key, event_type=event_type, response=response, request_xml=envelope, actor=actor)
        return response, record

    def inutilize_numbers(self, *, year: int, model: str, series: int, start_number: int, end_number: int, justification: str, password: str) -> tuple[FiscalResponse, dict[str, Any]]:
        actor = self.require_operational_readiness(
            operation="inutilizacao", model=model, password=password,
            permission="transmit", series=series, require_numbering=True,
        )
        config = self.load_config()
        state_code = self.STATE_CODES.get(str(config.get("state", "")).upper())
        if not state_code:
            raise ValueError("UF do emitente não possui código IBGE configurável.")
        xml, identifier = self.build_inutilization_xml(state_code=state_code, year=year, cnpj=config["cnpj"], model=model, series=series, start_number=start_number, end_number=end_number, justification=justification, environment=config["environment"])
        signed = self.sign_xml(xml, reference_id=identifier, pfx_path=config["certificate_path"], password=password)
        self.validate_official_xml(signed, document_type="inutilizacao")
        response = self.transmit(operation="inutilizacao", model=model, xml=signed, pfx_path=config["certificate_path"], password=password)
        record = self.register_event(
            access_key="0" * 44, event_type="INUTILIZACAO", response=response,
            request_xml=signed, actor=actor,
            metadata={
                "model": model, "series": int(series),
                "start_number": int(start_number), "end_number": int(end_number),
                "year": int(year), "environment": str(config.get("environment") or ""),
            },
        )
        return response, record

    @classmethod
    def _extract_access_key_from_xml(cls, xml: bytes | str) -> str:
        raw = xml.encode("utf-8") if isinstance(xml, str) else bytes(xml)
        try:
            root = etree.fromstring(raw, parser=etree.XMLParser(resolve_entities=False, no_network=True))
        except (etree.XMLSyntaxError, ValueError, TypeError):
            return ""
        identifier = str(root.xpath("string(//*[local-name()='infNFe'][1]/@Id)") or "")
        key = cls._normalize_access_key(identifier.replace("NFe", ""))
        if len(key) == 44:
            return key
        protocol_key = cls._normalize_access_key(str(root.xpath("string(//*[local-name()='chNFe'][1])") or ""))
        return protocol_key if len(protocol_key) == 44 else ""

    @staticmethod
    def _extract_nfe_xml(xml: bytes | str) -> bytes:
        raw = xml.encode("utf-8") if isinstance(xml, str) else bytes(xml)
        root = etree.fromstring(raw, parser=etree.XMLParser(resolve_entities=False, no_network=True))
        if etree.QName(root).localname == "NFe":
            return etree.tostring(root, xml_declaration=True, encoding="utf-8")
        nodes = root.xpath("//*[local-name()='NFe'][1]")
        if not nodes:
            raise ValueError("XML de autorização não contém uma NF-e assinada.")
        return etree.tostring(nodes[0], xml_declaration=True, encoding="utf-8")

    @staticmethod
    def _authorization_envelope(signed_xml: bytes, *, environment: str) -> bytes:
        ns = "http://www.portalfiscal.inf.br/nfe"
        root = etree.Element(etree.QName(ns, "enviNFe"), nsmap={None: ns}, versao="4.00")
        id_lote = etree.SubElement(root, etree.QName(ns, "idLote")); id_lote.text = datetime.now().strftime("%Y%m%d%H%M%S")
        ind = etree.SubElement(root, etree.QName(ns, "indSinc")); ind.text = "1"
        nfe = etree.fromstring(signed_xml, parser=etree.XMLParser(resolve_entities=False, no_network=True))
        root.append(nfe)
        return etree.tostring(root, xml_declaration=True, encoding="utf-8")

    @staticmethod
    def _event_envelope(signed_xml: bytes) -> bytes:
        ns = "http://www.portalfiscal.inf.br/nfe"
        root = etree.Element(etree.QName(ns, "envEvento"), nsmap={None: ns}, versao="1.00")
        lot = etree.SubElement(root, etree.QName(ns, "idLote"))
        lot.text = datetime.now().strftime("%y%m%d%H%M%S%f")[-15:]
        event = etree.fromstring(
            signed_xml,
            parser=etree.XMLParser(resolve_entities=False, no_network=True),
        )
        root.append(event)
        return etree.tostring(root, xml_declaration=True, encoding="utf-8")

    def _temporary_pem_files(self, pfx_path: str | Path, password: str) -> tuple[str, str]:
        key, cert, chain = pkcs12.load_key_and_certificates(Path(pfx_path).read_bytes(), str(password).encode("utf-8"))
        if key is None or cert is None:
            raise ValueError("Certificado A1 inválido para comunicação.")
        cert_bytes = cert.public_bytes(serialization.Encoding.PEM)
        for item in chain or []:
            cert_bytes += item.public_bytes(serialization.Encoding.PEM)
        key_bytes = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        cert_file = tempfile.NamedTemporaryFile(prefix="nabicode_cert_", suffix=".pem", delete=False)
        key_file = tempfile.NamedTemporaryFile(prefix="nabicode_key_", suffix=".pem", delete=False)
        try:
            os.chmod(cert_file.name, 0o600)
            os.chmod(key_file.name, 0o600)
            cert_file.write(cert_bytes)
            cert_file.flush()
            os.fsync(cert_file.fileno())
            key_file.write(key_bytes)
            key_file.flush()
            os.fsync(key_file.fileno())
        except Exception:
            cert_file.close()
            key_file.close()
            self._secure_delete_file(cert_file.name)
            self._secure_delete_file(key_file.name)
            raise
        finally:
            if not cert_file.closed:
                cert_file.close()
            if not key_file.closed:
                key_file.close()
        return cert_file.name, key_file.name

    @staticmethod
    def _temporary_server_ca_bundle() -> str:
        """Combina Mozilla/certifi com as autoridades confiáveis do Windows.

        ``requests`` substitui o repositório do sistema pelo bundle do certifi.
        Alguns serviços estaduais dependem de uma intermediária já distribuída
        pelo Windows; usar apenas certifi produz ``unable to get local issuer``.
        A composição mantém a verificação TLS obrigatória e nunca inclui o A1.
        """
        if requests is None:
            raise RuntimeError("A dependência 'requests' não está instalada.")
        chunks: list[bytes] = []
        seen: set[str] = set()

        certifi_path = Path(requests.certs.where())
        if certifi_path.is_file():
            chunks.append(certifi_path.read_bytes().rstrip() + b"\n")

        # O catálogo público oficial do ITI já é verificado por SHA-512 em
        # cada leitura. Ele inclui as intermediárias ICP-Brasil que alguns
        # endpoints estaduais não entregam durante o handshake TLS.
        resource_root = Path(__file__).resolve().parents[1] / "resources" / "fiscal" / "icp_brasil"
        catalog_path = resource_root / "catalog.json"
        if catalog_path.is_file():
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            archive_path = resource_root / str(catalog.get("file") or "")
            expected_hash = str(catalog.get("sha512") or "").lower()
            archive_bytes = archive_path.read_bytes()
            if not expected_hash or hashlib.sha512(archive_bytes).hexdigest() != expected_hash:
                raise RuntimeError("O catálogo público ICP-Brasil falhou na verificação de integridade.")
            with zipfile.ZipFile(archive_path) as archive:
                for name in sorted(archive.namelist()):
                    if not name.lower().endswith((".crt", ".cer", ".pem")):
                        continue
                    raw = archive.read(name)
                    try:
                        public_cert = (
                            x509.load_pem_x509_certificate(raw)
                            if b"BEGIN CERTIFICATE" in raw
                            else x509.load_der_x509_certificate(raw)
                        )
                    except (TypeError, ValueError):
                        continue
                    der = public_cert.public_bytes(serialization.Encoding.DER)
                    digest = hashlib.sha256(der).hexdigest()
                    if digest in seen:
                        continue
                    seen.add(digest)
                    chunks.append(public_cert.public_bytes(serialization.Encoding.PEM))

        enum_certificates = getattr(ssl, "enum_certificates", None)
        if os.name == "nt" and callable(enum_certificates):
            for store in ("ROOT", "CA"):
                for certificate, encoding, trust in enum_certificates(store):
                    if encoding != "x509_asn":
                        continue
                    if trust is not True and (
                        not isinstance(trust, set)
                        or "1.3.6.1.5.5.7.3.1" not in trust
                    ):
                        continue
                    digest = hashlib.sha256(certificate).hexdigest()
                    if digest in seen:
                        continue
                    seen.add(digest)
                    chunks.append(
                        ssl.DER_cert_to_PEM_cert(certificate).encode("ascii")
                    )

        if not chunks:
            raise RuntimeError(
                "Nenhuma autoridade certificadora confiável está disponível para HTTPS."
            )
        bundle = tempfile.NamedTemporaryFile(
            prefix="nabicode_server_ca_", suffix=".pem", delete=False
        )
        try:
            os.chmod(bundle.name, 0o600)
            bundle.write(b"\n".join(chunks))
            bundle.flush()
            os.fsync(bundle.fileno())
        except Exception:
            bundle.close()
            FiscalService._secure_delete_file(bundle.name)
            raise
        finally:
            if not bundle.closed:
                bundle.close()
        return bundle.name

    @staticmethod
    def _secure_delete_file(path: str | Path) -> None:
        """Sobrescreve o conteúdo temporário quando possível e remove o arquivo."""
        target = Path(path)
        try:
            if target.is_file():
                size = target.stat().st_size
                if size > 0:
                    with target.open("r+b", buffering=0) as stream:
                        stream.write(b"\x00" * size)
                        stream.flush()
                        os.fsync(stream.fileno())
        except OSError:
            pass
        try:
            target.unlink(missing_ok=True)
        except OSError:
            pass

    @staticmethod
    def _atomic_write_bytes(path: Path, data: bytes) -> None:
        """Grava bytes sem expor arquivo fiscal parcialmente escrito."""
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
        temp_path = Path(temp_name)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, path)
        except Exception:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise

    @staticmethod
    def _cert_datetime(cert: x509.Certificate, utc_attr: str, legacy_attr: str) -> datetime:
        value = getattr(cert, utc_attr, None) or getattr(cert, legacy_attr)
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

    @staticmethod
    def _document_from_certificate(cert: x509.Certificate) -> str:
        # No padrão ICP-Brasil, o CNPJ empresarial possui OID próprio no
        # SubjectAlternativeName. Ele precisa ter precedência sobre o CN, que
        # pode conter também CPF do responsável ou outros números.
        try:
            alternative_names = cert.extensions.get_extension_for_class(
                x509.SubjectAlternativeName
            ).value
            for other_name in alternative_names.get_values_for_type(x509.OtherName):
                if other_name.type_id.dotted_string != "2.16.76.1.3.3":
                    continue
                candidates = re.findall(rb"[0-9]{14}", bytes(other_name.value))
                for candidate in candidates:
                    document = candidate.decode("ascii")
                    if FiscalService._is_valid_cnpj(document):
                        return document
        except x509.ExtensionNotFound:
            pass
        for attribute in cert.subject:
            value = str(attribute.value)
            for token in re.findall(r"(?<![A-Z0-9])[A-Z0-9][A-Z0-9./-]{12,20}(?![A-Z0-9])", value.upper()):
                try:
                    document = FiscalService._normalize_cnpj(token)
                except ValueError:
                    continue
                if FiscalService._is_valid_cnpj_format(document):
                    return document
            digits = FiscalService._digits(value)
            if len(digits) == 14:
                return digits
        return ""

    @staticmethod
    def _normalize_cnpj(value: Any) -> str:
        normalized = re.sub(r"[\s./-]+", "", str(value or "").upper())
        if normalized and not re.fullmatch(r"[A-Z0-9]+", normalized):
            raise ValueError("CNPJ contém caracteres inválidos.")
        return normalized

    @staticmethod
    def _is_valid_cnpj_format(value: Any) -> bool:
        try:
            normalized = FiscalService._normalize_cnpj(value)
        except ValueError:
            return False
        return bool(re.fullmatch(r"[A-Z0-9]{12}[0-9]{2}", normalized))

    @staticmethod
    def _is_valid_cnpj(value: Any) -> bool:
        if not FiscalService._is_valid_cnpj_format(value):
            return False
        normalized = FiscalService._normalize_cnpj(value)

        def digit(text: str, weights: Sequence[int]) -> int:
            total = sum((ord(char) - 48) * weight for char, weight in zip(text, weights))
            remainder = total % 11
            return 0 if remainder < 2 else 11 - remainder

        first = digit(normalized[:12], (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
        second = digit(normalized[:12] + str(first), (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
        return normalized[-2:] == f"{first}{second}"

    @staticmethod
    def _normalize_access_key(value: Any) -> str:
        normalized = re.sub(r"[\s.-]+", "", str(value or "").upper())
        if normalized and not re.fullmatch(r"[A-Z0-9]+", normalized):
            raise ValueError("Chave de acesso contém caracteres inválidos.")
        return normalized

    @staticmethod
    def _is_valid_access_key(value: Any) -> bool:
        try:
            normalized = FiscalService._normalize_access_key(value)
        except ValueError:
            return False
        if not re.fullmatch(r"[0-9]{6}[A-Z0-9]{12}[0-9]{26}", normalized):
            return False
        return FiscalService.calculate_access_key_digit(normalized[:43]) == normalized[-1]

    @staticmethod
    def _normalize_tax_document(value: Any) -> str:
        raw = str(value or "")
        return FiscalService._normalize_cnpj(raw) if re.search(r"[A-Za-z]", raw) else FiscalService._digits(raw)

    @staticmethod
    def _is_valid_cpf(value: Any) -> bool:
        cpf = FiscalService._digits(value)
        if len(cpf) != 11 or cpf == cpf[0] * 11:
            return False
        for size in (9, 10):
            total = sum(int(cpf[index]) * (size + 1 - index) for index in range(size))
            digit = 11 - total % 11
            if digit >= 10:
                digit = 0
            if int(cpf[size]) != digit:
                return False
        return True

    @staticmethod
    def _digits(value: Any) -> str:
        return "".join(ch for ch in str("" if value is None else value) if ch.isdigit())

    def _load_numbering(self) -> dict[str, Any]:
        conn = self.connection_factory()
        try:
            return self._load_numbering_conn(conn)
        finally:
            conn.close()

    def _load_numbering_conn(self, conn: Any) -> dict[str, Any]:
        row = conn.execute("SELECT valor FROM configuracoes WHERE chave = ?", (self.NUMBERING_KEY,)).fetchone()
        if row is None:
            has_history = False
            for table in ("fiscal_sale_documents", "fiscal_outbox"):
                exists = conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
                ).fetchone()
                if exists and conn.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone():
                    has_history = True
                    break
            if has_history:
                raise RuntimeError(
                    "A numeração fiscal não foi encontrada, mas já existem documentos fiscais. "
                    "A emissão foi bloqueada para impedir reutilização de número."
                )
            return {"scopes": {}, "records": {}, "initializations": []}
        try:
            data = json.loads(str(row[0]))
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                "A numeração fiscal armazenada está corrompida; emissão bloqueada."
            ) from exc
        if not isinstance(data, dict):
            raise RuntimeError(
                "A numeração fiscal armazenada possui formato inválido; emissão bloqueada."
            )
        data.setdefault("scopes", {})
        data.setdefault("records", {})
        data.setdefault("initializations", [])
        return data

    def _save_numbering_conn(self, conn: Any, data: Mapping[str, Any]) -> None:
        conn.execute(
            "INSERT OR REPLACE INTO configuracoes (chave, valor) VALUES (?, ?)",
            (self.NUMBERING_KEY, json.dumps(dict(data), ensure_ascii=False, sort_keys=True)),
        )

    def _recover_expired_reservations(
        self, data: dict[str, Any], *, now: datetime, connection: Any | None = None
    ) -> None:
        for record in data.get("records", {}).values():
            if record.get("status") != "RESERVADO":
                continue
            try:
                expires_at = datetime.fromisoformat(str(record.get("expires_at", "")))
            except ValueError:
                expires_at = now - timedelta(seconds=1)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at <= now:
                if connection is not None and self._reservation_is_linked(
                    connection, str(record.get("id") or "")
                ):
                    record["expiration_blocked_at"] = now.isoformat()
                    record["expiration_blocked_reason"] = "Documento fiscal vinculado."
                    continue
                record.update({
                    "status": "LIBERADO",
                    "released_at": now.isoformat(),
                    "released_by": "SISTEMA",
                    "release_reason": "Reserva expirada automaticamente.",
                })

    @staticmethod
    def _reservation_is_linked(connection: Any, reservation_id: str) -> bool:
        if not reservation_id:
            return False
        table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='fiscal_sale_documents'"
        ).fetchone()
        return bool(table and connection.execute(
            "SELECT 1 FROM fiscal_sale_documents WHERE reservation_id=? LIMIT 1",
            (reservation_id,),
        ).fetchone())

    @staticmethod
    def _reservation_has_transmission_risk(connection: Any, reservation_id: str) -> bool:
        table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='fiscal_outbox'"
        ).fetchone()
        if not table:
            return False
        row = connection.execute(
            """SELECT status,attempts,metadata_json FROM fiscal_outbox
                 WHERE reservation_id=? ORDER BY id DESC LIMIT 1""",
            (reservation_id,),
        ).fetchone()
        if not row:
            return False
        try:
            metadata = json.loads(str(row[2] or "{}"))
        except (TypeError, ValueError):
            metadata = {}
        return bool(
            int(row[1] or 0) > 0
            or str(row[0] or "").upper() in {
                "PROCESSANDO", "RESPOSTA_DESCONHECIDA", "CONCLUIDO"
            }
            or metadata.get("transmission_started_at")
        )

    def _get_setting(self, key: str) -> str | None:
        conn = self.connection_factory()
        try:
            row = conn.execute("SELECT valor FROM configuracoes WHERE chave = ?", (str(key),)).fetchone()
            return None if row is None else str(row[0])
        finally:
            conn.close()

    def _set_setting(self, key: str, value: str) -> None:
        conn = self.connection_factory()
        try:
            conn.execute("INSERT OR REPLACE INTO configuracoes (chave, valor) VALUES (?, ?)", (str(key), str(value)))
            conn.commit()
        finally:
            conn.close()
