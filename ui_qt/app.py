from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from commercial.application.pdv_application_service import PDVApplicationService

from .commercial.pdv_view_model import PDVViewModel
from .commercial.pdv_window import PDVWindow


def create_application(application: PDVApplicationService, argv=None) -> tuple[QApplication, PDVWindow]:
    qt_application = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)
    qt_application.setApplicationName("NabiCode")
    qt_application.setOrganizationName("NabiCode")
    window = PDVWindow(PDVViewModel(application))
    return qt_application, window


def run(application: PDVApplicationService, argv=None) -> int:
    qt_application, window = create_application(application, argv)
    window.show()
    return qt_application.exec()
