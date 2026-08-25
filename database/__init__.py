"""Infraestrutura de acesso e manutenção do banco do NabiCode."""

from .database_manager import DatabaseManager
from .maintenance import DatabaseCheckReport, DatabaseMaintenanceService, Migration

__all__ = ["DatabaseManager", "DatabaseCheckReport", "DatabaseMaintenanceService", "Migration"]

from .sqlite_connection import (
    SQLitePragmaPolicyError, backup_database, connection_session,
    effective_pragmas, open_connection,
)

from .schema_initializer import initialize_database

from .product_decimal_migration import ProductDecimalMigration

from .product_schema_migration import ProductSchemaMigration
