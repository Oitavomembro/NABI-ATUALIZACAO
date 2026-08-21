from __future__ import annotations

import logging
import os
import socket
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from services.fiscal_outbox_service import FiscalOutboxService


class FiscalOutboxWorker:
    """Processa documentos fiscais persistidos sem bloquear a interface."""

    def __init__(
        self,
        fiscal_service: Any,
        *,
        poll_seconds: float = 15.0,
        lease_seconds: int = 180,
        heartbeat_seconds: float | None = None,
        credential_retry_minutes: int = 15,
        max_per_cycle: int = 5,
        result_handler: Any | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.fiscal_service = fiscal_service
        self.outbox = FiscalOutboxService(fiscal_service.connection_factory)
        self.poll_seconds = max(0.1, float(poll_seconds))
        self.lease_seconds = max(1, int(lease_seconds))
        default_heartbeat = max(0.1, self.lease_seconds / 3.0)
        self.heartbeat_seconds = max(
            0.01, float(default_heartbeat if heartbeat_seconds is None else heartbeat_seconds)
        )
        self.credential_retry_minutes = max(1, int(credential_retry_minutes))
        self.max_per_cycle = max(1, int(max_per_cycle))
        self.logger = logger or logging.getLogger("NabiCode.FiscalOutboxWorker")
        self.result_handler = result_handler
        self.worker_id = (
            f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:12]}"
        )
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lifecycle_lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self) -> bool:
        with self._lifecycle_lock:
            if self.is_running:
                return False
            self._stop_event.clear()
            self._wake_event.clear()
            self._thread = threading.Thread(
                target=self._run,
                name=f"FiscalOutbox-{self.worker_id[-12:]}",
                daemon=False,
            )
            self._thread.start()
            self.logger.info("worker_start worker_id=%s", self.worker_id)
            return True

    def stop(self, *, timeout: float = 55.0) -> bool:
        with self._lifecycle_lock:
            thread = self._thread
            self._stop_event.set()
            self._wake_event.set()
        if thread and thread is not threading.current_thread():
            thread.join(max(0.0, float(timeout)))
        stopped = not bool(thread and thread.is_alive())
        if stopped:
            self.logger.info("worker_stop worker_id=%s", self.worker_id)
        else:
            self.logger.warning("worker_stop_pending worker_id=%s", self.worker_id)
        return stopped

    def wake(self) -> None:
        """Antecipa o próximo ciclo sem criar polling agressivo."""
        self._wake_event.set()

    def run_once(self) -> dict[str, Any] | None:
        now = datetime.now(timezone.utc)
        claimed = self.outbox.claim_next(
            worker_id=self.worker_id,
            lease_seconds=self.lease_seconds,
            now=now,
            operations=("autorizacao", "recibo", "evento"),
        )
        reconciliation = False
        if claimed is None:
            claimed = self.outbox.claim_unknown(
                worker_id=self.worker_id, lease_seconds=self.lease_seconds, now=now
            )
            reconciliation = claimed is not None
        if claimed is None:
            return None

        item_id = int(claimed["id"])
        heartbeat_stop = threading.Event()
        claim_lost = threading.Event()
        heartbeat = threading.Thread(
            target=self._renew_claim_loop,
            args=(item_id, heartbeat_stop, claim_lost),
            name=f"FiscalLease-{self.worker_id[-12:]}",
            daemon=False,
        )
        heartbeat.start()
        self.logger.info(
            "claim worker_id=%s item=%s chave=%s operacao=%s tentativa=%s reconciliacao=%s",
            self.worker_id, item_id, claimed.get("access_key", ""),
            claimed.get("operation", ""), claimed.get("attempts", 0), reconciliation,
        )
        password = ""
        try:
            if str(claimed.get("environment") or "").upper() == "PRODUCAO":
                result = self.outbox.block_production(item_id, worker_id=self.worker_id)
                self.fiscal_service._sync_sale_document(
                    claimed, status="FALHA", error="Produção fiscal bloqueada nesta versão."
                )
                self.logger.error("production_blocked worker_id=%s item=%s", self.worker_id, item_id)
                return result

            password = self.fiscal_service.session_certificate_password()
            if not password:
                result = self.outbox.await_credential(
                    item_id,
                    worker_id=self.worker_id,
                    retry_at=now + timedelta(minutes=self.credential_retry_minutes),
                    preserve_unknown=reconciliation,
                )
                self.logger.warning(
                    "credential_required worker_id=%s item=%s chave=%s",
                    self.worker_id, item_id, claimed.get("access_key", ""),
                )
                return result

            if reconciliation:
                claimed = self.fiscal_service.prepare_claimed_reconciliation(
                    claimed, worker_id=self.worker_id
                )
            self.logger.info(
                "process_start worker_id=%s item=%s operacao=%s",
                self.worker_id, item_id, claimed.get("operation", ""),
            )
            processed = self.fiscal_service.process_transmission_queue(
                password=password,
                limit=1,
                queue_ids=[str(item_id)],
                claimed_worker_id=self.worker_id,
            )
            if not processed:
                raise RuntimeError("O item reivindicado não foi processado.")
            result = processed[0]
            if self.result_handler is not None:
                self.result_handler(dict(result))
            self.logger.info(
                "process_result worker_id=%s item=%s status=%s cstat=%s recibo=%s mensagem=%s",
                self.worker_id, item_id, result.get("status", ""),
                result.get("last_status_code", ""), result.get("receipt", ""),
                result.get("last_message") or result.get("last_error") or "",
            )
            return result
        except Exception as exc:
            # Falhas anteriores à comunicação são reagendáveis. Se a etapa já
            # marcou transmissão iniciada, a própria outbox preserva a incerteza.
            current = self.outbox.list_items()
            latest = next((row for row in current if str(row.get("id")) == str(item_id)), {})
            if (
                claim_lost.is_set()
                or latest.get("status") != "PROCESSANDO"
                or latest.get("worker_id") != self.worker_id
            ):
                result = latest
                self.logger.error(
                    "claim_lost worker_id=%s item=%s current_owner=%s",
                    self.worker_id, item_id, latest.get("worker_id", ""),
                )
            elif latest.get("transmission_started_at"):
                result = self.outbox.mark_unknown(
                    item_id, worker_id=self.worker_id,
                    error_code="PROCESSAMENTO_INTERROMPIDO", error_message=str(exc),
                )
            elif latest.get("status") == "PROCESSANDO":
                delay = min(60, max(1, int(latest.get("retry_minutes") or 5)))
                result = self.outbox.reschedule(
                    item_id, worker_id=self.worker_id,
                    next_attempt_at=datetime.now(timezone.utc) + timedelta(minutes=delay),
                    error_code="ERRO_LOCAL", error_message=str(exc),
                )
            else:
                result = latest
            self.logger.exception(
                "process_error worker_id=%s item=%s chave=%s",
                self.worker_id, item_id, claimed.get("access_key", ""),
            )
            return result
        finally:
            password = ""
            heartbeat_stop.set()
            heartbeat.join(max(1.0, self.heartbeat_seconds * 2.0))
            if heartbeat.is_alive():
                self.logger.critical(
                    "lease_heartbeat_stop_pending worker_id=%s item=%s",
                    self.worker_id, item_id,
                )

    def _renew_claim_loop(
        self, item_id: int, stop_event: threading.Event, claim_lost: threading.Event
    ) -> None:
        while not stop_event.wait(self.heartbeat_seconds):
            try:
                renewed = self.outbox.renew_lease(
                    item_id,
                    worker_id=self.worker_id,
                    lease_seconds=self.lease_seconds,
                )
            except Exception:
                self.logger.exception(
                    "lease_heartbeat_error worker_id=%s item=%s", self.worker_id, item_id
                )
                claim_lost.set()
                return
            if renewed is None:
                claim_lost.set()
                self.logger.error(
                    "lease_claim_lost worker_id=%s item=%s", self.worker_id, item_id
                )
                return

    def _run(self) -> None:
        while not self._stop_event.is_set():
            processed = 0
            try:
                for _ in range(self.max_per_cycle):
                    if self._stop_event.is_set():
                        break
                    if self.run_once() is None:
                        break
                    processed += 1
            except Exception:
                self.logger.exception("worker_cycle_error worker_id=%s", self.worker_id)
            wait_seconds = 0.25 if processed >= self.max_per_cycle else self.poll_seconds
            self._wake_event.wait(wait_seconds)
            self._wake_event.clear()
