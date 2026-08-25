from __future__ import annotations

import argparse
import builtins
import hashlib
import http.client
import io
import json
import os
import socket
import sqlite3
import urllib.request
import _socket
import _sqlite3
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence
from unittest.mock import patch


DOSSIER_SCHEMA_VERSION = "1.0"
HARNESS_VERSION = "1.1.0"
FIXED_TEST_TIME = "2026-08-25T12:00:00-03:00"
DEFAULT_SOURCE_REVISION = (
    "base:a179e791a82bc0a58c4ccccc1bccf357b6008fa8+"
    "codex/fiscal-regressao-offline"
)


class OfflineBoundaryViolation(RuntimeError):
    """Indica tentativa de sair da fronteira estritamente offline do harness."""


class SimulatedTimeout(TimeoutError):
    def __init__(self, message: str, *, dispatched: bool) -> None:
        super().__init__(message)
        self.dispatched = bool(dispatched)


class FakeStateTransitionBlocked(RuntimeError):
    """Indica que a máquina de estados fake recusou uma transição insegura."""


@dataclass(frozen=True)
class FakeFiscalResponse:
    success: bool
    status_code: str
    message: str
    protocol: str = ""


@dataclass
class FakeReadinessAdapter:
    """Matriz simbólica: não lê arquivo, certificado, configuração ou banco."""

    profile: str = "TESTE"
    checks: int = 0
    real_certificate_reads: int = 0
    test_double_kind: str = "FAKE_READINESS_DETERMINISTICO"

    def require(
        self,
        *,
        gate_composed: bool = True,
        permission: bool = True,
        symbolic_certificate_ready: bool = True,
        symbolic_numbering_ready: bool = True,
        production: bool = False,
    ) -> None:
        self.checks += 1
        if self.profile != "TESTE":
            raise PermissionError("O dossiê offline aceita exclusivamente o perfil TESTE.")
        if production:
            raise PermissionError("Produção fiscal permanece bloqueada.")
        if not gate_composed:
            raise PermissionError("Portão de prontidão fiscal não composto.")
        if not permission:
            raise PermissionError("Sessão/permissão fiscal ausente.")
        if not symbolic_certificate_ready:
            raise PermissionError("Pré-condição simbólica A1 ausente no cenário fake.")
        if not symbolic_numbering_ready:
            raise PermissionError("Numeração fiscal simbólica não inicializada no cenário fake.")


@dataclass
class FakeFiscalStore:
    """Estado efêmero em memória; deliberadamente não oferece conexão/SQL."""

    records: dict[str, dict[str, Any]] = field(default_factory=dict)
    writes: int = 0
    real_database_connections: int = 0
    test_double_kind: str = "FAKE_STORE_EM_MEMORIA"

    def save(self, record_id: str, **values: Any) -> dict[str, Any]:
        current = dict(self.records.get(record_id, {}))
        current.update(values)
        self.records[record_id] = current
        self.writes += 1
        return dict(current)

    def get(self, record_id: str) -> dict[str, Any]:
        return dict(self.records.get(record_id, {}))


@dataclass
class FakeFiscalTransport:
    """Retornos roteirizados; nunca possui URL, socket, TLS ou certificado."""

    calls: list[str] = field(default_factory=list)
    real_network_calls: int = 0
    real_certificate_reads: int = 0
    test_double_kind: str = "FAKE_TRANSPORT_ROTEIRIZADO"

    def authorize(self, outcome: str) -> FakeFiscalResponse:
        self.calls.append(f"authorize:{outcome}")
        if outcome == "authorized":
            return FakeFiscalResponse(
                True, "100", "AUTORIZAÇÃO SIMULADA — SEM SEFAZ",
                "PROTOCOLO-SINTETICO-TESTE-AUT-001",
            )
        if outcome == "rejected":
            return FakeFiscalResponse(False, "302", "REJEIÇÃO SIMULADA — SEM SEFAZ")
        if outcome == "timeout_before_dispatch":
            raise SimulatedTimeout("timeout fake antes do despacho", dispatched=False)
        if outcome == "timeout_after_dispatch":
            raise SimulatedTimeout("timeout fake após despacho", dispatched=True)
        if outcome == "unknown_payload":
            return FakeFiscalResponse(False, "", "RESPOSTA FAKE NÃO CLASSIFICÁVEL")
        raise ValueError("Roteiro fake de autorização desconhecido.")

    def query(self, outcome: str) -> FakeFiscalResponse:
        self.calls.append(f"query:{outcome}")
        if outcome == "authorized":
            return FakeFiscalResponse(
                True, "100", "CONSULTA SIMULADA CONFIRMOU AUTORIZAÇÃO",
                "PROTOCOLO-SINTETICO-TESTE-CONS-001",
            )
        raise ValueError("Roteiro fake de consulta desconhecido.")

    def event(self, event_type: str) -> FakeFiscalResponse:
        event = str(event_type).upper()
        self.calls.append(f"event:{event}")
        if event == "CANCELAMENTO":
            return FakeFiscalResponse(
                True, "135", "EVENTO SIMULADO REGISTRADO — SEM SEFAZ",
                "PROTOCOLO-SINTETICO-TESTE-CAN-001",
            )
        raise ValueError("Evento fake desconhecido.")

    def inutilize(self) -> FakeFiscalResponse:
        self.calls.append("inutilize")
        return FakeFiscalResponse(
            True, "102", "INUTILIZAÇÃO SIMULADA — SEM SEFAZ",
            "PROTOCOLO-SINTETICO-TESTE-INU-001",
        )


@dataclass
class OfflineBoundaryAudit:
    installed_guards: tuple[str, ...] = (
        "socket.socket",
        "socket.SocketType",
        "socket.create_connection",
        "socket.socketpair/fromfd/fromshare",
        "socket DNS resolution",
        "_socket.socket",
        "urllib.request.urlopen",
        "http.client.HTTPConnection.connect",
        "sqlite3.connect",
        "sqlite3.dbapi2/_sqlite3 connect/Connection",
        "builtins/io/_io/os.open(certificados/chaves)",
    )
    real_network_attempts: int = 0
    real_database_attempts: int = 0
    real_certificate_attempts: int = 0


def _blocked_boundary(audit: OfflineBoundaryAudit, kind: str, target: str):
    def blocker(*_args: Any, **_kwargs: Any) -> None:
        if kind == "network":
            audit.real_network_attempts += 1
        elif kind == "database":
            audit.real_database_attempts += 1
        else:
            audit.real_certificate_attempts += 1
        raise OfflineBoundaryViolation(
            f"Fronteira offline bloqueou tentativa de {kind}: {target}."
        )

    return blocker


@contextmanager
def offline_boundary_guards() -> Iterator[OfflineBoundaryAudit]:
    """Instala traps de processo enquanto os cenários determinísticos executam."""

    audit = OfflineBoundaryAudit()
    original_open = builtins.open
    original_io_open = io.open
    original_os_open = os.open

    def is_certificate_or_key(file: Any) -> bool:
        if isinstance(file, int):
            return False
        try:
            path = os.fsdecode(os.fspath(file))
        except TypeError:
            return False
        return Path(path).suffix.lower() in {".pfx", ".p12", ".pem", ".key"}

    def guarded_open(file: Any, *args: Any, **kwargs: Any):
        if is_certificate_or_key(file):
            audit.real_certificate_attempts += 1
            raise OfflineBoundaryViolation(
                "Fronteira offline bloqueou tentativa de abrir certificado/chave."
            )
        return original_open(file, *args, **kwargs)

    def guarded_io_open(file: Any, *args: Any, **kwargs: Any):
        if is_certificate_or_key(file):
            audit.real_certificate_attempts += 1
            raise OfflineBoundaryViolation(
                "Fronteira offline bloqueou tentativa de abrir certificado/chave."
            )
        return original_io_open(file, *args, **kwargs)

    def guarded_os_open(file: Any, *args: Any, **kwargs: Any):
        if is_certificate_or_key(file):
            audit.real_certificate_attempts += 1
            raise OfflineBoundaryViolation(
                "Fronteira offline bloqueou tentativa de abrir certificado/chave."
            )
        return original_os_open(file, *args, **kwargs)

    with ExitStack() as stack:
        network_blocker = _blocked_boundary(audit, "network", "socket/rede")
        database_blocker = _blocked_boundary(audit, "database", "SQLite")
        stack.enter_context(patch("socket.socket", network_blocker))
        stack.enter_context(patch("socket.SocketType", network_blocker))
        stack.enter_context(patch("_socket.socket", network_blocker))
        stack.enter_context(
            patch("socket.create_connection", network_blocker)
        )
        for name in ("socketpair", "fromfd", "fromshare"):
            if hasattr(socket, name):
                stack.enter_context(patch.object(socket, name, network_blocker))
            if hasattr(_socket, name):
                stack.enter_context(patch.object(_socket, name, network_blocker))
        for name in (
            "getaddrinfo",
            "gethostbyname",
            "gethostbyname_ex",
            "gethostbyaddr",
        ):
            stack.enter_context(patch.object(socket, name, network_blocker))
            if hasattr(_socket, name):
                stack.enter_context(patch.object(_socket, name, network_blocker))
        stack.enter_context(
            patch("urllib.request.urlopen", network_blocker)
        )
        stack.enter_context(
            patch("http.client.HTTPConnection.connect", network_blocker)
        )
        stack.enter_context(patch("sqlite3.connect", database_blocker))
        stack.enter_context(patch("sqlite3.dbapi2.connect", database_blocker))
        stack.enter_context(patch("_sqlite3.connect", database_blocker))
        stack.enter_context(patch("sqlite3.Connection", database_blocker))
        stack.enter_context(patch("_sqlite3.Connection", database_blocker))
        stack.enter_context(patch("builtins.open", guarded_open))
        stack.enter_context(patch("io.open", guarded_io_open))
        stack.enter_context(patch("_io.open", guarded_io_open))
        stack.enter_context(patch("os.open", guarded_os_open))
        yield audit


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _source_sha256(path: str | Path) -> str:
    source = Path(path).read_bytes()
    canonical_lf = source.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return _sha256(canonical_lf)


def _scenario(
    *,
    scenario_id: str,
    category: str,
    model: str,
    expected: str,
    fiscal_outcome: str,
    evidence: Mapping[str, Any],
    passed: bool,
) -> dict[str, Any]:
    clean_evidence = dict(evidence)
    return {
        "id": scenario_id,
        "categoria": category,
        "modelo": model,
        "resultado_teste": "APROVADO" if passed else "REPROVADO",
        "resultado_fiscal_simulado": fiscal_outcome,
        "comportamento_esperado": expected,
        "evidencia": clean_evidence,
        "evidencia_sha256": _sha256(_canonical_json(clean_evidence)),
    }


class OfflineFiscalDossierService:
    """Harness fiscal fechado, determinístico e exclusivo do perfil TESTE."""

    def __init__(
        self,
        *,
        profile: str = "TESTE",
        source_revision: str = DEFAULT_SOURCE_REVISION,
        application_version: str = "2.5.1",
        application_revision: str = "21",
        readiness: FakeReadinessAdapter | None = None,
        store: FakeFiscalStore | None = None,
        transport: FakeFiscalTransport | None = None,
    ) -> None:
        self.profile = str(profile).strip().upper()
        self.source_revision = str(source_revision).strip()
        self.application_version = str(application_version).strip()
        self.application_revision = str(application_revision).strip()
        self.readiness = readiness or FakeReadinessAdapter(profile=self.profile)
        self.store = store or FakeFiscalStore()
        self.transport = transport or FakeFiscalTransport()
        adapters = (self.readiness, self.store, self.transport)
        if any(
            not str(getattr(adapter, "test_double_kind", "")).startswith("FAKE_")
            for adapter in adapters
        ):
            raise TypeError("O dossiê offline aceita somente adapters fake identificados.")

    def _require_test_profile(self) -> None:
        if self.profile != "TESTE":
            raise PermissionError(
                "O dossiê automatizado fiscal é exclusivo do perfil TESTE; "
                "homologação e produção reais permanecem bloqueadas."
            )

    def _authorize_fake(
        self, record_id: str, outcome: str
    ) -> tuple[FakeFiscalResponse, dict[str, Any]]:
        self.readiness.require()
        try:
            response = self.transport.authorize(outcome)
        except SimulatedTimeout as exc:
            if exc.dispatched:
                self.store.save(
                    record_id,
                    status="RESPOSTA_DESCONHECIDA",
                    protocol="",
                    blind_retry_allowed=False,
                )
            raise
        if response.success:
            status = "AUTORIZADO_SIMULADO"
        elif response.status_code:
            status = "REJEITADO_SIMULADO"
        else:
            status = "RESPOSTA_DESCONHECIDA"
        record = self.store.save(
            record_id,
            status=status,
            protocol=response.protocol,
            blind_retry_allowed=False if status == "RESPOSTA_DESCONHECIDA" else None,
        )
        return response, record

    def _reconcile_unknown_fake(
        self, record_id: str
    ) -> tuple[FakeFiscalResponse, dict[str, Any]]:
        current = self.store.get(record_id)
        if current.get("status") != "RESPOSTA_DESCONHECIDA":
            raise FakeStateTransitionBlocked(
                "Consulta fake só reconcilia documento com resposta desconhecida."
            )
        self.readiness.require()
        response = self.transport.query("authorized")
        return response, self.store.save(
            record_id,
            status="AUTORIZADO_SIMULADO_RECONCILIADO",
            protocol=response.protocol,
        )

    def _cancel_authorized_fake(
        self, record_id: str
    ) -> tuple[FakeFiscalResponse, dict[str, Any]]:
        current = self.store.get(record_id)
        if not str(current.get("status", "")).startswith("AUTORIZADO_SIMULADO"):
            raise FakeStateTransitionBlocked(
                "Cancelamento fake exige autorização previamente reconciliada."
            )
        self.readiness.require()
        response = self.transport.event("CANCELAMENTO")
        return response, self.store.save(
            record_id,
            status="CANCELADO_SIMULADO",
            cancellation_protocol=response.protocol,
        )

    def _inutilize_fake(
        self, record_id: str
    ) -> tuple[FakeFiscalResponse, dict[str, Any]]:
        self.readiness.require()
        response = self.transport.inutilize()
        return response, self.store.save(
            record_id, status="INUTILIZADA_SIMULADA", protocol=response.protocol
        )

    def _register_contingency_fake(
        self, record_id: str, *, model: str
    ) -> dict[str, Any]:
        self.readiness.require()
        if str(model) != "65":
            raise FakeStateTransitionBlocked(
                "O roteiro offline fake não pode ser reutilizado para o modelo 55."
            )
        return self.store.save(
            record_id,
            model="65",
            emission_type="9_SIMULADO",
            status="CONTINGENCIA_SIMULADA_PENDENTE_RECONCILIACAO",
        )

    def run(self, *, boundary_audit: OfflineBoundaryAudit) -> dict[str, Any]:
        self._require_test_profile()
        scenarios: list[dict[str, Any]] = []

        self.readiness.require()
        scenarios.append(
            _scenario(
                scenario_id="PRONTIDAO-TESTE-FAKE",
                category="prontidao",
                model="55/65",
                expected="Aceitar apenas a matriz simbólica e isolada de TESTE.",
                fiscal_outcome="APTO_SOMENTE_PARA_TESTE_AUTOMATIZADO",
                evidence={
                    "adapter": self.readiness.test_double_kind,
                    "certificate_source": "SIMBOLO_FAKE_EM_MEMORIA",
                    "real_certificate_reads": self.readiness.real_certificate_reads,
                },
                passed=self.readiness.real_certificate_reads == 0,
            )
        )

        blocked = False
        readiness_calls_before = len(self.transport.calls)
        try:
            self.readiness.require(symbolic_certificate_ready=False)
        except PermissionError:
            blocked = True
        scenarios.append(
            _scenario(
                scenario_id="PRONTIDAO-A1-AUSENTE",
                category="prontidao",
                model="55/65",
                expected=(
                    "Bloquear antes de qualquer transporte quando a pré-condição "
                    "A1 fake falta."
                ),
                fiscal_outcome="BLOQUEADO",
                evidence={
                    "blocked_before_fake_transport": blocked,
                    "fake_transport_calls_added": (
                        len(self.transport.calls) - readiness_calls_before
                    ),
                },
                passed=(
                    blocked and len(self.transport.calls) == readiness_calls_before
                ),
            )
        )

        blocked = False
        readiness_calls_before = len(self.transport.calls)
        writes_before = self.store.writes
        try:
            self.readiness.require(symbolic_numbering_ready=False)
        except PermissionError:
            blocked = True
        scenarios.append(
            _scenario(
                scenario_id="PRONTIDAO-NUMERACAO-AUSENTE",
                category="prontidao",
                model="55/65",
                expected=(
                    "Bloquear antes de transporte e persistência quando a numeração "
                    "fake não foi inicializada."
                ),
                fiscal_outcome="BLOQUEADO",
                evidence={
                    "blocked_before_fake_transport": blocked,
                    "fake_transport_calls_added": (
                        len(self.transport.calls) - readiness_calls_before
                    ),
                    "in_memory_writes_added": self.store.writes - writes_before,
                },
                passed=(
                    blocked
                    and len(self.transport.calls) == readiness_calls_before
                    and self.store.writes == writes_before
                ),
            )
        )

        response, authorized = self._authorize_fake("DOC-AUT-001", "authorized")
        scenarios.append(
            _scenario(
                scenario_id="AUTORIZACAO-SIMULADA",
                category="autorizacao",
                model="65",
                expected="Registrar somente autorização simulada, sempre marcada como sem SEFAZ.",
                fiscal_outcome="AUTORIZADO_SIMULADO_SEM_SEFAZ",
                evidence={
                    "cstat_fake": response.status_code,
                    "protocol_kind": "SINTETICO_TESTE",
                    "stored_status": authorized["status"],
                },
                passed=response.success and "SIMULADO" in authorized["status"],
            )
        )

        response, rejected = self._authorize_fake("DOC-REJ-001", "rejected")
        scenarios.append(
            _scenario(
                scenario_id="REJEICAO-SIMULADA",
                category="rejeicao",
                model="55",
                expected="Preservar rejeição fake sem protocolo ou sucesso fabricado.",
                fiscal_outcome="REJEITADO_SIMULADO",
                evidence={
                    "cstat_fake": response.status_code,
                    "protocol_present": bool(rejected["protocol"]),
                    "stored_status": rejected["status"],
                },
                passed=not response.success and not rejected["protocol"],
            )
        )

        before_dispatched = None
        try:
            self._authorize_fake("DOC-TIMEOUT-BEFORE-001", "timeout_before_dispatch")
        except SimulatedTimeout as exc:
            before_dispatched = exc.dispatched
        scenarios.append(
            _scenario(
                scenario_id="TIMEOUT-ANTES-DESPACHO",
                category="timeout",
                model="55/65",
                expected=(
                    "Não declarar resultado fiscal quando o timeout fake ocorre "
                    "antes do despacho."
                ),
                fiscal_outcome="NAO_ENVIADO_SIMULADO",
                evidence={
                    "dispatched": before_dispatched,
                    "authorization_claimed": False,
                    "record_persisted": bool(
                        self.store.get("DOC-TIMEOUT-BEFORE-001")
                    ),
                },
                passed=(
                    before_dispatched is False
                    and not self.store.get("DOC-TIMEOUT-BEFORE-001")
                ),
            )
        )

        after_dispatched = None
        try:
            self._authorize_fake("DOC-UNK-001", "timeout_after_dispatch")
        except SimulatedTimeout as exc:
            after_dispatched = exc.dispatched
        unknown = self.store.get("DOC-UNK-001")
        scenarios.append(
            _scenario(
                scenario_id="TIMEOUT-APOS-DESPACHO",
                category="resposta_desconhecida",
                model="65",
                expected="Manter resposta desconhecida e impedir retransmissão cega.",
                fiscal_outcome="RESPOSTA_DESCONHECIDA_SIMULADA",
                evidence={
                    "dispatched": after_dispatched,
                    "stored_status": unknown["status"],
                    "blind_retry_allowed": unknown["blind_retry_allowed"],
                },
                passed=after_dispatched is True and not unknown["blind_retry_allowed"],
            )
        )

        response, malformed = self._authorize_fake("DOC-UNK-002", "unknown_payload")
        scenarios.append(
            _scenario(
                scenario_id="RESPOSTA-NAO-CLASSIFICAVEL",
                category="resposta_desconhecida",
                model="55",
                expected="Não promover payload fake inconclusivo a autorizado ou rejeitado.",
                fiscal_outcome="RESPOSTA_DESCONHECIDA_SIMULADA",
                evidence={
                    "fake_status_code_present": bool(response.status_code),
                    "stored_status": malformed["status"],
                    "protocol_present": bool(malformed["protocol"]),
                },
                passed=not response.status_code and not malformed["protocol"],
            )
        )

        auth_calls_before_query = len(
            [call for call in self.transport.calls if call.startswith("authorize:")]
        )
        response, reconciled = self._reconcile_unknown_fake("DOC-UNK-001")
        auth_calls_after_query = len(
            [call for call in self.transport.calls if call.startswith("authorize:")]
        )
        scenarios.append(
            _scenario(
                scenario_id="CONSULTA-RECONCILIACAO",
                category="consulta_reconciliacao",
                model="65",
                expected="Consultar o estado fake sem repetir a autorização desconhecida.",
                fiscal_outcome="AUTORIZADO_SIMULADO_APOS_CONSULTA",
                evidence={
                    "authorization_calls_added": (
                        auth_calls_after_query - auth_calls_before_query
                    ),
                    "query_calls": 1,
                    "stored_status": reconciled["status"],
                    "protocol_kind": "SINTETICO_TESTE",
                },
                passed=(auth_calls_after_query == auth_calls_before_query),
            )
        )

        response, cancelled = self._cancel_authorized_fake("DOC-UNK-001")
        scenarios.append(
            _scenario(
                scenario_id="CANCELAMENTO-SIMULADO",
                category="cancelamento",
                model="65",
                expected="Cancelar somente o documento fake reconciliado como autorizado.",
                fiscal_outcome="CANCELADO_SIMULADO_SEM_SEFAZ",
                evidence={
                    "cstat_fake": response.status_code,
                    "previous_status": reconciled["status"],
                    "stored_status": cancelled["status"],
                    "protocol_kind": "SINTETICO_TESTE",
                },
                passed=(
                    response.success
                    and reconciled["status"].startswith("AUTORIZADO_SIMULADO")
                ),
            )
        )

        events_before_block = len(
            [call for call in self.transport.calls if call.startswith("event:")]
        )
        cancellation_blocked = False
        try:
            self._cancel_authorized_fake("DOC-UNK-002")
        except FakeStateTransitionBlocked:
            cancellation_blocked = True
        events_after_block = len(
            [call for call in self.transport.calls if call.startswith("event:")]
        )
        scenarios.append(
            _scenario(
                scenario_id="CANCELAMENTO-BLOQUEADO-INCERTO",
                category="bloqueio",
                model="55",
                expected="Bloquear cancelamento enquanto a resposta fake permanecer desconhecida.",
                fiscal_outcome="BLOQUEADO",
                evidence={
                    "source_status": malformed["status"],
                    "event_calls_added": events_after_block - events_before_block,
                    "blocked": cancellation_blocked,
                },
                passed=cancellation_blocked and events_after_block == events_before_block,
            )
        )

        response, inutilized = self._inutilize_fake("FAIXA-INU-001")
        scenarios.append(
            _scenario(
                scenario_id="INUTILIZACAO-SIMULADA",
                category="inutilizacao",
                model="55",
                expected="Registrar apenas inutilização fake, sem afetar numeração real.",
                fiscal_outcome="INUTILIZADA_SIMULADA_SEM_SEFAZ",
                evidence={
                    "cstat_fake": response.status_code,
                    "range_kind": "FAIXA_SINTETICA_TESTE",
                    "stored_status": inutilized["status"],
                    "real_numbering_touched": False,
                },
                passed=response.success and not self.store.real_database_connections,
            )
        )

        transport_before_contingency = len(self.transport.calls)
        contingency = self._register_contingency_fake("CONT-65-001", model="65")
        scenarios.append(
            _scenario(
                scenario_id="CONTINGENCIA-OFFLINE-65",
                category="contingencia",
                model="65",
                expected=(
                    "Manter emissão fake offline pendente; não transmitir nem "
                    "alegar autorização."
                ),
                fiscal_outcome="CONTINGENCIA_SIMULADA_PENDENTE",
                evidence={
                    "stored_status": contingency["status"],
                    "fake_transport_calls_added": (
                        len(self.transport.calls) - transport_before_contingency
                    ),
                    "authorization_claimed": False,
                    "legal_deadline_validated": False,
                },
                passed=(
                    len(self.transport.calls) == transport_before_contingency
                    and "PENDENTE" in contingency["status"]
                ),
            )
        )

        for scenario_id, expected, kwargs in (
            (
                "BLOQUEIO-PRODUCAO",
                "Recusar perfil/ambiente de produção antes de qualquer operação.",
                {"production": True},
            ),
            (
                "BLOQUEIO-PORTAO-AUSENTE",
                "Recusar operação quando o portão fake não está composto.",
                {"gate_composed": False},
            ),
            (
                "BLOQUEIO-PERMISSAO-AUSENTE",
                "Recusar operação sem sessão/permissão fiscal fake.",
                {"permission": False},
            ),
        ):
            calls_before = len(self.transport.calls)
            was_blocked = False
            try:
                self.readiness.require(**kwargs)
            except PermissionError:
                was_blocked = True
            scenarios.append(
                _scenario(
                    scenario_id=scenario_id,
                    category="bloqueio",
                    model="55/65",
                    expected=expected,
                    fiscal_outcome="BLOQUEADO",
                    evidence={
                        "blocked": was_blocked,
                        "fake_transport_calls_added": len(self.transport.calls) - calls_before,
                    },
                    passed=was_blocked and len(self.transport.calls) == calls_before,
                )
            )

        transport_before_contingency_55 = len(self.transport.calls)
        store_writes_before_contingency_55 = self.store.writes
        contingency_55_blocked = False
        try:
            self._register_contingency_fake("CONT-55-BLOCKED", model="55")
        except FakeStateTransitionBlocked:
            contingency_55_blocked = True
        scenarios.append(
            _scenario(
                scenario_id="BLOQUEIO-CONTINGENCIA-55",
                category="bloqueio",
                model="55",
                expected="Não reutilizar o roteiro offline do modelo 65 para NF-e 55.",
                fiscal_outcome="BLOQUEADO",
                evidence={
                    "requested_model": "55",
                    "allowed_fake_offline_model": "65",
                    "blocked": contingency_55_blocked,
                    "fake_transport_calls_added": (
                        len(self.transport.calls) - transport_before_contingency_55
                    ),
                    "in_memory_writes_added": (
                        self.store.writes - store_writes_before_contingency_55
                    ),
                },
                passed=(
                    contingency_55_blocked
                    and len(self.transport.calls) == transport_before_contingency_55
                    and self.store.writes == store_writes_before_contingency_55
                ),
            )
        )

        approved = sum(item["resultado_teste"] == "APROVADO" for item in scenarios)
        failed = len(scenarios) - approved
        report: dict[str, Any] = {
            "schema_version": DOSSIER_SCHEMA_VERSION,
            "dossie_id": "NABICODE-FISCAL-OFFLINE-TESTE-001",
            "classificacao": "TESTE_AUTOMATIZADO_OFFLINE_COM_FAKES",
            "nao_e_homologacao_fisica": True,
            "nao_houve_sucesso_sefaz": True,
            "versao_aplicacao": self.application_version,
            "revisao_aplicacao": self.application_revision,
            "versao_harness": HARNESS_VERSION,
            "revisao_fonte": self.source_revision,
            "gerado_em_deterministico": FIXED_TEST_TIME,
            "perfil": self.profile,
            "ambiente": "SIMULADO_OFFLINE",
            "resumo": {
                "cenarios": len(scenarios),
                "aprovados": approved,
                "reprovados": failed,
                "homologacao_fiscal_real": "NAO_EXECUTADA",
                "homologacao_fisica": "PENDENTE",
                "producao_fiscal": "BLOQUEADA",
            },
            "prova_de_isolamento": {
                "runtime_guards": list(boundary_audit.installed_guards),
                "real_network_attempts": boundary_audit.real_network_attempts,
                "real_database_attempts": boundary_audit.real_database_attempts,
                "real_certificate_attempts": boundary_audit.real_certificate_attempts,
                "real_network_calls_by_adapter": self.transport.real_network_calls,
                "real_database_connections_by_adapter": self.store.real_database_connections,
                "real_certificate_reads_by_adapters": (
                    self.transport.real_certificate_reads + self.readiness.real_certificate_reads
                ),
                "fake_transport_calls": len(self.transport.calls),
                "in_memory_writes": self.store.writes,
                "adapters": [
                    self.readiness.test_double_kind,
                    self.transport.test_double_kind,
                    self.store.test_double_kind,
                ],
            },
            "cenarios": scenarios,
            "limitacoes": [
                "Os resultados aprovam apenas as asserções do harness determinístico.",
                (
                    "Nenhum certificado A1, CSC, chave privada, senha ou arquivo "
                    "fiscal real foi usado."
                ),
                "Nenhum socket, HTTP, TLS, endpoint SEFAZ ou outra rede foi usado.",
                "Nenhum SQLite, banco de cliente, XML real, DANFE ou numeração real foi usado.",
                "cStat, mensagens e protocolos deste relatório são dados sintéticos de TESTE.",
                (
                    "Autorização, cancelamento e inutilização simulados não provam "
                    "aceitação pela SEFAZ."
                ),
                (
                    "Contingência foi exercitada apenas como estado seguro; prazo "
                    "legal e calendário permanecem pendentes."
                ),
                (
                    "Homologação física acompanhada, credenciamento, certificado, "
                    "impressão, DANFE/QR e pacote contábil continuam pendentes."
                ),
                (
                    "Produção fiscal continua bloqueada e exige evidência externa "
                    "e autorização próprias."
                ),
            ],
        }
        report["harness_source_sha256"] = _source_sha256(__file__)
        report["payload_sha256"] = _sha256(_canonical_json(report))
        return report


def run_offline_dossier(
    *,
    profile: str = "TESTE",
    source_revision: str = DEFAULT_SOURCE_REVISION,
    application_version: str = "2.5.1",
    application_revision: str = "21",
    service: OfflineFiscalDossierService | None = None,
) -> dict[str, Any]:
    selected = service or OfflineFiscalDossierService(
        profile=profile,
        source_revision=source_revision,
        application_version=application_version,
        application_revision=application_revision,
    )
    selected._require_test_profile()
    with offline_boundary_guards() as audit:
        return selected.run(boundary_audit=audit)


def render_human_summary(report: Mapping[str, Any], *, json_sha256: str) -> str:
    summary = report["resumo"]
    isolation = report["prova_de_isolamento"]
    lines = [
        "# Dossiê fiscal automatizado OFFLINE — resumo sanitizado",
        "",
        "> **TESTE AUTOMATIZADO COM FAKES. NÃO É HOMOLOGAÇÃO FÍSICA, NÃO HOUVE",
        "> COMUNICAÇÃO OU SUCESSO SEFAZ E PRODUÇÃO FISCAL CONTINUA BLOQUEADA.**",
        "",
        f"- Dossiê: `{report['dossie_id']}`",
        f"- Aplicação: `{report['versao_aplicacao']} R{report['revisao_aplicacao']}`",
        f"- Harness/schema: `{report['versao_harness']}` / `{report['schema_version']}`",
        f"- Fonte: `{report['revisao_fonte']}`",
        f"- Perfil/ambiente: `{report['perfil']}` / `{report['ambiente']}`",
        (
            f"- Cenários automatizados: `{summary['cenarios']}`; aprovados: "
            f"`{summary['aprovados']}`; reprovados: `{summary['reprovados']}`"
        ),
        f"- Homologação fiscal real: `{summary['homologacao_fiscal_real']}`",
        f"- Homologação física: `{summary['homologacao_fisica']}`",
        f"- Produção fiscal: `{summary['producao_fiscal']}`",
        f"- SHA-256 do JSON: `{json_sha256}`",
        f"- SHA-256 do payload canônico: `{report['payload_sha256']}`",
        f"- SHA-256 do harness: `{report['harness_source_sha256']}`",
        "",
        "## Matriz executada",
        "",
        (
            "| Cenário | Modelo | Teste | Resultado fiscal explicitamente simulado "
            "| Evidência SHA-256 |"
        ),
        "|---|---:|---|---|---|",
    ]
    for scenario in report["cenarios"]:
        lines.append(
            f"| {scenario['id']} | {scenario['modelo']} | {scenario['resultado_teste']} | "
            f"{scenario['resultado_fiscal_simulado']} | `{scenario['evidencia_sha256']}` |"
        )
    lines.extend(
        [
            "",
            "## Prova de isolamento",
            "",
            f"- Tentativas de rede real: `{isolation['real_network_attempts']}`.",
            f"- Tentativas de banco real: `{isolation['real_database_attempts']}`.",
            (
                "- Tentativas de certificado/chave real: "
                f"`{isolation['real_certificate_attempts']}`."
            ),
            (
                "- Chamadas do transporte fake roteirizado: "
                f"`{isolation['fake_transport_calls']}`."
            ),
            (
                "- Escritas no store exclusivamente em memória: "
                f"`{isolation['in_memory_writes']}`."
            ),
            "- Guards ativos durante a execução: "
            + ", ".join(f"`{item}`" for item in isolation["runtime_guards"])
            + ".",
            "",
            "## Limitações impeditivas",
            "",
        ]
    )
    lines.extend(f"- {limitation}" for limitation in report["limitacoes"])
    lines.append("")
    return "\n".join(lines)


def write_dossier(
    output_dir: str | Path,
    *,
    profile: str = "TESTE",
    source_revision: str = DEFAULT_SOURCE_REVISION,
) -> tuple[Path, Path, str, str]:
    report = run_offline_dossier(profile=profile, source_revision=source_revision)
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    json_path = target / "dossie_fiscal_offline_teste.json"
    summary_path = target / "dossie_fiscal_offline_teste.md"
    json_bytes = (
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    json_sha256 = _sha256(json_bytes)
    summary_bytes = render_human_summary(report, json_sha256=json_sha256).encode("utf-8")
    json_path.write_bytes(json_bytes)
    summary_path.write_bytes(summary_bytes)
    return json_path, summary_path, json_sha256, _sha256(summary_bytes)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Gera dossiê fiscal automatizado OFFLINE, exclusivo do perfil TESTE."
    )
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--profile", default="TESTE")
    parser.add_argument("--source-revision", default=DEFAULT_SOURCE_REVISION)
    args = parser.parse_args(argv)
    json_path, summary_path, json_hash, summary_hash = write_dossier(
        args.output_dir, profile=args.profile, source_revision=args.source_revision
    )
    print(f"JSON: {json_path} SHA-256={json_hash}")
    print(f"RESUMO: {summary_path} SHA-256={summary_hash}")
    print("TESTE AUTOMATIZADO OFFLINE; NÃO É HOMOLOGAÇÃO FÍSICA OU SUCESSO SEFAZ.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
