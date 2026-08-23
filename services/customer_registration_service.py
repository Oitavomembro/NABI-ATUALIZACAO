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

    def next_record_number(self) -> int:
        """Retorna a próxima ficha configurada pela autoridade cadastral."""
        return max(1, int(self.get_config("proxima_ficha") or 5500))

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
        email: str = "",
        inscricao_estadual: str = "",
        contribuinte_icms: bool = False,
        fiscal_logradouro: str = "",
        fiscal_numero: str = "",
        fiscal_bairro: str = "",
        fiscal_codigo_municipio: str = "",
        fiscal_municipio: str = "",
        fiscal_uf: str = "",
        fiscal_cep: str = "",
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
            "email": str(email or "").strip(),
            "inscricao_estadual": str(inscricao_estadual or "").strip(),
            "contribuinte_icms": 1 if contribuinte_icms else 0,
            "fiscal_logradouro": str(fiscal_logradouro or "").strip(),
            "fiscal_numero": str(fiscal_numero or "").strip(),
            "fiscal_bairro": str(fiscal_bairro or "").strip(),
            "fiscal_codigo_municipio": "".join(ch for ch in str(fiscal_codigo_municipio or "") if ch.isdigit()),
            "fiscal_municipio": str(fiscal_municipio or "").strip(),
            "fiscal_uf": str(fiscal_uf or "").strip().upper(),
            "fiscal_cep": "".join(ch for ch in str(fiscal_cep or "") if ch.isdigit()),
        }
        if dados["fiscal_uf"] and len(dados["fiscal_uf"]) != 2:
            raise ValueError("UF fiscal do cliente deve possuir duas letras.")
        if dados["fiscal_codigo_municipio"] and len(dados["fiscal_codigo_municipio"]) != 7:
            raise ValueError("Código IBGE do município deve possuir 7 dígitos.")
        if dados["fiscal_cep"] and len(dados["fiscal_cep"]) != 8:
            raise ValueError("CEP fiscal deve possuir 8 dígitos.")
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

    def editar(
        self,
        cliente_id: int,
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
    ) -> None:
        normalized_id = int(cliente_id)
        if normalized_id <= 0:
            raise ValueError("Cliente inválido.")
        dados = {
            "numero_ficha": CustomerValidator.parse_record_number(numero_ficha),
            "codigo": str(codigo or "").strip(),
            "nome": CustomerValidator.normalize_name(nome),
            "cpf": str(cpf or "").strip(),
            "rg": str(rg or "").strip(),
            "telefone": str(telefone or "").strip(),
            "endereco": str(endereco or "").strip(),
            "observacoes": str(observacoes or "").strip(),
            "limite": CustomerValidator.parse_credit_limit(limite),
        }
        with self.repository.transaction() as connection:
            if dados["numero_ficha"] is not None and self.repository.ficha_existe(
                dados["numero_ficha"],
                ignorar_cliente_id=normalized_id,
                connection=connection,
            ):
                raise ValueError("Esta ficha já existe. Escolha outro número.")
            self.repository.atualizar_cadastro(normalized_id, dados, connection=connection)

        atual = int(self.get_config("proxima_ficha") or 5500)
        if dados["numero_ficha"] is not None and dados["numero_ficha"] >= atual:
            self.set_config("proxima_ficha", str(dados["numero_ficha"] + 1))
        if self.history_callback:
            self.history_callback(normalized_id, "EDIÇÃO", "Dados cadastrais atualizados.")

    def atualizar_perfil_fiscal(self, customer_id: int, **values: Any) -> None:
        data = {
            "email": str(values.get("email") or "").strip(),
            "inscricao_estadual": str(values.get("inscricao_estadual") or "").strip(),
            "contribuinte_icms": 1 if values.get("contribuinte_icms") else 0,
            "fiscal_logradouro": str(values.get("fiscal_logradouro") or "").strip(),
            "fiscal_numero": str(values.get("fiscal_numero") or "").strip(),
            "fiscal_bairro": str(values.get("fiscal_bairro") or "").strip(),
            "fiscal_codigo_municipio": "".join(ch for ch in str(values.get("fiscal_codigo_municipio") or "") if ch.isdigit()),
            "fiscal_municipio": str(values.get("fiscal_municipio") or "").strip(),
            "fiscal_uf": str(values.get("fiscal_uf") or "").strip().upper(),
            "fiscal_cep": "".join(ch for ch in str(values.get("fiscal_cep") or "") if ch.isdigit()),
        }
        if data["fiscal_uf"] and len(data["fiscal_uf"]) != 2:
            raise ValueError("UF fiscal do cliente deve possuir duas letras.")
        if data["fiscal_codigo_municipio"] and len(data["fiscal_codigo_municipio"]) != 7:
            raise ValueError("Código IBGE do município deve possuir 7 dígitos.")
        if data["fiscal_cep"] and len(data["fiscal_cep"]) != 8:
            raise ValueError("CEP fiscal deve possuir 8 dígitos.")
        if data["contribuinte_icms"] and not data["inscricao_estadual"]:
            raise ValueError("Cliente contribuinte de ICMS exige inscrição estadual.")
        self.repository.atualizar_perfil_fiscal(int(customer_id), data)
