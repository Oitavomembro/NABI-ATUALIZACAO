from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class FiscalSaleDraft:
    reservation_id: str
    access_key: str
    model: str
    environment: str
    xml: bytes


class FiscalSaleService:
    """Orquestra PDV e fiscal sem misturar transmissão à transação comercial."""

    PAYMENT_CODES = {
        "DINHEIRO": "01", "CHEQUE": "02", "CARTAO_CREDITO": "03",
        "CRÉDITO": "03", "CREDITO": "03", "CARTAO_DEBITO": "04",
        "DÉBITO": "04", "DEBITO": "04", "CREDIARIO": "05", "PIX": "17",
    }

    def __init__(self, fiscal_service: Any) -> None:
        self.fiscal_service = fiscal_service

    def prepare(
        self, *, items: Sequence[Mapping[str, Any]], payments: Sequence[Mapping[str, Any]],
        actor: str, recipient: Mapping[str, Any] | None = None, destination: int = 1,
        issued_at: datetime | None = None,
    ) -> FiscalSaleDraft:
        config = self.fiscal_service.load_config()
        model = str(config.get("default_model") or "65")
        problems = self.fiscal_service.validate_ready(operation="autorizacao", model=model)
        if problems:
            raise ValueError("; ".join(problems))
        fiscal_items = self.fiscal_service.prepare_sale_items(items, destination=destination)
        environment = str(config.get("environment") or "HOMOLOGACAO").upper()
        series = int(config.get("sale_series_65" if model == "65" else "sale_series_55") or 1)
        reservation = self.fiscal_service.reserve_number(
            model=model, series=series, actor=actor, environment=environment
        )
        try:
            issuer = dict(config.get("issuer") or {})
            issuer.update({
                "cnpj": config.get("cnpj", ""), "state": config.get("state", ""),
                "tax_regime_code": self.fiscal_service.TAX_REGIME_CODES.get(
                    str(config.get("tax_regime") or "").upper(), 0
                ),
            })
            when = issued_at or datetime.now().astimezone()
            digest = hashlib.sha256(
                f"{environment}:{model}:{series}:{reservation['number']}:{when.isoformat()}".encode()
            ).hexdigest()
            numeric_code = f"{int(digest[:12], 16) % 100_000_000:08d}"
            xml, access_key = self.fiscal_service.build_document_xml(
                issuer=issuer, recipient=dict(recipient or {}), items=fiscal_items,
                document={
                    "model": model, "series": series, "number": int(reservation["number"]),
                    "state_code": self.fiscal_service.STATE_CODES[str(config["state"]).upper()],
                    "issued_at": when, "environment": environment, "numeric_code": numeric_code,
                    "destination": int(destination), "payment_code": self._payment_code(payments),
                    "final_consumer": 1, "presence": 1,
                },
            )
            return FiscalSaleDraft(str(reservation["id"]), access_key, model, environment, xml)
        except Exception:
            self.fiscal_service.release_number(
                str(reservation["id"]), actor=actor,
                reason="Falha ao preparar documento antes da venda.",
            )
            raise

    @classmethod
    def _payment_code(cls, payments: Sequence[Mapping[str, Any]]) -> str:
        if len(payments) != 1:
            return "99"
        name = str(payments[0].get("forma") or "").strip().upper().replace(" ", "_")
        return cls.PAYMENT_CODES.get(name, "99")

    @staticmethod
    def persist_draft(connection: Any, sale_id: int, draft: FiscalSaleDraft) -> None:
        now = datetime.now().astimezone().isoformat()
        connection.execute(
            """INSERT INTO fiscal_sale_documents
               (sale_id,reservation_id,access_key,model,environment,status,xml_b64,created_at,updated_at)
               VALUES(?,?,?,?,?,'PENDENTE',?,?,?)""",
            (int(sale_id), draft.reservation_id, draft.access_key, draft.model,
             draft.environment, base64.b64encode(draft.xml).decode("ascii"), now, now),
        )

    def enqueue_pending(self, *, sale_id: int, actor: str) -> dict[str, Any]:
        connection = self.fiscal_service.connection_factory()
        try:
            row = connection.execute(
                """SELECT id,access_key,model,xml_b64,queue_id,status
                     FROM fiscal_sale_documents WHERE sale_id=?""", (int(sale_id),)
            ).fetchone()
        finally:
            connection.close()
        if not row:
            raise ValueError("Venda não possui documento fiscal preparado.")
        if str(row[5]) in {"AUTORIZADO", "CANCELADO"}:
            return {"id": str(row[4]), "status": str(row[5]), "access_key": str(row[1])}
        queued = self.fiscal_service.enqueue_transmission(
            operation="autorizacao", xml=base64.b64decode(row[3]), actor=actor,
            access_key=str(row[1]), model=str(row[2]), reservation_id=str(
                self._reservation_for_sale(int(sale_id))
            ),
        )
        connection = self.fiscal_service.connection_factory()
        try:
            connection.execute(
                """UPDATE fiscal_sale_documents SET queue_id=?,status='ENFILEIRADO',
                          last_error='',updated_at=? WHERE id=?""",
                (str(queued["id"]), datetime.now().astimezone().isoformat(), int(row[0])),
            )
            connection.commit()
        finally:
            connection.close()
        return queued

    def _reservation_for_sale(self, sale_id: int) -> str:
        connection = self.fiscal_service.connection_factory()
        try:
            row = connection.execute(
                "SELECT reservation_id FROM fiscal_sale_documents WHERE sale_id=?", (sale_id,)
            ).fetchone()
            return str(row[0]) if row else ""
        finally:
            connection.close()

    def list_pending(self) -> list[dict[str, Any]]:
        connection = self.fiscal_service.connection_factory()
        try:
            cursor = connection.execute(
                """SELECT sale_id,access_key,model,environment,status,queue_id,last_error,created_at
                     FROM fiscal_sale_documents
                    WHERE status NOT IN ('AUTORIZADO','CANCELADO') ORDER BY id"""
            )
            names = [column[0] for column in cursor.description]
            return [dict(zip(names, row)) for row in cursor.fetchall()]
        finally:
            connection.close()
