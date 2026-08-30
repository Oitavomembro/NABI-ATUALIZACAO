from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QToolBar, QWidget

from commercial.application.pdv_application_service import PDVApplicationService

from .commercial.pdv_view_model import PDVViewModel
from .commercial.pdv_window import PDVWindow
from .assistant_nabi import NabiAssistantPanel, NabiFloatingAssistant, NabiFloatingCoordinator
from .shell import NabiCodeShellWindow
from .backup_startup import DailyBackupController


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
    auto_activate_assistant=False,
    fiscal_mode=False,
    fiscal_sale_service=None,
    fiscal_outbox_worker=None,
) -> tuple[QApplication, PDVWindow]:
    qt_application = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)
    qt_application.setApplicationName("NabiCode")
    qt_application.setOrganizationName("NabiCode")
    window = PDVWindow(
        PDVViewModel(application), cash_label=cash_label, profile_label=profile_label,
        fiscal_mode=fiscal_mode,
        fiscal_sale_service=fiscal_sale_service,
        fiscal_outbox_worker=fiscal_outbox_worker,
        require_registered_customer=False,
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
                auto_activate=auto_activate_assistant,
            )
        floating = NabiFloatingAssistant(panel, window)
        window.nabi_assistant = floating
        window.nabi_assistant_coordinator = NabiFloatingCoordinator(qt_application, window, floating)
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


def create_shell_application(
    application: PDVApplicationService,
    security,
    modules,
    argv=None,
    *,
    store_name: str = "NabiCode",
    cash_label: str = "Caixa ativo",
    profile_label: str = "COMERCIAL / NÃO FISCAL",
    assistant_service=None,
    assistant_activation=None,
    nfe_entry_service=None,
    assistant_panel_factory=None,
    reauthenticate=None,
    daily_backup_service=None,
    visual_preferences=None,
    auto_activate_assistant=False,
    fiscal_mode=False,
    fiscal_sale_service=None,
    fiscal_outbox_worker=None,
):
    """Cria o shell Legacy; o PDV só nasce quando Vendas/F2 for acionado."""

    qt_application = QApplication.instance() or QApplication(
        argv if argv is not None else sys.argv
    )
    qt_application.setApplicationName("NabiCode")
    qt_application.setOrganizationName("NabiCode")

    def authorize_fiscal_cancellation(parent) -> bool:
        if reauthenticate is None or not bool(reauthenticate(parent)):
            raise PermissionError(
                "Informe a senha de um administrador autorizado para cancelar documentos fiscais."
            )
        if security.session is None or security.is_expired():
            raise PermissionError("A autenticação administrativa não foi confirmada.")
        if not security.require("fiscal", "transmit"):
            raise PermissionError(
                "O usuário autenticado não possui permissão para cancelamento fiscal."
            )
        security.touch()
        return True

    def pdv_factory():
        return PDVWindow(
            PDVViewModel(application),
            cash_label=cash_label,
            profile_label=profile_label,
            fiscal_mode=fiscal_mode,
            fiscal_sale_service=fiscal_sale_service,
            fiscal_outbox_worker=fiscal_outbox_worker,
            fiscal_cancellation_authorizer=authorize_fiscal_cancellation,
            require_registered_customer=False,
        )

    window = NabiCodeShellWindow(
        security,
        tuple(modules),
        pdv_factory,
        store_name=store_name,
        profile_label=profile_label,
        reauthenticate=reauthenticate,
        visual_preferences=visual_preferences,
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
            def transfer_draft(draft):
                pdv = window.ensure_pdv()
                if pdv is None:
                    raise RuntimeError("Não foi possível abrir Vendas.")
                return pdv.load_assistant_draft(draft)

            def open_product_search(*args, **kwargs):
                pdv = window.ensure_pdv()
                if pdv is None:
                    raise RuntimeError("Não foi possível abrir Vendas.")
                return pdv.open_assistant_product_search(*args, **kwargs)

            panel = NabiAssistantPanel(
                assistant_service,
                window,
                activation_manager=assistant_activation,
                draft_transfer=transfer_draft,
                nfe_entry_service=nfe_entry_service,
                product_search_opener=open_product_search,
                module_hub_opener=lambda: window.show_module("dashboard"),
                fiscal_configuration_opener=window.open_fiscal_configuration,
                company_xml_import_opener=window.open_company_xml_import,
                product_xml_import_opener=window.open_product_xml_import,
                auto_activate=auto_activate_assistant,
            )
        floating = NabiFloatingAssistant(panel, window)
        window.nabi_assistant = floating
    if daily_backup_service is not None:
        window.daily_backup_controller = DailyBackupController(
            daily_backup_service, window
        )
    if assistant_service is not None or assistant_panel_factory is not None:
        window.nabi_assistant_coordinator = NabiFloatingCoordinator(qt_application, window, floating)
    return qt_application, window


def run_shell(application, security, modules, argv=None, **kwargs) -> int:
    qt_application, window = create_shell_application(
        application, security, modules, argv, **kwargs
    )
    window.showMaximized()
    controller = getattr(window, "daily_backup_controller", None)
    if controller is not None:
        controller.start()
    fiscal_worker = kwargs.get("fiscal_outbox_worker")
    if fiscal_worker is not None:
        fiscal_worker.start()
        qt_application.aboutToQuit.connect(fiscal_worker.stop)
    return qt_application.exec()
