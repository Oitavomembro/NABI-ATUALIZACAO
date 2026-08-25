from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class FiscalModelReadiness:
    model: str
    label: str
    enabled: bool
    local_problems: tuple[str, ...]
    numbering_initialized: bool
    next_number: int | None


@dataclass(frozen=True, slots=True)
class FiscalReadinessSnapshot:
    state: str
    environment: str
    enabled: bool
    issuer_document: str
    issuer_state: str
    tax_regime: str
    certificate_configured: bool
    certificate_name: str
    models: tuple[FiscalModelReadiness, ...]
    notices: tuple[str, ...]


class FiscalReadinessApplicationService:
    """Consulta local da Central Fiscal; não recebe senha nem expõe transmissão."""

    def __init__(self, fiscal_service, security) -> None:
        if fiscal_service is None or security is None:
            raise ValueError("FiscalService e segurança são obrigatórios.")
        self._fiscal = fiscal_service
        self._security = security

    def _require_view(self) -> None:
        session = getattr(self._security, "session", None)
        if session is None or self._security.is_expired():
            raise PermissionError("Sessão expirada. Entre novamente.")
        if not self._security.require("fiscal", "view"):
            raise PermissionError("Seu perfil não pode consultar a Central Fiscal.")
        self._security.touch()

    def _require_configure(self) -> None:
        session = getattr(self._security, "session", None)
        if session is None or self._security.is_expired():
            raise PermissionError("Sessão expirada. Entre novamente.")
        if not self._security.require("fiscal", "configure"):
            raise PermissionError("Seu perfil não pode configurar a Central Fiscal.")
        self._security.touch()

    def configuration(self) -> dict:
        self._require_view()
        return dict(self._fiscal.load_config())

    def configure_homologation(self, values: dict, *, password: str) -> dict:
        """Valida o A1 e salva somente configuração de homologação.

        A senha permanece apenas na memória da sessão do FiscalService. O arquivo
        original não é movido, apagado ou incorporado ao banco.
        """
        self._require_configure()
        cnpj = "".join(ch for ch in str(values.get("cnpj") or "") if ch.isdigit())
        if len(cnpj) != 14:
            raise ValueError("Informe um CNPJ com 14 dígitos.")
        certificate_path = str(values.get("certificate_path") or "").strip()
        if not certificate_path:
            raise ValueError("Selecione o certificado A1 (.pfx ou .p12).")
        secret = str(password or "")
        if not secret:
            raise ValueError("Digite a senha do certificado A1.")
        certificate = self._fiscal.inspect_certificate(certificate_path, secret)
        if certificate.expired:
            raise ValueError("O certificado A1 está expirado ou ainda não é válido.")
        if certificate.document and certificate.document != cnpj:
            raise ValueError(
                "O CNPJ do certificado não corresponde ao emitente informado. "
                f"Informado: {cnpj}; certificado: {certificate.document}."
            )
        models = [model for model in ("55", "65") if values.get(f"model_{model}")]
        saved = self._fiscal.save_config({
            "enabled": True,
            "environment": "HOMOLOGACAO",
            "cnpj": cnpj,
            "state": values.get("state"),
            "tax_regime": values.get("tax_regime"),
            "enabled_models": models,
            "default_model": values.get("default_model"),
            "sale_series_55": values.get("sale_series_55"),
            "sale_series_65": values.get("sale_series_65"),
            "certificate_path": certificate_path,
            "issuer": {
                "name": values.get("issuer_name"),
                "state_registration": values.get("state_registration"),
                "city_code": values.get("city_code"),
                "city": values.get("city"),
                "street": values.get("street"),
                "number": values.get("number"),
                "district": values.get("district"),
                "zip_code": values.get("zip_code"),
            },
        })
        self._fiscal.cache_certificate_password(secret)
        return saved

    @staticmethod
    def _masked_document(value: object) -> str:
        digits = "".join(character for character in str(value or "") if character.isdigit())
        if len(digits) != 14:
            return "Não configurado"
        return f"{digits[:2]}.***.***/****-{digits[-2:]}"

    def snapshot(self) -> FiscalReadinessSnapshot:
        self._require_view()
        config = dict(self._fiscal.load_config())
        environment = str(config.get("environment") or "HOMOLOGACAO").upper()
        enabled_models = {
            str(model) for model in config.get("enabled_models", ())
        }
        issuer = dict(config.get("issuer") or {})
        configured_cnpj = config.get("cnpj") or issuer.get("cnpj")
        configured_state = config.get("state") or issuer.get("state")
        certificate_path = str(config.get("certificate_path") or "").strip()

        models = []
        all_problems: list[str] = []
        for model in ("55", "65"):
            problems = tuple(self._fiscal.validate_ready(operation="status", model=model))
            all_problems.extend(problems)
            series = int(
                issuer.get("return_series", 1)
                if model == "55" else config.get("nfce_series", 1)
            )
            numbering = self._fiscal.numbering_scope(
                model=model, series=series, environment=environment,
            )
            models.append(FiscalModelReadiness(
                model=model,
                label=str(self._fiscal.MODEL_LABELS.get(model) or f"Modelo {model}"),
                enabled=model in enabled_models,
                local_problems=problems,
                numbering_initialized=bool(numbering.get("initialized")),
                next_number=(
                    int(numbering.get("next_number"))
                    if numbering.get("initialized") else None
                ),
            ))

        notices = [
            "Consulta somente local: nenhuma comunicação com a SEFAZ foi iniciada.",
            "A senha do certificado não foi solicitada, lida nem armazenada.",
            "A prontidão completa depende da verificação manual do A1, cadeia, revogação e catálogo pelo portão oficial.",
        ]
        if environment == "PRODUCAO":
            notices.append("Produção permanece bloqueada nesta versão.")
        state = "BLOQUEADO" if all_problems else "AGUARDA_VERIFICACAO_MANUAL"
        return FiscalReadinessSnapshot(
            state=state,
            environment=environment,
            enabled=bool(config.get("enabled")),
            issuer_document=self._masked_document(configured_cnpj),
            issuer_state=str(configured_state or "Não configurada").upper(),
            tax_regime=str(config.get("tax_regime") or "Não configurado"),
            certificate_configured=bool(certificate_path and Path(certificate_path).is_file()),
            certificate_name=Path(certificate_path).name if certificate_path else "Não configurado",
            models=tuple(models),
            notices=tuple(notices),
        )
