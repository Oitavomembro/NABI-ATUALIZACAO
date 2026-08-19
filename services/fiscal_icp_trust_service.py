from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Iterable

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import dsa, ec, ed25519, ed448, padding, rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID


@dataclass(frozen=True)
class ICPTrustReport:
    trusted: bool
    message: str
    chain: tuple[str, ...] = ()
    anchor: str = ""


class FiscalICPTrustService:
    """Valida a cadeia do A1 contra o repositório público oficial do ITI.

    A validação de confiança não substitui a consulta de revogação (CRL/OCSP),
    que precisa ocorrer no pré-voo online imediatamente anterior à emissão.
    """

    MAX_BUNDLE_BYTES = 5 * 1024 * 1024
    MAX_ENTRIES = 1000
    MAX_CERT_BYTES = 128 * 1024

    def __init__(self, bundle_path: str | Path, *, expected_sha512: str | None = None) -> None:
        self.bundle_path = Path(bundle_path)
        self.expected_sha512 = str(expected_sha512 or "").strip().lower()
        self._catalog: tuple[x509.Certificate, ...] | None = None

    @classmethod
    def from_runtime(cls, runtime_root: str | Path) -> "FiscalICPTrustService":
        directory = Path(runtime_root) / "resources" / "fiscal" / "icp_brasil"
        metadata = json.loads((directory / "catalog.json").read_text(encoding="utf-8"))
        return cls(directory / metadata["file"], expected_sha512=metadata["sha512"])

    def validate_pkcs12(self, pfx_path: str | Path, password: str) -> ICPTrustReport:
        raw = Path(pfx_path).read_bytes()
        try:
            _key, leaf, embedded = pkcs12.load_key_and_certificates(
                raw, str(password).encode("utf-8")
            )
        except ValueError as exc:
            raise ValueError("Senha incorreta ou certificado A1 inválido.") from exc
        if leaf is None:
            raise ValueError("O arquivo A1 não contém certificado.")
        return self.validate_chain(leaf, embedded or ())

    def validate_chain(
        self, leaf: x509.Certificate, intermediates: Iterable[x509.Certificate] = ()
    ) -> ICPTrustReport:
        catalog = self._load_catalog()
        roots = {
            cert.fingerprint(hashes.SHA256()): cert
            for cert in catalog
            if cert.subject == cert.issuer and self._is_ca(cert) and self._signature_valid(cert, cert)
        }
        candidates = tuple(intermediates) + catalog
        now = datetime.now(timezone.utc)
        current = leaf
        chain = [self._label(leaf)]
        visited: set[bytes] = set()
        for _depth in range(12):
            fingerprint = current.fingerprint(hashes.SHA256())
            if fingerprint in visited:
                break
            visited.add(fingerprint)
            if not self._valid_now(current, now):
                return ICPTrustReport(False, f"Certificado fora da validade: {self._label(current)}.", tuple(chain))
            if fingerprint in roots:
                return ICPTrustReport(
                    True,
                    "Cadeia válida até uma AC Raiz oficial da ICP-Brasil.",
                    tuple(chain),
                    self._label(current),
                )
            issuers = [
                cert for cert in candidates
                if cert.subject == current.issuer
                and cert.fingerprint(hashes.SHA256()) not in visited
                and self._is_ca(cert)
                and self._signature_valid(current, cert)
            ]
            if not issuers:
                return ICPTrustReport(
                    False,
                    f"Emissor não encontrado ou assinatura inválida: {current.issuer.rfc4514_string()}.",
                    tuple(chain),
                )
            current = sorted(issuers, key=lambda cert: cert.not_valid_after_utc, reverse=True)[0]
            chain.append(self._label(current))
        return ICPTrustReport(False, "A cadeia do certificado é circular ou excede o limite seguro.", tuple(chain))

    def _load_catalog(self) -> tuple[x509.Certificate, ...]:
        if self._catalog is not None:
            return self._catalog
        if not self.bundle_path.is_file():
            raise ValueError("Catálogo oficial ICP-Brasil não encontrado.")
        if self.bundle_path.stat().st_size > self.MAX_BUNDLE_BYTES:
            raise ValueError("Catálogo ICP-Brasil excede o tamanho seguro.")
        raw = self.bundle_path.read_bytes()
        actual = hashlib.sha512(raw).hexdigest()
        if self.expected_sha512 and actual != self.expected_sha512:
            raise ValueError("Catálogo ICP-Brasil falhou na verificação SHA-512.")
        certificates: list[x509.Certificate] = []
        with zipfile.ZipFile(self.bundle_path) as archive:
            entries = archive.infolist()
            if len(entries) > self.MAX_ENTRIES:
                raise ValueError("Catálogo ICP-Brasil contém arquivos demais.")
            for entry in entries:
                path = PurePosixPath(entry.filename.replace("\\", "/"))
                if path.is_absolute() or ".." in path.parts or entry.file_size > self.MAX_CERT_BYTES:
                    raise ValueError("Catálogo ICP-Brasil contém entrada insegura.")
                if entry.is_dir() or path.suffix.lower() not in {".crt", ".cer", ".pem"}:
                    continue
                data = archive.read(entry)
                try:
                    cert = (
                        x509.load_pem_x509_certificate(data)
                        if b"-----BEGIN CERTIFICATE-----" in data
                        else x509.load_der_x509_certificate(data)
                    )
                except ValueError as exc:
                    raise ValueError(f"Certificado público inválido no catálogo: {entry.filename}.") from exc
                certificates.append(cert)
        if not certificates:
            raise ValueError("Catálogo ICP-Brasil não contém certificados válidos.")
        self._catalog = tuple(certificates)
        return self._catalog

    @staticmethod
    def _label(cert: x509.Certificate) -> str:
        try:
            return str(cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value)
        except (IndexError, AttributeError):
            return cert.subject.rfc4514_string()

    @staticmethod
    def _valid_now(cert: x509.Certificate, now: datetime) -> bool:
        return cert.not_valid_before_utc <= now <= cert.not_valid_after_utc

    @staticmethod
    def _is_ca(cert: x509.Certificate) -> bool:
        try:
            if not cert.extensions.get_extension_for_class(x509.BasicConstraints).value.ca:
                return False
        except x509.ExtensionNotFound:
            return False
        try:
            return cert.extensions.get_extension_for_class(x509.KeyUsage).value.key_cert_sign
        except x509.ExtensionNotFound:
            return True

    @staticmethod
    def _signature_valid(child: x509.Certificate, issuer: x509.Certificate) -> bool:
        try:
            key = issuer.public_key()
            if isinstance(key, rsa.RSAPublicKey):
                key.verify(child.signature, child.tbs_certificate_bytes, padding.PKCS1v15(), child.signature_hash_algorithm)
            elif isinstance(key, ec.EllipticCurvePublicKey):
                key.verify(child.signature, child.tbs_certificate_bytes, ec.ECDSA(child.signature_hash_algorithm))
            elif isinstance(key, dsa.DSAPublicKey):
                key.verify(child.signature, child.tbs_certificate_bytes, child.signature_hash_algorithm)
            elif isinstance(key, (ed25519.Ed25519PublicKey, ed448.Ed448PublicKey)):
                key.verify(child.signature, child.tbs_certificate_bytes)
            else:
                return False
            return True
        except Exception:
            return False
