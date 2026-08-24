from __future__ import annotations

from datetime import datetime

from database.schema_initializer import initialize_database
from database.sqlite_connection import backup_database


SCHEMA_VERSION = 21


def schema_version(database) -> int:
    if not database.database_path.exists(): return 0
    try:
        row = database.fetch_one(
            "SELECT valor FROM configuracoes WHERE chave='db_schema_version'"
        )
        return int(row[0]) if row else 0
    except Exception:
        return 0


def initialize_fichario_database(database, profile) -> None:
    last_update = {"executada": False, "de": 0, "para": SCHEMA_VERSION, "backup": ""}

    def backup_before_update(previous: int, target: int) -> str:
        profile.paths.backups.mkdir(parents=True, exist_ok=True)
        destination = profile.paths.backups / (
            f"pre_fichario_schema_{previous}_{target}_{datetime.now():%Y%m%d_%H%M%S}.db"
        )
        backup_database(database.database_path, destination)
        return str(destination)

    initialize_database(
        db_name=str(database.database_path), backup_dir=str(profile.paths.backups),
        pdf_dir=str(profile.paths.pdfs), schema_version=SCHEMA_VERSION,
        last_database_update=last_update, network_mode=False, network_role="local",
        connect=database.connect, read_existing_version=lambda: schema_version(database),
        backup_before_update=backup_before_update,
    )
