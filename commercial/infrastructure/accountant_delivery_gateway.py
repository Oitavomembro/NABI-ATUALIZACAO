from __future__ import annotations

from pathlib import Path

from commercial.application.accountant_delivery_dto import AccountantDeliveryStatus
from services.accountant_delivery_service import AccountantDeliveryService
from services.accountant_delivery_transport import LocalFolderAccountantTransport


class LocalFolderAccountantDeliveryGateway:
    """Adaptador sem rede própria: somente uma pasta já montada no sistema."""

    def __init__(self, *, outbox_path: str | Path, spool_dir: str | Path) -> None:
        self.outbox_path = Path(outbox_path).expanduser().resolve()
        self.spool_dir = Path(spool_dir).expanduser().resolve()

    def _service(self, plan) -> AccountantDeliveryService:
        return AccountantDeliveryService(
            outbox_path=self.outbox_path,
            spool_dir=self.spool_dir,
            transport=LocalFolderAccountantTransport(plan.destination),
        )

    @staticmethod
    def _status(record) -> AccountantDeliveryStatus:
        return AccountantDeliveryStatus(
            record.idempotency_key, record.status, record.attempts,
            record.transport_reference, record.receipt_sha256, record.last_error_code,
        )

    def prepare(self, plan):
        record = self._service(plan).prepare(
            package_path=plan.package_path, recipient=plan.recipient,
            cnpj=plan.cnpj, cnpj_confirmed=True, consent=True,
            competence=plan.competence, profile=plan.profile,
            idempotency_key=plan.idempotency_key,
        )
        return self._status(record)

    def enqueue(self, plan):
        return self._status(self._service(plan).enqueue(plan.idempotency_key))

    def dispatch(self, plan):
        return self._status(self._service(plan).dispatch(plan.idempotency_key))

    def check_receipt(self, plan):
        service = self._service(plan)
        current = service.get(plan.idempotency_key)
        if current.status == "DESCONHECIDO":
            current = service.reconcile_unknown(plan.idempotency_key)
        elif current.status == "ENVIADO_AO_TRANSPORTE":
            current = service.confirm_receipt(plan.idempotency_key)
        return self._status(current)
