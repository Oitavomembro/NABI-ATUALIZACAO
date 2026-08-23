"""Backup seguro disponível mesmo quando a licença operacional está bloqueada."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

from core.runtime_profile import configure_profile_environment
from services.backup_service import BackupService


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Modo restrito de preservação de dados")
    parser.add_argument("--profile", choices=("TESTE", "PRODUCAO"), default="PRODUCAO")
    parser.add_argument("--backup", action="store_true", required=True)
    parser.add_argument("--destination")
    options = parser.parse_args(argv)
    os.environ["NABICODE_PROFILE"] = options.profile
    profile = configure_profile_environment(options.profile)
    database = profile.validate_database(profile.paths.database)
    destination = (
        Path(options.destination).expanduser().resolve()
        if options.destination else profile.paths.backups
    )
    service = BackupService(
        database_path=database, default_directory=profile.paths.backups,
        get_config=lambda _key: "", set_config=lambda _key, _value: None,
    )
    created = service.create(destination, prefix="backup_modo_restrito")
    print(json.dumps({"created": created, "at": datetime.now().isoformat()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
