from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from xml.etree import ElementTree as ET

from services.fiscal_outbox_service import FiscalOutboxService


@dataclass(frozen=True)
class CancellationRule:
    state: str
    model: str
    event_type: str
    environment: str
    normal_deadline: timedelta
    source: str
    version: str


class FiscalCancellationService:
    """Orquestra cancelamento fiscal sem antecipar o estorno comercial."""

    RULES = {
        ("BA", "65", "CANCELAMENTO", "HOMOLOGACAO"): CancellationRule(
            "BA", "65", "CANCELAMENTO", "HOMOLOGACAO", timedelta(minutes=30),
            "SEFAZ-BA — Perguntas e Respostas NFC-e, item 31",
            "consultado-2026-08-21",
        ),
        ("BA", "55", "CANCELAMENTO", "HOMOLOGACAO"): CancellationRule(
            "BA", "55", "CANCELAMENTO", "HOMOLOGACAO", timedelta(hours=24),
            "RICMS-BA/2012, art. 92; Ato COTEPE ICMS 13/2010",
            "consultado-2026-08-21",
        ),
    }

    def __init__(
        self,
        fiscal_service: Any,
        *,
        cancel_commercial_sale: Callable[[int, str], None] | None = None,
    ) -> None:
        self.fiscal_service = fiscal_service
        self.connection_factory = fiscal_service.connection_factory
        self.outbox = FiscalOutboxService(self.connection_factory)
        self.cancel_commercial_sale = cancel_commercial_sale

    @staticmethod
    def _aware(value: Any) -> datetime:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(
            str(value or "").replace("Z", "+00:00")
        )
        if parsed.tzinfo is None:
            parsed = parsed.astimezone()
        return parsed.astimezone(timezone.utc)

    def resolve_rule(self, *, state: str, model: str, environment: str) -> CancellationRule:
        key = (str(state).upper(), str(model), "CANCELAMENTO", str(environment).upper())
        rule = self.RULES.get(key)
        if rule is None:
            raise ValueError(
                "Cancelamento normal não suportado: regra normativa não versionada "
                f"para UF {key[0]}, modelo {key[1]} e ambiente {key[3]}."
            )
        return rule

    def _sale_document(self, sale_id: int) -> dict[str, Any]:
        connection = self.connection_factory()
        try:
            cursor = connection.execute(
                """SELECT id,sale_id,access_key,model,environment,status,protocol,
                          xml_b64,created_at,updated_at,last_error
                     FROM fiscal_sale_documents WHERE sale_id=?""",
                (int(sale_id),),
            )
            row = cursor.fetchone()
            if row is None:
                raise ValueError("Venda COMERCIAL não possui documento fiscal para cancelar.")
            return dict(zip((column[0] for column in cursor.description), row))
        finally:
            connection.close()

    def _stored_authorized_document(self, access_key: str, environment: str) -> dict[str, Any]:
        matches = [
            row for row in self.fiscal_service.list_documents()
            if str(row.get("access_key") or "") == str(access_key)
            and str(row.get("environment") or "").upper() == str(environment).upper()
        ]
        if not matches:
            raise ValueError("XML autorizado original não foi encontrado.")
        stored = dict(matches[-1])
        if str(stored.get("status") or "").upper() != "AUTORIZADO":
            raise ValueError("Documento fiscal não está autorizado.")
        processed = Path(str(stored.get("processed_path") or ""))
        if not processed.is_file():
            raise ValueError("XML autorizado original não foi encontrado.")
        integrity = self.fiscal_service.verify_document_integrity(
            access_key=access_key, environment=environment
        )
        if not integrity.get("valid"):
            raise ValueError("XML autorizado original falhou na verificação de integridade.")
        return stored

    @classmethod
    def _official_authorized_at(cls, stored: dict[str, Any]) -> datetime:
        """Lê exclusivamente o dhRecbto do protocolo contido no XML processado íntegro."""
        processed = Path(str(stored.get("processed_path") or ""))
        try:
            root = ET.parse(processed).getroot()
        except (ET.ParseError, OSError) as exc:
            raise ValueError(
                "Não foi possível determinar com segurança a data/hora oficial "
                "da autorização SEFAZ no XML autorizado."
            ) from exc

        def local_name(element: ET.Element) -> str:
            return str(element.tag).rsplit("}", 1)[-1]

        received_at = ""
        for protocol in root.iter():
            if local_name(protocol) != "protNFe":
                continue
            info = next(
                (child for child in protocol if local_name(child) == "infProt"), None
            )
            if info is None:
                continue
            received = next(
                (child for child in info if local_name(child) == "dhRecbto"), None
            )
            received_at = str(received.text or "").strip() if received is not None else ""
            if received_at:
                break
        try:
            parsed = datetime.fromisoformat(received_at.replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "Não foi possível determinar com segurança a data/hora oficial "
                "da autorização SEFAZ (dhRecbto ausente ou inválido)."
            ) from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError(
                "Não foi possível determinar com segurança a data/hora oficial "
                "da autorização SEFAZ (dhRecbto sem timezone/offset)."
            )
        return parsed.astimezone(timezone.utc)

    def eligibility(
        self, sale_id: int, *, user_has_permission: bool, now: datetime | None = None
    ) -> dict[str, Any]:
        if not user_has_permission:
            raise PermissionError("Usuário sem permissão específica para cancelamento fiscal.")
        document = self._sale_document(sale_id)
        status = str(document.get("status") or "").upper()
        if status in {"CANCELADO", "CANCELADO_FISCAL"}:
            raise ValueError("Documento fiscal já está cancelado.")
        if status in {"CANCELAMENTO_PENDENTE", "PROCESSANDO"}:
            raise ValueError("Cancelamento fiscal já está pendente ou em processamento.")
        if status == "RESPOSTA_DESCONHECIDA":
            raise ValueError("Documento aguarda reconciliação da resposta da SEFAZ.")
        if status != "AUTORIZADO":
            raise ValueError("Somente documento fiscal AUTORIZADO pode ser cancelado.")
        if str(document.get("environment") or "").upper() == "PRODUCAO":
            raise ValueError("Produção fiscal permanece bloqueada nesta versão.")
        key = self.fiscal_service._normalize_access_key(document.get("access_key"))
        if len(key) != 44:
            raise ValueError("Chave de acesso inválida.")
        if not str(document.get("protocol") or "").strip():
            raise ValueError("Protocolo de autorização ausente.")
        stored = self._stored_authorized_document(key, str(document["environment"]))
        state_code = key[:2]
        state = next(
            (uf for uf, code in self.fiscal_service.STATE_CODES.items() if code == state_code), ""
        )
        rule = self.resolve_rule(
            state=state, model=str(document["model"]), environment=str(document["environment"])
        )
        authorized_at = self._official_authorized_at(stored)
        current = self._aware(now or datetime.now(timezone.utc))
        deadline = authorized_at + rule.normal_deadline
        remaining = deadline - current
        if remaining.total_seconds() <= 0:
            raise ValueError("Prazo normal de cancelamento encerrado.")
        return {
            **document,
            "state": state,
            "number": int(key[25:34]),
            "series": int(key[22:25]),
            "authorized_at": authorized_at.isoformat(),
            "deadline_at": deadline.isoformat(),
            "remaining_seconds": int(remaining.total_seconds()),
            "rule_source": rule.source,
            "rule_version": rule.version,
            "stored_document": stored,
        }

    def request(
        self,
        *,
        sale_id: int,
        password: str,
        actor: str,
        justification: str,
        no_circulation_confirmed: bool,
        user_has_permission: bool,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        reason = str(justification or "").strip()
        if not 15 <= len(reason) <= 255:
            raise ValueError("Justificativa deve possuir entre 15 e 255 caracteres.")
        if not no_circulation_confirmed:
            raise ValueError(
                "Confirme que a mercadoria não circulou / não saiu do estabelecimento."
            )
        eligible = self.eligibility(
            sale_id, user_has_permission=user_has_permission, now=now
        )
        if str(eligible["environment"]).upper() == "PRODUCAO":
            raise ValueError("Produção fiscal permanece bloqueada nesta versão.")
        config = self.fiscal_service.load_config()
        key = str(eligible["access_key"])
        self.fiscal_service.validate_event_eligibility(
            access_key=key, event_type="CANCELAMENTO", sequence=1,
            protocol=str(eligible["protocol"]),
        )
        xml, event_id = self.fiscal_service.build_event_xml(
            event_type="CANCELAMENTO", access_key=key, sequence=1,
            actor_document=config["cnpj"], protocol=str(eligible["protocol"]),
            justification=reason, environment=str(eligible["environment"]),
        )
        signed = self.fiscal_service.sign_xml(
            xml, reference_id=event_id,
            pfx_path=config["certificate_path"], password=password,
        )
        envelope = self.fiscal_service._event_envelope(signed)
        self.fiscal_service.validate_official_xml(envelope, document_type="evento")
        timestamp = self._aware(now or datetime.now(timezone.utc)).isoformat()
        metadata = {
            "event_type": "CANCELAMENTO", "event_sequence": 1,
            "event_id": event_id, "justification": reason,
            "no_circulation_confirmed": True,
            "no_circulation_confirmed_by": str(actor or "Sistema"),
            "no_circulation_confirmed_at": timestamp,
            "requested_by": str(actor or "Sistema"), "requested_at": timestamp,
            "authorized_at": eligible["authorized_at"],
            "authorization_protocol": str(eligible["protocol"]),
            "deadline_at": eligible["deadline_at"],
            "rule_source": eligible["rule_source"],
            "rule_version": eligible["rule_version"],
            "original_document_path": eligible["stored_document"].get("processed_path", ""),
            "original_document_sha256": eligible["stored_document"].get("processed_sha256", ""),
        }
        connection = self.connection_factory()
        try:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT status FROM fiscal_sale_documents WHERE id=?",
                (int(eligible["id"]),),
            ).fetchone()
            if not current or str(current[0]).upper() != "AUTORIZADO":
                raise ValueError("Documento deixou de estar disponível para cancelamento.")
            queued = self.outbox.enqueue_in_transaction(
                connection, sale_id=int(sale_id), fiscal_document_id=None,
                access_key=key, environment=str(eligible["environment"]),
                operation="evento", model=str(eligible["model"]), reservation_id="",
                xml_b64=base64.b64encode(envelope).decode("ascii"),
                original_xml_b64=base64.b64encode(envelope).decode("ascii"),
                actor=str(actor or "Sistema"), max_attempts=1,
                legacy_id=f"cancelamento:{key}:1", created_at=timestamp,
                metadata=metadata,
            )
            connection.execute(
                """UPDATE fiscal_sale_documents
                      SET status='CANCELAMENTO_PENDENTE',last_error='',updated_at=?
                    WHERE id=? AND status='AUTORIZADO'""",
                (timestamp, int(eligible["id"])),
            )
            connection.commit()
            return queued
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def handle_worker_result(self, record: dict[str, Any]) -> None:
        if str(record.get("event_type") or "").upper() != "CANCELAMENTO":
            return
        sale_id = int(record.get("sale_id") or 0)
        status = str(record.get("status") or "").upper()
        if status != "CONCLUIDO" or not record.get("event_success"):
            return
        if self.cancel_commercial_sale is None:
            self._set_document_status(
                sale_id, "FISCAL_CANCELADO_ESTORNO_PENDENTE",
                "Cancelamento fiscal aceito; estorno comercial não configurado.",
            )
            return
        try:
            self.cancel_commercial_sale(sale_id, str(record.get("actor") or "Sistema"))
        except Exception as exc:
            self._set_document_status(
                sale_id, "FISCAL_CANCELADO_ESTORNO_PENDENTE", str(exc)
            )

    def recover_pending_reversals(self) -> list[int]:
        if self.cancel_commercial_sale is None:
            return []
        connection = self.connection_factory()
        try:
            rows = connection.execute(
                """SELECT f.sale_id FROM fiscal_sale_documents f
                     JOIN movimentacoes m ON m.id=f.sale_id
                    WHERE f.status IN ('CANCELADO_FISCAL','FISCAL_CANCELADO_ESTORNO_PENDENTE')
                      AND COALESCE(m.status_pagamento,'')!='CANCELADO'"""
            ).fetchall()
        finally:
            connection.close()
        recovered = []
        for (sale_id,) in rows:
            try:
                self.cancel_commercial_sale(int(sale_id), "Recuperação automática")
                recovered.append(int(sale_id))
            except Exception as exc:
                self._set_document_status(
                    int(sale_id), "FISCAL_CANCELADO_ESTORNO_PENDENTE", str(exc)
                )
        return recovered

    def _set_document_status(self, sale_id: int, status: str, error: str = "") -> None:
        connection = self.connection_factory()
        try:
            connection.execute(
                """UPDATE fiscal_sale_documents SET status=?,last_error=?,updated_at=?
                    WHERE sale_id=?""",
                (str(status), str(error), datetime.now(timezone.utc).isoformat(), int(sale_id)),
            )
            connection.commit()
        finally:
            connection.close()
