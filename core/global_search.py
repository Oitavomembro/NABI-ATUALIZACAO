"""Pesquisa global e paleta de comandos do NabiCode.

O motor é independente da interface: recebe uma fábrica de conexões SQLite e
retorna resultados tipados. A janela CommandPalette apenas apresenta esses
resultados e delega a execução para a aplicação principal.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, List, Mapping, Optional, Sequence
import sqlite3
import unicodedata

from services.search_entry_behavior import SearchEntryBehavior
from repositories.decimal_storage import DecimalStorage


@dataclass(frozen=True)
class CommandDefinition:
    key: str
    title: str
    keywords: Sequence[str] = field(default_factory=tuple)
    subtitle: str = "Comando do sistema"


@dataclass(frozen=True)
class SearchResult:
    kind: str
    identifier: str
    title: str
    subtitle: str
    action: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    score: int = 0


def normalize_search_text(value: Any) -> str:
    text = str(value or "").strip().casefold()
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


class GlobalSearchEngine:
    """Pesquisa comandos e registros sem expor SQL à interface gráfica."""

    def __init__(
        self,
        connection_factory: Callable[[], sqlite3.Connection],
        commands: Optional[Iterable[CommandDefinition]] = None,
    ) -> None:
        self.connection_factory = connection_factory
        self.commands = tuple(commands or ())

    @staticmethod
    def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
        row = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
            (table,),
        ).fetchone()
        return bool(row)

    @staticmethod
    def _score(query: str, *values: Any) -> int:
        normalized_values = [normalize_search_text(value) for value in values]
        if not query:
            return 0
        best = 0
        for value in normalized_values:
            if not value:
                continue
            if value == query:
                best = max(best, 100)
            elif value.startswith(query):
                best = max(best, 85)
            elif f" {query}" in value:
                best = max(best, 70)
            elif query in value:
                best = max(best, 55)
        return best

    def _search_commands(self, query: str) -> List[SearchResult]:
        results: List[SearchResult] = []
        for command in self.commands:
            score = self._score(query, command.title, command.key, *command.keywords)
            if query and score <= 0:
                continue
            results.append(
                SearchResult(
                    kind="command",
                    identifier=command.key,
                    title=command.title,
                    subtitle=command.subtitle,
                    action=command.key,
                    score=score + 20,
                )
            )
        return results

    def _search_products(self, connection: sqlite3.Connection, raw_query: str, query: str, limit: int) -> List[SearchResult]:
        if not self._table_exists(connection, "produtos"):
            return []
        like = f"%{raw_query.strip()}%"
        rows = connection.execute(
            """
            SELECT id, codigo, nome, COALESCE(codigo_barras,''),
                   COALESCE(preco_venda,0), COALESCE(estoque_atual,0), COALESCE(ativo,1)
            FROM produtos
            WHERE nome LIKE ? COLLATE NOCASE
               OR codigo LIKE ? COLLATE NOCASE
               OR COALESCE(codigo_barras,'') LIKE ? COLLATE NOCASE
            ORDER BY CASE WHEN codigo = ? COLLATE NOCASE THEN 0
                          WHEN COALESCE(codigo_barras,'') = ? COLLATE NOCASE THEN 1
                          WHEN nome = ? COLLATE NOCASE THEN 2
                          ELSE 3 END,
                     nome COLLATE NOCASE
            LIMIT ?
            """,
            (like, like, like, raw_query.strip(), raw_query.strip(), raw_query.strip(), limit),
        ).fetchall()
        if not rows:
            candidates = connection.execute(
                """SELECT id, codigo, nome, COALESCE(codigo_barras,''),
                          COALESCE(preco_venda,0), COALESCE(estoque_atual,0), COALESCE(ativo,1)
                   FROM produtos ORDER BY nome COLLATE NOCASE LIMIT 500"""
            ).fetchall()
            rows = [row for row in candidates if self._score(query, row[1], row[2], row[3]) > 0][:limit]
        results: List[SearchResult] = []
        for row in rows:
            product_id, code, name, barcode, price, stock, active = row
            score = self._score(query, code, name, barcode)
            status = "ATIVO" if active else "INATIVO"
            subtitle = f"Produto • cód. {code} • estoque {float(stock):g} • R$ {DecimalStorage.to_decimal(price, field='preço do produto'):.2f} • {status}"
            results.append(
                SearchResult(
                    kind="product",
                    identifier=str(product_id),
                    title=str(name or code),
                    subtitle=subtitle,
                    action="open_product",
                    payload={"product_id": int(product_id)},
                    score=score,
                )
            )
        return results

    def _search_clients(self, connection: sqlite3.Connection, raw_query: str, query: str, limit: int) -> List[SearchResult]:
        if not self._table_exists(connection, "clientes"):
            return []
        like = f"%{raw_query.strip()}%"
        digits = "".join(char for char in raw_query if char.isdigit())
        rows = connection.execute(
            """
            SELECT id, COALESCE(numero_ficha,''), COALESCE(nome,''), COALESCE(cpf,''),
                   COALESCE(telefone,''), COALESCE(saldo_devedor,0)
            FROM clientes
            WHERE nome LIKE ? COLLATE NOCASE
               OR CAST(COALESCE(numero_ficha,'') AS TEXT) LIKE ?
               OR COALESCE(cpf,'') LIKE ?
               OR COALESCE(telefone,'') LIKE ?
               OR COALESCE(codigo,'') LIKE ? COLLATE NOCASE
            ORDER BY CASE WHEN CAST(COALESCE(numero_ficha,'') AS TEXT) = ? THEN 0
                          WHEN nome = ? COLLATE NOCASE THEN 1 ELSE 2 END,
                     nome COLLATE NOCASE
            LIMIT ?
            """,
            (like, like, like, like, like, digits, raw_query.strip(), limit),
        ).fetchall()
        if not rows:
            candidates = connection.execute(
                """SELECT id, COALESCE(numero_ficha,''), COALESCE(nome,''), COALESCE(cpf,''),
                          COALESCE(telefone,''), COALESCE(saldo_devedor,0)
                   FROM clientes ORDER BY nome COLLATE NOCASE LIMIT 500"""
            ).fetchall()
            rows = [row for row in candidates if self._score(query, row[1], row[2], row[3], row[4]) > 0][:limit]
        results: List[SearchResult] = []
        for row in rows:
            client_id, record_number, name, cpf, phone, debt = row
            score = self._score(query, record_number, name, cpf, phone)
            subtitle = f"Cliente • ficha {record_number or '-'} • {phone or 'sem telefone'} • saldo R$ {DecimalStorage.to_decimal(debt, field='saldo do cliente'):.2f}"
            results.append(
                SearchResult(
                    kind="client",
                    identifier=str(client_id),
                    title=str(name or f"Cliente {client_id}"),
                    subtitle=subtitle,
                    action="open_client",
                    payload={"client_id": int(client_id), "client_name": str(name or "")},
                    score=score,
                )
            )
        return results

    def _search_suppliers(self, connection: sqlite3.Connection, raw_query: str, query: str, limit: int) -> List[SearchResult]:
        if not self._table_exists(connection, "fornecedores"):
            return []
        like = f"%{raw_query.strip()}%"
        rows = connection.execute(
            """
            SELECT id, COALESCE(nome_fantasia,''), COALESCE(razao_social,''),
                   COALESCE(cnpj,''), COALESCE(telefone,''), COALESCE(ativo,1)
            FROM fornecedores
            WHERE nome_fantasia LIKE ? COLLATE NOCASE
               OR razao_social LIKE ? COLLATE NOCASE
               OR cnpj LIKE ?
               OR telefone LIKE ?
            ORDER BY nome_fantasia COLLATE NOCASE
            LIMIT ?
            """,
            (like, like, like, like, limit),
        ).fetchall()
        return [
            SearchResult(
                kind="supplier",
                identifier=str(row[0]),
                title=str(row[1] or row[2] or f"Fornecedor {row[0]}"),
                subtitle=f"Fornecedor • {row[2] or 'sem razão social'} • {row[3] or 'sem CNPJ'}",
                action="open_supplier",
                payload={"supplier_id": int(row[0]), "supplier_name": str(row[1] or row[2] or "")},
                score=self._score(query, row[1], row[2], row[3], row[4]),
            )
            for row in rows
        ]

    def _search_nfe(self, connection: sqlite3.Connection, raw_query: str, query: str, limit: int) -> List[SearchResult]:
        if not self._table_exists(connection, "nfe_importacoes"):
            return []
        like = f"%{raw_query.strip()}%"
        rows = connection.execute(
            """
            SELECT id, COALESCE(numero,''), COALESCE(chave,''), COALESCE(fornecedor_nome,''),
                   COALESCE(fornecedor_cnpj,''), COALESCE(status,''), COALESCE(data_importacao,'')
            FROM nfe_importacoes
            WHERE numero LIKE ? OR chave LIKE ? OR fornecedor_nome LIKE ? COLLATE NOCASE OR fornecedor_cnpj LIKE ?
            ORDER BY data_importacao DESC
            LIMIT ?
            """,
            (like, like, like, like, limit),
        ).fetchall()
        return [
            SearchResult(
                kind="nfe",
                identifier=str(row[0]),
                title=f"NF-e {row[1] or row[0]} — {row[3] or 'Fornecedor não informado'}",
                subtitle=f"NF-e importada • {row[5] or '-'} • {row[6] or '-'} • chave {row[2][:12]}…",
                action="open_nfe_history",
                payload={"nfe_id": int(row[0]), "nfe_number": str(row[1] or "")},
                score=self._score(query, row[1], row[2], row[3], row[4]),
            )
            for row in rows
        ]

    def _search_financial(self, connection: sqlite3.Connection, raw_query: str, query: str, limit: int) -> List[SearchResult]:
        if not self._table_exists(connection, "titulos_financeiros"):
            return []
        like = f"%{raw_query.strip()}%"
        rows = connection.execute(
            """
            SELECT id, tipo, COALESCE(pessoa_nome,''), COALESCE(documento,''), COALESCE(descricao,''),
                   COALESCE(data_vencimento,''), COALESCE(valor_original,0), COALESCE(valor_pago,0), status
            FROM titulos_financeiros
            WHERE pessoa_nome LIKE ? COLLATE NOCASE
               OR documento LIKE ? COLLATE NOCASE
               OR descricao LIKE ? COLLATE NOCASE
               OR origem_id LIKE ? COLLATE NOCASE
            ORDER BY data_vencimento DESC
            LIMIT ?
            """,
            (like, like, like, like, limit),
        ).fetchall()
        if not rows:
            candidates = connection.execute(
                """SELECT id, tipo, COALESCE(pessoa_nome,''), COALESCE(documento,''), COALESCE(descricao,''),
                          COALESCE(data_vencimento,''), COALESCE(valor_original,0), COALESCE(valor_pago,0), status
                   FROM titulos_financeiros ORDER BY data_vencimento DESC LIMIT 500"""
            ).fetchall()
            rows = [row for row in candidates if self._score(query, row[2], row[3], row[4]) > 0][:limit]
        results: List[SearchResult] = []
        for row in rows:
            balance = max(DecimalStorage.to_decimal(0), DecimalStorage.to_decimal(row[6], field="valor original") - DecimalStorage.to_decimal(row[7], field="valor pago"))
            results.append(
                SearchResult(
                    kind="financial",
                    identifier=str(row[0]),
                    title=f"{row[1]} — {row[2] or row[4] or row[3] or row[0]}",
                    subtitle=f"Financeiro • venc. {row[5] or '-'} • saldo R$ {balance:.2f} • {row[8]}",
                    action="open_financial",
                    payload={"title_id": int(row[0]), "person_name": str(row[2] or "")},
                    score=self._score(query, row[2], row[3], row[4]),
                )
            )
        return results

    def search(self, term: str, limit: int = 40) -> List[SearchResult]:
        raw_query = str(term or "").strip()
        query = normalize_search_text(raw_query)
        results = self._search_commands(query)
        if not raw_query:
            return sorted(results, key=lambda item: (-item.score, item.title.casefold()))[:limit]

        connection = self.connection_factory()
        try:
            per_group = max(5, min(15, limit // 3 or 5))
            results.extend(self._search_products(connection, raw_query, query, per_group))
            results.extend(self._search_clients(connection, raw_query, query, per_group))
            results.extend(self._search_suppliers(connection, raw_query, query, per_group))
            results.extend(self._search_nfe(connection, raw_query, query, per_group))
            results.extend(self._search_financial(connection, raw_query, query, per_group))
        finally:
            connection.close()

        unique = {}
        for result in results:
            key = (result.kind, result.identifier, result.action)
            previous = unique.get(key)
            if previous is None or result.score > previous.score:
                unique[key] = result
        return sorted(unique.values(), key=lambda item: (-item.score, item.kind, item.title.casefold()))[:limit]


class CommandPalette:
    """Janela leve de pesquisa global com ativação por teclado ou mouse."""

    def __init__(
        self,
        parent: Any,
        engine: GlobalSearchEngine,
        on_activate: Callable[[SearchResult], None],
        accent_color: str = "#00FF88",
    ) -> None:
        import customtkinter as ctk
        import tkinter as tk
        from tkinter import ttk

        self.parent = parent
        self.engine = engine
        self.on_activate = on_activate
        self.results: List[SearchResult] = []
        self._after_id: Optional[str] = None

        self.window = ctk.CTkToplevel(parent)
        self.window.title("Pesquisa global — Ctrl+K")
        self.window.geometry("900x580")
        self.window.minsize(720, 440)
        self.window.configure(fg_color="#0d1117")
        self.window.transient(parent)
        self.window.grab_set()

        header = ctk.CTkFrame(self.window, fg_color="#161b22", corner_radius=10)
        header.pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkLabel(
            header,
            text="Pesquisar no NabiCode",
            font=ctk.CTkFont(size=19, weight="bold"),
            text_color=accent_color,
        ).pack(anchor="w", padx=14, pady=(10, 3))
        ctk.CTkLabel(
            header,
            text="Produtos, clientes, fornecedores, NF-e, financeiro, telas e comandos",
            text_color="#8b949e",
        ).pack(anchor="w", padx=14, pady=(0, 8))

        self.entry = ctk.CTkEntry(
            header,
            placeholder_text="Digite para pesquisar…",
            height=44,
            font=ctk.CTkFont(size=15),
        )
        self.entry.pack(fill="x", padx=14, pady=(0, 14))
        SearchEntryBehavior.attach(
            self.entry, on_enter=self.activate_selected
        )

        table_frame = ctk.CTkFrame(self.window, fg_color="#161b22", corner_radius=10)
        table_frame.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        columns = ("Tipo", "Título", "Detalhes")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("Tipo", text="Tipo")
        self.tree.heading("Título", text="Resultado")
        self.tree.heading("Detalhes", text="Detalhes")
        self.tree.column("Tipo", width=110, anchor="center", stretch=False)
        self.tree.column("Título", width=290, anchor="w")
        self.tree.column("Detalhes", width=440, anchor="w")
        scroll_y = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        scroll_x = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(10, 0), pady=(10, 0))
        scroll_y.grid(row=0, column=1, sticky="ns", pady=(10, 0), padx=(0, 10))
        scroll_x.grid(row=1, column=0, sticky="ew", padx=(10, 0), pady=(0, 10))
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        footer = ctk.CTkFrame(self.window, fg_color="transparent")
        footer.pack(fill="x", padx=16, pady=(0, 14))
        self.status = ctk.CTkLabel(footer, text="Enter abre • Esc fecha • ↑/↓ seleciona", text_color="#8b949e")
        self.status.pack(side="left")
        ctk.CTkButton(footer, text="Abrir", width=110, command=self.activate_selected).pack(side="right")

        self.entry.bind("<KeyRelease>", self._on_query_changed, add="+")
        self.entry.bind("<Down>", self._focus_results)
        self.tree.bind("<Double-1>", lambda _event: self.activate_selected())
        self.tree.bind("<Return>", self._activate_selected_from_enter)
        self.tree.bind("<Escape>", lambda _event: self.close())
        self.window.bind("<Escape>", lambda _event: self.close())
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.window.after(40, self.entry.focus_set)
        self.refresh("")


    def _activate_selected_from_enter(self, _event=None) -> str:
        self.activate_selected()
        return SearchEntryBehavior.consume_enter()

    @staticmethod
    def _kind_label(kind: str) -> str:
        return {
            "command": "Comando",
            "product": "Produto",
            "client": "Cliente",
            "supplier": "Fornecedor",
            "nfe": "NF-e",
            "financial": "Financeiro",
        }.get(kind, kind.title())

    def _on_query_changed(self, _event: Any = None) -> None:
        if self._after_id:
            try:
                self.window.after_cancel(self._after_id)
            except Exception:
                pass
        self._after_id = self.window.after(160, lambda: self.refresh(self.entry.get()))

    def refresh(self, term: str) -> None:
        self._after_id = None
        try:
            self.results = self.engine.search(term)
        except Exception as exc:
            self.results = []
            self.status.configure(text=f"Falha na pesquisa: {exc}")
        for item in self.tree.get_children():
            self.tree.delete(item)
        for index, result in enumerate(self.results):
            self.tree.insert(
                "",
                "end",
                iid=str(index),
                values=(self._kind_label(result.kind), result.title, result.subtitle),
            )
        if self.results:
            self.tree.selection_set("0")
            self.tree.focus("0")
            self.status.configure(text=f"{len(self.results)} resultado(s) • Enter abre • Esc fecha")
        else:
            self.status.configure(text="Nenhum resultado encontrado")

    def _focus_results(self, _event: Any = None) -> str:
        if self.results:
            self.tree.focus_set()
            self.tree.selection_set("0")
            self.tree.focus("0")
        return "break"

    def activate_selected(self) -> str:
        selected = self.tree.selection()
        if not selected and self.results:
            selected = ("0",)
        if not selected:
            return "break"
        index = int(selected[0])
        if index < 0 or index >= len(self.results):
            return "break"
        result = self.results[index]
        self.close()
        self.on_activate(result)
        return "break"

    def close(self) -> str:
        try:
            self.window.grab_release()
        except Exception:
            pass
        try:
            self.window.destroy()
        except Exception:
            pass
        return "break"
