from __future__ import annotations

import unittest
from datetime import datetime

from services.license_service import LicenseService


class LicenseServiceTests(unittest.TestCase):
    def service(self, values, now):
        def get(key):
            return values.get(key, "")
        def set_(key, value):
            values[key] = value
        return LicenseService(get, set_, now=lambda: now)

    def test_expiracao_exata_bloqueia(self):
        values = {"licenca_expira_em": "2026-08-02T12:00:00"}
        status = self.service(values, datetime(2026, 8, 2, 12, 0, 1)).evaluate()
        self.assertTrue(status.blocked)
        self.assertEqual(values["licenca_bloqueada"], "1")

    def test_validade_diaria_inclui_final_do_dia(self):
        values = {"licenca_validade": "2026-08-02"}
        status = self.service(values, datetime(2026, 8, 2, 23, 59, 59)).evaluate()
        self.assertFalse(status.blocked)
        self.assertEqual(status.days_remaining, 0)

    def test_monitor_limpa_data_invalida_sem_bloquear(self):
        values = {"licenca_expira_em": "invalida"}
        status = self.service(values, datetime(2026, 8, 2, 10, 0, 0)).monitor_exact_expiration()
        self.assertFalse(status.blocked)
        self.assertTrue(status.invalid_value)
        self.assertEqual(values["licenca_expira_em"], "")

    def test_monitor_expirado_limpa_data_e_bloqueia(self):
        values = {"licenca_expira_em": "2026-08-02T09:00:00"}
        status = self.service(values, datetime(2026, 8, 2, 10, 0, 0)).monitor_exact_expiration()
        self.assertTrue(status.blocked)
        self.assertEqual(values["licenca_bloqueada"], "1")
        self.assertEqual(values["licenca_expira_em"], "")

    def test_modalidades_reais_nos_limites_de_tempo(self):
        cases = (
            (
                "teste_exato_antes",
                {"licenca_expira_em": "2026-08-02T12:00:00"},
                datetime(2026, 8, 2, 11, 59, 59),
                False,
                "ATIVA_EXATA",
            ),
            (
                "teste_exato_no_limite",
                {"licenca_expira_em": "2026-08-02T12:00:00"},
                datetime(2026, 8, 2, 12, 0, 0),
                True,
                "EXPIRACAO_EXATA",
            ),
            (
                "teste_exato_depois",
                {"licenca_expira_em": "2026-08-02T12:00:00"},
                datetime(2026, 8, 2, 12, 0, 1),
                True,
                "EXPIRACAO_EXATA",
            ),
            (
                "diaria_no_ultimo_segundo",
                {"licenca_validade": "2026-08-02"},
                datetime(2026, 8, 2, 23, 59, 59),
                False,
                "ATIVA",
            ),
            (
                "diaria_no_ultimo_microssegundo",
                {"licenca_validade": "2026-08-02"},
                datetime(2026, 8, 2, 23, 59, 59, 999999),
                False,
                "ATIVA",
            ),
            (
                "diaria_exatamente_na_meia_noite",
                {"licenca_validade": "2026-08-02"},
                datetime(2026, 8, 3, 0, 0, 0),
                True,
                "VALIDADE_EXPIRADA",
            ),
            (
                "bloqueio_manual",
                {"licenca_bloqueada": "1", "licenca_validade": "2099-01-01"},
                datetime(2026, 8, 2, 10, 0, 0),
                True,
                "BLOQUEADA",
            ),
            (
                "sem_validade",
                {},
                datetime(2026, 8, 2, 10, 0, 0),
                False,
                "SEM_VALIDADE",
            ),
        )
        for name, values, now, blocked, reason in cases:
            with self.subTest(name=name):
                status = self.service(dict(values), now).evaluate()
                self.assertEqual(status.blocked, blocked)
                self.assertEqual(status.reason, reason)

    def test_senha_errada_nao_persiste_e_senha_correta_libera(self):
        now = datetime(2026, 8, 2, 10, 0, 0)
        values = {
            "licenca_bloqueada": "1",
            "licenca_expira_em": "2026-08-02T09:00:00",
            "licenca_validade": "2026-08-01",
        }
        service = self.service(values, now)
        before = dict(values)
        self.assertFalse(service.attempt_admin_unlock("errada", lambda value: value == "correta"))
        self.assertEqual(values, before)

        self.assertTrue(service.attempt_admin_unlock("correta", lambda value: value == "correta"))
        self.assertEqual(values["licenca_bloqueada"], "0")
        self.assertEqual(values["licenca_expira_em"], "")
        self.assertEqual(values["licenca_validade"], "2026-09-01")
        restarted = self.service(values, datetime(2026, 8, 3, 8, 0, 0)).evaluate()
        self.assertFalse(restarted.blocked)

    def test_licenca_expirada_permanece_bloqueada_ate_liberacao_valida(self):
        values = {"licenca_validade": "2026-08-01", "licenca_bloqueada": "0"}
        service = self.service(values, datetime(2026, 8, 2, 0, 0, 0))
        self.assertTrue(service.evaluate().blocked)
        self.assertTrue(service.evaluate().blocked)
        self.assertEqual(values["licenca_bloqueada"], "1")


if __name__ == "__main__":
    unittest.main()
