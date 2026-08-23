from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from assistant_nabi import (
    AssistantActor, DraftConfirmationService, SaleDraft, SaleDraftItem,
)


def draft(fingerprint="a" * 64):
    item = SaleDraftItem(1, "P1", "Café", Decimal("1"), Decimal("10"), Decimal("10"), Decimal("5"), Decimal("4"))
    return SaleDraft("draft-1", fingerprint, None, "PIX", (item,), Decimal("10"))


class Clock:
    def __init__(self): self.now = datetime(2026, 8, 23, tzinfo=timezone.utc)
    def __call__(self): return self.now


class DraftConfirmationTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.service = DraftConfirmationService(ttl_seconds=30, clock=self.clock)
        self.actor = AssistantActor("operador", "OPERADOR", "sessao-1")

    def test_confirma_uma_unica_vez_e_vincula_usuario_sessao_e_hash(self):
        current = draft()
        challenge = self.service.issue(current, actor=self.actor)
        result = self.service.confirm(token=challenge.token, draft=current, actor=self.actor)
        self.assertEqual(result.fingerprint, current.fingerprint)
        self.assertEqual(result.session_id, "sessao-1")
        with self.assertRaisesRegex(PermissionError, "já foi utilizada"):
            self.service.confirm(token=challenge.token, draft=current, actor=self.actor)

    def test_expiracao_consumo_e_troca_de_sessao_falham_fechado(self):
        current = draft()
        expired = self.service.issue(current, actor=self.actor)
        self.clock.now += timedelta(seconds=30)
        with self.assertRaisesRegex(PermissionError, "expirou"):
            self.service.confirm(token=expired.token, draft=current, actor=self.actor)
        challenge = self.service.issue(current, actor=self.actor)
        other = AssistantActor("operador", "OPERADOR", "sessao-2")
        with self.assertRaisesRegex(PermissionError, "outro usuário ou sessão"):
            self.service.confirm(token=challenge.token, draft=current, actor=other)

    def test_qualquer_mudanca_do_rascunho_invalida_confirmacao(self):
        current = draft()
        challenge = self.service.issue(current, actor=self.actor)
        changed = replace(current, fingerprint="b" * 64)
        with self.assertRaisesRegex(PermissionError, "mudou"):
            self.service.confirm(token=challenge.token, draft=changed, actor=self.actor)

    def test_nova_revisao_invalida_desafio_anterior_e_parar_invalida_sessao(self):
        current = draft()
        first = self.service.issue(current, actor=self.actor)
        second = self.service.issue(current, actor=self.actor)
        with self.assertRaises(PermissionError):
            self.service.confirm(token=first.token, draft=current, actor=self.actor)
        self.service.invalidate_session(self.actor.session_id)
        with self.assertRaises(PermissionError):
            self.service.confirm(token=second.token, draft=current, actor=self.actor)


if __name__ == "__main__": unittest.main()
