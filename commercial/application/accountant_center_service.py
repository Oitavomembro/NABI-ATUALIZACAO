from __future__ import annotations

import hashlib
from pathlib import Path
from dataclasses import dataclass

from .accountant_center_dto import AccountantPackageOutcome, AccountantPackagePlan


@dataclass(frozen=True, slots=True)
class CompanyIdentity:
    cnpj: str
    legal_name: str
    source: str


class AccountantCenterApplicationService:
    """Porta autenticada para preparar e exportar o pacote oficial do contador."""

    PROFILES = ("ESSENCIAL", "COMPLETO", "AUDITORIA")

    def __init__(self, package_service, security, company_identity_provider) -> None:
        self._package_service = package_service
        self._security = security
        if not callable(company_identity_provider):
            raise ValueError("A fonte central da identidade empresarial é obrigatória.")
        self._company_identity_provider = company_identity_provider

    def company_identity(self) -> CompanyIdentity:
        self._actor()
        identity = self._company_identity_provider()
        if not isinstance(identity, CompanyIdentity):
            raise RuntimeError("A fonte central não forneceu uma identidade empresarial válida.")
        document, _, _, _ = self._package_service.normalize_request(
            cnpj=identity.cnpj, competence="2000-01", profile="ESSENCIAL",
            output_path="identidade.zip",
        )
        if not str(identity.source or "").strip():
            raise RuntimeError("A origem da identidade empresarial não foi comprovada.")
        return CompanyIdentity(document, str(identity.legal_name or "").strip(), identity.source)

    def _actor(self) -> str:
        if not self._security.require("relatorios", "generate"):
            raise PermissionError("Sessão válida e permissão de Relatórios são obrigatórias.")
        session = self._security.session
        actor = str(session.user.username if session and session.user else "").strip()
        if not actor:
            raise PermissionError("Não foi possível confirmar o operador da sessão.")
        return actor

    def review(self, *, competence: str, profile: str,
               output_path: str) -> AccountantPackagePlan:
        actor = self._actor()
        identity = self.company_identity()
        document,period,normalized_profile,destination=self._package_service.normalize_request(
            cnpj=identity.cnpj,competence=competence,profile=profile,output_path=output_path,
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
