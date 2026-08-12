from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import Any

from repositories import ClienteRepository
from validators import CustomerValidator


class CustomerRegistrationService:
    """Regras de cadastro de clientes sem dependência da interface gráfica."""

    def __init__(
        self,
        repository: ClienteRepository,
        *,
        get_config: Callable[[str], Any],
        set_config: Callable[[str, str], None],
        history_callback: Callable[[int, str, str], None] | None = None,
        now: Callable[[], datetime] = datetime.now,
    ) -> None:
        self.repository = repository
        self.get_config = get_config
        self.set_config = set_config
        self.history_callback = history_callback
        self.now = now

    def criar(
        self,
        *,
        nome: str,
        codigo: str = "",
        numero_ficha: int | str | None = None,
        cpf: str = "",
        rg: str = "",
        telefone: str = "",
        endereco: str = "",
        observacoes: str = "",
        limite: Decimal | float | str = Decimal("0"),
    ) -> int:
        nome_limpo = CustomerValidator.normalize_name(nome)
        ficha = CustomerValidator.parse_record_number(numero_ficha)
        limite_valor = CustomerValidator.parse_credit_limit(limite)
        codigo_limpo = str(codigo or "").strip() or f"CLI{self.now().strftime('%H%M%S')}"
        dados = {
            "codigo": codigo_limpo,
            "numero_ficha": ficha,
            "nome": nome_limpo,
            "cpf": str(cpf or "").strip(),
            "rg": str(rg or "").strip(),
            "telefone": str(telefone or "").strip(),
            "endereco": str(endereco or "").strip(),
            "observacoes": str(observacoes or "").strip(),
            "limite": limite_valor,
            "saldo_devedor": 0.0,
        }
        with self.repository.transaction() as connection:
            if ficha is not None and self.repository.ficha_existe(ficha, connection=connection):
                raise ValueError("Esta ficha já existe. Escolha outro número.")
            cliente_id = self.repository.criar(dados, connection=connection)

        atual = int(self.get_config("proxima_ficha") or 5500)
        if ficha is not None and ficha >= atual:
            self.set_config("proxima_ficha", str(ficha + 1))
        if self.history_callback:
            self.history_callback(cliente_id, "CADASTRO", "Cadastro criado.")
        return cliente_id
