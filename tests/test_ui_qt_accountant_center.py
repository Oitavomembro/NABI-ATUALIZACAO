from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import pytest
pytest.importorskip("PySide6")
from PySide6.QtCore import QEvent,Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QCheckBox, QLabel, QLineEdit

from commercial.application.accountant_center_dto import AccountantPackagePlan
from commercial.application.accountant_center_service import CompanyIdentity
from ui_qt.commercial.accountant_center_dialog import AccountantCenterDialog


APP=QApplication.instance() or QApplication([])


class Application:
    def __init__(self):self.reviews=0;self.generations=0;self.status="PENDENTE"
    def company_identity(self):
        return CompanyIdentity("12345678000195", "EMPRESA TESTE LTDA", "cadastro central")
    def review(self,**kwargs):
        self.reviews+=1
        return AccountantPackagePlan.create(cnpj="12345678000195",competence="2026-08",profile=kwargs["profile"],output_path=kwargs["output_path"],reviewed_by="operador")
    def generate(self,plan):
        self.generations+=1
        return SimpleNamespace(path=plan.output_path,cnpj=plan.cnpj,competence=plan.competence,profile=plan.profile,status=self.status,movements=12,files=30,pendencies=4,package_sha256="a"*64)


class Pool:
    def __init__(self,automatic=True):self.workers=[];self.automatic=automatic
    def start(self,worker):
        self.workers.append(worker)
        if self.automatic:worker.run()


def enter(*,shift=False,repeat=False):
    modifiers=Qt.KeyboardModifier.ShiftModifier if shift else Qt.KeyboardModifier.NoModifier
    return QKeyEvent(QEvent.Type.KeyPress,Qt.Key.Key_Return,modifiers,"\r",repeat,1)


def ready(dialog,tmp_path):
    dialog.output.setText(str(tmp_path/"pacote.zip"));dialog._review()


def test_dois_caminhos_principais_e_auditoria_avancada(tmp_path):
    dialog=AccountantCenterDialog(Application(),worker_pool=Pool())
    assert dialog.essential.text().startswith("PACOTE ESSENCIAL")
    assert dialog.complete.text().startswith("PACOTE COMPLETO") and dialog.audit.isHidden()
    dialog.advanced.setChecked(True); assert not dialog.audit.isHidden()
    assert "todos os totais e movimentos" in dialog.explanation.text();dialog.close()


def test_revisar_nao_gera_e_enter_gera_exatamente_uma_vez(tmp_path):
    application=Application();dialog=AccountantCenterDialog(application,worker_pool=Pool());ready(dialog,tmp_path)
    assert application.reviews==1 and application.generations==0 and dialog.generate_button.isEnabled()
    dialog.eventFilter(dialog.generate_button,enter());assert application.generations==1
    assert dialog.semaphore.text().startswith("PENDENTE") and "12" in dialog.details.text();dialog.close()


def test_auto_repeat_shift_enter_e_alteracao_invalidam_revisao(tmp_path):
    application=Application();dialog=AccountantCenterDialog(application,worker_pool=Pool());ready(dialog,tmp_path)
    dialog.eventFilter(dialog.generate_button,enter(repeat=True));assert application.generations==0
    dialog.generate_button.setFocus();dialog.eventFilter(dialog.generate_button,enter(shift=True));assert application.generations==0
    dialog.output.setText(str(tmp_path/"outro.zip"));assert dialog._plan is None and not dialog.generate_button.isEnabled();dialog.close()


def test_bloqueio_reentrada_resposta_atrasada_e_fechamento(tmp_path):
    application=Application();pool=Pool(False);dialog=AccountantCenterDialog(application,worker_pool=pool);ready(dialog,tmp_path);dialog._generate();dialog._generate()
    assert len(pool.workers)==1
    old=dialog._generation-1;dialog._completed(old,SimpleNamespace(status="CONCILIADO"),None);assert "CONCILIADO" not in dialog.semaphore.text()
    generation=dialog._generation;dialog.close();assert dialog._generation>generation
    pool.workers[0].run();assert application.generations==1


def test_status_divergente_e_erro_sao_honestos(tmp_path):
    application=Application();application.status="DIVERGENTE";dialog=AccountantCenterDialog(application,worker_pool=Pool());ready(dialog,tmp_path);dialog._generate();assert dialog.semaphore.text().startswith("DIVERGENTE");dialog.close()


def test_cnpj_e_somente_rotulo_sem_checkbox_ou_entrada_manual():
    dialog=AccountantCenterDialog(Application(),worker_pool=Pool())
    assert isinstance(dialog.cnpj,QLabel)
    assert dialog.cnpj.text()=="12.345.678/0001-95"
    assert dialog.cnpj.textInteractionFlags()==Qt.TextInteractionFlag.NoTextInteraction
    assert "Origem comprovada: cadastro central" in dialog.identity_source.text()
    assert not hasattr(dialog,"cnpj_confirmed")
    assert all(widget is not dialog.cnpj for widget in dialog.findChildren(QLineEdit))
    assert not any("CNPJ" in widget.text() for widget in dialog.findChildren(QCheckBox))
    dialog.close()


def test_identidade_indisponivel_bloqueia_revisao():
    application=Application()
    application.company_identity=lambda: (_ for _ in ()).throw(RuntimeError("CNPJ divergente entre fontes"))
    dialog=AccountantCenterDialog(application,worker_pool=Pool())
    assert not dialog.review.isEnabled()
    assert "indisponível" in dialog.cnpj.text().casefold()
    assert "divergente" in dialog.identity_source.text().casefold()
    dialog.close()


def test_entrega_so_abre_por_clique_depois_de_geracao_bem_sucedida(tmp_path):
    delivery = Mock()
    dialog = AccountantCenterDialog(
        Application(), worker_pool=Pool(), delivery_application=delivery
    )
    assert not dialog.delivery_button.isEnabled()
    ready(dialog, tmp_path)
    assert not dialog.delivery_button.isEnabled()
    dialog._generate()
    assert dialog.delivery_button.isEnabled()
    with patch("ui_qt.commercial.accountant_delivery_dialog.AccountantDeliveryDialog") as dialog_type:
        dialog._open_delivery()
    dialog_type.assert_called_once()
    dialog_type.return_value.exec.assert_called_once_with()
    delivery.assert_not_called()
    dialog.close()


def test_gui_nao_importa_banco_fiscal_ia_shell_ou_main():
    from pathlib import Path
    source=Path(__file__).parents[1].joinpath("ui_qt/commercial/accountant_center_dialog.py").read_text(encoding="utf-8").lower()
    for forbidden in ("sqlite3","database","fiscal_service","sefaz","assistant_nabi","main_qt","shell"):
        assert forbidden not in source
