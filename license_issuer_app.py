"""Entrada gráfica exclusiva do emissor externo NabiCode V2."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from license_issuer.ui_qt import LicenseIssuerWindow


def main(argv=None) -> int:
    app = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)
    window = LicenseIssuerWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
