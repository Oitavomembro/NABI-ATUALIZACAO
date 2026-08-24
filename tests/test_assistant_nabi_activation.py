from __future__ import annotations

import unittest
from threading import Event, Thread

from assistant_nabi import AuthenticatedAssistantActivation


class Security:
    def __init__(self, *, accepted=True):
        self.accepted = accepted
        self.calls = []

    def authenticate(self, username, password):
        self.calls.append(("authenticate", username, password))
        return object() if self.accepted else None

    def logout(self, reason):
        self.calls.append(("logout", reason))


class Runtime:
    def __init__(self, *, fail_start=False):
        self.fail_start = fail_start
        self.started = 0
        self.stopped = 0

    def start(self):
        self.started += 1
        if self.fail_start:
            raise RuntimeError("runtime inválido")

    def create_model_adapter(self):
        return "modelo-local"

    def stop(self):
        self.stopped += 1


class AuthenticatedAssistantActivationTests(unittest.TestCase):
    def create(self, *, accepted=True, fail_start=False):
        security = Security(accepted=accepted)
        runtime = Runtime(fail_start=fail_start)
        factory_calls = []

        def assistant_factory(model, session_id):
            factory_calls.append((model, session_id))
            return "assistente"

        activation = AuthenticatedAssistantActivation(
            security_service=security,
            runtime_factory=lambda: runtime,
            assistant_factory=assistant_factory,
        )
        return activation, security, runtime, factory_calls

    def test_autentica_antes_de_iniciar_runtime_e_cria_sessao_unica(self):
        activation, security, runtime, calls = self.create()
        self.assertEqual(activation.activate(" operador ", "segredo"), "assistente")
        self.assertEqual(security.calls[0], ("authenticate", "operador", "segredo"))
        self.assertEqual(runtime.started, 1)
        self.assertEqual(calls[0][0], "modelo-local")
        self.assertEqual(len(calls[0][1]), 32)
        self.assertTrue(activation.active)
        with self.assertRaisesRegex(RuntimeError, "já está ativa"):
            activation.activate("operador", "segredo")

    def test_credencial_invalida_nao_inicia_runtime(self):
        activation, _, runtime, calls = self.create(accepted=False)
        with self.assertRaisesRegex(PermissionError, "inválidos"):
            activation.activate("operador", "errada")
        self.assertEqual(runtime.started, 0)
        self.assertEqual(calls, [])
        self.assertFalse(activation.active)

    def test_falha_do_runtime_encerra_e_invalida_sessao(self):
        activation, security, runtime, calls = self.create(fail_start=True)
        with self.assertRaisesRegex(RuntimeError, "runtime inválido"):
            activation.activate("operador", "segredo")
        self.assertEqual(runtime.stopped, 1)
        self.assertEqual(calls, [])
        self.assertIn(("logout", "IA_NABI_ATIVACAO_FALHOU"), security.calls)
        self.assertFalse(activation.active)

    def test_stop_encerra_runtime_e_sessao(self):
        activation, security, runtime, _ = self.create()
        activation.activate("operador", "segredo")
        activation.stop()
        self.assertEqual(runtime.stopped, 1)
        self.assertIn(("logout", "IA_NABI_ENCERRADA"), security.calls)
        self.assertFalse(activation.active)

    def test_stop_com_sessao_compartilhada_nao_desloga_o_sistema(self):
        security = Security()
        runtime = Runtime()
        activation = AuthenticatedAssistantActivation(
            security_service=security,
            runtime_factory=lambda: runtime,
            assistant_factory=lambda model, session_id: "assistente",
            logout_on_stop=False,
        )
        activation.activate("operador", "segredo")
        activation.stop()
        self.assertEqual(runtime.stopped, 1)
        self.assertFalse(any(call[0] == "logout" for call in security.calls))

    def test_falha_com_sessao_compartilhada_nao_desloga_o_sistema(self):
        security = Security()
        runtime = Runtime(fail_start=True)
        activation = AuthenticatedAssistantActivation(
            security_service=security,
            runtime_factory=lambda: runtime,
            assistant_factory=lambda model, session_id: "assistente",
            logout_on_stop=False,
        )
        with self.assertRaisesRegex(RuntimeError, "runtime inválido"):
            activation.activate("operador", "segredo")
        self.assertFalse(any(call[0] == "logout" for call in security.calls))

    def test_parar_durante_carregamento_impede_ativacao_tardia(self):
        entered = Event()
        release = Event()
        security = Security()
        runtime = Runtime()
        original_start = runtime.start

        def blocked_start():
            original_start()
            entered.set()
            release.wait(2)

        runtime.start = blocked_start
        activation = AuthenticatedAssistantActivation(
            security_service=security,
            runtime_factory=lambda: runtime,
            assistant_factory=lambda model, session_id: "assistente",
        )
        errors = []

        def activate():
            try:
                activation.activate("operador", "segredo")
            except Exception as error:
                errors.append(error)

        thread = Thread(target=activate)
        thread.start()
        self.assertTrue(entered.wait(1))
        activation.stop()
        release.set()
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(errors), 1)
        self.assertIn("cancelada", str(errors[0]))
        self.assertEqual(runtime.stopped, 1)
        self.assertFalse(activation.active)
        self.assertIn(("logout", "IA_NABI_ATIVACAO_FALHOU"), security.calls)


if __name__ == "__main__":
    unittest.main()
