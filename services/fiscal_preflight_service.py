from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class FiscalPreflightResult:
    model: str
    validated_models: tuple[str, ...]
    catalog_total: int
    catalog_ready: int
    certificate_document: str
    xml_sha256: str
    xml_sha256_by_model: tuple[tuple[str, str], ...]
    problems: tuple[str, ...]

    @property
    def success(self) -> bool:
        return not self.problems


class FiscalPreflightService:
    """Prova local de prontidão fiscal sem rede, reserva ou persistência."""

    def __init__(self, fiscal_service: Any, catalog_service: Any) -> None:
        self.fiscal_service = fiscal_service
        self.catalog_service = catalog_service

    def run(self, *, password: str) -> FiscalPreflightResult:
        config = self.fiscal_service.load_config()
        model = str(config.get("default_model") or "65")
        configured_models = config.get("enabled_models") or [model]
        models = tuple(dict.fromkeys(str(item) for item in configured_models if str(item) in {"55", "65"}))
        if not models:
            models = (model,)
        problems: list[str] = []
        for current_model in models:
            label = "NF-e 55" if current_model == "55" else "NFC-e 65"
            problems.extend(
                f"{label}: {problem}"
                for problem in self.fiscal_service.validate_ready(
                    operation="autorizacao", model=current_model
                )
            )
        crt = self.fiscal_service.TAX_REGIME_CODES.get(
            str(config.get("tax_regime") or "").upper(), 0
        )
        catalog = self.catalog_service.audit(crt=crt)
        if not catalog.total:
            problems.append("O catálogo não possui mercadorias fiscais ativas.")
        elif catalog.blocked:
            problems.append(
                f"O catálogo possui {catalog.blocked} produto(s) com pendência fiscal."
            )

        certificate_document = ""
        xml_hash = ""
        model_hashes: list[tuple[str, str]] = []
        certificate_path = str(config.get("certificate_path") or "")
        try:
            certificate = self.fiscal_service.inspect_certificate(certificate_path, password)
            certificate_document = certificate.document
            configured_document = self.fiscal_service._normalize_cnpj(config.get("cnpj"))
            if certificate.expired:
                problems.append("O certificado está expirado ou ainda não é válido.")
            if configured_document and certificate.document and configured_document != certificate.document:
                problems.append("O CNPJ do certificado não corresponde ao emitente configurado.")
        except Exception as exc:
            problems.append(str(exc))

        if not problems and catalog.ready_product_ids:
            for current_model in models:
                label = "NF-e 55" if current_model == "55" else "NFC-e 65"
                try:
                    fiscal_items = self.fiscal_service.prepare_sale_items(
                        [{"produto_id": catalog.ready_product_ids[0], "item": "PRÉ-VOO", "qtd": 1, "preco": "1.00"}],
                        destination=1, crt=crt,
                    )
                    issuer = dict(config.get("issuer") or {})
                    issuer.update({
                        "cnpj": config.get("cnpj", ""), "state": config.get("state", ""),
                        "tax_regime_code": crt,
                    })
                    recipient = {} if current_model == "65" else {
                        "document": "52998224725", "name": "CONSUMIDOR DE HOMOLOGACAO"
                    }
                    issued_at = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
                    xml, access_key = self.fiscal_service.build_document_xml(
                        issuer=issuer, recipient=recipient, items=fiscal_items,
                        document={
                            "model": current_model, "series": 999, "number": 1,
                            "state_code": self.fiscal_service.STATE_CODES[str(config.get("state") or "").upper()],
                            "issued_at": issued_at, "environment": "HOMOLOGACAO",
                            "numeric_code": "00000001", "destination": 1,
                            "strict_tax_profile": True, "final_consumer": 1, "presence": 1,
                        },
                    )
                    signed = self.fiscal_service.sign_xml(
                        xml, reference_id=f"NFe{access_key}",
                        pfx_path=certificate_path, password=password,
                    )
                    schema_problems = self.fiscal_service.validate_xml_schema(
                        signed, self.fiscal_service.official_schema_path("nfe")
                    )
                    problems.extend(f"{label}: {problem}" for problem in schema_problems)
                    if not schema_problems:
                        current_hash = hashlib.sha256(signed).hexdigest().upper()
                        model_hashes.append((current_model, current_hash))
                        if current_model == model or not xml_hash:
                            xml_hash = current_hash
                except Exception as exc:
                    problems.append(f"{label}: {exc}")
        return FiscalPreflightResult(
            model=model, validated_models=tuple(item[0] for item in model_hashes),
            catalog_total=catalog.total, catalog_ready=catalog.ready,
            certificate_document=certificate_document, xml_sha256=xml_hash,
            xml_sha256_by_model=tuple(model_hashes),
            problems=tuple(dict.fromkeys(problem for problem in problems if problem)),
        )
