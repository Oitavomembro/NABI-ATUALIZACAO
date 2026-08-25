from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path

from .accountant_delivery_dto import AccountantDeliveryPlan


class AccountantDeliveryApplicationService:
    """Caso de uso humano; revisar nunca prepara, enfileira ou transporta."""

    def __init__(self, gateway, security) -> None:
        self._gateway = gateway
        self._security = security

    def _actor(self) -> str:
        if not self._security.require("relatorios", "generate"):
            raise PermissionError("Sessão válida e permissão de Relatórios são obrigatórias.")
        session = self._security.session
        actor = str(session.user.username if session and session.user else "").strip()
        if not actor:
            raise PermissionError("Não foi possível confirmar o operador da sessão.")
        return actor

    @staticmethod
    def _sha(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as package:
            for chunk in iter(lambda: package.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _recipient(value: object) -> str:
        recipient = " ".join(unicodedata.normalize("NFKC", str(value or "")).split())
        if not recipient or len(recipient) > 200:
            raise ValueError("Informe um destinatário/contador válido.")
        if any(unicodedata.category(character).startswith("C") for character in recipient):
            raise ValueError("Informe um destinatário/contador válido.")
        return recipient

    @staticmethod
    def _valid_cnpj(value: str) -> bool:
        if not re.fullmatch(r"\d{14}", value) or len(set(value)) == 1:
            return False
        numbers = [int(character) for character in value]
        for size, weights in (
            (12, (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)),
            (13, (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)),
        ):
            remainder = sum(numbers[index] * weights[index] for index in range(size)) % 11
            expected = 0 if remainder < 2 else 11 - remainder
            if numbers[size] != expected:
                return False
        return True

    @staticmethod
    def _payload(plan: AccountantDeliveryPlan) -> dict[str, str]:
        return {
            "package_path": plan.package_path,
            "package_sha256": plan.package_sha256,
            "cnpj": plan.cnpj,
            "competence": plan.competence,
            "profile": plan.profile,
            "recipient": plan.recipient,
            "destination": plan.destination,
            "reviewed_by": plan.reviewed_by,
            "idempotency_key": plan.idempotency_key,
        }

    @classmethod
    def _fingerprint(cls, payload: dict[str, str]) -> str:
        return hashlib.sha256(json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")).hexdigest()

    def review(self, *, package, recipient: str, destination: str,
               cnpj_confirmed: bool, consent: bool) -> AccountantDeliveryPlan:
        actor = self._actor()
        if cnpj_confirmed is not True:
            raise ValueError("Confirme explicitamente o CNPJ da empresa.")
        if consent is not True:
            raise ValueError("O consentimento explícito para entrega é obrigatório.")
        package_path = Path(package.path).expanduser().resolve()
        if package_path.suffix.casefold() != ".zip" or not package_path.is_file():
            raise ValueError("Pacote mensal não encontrado.")
        cnpj = str(package.cnpj or "").strip()
        competence = str(package.competence or "").strip()
        profile = str(package.profile or "").strip().upper()
        if not self._valid_cnpj(cnpj):
            raise ValueError("O CNPJ do pacote é inválido.")
        if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", competence):
            raise ValueError("A competência do pacote é inválida.")
        if profile not in {"ESSENCIAL", "COMPLETO", "AUDITORIA"}:
            raise ValueError("O perfil do pacote é inválido.")
        declared_hash = str(package.package_sha256 or "").strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", declared_hash):
            raise ValueError("O hash do pacote é inválido.")
        package_hash = self._sha(package_path)
        if package_hash != declared_hash:
            raise ValueError("O pacote mudou depois da geração. Gere e revise novamente.")
        destination_path = Path(destination).expanduser().resolve()
        if not destination_path.is_dir():
            raise ValueError("Escolha uma pasta local, de rede ou OneDrive já existente.")
        recipient_value = self._recipient(recipient)
        identity = {
            "package_sha256": package_hash,
            "cnpj": cnpj,
            "competence": competence,
            "profile": profile,
            "recipient_hash": hashlib.sha256(recipient_value.casefold().encode("utf-8")).hexdigest(),
            "destination": str(destination_path),
        }
        key = "acct-" + self._fingerprint(identity)[:48]
        payload = {
            "package_path": str(package_path), "package_sha256": package_hash,
            "cnpj": cnpj, "competence": competence,
            "profile": profile, "recipient": recipient_value,
            "destination": str(destination_path), "reviewed_by": actor,
            "idempotency_key": key,
        }
        return AccountantDeliveryPlan(**payload, fingerprint=self._fingerprint(payload))

    def _validate(self, plan: AccountantDeliveryPlan, *, verify_package: bool = False) -> None:
        if self._actor() != plan.reviewed_by:
            raise PermissionError("A sessão mudou depois da revisão. Revise novamente.")
        if self._fingerprint(self._payload(plan)) != plan.fingerprint:
            raise ValueError("A revisão de entrega foi alterada. Revise novamente.")
        if verify_package:
            try:
                current = self._sha(Path(plan.package_path))
            except OSError as exc:
                raise ValueError("Pacote mensal não encontrado.") from exc
            if current != plan.package_sha256:
                raise ValueError("O pacote mudou depois da revisão. Gere e revise novamente.")

    def prepare(self, plan: AccountantDeliveryPlan):
        self._validate(plan, verify_package=True)
        return self._gateway.prepare(plan)

    def enqueue(self, plan: AccountantDeliveryPlan):
        self._validate(plan)
        return self._gateway.enqueue(plan)

    def dispatch(self, plan: AccountantDeliveryPlan):
        self._validate(plan)
        return self._gateway.dispatch(plan)

    def check_receipt(self, plan: AccountantDeliveryPlan):
        self._validate(plan)
        return self._gateway.check_receipt(plan)
