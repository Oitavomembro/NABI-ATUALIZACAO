import tempfile
import unittest
from pathlib import Path

try:
    from PySide6.QtCore import QPoint, QSettings, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QDialog, QLineEdit, QWidget

    from ui_qt.assistant_nabi import (
        NabiFloatingAssistant,
        NabiFloatingCoordinator,
        classify_nabi_overlay,
    )
    QT_AVAILABLE = True
    QT_ERROR = ""
except Exception as error:  # pragma: no cover
    QT_AVAILABLE = False
    QT_ERROR = str(error)


@unittest.skipUnless(QT_AVAILABLE, f"Qt indisponível: {QT_ERROR}")
class NabiFloatingGlobalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        path = Path(self.temporary.name) / "settings.ini"
        self.settings = QSettings(str(path), QSettings.Format.IniFormat)
        self.root = QWidget()
        self.root.resize(900, 700)
        self.root.show()
        self.panel = QWidget()
        self.floating = NabiFloatingAssistant(self.panel, self.root, settings=self.settings)
        self.coordinator = NabiFloatingCoordinator(self.app, self.root, self.floating)
        self.addCleanup(self.root.close)
        QTest.qWait(5)

    def test_clique_abre_sem_arrastar_e_arraste_nao_captura_foco(self):
        field = QLineEdit(self.root)
        field.show()
        field.setFocus()
        QTest.mouseClick(self.floating.launcher, Qt.MouseButton.LeftButton)
        self.assertTrue(self.floating.isExpanded())
        self.floating.collapse()
        field.setFocus()
        center = self.floating.launcher.rect().center()
        QTest.mousePress(self.floating.launcher, Qt.MouseButton.LeftButton, pos=center)
        QTest.mouseMove(self.floating.launcher, center + QPoint(-40, -30), delay=1)
        QTest.mouseRelease(self.floating.launcher, Qt.MouseButton.LeftButton,
                           pos=center + QPoint(-40, -30))
        self.assertIs(self.app.focusWidget(), field)

    def test_clique_programatico_preserva_api_do_botao(self):
        self.floating.launcher.click()
        self.assertTrue(self.floating.isExpanded())

    def test_arraste_nao_abre_e_persiste_posicao(self):
        start = self.floating.pos()
        center = self.floating.launcher.rect().center()
        QTest.mousePress(self.floating.launcher, Qt.MouseButton.LeftButton, pos=center)
        QTest.mouseMove(self.floating.launcher, center + QPoint(-80, -60), delay=1)
        QTest.mouseRelease(self.floating.launcher, Qt.MouseButton.LeftButton,
                           pos=center + QPoint(-80, -60))
        self.assertFalse(self.floating.isExpanded())
        self.assertNotEqual(self.floating.pos(), start)
        self.assertEqual(self.settings.value(self.floating.POSITION_KEY), self.floating.pos())

    def test_restauracao_e_resize_limitam_ao_retangulo_visivel(self):
        self.settings.setValue(self.floating.POSITION_KEY, QPoint(5000, 5000))
        self.floating.restore_position()
        self.assertLessEqual(self.floating.geometry().right(), self.root.contentsRect().right())
        self.assertLessEqual(self.floating.geometry().bottom(), self.root.contentsRect().bottom())
        self.root.resize(360, 260)
        QTest.qWait(5)
        self.assertLessEqual(self.floating.geometry().right(), self.root.contentsRect().right())
        self.assertLessEqual(self.floating.geometry().bottom(), self.root.contentsRect().bottom())

    def test_dialogo_normal_recebe_mesma_instancia_e_retorna_ao_shell(self):
        dialog = QDialog(self.root)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.setModal(False)
        dialog.resize(600, 400)
        dialog.show()
        dialog.activateWindow()
        QTest.qWait(5)
        self.coordinator.refresh()
        self.assertIs(self.floating.parentWidget(), dialog)
        self.assertEqual(len(self.root.findChildren(NabiFloatingAssistant)), 1)
        dialog.close()
        self.root.activateWindow()
        QTest.qWait(5)
        self.coordinator.refresh()
        self.assertIs(self.floating.parentWidget(), self.root)
        self.assertFalse(self.floating.isHidden())

    def test_dialogo_modal_e_sensivel_ocultam_sem_contornar_modalidade(self):
        modal = QDialog(self.root)
        modal.setWindowModality(Qt.WindowModality.ApplicationModal)
        modal.show()
        QTest.qWait(5)
        self.coordinator.refresh()
        self.assertTrue(self.floating.isHidden())
        modal.close()
        sensitive = QDialog(self.root)
        classify_nabi_overlay(sensitive, "login")
        sensitive.show()
        sensitive.activateWindow()
        QTest.qWait(5)
        self.coordinator.refresh()
        self.assertTrue(self.floating.isHidden())

    def test_classificacao_invalida_falha_fechado(self):
        with self.assertRaisesRegex(ValueError, "inválida"):
            classify_nabi_overlay(QDialog(self.root), "livre")

    def test_fechar_shell_remove_imediatamente_o_filtro_global(self):
        self.assertTrue(self.coordinator._installed)

        self.root.close()
        QTest.qWait(1)

        self.assertFalse(self.coordinator._installed)
        self.assertTrue(self.floating.isHidden())

    def test_varios_shells_fechados_nao_deixam_coordenadores_globais(self):
        coordinators = []
        roots = []
        for _index in range(20):
            root = QWidget()
            floating = NabiFloatingAssistant(QWidget(), root, settings=self.settings)
            coordinator = NabiFloatingCoordinator(self.app, root, floating)
            roots.append(root)
            coordinators.append(coordinator)
            root.show()
            root.close()
        QTest.qWait(1)

        self.assertTrue(all(not item._installed for item in coordinators))


if __name__ == "__main__":
    unittest.main()
