from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from build_tools.demo_splash_login import SplashLoginDemo


APP = QApplication.instance() or QApplication([])


def _settings(tmp_path):
    return QSettings(str(tmp_path / "demo.ini"), QSettings.Format.IniFormat)


def test_animacao_continua_enquanto_usuario_demora(tmp_path):
    demo = SplashLoginDemo(lambda _u, _p: True, settings=_settings(tmp_path))
    demo.show(); APP.processEvents()
    for _ in range(5):
        demo._animate()
    assert demo.animation_frames == 5
    assert demo.isVisible()
    demo.close()


def test_fecha_somente_quando_login_e_sistema_estao_prontos(tmp_path):
    demo = SplashLoginDemo(lambda u, p: (u, p) == ("maria", "segredo"), settings=_settings(tmp_path))
    demo.show(); demo.username.setText("maria"); demo.password.setText("segredo")
    demo.authenticate(); APP.processEvents()
    assert demo.authenticated is True and demo.isVisible()
    assert demo.password.text() == ""
    demo.set_system_ready(); APP.processEvents()
    assert not demo.isVisible()


def test_sistema_pronto_aguarda_login_e_nunca_lembra_senha(tmp_path):
    settings = _settings(tmp_path)
    demo = SplashLoginDemo(lambda _u, _p: True, settings=settings)
    demo.show(); demo.set_system_ready(); APP.processEvents()
    assert demo.isVisible()
    demo.username.setText("joao"); demo.password.setText("senha"); demo.remember.setChecked(True)
    demo.authenticate(); APP.processEvents()
    assert settings.value("remembered_username") == "joao"
    assert settings.value("password") is None
    assert demo.password.text() == ""


def test_falha_fica_no_painel_sem_expor_excecao(tmp_path):
    def fail(_u, _p):
        raise RuntimeError("detalhe secreto")

    demo = SplashLoginDemo(fail, settings=_settings(tmp_path))
    demo.username.setText("x"); demo.password.setText("y"); demo.authenticate()
    assert demo.status.text() == "Usuário ou senha inválidos."
    assert "secreto" not in demo.status.text()
    demo.close()
