from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QApplication, QDialog, QDockWidget, QMessageBox, QToolBar, QWidget

from commercial.application.pdv_application_service import PDVApplicationService

from .commercial.pdv_view_model import PDVViewModel
from .commercial.pdv_window import PDVWindow
from .assistant_nabi import NabiAssistantPanel


def create_application(
    application: PDVApplicationService,
    argv=None,
    *,
    cash_label: str = "Caixa ativo",
    profile_label: str = "COMERCIAL / NÃO FISCAL",
    assistant_service=None,
    assistant_activation=None,
    nfe_entry_service=None,
    assistant_panel_factory=None,
    administrative_hub_factory=None,
) -> tuple[QApplication, PDVWindow]:
    qt_application = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)
    qt_application.setApplicationName("NabiCode")
    qt_application.setOrganizationName("NabiCode")
    window = PDVWindow(
        PDVViewModel(application), cash_label=cash_label, profile_label=profile_label
    )
    if administrative_hub_factory is not None:
        toolbar = QToolBar("NabiCode", window)
        toolbar.setObjectName("nabicodeModulesToolbar")
        toolbar.setMovable(False)
        action = QAction("Módulos  [F1]", window)
        action.setShortcut(QKeySequence("F1"))
        action.setAutoRepeat(False)
        state = {"open": False}

        def open_hub():
            if state["open"]:
                return
            state["open"] = True
            try:
                hub = administrative_hub_factory(window)
                if not isinstance(hub, QDialog):
                    raise TypeError("O hub deve ser uma janela Qt.")
                hub.exec()
            except Exception as error:
                QMessageBox.warning(window, "Módulos NabiCode", str(error))
            finally:
                state["open"] = False

        action.triggered.connect(open_hub)
        toolbar.addAction(action)
        window.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)
        window.nabicode_modules_toolbar = toolbar
        window.nabicode_modules_action = action
        window.open_administrative_hub = open_hub
    if assistant_service is not None and assistant_panel_factory is not None:
        window.close()
        raise ValueError("Forneça o serviço da Nabi ou uma fábrica de painel, não ambos.")
    if assistant_service is not None or assistant_panel_factory is not None:
        if assistant_panel_factory is not None:
            panel = assistant_panel_factory(window)
            if not isinstance(panel, QWidget):
                window.close()
                raise TypeError("A fábrica do painel da Nabi deve retornar um QWidget.")
        else:
            panel = NabiAssistantPanel(
                assistant_service, window, activation_manager=assistant_activation,
                draft_transfer=window.load_assistant_draft,
                nfe_entry_service=nfe_entry_service,
                product_search_opener=getattr(
                    window, "open_assistant_product_search", None
                ),
                module_hub_opener=getattr(window, "open_administrative_hub", None),
            )
        dock = QDockWidget("Nabi", window)
        dock.setObjectName("nabiAssistantDock")
        dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        dock.setWidget(panel)
        window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        window.nabi_assistant_dock = dock
    return qt_application, window


def run(
    application: PDVApplicationService,
    argv=None,
    *,
    cash_label: str = "Caixa ativo",
    profile_label: str = "COMERCIAL / NÃO FISCAL",
    assistant_service=None,
    assistant_activation=None,
    nfe_entry_service=None,
    assistant_panel_factory=None,
    administrative_hub_factory=None,
) -> int:
    qt_application, window = create_application(
        application,
        argv,
        cash_label=cash_label,
        profile_label=profile_label,
        assistant_service=assistant_service,
        assistant_activation=assistant_activation,
        nfe_entry_service=nfe_entry_service,
        assistant_panel_factory=assistant_panel_factory,
        administrative_hub_factory=administrative_hub_factory,
    )
    window.show()
    return qt_application.exec()
