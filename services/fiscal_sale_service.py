from __future__ import annotations

import base64
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Mapping, Sequence

from services.fiscal_outbox_service import FiscalOutboxService


@dataclass(frozen=True)
class FiscalSaleDraft:
    reservation_id: str
    access_key: str
    model: str
    environment: str
    xml: bytes
    contingency: bool = False


@dataclass(frozen=True)
class FiscalSalePreview:
    model: str
    environment: str
    series: int
    item_count: int
    total: Decimal
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

    @staticmethod
    def _requires_rtc(config: Mapping[str, Any], issued_at: datetime) -> bool:
        """Aplica o cronograma vigente sem tratar Simples como regime regular.

        Em 2026 os documentos de optantes do Simples/MEI ainda não entram na
        obrigatoriedade dos grupos IBS/CBS. A estrutura permanece habilitada a
        partir de 2027; até lá, não se pode acrescentar o 1% informativo ao
        valor cobrado do consumidor.
        """
        regime = str(config.get("tax_regime") or "").strip().upper()
        return not (
            regime in {"SIMPLES_NACIONAL", "SIMPLES", "MEI"}
            and issued_at.year < 2027
        )

    def prepare(
        self, *, items: Sequence[Mapping[str, Any]], payments: Sequence[Mapping[str, Any]],
        recipient: Mapping[str, Any] | None = None, destination: int = 1,
        issued_at: datetime | None = None, contingency_reason: str = "",
        certificate_password: str = "",
    ) -> FiscalSaleDraft:
        config = self.fiscal_service.load_config()
        model = str(config.get("default_model") or "65")
        problems = self.fiscal_service.validate_ready(operation="autorizacao", model=model)
        if problems:
            raise ValueError("; ".join(problems))
        crt = self.fiscal_service.TAX_REGIME_CODES.get(
            str(config.get("tax_regime") or "").upper(), 0
        )
        when = issued_at or datetime.now().astimezone()
        fiscal_items = self.fiscal_service.prepare_sale_items(
            items, destination=destination, crt=crt,
            destination_state=str((recipient or {}).get("state") or config.get("state") or ""),
            tax_regime=str(config.get("tax_regime") or ""),
            require_rtc=self._requires_rtc(config, when),
        )
        environment = str(config.get("environment") or "HOMOLOGACAO").upper()
        series = int(config.get("sale_series_65" if model == "65" else "sale_series_55") or 1)
        readiness = getattr(self.fiscal_service, "require_operational_readiness", None)
        if readiness is not None:
            password_provider = getattr(
                self.fiscal_service, "session_certificate_password", lambda: None
            )
            readiness_password = (
                str(certificate_password or "").strip()
                or str(password_provider() or "").strip()
            )
            readiness(
                operation="autorizacao", model=model, password=readiness_password,
                permission="transmit", series=series,
                require_catalog=True, require_numbering=True,
            )
        reservation = self.fiscal_service.reserve_number(
            model=model, series=series, environment=environment
        )
        try:
            issuer = dict(config.get("issuer") or {})
            issuer.update({
                "cnpj": config.get("cnpj", ""), "state": config.get("state", ""),
                "tax_regime_code": crt,
            })
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
                    "strict_tax_profile": True,
                    "final_consumer": 1, "presence": 1,
                },
            )
            reason = str(contingency_reason or "").strip()
            if reason:
                if model != "65":
                    raise ValueError("A contingência offline do PDV é exclusiva para NFC-e modelo 65.")
                if not certificate_password:
                    raise ValueError("Informe a senha do certificado A1 para emitir em contingência.")
                xml = self.fiscal_service.apply_contingency(xml, reason=reason, emission_type=9)
                access_key = self.fiscal_service._extract_access_key_from_xml(xml)
                xml = self.fiscal_service.add_nfce_qr_code_v3(
                    xml, pfx_path=config.get("certificate_path", ""), password=certificate_password,
                )
                xml = self.fiscal_service.sign_xml(
                    xml, reference_id=f"NFe{access_key}",
                    pfx_path=config.get("certificate_path", ""), password=certificate_password,
                )
                self.fiscal_service.validate_official_xml(xml, document_type="nfe")
            return FiscalSaleDraft(
                str(reservation["id"]), access_key, model, environment, xml,
                contingency=bool(reason),
            )
        except Exception:
            self.fiscal_service.release_number(
                str(reservation["id"]),
                reason="Falha ao preparar documento antes da venda.",
            )
            raise

    def preview(
        self, *, items: Sequence[Mapping[str, Any]],
        recipient: Mapping[str, Any] | None = None, destination: int = 1,
        issued_at: datetime | None = None,
    ) -> FiscalSalePreview:
        """Gera uma conferência fiscal local sem reservar número nem persistir documento."""
        config = self.fiscal_service.load_config()
        model = str(config.get("default_model") or "65")
        problems = self.fiscal_service.validate_ready(operation="autorizacao", model=model)
        if problems:
            raise ValueError("; ".join(problems))
        crt = self.fiscal_service.TAX_REGIME_CODES.get(
            str(config.get("tax_regime") or "").upper(), 0
        )
        when = issued_at or datetime.now().astimezone()
        fiscal_items = self.fiscal_service.prepare_sale_items(
            items, destination=destination, crt=crt,
            destination_state=str((recipient or {}).get("state") or config.get("state") or ""),
            tax_regime=str(config.get("tax_regime") or ""),
            require_rtc=self._requires_rtc(config, when),
        )
        environment = str(config.get("environment") or "HOMOLOGACAO").upper()
        series = int(config.get("sale_series_65" if model == "65" else "sale_series_55") or 1)
        issuer = dict(config.get("issuer") or {})
        issuer.update({
            "cnpj": config.get("cnpj", ""), "state": config.get("state", ""),
            "tax_regime_code": crt,
        })
        xml, _temporary_key = self.fiscal_service.build_document_xml(
            issuer=issuer, recipient=dict(recipient or {}), items=fiscal_items,
            document={
                "model": model, "series": series, "number": 1,
                "state_code": self.fiscal_service.STATE_CODES[str(config["state"]).upper()],
                "issued_at": when, "environment": environment,
                "numeric_code": "00000001", "destination": int(destination),
                "payment_code": "90", "strict_tax_profile": True,
                "final_consumer": 1, "presence": 1,
            },
        )
        root = ET.fromstring(xml)
        total_text = next(
            (node.text for node in root.iter() if node.tag.rsplit("}", 1)[-1] == "vNFTot"),
            None,
        ) or next(
            (node.text for node in root.iter() if node.tag.rsplit("}", 1)[-1] == "vNF"),
            "0",
        )
        return FiscalSalePreview(
            model=model, environment=environment, series=series,
            item_count=len(fiscal_items), total=Decimal(str(total_text)), xml=xml,
        )

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
        # O cadastro técnico CONSUMIDOR_FINAL representa operação sem
        # destinatário identificado. Isso é diferente de um cliente digitado
        # parcialmente: quando há destinatário, CPF/CNPJ e endereço continuam
        # obrigatórios para NF-e 55.
        if technical_consumer:
            if fiscal_model == "65":
                return {}, 1
            environment = str(config.get("environment") or "HOMOLOGACAO").upper()
            if environment != "HOMOLOGACAO":
                raise ValueError(
                    "NF-e modelo 55 exige destinatário identificado. Selecione um cliente "
                    "com CPF/CNPJ e endereço fiscal completo."
                )
            issuer = dict(config.get("issuer") or {})
            required = {
                "street": issuer.get("street"), "number": issuer.get("number"),
                "district": issuer.get("district"), "city_code": issuer.get("city_code"),
                "city": issuer.get("city"), "state": issuer.get("state") or config.get("state"),
                "zip_code": issuer.get("zip_code"),
            }
            if any(not str(value or "").strip() for value in required.values()):
                raise ValueError(
                    "Homologação da NF-e 55 exige endereço completo no cadastro do emitente."
                )
            return {
                "document": self.fiscal_service.HOMOLOGATION_RECIPIENT_CNPJ,
                "name": self.fiscal_service.HOMOLOGATION_RECIPIENT_NAME,
                "state_taxpayer_indicator": 9,
                **required,
            }, 1
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
            }
            if any(not str(value or "").strip() for value in required.values()):
                raise ValueError(
                    "NF-e exige o endereço fiscal completo do cliente. Preencha logradouro, número, "
                    "bairro, município, código IBGE e UF no cadastro."
                )
            recipient.update(required)
            zip_code = str(customer.get("fiscal_cep") or "").strip()
            if zip_code:
                recipient["zip_code"] = zip_code
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

    def persist_draft(
        self, connection: Any, sale_id: int, draft: FiscalSaleDraft
    ) -> dict[str, Any]:
        actor = self.fiscal_service.require_authenticated_actor(
            "transmit", operation="registrar uma venda na fila fiscal"
        )
        now = datetime.now().astimezone().isoformat()
        cursor = connection.execute(
            """INSERT INTO fiscal_sale_documents
               (sale_id,reservation_id,access_key,model,environment,status,xml_b64,created_at,updated_at)
               VALUES(?,?,?,?,?,'PENDENTE',?,?,?)""",
            (int(sale_id), draft.reservation_id, draft.access_key, draft.model,
             draft.environment, base64.b64encode(draft.xml).decode("ascii"), now, now),
        )
        document_id = int(cursor.lastrowid)
        xml_b64 = base64.b64encode(draft.xml).decode("ascii")
        return FiscalOutboxService.enqueue_in_transaction(
            connection, sale_id=int(sale_id), fiscal_document_id=document_id,
            access_key=draft.access_key, environment=draft.environment,
            operation="autorizacao", model=draft.model,
            reservation_id=draft.reservation_id, xml_b64=xml_b64,
            original_xml_b64=xml_b64, actor=actor, contingency=draft.contingency,
            contingency_deadline_at=(
                (datetime.now().astimezone() + timedelta(hours=24)).isoformat()
                if draft.contingency and draft.model == "65" else ""
            ),
        )

    def enqueue_pending(self, *, sale_id: int) -> dict[str, Any]:
        actor = self.fiscal_service.require_authenticated_actor(
            "transmit", operation="enfileirar uma venda fiscal pendente"
        )
        connection = self.fiscal_service.connection_factory()
        try:
            row = connection.execute(
                """SELECT d.id,d.access_key,d.model,d.xml_b64,d.queue_id,d.status,d.environment,
                          d.reservation_id,o.id,o.status
                     FROM fiscal_sale_documents d
                     LEFT JOIN fiscal_outbox o ON o.fiscal_document_id=d.id
                    WHERE d.sale_id=?""", (int(sale_id),)
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
        if row[8] is not None:
            return {"id": str(row[8]), "status": str(row[9]), "access_key": str(row[1])}
        connection = self.fiscal_service.connection_factory()
        try:
            connection.execute("BEGIN IMMEDIATE")
            queued = FiscalOutboxService.enqueue_in_transaction(
                connection, sale_id=int(sale_id), fiscal_document_id=int(row[0]),
                access_key=str(row[1]), environment=str(row[6]), operation="autorizacao",
                model=str(row[2]), reservation_id=str(row[7]), xml_b64=str(row[3]),
                original_xml_b64=str(row[3]), actor=actor,
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
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

    def generate_danfe_for_sale(self, sale_id: int) -> Path:
        """Gera DANFE somente a partir do XML processado e autorizado."""

        sale = next(
            (row for row in self.list_sales() if int(row.get("sale_id") or 0) == int(sale_id)),
            None,
        )
        if sale is None or str(sale.get("status") or "").upper() != "AUTORIZADO":
            raise ValueError("O DANFE só pode ser gerado depois da autorização da NF-e.")
        key = str(sale.get("access_key") or "").strip()
        document = next(
            (
                row for row in self.fiscal_service.list_documents()
                if str(row.get("access_key") or "").strip() == key
                and str(row.get("status") or "").upper() == "AUTORIZADO"
            ),
            None,
        )
        source = Path(str((document or {}).get("processed_path") or ""))
        if len(key) != 44 or not source.is_file():
            raise ValueError("O XML autorizado da NF-e não está disponível para gerar o DANFE.")
        output = self.fiscal_service.storage_dir / "danfe" / f"DANFE_{key}.pdf"
        return self.fiscal_service.generate_official_danfe_pdf(
            authorized_xml=source.read_bytes(), output_path=output,
        )

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
            "SELECT id,status FROM fiscal_sale_documents WHERE sale_id=?", (int(sale_id),)
        ).fetchone()
        if not row:
            return
        document_id, status = int(row[0]), str(row[1] or "").upper()
        if status == "AUTORIZADO":
            raise ValueError(
                "Esta venda possui documento autorizado. Cancele pela Central Fiscal antes de reverter estoque e financeiro."
            )
        if status in {"CANCELAMENTO_PENDENTE", "PROCESSANDO", "RESPOSTA_DESCONHECIDA"}:
            raise ValueError(
                "O documento possui cancelamento fiscal pendente ou resposta desconhecida. "
                "O estorno comercial só pode ocorrer após confirmação da SEFAZ."
            )
        if status == "CANCELADO":
            raise ValueError("O documento fiscal desta venda já está cancelado.")
        # Depois que a SEFAZ aceitou o cancelamento, transmissões históricas da
        # autorização não podem bloquear o estorno comercial. A trava da fila
        # continua obrigatória para todos os estados anteriores à confirmação.
        outbox_exists = status != "CANCELADO_FISCAL" and connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='fiscal_outbox'"
        ).fetchone()
        if outbox_exists:
            queued = connection.execute(
                """SELECT status,attempts,metadata_json FROM fiscal_outbox
                     WHERE fiscal_document_id=? ORDER BY id DESC LIMIT 1""",
                (document_id,),
            ).fetchone()
            if queued:
                try:
                    metadata = json.loads(str(queued[2] or "{}"))
                except (TypeError, ValueError):
                    metadata = {}
                if (
                    int(queued[1] or 0) > 0
                    or str(queued[0] or "").upper() in {
                        "PROCESSANDO", "RESPOSTA_DESCONHECIDA", "CONCLUIDO"
                    }
                    or metadata.get("transmission_started_at")
                ):
                    raise ValueError(
                        "A venda possui transmissão fiscal iniciada ou de resposta desconhecida. "
                        "Consulte a SEFAZ antes de cancelar."
                    )
        new_status = "CANCELADO" if status == "CANCELADO_FISCAL" else "CANCELADO_LOCAL"
        connection.execute(
            "UPDATE fiscal_sale_documents SET status=?,updated_at=? WHERE sale_id=?",
            (new_status, datetime.now().astimezone().isoformat(), int(sale_id)),
        )

    def finalize_local_cancellation(self, *, sale_id: int) -> None:
        self.fiscal_service.require_authenticated_actor(
            "transmit", operation="finalizar o cancelamento local de uma venda fiscal"
        )
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
                str(row[1]), reason="Venda cancelada antes da autorização fiscal."
            )
        if str(row[0] or ""):
            try:
                self.fiscal_service.release_number(
                    str(row[0]), reason="Venda cancelada antes da autorização fiscal."
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
        self, *, sale_id: int, password: str, justification: str
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
            password=password, protocol=str(row[1]),
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
