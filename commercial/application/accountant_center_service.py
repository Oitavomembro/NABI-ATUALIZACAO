from __future__ import annotations

import hashlib
from pathlib import Path

from .accountant_center_dto import AccountantPackageOutcome, AccountantPackagePlan


class AccountantCenterApplicationService:
    """Porta autenticada para preparar e exportar o pacote oficial do contador."""

    PROFILES = ("ESSENCIAL", "COMPLETO", "AUDITORIA")

    def __init__(self, package_service, security) -> None:
        self._package_service = package_service
        self._security = security

    def _actor(self) -> str:
        if not self._security.require("relatorios", "generate"):
            raise PermissionError("Sessão válida e permissão de Relatórios são obrigatórias.")
        session = self._security.session
        actor = str(session.user.username if session and session.user else "").strip()
        if not actor:
            raise PermissionError("Não foi possível confirmar o operador da sessão.")
        return actor

    def review(self, *, cnpj: str, competence: str, profile: str,
               output_path: str, cnpj_confirmed: bool) -> AccountantPackagePlan:
        actor = self._actor()
        if not cnpj_confirmed:
            raise ValueError("Confirme que o CNPJ pertence à empresa deste pacote.")
        document,period,normalized_profile,destination=self._package_service.normalize_request(
            cnpj=cnpj,competence=competence,profile=profile,output_path=output_path,
        )
        return AccountantPackagePlan.create(
            cnpj=document, competence=period, profile=normalized_profile,
            output_path=str(destination), reviewed_by=actor,
        )

    def generate(self, plan: AccountantPackagePlan) -> AccountantPackageOutcome:
        actor = self._actor()
        if actor != plan.reviewed_by:
            raise PermissionError("A sessão mudou depois da revisão. Revise novamente.")
        expected = AccountantPackagePlan.create(
            cnpj=plan.cnpj, competence=plan.competence, profile=plan.profile,
            output_path=plan.output_path, reviewed_by=plan.reviewed_by,
        )
        if expected.fingerprint != plan.fingerprint:
            raise ValueError("A revisão foi alterada. Revise novamente antes de gerar.")
        result = self._package_service.export(
            cnpj=plan.cnpj, competence=plan.competence, profile=plan.profile,
            output_path=plan.output_path,
        )
        digest = hashlib.sha256()
        with Path(result.path).open("rb") as package:
            for chunk in iter(lambda: package.read(1024 * 1024), b""):
                digest.update(chunk)
        return AccountantPackageOutcome(
            result.path, result.cnpj, result.competence, result.profile,
            result.status, result.files, result.movements, result.pendencies,
            digest.hexdigest(),
        )
