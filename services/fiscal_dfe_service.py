from __future__ import annotations

import base64
import gzip
import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from lxml import etree


@dataclass(frozen=True)
class DFeDistributionResult:
    status_code: str
    message: str
    last_nsu: str
    max_nsu: str
    documents: tuple[dict[str, Any], ...]


class FiscalDFeService:
    """Distribuição nacional de DF-e 1.01 com consumo incremental por NSU."""

    CONFIG_KEY = "fiscal.dfe.distribuicao.v1"
    INDEX_KEY = "fiscal.dfe.documentos.v1"
    VERSION = "1.01"
    MAX_DOCUMENTS = 50
    MAX_COMPRESSED_BYTES = 2 * 1024 * 1024
    MAX_XML_BYTES = 20 * 1024 * 1024
    ALLOWED_SCHEMAS = {
        "resnfe_v1.00.xsd", "procnfe_v4.00.xsd", "resevento_v1.00.xsd",
        "proceventonfe_v1.00.xsd",
    }
    SCHEMA_ROOTS = {
        "resnfe_v1.00.xsd": "resNFe",
        "procnfe_v4.00.xsd": "nfeProc",
        "resevento_v1.00.xsd": "resEvento",
        "proceventonfe_v1.00.xsd": "procEventoNFe",
    }
    ENDPOINTS = {
        "HOMOLOGACAO": "https://hom.nfe.fazenda.gov.br/NFeDistribuicaoDFe/NFeDistribuicaoDFe.asmx",
        "PRODUCAO": "https://www1.nfe.fazenda.gov.br/NFeDistribuicaoDFe/NFeDistribuicaoDFe.asmx",
    }
    SOAP_ACTION = (
        "http://www.portalfiscal.inf.br/nfe/wsdl/"
        "NFeDistribuicaoDFe/nfeDistDFeInteresse"
    )
    MANIFESTATIONS = {
        "CIENCIA": ("210210", "Ciencia da Operacao"),
        "CONFIRMACAO": ("210200", "Confirmacao da Operacao"),
        "DESCONHECIMENTO": ("210220", "Desconhecimento da Operacao"),
        "NAO_REALIZADA": ("210240", "Operacao nao Realizada"),
    }
    CONCLUSIVE = {"CONFIRMACAO", "DESCONHECIMENTO", "NAO_REALIZADA"}

    def __init__(
        self,
        fiscal_service: Any,
        *,
        storage_dir: str | Path,
        actor_provider: Callable[[], str | None] | None = None,
        authorization_provider: Callable[[str], bool] | None = None,
        transport: Callable[..., Any] | None = None,
    ) -> None:
        self.fiscal_service = fiscal_service
        self.storage_dir = Path(storage_dir)
        self._actor_provider = actor_provider
        self._authorization_provider = authorization_provider
        self._transport = transport
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _authenticated_actor(self, action: str) -> str:
        if self._authorization_provider is None:
            raise PermissionError(
                "Uma sessão autenticada com permissão fiscal é obrigatória para manifestar DF-e."
            )
        try:
            authorized = bool(self._authorization_provider(action))
        except PermissionError:
            raise
        except Exception as exc:
            raise PermissionError(
                "Não foi possível confirmar a permissão fiscal para manifestar DF-e."
            ) from exc
        if not authorized:
            raise PermissionError(
                "A sessão autenticada não possui permissão para manifestar DF-e."
            )
        if self._actor_provider is None:
            raise PermissionError(
                "Uma sessão autenticada é obrigatória para manifestar DF-e."
            )
        try:
            actor = str(self._actor_provider() or "").strip()
        except PermissionError:
            raise
        except Exception as exc:
            raise PermissionError(
                "Não foi possível confirmar a identidade autenticada para manifestar DF-e."
            ) from exc
        if not actor:
            raise PermissionError(
                "A sessão autenticada não possui uma identidade válida."
            )
        return actor

    def state(self) -> dict[str, str]:
        raw = self.fiscal_service._get_setting(self.CONFIG_KEY)
        try:
            value = json.loads(raw) if raw else {}
        except (TypeError, ValueError):
            value = {}
        return {
            "last_nsu": self._nsu(value.get("last_nsu", "0")),
            "max_nsu": self._nsu(value.get("max_nsu", "0")),
        }

    def build_request(
        self, *, cnpj: str, state_code: str, environment: str,
        last_nsu: str | None = None, nsu: str | None = None,
        access_key: str | None = None,
    ) -> bytes:
        environment = self._environment(environment)
        document = self.fiscal_service._normalize_cnpj(cnpj)
        if not self.fiscal_service._is_valid_cnpj(document):
            raise ValueError("CNPJ inválido para distribuição de DF-e.")
        state_code = re.sub(r"\D", "", str(state_code or ""))
        if len(state_code) != 2:
            raise ValueError("Código da UF do autor é inválido.")
        choices = sum(value is not None for value in (last_nsu, nsu, access_key))
        if choices != 1:
            raise ValueError("Escolha exatamente uma consulta: último NSU, NSU ou chave.")
        ns = "http://www.portalfiscal.inf.br/nfe"
        root = etree.Element(etree.QName(ns, "distDFeInt"), nsmap={None: ns}, versao=self.VERSION)
        self._element(root, ns, "tpAmb", "1" if environment == "PRODUCAO" else "2")
        self._element(root, ns, "cUFAutor", state_code)
        self._element(root, ns, "CNPJ", document)
        if last_nsu is not None:
            group = etree.SubElement(root, etree.QName(ns, "distNSU"))
            self._element(group, ns, "ultNSU", self._nsu(last_nsu))
        elif nsu is not None:
            group = etree.SubElement(root, etree.QName(ns, "consNSU"))
            self._element(group, ns, "NSU", self._nsu(nsu))
        else:
            key = self.fiscal_service._normalize_access_key(access_key)
            if len(key) != 44 or not self.fiscal_service._is_valid_access_key(key):
                raise ValueError("Chave de acesso inválida para distribuição de DF-e.")
            group = etree.SubElement(root, etree.QName(ns, "consChNFe"))
            self._element(group, ns, "chNFe", key)
        return etree.tostring(root, xml_declaration=True, encoding="utf-8")

    def parse_response(
        self, xml: bytes | str, *, persist: bool = True,
        expected_environment: str | None = None, origin_url: str = "",
        actor: str = "",
    ) -> DFeDistributionResult:
        raw = xml.encode("utf-8") if isinstance(xml, str) else bytes(xml)
        root = etree.fromstring(raw, parser=etree.XMLParser(resolve_entities=False, no_network=True))
        if etree.QName(root).localname != "retDistDFeInt":
            raise ValueError("Resposta DF-e possui elemento raiz inválido.")
        version = str(root.get("versao") or "").strip()
        if version and version != self.VERSION:
            raise ValueError("Resposta DF-e possui versão incompatível.")
        environment = self._environment(expected_environment) if expected_environment else None
        response_environment = self._text(root, "tpAmb")
        if environment and response_environment != ("1" if environment == "PRODUCAO" else "2"):
            raise ValueError("O ambiente da resposta DF-e não corresponde ao ambiente consultado.")
        if origin_url and origin_url != self.ENDPOINTS[environment]:
            raise ValueError("A origem da resposta DF-e não é um endpoint oficial permitido.")
        status = self._text(root, "cStat")
        message = self._text(root, "xMotivo")
        last_nsu = self._nsu(self._text(root, "ultNSU") or "0")
        max_nsu = self._nsu(self._text(root, "maxNSU") or "0")
        if status in {"137", "138"} and int(max_nsu) < int(last_nsu):
            raise ValueError("Resposta DF-e possui sequência máxima inferior ao último NSU.")
        current = self.state() if persist else {"last_nsu": "000000000000000"}
        nodes = root.xpath("//*[local-name()='docZip']")
        if len(nodes) > self.MAX_DOCUMENTS:
            raise ValueError("A resposta DF-e excede o limite de documentos por lote.")
        documents: list[dict[str, Any]] = []
        batch_nsus: set[str] = set()
        for node in nodes:
            nsu = self._nsu(node.get("NSU") or "")
            if nsu in batch_nsus:
                raise ValueError(f"Resposta DF-e repete o NSU {nsu} no mesmo lote.")
            batch_nsus.add(nsu)
            schema = str(node.get("schema") or "").strip()
            if schema.casefold() not in self.ALLOWED_SCHEMAS:
                raise ValueError(f"Schema DF-e não reconhecido: {schema}.")
            try:
                compressed = base64.b64decode("".join(str(node.text or "").split()), validate=True)
            except (ValueError, TypeError) as exc:
                raise ValueError(f"Documento DF-e {nsu} possui Base64 inválido.") from exc
            if not compressed or len(compressed) > self.MAX_COMPRESSED_BYTES:
                raise ValueError(f"Documento DF-e {nsu} excede o tamanho comprimido seguro.")
            try:
                content = gzip.decompress(compressed)
            except (OSError, EOFError) as exc:
                raise ValueError(f"Documento DF-e {nsu} possui GZip inválido.") from exc
            if not content or len(content) > self.MAX_XML_BYTES:
                raise ValueError(f"Documento DF-e {nsu} excede o tamanho XML seguro.")
            content_root = etree.fromstring(
                content, parser=etree.XMLParser(resolve_entities=False, no_network=True)
            )
            if etree.QName(content_root).localname != self.SCHEMA_ROOTS[schema.casefold()]:
                raise ValueError(f"Documento DF-e {nsu} não corresponde ao schema declarado.")
            path = self.storage_dir / f"NSU_{nsu}_{schema.removesuffix('.xsd')}.xml"
            documents.append({
                "nsu": nsu, "schema": schema, "path": str(path) if persist else "",
                "sha256": hashlib.sha256(content).hexdigest(), "xml": content,
            })
        if status in {"137", "138"} and any(
            int(document["nsu"]) > int(last_nsu) for document in documents
        ):
            raise ValueError("A resposta DF-e contém documento acima do último NSU informado.")
        if persist and status in {"137", "138"} and int(last_nsu) < int(current["last_nsu"]):
            raise ValueError("Resposta DF-e tentou regredir o último NSU confirmado.")
        if status in {"137", "138"} and persist:
            index = self._index()
            for document in documents:
                previous = next((
                    row for row in index
                    if row.get("nsu") == document["nsu"] and row.get("schema") == document["schema"]
                ), None)
                if previous and previous.get("sha256") != document["sha256"]:
                    raise ValueError(f"NSU {document['nsu']} já existe com conteúdo divergente.")
                if previous:
                    continue
                self._atomic_write(Path(document["path"]), document["xml"])
                index.append({
                    "nsu": document["nsu"], "schema": document["schema"],
                    "path": document["path"], "sha256": document["sha256"],
                    "origin": origin_url or "RESPOSTA_LOCAL_NAO_TRANSMITIDA",
                    "environment": environment or "NAO_INFORMADO",
                    "received_by": str(actor or "NAO_INFORMADO").strip(),
                    "received_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                })
            self.fiscal_service._set_setting(self.CONFIG_KEY, json.dumps({
                "last_nsu": last_nsu, "max_nsu": max_nsu,
            }, sort_keys=True))
            self.fiscal_service._set_setting(
                self.INDEX_KEY, json.dumps(index[-5000:], ensure_ascii=False, sort_keys=True)
            )
        return DFeDistributionResult(status, message, last_nsu, max_nsu, tuple(documents))

    def next_request(self, *, cnpj: str, state_code: str, environment: str) -> bytes:
        return self.build_request(
            cnpj=cnpj, state_code=state_code, environment=environment,
            last_nsu=self.state()["last_nsu"],
        )

    def fetch_next(self, *, password: str) -> DFeDistributionResult:
        config = self.fiscal_service.load_config()
        environment = self._environment(config.get("environment"))
        actor = self.fiscal_service.require_operational_readiness(
            operation="consulta", model="55", password=password,
            permission="configure",
        )
        cnpj = str(config.get("cnpj") or "")
        normalized_cnpj = self.fiscal_service._normalize_cnpj(cnpj)
        if not self.fiscal_service._is_valid_cnpj(normalized_cnpj):
            raise ValueError("O CNPJ configurado para distribuição DF-e é inválido.")
        state = str(config.get("state") or "").upper()
        state_code = self.fiscal_service.STATE_CODES.get(state, "")
        certificate = str(config.get("certificate_path") or "")
        certificate_info = self.fiscal_service.inspect_certificate(certificate, password)
        certificate_document = self.fiscal_service._normalize_cnpj(
            getattr(certificate_info, "document", "")
        )
        if not certificate_document or certificate_document != normalized_cnpj:
            raise ValueError("O CNPJ do certificado não corresponde à empresa configurada.")
        trust = self.fiscal_service.validate_certificate_trust(certificate, password)
        if not trust.trusted:
            raise ValueError(f"Cadeia ICP-Brasil não confirmada: {trust.message}")
        revocation = self.fiscal_service.check_certificate_revocation(certificate, password)
        if not revocation.good:
            raise ValueError(f"Situação de revogação não confirmada: {revocation.message}")
        request = self.next_request(
            cnpj=cnpj, state_code=state_code, environment=environment
        )
        envelope = self._soap_envelope(request)
        pem_cert, pem_key = self.fiscal_service._temporary_pem_files(certificate, password)
        try:
            endpoint = self.ENDPOINTS[environment]
            transport = self._transport or self.fiscal_service.http_post
            if not callable(transport):
                raise RuntimeError("Transporte DF-e indisponível.")
            response = transport(
                endpoint, data=envelope,
                headers={"Content-Type": "text/xml; charset=utf-8", "SOAPAction": self.SOAP_ACTION},
                cert=(pem_cert, pem_key), timeout=45,
            )
            response.raise_for_status()
            return self.parse_response(
                response.content, persist=True,
                expected_environment=environment, origin_url=endpoint, actor=str(actor or ""),
            )
        finally:
            self.fiscal_service._secure_delete_file(pem_cert)
            self.fiscal_service._secure_delete_file(pem_key)

    def list_documents(self) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for record in reversed(self._index()):
            path = Path(str(record.get("path") or ""))
            try:
                raw = path.read_bytes()
                if hashlib.sha256(raw).hexdigest() != record.get("sha256"):
                    continue
                root = etree.fromstring(raw, parser=etree.XMLParser(resolve_entities=False, no_network=True))
            except (OSError, etree.XMLSyntaxError):
                continue
            key = self._text(root, "chNFe")
            if not key:
                identifier = str(root.xpath("string(//*[local-name()='infNFe'][1]/@Id)") or "")
                key = identifier.removeprefix("NFe")
            rows.append({
                "nsu": str(record.get("nsu") or ""), "access_key": key,
                "issuer": self._text(root, "xNome"), "document": self._text(root, "CNPJ"),
                "issued_at": self._text(root, "dhEmi"), "total": self._text(root, "vNF"),
                "path": str(path), "schema": str(record.get("schema") or ""),
                "sha256": str(record.get("sha256") or ""),
            })
        return rows

    def _index(self) -> list[dict[str, Any]]:
        raw = self.fiscal_service._get_setting(self.INDEX_KEY)
        try:
            value = json.loads(raw) if raw else []
        except (TypeError, ValueError):
            value = []
        return [dict(row) for row in value if isinstance(row, dict)] if isinstance(value, list) else []

    def build_manifestation(
        self, *, access_key: str, cnpj: str, environment: str,
        kind: str, justification: str = "",
    ) -> tuple[bytes, str]:
        environment = self._environment(environment)
        key = self.fiscal_service._normalize_access_key(access_key)
        if len(key) != 44 or not self.fiscal_service._is_valid_access_key(key):
            raise ValueError("Chave inválida para manifestação do destinatário.")
        document = self.fiscal_service._normalize_cnpj(cnpj)
        if not self.fiscal_service._is_valid_cnpj(document):
            raise ValueError("CNPJ inválido para manifestação do destinatário.")
        kind = str(kind or "").strip().upper()
        if kind not in self.MANIFESTATIONS:
            raise ValueError("Manifestação deve ser Ciência, Confirmação, Desconhecimento ou Não Realizada.")
        if kind == "NAO_REALIZADA" and len(str(justification or "").strip()) < 15:
            raise ValueError("Operação não realizada exige justificativa com ao menos 15 caracteres.")
        code, description = self.MANIFESTATIONS[kind]
        ns = "http://www.portalfiscal.inf.br/nfe"
        event_id = f"ID{code}{key}01"
        root = etree.Element(etree.QName(ns, "evento"), nsmap={None: ns}, versao="1.00")
        info = etree.SubElement(root, etree.QName(ns, "infEvento"), Id=event_id)
        values = (
            ("cOrgao", key[:2]),
            ("tpAmb", "1" if environment == "PRODUCAO" else "2"),
            ("CNPJ", document), ("chNFe", key),
            ("dhEvento", datetime.now().astimezone().isoformat(timespec="seconds")),
            ("tpEvento", code), ("nSeqEvento", "1"), ("verEvento", "1.00"),
        )
        for name, value in values:
            self._element(info, ns, name, value)
        detail = etree.SubElement(info, etree.QName(ns, "detEvento"), versao="1.00")
        self._element(detail, ns, "descEvento", description)
        if kind == "NAO_REALIZADA":
            self._element(detail, ns, "xJust", str(justification).strip())
        return etree.tostring(root, xml_declaration=True, encoding="utf-8"), event_id

    def send_manifestation(
        self, *, access_key: str, kind: str, password: str,
        justification: str = "",
    ) -> tuple[Any, dict[str, Any]]:
        actor = self._authenticated_actor("transmit")
        self.fiscal_service.require_operational_readiness(
            operation="evento", model="55", password=password,
            permission="transmit",
        )
        key = self.fiscal_service._normalize_access_key(access_key)
        if not any(row.get("access_key") == key for row in self.list_documents()):
            raise ValueError("A NF-e recebida não foi localizada na distribuição DF-e.")
        normalized_kind = str(kind or "").strip().upper()
        existing = [
            row for row in self.fiscal_service.list_events(key)
            if row.get("success") and str(row.get("event_type") or "").startswith("MANIFESTACAO_")
        ]
        if normalized_kind == "CIENCIA" and any(row.get("event_type") == "MANIFESTACAO_CIENCIA" for row in existing):
            raise ValueError("A Ciência da Operação já foi registrada.")
        if normalized_kind in self.CONCLUSIVE and any(
            str(row.get("event_type") or "").removeprefix("MANIFESTACAO_") in self.CONCLUSIVE
            for row in existing
        ):
            raise ValueError("A NF-e já possui manifestação conclusiva registrada.")
        config = self.fiscal_service.load_config()
        xml, event_id = self.build_manifestation(
            access_key=key, cnpj=config.get("cnpj", ""), environment=config.get("environment", ""),
            kind=normalized_kind, justification=justification,
        )
        signed = self.fiscal_service.sign_xml(
            xml, reference_id=event_id,
            pfx_path=config.get("certificate_path", ""), password=password,
        )
        envelope = self.fiscal_service._event_envelope(signed)
        response = self.fiscal_service.transmit(
            operation="evento", model="55", xml=envelope,
            pfx_path=config.get("certificate_path", ""), password=password,
        )
        record = self.fiscal_service.register_event(
            access_key=key, event_type=f"MANIFESTACAO_{normalized_kind}",
            response=response, request_xml=envelope, actor=actor,
        )
        return response, record

    @staticmethod
    def _soap_envelope(request: bytes) -> bytes:
        soap = "http://schemas.xmlsoap.org/soap/envelope/"
        wsdl = "http://www.portalfiscal.inf.br/nfe/wsdl/NFeDistribuicaoDFe"
        envelope = etree.Element(etree.QName(soap, "Envelope"), nsmap={"soap": soap})
        body = etree.SubElement(envelope, etree.QName(soap, "Body"))
        operation = etree.SubElement(body, etree.QName(wsdl, "nfeDistDFeInteresse"))
        data = etree.SubElement(operation, etree.QName(wsdl, "nfeDadosMsg"))
        data.append(etree.fromstring(request, parser=etree.XMLParser(resolve_entities=False, no_network=True)))
        return etree.tostring(envelope, xml_declaration=True, encoding="utf-8")

    @staticmethod
    def _nsu(value: Any) -> str:
        digits = re.sub(r"\D", "", str(value or ""))
        if len(digits) > 15:
            raise ValueError("NSU deve possuir no máximo 15 dígitos.")
        return digits.zfill(15)

    @classmethod
    def _environment(cls, value: Any) -> str:
        environment = str(value or "").strip().upper()
        if environment not in cls.ENDPOINTS:
            raise ValueError("Ambiente DF-e deve ser HOMOLOGACAO ou PRODUCAO.")
        return environment

    @staticmethod
    def _text(root: Any, name: str) -> str:
        return str(root.xpath(f"string(//*[local-name()='{name}'][1])") or "").strip()

    @staticmethod
    def _element(parent: Any, namespace: str, name: str, value: Any) -> Any:
        node = etree.SubElement(parent, etree.QName(namespace, name))
        node.text = str(value)
        return node

    @staticmethod
    def _atomic_write(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        temporary.write_bytes(data)
        temporary.replace(path)
