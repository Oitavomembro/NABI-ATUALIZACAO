from __future__ import annotations

import unittest
from unittest import mock

from services.printing_service import PrintingService


class PrintingServiceTests(unittest.TestCase):
    def test_format_uses_defaults_and_rejects_invalid_config(self):
        values = {"formato_impressao_recibo": "INVALIDO", "formato_impressao_ficha": "PDF virtual"}
        service = PrintingService(values.get)
        self.assertEqual(service.output_format("recibo"), "Cupom 80 mm")
        self.assertEqual(service.output_format("movimento"), "Cupom 80 mm")
        self.assertEqual(service.output_format("ficha"), "PDF virtual")

    def test_legacy_58mm_config_is_migrated_in_memory_to_80mm(self):
        service = PrintingService({"formato_impressao_recibo": "Cupom 58 mm"}.get)
        self.assertEqual(service.output_format("recibo"), "Cupom 80 mm")
        self.assertNotIn("Cupom 58 mm", service.VALID_FORMATS)

    def test_wrap_receipt_preserves_separators_and_width(self):
        result = PrintingService.wrap_receipt_text("ABC\n----------\ntexto muito comprido", 16)
        lines = result.splitlines()
        self.assertEqual(lines[1], "-" * 16)
        self.assertTrue(all(len(line) <= 16 for line in lines if line))

    def test_wrap_receipt_rejects_unusable_width(self):
        with self.assertRaises(ValueError):
            PrintingService.wrap_receipt_text("x", 8)


    def test_raw_payload_uses_cp850_crlf_and_single_partial_cut(self):
        values = {
            "impressao_corte_automatico": "1",
            "impressao_linhas_antes_corte": "2",
            "impressao_tipo_corte": "PARCIAL",
        }
        service = PrintingService(values.get)

        payload = service._raw_payload("Olá\nMundo")

        assert payload.startswith("Olá\r\nMundo".encode("cp850"))
        assert payload.endswith((b"\r\n" * 2) + service._ESC_POS_CUT_PARTIAL)
        assert payload.count(service._ESC_POS_CUT_PARTIAL) == 1

    def test_raw_payload_total_cut_and_feed_are_bounded(self):
        values = {
            "impressao_corte_automatico": "true",
            "impressao_linhas_antes_corte": "99",
            "impressao_tipo_corte": "TOTAL",
        }
        service = PrintingService(values.get)

        payload = service._raw_payload("Cupom")

        assert payload == b"Cupom" + (b"\r\n" * 12) + service._ESC_POS_CUT_TOTAL

    def test_raw_payload_does_not_append_cut_when_disabled(self):
        values = {"impressao_corte_automatico": "0"}
        service = PrintingService(values.get)

        payload = service._raw_payload("Cupom\n")

        assert payload == b"Cupom\r\n"
        assert service._ESC_POS_CUT_PARTIAL not in payload
        assert service._ESC_POS_CUT_TOTAL not in payload

    def test_non_windows_has_only_system_default_and_direct_print_is_blocked(self):
        service = PrintingService()
        with mock.patch("services.printing_service.os.name", "posix"):
            self.assertEqual(service.list_printers(), ["Padrão do Sistema"])
            self.assertTrue(service.is_available("Padrão do Sistema"))
            with self.assertRaises(RuntimeError):
                service.print_raw_text("teste")
            with self.assertRaises(RuntimeError):
                service.print_a4_text("teste")


if __name__ == "__main__":
    unittest.main()
