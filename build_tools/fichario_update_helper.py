from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from services.update_package_service import apply_prepared_update, rollback_prepared_update


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--pid", required=True, type=int)
    parser.add_argument("--launcher", required=True)
    parser.add_argument("--source-main")
    parser.add_argument("--process-started-at", type=float)
    parser.add_argument("--rollback", action="store_true")
    args = parser.parse_args(argv)
    if getattr(sys, "frozen", False):
        state_path = Path(args.state).expanduser().resolve()
        allowed_root = (
            Path(os.environ.get("APPDATA") or Path.home())
            / "NabiCode" / "Fichario"
        ).resolve()
        try:
            state_path.relative_to(allowed_root)
        except ValueError as exc:
            raise SystemExit("Estado de atualização fora da área persistente do Fichário.") from exc
        if state_path.name != "estado_atualizacao.json":
            raise SystemExit("Nome inválido para o estado da atualização.")
        install_dir = Path(sys.executable).resolve().parent
        version = next(
            (path.read_text(encoding="utf-8-sig").strip() for path in (
                install_dir / "VERSAO.txt", install_dir / "_internal" / "VERSAO.txt",
            ) if path.is_file()),
            "",
        )
        pinned_launcher = install_dir / f"NabiCode_Fichario_v{version.replace('.', '_')}.exe"
        if not version or not pinned_launcher.is_file():
            raise SystemExit("Executável principal do Fichário não foi encontrado.")
        args.state = str(state_path)
        args.launcher = str(pinned_launcher)
        args.source_main = None
    operation = rollback_prepared_update if args.rollback else apply_prepared_update
    return operation(
        args.state, pid=args.pid, launcher=args.launcher,
        source_main=args.source_main, process_started_at=args.process_started_at,
        use_shell_broker=bool(getattr(sys, "frozen", False)),
    )


if __name__ == "__main__":
    raise SystemExit(main())
