"""Entrada distribuível do NabiCode Qt.

Mantém o ciclo de atualização e o mutex do instalador fora da aplicação Qt,
sem reativar a interface Legacy como tela principal.
"""

from __future__ import annotations

import logging

from main import (
    _acquire_installer_app_mutex,
    _release_installer_app_mutex,
    _run_update_helper,
)


def main() -> int:
    update_result = _run_update_helper()
    if update_result is not None:
        return update_result

    installer_mutex = None
    try:
        installer_mutex = _acquire_installer_app_mutex()
        from main_qt import main as run_qt

        return run_qt()
    except OSError as error:
        logging.getLogger("NabiCode.Qt").exception(
            "Não foi possível registrar o processo para o instalador"
        )
        raise SystemExit(
            "O Windows não permitiu iniciar o NabiCode com proteção de "
            f"atualização/desinstalação: {error}"
        ) from error
    finally:
        _release_installer_app_mutex(installer_mutex)


if __name__ == "__main__":
    raise SystemExit(main())
