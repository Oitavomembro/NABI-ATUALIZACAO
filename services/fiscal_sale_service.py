from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
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
                    "payment_detail": self._payment_detail(payments),
                    "payments": self._payment_details(payments),
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

    def recipient_for_customer(self, customer_id: int, *, model: str | None = None) -> tuple[dict[str, Any], int]:
        config = self.fiscal_service.load_config()
        fiscal_model = str(model or config.get("default_model") or "65")
        connection = self.fiscal_service.connection_factory()
        try:
            cursor = connection.execute("SELECT * FROM clientes WHERE id=?", (int(customer_id),))
            names = [column[0] for column in cursor.description]
            row = cursor.fetchone()
        finally:
            connection.close()
        if not row:
            raise ValueError("Cliente selecionado não foi encontrado.")
        customer = dict(zip(names, row))
        technical_consumer = str(customer.get("codigo") or "").upper() == "CONSUMIDOR_FINAL"
        if technical_consumer and fiscal_model == "65":
            return {}, 1
        document = self.fiscal_service._normalize_tax_document(customer.get("cpf"))
        valid_document = (
            self.fiscal_service._is_valid_cnpj(document) if len(document) == 14
            else self.fiscal_service._is_valid_cpf(document) if len(document) == 11
            else False
        )
        if not valid_document:
            if fiscal_model == "65":
                return {}, 1
            raise ValueError("NF-e exige CPF ou CNPJ válido no cadastro do cliente.")
        recipient = {"document": document, "name": str(customer.get("nome") or "").strip()}
        customer_state = str(customer.get("fiscal_uf") or "").strip().upper()
        if fiscal_model == "55":
            required = {
                "street": customer.get("fiscal_logradouro"), "number": customer.get("fiscal_numero"),
                "district": customer.get("fiscal_bairro"), "city_code": customer.get("fiscal_codigo_municipio"),
                "city": customer.get("fiscal_municipio"), "state": customer_state,
                "zip_code": customer.get("fiscal_cep"),
            }
            if any(not str(value or "").strip() for value in required.values()):
                raise ValueError(
                    "NF-e exige o endereço fiscal completo do cliente. Preencha logradouro, número, "
                    "bairro, município, código IBGE, UF e CEP no cadastro."
                )
            recipient.update(required)
        state_registration = str(customer.get("inscricao_estadual") or "").strip()
        taxpayer = bool(customer.get("contribuinte_icms"))
        recipient.update({
            "state_registration": state_registration,
            "state_taxpayer_indicator": 1 if taxpayer and state_registration else 9,
            "email": str(customer.get("email") or "").strip(),
        })
        issuer_state = str(config.get("state") or "").upper()
        destination = 2 if customer_state and customer_state != issuer_state else 1
        return recipient, destination

    @classmethod
    def _payment_code(cls, payments: Sequence[Mapping[str, Any]]) -> str:
        if len(payments) != 1:
            return "99"
        name = str(payments[0].get("forma") or "").strip().upper().replace(" ", "_")
        return cls.PAYMENT_CODES.get(name, "99")

    @classmethod
    def _payment_detail(cls, payments: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        if len(payments) != 1:
            return {}
        payment = payments[0]
        code = cls._payment_code(payments)
        if code not in {"03", "04"}:
            return {}
        integration = int(payment.get("card_integration", 2) or 2)
        if integration not in {1, 2}:
            raise ValueError("Tipo de integração do cartão deve ser TEF (1) ou POS (2).")
        authorization = str(payment.get("card_authorization") or "").strip()
        if len(authorization) > 20:
            raise ValueError("Autorização do cartão deve possuir no máximo 20 caracteres.")
        return {"integration": integration, "authorization": authorization}

    @classmethod
    def _payment_details(cls, payments: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        details: list[dict[str, Any]] = []
        for payment in payments:
            name = str(payment.get("forma") or "").strip().upper().replace(" ", "_")
            try:
                amount = Decimal(str(payment.get("valor", 0))).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
            except (InvalidOperation, ValueError) as exc:
                raise ValueError("Valor de pagamento fiscal inválido.") from exc
            if amount <= 0:
                raise ValueError("Cada pagamento fiscal deve possuir valor maior que zero.")
            code = cls.PAYMENT_CODES.get(name, "99")
            detail: dict[str, Any] = {"code": code, "amount": amount}
            if code in {"03", "04"}:
                integration = int(payment.get("card_integration", 2) or 2)
                if integration not in {1, 2}:
                    raise ValueError("Tipo de integração do cartão deve ser TEF (1) ou POS (2).")
                authorization = str(payment.get("card_authorization") or "").strip()
                if len(authorization) > 20:
                    raise ValueError("Autorização do cartão deve possuir no máximo 20 caracteres.")
                detail.update({"integration": integration, "authorization": authorization})
            details.append(detail)
        if not details:
            raise ValueError("Informe ao menos uma forma de pagamento para o documento fiscal.")
        return details

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
        status = str(row[5] or "").upper()
        if status == "AUTORIZADO":
            return {"id": str(row[4]), "status": str(row[5]), "access_key": str(row[1])}
        if status in {"CANCELADO", "CANCELADO_LOCAL", "CANCELADO_FISCAL"}:
            raise ValueError("Documento cancelado não pode ser colocado novamente na fila fiscal.")
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
        return [
            row for row in self.list_sales()
            if str(row.get("status") or "").upper() in {"PENDENTE", "ENFILEIRADO", "PROCESSANDO"}
        ]

    def list_sales(self) -> list[dict[str, Any]]:
        connection = self.fiscal_service.connection_factory()
        try:
            cursor = connection.execute(
                """SELECT sale_id,access_key,model,environment,status,queue_id,protocol,
                          last_error,created_at,updated_at
                     FROM fiscal_sale_documents ORDER BY id DESC"""
            )
            names = [column[0] for column in cursor.description]
            return [dict(zip(names, row)) for row in cursor.fetchall()]
        finally:
            connection.close()

    def summary(self) -> dict[str, int]:
        result = {"total": 0, "authorized": 0, "pending": 0, "failed": 0, "cancelled": 0}
        for row in self.list_sales():
            result["total"] += 1
            status = str(row.get("status") or "").upper()
            if status == "AUTORIZADO":
                result["authorized"] += 1
            elif status == "FALHA":
                result["failed"] += 1
            elif status in {"CANCELADO", "CANCELADO_LOCAL", "CANCELADO_FISCAL"}:
                result["cancelled"] += 1
            elif status in {"PENDENTE", "ENFILEIRADO", "PROCESSANDO"}:
                result["pending"] += 1
        return result

    @staticmethod
    def prepare_local_cancellation(connection: Any, sale_id: int) -> None:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='fiscal_sale_documents'"
        ).fetchone()
        if not exists:
            return
        row = connection.execute(
            "SELECT status FROM fiscal_sale_documents WHERE sale_id=?", (int(sale_id),)
        ).fetchone()
        if not row:
            return
        status = str(row[0] or "").upper()
        if status == "AUTORIZADO":
            raise ValueError(
                "Esta venda possui documento autorizado. Cancele pela Central Fiscal antes de reverter estoque e financeiro."
            )
        if status == "CANCELADO":
            raise ValueError("O documento fiscal desta venda já está cancelado.")
        new_status = "CANCELADO" if status == "CANCELADO_FISCAL" else "CANCELADO_LOCAL"
        connection.execute(
            "UPDATE fiscal_sale_documents SET status=?,updated_at=? WHERE sale_id=?",
            (new_status, datetime.now().astimezone().isoformat(), int(sale_id)),
        )

    def finalize_local_cancellation(self, *, sale_id: int, actor: str) -> None:
        connection = self.fiscal_service.connection_factory()
        try:
            row = connection.execute(
                "SELECT reservation_id,queue_id,status FROM fiscal_sale_documents WHERE sale_id=?",
                (int(sale_id),),
            ).fetchone()
        finally:
            connection.close()
        if not row or str(row[2]) == "CANCELADO":
            return
        if str(row[1] or ""):
            self.fiscal_service.cancel_transmission(
                str(row[1]), actor=actor, reason="Venda cancelada antes da autorização fiscal."
            )
        if str(row[0] or ""):
            try:
                self.fiscal_service.release_number(
                    str(row[0]), actor=actor, reason="Venda cancelada antes da autorização fiscal."
                )
            except ValueError as exc:
                if "confirmada" not in str(exc).lower():
                    raise
        connection = self.fiscal_service.connection_factory()
        try:
            connection.execute(
                "UPDATE fiscal_sale_documents SET status='CANCELADO',updated_at=? WHERE sale_id=?",
                (datetime.now().astimezone().isoformat(), int(sale_id)),
            )
            connection.commit()
        finally:
            connection.close()

    def cancel_authorized(
        self, *, sale_id: int, password: str, actor: str, justification: str
    ) -> dict[str, Any]:
        connection = self.fiscal_service.connection_factory()
        try:
            row = connection.execute(
                "SELECT access_key,protocol,status FROM fiscal_sale_documents WHERE sale_id=?",
                (int(sale_id),),
            ).fetchone()
        finally:
            connection.close()
        if row and str(row[2]) == "CANCELADO_FISCAL":
            return {"recovery": True, "access_key": str(row[0])}
        if not row or str(row[2]) != "AUTORIZADO":
            raise ValueError("A venda selecionada não possui documento autorizado para cancelar.")
        response, event = self.fiscal_service.send_event(
            event_type="CANCELAMENTO", access_key=str(row[0]), sequence=1,
            password=password, actor=actor, protocol=str(row[1]),
            justification=str(justification or "").strip(),
        )
        if not response.success:
            raise ValueError(f"Cancelamento rejeitado pela SEFAZ: {response.status_code} — {response.message}")
        connection = self.fiscal_service.connection_factory()
        try:
            connection.execute(
                """UPDATE fiscal_sale_documents SET status='CANCELADO_FISCAL',
                          protocol=?,last_error='',updated_at=? WHERE sale_id=?""",
                (str(response.protocol or row[1]), datetime.now().astimezone().isoformat(), int(sale_id)),
            )
            connection.commit()
        finally:
            connection.close()
        return event
