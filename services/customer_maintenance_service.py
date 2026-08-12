from __future__ import annotations

import csv
from pathlib import Path

from database import DatabaseManager
from repositories.customer_maintenance_repository import CustomerMaintenanceRepository


class CustomerMaintenanceService:
    """Operações administrativas de clientes fora da camada gráfica."""

    DEMO_CUSTOMERS = (
        ("CLI001", 1, "Ana Souza", "111.111.111-11", "11.111.111-1", "(11) 98888-1111", "Rua das Flores, 10", "Cliente fictício para testes", 1200.0, 0.0, 1),
        ("CLI002", 2, "Bruno Lima", "222.222.222-22", "22.222.222-2", "(11) 97777-2222", "Av. Central, 250", "Recebe no dia 5", 800.0, 185.0, 1),
        ("CLI003", 3, "Carla Mendes", "333.333.333-33", "33.333.333-3", "(11) 96666-3333", "Rua do Comércio, 75", "Prefere contato por telefone", 1500.0, 640.0, 1),
    )

    CSV_HEADER = (
        "Ficha",
        "Código",
        "Nome",
        "CPF",
        "RG",
        "Telefone",
        "Endereço",
        "Limite",
        "Saldo",
        "Observações",
    )

    def __init__(
        self,
        database: DatabaseManager,
        repository: CustomerMaintenanceRepository | None = None,
    ) -> None:
        self.repository = repository or CustomerMaintenanceRepository(database)

    def delete_fictitious_customers(self) -> int:
        """Remove clientes fictícios e seus vínculos transacionais."""
        return self.repository.delete_fictitious()

    def recreate_demo_customers(self) -> int:
        """Recria os cadastros de demonstração de forma idempotente."""
        return self.repository.create_missing_demo_customers(self.DEMO_CUSTOMERS)

    def export_csv(self, destination: str | Path) -> Path:
        path = Path(destination).expanduser().resolve()
        if path.suffix.lower() != ".csv":
            path = path.with_suffix(".csv")
        path.parent.mkdir(parents=True, exist_ok=True)

        rows = self.repository.export_rows()
        temporary = path.with_name(f".{path.name}.tmp")
        try:
            with temporary.open("w", newline="", encoding="utf-8-sig") as output:
                writer = csv.writer(output, delimiter=";")
                writer.writerow(self.CSV_HEADER)
                writer.writerows(tuple(row) for row in rows)
                output.flush()
            temporary.replace(path)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        return path
