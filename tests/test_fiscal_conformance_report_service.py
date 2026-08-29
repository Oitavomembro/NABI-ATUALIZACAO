from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import unittest

from services.fiscal_conformance_report_service import FiscalConformanceReportService
from services.fiscal_regulatory_catalog_service import FiscalRegulatoryCatalogService


class FiscalConformanceReportServiceTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        regulatory = FiscalRegulatoryCatalogService(
            runtime_root=root, today_provider=lambda: date(2026, 8, 29)
        )
        self.service = FiscalConformanceReportService(regulatory)

    def test_snapshot_declara_limites_sem_prometer_producao(self):
        report = self.service.snapshot()
        self.assertTrue(report.ready_for_local_homologation)
        self.assertEqual(report.jurisdiction, "BR-BA")
        self.assertEqual(report.models, ("55", "65"))
        self.assertTrue(report.production_blocked)
        self.assertIn("general_tax_matrix", report.blocked_operations)
        self.assertIn("rtc_special_regimes", report.blocked_operations)
        self.assertIn("selective_tax", report.blocked_operations)
        self.assertIn("5102", report.automated_sale_cfops)
        self.assertIn("6102", report.automated_sale_cfops)
        self.assertIn("102", report.supported_icms_codes)
        self.assertIn("00", report.supported_icms_codes)
        self.assertIn("000/000001:NACIONAL", report.rtc_profiles)
        self.assertIn("410/410004:EXPORTACAO", report.rtc_profiles)
        self.assertEqual(len(report.snapshot_sha256), 64)

    def test_exportacao_e_deterministica_e_auditavel(self):
        first = self.service.export_json()
        second = self.service.export_json()
        self.assertEqual(first, second)
        payload = json.loads(first)
        self.assertEqual(payload["schema"], "nabicode.fiscal-conformance-report.v1")
        self.assertTrue(payload["mandatory_manual_gates"])
        self.assertNotIn("password", first.casefold())
        self.assertNotIn("certificate_path", first)

    def test_relatorio_reflete_catalogo_regulatorio_invalido(self):
        root = Path(__file__).resolve().parents[1]
        regulatory = FiscalRegulatoryCatalogService(
            runtime_root=root, expected_sha256="0" * 64,
            today_provider=lambda: date(2026, 8, 29),
        )
        report = FiscalConformanceReportService(regulatory).snapshot()
        self.assertFalse(report.ready_for_local_homologation)
        self.assertTrue(report.regulatory_problems)
        self.assertTrue(report.production_blocked)


if __name__ == "__main__":
    unittest.main()
