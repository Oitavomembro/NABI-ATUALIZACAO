from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDockWidget, QWidget

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
) -> tuple[QApplication, PDVWindow]:
    qt_application = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)
    qt_application.setApplicationName("NabiCode")
    qt_application.setOrganizationName("NabiCode")
    window = PDVWindow(
        PDVViewModel(application), cash_label=cash_label, profile_label=profile_label
    )
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
    )
    window.show()
    return qt_application.exec()
