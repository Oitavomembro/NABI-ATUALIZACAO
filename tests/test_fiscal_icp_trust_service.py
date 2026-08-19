from __future__ import annotations

import hashlib
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

from services.fiscal_icp_trust_service import FiscalICPTrustService


class FiscalICPTrustServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root_dir = Path(self.tmp.name)
        now = datetime.now(timezone.utc)
        self.root_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        root_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "AC Raiz ICP Teste")])
        self.root = self._certificate(root_name, root_name, self.root_key.public_key(), self.root_key, now, ca=True)
        self.intermediate_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        intermediate_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "AC Intermediária Teste")])
        self.intermediate = self._certificate(
            intermediate_name, root_name, self.intermediate_key.public_key(), self.root_key, now,
            ca=True, crl_url="https://teste.invalid/raiz.crl",
        )
        self.leaf_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        leaf_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "EMPRESA TESTE 12345678000195")])
        self.leaf = self._certificate(
            leaf_name, intermediate_name, self.leaf_key.public_key(), self.intermediate_key, now,
            ca=False, crl_url="https://teste.invalid/intermediaria.crl",
        )
        self.bundle = self.root_dir / "catalog.zip"
        with zipfile.ZipFile(self.bundle, "w") as archive:
            archive.writestr("raiz.crt", self.root.public_bytes(serialization.Encoding.DER))
            archive.writestr("intermediaria.crt", self.intermediate.public_bytes(serialization.Encoding.DER))
        self.digest = hashlib.sha512(self.bundle.read_bytes()).hexdigest()

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def _certificate(subject, issuer, public_key, issuer_key, now, *, ca, crl_url=""):
        builder = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(public_key)
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=1))
            .not_valid_after(now + timedelta(days=30))
            .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True)
        )
        if ca:
            builder = builder.add_extension(
                x509.KeyUsage(True, False, False, False, False, True, True, False, False),
                critical=True,
            )
        if crl_url:
            builder = builder.add_extension(
                x509.CRLDistributionPoints([
                    x509.DistributionPoint(
                        full_name=[x509.UniformResourceIdentifier(crl_url)],
                        relative_name=None, reasons=None, crl_issuer=None,
                    )
                ]),
                critical=False,
            )
        return builder.sign(issuer_key, hashes.SHA256())

    @staticmethod
    def _crl(issuer, issuer_key, *, revoked_serial=None, expired=False):
        now = datetime.now(timezone.utc)
        builder = (
            x509.CertificateRevocationListBuilder()
            .issuer_name(issuer.subject)
            .last_update(now - timedelta(days=2 if expired else 1))
            .next_update(now - timedelta(days=1) if expired else now + timedelta(days=1))
        )
        if revoked_serial is not None:
            revoked = (
                x509.RevokedCertificateBuilder()
                .serial_number(revoked_serial)
                .revocation_date(now - timedelta(hours=1))
                .build()
            )
            builder = builder.add_revoked_certificate(revoked)
        return builder.sign(issuer_key, hashes.SHA256()).public_bytes(serialization.Encoding.DER)

    class _Response:
        def __init__(self, content): self.content = content
        def raise_for_status(self): return None

    def test_valida_cadeia_ate_raiz_confiavel(self):
        service = FiscalICPTrustService(self.bundle, expected_sha512=self.digest)
        report = service.validate_chain(self.leaf, [self.intermediate])
        self.assertTrue(report.trusted)
        self.assertEqual(report.anchor, "AC Raiz ICP Teste")
        self.assertEqual(len(report.chain), 3)

    def test_rejeita_certificado_sem_cadeia_oficial(self):
        service = FiscalICPTrustService(self.bundle, expected_sha512=self.digest)
        other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Não confiável")])
        other = self._certificate(name, name, other_key.public_key(), other_key, datetime.now(timezone.utc), ca=False)
        report = service.validate_chain(other)
        self.assertFalse(report.trusted)
        self.assertIn("Emissor não encontrado", report.message)

    def test_rejeita_catalogo_adulterado(self):
        service = FiscalICPTrustService(self.bundle, expected_sha512="0" * 128)
        with self.assertRaisesRegex(ValueError, "SHA-512"):
            service.validate_chain(self.leaf, [self.intermediate])

    def test_le_pkcs12_sem_expor_senha_ou_chave(self):
        pfx = self.root_dir / "teste.pfx"
        pfx.write_bytes(pkcs12.serialize_key_and_certificates(
            b"teste", self.leaf_key, self.leaf, [self.intermediate],
            serialization.BestAvailableEncryption(b"senha-teste"),
        ))
        service = FiscalICPTrustService(self.bundle, expected_sha512=self.digest)
        self.assertTrue(service.validate_pkcs12(pfx, "senha-teste").trusted)

    def test_crls_validas_confirmam_certificado_nao_revogado(self):
        responses = {
            "https://teste.invalid/intermediaria.crl": self._crl(self.intermediate, self.intermediate_key),
            "https://teste.invalid/raiz.crl": self._crl(self.root, self.root_key),
        }
        service = FiscalICPTrustService(
            self.bundle, expected_sha512=self.digest,
            http_get=lambda url, **_kwargs: self._Response(responses[url]),
        )
        report = service.check_chain_revocation([self.leaf, self.intermediate, self.root])
        self.assertTrue(report.good)
        self.assertEqual(len(report.checked), 2)

    def test_crl_rejeita_certificado_revogado(self):
        responses = {
            "https://teste.invalid/intermediaria.crl": self._crl(
                self.intermediate, self.intermediate_key, revoked_serial=self.leaf.serial_number
            ),
            "https://teste.invalid/raiz.crl": self._crl(self.root, self.root_key),
        }
        service = FiscalICPTrustService(
            self.bundle, expected_sha512=self.digest,
            http_get=lambda url, **_kwargs: self._Response(responses[url]),
        )
        report = service.check_chain_revocation([self.leaf, self.intermediate, self.root])
        self.assertEqual(report.status, "REVOKED")

    def test_crl_expirada_falha_fechado(self):
        service = FiscalICPTrustService(
            self.bundle, expected_sha512=self.digest,
            http_get=lambda _url, **_kwargs: self._Response(
                self._crl(self.intermediate, self.intermediate_key, expired=True)
            ),
        )
        report = service.check_chain_revocation([self.leaf, self.intermediate, self.root])
        self.assertEqual(report.status, "UNKNOWN")
        self.assertIn("CRL fora da validade", report.message)


if __name__ == "__main__":
    unittest.main()
