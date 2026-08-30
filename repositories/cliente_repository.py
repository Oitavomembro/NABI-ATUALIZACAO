from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any
import unicodedata

from database import DatabaseManager


@dataclass(frozen=True)
class ClienteSuggestion:
    id: int
    codigo: str
    nome: str
    numero_ficha: int | None
    cpf: str
    telefone: str


@dataclass(frozen=True)
class ClientePage:
    rows: list[tuple[Any, ...]]
    total: int
    total_pages: int
    page: int
    offset: int
    per_page: int


class ClienteRepository:
    """Consultas de clientes isoladas da camada gráfica."""

    def __init__(self, database: DatabaseManager) -> None:
        self.database = database

    @staticmethod
    def _clean_term(term: str | None) -> str:
        return " ".join(str(term or "").strip().lower().split())


    @staticmethod
    def _normalize_search(value: str | None) -> str:
        normalized = unicodedata.normalize("NFKD", str(value or ""))
        return "".join(ch for ch in normalized if not unicodedata.combining(ch)).casefold().strip()

    @classmethod
    def sort_sales_rows(cls, rows: list[Any], term: str) -> list[Any]:
        term_normalized = cls._normalize_search(term)

        def sort_key(row: Any) -> tuple[Any, ...]:
            name_normalized = cls._normalize_search(row[2])
            position = name_normalized.find(term_normalized) if term_normalized else 0
            group = position if position >= 0 else 10_000
            return (group, name_normalized, cls._normalize_search(row[1]), int(row[0]))

        return sorted(rows, key=sort_key)

    def search_sales_suggestions(self, term: str, *, limit: int = 30) -> list[ClienteSuggestion]:
        clean_term = str(term or "").strip()
        if not clean_term:
            return []
        limit = max(1, min(int(limit), 200))
        search = f"%{clean_term}%"
        numeric_term = "".join(character for character in clean_term if character.isdigit())
        rows = self.database.fetch_all(
            """
            SELECT id, codigo, nome, numero_ficha, cpf, telefone
            FROM clientes
            WHERE nome LIKE ? COLLATE NOCASE
               OR codigo LIKE ? COLLATE NOCASE
               OR CAST(numero_ficha AS TEXT) LIKE ?
               OR cpf LIKE ?
               OR telefone LIKE ?
            ORDER BY
                CASE
                    WHEN CAST(COALESCE(numero_ficha, '') AS TEXT) = ? THEN 0
                    WHEN codigo = ? COLLATE NOCASE THEN 1
                    WHEN nome = ? COLLATE NOCASE THEN 2
                    WHEN nome LIKE ? COLLATE NOCASE THEN 3
                    WHEN INSTR(' ' || LOWER(TRIM(COALESCE(nome, ''))),
                               ' ' || LOWER(?)) > 0 THEN 4
                    WHEN INSTR(LOWER(COALESCE(nome, '')), LOWER(?)) > 0 THEN 5
                    ELSE 6
                END,
                nome COLLATE NOCASE,
                CASE WHEN numero_ficha IS NULL THEN 1 ELSE 0 END,
                numero_ficha,
                id
            LIMIT ?
            """,
            (
                search, search, search, search, search,
                numeric_term or "__NO_NUMERIC_MATCH__", clean_term, clean_term,
                f"{clean_term}%", clean_term, clean_term, limit,
            ),
        )
        return [
            ClienteSuggestion(
                id=int(row[0]),
                codigo=str(row[1] or ""),
                nome=str(row[2] or ""),
                numero_ficha=int(row[3]) if row[3] not in (None, "") else None,
                cpf=str(row[4] or ""),
                telefone=str(row[5] or ""),
            )
            for row in rows
        ]

    def resolve_sales_reference(self, reference: str) -> ClienteSuggestion | None:
        """Resolve somente uma referência exata exibida ou digitada no PDV."""
        text = str(reference or "").strip()
        if not text:
            return None
        identifier, separator, displayed_name = text.partition(" — ")
        if separator:
            rows = self.database.fetch_all(
                """SELECT id, codigo, nome, numero_ficha, cpf, telefone
                     FROM clientes
                    WHERE nome = ? COLLATE NOCASE
                      AND (codigo = ? COLLATE NOCASE OR CAST(numero_ficha AS TEXT) = ?)
                    LIMIT 2""",
                (displayed_name.strip(), identifier.strip(), identifier.strip()),
            )
        else:
            rows = self.database.fetch_all(
                """SELECT id, codigo, nome, numero_ficha, cpf, telefone
                     FROM clientes
                    WHERE codigo = ? COLLATE NOCASE
                       OR nome = ? COLLATE NOCASE
                       OR CAST(numero_ficha AS TEXT) = ?
                    LIMIT 2""",
                (text, text, text),
            )
        if len(rows) > 1:
            raise ValueError("Referência de cliente ambígua; selecione o cliente na lista.")
        if not rows:
            return None
        row = rows[0]
        return ClienteSuggestion(
            id=int(row[0]), codigo=str(row[1] or ""), nome=str(row[2] or ""),
            numero_ficha=int(row[3]) if row[3] not in (None, "") else None,
            cpf=str(row[4] or ""), telefone=str(row[5] or ""),
        )

    def list_page(
        self,
        term: str = "",
        *,
        favorites_only: bool = False,
        page: int = 0,
        per_page: int = 250,
    ) -> ClientePage:
        per_page = max(1, min(int(per_page), 2000))
        requested_page = max(0, int(page))
        clean_term = self._clean_term(term)

        filters: list[str] = []
        params: list[Any] = []
        if clean_term:
            search = f"%{clean_term}%"
            filters.append(
                """(LOWER(CAST(numero_ficha AS TEXT)) LIKE ?
                    OR LOWER(COALESCE(codigo, '')) LIKE ?
                    OR LOWER(COALESCE(nome, '')) LIKE ?
                    OR LOWER(COALESCE(cpf, '')) LIKE ?
                    OR LOWER(COALESCE(rg, '')) LIKE ?
                    OR LOWER(COALESCE(telefone, '')) LIKE ?
                    OR LOWER(COALESCE(endereco, '')) LIKE ?
                    OR LOWER(COALESCE(observacoes, '')) LIKE ?)"""
            )
            params.extend([search] * 8)
        if favorites_only:
            filters.append("COALESCE(favorito, 0) = 1")

        where_sql = (" WHERE " + " AND ".join(filters)) if filters else ""

        sql = """
            SELECT id, numero_ficha, nome, saldo_devedor, limite,
                   telefone, cpf, COALESCE(favorito, 0)
            FROM clientes
        """ + where_sql
        query_params = list(params)
        if clean_term:
            numeric_term = "".join(ch for ch in clean_term if ch.isdigit()) or "__NO_NUMERIC_MATCH__"
            sql += """ ORDER BY
                CASE
                    WHEN CAST(COALESCE(numero_ficha, '') AS TEXT) = ? THEN 0
                    WHEN LOWER(TRIM(COALESCE(nome, ''))) = ? THEN 1
                    WHEN REPLACE(REPLACE(REPLACE(COALESCE(cpf, ''), '.', ''), '-', ''), ' ', '') = ? THEN 2
                    WHEN LOWER(TRIM(COALESCE(nome, ''))) LIKE ? THEN 3
                    WHEN INSTR(' ' || LOWER(TRIM(COALESCE(nome, ''))), ' ' || ?) > 0 THEN 4
                    WHEN INSTR(LOWER(COALESCE(nome, '')), ?) > 0 THEN 5
                    ELSE 6
                END ASC,
                nome COLLATE NOCASE ASC,
                CASE WHEN numero_ficha IS NULL THEN 1 ELSE 0 END ASC,
                numero_ficha ASC
            """
            query_params.extend(
                [
                    numeric_term,
                    clean_term,
                    numeric_term,
                    f"{clean_term}%",
                    clean_term,
                    clean_term,
                ]
            )
        else:
            sql += (
                " ORDER BY (numero_ficha IS NULL) ASC, numero_ficha ASC, "
                "nome COLLATE NOCASE ASC, id ASC"
            )
        with self.database.session() as connection:
            # Snapshot curto e sempre novo: evita qualquer estado em memória e garante
            # que contagem e linhas pertençam à mesma visão após o commit financeiro.
            connection.execute("BEGIN")
            count_row = connection.execute(
                "SELECT COUNT(*) AS total FROM clientes" + where_sql,
                tuple(params),
            ).fetchone()
            total = int((count_row["total"] if count_row else 0) or 0)
            total_pages = max(1, (total + per_page - 1) // per_page)
            current_page = min(requested_page, total_pages - 1)
            offset = current_page * per_page
            rows = connection.execute(
                sql + " LIMIT ? OFFSET ?",
                tuple(query_params + [per_page, offset]),
            ).fetchall()

        return ClientePage(
            rows=[tuple(row) for row in rows],
            total=total,
            total_pages=total_pages,
            page=current_page,
            offset=offset,
            per_page=per_page,
        )


    @contextmanager
    def transaction(self):
        """Expõe uma única transação para operações coordenadas de clientes."""
        with self.database.session(write=True) as connection:
            if not connection.in_transaction:
                connection.execute("BEGIN IMMEDIATE")
            yield connection

    def ficha_existe(
        self, numero_ficha: int, *, ignorar_cliente_id: int | None = None, connection=None
    ) -> bool:
        sql = "SELECT 1 FROM clientes WHERE numero_ficha = ?"
        params: list[Any] = [int(numero_ficha)]
        if ignorar_cliente_id is not None:
            sql += " AND id <> ?"
            params.append(int(ignorar_cliente_id))
        sql += " LIMIT 1"
        row = (
            connection.execute(sql, tuple(params)).fetchone()
            if connection is not None
            else self.database.fetch_one(sql, params)
        )
        return row is not None

    def criar(self, dados: dict[str, Any], connection=None) -> int:
        target = connection
        columns = {
            str(row[1]) for row in (
                target.execute("PRAGMA table_info(clientes)").fetchall()
                if target is not None else self.database.fetch_all("PRAGMA table_info(clientes)")
            )
        }
        ordered = [
            "codigo", "numero_ficha", "nome", "cpf", "rg", "telefone", "endereco",
            "observacoes", "limite", "saldo_devedor", "email", "inscricao_estadual",
            "contribuinte_icms", "fiscal_logradouro", "fiscal_numero", "fiscal_bairro",
            "fiscal_codigo_municipio", "fiscal_municipio", "fiscal_uf", "fiscal_cep",
        ]
        selected = [name for name in ordered if name in columns]
        sql = f"INSERT INTO clientes ({','.join(selected)}) VALUES ({','.join('?' for _ in selected)})"
        params = tuple(dados.get(name, "") for name in selected)
        if connection is not None:
            return int(connection.execute(sql, params).lastrowid)
        return self.database.execute(sql, params)

    def atualizar_cadastro(
        self, cliente_id: int, dados: dict[str, Any], *, connection
    ) -> None:
        columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(clientes)")}
        ordered = (
            "numero_ficha", "codigo", "nome", "cpf", "rg", "telefone", "endereco",
            "limite", "observacoes", "email", "inscricao_estadual", "contribuinte_icms",
            "fiscal_logradouro", "fiscal_numero", "fiscal_bairro",
            "fiscal_codigo_municipio", "fiscal_municipio", "fiscal_uf", "fiscal_cep",
        )
        selected = [field for field in ordered if field in columns]
        cursor = connection.execute(
            "UPDATE clientes SET " + ",".join(f"{field}=?" for field in selected) + " WHERE id=?",
            tuple(dados.get(field, "") for field in selected) + (int(cliente_id),),
        )
        if cursor.rowcount != 1:
            raise ValueError("Cliente não encontrado.")

    def excluir_cadastro_sem_movimento(self, cliente_id: int) -> None:
        """Remove erro cadastral vazio sem apagar qualquer histórico comercial."""
        normalized_id = int(cliente_id)
        with self.database.session(write=True) as connection:
            customer = connection.execute(
                "SELECT codigo, COALESCE(saldo_devedor, 0) FROM clientes WHERE id=?",
                (normalized_id,),
            ).fetchone()
            if customer is None:
                raise ValueError("Cliente não encontrado.")
            if str(customer[0] or "").strip().upper() == "CONSUMIDOR_FINAL":
                raise ValueError("Consumidor Final é um cadastro técnico e não pode ser excluído.")
            if abs(float(customer[1] or 0)) > 0.005:
                raise ValueError("Cliente com saldo devedor não pode ser excluído.")

            references: list[tuple[str, str]] = []
            tables = connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
            for table_row in tables:
                table = str(table_row[0])
                if table in {"clientes", "historico_clientes"}:
                    continue
                columns = {
                    str(column[1])
                    for column in connection.execute(
                        f'SELECT * FROM pragma_table_info("{table.replace(chr(34), chr(34) * 2)}")'
                    ).fetchall()
                }
                if "cliente_id" in columns:
                    quoted = table.replace('"', '""')
                    row = connection.execute(
                        f'SELECT 1 FROM "{quoted}" WHERE cliente_id=? LIMIT 1',
                        (normalized_id,),
                    ).fetchone()
                    if row is not None:
                        references.append((table, "cliente_id"))
            if references:
                raise ValueError(
                    "Cliente possui compras, recebimentos ou histórico comercial e não pode "
                    "ser excluído. Edite o cadastro para preservar os registros."
                )
            if any(str(row[0]) == "historico_clientes" for row in tables):
                connection.execute(
                    "DELETE FROM historico_clientes WHERE cliente_id=?", (normalized_id,)
                )
            deleted = connection.execute(
                "DELETE FROM clientes WHERE id=?", (normalized_id,)
            )
            if deleted.rowcount != 1:
                raise ValueError("Cliente não encontrado.")

    def get_or_create_final_consumer(self) -> int:
        with self.database.session(write=True) as connection:
            row = connection.execute(
                "SELECT id FROM clientes WHERE codigo='CONSUMIDOR_FINAL' LIMIT 1"
            ).fetchone()
            if row:
                return int(row[0])
            cursor = connection.execute(
                """INSERT INTO clientes (
                       codigo, numero_ficha, nome, cpf, rg, telefone, endereco,
                       observacoes, limite, saldo_devedor, ficticio
                   ) VALUES (
                       'CONSUMIDOR_FINAL', 0, 'CONSUMIDOR FINAL', '', '', '', '',
                       'Cliente técnico do PDV', 0, 0, 0
                   )"""
            )
            return int(cursor.lastrowid)

    def atualizar_perfil_fiscal(self, customer_id: int, dados: dict[str, Any]) -> None:
        fields = (
            "email", "inscricao_estadual", "contribuinte_icms", "fiscal_logradouro",
            "fiscal_numero", "fiscal_bairro", "fiscal_codigo_municipio",
            "fiscal_municipio", "fiscal_uf", "fiscal_cep",
        )
        with self.database.session(write=True) as connection:
            cursor = connection.execute(
                "UPDATE clientes SET " + ",".join(f"{field}=?" for field in fields) + " WHERE id=?",
                tuple(dados.get(field, "") for field in fields) + (int(customer_id),),
            )
            if cursor.rowcount != 1:
                raise ValueError("Cliente não encontrado.")


    def toggle_favorite(self, customer_id: int, *, event_date: str = "") -> bool:
        """Alterna o favorito e registra o histórico na mesma transação."""
        try:
            customer_id = int(customer_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("Cliente inválido.") from exc
        if customer_id <= 0:
            raise ValueError("Cliente inválido.")

        with self.database.session(write=True) as connection:
            row = connection.execute(
                "SELECT COALESCE(favorito, 0) AS favorito FROM clientes WHERE id = ?",
                (customer_id,),
            ).fetchone()
            if row is None:
                raise ValueError("Cliente não encontrado.")

            new_value = 0 if int(row["favorito"] or 0) else 1
            connection.execute(
                "UPDATE clientes SET favorito = ? WHERE id = ?",
                (new_value, customer_id),
            )

            has_history = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='historico_clientes'"
            ).fetchone()
            if has_history:
                from datetime import datetime

                timestamp = str(event_date or "").strip() or datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                details = (
                    "Cliente marcado como favorito."
                    if new_value
                    else "Cliente removido dos favoritos."
                )
                connection.execute(
                    "INSERT INTO historico_clientes (cliente_id, evento, detalhes, data) VALUES (?, ?, ?, ?)",
                    (customer_id, "FAVORITO", details, timestamp),
                )

        return bool(new_value)
