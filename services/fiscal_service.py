from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import sys
import tempfile
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlsplit

from services.fiscal_state_catalog import FISCAL_STATE_PROFILES, STATE_CODES, state_profile

try:
    import requests
except ModuleNotFoundError:  # O módulo fiscal é opcional no uso comum.
    requests = None  # type: ignore[assignment]

try:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.serialization import pkcs12
except ModuleNotFoundError:  # Não deve impedir o uso não fiscal do sistema.
    x509 = hashes = serialization = padding = pkcs12 = None  # type: ignore[assignment]

try:
    from lxml import etree
except ModuleNotFoundError:  # Não deve impedir o uso não fiscal do sistema.
    etree = None  # type: ignore[assignment]

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
except ModuleNotFoundError:  # DANFE é opcional no uso comum.
    A4 = mm = canvas = None  # type: ignore[assignment]


@dataclass(frozen=True)
class FiscalCertificateInfo:
    subject: str
    issuer: str
    serial_number: str
    valid_from: str
    valid_until: str
    document: str
    expired: bool


@dataclass(frozen=True)
class FiscalResponse:
    success: bool
    status_code: str
    message: str
    protocol: str = ""
    receipt: str = ""
    access_key: str = ""
    raw_xml: str = ""


class FiscalService:
    """Infraestrutura fiscal opcional sem alterar o schema existente.

    A configuração fica em ``configuracoes``. O certificado e a senha não são
    obrigatórios para o uso geral do sistema e a senha nunca é persistida.
    """

    CONFIG_KEY = "fiscal.config.v1"
    DOCUMENT_INDEX_KEY = "fiscal.documentos.v1"
    EVENT_INDEX_KEY = "fiscal.eventos.v1"
    REJECTION_INDEX_KEY = "fiscal.rejeicoes.v1"
    NUMBERING_KEY = "fiscal.numeracao.v1"
    TRANSMISSION_QUEUE_KEY = "fiscal.fila_transmissao.v1"
    AUTHORIZED_STATUS = {"100", "150"}
    EVENT_ACCEPTED_STATUS = {"128", "135", "136", "155"}
    INUTILIZATION_ACCEPTED_STATUS = {"102"}
    ACCEPTED_STATUS = AUTHORIZED_STATUS | EVENT_ACCEPTED_STATUS | INUTILIZATION_ACCEPTED_STATUS
    VALID_ENVIRONMENTS = {"HOMOLOGACAO", "PRODUCAO"}
    VALID_MODELS = {"55", "65"}
    VALID_EVENTS = {"CANCELAMENTO", "CCE"}
    STATE_CODES = STATE_CODES
    TAX_REGIME_CODES = {
        "MEI": 4,
        "SIMPLES": 1,
        "SIMPLES_NACIONAL": 1,
        "EXCESSO_SUBLIMITE": 2,
        "LUCRO_PRESUMIDO": 3,
        "LUCRO_REAL": 3,
        "REGIME_NORMAL": 3,
        "NORMAL": 3,
    }
    TAX_REGIME_LABELS = {
        "MEI": "MEI",
        "SIMPLES_NACIONAL": "Simples Nacional",
        "EXCESSO_SUBLIMITE": "Simples Nacional — excesso de sublimite",
        "LUCRO_PRESUMIDO": "Lucro Presumido",
        "LUCRO_REAL": "Lucro Real",
    }
    MODEL_LABELS = {"55": "NF-e — modelo 55", "65": "NFC-e — modelo 65"}
    DS_NS = "http://www.w3.org/2000/09/xmldsig#"

    @staticmethod
    def state_profile(uf: str) -> dict[str, Any]:
        """Retorna o perfil nacional sem liberar UFs ainda não homologadas."""
        return dict(state_profile(uf))

    @staticmethod
    def state_catalog() -> list[dict[str, Any]]:
        return [dict(FISCAL_STATE_PROFILES[uf]) for uf in sorted(FISCAL_STATE_PROFILES)]

    def __init__(
        self,
        connection_factory: Callable[[], Any],
        *,
        storage_dir: str | Path | None = None,
        schema_dir: str | Path | None = None,
        http_post: Callable[..., Any] | None = None,
    ) -> None:
        self.connection_factory = connection_factory
        self.storage_dir = Path(storage_dir or (Path.home() / ".nabicode" / "fiscal"))
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        runtime_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
        self.schema_dir = Path(
            schema_dir or runtime_root / "resources" / "fiscal" / "schemas"
        )
        if http_post is not None:
            self.http_post = http_post
        elif requests is not None:
            self.http_post = requests.post
        else:
            self.http_post = None

    @staticmethod
    def _require_dependency(name: str) -> None:
        available = {
            "requests": requests is not None,
            "cryptography": pkcs12 is not None,
            "lxml": etree is not None,
            "reportlab": canvas is not None,
        }
        if not available.get(name, False):
            raise RuntimeError(
                f"A dependência '{name}' não está disponível. "
                "Execute ATUALIZAR_DEPENDENCIAS.bat e gere novamente o executável."
            )

    def load_config(self) -> dict[str, Any]:
        default = {
            "enabled": False,
            "environment": "HOMOLOGACAO",
            "cnpj": "",
            "state": "BA",
            "tax_regime": "SIMPLES_NACIONAL",
            "enabled_models": ["55", "65"],
            "default_model": "65",
            "certificate_path": "",
            "certificate_info": {},
            "issuer": {
                "name": "", "state_registration": "", "city_code": "",
                "city": "", "street": "", "number": "", "district": "",
                "zip_code": "", "return_series": 1,
            },
            "endpoints": {"HOMOLOGACAO": {}, "PRODUCAO": {}},
        }
        value = self._get_setting(self.CONFIG_KEY)
        if not value:
            return default
        try:
            loaded = json.loads(value)
        except (TypeError, ValueError):
            return default
        if not isinstance(loaded, dict):
            return default
        result = dict(default)
        result.update(loaded)
        result["endpoints"] = dict(default["endpoints"]) | dict(loaded.get("endpoints") or {})
        result["issuer"] = dict(default["issuer"]) | dict(loaded.get("issuer") or {})
        models = [str(model) for model in loaded.get("enabled_models", default["enabled_models"]) if str(model) in self.VALID_MODELS]
        result["enabled_models"] = models or list(default["enabled_models"])
        default_model = str(loaded.get("default_model", default["default_model"]))
        result["default_model"] = default_model if default_model in result["enabled_models"] else result["enabled_models"][0]
        return result

    def save_config(self, config: Mapping[str, Any]) -> dict[str, Any]:
        current = self.load_config()
        environment = str(config.get("environment", current["environment"])).strip().upper()
        if environment not in self.VALID_ENVIRONMENTS:
            raise ValueError("Ambiente fiscal inválido.")
        state = str(config.get("state", current["state"])).strip().upper()
        tax_regime = str(config.get("tax_regime", current["tax_regime"])).strip().upper()
        if state and state not in self.STATE_CODES:
            raise ValueError("UF fiscal inválida.")
        if tax_regime and tax_regime not in self.TAX_REGIME_CODES:
            raise ValueError("Regime tributário fiscal inválido.")
        enabled_models = [str(model) for model in config.get("enabled_models", current.get("enabled_models", ["55", "65"]))]
        enabled_models = list(dict.fromkeys(model for model in enabled_models if model in self.VALID_MODELS))
        if not enabled_models:
            raise ValueError("Selecione NF-e 55, NFC-e 65 ou ambas.")
        default_model = str(config.get("default_model", current.get("default_model", "65")))
        if default_model not in enabled_models:
            raise ValueError("O modelo fiscal padrão precisa estar entre os modelos habilitados.")
        current.update({
            "enabled": bool(config.get("enabled", current["enabled"])),
            "environment": environment,
            "cnpj": self._normalize_cnpj(config.get("cnpj", current["cnpj"])),
            "state": state,
            "tax_regime": tax_regime,
            "enabled_models": enabled_models,
            "default_model": default_model,
            "certificate_path": str(config.get("certificate_path", current["certificate_path"])).strip(),
        })
        if "issuer" in config:
            issuer = dict(current.get("issuer") or {})
            issuer.update({str(k): v for k, v in dict(config.get("issuer") or {}).items()})
            issuer["name"] = str(issuer.get("name") or "").strip()
            issuer["state_registration"] = self._digits(issuer.get("state_registration"))
            issuer["city_code"] = self._digits(issuer.get("city_code"))
            issuer["zip_code"] = self._digits(issuer.get("zip_code"))
            issuer["city"] = str(issuer.get("city") or "").strip()
            issuer["street"] = str(issuer.get("street") or "").strip()
            issuer["number"] = str(issuer.get("number") or "").strip()
            issuer["district"] = str(issuer.get("district") or "").strip()
            series = int(issuer.get("return_series") or 1)
            if series < 0 or series > 999:
                raise ValueError("Série fiscal de devolução inválida.")
            issuer["return_series"] = series
            current["issuer"] = issuer
        if "endpoints" in config:
            endpoints = config.get("endpoints") or {}
            validated_endpoints: dict[str, dict[str, str]] = {}
            for env in self.VALID_ENVIRONMENTS:
                validated_endpoints[env] = {}
                for operation, value in dict(endpoints.get(env, {})).items():
                    url = str(value).strip()
                    if not url:
                        continue
                    validated_endpoints[env][str(operation)] = self._validate_endpoint_url(url)
            current["endpoints"] = validated_endpoints
        self._set_setting(self.CONFIG_KEY, json.dumps(current, ensure_ascii=False, sort_keys=True))
        return current

    def is_enabled(self) -> bool:
        return bool(self.load_config().get("enabled"))

    def numbering_status(self, *, model: str | None = None, series: int | None = None, environment: str | None = None) -> list[dict[str, Any]]:
        data = self._load_numbering()
        records = list(data.get("records", {}).values())
        result: list[dict[str, Any]] = []
        for record in records:
            if model is not None and str(record.get("model")) != str(model):
                continue
            if series is not None and int(record.get("series", -1)) != int(series):
                continue
            if environment is not None and str(record.get("environment", "")).upper() != str(environment).upper():
                continue
            result.append(dict(record))
        return sorted(result, key=lambda item: (str(item.get("environment")), str(item.get("model")), int(item.get("series", 0)), int(item.get("number", 0))))

    def reserve_number(
        self,
        *,
        model: str,
        series: int,
        actor: str,
        environment: str | None = None,
        ttl_minutes: int = 30,
    ) -> dict[str, Any]:
        model = str(model).strip()
        if model not in self.VALID_MODELS:
            raise ValueError("Modelo fiscal deve ser 55 ou 65.")
        series = int(series)
        if series < 0 or series > 999:
            raise ValueError("Série fiscal inválida.")
        environment = str(environment or self.load_config().get("environment", "HOMOLOGACAO")).upper()
        if environment not in self.VALID_ENVIRONMENTS:
            raise ValueError("Ambiente fiscal inválido.")
        ttl_minutes = max(1, int(ttl_minutes))
        now = datetime.now(timezone.utc)
        conn = self.connection_factory()
        try:
            conn.execute("BEGIN IMMEDIATE")
            data = self._load_numbering_conn(conn)
            self._recover_expired_reservations(data, now=now)
            scope = f"{environment}:{model}:{series}"
            scopes = data.setdefault("scopes", {})
            last_number = int(scopes.get(scope, 0))
            used = {
                int(item.get("number", 0))
                for item in data.get("records", {}).values()
                if item.get("scope") == scope and item.get("status") in {"RESERVADO", "CONFIRMADO"}
            }
            number = last_number + 1
            while number in used:
                number += 1
            reservation_id = f"{scope}:{number}"
            record = {
                "id": reservation_id,
                "scope": scope,
                "environment": environment,
                "model": model,
                "series": series,
                "number": number,
                "status": "RESERVADO",
                "actor": str(actor or "").strip(),
                "reserved_at": now.isoformat(),
                "expires_at": (now + timedelta(minutes=ttl_minutes)).isoformat(),
                "confirmed_at": "",
                "released_at": "",
                "access_key": "",
            }
            data.setdefault("records", {})[reservation_id] = record
            scopes[scope] = number
            self._save_numbering_conn(conn, data)
            conn.commit()
            return dict(record)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def confirm_number(self, reservation_id: str, *, access_key: str, actor: str) -> dict[str, Any]:
        key = self._normalize_access_key(access_key)
        if len(key) != 44:
            raise ValueError("Chave de acesso inválida para confirmar numeração.")
        conn = self.connection_factory()
        try:
            conn.execute("BEGIN IMMEDIATE")
            data = self._load_numbering_conn(conn)
            record = data.get("records", {}).get(str(reservation_id))
            if not record:
                raise ValueError("Reserva de numeração não encontrada.")
            if record.get("status") == "CONFIRMADO":
                if record.get("access_key") != key:
                    raise ValueError("A numeração já foi confirmada para outra chave de acesso.")
                conn.commit()
                return dict(record)
            if record.get("status") != "RESERVADO":
                raise ValueError("A numeração não está disponível para confirmação.")
            expected_model = key[20:22]
            expected_series = int(key[22:25])
            expected_number = int(key[25:34])
            if expected_model != str(record.get("model")) or expected_series != int(record.get("series")) or expected_number != int(record.get("number")):
                raise ValueError("A chave de acesso não corresponde à numeração reservada.")
            record.update({
                "status": "CONFIRMADO",
                "access_key": key,
                "confirmed_at": datetime.now(timezone.utc).isoformat(),
                "confirmed_by": str(actor or "").strip(),
            })
            self._save_numbering_conn(conn, data)
            conn.commit()
            return dict(record)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def release_number(self, reservation_id: str, *, actor: str, reason: str) -> dict[str, Any]:
        if not str(reason).strip():
            raise ValueError("Motivo da liberação da numeração é obrigatório.")
        conn = self.connection_factory()
        try:
            conn.execute("BEGIN IMMEDIATE")
            data = self._load_numbering_conn(conn)
            record = data.get("records", {}).get(str(reservation_id))
            if not record:
                raise ValueError("Reserva de numeração não encontrada.")
            if record.get("status") == "CONFIRMADO":
                raise ValueError("Numeração confirmada não pode ser liberada.")
            if record.get("status") == "LIBERADO":
                conn.commit()
                return dict(record)
            record.update({
                "status": "LIBERADO",
                "released_at": datetime.now(timezone.utc).isoformat(),
                "released_by": str(actor or "").strip(),
                "release_reason": str(reason).strip(),
            })
            self._save_numbering_conn(conn, data)
            conn.commit()
            return dict(record)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def validate_ready(self, *, operation: str, model: str = "55") -> list[str]:
        config = self.load_config()
        if not config.get("enabled"):
            return ["O módulo fiscal não está habilitado."]
        model = str(model).strip()
        problems: list[str] = []
        if str(config.get("environment", "HOMOLOGACAO")).upper() == "PRODUCAO":
            problems.append(
                "Emissão em produção bloqueada nesta versão: configure e homologue "
                "IBS/CBS conforme as Notas Técnicas vigentes antes de liberar documentos reais."
            )
        if model not in self.VALID_MODELS:
            problems.append("Modelo fiscal deve ser 55 (NF-e) ou 65 (NFC-e).")
        elif model not in {str(item) for item in config.get("enabled_models", self.VALID_MODELS)}:
            problems.append(f"O modelo fiscal {model} não está habilitado para esta empresa.")
        if not self._is_valid_cnpj(config.get("cnpj")):
            problems.append("CNPJ do emitente não configurado.")
        state = str(config.get("state", "")).upper()
        if state not in self.STATE_CODES:
            problems.append("UF do emitente não configurada ou inválida.")
        elif state_profile(state)["status"] != "VALIDADO":
            problems.append(
                f"UF {state} preparada, mas ainda não homologada no NabiCode. "
                "Valide o perfil estadual antes de emitir documentos."
            )
        tax_regime = str(config.get("tax_regime", "")).upper()
        if tax_regime not in self.TAX_REGIME_CODES:
            problems.append("Regime tributário não configurado ou inválido.")
        certificate_path = str(config.get("certificate_path", "")).strip()
        if not certificate_path or not Path(certificate_path).is_file():
            problems.append("Certificado A1 não configurado ou arquivo inexistente.")
        endpoint = self.endpoint(operation, model=model)
        if not endpoint:
            problems.append(f"Endpoint SEFAZ não configurado para {operation}.")
        return problems

    def inspect_certificate(self, pfx_path: str | Path, password: str) -> FiscalCertificateInfo:
        self._require_dependency("cryptography")
        path = Path(pfx_path)
        if not path.is_file():
            raise ValueError("Arquivo do certificado A1 não encontrado.")
        key, cert, _chain = pkcs12.load_key_and_certificates(path.read_bytes(), str(password).encode("utf-8"))
        if key is None or cert is None:
            raise ValueError("O arquivo não contém chave privada e certificado válidos.")
        now = datetime.now(timezone.utc)
        valid_from = self._cert_datetime(cert, "not_valid_before_utc", "not_valid_before")
        valid_until = self._cert_datetime(cert, "not_valid_after_utc", "not_valid_after")
        subject = cert.subject.rfc4514_string()
        document = self._document_from_certificate(cert)
        return FiscalCertificateInfo(
            subject=subject,
            issuer=cert.issuer.rfc4514_string(),
            serial_number=f"{cert.serial_number:X}",
            valid_from=valid_from.isoformat(),
            valid_until=valid_until.isoformat(),
            document=document,
            expired=not (valid_from <= now <= valid_until),
        )

    def configure_certificate(self, pfx_path: str | Path, password: str) -> FiscalCertificateInfo:
        info = self.inspect_certificate(pfx_path, password)
        if info.expired:
            raise ValueError("O certificado A1 está expirado ou ainda não é válido.")
        config = self.load_config()
        configured_cnpj = self._normalize_cnpj(config.get("cnpj"))
        if configured_cnpj and info.document and configured_cnpj != info.document:
            raise ValueError("O CNPJ do certificado não corresponde ao emitente configurado.")
        config["certificate_path"] = str(Path(pfx_path).resolve())
        config["certificate_info"] = asdict(info)
        self._set_setting(self.CONFIG_KEY, json.dumps(config, ensure_ascii=False, sort_keys=True))
        return info

    def endpoint(self, operation: str, *, model: str | None = None) -> str:
        config = self.load_config()
        environment = str(config.get("environment", "HOMOLOGACAO")).upper()
        model = str(model or config.get("default_model") or "65")
        if model not in self.VALID_MODELS:
            raise ValueError("Modelo fiscal deve ser 55 ou 65 para selecionar o endpoint.")
        endpoints = (config.get("endpoints") or {}).get(environment, {})
        operation = str(operation)
        if operation == "recibo":
            custom = endpoints.get("recibo") or endpoints.get("consulta_recibo")
        else:
            custom = endpoints.get(operation)
        if custom:
            return self._validate_endpoint_url(str(custom).strip())
        state = str(config.get("state") or "").upper()
        if state not in self.STATE_CODES:
            return ""
        profile = state_profile(state)
        return str(
            profile.get("endpoints", {}).get(model, {}).get(environment, {}).get(operation, "")
        ).strip()

    @staticmethod
    def _validate_endpoint_url(value: str) -> str:
        url = str(value or "").strip()
        try:
            parsed = urlsplit(url)
            port = parsed.port
        except ValueError as exc:
            raise ValueError("Endpoint fiscal inválido.") from exc
        hostname = str(parsed.hostname or "").rstrip(".").casefold()
        if parsed.scheme.casefold() != "https":
            raise ValueError("Endpoint fiscal deve usar HTTPS.")
        if not hostname or parsed.username is not None or parsed.password is not None:
            raise ValueError("Endpoint fiscal não pode conter credenciais na URL.")
        if port not in {None, 443}:
            raise ValueError("Endpoint fiscal deve usar a porta HTTPS padrão 443.")
        if parsed.query or parsed.fragment:
            raise ValueError("Endpoint fiscal não pode conter consulta ou fragmento na URL.")
        if not (hostname.endswith(".gov.br") or hostname.endswith(".invalid")):
            raise ValueError("Endpoint fiscal deve pertencer a um domínio governamental oficial.")
        return url

    def sign_xml(self, xml: bytes | str, *, reference_id: str, pfx_path: str | Path, password: str) -> bytes:
        self._require_dependency("cryptography")
        self._require_dependency("lxml")
        key, cert, _chain = pkcs12.load_key_and_certificates(
            Path(pfx_path).read_bytes(), str(password).encode("utf-8")
        )
        if key is None or cert is None:
            raise ValueError("Certificado A1 inválido para assinatura.")
        parser = etree.XMLParser(remove_blank_text=True, resolve_entities=False, no_network=True)
        root = etree.fromstring(xml.encode("utf-8") if isinstance(xml, str) else xml, parser=parser)
        matches = root.xpath(f'//*[@Id="{reference_id}"]')
        if len(matches) != 1:
            raise ValueError("Elemento fiscal com Id informado não foi localizado de forma única.")
        target = matches[0]
        digest = hashes.Hash(hashes.SHA1())
        digest.update(etree.tostring(target, method="c14n", exclusive=False, with_comments=False))
        digest_value = base64.b64encode(digest.finalize()).decode("ascii")

        signature = etree.Element(etree.QName(self.DS_NS, "Signature"), nsmap={None: self.DS_NS})
        signed_info = etree.SubElement(signature, etree.QName(self.DS_NS, "SignedInfo"))
        etree.SubElement(signed_info, etree.QName(self.DS_NS, "CanonicalizationMethod"), Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315")
        etree.SubElement(signed_info, etree.QName(self.DS_NS, "SignatureMethod"), Algorithm="http://www.w3.org/2000/09/xmldsig#rsa-sha1")
        reference = etree.SubElement(signed_info, etree.QName(self.DS_NS, "Reference"), URI=f"#{reference_id}")
        transforms = etree.SubElement(reference, etree.QName(self.DS_NS, "Transforms"))
        etree.SubElement(transforms, etree.QName(self.DS_NS, "Transform"), Algorithm="http://www.w3.org/2000/09/xmldsig#enveloped-signature")
        etree.SubElement(transforms, etree.QName(self.DS_NS, "Transform"), Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315")
        etree.SubElement(reference, etree.QName(self.DS_NS, "DigestMethod"), Algorithm="http://www.w3.org/2000/09/xmldsig#sha1")
        etree.SubElement(reference, etree.QName(self.DS_NS, "DigestValue")).text = digest_value

        signed_info_c14n = etree.tostring(signed_info, method="c14n", exclusive=False, with_comments=False)
        signature_value = key.sign(signed_info_c14n, padding.PKCS1v15(), hashes.SHA1())
        etree.SubElement(signature, etree.QName(self.DS_NS, "SignatureValue")).text = base64.b64encode(signature_value).decode("ascii")
        key_info = etree.SubElement(signature, etree.QName(self.DS_NS, "KeyInfo"))
        x509_data = etree.SubElement(key_info, etree.QName(self.DS_NS, "X509Data"))
        etree.SubElement(x509_data, etree.QName(self.DS_NS, "X509Certificate")).text = base64.b64encode(cert.public_bytes(serialization.Encoding.DER)).decode("ascii")
        target.addnext(signature)
        return etree.tostring(root, xml_declaration=True, encoding="utf-8", standalone=False)

    def verify_xml_signature(self, xml: bytes | str) -> dict[str, Any]:
        """Valida a assinatura XMLDSig incorporada ao documento fiscal.

        A validação cobre a referência, o digest do elemento fiscal, o
        certificado embutido e a assinatura de ``SignedInfo``. Ela não
        substitui a validação da cadeia ICP-Brasil, que depende de uma cadeia
        de confiança atualizada no ambiente de implantação.
        """
        self._require_dependency("cryptography")
        self._require_dependency("lxml")
        raw = xml.encode("utf-8") if isinstance(xml, str) else bytes(xml)
        parser = etree.XMLParser(remove_blank_text=True, resolve_entities=False, no_network=True)
        root = etree.fromstring(raw, parser=parser)
        signatures = root.xpath("//*[local-name()='Signature' and namespace-uri()=$ns]", ns=self.DS_NS)
        if len(signatures) != 1:
            raise ValueError("XML fiscal deve possuir exatamente uma assinatura XMLDSig.")
        signature = signatures[0]
        references = signature.xpath("./*[local-name()='SignedInfo']/*[local-name()='Reference']")
        if len(references) != 1:
            raise ValueError("Assinatura fiscal deve possuir exatamente uma referência.")
        reference = references[0]
        uri = str(reference.get("URI") or "")
        if not uri.startswith("#") or len(uri) < 2:
            raise ValueError("Referência da assinatura fiscal é inválida.")
        reference_id = uri[1:]
        targets = root.xpath('//*[@Id=$reference_id]', reference_id=reference_id)
        if len(targets) != 1:
            raise ValueError("Elemento referenciado pela assinatura não foi localizado de forma única.")
        target = targets[0]
        digest_text = str(reference.xpath("string(./*[local-name()='DigestValue'])") or "").strip()
        if not digest_text:
            raise ValueError("Assinatura fiscal não contém DigestValue.")
        digest = hashes.Hash(hashes.SHA1())
        digest.update(etree.tostring(target, method="c14n", exclusive=False, with_comments=False))
        calculated_digest = base64.b64encode(digest.finalize()).decode("ascii")
        if calculated_digest != digest_text:
            raise ValueError("Digest da assinatura fiscal não corresponde ao conteúdo do XML.")

        certificate_text = str(signature.xpath("string(.//*[local-name()='X509Certificate'])") or "").strip()
        signature_text = str(signature.xpath("string(./*[local-name()='SignatureValue'])") or "").strip()
        signed_info_nodes = signature.xpath("./*[local-name()='SignedInfo']")
        if not certificate_text or not signature_text or len(signed_info_nodes) != 1:
            raise ValueError("Assinatura fiscal não contém certificado ou valor de assinatura válido.")
        try:
            cert = x509.load_der_x509_certificate(base64.b64decode(certificate_text, validate=True))
            signature_value = base64.b64decode(signature_text, validate=True)
        except Exception as exc:
            raise ValueError("Certificado ou assinatura XMLDSig possui codificação inválida.") from exc
        signed_info_c14n = etree.tostring(
            signed_info_nodes[0], method="c14n", exclusive=False, with_comments=False
        )
        try:
            cert.public_key().verify(signature_value, signed_info_c14n, padding.PKCS1v15(), hashes.SHA1())
        except Exception as exc:
            raise ValueError("Assinatura criptográfica do XML fiscal é inválida.") from exc
        valid_from = self._cert_datetime(cert, "not_valid_before_utc", "not_valid_before")
        valid_until = self._cert_datetime(cert, "not_valid_after_utc", "not_valid_after")
        return {
            "valid": True,
            "reference_id": reference_id,
            "certificate_subject": cert.subject.rfc4514_string(),
            "certificate_serial": f"{cert.serial_number:X}",
            "certificate_valid_from": valid_from.isoformat(),
            "certificate_valid_until": valid_until.isoformat(),
            "certificate_expired_now": not (valid_from <= datetime.now(timezone.utc) <= valid_until),
        }

    def validate_authorized_xml(self, xml: bytes | str, *, require_signature: bool = True) -> dict[str, Any]:
        """Valida chave, protocolo e assinatura de um XML autorizado importado."""
        raw = xml.encode("utf-8") if isinstance(xml, str) else bytes(xml)
        parser = etree.XMLParser(remove_blank_text=True, resolve_entities=False, no_network=True)
        root = etree.fromstring(raw, parser=parser)
        inf_nodes = root.xpath("//*[local-name()='NFe']/*[local-name()='infNFe']")
        protocol_nodes = root.xpath("//*[local-name()='protNFe']/*[local-name()='infProt']")
        if len(inf_nodes) != 1 or len(protocol_nodes) != 1:
            raise ValueError("XML autorizado deve conter uma NF-e e um protocolo completos.")
        inf = inf_nodes[0]
        protocol = protocol_nodes[0]
        identifier = str(inf.get("Id") or "")
        access_key = self._normalize_access_key(identifier[3:] if identifier.startswith("NFe") else identifier)
        protocol_key = self._normalize_access_key(protocol.xpath("string(./*[local-name()='chNFe'])"))
        protocol_number = str(protocol.xpath("string(./*[local-name()='nProt'])") or "").strip()
        status_code = str(protocol.xpath("string(./*[local-name()='cStat'])") or "").strip()
        model = str(inf.xpath("string(.//*[local-name()='ide']/*[local-name()='mod'])") or "").zfill(2)
        environment_code = str(protocol.xpath("string(./*[local-name()='tpAmb'])") or "").strip()
        environment = "PRODUCAO" if environment_code == "1" else "HOMOLOGACAO"
        if not self._is_valid_access_key(access_key):
            raise ValueError("Chave de acesso do XML autorizado é inválida.")
        if protocol_key != access_key:
            raise ValueError("O protocolo pertence a outra chave de acesso.")
        if status_code not in self.AUTHORIZED_STATUS or not protocol_number:
            raise ValueError("XML não possui autorização e protocolo válidos.")
        if model not in self.VALID_MODELS:
            raise ValueError("Modelo fiscal do XML autorizado é inválido.")
        signature = self.verify_xml_signature(raw) if require_signature else {"valid": False}
        if require_signature and signature.get("reference_id") != str(inf.get("Id") or ""):
            raise ValueError("A assinatura não referencia o infNFe autorizado.")
        return {
            "valid": True,
            "access_key": access_key,
            "protocol": protocol_number,
            "status_code": status_code,
            "model": model,
            "environment": environment,
            "signature": signature,
        }

    def import_authorized_xml(self, xml: bytes | str, *, actor: str, require_signature: bool = True) -> dict[str, Any]:
        """Importa um XML autorizado externo após validações de integridade fiscal."""
        raw = xml.encode("utf-8") if isinstance(xml, str) else bytes(xml)
        validation = self.validate_authorized_xml(raw, require_signature=require_signature)
        key = validation["access_key"]
        environment = validation["environment"]
        model = validation["model"]
        folder = self.storage_dir / environment.lower() / model / key
        folder.mkdir(parents=True, exist_ok=True)
        processed_path = folder / "processado_importado.xml"
        processed_path.write_bytes(raw)
        record = {
            "access_key": key,
            "model": model,
            "environment": environment,
            "status": "AUTORIZADO",
            "protocol": validation["protocol"],
            "response_access_key": key,
            "status_code": validation["status_code"],
            "message": "XML autorizado importado e validado.",
            "actor": str(actor or "Sistema"),
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source": "IMPORTADO",
            "request_path": "",
            "response_path": "",
            "processed_path": str(processed_path),
            "request_sha256": "",
            "response_sha256": "",
            "processed_sha256": hashlib.sha256(raw).hexdigest(),
            "signature": validation["signature"],
        }
        index = [
            row for row in self.list_documents()
            if row.get("access_key") != key or row.get("environment") != environment
        ]
        index.append(record)
        self._set_setting(self.DOCUMENT_INDEX_KEY, json.dumps(index, ensure_ascii=False, sort_keys=True))
        return record

    def transmit(
        self,
        *,
        operation: str,
        model: str | None = None,
        xml: bytes | str,
        pfx_path: str | Path,
        password: str,
        timeout: int = 45,
        headers: Mapping[str, str] | None = None,
    ) -> FiscalResponse:
        self._require_dependency("requests")
        self._require_dependency("cryptography")
        endpoint = self.endpoint(operation, model=model)
        if not endpoint:
            raise ValueError(f"Endpoint SEFAZ não configurado para {operation}.")
        if self.http_post is None:
            raise RuntimeError(
                "A dependência 'requests' não está instalada. Execute "
                "ATUALIZAR_DEPENDENCIAS.bat antes de usar a transmissão fiscal."
            )
        pem_cert, pem_key = self._temporary_pem_files(pfx_path, password)
        try:
            response = self.http_post(
                endpoint,
                data=xml.encode("utf-8") if isinstance(xml, str) else xml,
                headers={"Content-Type": "application/soap+xml; charset=utf-8", **dict(headers or {})},
                cert=(pem_cert, pem_key),
                timeout=int(timeout),
            )
            response.raise_for_status()
            return self.parse_response(response.content)
        except Exception as exc:
            if requests is not None and isinstance(exc, requests.RequestException):
                raise RuntimeError(f"Falha de comunicação com a SEFAZ: {exc}") from exc
            raise
        finally:
            for temp_path in (pem_cert, pem_key):
                self._secure_delete_file(temp_path)

    def parse_response(self, xml: bytes | str) -> FiscalResponse:
        self._require_dependency("lxml")
        raw = xml.decode("utf-8", errors="replace") if isinstance(xml, bytes) else str(xml)
        try:
            root = etree.fromstring(
                raw.encode("utf-8"),
                parser=etree.XMLParser(resolve_entities=False, no_network=True),
            )
        except etree.XMLSyntaxError as exc:
            raise ValueError("Resposta da SEFAZ não contém XML válido.") from exc

        def value(node: Any, name: str) -> str:
            return str(node.xpath(f"string(.//*[local-name()='{name}'][1])") or "").strip()

        # A SEFAZ normalmente devolve um status do lote e outro do documento/evento.
        # O status interno é o que define autorização, registro do evento ou rejeição.
        candidates = (
            root.xpath("//*[local-name()='protNFe']/*[local-name()='infProt'][1]"),
            root.xpath("//*[local-name()='retEvento']/*[local-name()='infEvento'][1]"),
            root.xpath("//*[local-name()='retInutNFe']/*[local-name()='infInut'][1]"),
            root.xpath("//*[local-name()='infProt'][1]"),
            root.xpath("//*[local-name()='infEvento'][1]"),
            root.xpath("//*[local-name()='infInut'][1]"),
        )
        detail = next((nodes[0] for nodes in candidates if nodes), root)
        status = value(detail, "cStat") or value(root, "cStat")
        protocol = value(detail, "nProt") or value(root, "nProt")
        message = value(detail, "xMotivo") or value(root, "xMotivo") or "Resposta recebida"
        receipt = value(root, "nRec")
        access_key = self._normalize_access_key(value(detail, "chNFe") or value(root, "chNFe"))

        # 128 apenas informa que o lote de eventos foi processado; sem um retorno
        # interno aceito ele não representa sucesso fiscal por si só.
        success = status in self.ACCEPTED_STATUS and (
            bool(protocol) or status in self.INUTILIZATION_ACCEPTED_STATUS
        )
        return FiscalResponse(success, status, message, protocol, receipt, access_key, raw)



    def validate_xml_schema(self, xml: bytes | str, xsd_path: str | Path) -> list[str]:
        """Valida um XML usando parser local, sem rede ou entidades externas."""
        self._require_dependency("lxml")
        path = Path(xsd_path)
        if not path.is_file():
            raise ValueError("Arquivo XSD não encontrado.")
        parser = etree.XMLParser(resolve_entities=False, no_network=True)
        try:
            schema_doc = etree.parse(str(path), parser)
            schema = etree.XMLSchema(schema_doc)
            document = etree.fromstring(xml.encode("utf-8") if isinstance(xml, str) else xml, parser)
        except (etree.XMLSyntaxError, etree.XMLSchemaParseError) as exc:
            raise ValueError(f"Schema ou XML inválido: {exc}") from exc
        if schema.validate(document):
            return []
        return [str(error) for error in schema.error_log]

    def official_schema_path(self, document_type: str) -> Path:
        paths = {
            "nfe": self.schema_dir / "nfe_010e_v1.02" / "nfe_v4.00.xsd",
            "evento": self.schema_dir / "eventos_010d_v1.03" / "envEvento_v1.00.xsd",
            "inutilizacao": self.schema_dir / "servicos_010d_v1.03" / "nabicode_inutNFe_v4.00.xsd",
            "consulta": self.schema_dir / "servicos_010d_v1.03" / "consSitNFe_v4.00.xsd",
        }
        kind = str(document_type or "").strip().casefold()
        if kind not in paths:
            raise ValueError("Tipo de schema fiscal oficial desconhecido.")
        path = paths[kind]
        if not path.is_file():
            raise RuntimeError(
                f"Schema fiscal oficial ausente: {path.name}. Repare a instalação do NabiCode."
            )
        return path

    def validate_official_xml(self, xml: bytes | str, *, document_type: str) -> None:
        errors = self.validate_xml_schema(xml, self.official_schema_path(document_type))
        if errors:
            summary = "; ".join(errors[:5])
            extra = len(errors) - 5
            if extra > 0:
                summary += f"; e mais {extra} erro(s)"
            raise ValueError(f"XML fiscal reprovado pelo schema oficial: {summary}")

    def validate_fiscal_profile(self, *, issuer: Mapping[str, Any], model: str) -> list[str]:
        problems: list[str] = []
        model = str(model).zfill(2)
        if model not in self.VALID_MODELS:
            problems.append("Modelo fiscal deve ser 55 ou 65.")
        cnpj = self._normalize_cnpj(issuer.get("cnpj"))
        if not self._is_valid_cnpj(cnpj):
            problems.append("CNPJ do emitente é inválido.")
        state = str(issuer.get("state", "")).upper()
        if state not in self.STATE_CODES:
            problems.append("UF do emitente é inválida.")
        regime_code = int(issuer.get("tax_regime_code", 0) or 0)
        if regime_code not in {1, 2, 3, 4}:
            problems.append("CRT do emitente deve ser 1, 2, 3 ou 4.")
        if len(self._digits(issuer.get("city_code"))) != 7:
            problems.append("Código IBGE do município do emitente deve possuir 7 dígitos.")
        if not self._digits(issuer.get("state_registration")):
            problems.append("Inscrição estadual do emitente é obrigatória para emissão fiscal.")
        return problems

    def register_rejection(self, *, operation: str, response: FiscalResponse, access_key: str = "", actor: str = "") -> dict[str, Any]:
        record = {
            "operation": str(operation).upper(),
            "access_key": self._normalize_access_key(access_key) or self._normalize_access_key(response.access_key),
            "status_code": response.status_code,
            "message": response.message,
            "protocol": response.protocol,
            "actor": str(actor or "Sistema"),
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        rows = self.list_rejections()
        rows.append(record)
        self._set_setting(self.REJECTION_INDEX_KEY, json.dumps(rows[-2000:], ensure_ascii=False, sort_keys=True))
        return record

    def list_rejections(self, *, operation: str = "", access_key: str = "") -> list[dict[str, Any]]:
        raw = self._get_setting(self.REJECTION_INDEX_KEY)
        try:
            rows = json.loads(raw) if raw else []
        except (TypeError, ValueError):
            rows = []
        result = [dict(row) for row in rows if isinstance(row, dict)]
        if operation:
            wanted = str(operation).upper()
            result = [row for row in result if row.get("operation") == wanted]
        if access_key:
            wanted_key = self._normalize_access_key(access_key)
            result = [row for row in result if row.get("access_key") == wanted_key]
        return result

    def merge_authorization_protocol(self, request_xml: bytes | str, response_xml: bytes | str) -> bytes:
        request_root = etree.fromstring(request_xml.encode() if isinstance(request_xml, str) else request_xml, parser=etree.XMLParser(resolve_entities=False, no_network=True))
        response_root = etree.fromstring(response_xml.encode() if isinstance(response_xml, str) else response_xml, parser=etree.XMLParser(resolve_entities=False, no_network=True))
        nfe_nodes = request_root.xpath("self::*[local-name()='NFe'] | .//*[local-name()='NFe'][1]")
        protocol_nodes = response_root.xpath("//*[local-name()='protNFe'][1]")
        if not nfe_nodes or not protocol_nodes:
            raise ValueError("XML de autorização não contém NF-e e protocolo completos.")
        request_key = self._normalize_access_key(str(nfe_nodes[0].xpath("string(.//*[local-name()='infNFe'][1]/@Id)") or "").replace("NFe", ""))
        protocol_key = self._normalize_access_key(str(protocol_nodes[0].xpath("string(.//*[local-name()='chNFe'][1])") or ""))
        if request_key and protocol_key and request_key != protocol_key:
            raise ValueError("O protocolo retornado pertence a outra chave de acesso.")
        ns = "http://www.portalfiscal.inf.br/nfe"
        proc = etree.Element(etree.QName(ns, "nfeProc"), nsmap={None: ns}, versao="4.00")
        proc.append(etree.fromstring(etree.tostring(nfe_nodes[0])))
        proc.append(etree.fromstring(etree.tostring(protocol_nodes[0])))
        return etree.tostring(proc, xml_declaration=True, encoding="utf-8")

    def store_document(
        self,
        *,
        access_key: str,
        model: str,
        environment: str,
        request_xml: bytes | str,
        response: FiscalResponse,
        actor: str,
    ) -> dict[str, Any]:
        key = self._normalize_access_key(access_key)
        if len(key) != 44:
            raise ValueError("Chave de acesso deve possuir 44 caracteres válidos.")
        model = str(model).strip()
        if model not in self.VALID_MODELS:
            raise ValueError("Modelo fiscal inválido.")
        environment = str(environment).strip().upper()
        if environment not in self.VALID_ENVIRONMENTS:
            raise ValueError("Ambiente fiscal inválido.")
        if response.access_key and response.access_key != key:
            raise ValueError("A resposta da SEFAZ pertence a outra chave de acesso.")
        authorized = response.status_code in self.AUTHORIZED_STATUS and bool(response.protocol)
        if response.status_code in self.AUTHORIZED_STATUS and not response.protocol:
            raise ValueError("Documento não pode ser autorizado sem protocolo válido.")
        status = "AUTORIZADO" if authorized else "REJEITADO"
        folder = self.storage_dir / environment.lower() / model / key
        folder.mkdir(parents=True, exist_ok=True)
        request_path = folder / "envio.xml"
        response_path = folder / "retorno.xml"
        processed_path = folder / "processado.xml"
        request_bytes = request_xml.encode("utf-8") if isinstance(request_xml, str) else bytes(request_xml)
        response_bytes = response.raw_xml.encode("utf-8")
        processed_bytes: bytes | None = None
        if authorized:
            # Um documento autorizado só pode ser indexado depois que o XML
            # processado (NFe + protNFe) for construído e validado. Engolir a
            # falha aqui criava um registro AUTORIZADO sem arquivo fiscal legal.
            processed_bytes = self.merge_authorization_protocol(request_bytes, response_bytes)

        written_paths: list[Path] = []
        try:
            self._atomic_write_bytes(request_path, request_bytes)
            written_paths.append(request_path)
            self._atomic_write_bytes(response_path, response_bytes)
            written_paths.append(response_path)
            if processed_bytes is not None:
                self._atomic_write_bytes(processed_path, processed_bytes)
                written_paths.append(processed_path)
        except Exception:
            for written_path in reversed(written_paths):
                try:
                    written_path.unlink(missing_ok=True)
                except OSError:
                    pass
            raise

        processed_value = str(processed_path) if processed_bytes is not None else ""
        processed_hash = hashlib.sha256(processed_bytes).hexdigest() if processed_bytes is not None else ""
        record = {
            "access_key": key,
            "model": model,
            "environment": environment,
            "status": status,
            "protocol": response.protocol,
            "response_access_key": response.access_key,
            "status_code": response.status_code,
            "message": response.message,
            "actor": str(actor or "Sistema"),
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "request_path": str(request_path),
            "response_path": str(response_path),
            "processed_path": processed_value,
            "request_sha256": hashlib.sha256(request_bytes).hexdigest(),
            "response_sha256": hashlib.sha256(response_bytes).hexdigest(),
            "processed_sha256": processed_hash,
        }
        index = self.list_documents()
        index = [row for row in index if row.get("access_key") != key or row.get("environment") != environment]
        index.append(record)
        self._set_setting(self.DOCUMENT_INDEX_KEY, json.dumps(index, ensure_ascii=False, sort_keys=True))
        if not authorized:
            self.register_rejection(operation="AUTORIZACAO", response=response, access_key=key, actor=actor)
        return record


    def verify_document_integrity(self, *, access_key: str, environment: str = "") -> dict[str, Any]:
        key = self._normalize_access_key(access_key)
        if len(key) != 44:
            raise ValueError("Chave de acesso deve possuir 44 caracteres válidos.")
        wanted_environment = str(environment or "").strip().upper()
        records = [
            row for row in self.list_documents()
            if row.get("access_key") == key
            and (not wanted_environment or row.get("environment") == wanted_environment)
        ]
        if not records:
            raise ValueError("Documento fiscal não encontrado no índice.")
        record = records[-1]
        checks: dict[str, Any] = {}
        ok = True
        for name in ("request", "response", "processed"):
            path_value = str(record.get(f"{name}_path") or "").strip()
            expected = str(record.get(f"{name}_sha256") or "").strip().lower()
            if not path_value:
                checks[name] = {"exists": False, "expected": expected, "actual": "", "valid": not expected}
                ok = ok and not expected
                continue
            path = Path(path_value)
            exists = path.is_file()
            actual = hashlib.sha256(path.read_bytes()).hexdigest() if exists else ""
            valid = exists and bool(expected) and actual == expected
            checks[name] = {"exists": exists, "expected": expected, "actual": actual, "valid": valid}
            ok = ok and valid
        return {"access_key": key, "environment": record.get("environment"), "valid": ok, "checks": checks}

    def export_accounting_package(
        self, *, start_date: str | datetime, end_date: str | datetime,
        output_path: str | Path, include_homologation: bool = False,
    ) -> dict[str, Any]:
        """Exporta XMLs autorizados e eventos aceitos para a contabilidade."""
        def as_date(value: str | datetime):
            return value.date() if isinstance(value, datetime) else datetime.fromisoformat(str(value).strip()).date()

        start, end = as_date(start_date), as_date(end_date)
        if start > end:
            raise ValueError("A data inicial não pode ser posterior à data final.")
        destination = Path(output_path)
        if destination.suffix.lower() != ".zip":
            destination = destination.with_suffix(".zip")
        destination.parent.mkdir(parents=True, exist_ok=True)
        documents: list[dict[str, Any]] = []
        for row in self.list_documents():
            if str(row.get("status") or "").upper() != "AUTORIZADO":
                continue
            environment = str(row.get("environment") or "").upper()
            if environment != "PRODUCAO" and not include_homologation:
                continue
            try:
                created = datetime.fromisoformat(str(row.get("created_at") or "")).date()
            except ValueError:
                continue
            if not start <= created <= end:
                continue
            integrity = self.verify_document_integrity(
                access_key=str(row.get("access_key") or ""), environment=environment,
            )
            if not integrity["valid"] or not str(row.get("processed_path") or ""):
                raise ValueError(f"XML fiscal {row.get('access_key', '')} falhou na verificação de integridade.")
            documents.append(dict(row))

        document_environment = {
            str(row.get("access_key") or ""): str(row.get("environment") or "").upper()
            for row in self.list_documents()
            if str(row.get("status") or "").upper() == "AUTORIZADO"
        }
        events: list[dict[str, Any]] = []
        for row in self.list_events():
            key = str(row.get("access_key") or "")
            environment = str(row.get("environment") or document_environment.get(key, "")).upper()
            if str(row.get("status_code") or "") not in self.EVENT_ACCEPTED_STATUS:
                continue
            if environment != "PRODUCAO" and not include_homologation:
                continue
            try:
                created = datetime.fromisoformat(str(row.get("created_at") or "")).date()
            except ValueError:
                continue
            if start <= created <= end:
                events.append(dict(row))
        manifest: dict[str, Any] = {
            "product": "NabiCode", "purpose": "Pacote fiscal para contabilidade",
            "period": {"start": start.isoformat(), "end": end.isoformat()},
            "includes_homologation": bool(include_homologation),
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "documents": [], "events": [],
        }
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                prefix=f".{destination.stem}_", suffix=".tmp", dir=destination.parent, delete=False
            ) as temporary:
                temp_path = Path(temporary.name)
            with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for row in documents:
                    key, model = str(row["access_key"]), str(row["model"])
                    label = "NFCe" if model == "65" else "NFe"
                    name = f"{str(row['environment']).lower()}/{label}/{label}{key}.xml"
                    data = Path(str(row["processed_path"])).read_bytes()
                    archive.writestr(name, data)
                    manifest["documents"].append({
                        "access_key": key, "model": model, "environment": row["environment"],
                        "protocol": row.get("protocol", ""), "created_at": row.get("created_at", ""),
                        "file": name, "sha256": hashlib.sha256(data).hexdigest(),
                    })
                for index, row in enumerate(events, 1):
                    key = str(row["access_key"])
                    kind = str(row.get("event_type") or "EVENTO").upper()
                    base = f"eventos/{key}/{index:03d}_{kind}"
                    exported: list[str] = []
                    for suffix, field in (("envio", "request_path"), ("retorno", "response_path")):
                        path = Path(str(row.get(field) or ""))
                        if path.is_file():
                            data = path.read_bytes()
                            expected = str(row.get(f"{suffix.replace('envio', 'request').replace('retorno', 'response')}_sha256") or "").lower()
                            if not expected or hashlib.sha256(data).hexdigest() != expected:
                                raise ValueError(f"Evento fiscal {kind} da chave {key} falhou na verificação de integridade.")
                            name = f"{base}_{suffix}.xml"
                            archive.writestr(name, data)
                            exported.append(name)
                    manifest["events"].append({
                        "access_key": key, "type": kind, "protocol": row.get("protocol", ""),
                        "status_code": row.get("status_code", ""), "created_at": row.get("created_at", ""),
                        "files": exported,
                    })
                archive.writestr("manifesto.json", json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
            os.replace(temp_path, destination)
            temp_path = None
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
        return {
            "path": str(destination), "documents": len(documents), "events": len(events),
            "period_start": start.isoformat(), "period_end": end.isoformat(),
        }

    def list_documents(self) -> list[dict[str, Any]]:
        value = self._get_setting(self.DOCUMENT_INDEX_KEY)
        if not value:
            return []
        try:
            rows = json.loads(value)
        except (TypeError, ValueError):
            return []
        return [dict(row) for row in rows if isinstance(row, dict)]


    @staticmethod
    def calculate_access_key_digit(base43: str) -> str:
        normalized = FiscalService._normalize_access_key(base43)
        if len(normalized) != 43 or not re.fullmatch(r"[0-9]{6}[A-Z0-9]{12}[0-9]{25}", normalized):
            raise ValueError("A base da chave de acesso possui formato inválido.")
        weights = [2, 3, 4, 5, 6, 7, 8, 9]
        total = sum((ord(ch) - 48) * weights[i % len(weights)] for i, ch in enumerate(reversed(normalized)))
        remainder = total % 11
        digit = 11 - remainder
        return "0" if digit in (10, 11) else str(digit)

    def build_access_key(
        self, *, state_code: str, issued_at: datetime, cnpj: str, model: str,
        series: int, number: int, emission_type: int = 1, numeric_code: str | int = "00000000"
    ) -> str:
        model = str(model).zfill(2)
        if model not in self.VALID_MODELS:
            raise ValueError("Modelo fiscal inválido.")
        normalized_cnpj = self._normalize_cnpj(cnpj)
        if not self._is_valid_cnpj(normalized_cnpj):
            raise ValueError("CNPJ inválido para gerar a chave de acesso.")
        state = self._digits(state_code).zfill(2)
        if len(state) != 2:
            raise ValueError("Código numérico da UF inválido.")
        code = self._digits(numeric_code).zfill(8)[-8:]
        base = (
            f"{state}{issued_at:%y%m}{normalized_cnpj}{model}{int(series):03d}"
            f"{int(number):09d}{int(emission_type)}{code}"
        )
        return base + self.calculate_access_key_digit(base)


    def validate_document_rules(
        self, *, issuer: Mapping[str, Any], recipient: Mapping[str, Any],
        items: Sequence[Mapping[str, Any]], document: Mapping[str, Any]
    ) -> list[str]:
        problems: list[str] = []
        model = str(document.get("model", "55")).zfill(2)
        crt = int(issuer.get("tax_regime_code", self.TAX_REGIME_CODES.get(str(issuer.get("tax_regime", "SIMPLES")).upper(), 1)))
        if model not in self.VALID_MODELS:
            problems.append("Modelo fiscal deve ser 55 ou 65.")
        if crt not in {1, 2, 3, 4}:
            problems.append("CRT do emitente deve ser 1, 2, 3 ou 4.")
        state = str(issuer.get("state", "")).strip().upper()
        expected_state_code = self.STATE_CODES.get(state, "")
        informed_state_code = self._digits(document.get("state_code"))
        if expected_state_code and informed_state_code and expected_state_code != informed_state_code.zfill(2):
            problems.append("Código da UF do documento não corresponde à UF do emitente.")
        operation_type = int(document.get("operation_type", 1))
        destination = int(document.get("destination", 1))
        if operation_type not in {0, 1}:
            problems.append("Tipo de operação deve ser 0 (entrada) ou 1 (saída).")
        if destination not in {1, 2, 3}:
            problems.append("Destino da operação deve ser 1, 2 ou 3.")
        if model == "65":
            if int(document.get("final_consumer", 1)) != 1:
                problems.append("NFC-e exige consumidor final.")
            if int(document.get("presence", 1)) not in {1, 2, 3, 4, 5, 9}:
                problems.append("Indicador de presença inválido para NFC-e.")
            if operation_type != 1:
                problems.append("NFC-e somente pode representar operação de saída.")
        recipient_document = self._normalize_tax_document(recipient.get("document"))
        if recipient_document and len(recipient_document) not in {11, 14}:
            problems.append("Documento do destinatário deve ser CPF ou CNPJ válido em tamanho.")
        for index, item in enumerate(items, 1):
            prefix = f"Item {index}"
            if not str(item.get("code", "")).strip():
                problems.append(f"{prefix}: código é obrigatório.")
            if not str(item.get("description", "")).strip():
                problems.append(f"{prefix}: descrição é obrigatória.")
            ncm = self._digits(item.get("ncm"))
            if len(ncm) != 8 or ncm == "00000000":
                problems.append(f"{prefix}: NCM deve possuir 8 dígitos e não pode ser genérico.")
            cfop = self._digits(item.get("cfop"))
            if len(cfop) != 4 or cfop[0] not in "123567":
                problems.append(f"{prefix}: CFOP inválido.")
            if operation_type == 1 and cfop and cfop[0] not in "567":
                problems.append(f"{prefix}: CFOP de saída deve iniciar por 5, 6 ou 7.")
            if operation_type == 0 and cfop and cfop[0] not in "123":
                problems.append(f"{prefix}: CFOP de entrada deve iniciar por 1, 2 ou 3.")
            if not str(item.get("unit", "")).strip():
                problems.append(f"{prefix}: unidade é obrigatória.")
            try:
                quantity = Decimal(str(item.get("quantity", 0)))
                unit_price = Decimal(str(item.get("unit_price", 0)))
            except Exception:
                problems.append(f"{prefix}: quantidade ou preço não é numérico.")
                continue
            if quantity <= 0:
                problems.append(f"{prefix}: quantidade deve ser maior que zero.")
            if unit_price < 0:
                problems.append(f"{prefix}: preço não pode ser negativo.")
            if crt in {1, 2}:
                csosn = self._digits(item.get("csosn") or "102")
                if len(csosn) != 3:
                    problems.append(f"{prefix}: CSOSN deve possuir 3 dígitos.")
            else:
                cst = self._digits(item.get("cst"))
                if cst not in {"00", "40", "41", "50"}:
                    problems.append(f"{prefix}: CST suportado deve ser 00, 40, 41 ou 50.")
                if cst == "00":
                    try:
                        rate = Decimal(str(item.get("icms_rate", "0")))
                    except Exception:
                        rate = Decimal("-1")
                    if rate < 0 or rate > 100:
                        problems.append(f"{prefix}: alíquota de ICMS inválida.")
        purpose = int(document.get("purpose", 1) or 1)
        referenced = [self._normalize_access_key(value) for value in document.get("referenced_access_keys", []) or []]
        if purpose == 4:
            if model != "55":
                problems.append("NF-e de devolução deve utilizar o modelo 55.")
            if not referenced:
                problems.append("NF-e de devolução deve referenciar a chave da nota original.")
        for key in referenced:
            if len(key) != 44:
                problems.append("Chave de NF-e referenciada deve possuir 44 dígitos.")
        payment_code = self._digits(document.get("payment_code", "01")).zfill(2)
        if len(payment_code) != 2:
            problems.append("Código de pagamento inválido.")
        return problems

    def build_document_xml(
        self, *, issuer: Mapping[str, Any], recipient: Mapping[str, Any],
        items: Sequence[Mapping[str, Any]], document: Mapping[str, Any]
    ) -> tuple[bytes, str]:
        """Gera um rascunho XML NF-e/NFC-e sem transmitir.

        A validação oficial depende dos XSD e regras vigentes da SEFAZ; este método
        produz a estrutura de trabalho e nunca marca o documento como autorizado.
        """
        model = str(document.get("model", "55")).zfill(2)
        if model not in self.VALID_MODELS:
            raise ValueError("Modelo fiscal deve ser 55 ou 65.")
        if not items:
            raise ValueError("Documento fiscal precisa possuir ao menos um item.")
        profile_problems = self.validate_fiscal_profile(issuer=issuer, model=model)
        rule_problems = self.validate_document_rules(issuer=issuer, recipient=recipient, items=items, document=document)
        problems = profile_problems + rule_problems
        if problems:
            raise ValueError("; ".join(problems))
        cnpj = self._normalize_cnpj(issuer.get("cnpj"))
        issued_at = document.get("issued_at") or datetime.now().astimezone()
        if not isinstance(issued_at, datetime):
            issued_at = datetime.fromisoformat(str(issued_at))
        key = str(document.get("access_key") or "")
        if not key:
            key = self.build_access_key(
                state_code=str(document.get("state_code", "29")), issued_at=issued_at, cnpj=cnpj,
                model=model, series=int(document.get("series", 1)), number=int(document.get("number", 1)),
                emission_type=int(document.get("emission_type", 1)), numeric_code=document.get("numeric_code", "00000000")
            )
        if len(self._normalize_access_key(key)) != 44:
            raise ValueError("Chave de acesso inválida.")
        ns = "http://www.portalfiscal.inf.br/nfe"
        root = etree.Element(etree.QName(ns, "NFe"), nsmap={None: ns})
        inf = etree.SubElement(root, etree.QName(ns, "infNFe"), Id=f"NFe{key}", versao="4.00")
        ide = etree.SubElement(inf, etree.QName(ns, "ide"))
        def el(parent, name, value):
            node = etree.SubElement(parent, etree.QName(ns, name)); node.text = str(value); return node
        el(ide, "cUF", str(document.get("state_code", "29")).zfill(2))
        el(ide, "cNF", self._digits(document.get("numeric_code", key[35:43])).zfill(8)[-8:])
        el(ide, "natOp", document.get("nature", "VENDA"))
        el(ide, "mod", model); el(ide, "serie", int(document.get("series", 1)))
        el(ide, "nNF", int(document.get("number", 1)))
        el(ide, "dhEmi", issued_at.astimezone().isoformat(timespec="seconds"))
        el(ide, "tpNF", int(document.get("operation_type", 1)))
        el(ide, "idDest", int(document.get("destination", 1)))
        el(ide, "cMunFG", self._digits(issuer.get("city_code")))
        el(ide, "tpImp", 4 if model == "65" else 1)
        el(ide, "tpEmis", int(document.get("emission_type", 1)))
        el(ide, "cDV", key[-1]); el(ide, "tpAmb", 2 if str(document.get("environment", "HOMOLOGACAO")).upper()=="HOMOLOGACAO" else 1)
        el(ide, "finNFe", int(document.get("purpose", 1))); el(ide, "indFinal", int(document.get("final_consumer", 1)))
        el(ide, "indPres", int(document.get("presence", 1))); el(ide, "procEmi", 0); el(ide, "verProc", document.get("app_version", "NabiCode"))
        for referenced_key in document.get("referenced_access_keys", []) or []:
            digits = self._normalize_access_key(referenced_key)
            if len(digits) != 44:
                raise ValueError("Chave de NF-e referenciada deve possuir 44 dígitos.")
            nfref = etree.SubElement(ide, etree.QName(ns, "NFref"))
            el(nfref, "refNFe", digits)
        emit = etree.SubElement(inf, etree.QName(ns, "emit")); el(emit, "CNPJ", cnpj); el(emit, "xNome", issuer.get("name", ""))
        ender = etree.SubElement(emit, etree.QName(ns, "enderEmit"))
        for name, key_name in (("xLgr","street"),("nro","number"),("xBairro","district"),("cMun","city_code"),("xMun","city"),("UF","state"),("CEP","zip_code")):
            value=issuer.get(key_name);
            if value not in (None, ""): el(ender, name, self._digits(value) if name in {"cMun","CEP"} else value)
        el(emit, "IE", self._digits(issuer.get("state_registration"))); el(emit, "CRT", int(issuer.get("tax_regime_code", 1)))
        dest = etree.SubElement(inf, etree.QName(ns, "dest"))
        doc_rec = self._normalize_tax_document(recipient.get("document"))
        if len(doc_rec)==14: el(dest, "CNPJ", doc_rec)
        elif len(doc_rec)==11: el(dest, "CPF", doc_rec)
        if recipient.get("name"): el(dest, "xNome", recipient.get("name"))
        recipient_ie = self._digits(recipient.get("state_registration"))
        taxpayer_indicator = recipient.get("state_taxpayer_indicator")
        if taxpayer_indicator in (None, ""):
            taxpayer_indicator = 1 if recipient_ie else 2 if recipient.get("icms_exempt") else 9
        taxpayer_indicator = int(taxpayer_indicator)
        if taxpayer_indicator not in {1, 2, 9}:
            raise ValueError("Indicador de inscrição estadual do destinatário deve ser 1, 2 ou 9.")
        if taxpayer_indicator == 1 and not recipient_ie:
            raise ValueError("Destinatário contribuinte de ICMS exige inscrição estadual.")
        el(dest, "indIEDest", taxpayer_indicator)
        if recipient_ie:
            el(dest, "IE", recipient_ie)
        total_products = Decimal("0")
        total_icms_base = Decimal("0")
        total_icms = Decimal("0")
        total_pis = Decimal("0")
        total_cofins = Decimal("0")
        total_ipi_return = Decimal("0")
        total_ibs_cbs_base = Decimal("0")
        total_ibs_uf = Decimal("0")
        total_ibs_city = Decimal("0")
        total_cbs = Decimal("0")
        for index, item in enumerate(items, 1):
            qty=Decimal(str(item.get("quantity", 0))); unit=Decimal(str(item.get("unit_price", 0)))
            if qty <= 0 or unit < 0: raise ValueError(f"Item {index}: quantidade/preço inválidos.")
            value=(qty*unit).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP); total_products += value
            det=etree.SubElement(inf, etree.QName(ns,"det"), nItem=str(index)); prod=etree.SubElement(det, etree.QName(ns,"prod"))
            el(prod,"cProd",item.get("code",index)); el(prod,"cEAN",item.get("ean") or "SEM GTIN"); el(prod,"xProd",str(item.get("description","")).upper())
            el(prod,"NCM",self._digits(item.get("ncm")) or "00000000"); el(prod,"CFOP",item.get("cfop") or "5102"); el(prod,"uCom",str(item.get("unit","UN")).upper())
            el(prod,"qCom",f"{qty:.4f}"); el(prod,"vUnCom",f"{unit:.10f}"); el(prod,"vProd",f"{value:.2f}"); el(prod,"cEANTrib",item.get("ean") or "SEM GTIN")
            el(prod,"uTrib",str(item.get("unit","UN")).upper()); el(prod,"qTrib",f"{qty:.4f}"); el(prod,"vUnTrib",f"{unit:.10f}"); el(prod,"indTot",1)
            imposto=etree.SubElement(det, etree.QName(ns,"imposto")); icms=etree.SubElement(imposto, etree.QName(ns,"ICMS"))
            crt = int(issuer.get("tax_regime_code", 1))
            explicit_icms_base = Decimal(str(item.get("icms_base", 0))).quantize(Decimal("0.01"))
            explicit_icms_value = Decimal(str(item.get("icms_value", 0))).quantize(Decimal("0.01"))
            if crt in {1, 2}:
                icmssn=etree.SubElement(icms, etree.QName(ns,"ICMSSN102")); el(icmssn,"orig",int(item.get("origin",0))); el(icmssn,"CSOSN",self._digits(item.get("csosn") or "102"))
            else:
                cst = self._digits(item.get("cst"))
                if cst == "00":
                    rate = Decimal(str(item.get("icms_rate", "0"))).quantize(Decimal("0.01"))
                    tax_base = explicit_icms_base if explicit_icms_base > 0 else value
                    tax_value = explicit_icms_value if explicit_icms_value > 0 else (tax_base * rate / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    total_icms_base += tax_base; total_icms += tax_value
                    icms00=etree.SubElement(icms, etree.QName(ns,"ICMS00")); el(icms00,"orig",int(item.get("origin",0))); el(icms00,"CST","00")
                    el(icms00,"modBC",int(item.get("bc_mode",3))); el(icms00,"vBC",f"{tax_base:.2f}"); el(icms00,"pICMS",f"{rate:.2f}"); el(icms00,"vICMS",f"{tax_value:.2f}")
                else:
                    icms40=etree.SubElement(icms, etree.QName(ns,"ICMS40")); el(icms40,"orig",int(item.get("origin",0))); el(icms40,"CST",cst)

            pis_value = Decimal(str(item.get("pis_value", 0))).quantize(Decimal("0.01"))
            pis_base = Decimal(str(item.get("pis_base", 0))).quantize(Decimal("0.01"))
            pis_rate = Decimal(str(item.get("pis_rate", 0))).quantize(Decimal("0.01"))
            pis=etree.SubElement(imposto, etree.QName(ns,"PIS"))
            if pis_value > 0 or pis_base > 0 or pis_rate > 0:
                pis_out=etree.SubElement(pis, etree.QName(ns,"PISOutr")); el(pis_out,"CST",self._digits(item.get("pis_cst") or "49"))
                el(pis_out,"vBC",f"{pis_base:.2f}"); el(pis_out,"pPIS",f"{pis_rate:.2f}"); el(pis_out,"vPIS",f"{pis_value:.2f}")
                total_pis += pis_value
            else:
                pisnt=etree.SubElement(pis, etree.QName(ns,"PISNT")); el(pisnt,"CST","07")

            cofins_value = Decimal(str(item.get("cofins_value", 0))).quantize(Decimal("0.01"))
            cofins_base = Decimal(str(item.get("cofins_base", 0))).quantize(Decimal("0.01"))
            cofins_rate = Decimal(str(item.get("cofins_rate", 0))).quantize(Decimal("0.01"))
            cof=etree.SubElement(imposto, etree.QName(ns,"COFINS"))
            if cofins_value > 0 or cofins_base > 0 or cofins_rate > 0:
                cof_out=etree.SubElement(cof, etree.QName(ns,"COFINSOutr")); el(cof_out,"CST",self._digits(item.get("cofins_cst") or "49"))
                el(cof_out,"vBC",f"{cofins_base:.2f}"); el(cof_out,"pCOFINS",f"{cofins_rate:.2f}"); el(cof_out,"vCOFINS",f"{cofins_value:.2f}")
                total_cofins += cofins_value
            else:
                cofnt=etree.SubElement(cof, etree.QName(ns,"COFINSNT")); el(cofnt,"CST","07")

            rtc_cst = self._digits(item.get("ibs_cbs_cst"))
            if rtc_cst:
                rtc_class = self._digits(item.get("ibs_cbs_class"))
                if rtc_cst != "000" or len(rtc_class) != 6:
                    raise ValueError(
                        f"Item {index}: esta etapa suporta CST IBS/CBS 000 com classificação de 6 dígitos."
                    )
                rtc_base = Decimal(str(item.get("ibs_cbs_base", value))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                ibs_uf_rate = Decimal(str(item.get("ibs_uf_rate", 0))).quantize(Decimal("0.0001"))
                ibs_city_rate = Decimal(str(item.get("ibs_city_rate", 0))).quantize(Decimal("0.0001"))
                cbs_rate = Decimal(str(item.get("cbs_rate", 0))).quantize(Decimal("0.0001"))
                if rtc_base < 0 or any(rate < 0 or rate > 100 for rate in (ibs_uf_rate, ibs_city_rate, cbs_rate)):
                    raise ValueError(f"Item {index}: base ou alíquota IBS/CBS inválida.")
                ibs_uf_value = (rtc_base * ibs_uf_rate / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                ibs_city_value = (rtc_base * ibs_city_rate / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                cbs_value = (rtc_base * cbs_rate / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                rtc = etree.SubElement(imposto, etree.QName(ns, "IBSCBS"))
                el(rtc, "CST", rtc_cst); el(rtc, "cClassTrib", rtc_class)
                group = etree.SubElement(rtc, etree.QName(ns, "gIBSCBS")); el(group, "vBC", f"{rtc_base:.2f}")
                ibs_uf = etree.SubElement(group, etree.QName(ns, "gIBSUF")); el(ibs_uf, "pIBSUF", f"{ibs_uf_rate:.4f}"); el(ibs_uf, "vIBSUF", f"{ibs_uf_value:.2f}")
                ibs_city = etree.SubElement(group, etree.QName(ns, "gIBSMun")); el(ibs_city, "pIBSMun", f"{ibs_city_rate:.4f}"); el(ibs_city, "vIBSMun", f"{ibs_city_value:.2f}")
                el(group, "vIBS", f"{ibs_uf_value + ibs_city_value:.2f}")
                cbs = etree.SubElement(group, etree.QName(ns, "gCBS")); el(cbs, "pCBS", f"{cbs_rate:.4f}"); el(cbs, "vCBS", f"{cbs_value:.2f}")
                total_ibs_cbs_base += rtc_base
                total_ibs_uf += ibs_uf_value
                total_ibs_city += ibs_city_value
                total_cbs += cbs_value

            ipi_return = Decimal(str(item.get("ipi_return_value", 0))).quantize(Decimal("0.01"))
            if ipi_return > 0:
                percent = Decimal(str(item.get("devolution_percent", 100))).quantize(Decimal("0.01"))
                imposto_devol = etree.SubElement(det, etree.QName(ns,"impostoDevol"))
                el(imposto_devol,"pDevol",f"{percent:.2f}")
                ipi = etree.SubElement(imposto_devol, etree.QName(ns,"IPI")); el(ipi,"vIPIDevol",f"{ipi_return:.2f}")
                total_ipi_return += ipi_return

        total=etree.SubElement(inf, etree.QName(ns,"total")); icmstot=etree.SubElement(total, etree.QName(ns,"ICMSTot"))
        total_nf = total_products + total_ipi_return
        for name,val in (("vBC",total_icms_base),("vICMS",total_icms),("vICMSDeson",0),("vFCP",0),("vBCST",0),("vST",0),("vFCPST",0),("vFCPSTRet",0),("vProd",total_products),("vFrete",0),("vSeg",0),("vDesc",0),("vII",0),("vIPI",0),("vIPIDevol",total_ipi_return),("vPIS",total_pis),("vCOFINS",total_cofins),("vOutro",0),("vNF",total_nf)):
            el(icmstot,name,f"{Decimal(str(val)):.2f}")
        total_with_rtc = total_nf
        if total_ibs_cbs_base > 0:
            rtc_tot = etree.SubElement(total, etree.QName(ns, "IBSCBSTot")); el(rtc_tot, "vBCIBSCBS", f"{total_ibs_cbs_base:.2f}")
            ibs_tot = etree.SubElement(rtc_tot, etree.QName(ns, "gIBS"))
            ibs_uf_tot = etree.SubElement(ibs_tot, etree.QName(ns, "gIBSUF")); el(ibs_uf_tot, "vDif", "0.00"); el(ibs_uf_tot, "vDevTrib", "0.00"); el(ibs_uf_tot, "vIBSUF", f"{total_ibs_uf:.2f}")
            ibs_city_tot = etree.SubElement(ibs_tot, etree.QName(ns, "gIBSMun")); el(ibs_city_tot, "vDif", "0.00"); el(ibs_city_tot, "vDevTrib", "0.00"); el(ibs_city_tot, "vIBSMun", f"{total_ibs_city:.2f}")
            el(ibs_tot, "vIBS", f"{total_ibs_uf + total_ibs_city:.2f}")
            el(ibs_tot, "vCredPres", "0.00"); el(ibs_tot, "vCredPresCondSus", "0.00")
            cbs_tot = etree.SubElement(rtc_tot, etree.QName(ns, "gCBS")); el(cbs_tot, "vDif", "0.00"); el(cbs_tot, "vDevTrib", "0.00"); el(cbs_tot, "vCBS", f"{total_cbs:.2f}")
            el(cbs_tot, "vCredPres", "0.00"); el(cbs_tot, "vCredPresCondSus", "0.00")
            total_with_rtc += total_ibs_uf + total_ibs_city + total_cbs
            el(total, "vNFTot", f"{total_with_rtc:.2f}")
        transp=etree.SubElement(inf, etree.QName(ns,"transp")); el(transp,"modFrete",9)
        pag=etree.SubElement(inf, etree.QName(ns,"pag")); detpag=etree.SubElement(pag, etree.QName(ns,"detPag")); el(detpag,"tPag",document.get("payment_code","01")); el(detpag,"vPag",f"{total_with_rtc:.2f}")
        if document.get("additional_info"):
            infad=etree.SubElement(inf, etree.QName(ns,"infAdic")); el(infad,"infCpl",document.get("additional_info"))
        if model == "65" and int(document.get("emission_type", 1)) == 1:
            self._set_nfce_supplement(
                root,
                qr_code=self.build_nfce_qr_code_v3(
                    access_key=key,
                    environment=str(document.get("environment", "HOMOLOGACAO")),
                ),
                environment=str(document.get("environment", "HOMOLOGACAO")),
            )
        return etree.tostring(root, xml_declaration=True, encoding="utf-8"), key

    def prepare_sale_items(
        self, cart_items: Sequence[Mapping[str, Any]], *, destination: int = 1,
        require_rtc: bool = True,
    ) -> list[dict[str, Any]]:
        """Transforma o carrinho em itens fiscais usando uma única ficha por produto."""
        if destination not in {1, 2, 3}:
            raise ValueError("Destino fiscal da venda deve ser interno, interestadual ou exterior.")
        product_ids = [int(item.get("produto_id") or 0) for item in cart_items]
        if not product_ids or any(product_id <= 0 for product_id in product_ids):
            raise ValueError("Venda fiscal exige que todos os itens estejam cadastrados.")
        unique_ids = sorted(set(product_ids))
        placeholders = ",".join("?" for _ in unique_ids)
        conn = self.connection_factory()
        try:
            cursor = conn.execute(
                f"""SELECT id,codigo,nome,ncm,cfop,
                           ibs_cbs_cst,ibs_cbs_class,ibs_uf_rate,ibs_city_rate,cbs_rate
                    FROM produtos WHERE id IN ({placeholders})""",
                tuple(unique_ids),
            )
            columns = [column[0] for column in cursor.description]
            products = {int(row[0]): dict(zip(columns, row)) for row in cursor.fetchall()}
        finally:
            conn.close()
        result: list[dict[str, Any]] = []
        for index, cart_item in enumerate(cart_items, 1):
            product_id = int(cart_item.get("produto_id") or 0)
            product = products.get(product_id)
            if not product:
                raise ValueError(f"Item {index}: produto cadastrado não foi encontrado.")
            ncm = self._digits(product.get("ncm"))
            stored_cfop = self._digits(product.get("cfop"))
            cst = self._digits(product.get("ibs_cbs_cst"))
            classification = self._digits(product.get("ibs_cbs_class"))
            missing = []
            if len(ncm) != 8: missing.append("NCM")
            if len(stored_cfop) != 4: missing.append("CFOP")
            if require_rtc and len(cst) != 3: missing.append("CST IBS/CBS")
            if require_rtc and len(classification) != 6: missing.append("classificação IBS/CBS")
            if missing:
                raise ValueError(
                    f"Item {index} ({product.get('nome') or product.get('codigo')}): "
                    f"ficha fiscal incompleta — {', '.join(missing)}. Importe a NF-e de compra ou revise o cadastro."
                )
            cfop_prefix = {1: "5", 2: "6", 3: "7"}[destination]
            fiscal_item = {
                "product_id": product_id,
                "code": product.get("codigo") or product_id,
                "description": product.get("nome") or cart_item.get("item") or "PRODUTO",
                "quantity": cart_item.get("qtd"),
                "unit_price": cart_item.get("preco"),
                "unit": "UN",
                "ncm": ncm,
                "cfop": cfop_prefix + stored_cfop[1:],
            }
            if require_rtc:
                fiscal_item.update({
                    "ibs_cbs_cst": cst,
                    "ibs_cbs_class": classification,
                    "ibs_uf_rate": product.get("ibs_uf_rate") or "0",
                    "ibs_city_rate": product.get("ibs_city_rate") or "0",
                    "cbs_rate": product.get("cbs_rate") or "0",
                })
            result.append(fiscal_item)
        return result

    def build_nfce_qr_code_v3(
        self, *, access_key: str, environment: str,
        issued_at: datetime | str | None = None,
        total: Decimal | str | float | None = None,
        recipient_document: str = "", recipient_foreign_id: str = "",
        pfx_path: str | Path = "", password: str = "",
    ) -> str:
        """Monta o QR Code 3.00 oficial da NFC-e, sem CSC."""
        key = self._normalize_access_key(access_key)
        if len(key) != 44 or key[20:22] != "65":
            raise ValueError("QR Code NFC-e exige chave válida do modelo 65.")
        env_name = str(environment or "").strip().upper()
        if env_name not in self.VALID_ENVIRONMENTS:
            raise ValueError("Ambiente fiscal inválido para QR Code NFC-e.")
        parts = [key, "3", "2" if env_name == "HOMOLOGACAO" else "1"]
        if int(key[34]) != 1:
            if issued_at is None or total is None:
                raise ValueError("QR Code offline exige data de emissão e valor total.")
            when = issued_at if isinstance(issued_at, datetime) else datetime.fromisoformat(str(issued_at))
            amount = Decimal(str(total)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            document = self._normalize_tax_document(recipient_document)
            foreign_id = str(recipient_foreign_id or "").strip()
            if len(document) == 14:
                recipient_type, recipient_id = "1", document
            elif len(document) == 11:
                recipient_type, recipient_id = "2", document
            elif foreign_id:
                recipient_type, recipient_id = "3", ""
            else:
                recipient_type = recipient_id = ""
            parts.extend([f"{when.day:02d}", f"{amount:.2f}", recipient_type, recipient_id])
            self._require_dependency("cryptography")
            path = Path(pfx_path)
            if not path.is_file():
                raise ValueError("Certificado A1 é obrigatório para assinar o QR Code offline.")
            private_key, _cert, _chain = pkcs12.load_key_and_certificates(
                path.read_bytes(), str(password).encode("utf-8")
            )
            if private_key is None:
                raise ValueError("O certificado A1 não contém chave privada.")
            signature = private_key.sign(
                "|".join(parts).encode("utf-8"), padding.PKCS1v15(), hashes.SHA1()
            )
            parts.append(base64.b64encode(signature).decode("ascii"))
        state_code = key[:2]
        uf = next((name for name, code in self.STATE_CODES.items() if code == state_code), "")
        profile = state_profile(uf)
        base_url = str(profile.get("nfce_urls", {}).get(env_name, {}).get("qr_code", ""))
        if not base_url:
            raise ValueError(f"QR Code da NFC-e ainda não homologado para a UF {uf}.")
        return f"{base_url}?p={'|'.join(parts)}"

    def _set_nfce_supplement(self, root: Any, *, qr_code: str, environment: str) -> None:
        ns = "http://www.portalfiscal.inf.br/nfe"
        for node in root.xpath("./*[local-name()='infNFeSupl']"):
            root.remove(node)
        supplement = etree.SubElement(root, etree.QName(ns, "infNFeSupl"))
        qr_node = etree.SubElement(supplement, etree.QName(ns, "qrCode"))
        qr_node.text = qr_code
        key_node = etree.SubElement(supplement, etree.QName(ns, "urlChave"))
        key = str(root.xpath("string(./*[local-name()='infNFe'][1]/@Id)")).removeprefix("NFe")
        state_code = key[:2]
        uf = next((name for name, code in self.STATE_CODES.items() if code == state_code), "")
        profile = state_profile(uf)
        key_url = str(
            profile.get("nfce_urls", {})
            .get(str(environment).strip().upper(), {})
            .get("consulta_chave", "")
        )
        if not key_url:
            raise ValueError(f"Consulta da NFC-e ainda não homologada para a UF {uf}.")
        key_node.text = key_url

    def add_nfce_qr_code_v3(
        self, xml: bytes | str, *, pfx_path: str | Path = "", password: str = ""
    ) -> bytes:
        self._require_dependency("lxml")
        root = etree.fromstring(xml.encode("utf-8") if isinstance(xml, str) else bytes(xml))
        model = str(root.xpath("string(//*[local-name()='ide']/*[local-name()='mod'][1])"))
        if model != "65":
            return etree.tostring(root, xml_declaration=True, encoding="utf-8")
        key = str(root.xpath("string(//*[local-name()='infNFe'][1]/@Id)")).removeprefix("NFe")
        environment_code = str(root.xpath("string(//*[local-name()='ide']/*[local-name()='tpAmb'][1])"))
        environment = "HOMOLOGACAO" if environment_code == "2" else "PRODUCAO"
        issued_at = str(root.xpath("string(//*[local-name()='ide']/*[local-name()='dhEmi'][1])"))
        total = str(root.xpath("string(//*[local-name()='ICMSTot']/*[local-name()='vNF'][1])"))
        recipient_document = str(root.xpath("string(//*[local-name()='dest']/*[local-name()='CNPJ' or local-name()='CPF'][1])"))
        foreign_id = str(root.xpath("string(//*[local-name()='dest']/*[local-name()='idEstrangeiro'][1])"))
        qr_code = self.build_nfce_qr_code_v3(
            access_key=key, environment=environment, issued_at=issued_at, total=total,
            recipient_document=recipient_document, recipient_foreign_id=foreign_id,
            pfx_path=pfx_path, password=password,
        )
        self._set_nfce_supplement(root, qr_code=qr_code, environment=environment)
        return etree.tostring(root, xml_declaration=True, encoding="utf-8")

    def build_event_xml(
        self, *, event_type: str, access_key: str, sequence: int, actor_document: str,
        protocol: str = "", justification: str = "", correction: str = "", environment: str = "HOMOLOGACAO"
    ) -> tuple[bytes, str]:
        event_type = str(event_type).strip().upper()
        if event_type not in self.VALID_EVENTS:
            raise ValueError("Evento fiscal suportado: CANCELAMENTO ou CCE.")
        key=self._normalize_access_key(access_key); actor=self._normalize_tax_document(actor_document)
        if len(key)!=44 or len(actor) not in {11,14}: raise ValueError("Chave ou documento do autor inválido.")
        if event_type=="CANCELAMENTO":
            if not protocol: raise ValueError("Protocolo de autorização é obrigatório para cancelamento.")
            if len(str(justification).strip()) < 15: raise ValueError("Justificativa de cancelamento deve possuir ao menos 15 caracteres.")
            code, desc, detail = "110111", "Cancelamento", {"nProt":protocol,"xJust":str(justification).strip()}
        else:
            if len(str(correction).strip()) < 15: raise ValueError("Correção deve possuir ao menos 15 caracteres.")
            code, desc, detail = "110110", "Carta de Correcao", {"xCorrecao":str(correction).strip(),"xCondUso":"A Carta de Correcao e disciplinada pelo paragrafo 1o-A do art. 7o do Convenio S/N, de 15 de dezembro de 1970."}
        ns="http://www.portalfiscal.inf.br/nfe"; env=2 if str(environment).upper()=="HOMOLOGACAO" else 1
        event_id=f"ID{code}{key}{int(sequence):02d}"
        root=etree.Element(etree.QName(ns,"evento"), nsmap={None:ns}, versao="1.00"); inf=etree.SubElement(root,etree.QName(ns,"infEvento"),Id=event_id)
        def el(parent,name,value): node=etree.SubElement(parent,etree.QName(ns,name)); node.text=str(value); return node
        el(inf,"cOrgao",key[:2]); el(inf,"tpAmb",env); el(inf,"CNPJ" if len(actor)==14 else "CPF",actor); el(inf,"chNFe",key); el(inf,"dhEvento",datetime.now().astimezone().isoformat(timespec="seconds")); el(inf,"tpEvento",code); el(inf,"nSeqEvento",int(sequence)); el(inf,"verEvento","1.00")
        det=etree.SubElement(inf,etree.QName(ns,"detEvento"),versao="1.00"); el(det,"descEvento",desc)
        for n,v in detail.items(): el(det,n,v)
        return etree.tostring(root,xml_declaration=True,encoding="utf-8"), event_id

    def build_inutilization_xml(self, *, state_code: str, year: int, cnpj: str, model: str, series: int, start_number: int, end_number: int, justification: str, environment: str="HOMOLOGACAO") -> tuple[bytes,str]:
        cnpj=self._normalize_cnpj(cnpj); model=str(model).zfill(2)
        if not self._is_valid_cnpj(cnpj) or model not in self.VALID_MODELS: raise ValueError("Dados da inutilização inválidos.")
        if int(start_number)>int(end_number): raise ValueError("Faixa de inutilização inválida.")
        if len(str(justification).strip())<15: raise ValueError("Justificativa deve possuir ao menos 15 caracteres.")
        identifier=f"ID{str(state_code).zfill(2)}{int(year)%100:02d}{cnpj}{model}{int(series):03d}{int(start_number):09d}{int(end_number):09d}"
        ns="http://www.portalfiscal.inf.br/nfe"; root=etree.Element(etree.QName(ns,"inutNFe"),nsmap={None:ns},versao="4.00"); inf=etree.SubElement(root,etree.QName(ns,"infInut"),Id=identifier)
        def el(n,v): node=etree.SubElement(inf,etree.QName(ns,n)); node.text=str(v)
        el("tpAmb",2 if str(environment).upper()=="HOMOLOGACAO" else 1); el("xServ","INUTILIZAR"); el("cUF",str(state_code).zfill(2)); el("ano",f"{int(year)%100:02d}"); el("CNPJ",cnpj); el("mod",model); el("serie",int(series)); el("nNFIni",int(start_number)); el("nNFFin",int(end_number)); el("xJust",str(justification).strip())
        return etree.tostring(root,xml_declaration=True,encoding="utf-8"),identifier

    def build_query_xml(self, *, access_key: str, environment: str="HOMOLOGACAO") -> bytes:
        key=self._normalize_access_key(access_key)
        if len(key)!=44: raise ValueError("Chave de acesso inválida para consulta.")
        ns="http://www.portalfiscal.inf.br/nfe"; root=etree.Element(etree.QName(ns,"consSitNFe"),nsmap={None:ns},versao="4.00")
        for name,value in (("tpAmb",2 if str(environment).upper()=="HOMOLOGACAO" else 1),("xServ","CONSULTAR"),("chNFe",key)):
            node=etree.SubElement(root,etree.QName(ns,name)); node.text=str(value)
        return etree.tostring(root,xml_declaration=True,encoding="utf-8")

    def build_receipt_query_xml(self, *, receipt: str, environment: str = "HOMOLOGACAO") -> bytes:
        receipt_number = self._digits(receipt)
        if not receipt_number:
            raise ValueError("Número do recibo da SEFAZ é obrigatório.")
        ns = "http://www.portalfiscal.inf.br/nfe"
        root = etree.Element(etree.QName(ns, "consReciNFe"), nsmap={None: ns}, versao="4.00")
        for name, value in (
            ("tpAmb", 2 if str(environment).upper() == "HOMOLOGACAO" else 1),
            ("nRec", receipt_number),
        ):
            node = etree.SubElement(root, etree.QName(ns, name))
            node.text = str(value)
        return etree.tostring(root, xml_declaration=True, encoding="utf-8")

    def validate_event_eligibility(
        self,
        *,
        access_key: str,
        event_type: str,
        sequence: int,
        protocol: str = "",
    ) -> dict[str, Any]:
        key = self._normalize_access_key(access_key)
        if len(key) != 44:
            raise ValueError("Chave de acesso inválida.")
        kind = str(event_type or "").strip().upper()
        if kind not in self.VALID_EVENTS:
            raise ValueError("Tipo de evento fiscal inválido.")
        seq = int(sequence)
        if seq < 1 or seq > 20:
            raise ValueError("Sequência do evento deve estar entre 1 e 20.")

        documents = [
            row for row in self.list_documents()
            if row.get("access_key") == key
        ]
        if not documents:
            raise ValueError("Evento fiscal exige documento autorizado armazenado.")
        document = documents[-1]
        document_status = str(document.get("status") or "").upper()
        if document_status == "CANCELADO":
            if kind == "CCE":
                raise ValueError("Carta de correção não pode ser enviada após cancelamento aceito.")
            raise ValueError("Documento fiscal já possui cancelamento aceito.")
        if document_status != "AUTORIZADO":
            raise ValueError("Evento fiscal exige documento autorizado armazenado.")
        integrity = self.verify_document_integrity(
            access_key=key, environment=str(document.get("environment") or "")
        )
        if not integrity.get("valid"):
            raise ValueError("Documento autorizado falhou na verificação de integridade.")

        if kind == "CANCELAMENTO":
            informed_protocol = str(protocol or "").strip()
            stored_protocol = str(document.get("protocol") or "").strip()
            if not informed_protocol or informed_protocol != stored_protocol:
                raise ValueError("Cancelamento exige o protocolo de autorização do documento.")

        accepted = [
            row for row in self.list_events(key)
            if row.get("success")
            and str(row.get("event_type") or "").upper() == kind
        ]
        if kind == "CANCELAMENTO" and accepted:
            raise ValueError("Documento fiscal já possui cancelamento aceito.")
        if any(int(row.get("sequence") or 0) == seq for row in accepted):
            raise ValueError("Sequência de evento já utilizada para este documento.")
        if kind == "CCE" and any(str(row.get("event_type") or "").upper() == "CANCELAMENTO" for row in self.list_events(key) if row.get("success")):
            raise ValueError("Carta de correção não pode ser enviada após cancelamento aceito.")
        return dict(document)

    def register_event(self, *, access_key: str, event_type: str, response: FiscalResponse, request_xml: bytes|str, actor: str) -> dict[str,Any]:
        key=self._normalize_access_key(access_key)
        if len(key)!=44: raise ValueError("Chave de acesso inválida.")
        folder=self.storage_dir/"eventos"/key; folder.mkdir(parents=True,exist_ok=True)
        stamp=datetime.now().strftime("%Y%m%d_%H%M%S_%f"); request_path=folder/f"{stamp}_{event_type.lower()}_envio.xml"; response_path=folder/f"{stamp}_{event_type.lower()}_retorno.xml"
        request_path.write_bytes(request_xml.encode() if isinstance(request_xml,str) else request_xml); response_path.write_text(response.raw_xml,encoding="utf-8")
        try:
            request_root = etree.fromstring(request_xml.encode() if isinstance(request_xml, str) else bytes(request_xml), parser=etree.XMLParser(resolve_entities=False, no_network=True))
            sequence = int(str(request_root.xpath("string(//*[local-name()='nSeqEvento'][1])") or "0"))
            environment_code = str(request_root.xpath("string(//*[local-name()='tpAmb'][1])") or "")
            event_environment = "HOMOLOGACAO" if environment_code == "2" else "PRODUCAO" if environment_code == "1" else ""
        except (ValueError, TypeError, etree.XMLSyntaxError):
            sequence = 0
            event_environment = ""
        request_bytes = request_xml.encode() if isinstance(request_xml, str) else bytes(request_xml)
        response_bytes = response.raw_xml.encode("utf-8")
        record={
            "access_key":key,
            "event_type":str(event_type).upper(),
            "environment":event_environment,
            "sequence":sequence,
            "status_code":response.status_code,
            "message":response.message,
            "protocol":response.protocol,
            "success":response.success,
            "actor":actor or "Sistema",
            "created_at":datetime.now().isoformat(timespec="seconds"),
            "request_path":str(request_path),
            "response_path":str(response_path),
            "request_sha256":hashlib.sha256(request_bytes).hexdigest(),
            "response_sha256":hashlib.sha256(response_bytes).hexdigest(),
        }
        rows=self.list_events(); rows.append(record); self._set_setting(self.EVENT_INDEX_KEY,json.dumps(rows,ensure_ascii=False,sort_keys=True))
        if response.success and str(event_type).upper() == "CANCELAMENTO":
            self._mark_document_cancelled(
                access_key=key,
                event_protocol=response.protocol,
                actor=actor,
                event_record=record,
            )
        if not response.success:
            self.register_rejection(
                operation=str(event_type).upper(),
                response=response,
                access_key=key,
                actor=actor,
            )
        return record


    def _mark_document_cancelled(
        self, *, access_key: str, event_protocol: str, actor: str, event_record: Mapping[str, Any]
    ) -> dict[str, Any]:
        key = self._normalize_access_key(access_key)
        if len(key) != 44:
            raise ValueError("Chave de acesso inválida para cancelamento.")
        rows = self.list_documents()
        matched = None
        for row in reversed(rows):
            if row.get("access_key") == key:
                matched = row
                break
        if not matched:
            raise ValueError("Documento fiscal autorizado não encontrado para registrar cancelamento.")
        if matched.get("status") not in {"AUTORIZADO", "CANCELADO"}:
            raise ValueError("Somente documento autorizado pode ser marcado como cancelado.")
        if matched.get("status") == "CANCELADO":
            if str(matched.get("cancellation_protocol") or "") != str(event_protocol or ""):
                raise ValueError("Documento já foi cancelado com outro protocolo.")
            return dict(matched)
        matched.update({
            "status": "CANCELADO",
            "cancelled_at": datetime.now().isoformat(timespec="seconds"),
            "cancelled_by": str(actor or "Sistema"),
            "cancellation_protocol": str(event_protocol or ""),
            "cancellation_status_code": str(event_record.get("status_code") or ""),
            "cancellation_message": str(event_record.get("message") or ""),
            "cancellation_request_path": str(event_record.get("request_path") or ""),
            "cancellation_response_path": str(event_record.get("response_path") or ""),
            "cancellation_request_sha256": str(event_record.get("request_sha256") or ""),
            "cancellation_response_sha256": str(event_record.get("response_sha256") or ""),
        })
        self._set_setting(self.DOCUMENT_INDEX_KEY, json.dumps(rows, ensure_ascii=False, sort_keys=True))
        return dict(matched)

    def list_events(self, access_key: str="") -> list[dict[str,Any]]:
        raw=self._get_setting(self.EVENT_INDEX_KEY)
        try: rows=json.loads(raw) if raw else []
        except (TypeError,ValueError): rows=[]
        key=self._normalize_access_key(access_key)
        result=[dict(r) for r in rows if isinstance(r,dict)]
        return [r for r in result if r.get("access_key")==key] if key else result

    def generate_danfe_pdf(self, *, authorized_xml: bytes|str, output_path: str|Path) -> Path:
        self._require_dependency("lxml")
        self._require_dependency("reportlab")
        raw=authorized_xml.encode() if isinstance(authorized_xml,str) else authorized_xml
        root=etree.fromstring(raw,parser=etree.XMLParser(resolve_entities=False,no_network=True))
        text=lambda n: str(root.xpath(f"string(//*[local-name()='{n}'][1])") or "").strip()
        protocol=text("nProt"); status=text("cStat")
        if not protocol or status not in self.AUTHORIZED_STATUS:
            raise ValueError("DANFE só pode ser gerado para documento autorizado com protocolo válido.")
        key=text("chNFe") or str(root.xpath("string(//*[local-name()='infNFe'][1]/@Id)")).replace("NFe","")
        output=Path(output_path); output.parent.mkdir(parents=True,exist_ok=True)
        document_record = next((row for row in reversed(self.list_documents()) if row.get("access_key") == key), {})
        cancelled = str(document_record.get("status") or "").upper() == "CANCELADO"
        c=canvas.Canvas(str(output),pagesize=A4); width,height=A4
        c.setFont("Helvetica-Bold",14); c.drawString(15*mm,height-18*mm,"DANFE — Documento Auxiliar da NF-e")
        if cancelled:
            c.saveState()
            c.setFont("Helvetica-Bold", 42)
            c.setFillGray(0.80)
            c.translate(width / 2, height / 2)
            c.rotate(35)
            c.drawCentredString(0, 0, "CANCELADO")
            c.restoreState()
        c.setFont("Helvetica",9); y=height-28*mm
        lines=[f"Chave de acesso: {key}",f"Protocolo: {protocol}",f"Número: {text('nNF')}  Série: {text('serie')}  Modelo: {text('mod')}",f"Emitente: {text('xNome')}  CNPJ: {text('CNPJ')}",f"Destinatário: {str(root.xpath("string(//*[local-name()='dest']/*[local-name()='xNome'][1])") or '').strip()}",f"Valor total: R$ {text('vNF')}"]
        if cancelled:
            lines.insert(2, f"CANCELADO — protocolo: {document_record.get('cancellation_protocol', '')}")
        for line in lines: c.drawString(15*mm,y,line); y-=6*mm
        c.line(15*mm,y,width-15*mm,y); y-=7*mm; c.setFont("Helvetica-Bold",8); c.drawString(15*mm,y,"ITEM  CÓDIGO  DESCRIÇÃO  QTD  UN  V.UNIT  V.TOTAL"); y-=5*mm; c.setFont("Helvetica",7)
        dets=root.xpath("//*[local-name()='det']")
        for det in dets:
            get=lambda n: str(det.xpath(f"string(.//*[local-name()='{n}'][1])") or "").strip()
            line=f"{det.get('nItem','')}  {get('cProd')[:12]}  {get('xProd')[:42]}  {get('qCom')}  {get('uCom')}  {get('vUnCom')}  {get('vProd')}"
            c.drawString(15*mm,y,line); y-=4.5*mm
            if y<20*mm: c.showPage(); y=height-20*mm; c.setFont("Helvetica",7)
        c.setFont("Helvetica-Oblique",7); c.drawString(15*mm,12*mm,"Documento auxiliar gerado pelo NabiCode. A validade fiscal depende do XML autorizado armazenado.")
        c.save(); return output


    def apply_contingency(self, xml: bytes | str, *, reason: str, emission_type: int = 9, started_at: datetime | None = None) -> bytes:
        emission_type = int(emission_type)
        if emission_type not in {2, 4, 5, 6, 7, 9}:
            raise ValueError("Tipo de emissão em contingência inválido.")
        if len(str(reason).strip()) < 15:
            raise ValueError("Justificativa da contingência deve possuir ao menos 15 caracteres.")
        root = etree.fromstring(
            xml.encode() if isinstance(xml, str) else xml,
            parser=etree.XMLParser(resolve_entities=False, no_network=True),
        )
        ide_nodes = root.xpath("//*[local-name()='ide'][1]")
        inf_nodes = root.xpath("//*[local-name()='infNFe'][1]")
        if not ide_nodes or not inf_nodes:
            raise ValueError("XML não possui grupos ide e infNFe para aplicar contingência.")
        ide = ide_nodes[0]
        inf_nfe = inf_nodes[0]
        ns = "http://www.portalfiscal.inf.br/nfe"

        def text(name: str, *, context=ide) -> str:
            return str(context.xpath(f"string(./*[local-name()='{name}'][1])") or "").strip()

        tp_nodes = ide.xpath("./*[local-name()='tpEmis'][1]")
        tp_node = tp_nodes[0] if tp_nodes else etree.SubElement(ide, etree.QName(ns, "tpEmis"))
        tp_node.text = str(emission_type)
        for node in ide.xpath("./*[local-name()='dhCont' or local-name()='xJust']"):
            ide.remove(node)
        dh = etree.SubElement(ide, etree.QName(ns, "dhCont"))
        dh.text = (started_at or datetime.now().astimezone()).astimezone().isoformat(timespec="seconds")
        xj = etree.SubElement(ide, etree.QName(ns, "xJust"))
        xj.text = str(reason).strip()

        issued_text = text("dhEmi") or text("dEmi")
        try:
            issued_at = datetime.fromisoformat(issued_text.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            raise ValueError("Data de emissão inválida ou ausente para recalcular a chave de contingência.")
        cnpj = str(root.xpath("string(//*[local-name()='emit']/*[local-name()='CNPJ'][1])") or "").strip()
        required = {
            "cUF": text("cUF"), "mod": text("mod"), "serie": text("serie"),
            "nNF": text("nNF"), "cNF": text("cNF"), "CNPJ": cnpj,
        }
        missing = [name for name, value in required.items() if not self._digits(value)]
        if missing:
            raise ValueError("Dados insuficientes para recalcular a chave de contingência: " + ", ".join(missing))
        access_key = self.build_access_key(
            state_code=required["cUF"], issued_at=issued_at, cnpj=required["CNPJ"],
            model=required["mod"], series=int(required["serie"]), number=int(required["nNF"]),
            emission_type=emission_type, numeric_code=required["cNF"],
        )
        inf_nfe.set("Id", f"NFe{access_key}")
        cdv_nodes = ide.xpath("./*[local-name()='cDV'][1]")
        cdv_node = cdv_nodes[0] if cdv_nodes else etree.SubElement(ide, etree.QName(ns, "cDV"))
        cdv_node.text = access_key[-1]
        return etree.tostring(root, xml_declaration=True, encoding="utf-8")

    def list_transmission_queue(self, *, status: str = "") -> list[dict[str, Any]]:
        raw = self._get_setting(self.TRANSMISSION_QUEUE_KEY)
        try:
            rows = json.loads(raw) if raw else []
        except (TypeError, ValueError):
            rows = []
        result = [dict(row) for row in rows if isinstance(row, dict)]
        wanted = str(status or "").strip().upper()
        if wanted:
            result = [row for row in result if str(row.get("status", "")).upper() == wanted]
        return sorted(result, key=lambda row: str(row.get("created_at", "")))

    def enqueue_transmission(
        self,
        *,
        operation: str,
        xml: bytes | str,
        actor: str,
        access_key: str = "",
        model: str = "55",
        max_attempts: int = 5,
        retry_minutes: int = 5,
    ) -> dict[str, Any]:
        operation = str(operation or "").strip().lower()
        if operation not in {"autorizacao", "consulta", "recibo", "evento", "inutilizacao"}:
            raise ValueError("Operação fiscal inválida para a fila de transmissão.")
        model = str(model or "55").strip()
        if model not in self.VALID_MODELS:
            raise ValueError("Modelo fiscal deve ser 55 ou 65.")
        raw_xml = xml.encode("utf-8") if isinstance(xml, str) else bytes(xml)
        if not raw_xml.strip():
            raise ValueError("XML fiscal é obrigatório para enfileirar transmissão.")
        supplied_key = self._normalize_access_key(access_key)
        embedded_key = self._extract_access_key_from_xml(raw_xml)
        if supplied_key and embedded_key and supplied_key != embedded_key:
            raise ValueError("A chave informada não corresponde ao XML enfileirado.")
        resolved_key = supplied_key or embedded_key
        if operation == "autorizacao" and len(resolved_key) != 44:
            raise ValueError("Autorização enfileirada exige uma chave de acesso válida no XML ou no parâmetro access_key.")
        now = datetime.now(timezone.utc)
        rows = self.list_transmission_queue()
        record = {
            "id": f"{now.strftime('%Y%m%d%H%M%S%f')}-{len(rows)+1}",
            "operation": operation,
            "access_key": resolved_key,
            "model": model,
            "xml_b64": base64.b64encode(raw_xml).decode("ascii"),
            "original_xml_b64": base64.b64encode(raw_xml).decode("ascii") if operation == "autorizacao" else "",
            "receipt": "",
            "actor": str(actor or "").strip(),
            "status": "PENDENTE",
            "attempts": 0,
            "max_attempts": max(1, int(max_attempts)),
            "retry_minutes": max(1, int(retry_minutes)),
            "created_at": now.isoformat(),
            "next_attempt_at": now.isoformat(),
            "last_error": "",
            "last_status_code": "",
            "last_message": "",
        }
        rows.append(record)
        self._set_setting(self.TRANSMISSION_QUEUE_KEY, json.dumps(rows[-5000:], ensure_ascii=False, sort_keys=True))
        return dict(record)

    def process_transmission_queue(
        self,
        *,
        password: str,
        limit: int = 20,
        now: datetime | None = None,
    ) -> list[dict[str, Any]]:
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        rows = self.list_transmission_queue()
        processed: list[dict[str, Any]] = []
        count = 0
        for record in rows:
            if count >= max(1, int(limit)):
                break
            if record.get("status") not in {"PENDENTE", "ERRO"}:
                continue
            try:
                next_attempt = datetime.fromisoformat(str(record.get("next_attempt_at") or record.get("created_at")))
                if next_attempt.tzinfo is None:
                    next_attempt = next_attempt.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                next_attempt = current
            if next_attempt > current:
                continue
            count += 1
            record["attempts"] = int(record.get("attempts", 0)) + 1
            record["last_attempt_at"] = current.isoformat()
            try:
                config = self.load_config()
                xml = base64.b64decode(str(record.get("xml_b64", "")))
                response = self.transmit(
                    operation=str(record.get("operation")),
                    model=str(record.get("model") or config.get("default_model") or "65"),
                    xml=xml,
                    pfx_path=config.get("certificate_path", ""),
                    password=password,
                )
                record["last_status_code"] = response.status_code
                record["last_message"] = response.message
                record["last_error"] = ""
                operation = str(record.get("operation", "")).lower()
                queued_key = self._normalize_access_key(record.get("access_key", ""))
                if operation == "autorizacao" and response.status_code == "103" and response.receipt:
                    record["operation"] = "recibo"
                    record["receipt"] = self._digits(response.receipt)
                    record["xml_b64"] = base64.b64encode(
                        self.build_receipt_query_xml(
                            receipt=record["receipt"],
                            environment=str(config.get("environment", "HOMOLOGACAO")),
                        )
                    ).decode("ascii")
                    record["status"] = "PENDENTE"
                    retry = max(1, int(record.get("retry_minutes", 5)))
                    record["next_attempt_at"] = (current + timedelta(minutes=retry)).isoformat()
                    record["last_error"] = ""
                elif operation == "recibo" and response.status_code == "105":
                    record["status"] = "PENDENTE"
                    retry = max(1, int(record.get("retry_minutes", 5)))
                    record["next_attempt_at"] = (current + timedelta(minutes=retry)).isoformat()
                    record["last_error"] = ""
                elif response.success:
                    if operation in {"autorizacao", "recibo"}:
                        response_key = self._normalize_access_key(response.access_key)
                        if len(queued_key) != 44:
                            raise ValueError("Item de autorização sem chave de acesso válida.")
                        if response_key != queued_key:
                            raise ValueError("A resposta SEFAZ não corresponde à chave enfileirada.")
                        original_b64 = str(record.get("original_xml_b64") or record.get("xml_b64", ""))
                        original_xml = base64.b64decode(original_b64)
                        nfe_xml = self._extract_nfe_xml(original_xml)
                        stored = self.store_document(
                            access_key=queued_key,
                            model=str(record.get("model", "55")),
                            environment=str(config.get("environment", "HOMOLOGACAO")),
                            request_xml=nfe_xml,
                            response=response,
                            actor=str(record.get("actor", "")),
                        )
                        record["document_record"] = {
                            "request_path": stored.get("request_path", ""),
                            "response_path": stored.get("response_path", ""),
                            "processed_path": stored.get("processed_path", ""),
                            "protocol": stored.get("protocol", ""),
                        }
                    record["status"] = "CONCLUIDO"
                    record["completed_at"] = current.isoformat()
                else:
                    raise ValueError(f"{response.status_code}: {response.message}")
            except Exception as exc:
                record["last_error"] = str(exc)
                if int(record["attempts"]) >= int(record.get("max_attempts", 1)):
                    record["status"] = "FALHA"
                    record["failed_at"] = current.isoformat()
                else:
                    record["status"] = "ERRO"
                    retry = max(1, int(record.get("retry_minutes", 5)))
                    record["next_attempt_at"] = (current + timedelta(minutes=retry)).isoformat()
            processed.append(dict(record))
        self._set_setting(self.TRANSMISSION_QUEUE_KEY, json.dumps(rows[-5000:], ensure_ascii=False, sort_keys=True))
        return processed

    def retry_transmission(self, queue_id: str, *, actor: str) -> dict[str, Any]:
        rows = self.list_transmission_queue()
        target = None
        for record in rows:
            if str(record.get("id")) == str(queue_id):
                target = record
                break
        if target is None:
            raise ValueError("Item da fila fiscal não encontrado.")
        if target.get("status") == "CONCLUIDO":
            raise ValueError("Transmissão concluída não pode ser reenviada.")
        target.update({
            "status": "PENDENTE",
            "next_attempt_at": datetime.now(timezone.utc).isoformat(),
            "retried_by": str(actor or "").strip(),
            "retried_at": datetime.now(timezone.utc).isoformat(),
            "last_error": "",
        })
        self._set_setting(self.TRANSMISSION_QUEUE_KEY, json.dumps(rows[-5000:], ensure_ascii=False, sort_keys=True))
        return dict(target)

    def authorize_document(
        self,
        *,
        xml: bytes | str,
        access_key: str,
        password: str,
        actor: str,
        model: str = "55",
        reservation_id: str = "",
    ) -> tuple[FiscalResponse, dict[str, Any]]:
        problems = self.validate_ready(operation="autorizacao", model=model)
        if problems:
            raise ValueError("; ".join(problems))
        config = self.load_config()
        key = self._normalize_access_key(access_key)
        if len(key) != 44:
            raise ValueError("Chave de acesso inválida para autorização.")

        xml_key = self._extract_access_key_from_xml(xml)
        if xml_key and xml_key != key:
            raise ValueError("A chave informada não corresponde ao XML fiscal.")

        reservation = None
        if reservation_id:
            reservation = next(
                (item for item in self.numbering_status() if item.get("id") == str(reservation_id)),
                None,
            )
            if not reservation:
                raise ValueError("Reserva de numeração não encontrada.")
            if reservation.get("status") != "RESERVADO":
                raise ValueError("A numeração não está reservada para autorização.")
            if str(reservation.get("environment", "")).upper() != str(config["environment"]).upper():
                raise ValueError("A reserva pertence a outro ambiente fiscal.")
            if str(reservation.get("model")) != str(model):
                raise ValueError("A reserva pertence a outro modelo fiscal.")
            expected_series = int(key[22:25])
            expected_number = int(key[25:34])
            if expected_series != int(reservation.get("series", -1)) or expected_number != int(reservation.get("number", -1)):
                raise ValueError("A chave de acesso não corresponde à numeração reservada.")

        if str(model) == "65":
            xml = self.add_nfce_qr_code_v3(
                xml, pfx_path=config["certificate_path"], password=password
            )
        signed = self.sign_xml(xml, reference_id=f"NFe{key}", pfx_path=config["certificate_path"], password=password)
        self.validate_official_xml(signed, document_type="nfe")
        envelope = self._authorization_envelope(signed, environment=config["environment"])
        response = self.transmit(operation="autorizacao", model=model, xml=envelope, pfx_path=config["certificate_path"], password=password)
        record = self.store_document(
            access_key=key,
            model=model,
            environment=config["environment"],
            request_xml=signed,
            response=response,
            actor=actor,
        )
        if reservation_id and response.success:
            numbering = self.confirm_number(reservation_id, access_key=key, actor=actor)
            record = dict(record)
            record["numbering"] = numbering
        return response, record

    def consult_document(self, *, access_key: str, password: str) -> FiscalResponse:
        key = self._normalize_access_key(access_key)
        model = key[20:22] if len(key) == 44 else str(self.load_config().get("default_model") or "65")
        problems = self.validate_ready(operation="consulta", model=model)
        if problems:
            raise ValueError("; ".join(problems))
        config = self.load_config()
        xml = self.build_query_xml(access_key=access_key, environment=config["environment"])
        self.validate_official_xml(xml, document_type="consulta")
        return self.transmit(operation="consulta", model=model, xml=xml, pfx_path=config["certificate_path"], password=password)

    def send_event(self, *, event_type: str, access_key: str, sequence: int, password: str, actor: str, protocol: str = "", justification: str = "", correction: str = "") -> tuple[FiscalResponse, dict[str, Any]]:
        key = self._normalize_access_key(access_key)
        model = key[20:22] if len(key) == 44 else str(self.load_config().get("default_model") or "65")
        problems = self.validate_ready(operation="evento", model=model)
        if problems:
            raise ValueError("; ".join(problems))
        config = self.load_config()
        self.validate_event_eligibility(
            access_key=access_key, event_type=event_type, sequence=sequence, protocol=protocol
        )
        xml, event_id = self.build_event_xml(event_type=event_type, access_key=access_key, sequence=sequence, actor_document=config["cnpj"], protocol=protocol, justification=justification, correction=correction, environment=config["environment"])
        signed = self.sign_xml(xml, reference_id=event_id, pfx_path=config["certificate_path"], password=password)
        envelope = self._event_envelope(signed)
        self.validate_official_xml(envelope, document_type="evento")
        response = self.transmit(operation="evento", model=model, xml=envelope, pfx_path=config["certificate_path"], password=password)
        record = self.register_event(access_key=access_key, event_type=event_type, response=response, request_xml=envelope, actor=actor)
        return response, record

    def inutilize_numbers(self, *, year: int, model: str, series: int, start_number: int, end_number: int, justification: str, password: str, actor: str) -> tuple[FiscalResponse, dict[str, Any]]:
        problems = self.validate_ready(operation="inutilizacao", model=model)
        if problems:
            raise ValueError("; ".join(problems))
        config = self.load_config()
        state_code = self.STATE_CODES.get(str(config.get("state", "")).upper())
        if not state_code:
            raise ValueError("UF do emitente não possui código IBGE configurável.")
        xml, identifier = self.build_inutilization_xml(state_code=state_code, year=year, cnpj=config["cnpj"], model=model, series=series, start_number=start_number, end_number=end_number, justification=justification, environment=config["environment"])
        signed = self.sign_xml(xml, reference_id=identifier, pfx_path=config["certificate_path"], password=password)
        self.validate_official_xml(signed, document_type="inutilizacao")
        response = self.transmit(operation="inutilizacao", model=model, xml=signed, pfx_path=config["certificate_path"], password=password)
        record = self.register_event(access_key="0" * 44, event_type="INUTILIZACAO", response=response, request_xml=signed, actor=actor)
        record.update({"model": model, "series": int(series), "start_number": int(start_number), "end_number": int(end_number), "year": int(year)})
        return response, record

    @classmethod
    def _extract_access_key_from_xml(cls, xml: bytes | str) -> str:
        raw = xml.encode("utf-8") if isinstance(xml, str) else bytes(xml)
        try:
            root = etree.fromstring(raw, parser=etree.XMLParser(resolve_entities=False, no_network=True))
        except (etree.XMLSyntaxError, ValueError, TypeError):
            return ""
        identifier = str(root.xpath("string(//*[local-name()='infNFe'][1]/@Id)") or "")
        key = cls._normalize_access_key(identifier.replace("NFe", ""))
        if len(key) == 44:
            return key
        protocol_key = cls._normalize_access_key(str(root.xpath("string(//*[local-name()='chNFe'][1])") or ""))
        return protocol_key if len(protocol_key) == 44 else ""

    @staticmethod
    def _extract_nfe_xml(xml: bytes | str) -> bytes:
        raw = xml.encode("utf-8") if isinstance(xml, str) else bytes(xml)
        root = etree.fromstring(raw, parser=etree.XMLParser(resolve_entities=False, no_network=True))
        if etree.QName(root).localname == "NFe":
            return etree.tostring(root, xml_declaration=True, encoding="utf-8")
        nodes = root.xpath("//*[local-name()='NFe'][1]")
        if not nodes:
            raise ValueError("XML de autorização não contém uma NF-e assinada.")
        return etree.tostring(nodes[0], xml_declaration=True, encoding="utf-8")

    @staticmethod
    def _authorization_envelope(signed_xml: bytes, *, environment: str) -> bytes:
        ns = "http://www.portalfiscal.inf.br/nfe"
        root = etree.Element(etree.QName(ns, "enviNFe"), nsmap={None: ns}, versao="4.00")
        id_lote = etree.SubElement(root, etree.QName(ns, "idLote")); id_lote.text = datetime.now().strftime("%Y%m%d%H%M%S")
        ind = etree.SubElement(root, etree.QName(ns, "indSinc")); ind.text = "1"
        nfe = etree.fromstring(signed_xml, parser=etree.XMLParser(resolve_entities=False, no_network=True))
        root.append(nfe)
        return etree.tostring(root, xml_declaration=True, encoding="utf-8")

    @staticmethod
    def _event_envelope(signed_xml: bytes) -> bytes:
        ns = "http://www.portalfiscal.inf.br/nfe"
        root = etree.Element(etree.QName(ns, "envEvento"), nsmap={None: ns}, versao="1.00")
        lot = etree.SubElement(root, etree.QName(ns, "idLote"))
        lot.text = datetime.now().strftime("%y%m%d%H%M%S%f")[-15:]
        event = etree.fromstring(
            signed_xml,
            parser=etree.XMLParser(resolve_entities=False, no_network=True),
        )
        root.append(event)
        return etree.tostring(root, xml_declaration=True, encoding="utf-8")

    def _temporary_pem_files(self, pfx_path: str | Path, password: str) -> tuple[str, str]:
        key, cert, chain = pkcs12.load_key_and_certificates(Path(pfx_path).read_bytes(), str(password).encode("utf-8"))
        if key is None or cert is None:
            raise ValueError("Certificado A1 inválido para comunicação.")
        cert_bytes = cert.public_bytes(serialization.Encoding.PEM)
        for item in chain or []:
            cert_bytes += item.public_bytes(serialization.Encoding.PEM)
        key_bytes = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        cert_file = tempfile.NamedTemporaryFile(prefix="nabicode_cert_", suffix=".pem", delete=False)
        key_file = tempfile.NamedTemporaryFile(prefix="nabicode_key_", suffix=".pem", delete=False)
        try:
            os.chmod(cert_file.name, 0o600)
            os.chmod(key_file.name, 0o600)
            cert_file.write(cert_bytes)
            cert_file.flush()
            os.fsync(cert_file.fileno())
            key_file.write(key_bytes)
            key_file.flush()
            os.fsync(key_file.fileno())
        except Exception:
            cert_file.close()
            key_file.close()
            self._secure_delete_file(cert_file.name)
            self._secure_delete_file(key_file.name)
            raise
        finally:
            if not cert_file.closed:
                cert_file.close()
            if not key_file.closed:
                key_file.close()
        return cert_file.name, key_file.name

    @staticmethod
    def _secure_delete_file(path: str | Path) -> None:
        """Sobrescreve o conteúdo temporário quando possível e remove o arquivo."""
        target = Path(path)
        try:
            if target.is_file():
                size = target.stat().st_size
                if size > 0:
                    with target.open("r+b", buffering=0) as stream:
                        stream.write(b"\x00" * size)
                        stream.flush()
                        os.fsync(stream.fileno())
        except OSError:
            pass
        try:
            target.unlink(missing_ok=True)
        except OSError:
            pass

    @staticmethod
    def _atomic_write_bytes(path: Path, data: bytes) -> None:
        """Grava bytes sem expor arquivo fiscal parcialmente escrito."""
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
        temp_path = Path(temp_name)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, path)
        except Exception:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise

    @staticmethod
    def _cert_datetime(cert: x509.Certificate, utc_attr: str, legacy_attr: str) -> datetime:
        value = getattr(cert, utc_attr, None) or getattr(cert, legacy_attr)
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

    @staticmethod
    def _document_from_certificate(cert: x509.Certificate) -> str:
        for attribute in cert.subject:
            value = str(attribute.value)
            for token in re.findall(r"(?<![A-Z0-9])[A-Z0-9][A-Z0-9./-]{12,20}(?![A-Z0-9])", value.upper()):
                try:
                    document = FiscalService._normalize_cnpj(token)
                except ValueError:
                    continue
                if FiscalService._is_valid_cnpj_format(document):
                    return document
            digits = FiscalService._digits(value)
            if len(digits) == 14:
                return digits
        return ""

    @staticmethod
    def _normalize_cnpj(value: Any) -> str:
        normalized = re.sub(r"[\s./-]+", "", str(value or "").upper())
        if normalized and not re.fullmatch(r"[A-Z0-9]+", normalized):
            raise ValueError("CNPJ contém caracteres inválidos.")
        return normalized

    @staticmethod
    def _is_valid_cnpj_format(value: Any) -> bool:
        try:
            normalized = FiscalService._normalize_cnpj(value)
        except ValueError:
            return False
        return bool(re.fullmatch(r"[A-Z0-9]{12}[0-9]{2}", normalized))

    @staticmethod
    def _is_valid_cnpj(value: Any) -> bool:
        if not FiscalService._is_valid_cnpj_format(value):
            return False
        normalized = FiscalService._normalize_cnpj(value)

        def digit(text: str, weights: Sequence[int]) -> int:
            total = sum((ord(char) - 48) * weight for char, weight in zip(text, weights))
            remainder = total % 11
            return 0 if remainder < 2 else 11 - remainder

        first = digit(normalized[:12], (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
        second = digit(normalized[:12] + str(first), (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
        return normalized[-2:] == f"{first}{second}"

    @staticmethod
    def _normalize_access_key(value: Any) -> str:
        normalized = re.sub(r"[\s.-]+", "", str(value or "").upper())
        if normalized and not re.fullmatch(r"[A-Z0-9]+", normalized):
            raise ValueError("Chave de acesso contém caracteres inválidos.")
        return normalized

    @staticmethod
    def _is_valid_access_key(value: Any) -> bool:
        try:
            normalized = FiscalService._normalize_access_key(value)
        except ValueError:
            return False
        if not re.fullmatch(r"[0-9]{6}[A-Z0-9]{12}[0-9]{26}", normalized):
            return False
        return FiscalService.calculate_access_key_digit(normalized[:43]) == normalized[-1]

    @staticmethod
    def _normalize_tax_document(value: Any) -> str:
        raw = str(value or "")
        return FiscalService._normalize_cnpj(raw) if re.search(r"[A-Za-z]", raw) else FiscalService._digits(raw)

    @staticmethod
    def _digits(value: Any) -> str:
        return "".join(ch for ch in str(value or "") if ch.isdigit())

    def _load_numbering(self) -> dict[str, Any]:
        conn = self.connection_factory()
        try:
            return self._load_numbering_conn(conn)
        finally:
            conn.close()

    def _load_numbering_conn(self, conn: Any) -> dict[str, Any]:
        row = conn.execute("SELECT valor FROM configuracoes WHERE chave = ?", (self.NUMBERING_KEY,)).fetchone()
        if row is None:
            return {"scopes": {}, "records": {}}
        try:
            data = json.loads(str(row[0]))
        except (TypeError, ValueError):
            return {"scopes": {}, "records": {}}
        if not isinstance(data, dict):
            return {"scopes": {}, "records": {}}
        data.setdefault("scopes", {})
        data.setdefault("records", {})
        return data

    def _save_numbering_conn(self, conn: Any, data: Mapping[str, Any]) -> None:
        conn.execute(
            "INSERT OR REPLACE INTO configuracoes (chave, valor) VALUES (?, ?)",
            (self.NUMBERING_KEY, json.dumps(dict(data), ensure_ascii=False, sort_keys=True)),
        )

    @staticmethod
    def _recover_expired_reservations(data: dict[str, Any], *, now: datetime) -> None:
        for record in data.get("records", {}).values():
            if record.get("status") != "RESERVADO":
                continue
            try:
                expires_at = datetime.fromisoformat(str(record.get("expires_at", "")))
            except ValueError:
                expires_at = now - timedelta(seconds=1)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at <= now:
                record.update({
                    "status": "LIBERADO",
                    "released_at": now.isoformat(),
                    "released_by": "SISTEMA",
                    "release_reason": "Reserva expirada automaticamente.",
                })

    def _get_setting(self, key: str) -> str | None:
        conn = self.connection_factory()
        try:
            row = conn.execute("SELECT valor FROM configuracoes WHERE chave = ?", (str(key),)).fetchone()
            return None if row is None else str(row[0])
        finally:
            conn.close()

    def _set_setting(self, key: str, value: str) -> None:
        conn = self.connection_factory()
        try:
            conn.execute("INSERT OR REPLACE INTO configuracoes (chave, valor) VALUES (?, ?)", (str(key), str(value)))
            conn.commit()
        finally:
            conn.close()
