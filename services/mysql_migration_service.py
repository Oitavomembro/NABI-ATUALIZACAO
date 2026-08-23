from __future__ import annotations

import hashlib
import heapq
import os
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterator, Any

ProgressCallback = Callable[[float], None]


class MySQLMigrationService:
    """Analisa dumps MySQL legados e prepara uma migração resumida."""

    @staticmethod
    def iter_sql_statements(path: str | os.PathLike[str]) -> Iterator[str]:
        buffer: list[str] = []
        in_string = False
        escaped = False
        with open(path, "r", encoding="latin1", errors="replace") as stream:
            for line in stream:
                for char in line:
                    buffer.append(char)
                    if escaped:
                        escaped = False
                        continue
                    if char == "\\" and in_string:
                        escaped = True
                    elif char == "'":
                        in_string = not in_string
                    elif char == ";" and not in_string:
                        statement = "".join(buffer).strip()
                        buffer.clear()
                        if statement:
                            yield statement
        remainder = "".join(buffer).strip()
        if remainder:
            yield remainder

    @classmethod
    def parse_mysql_values(cls, block: str) -> list[list[object]]:
        records: list[list[object]] = []
        current: list[object] = []
        field: list[str] = []
        in_string = False
        escaped = False
        depth = 0
        for char in block:
            if in_string:
                if escaped:
                    field.append({"n": "\n", "r": "\r", "t": "\t", "0": "\0"}.get(char, char))
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == "'":
                    in_string = False
                else:
                    field.append(char)
                continue
            if char == "'":
                in_string = True
            elif char == "(":
                depth += 1
                if depth == 1:
                    current, field = [], []
            elif char == "," and depth == 1:
                current.append(cls.convert_sql_value("".join(field).strip()))
                field = []
            elif char == ")" and depth == 1:
                current.append(cls.convert_sql_value("".join(field).strip()))
                records.append(current)
                current, field = [], []
                depth = 0
            elif depth == 1:
                field.append(char)
        if in_string or depth != 0:
            raise ValueError("Bloco VALUES incompleto ou malformado.")
        return records

    @staticmethod
    def convert_sql_value(value: str) -> object:
        return None if value.upper() == "NULL" else value

    @staticmethod
    def clean_text(value: object) -> str:
        return " ".join(str(value or "").strip().split())

    @staticmethod
    def migration_date(value: object) -> str:
        text = str(value or "").strip()
        try:
            date = datetime.strptime(text, "%Y-%m-%d")
        except (TypeError, ValueError):
            return ""
        if 1900 <= date.year <= datetime.now().year:
            return date.strftime("%d/%m/%Y")
        return ""

    @staticmethod
    def migration_document(value: object, length: int | None = None) -> str:
        digits = re.sub(r"\D", "", str(value or ""))
        if not digits or set(digits) <= {"0"} or set(digits) <= {"1"}:
            return ""
        if length and len(digits) != length:
            return digits
        return digits

    def analyze_dump(self, path: str | os.PathLike[str], progress: ProgressCallback | None = None) -> dict:
        path = os.fspath(path)
        size = max(1, os.path.getsize(path))
        tables: dict[str, dict] = {}
        counts: Counter[str] = Counter()
        columns: dict[str, list[str]] = {}
        clients: list[list[object]] = []
        warnings: list[str] = []
        processed = 0

        for statement in self.iter_sql_statements(path):
            processed += len(statement.encode("latin1", errors="ignore"))
            if progress:
                progress(min(0.99, processed / size))
            create_match = re.search(r"CREATE TABLE `([^`]+)`\s*\((.*?)\) ENGINE=", statement, re.S | re.I)
            if create_match:
                table = create_match.group(1)
                body = create_match.group(2)
                found = re.findall(r"^\s*`([^`]+)`\s+([^,\n]+)", body, re.M)
                columns[table] = [column[0] for column in found]
                tables[table] = {"colunas": columns[table]}
                continue
            insert_match = re.search(r"INSERT INTO `([^`]+)`(?:\s*\([^)]*\))?\s+VALUES\s*(.*);\s*$", statement, re.S | re.I)
            if not insert_match:
                continue
            table = insert_match.group(1)
            records = self.parse_mysql_values(insert_match.group(2))
            counts[table] += len(records)
            if table == "cliente":
                clients.extend(records)

        cpfs: Counter[str] = Counter()
        records_cards: Counter[str] = Counter()
        codes: Counter[str] = Counter()
        missing_name = invalid_dates = invalid_phones = 0
        for record in clients:
            if len(record) < 8:
                warnings.append("Registro de cliente com quantidade inesperada de campos.")
                continue
            code, card, cpf, name, _rg, birth, _address, phone = record[:8]
            codes[str(code)] += 1
            records_cards[str(card)] += 1
            clean_cpf = re.sub(r"\D", "", str(cpf or ""))
            if clean_cpf and clean_cpf not in ("00000000000", "11111111111"):
                cpfs[clean_cpf] += 1
            if not str(name or "").strip():
                missing_name += 1
            birth_text = str(birth or "")
            try:
                year = int(birth_text[:4])
                datetime.strptime(birth_text, "%Y-%m-%d")
                if year < 1900 or year > datetime.now().year:
                    invalid_dates += 1
            except (TypeError, ValueError):
                invalid_dates += 1
            clean_phone = re.sub(r"\D", "", str(phone or ""))
            if clean_phone and len(clean_phone) not in (8, 9, 10, 11):
                invalid_phones += 1

        result = {
            "arquivo": os.path.abspath(path),
            "tamanho": size,
            "tabelas": sorted(set(tables) | set(counts)),
            "colunas": columns,
            "contagens": dict(counts),
            "clientes": len(clients),
            "duplicados_cpf": sum(value - 1 for value in cpfs.values() if value > 1),
            "duplicados_ficha": sum(value - 1 for value in records_cards.values() if value > 1),
            "duplicados_codigo": sum(value - 1 for value in codes.values() if value > 1),
            "sem_nome": missing_name,
            "datas_invalidas": invalid_dates,
            "telefones_invalidos": invalid_phones,
            "avisos": warnings,
        }
        if progress:
            progress(1.0)
        return result

    def prepare_summary(self, path: str | os.PathLike[str], progress: ProgressCallback | None = None) -> dict:
        path = os.fspath(path)
        size = max(1, os.path.getsize(path))
        clients: dict[str, dict] = {}
        balances: defaultdict[str, float] = defaultdict(float)
        latest: defaultdict[str, list] = defaultdict(list)
        counts: Counter[str] = Counter()
        processed = 0

        def save_event(old_client: object, key: tuple, event: dict) -> None:
            heap = latest[str(old_client)]
            item = (key, event)
            if len(heap) < 12:
                heapq.heappush(heap, item)
            elif key > heap[0][0]:
                heapq.heapreplace(heap, item)

        for statement in self.iter_sql_statements(path):
            processed += len(statement.encode("latin1", errors="ignore"))
            if progress:
                progress(min(0.98, processed / size))
            insert_match = re.search(r"INSERT INTO `([^`]+)`(?:\s*\([^)]*\))?\s+VALUES\s*(.*);\s*$", statement, re.S | re.I)
            if not insert_match:
                continue
            table = insert_match.group(1).lower()
            if table not in ("cliente", "venda", "recebimento"):
                continue
            records = self.parse_mysql_values(insert_match.group(2))
            counts[table] += len(records)
            if table == "cliente":
                for record in records:
                    if len(record) < 8:
                        continue
                    code, card, cpf, name, rg, birth, address, phone = record[:8]
                    clients[str(code)] = {
                        "codigo": str(code),
                        "ficha": int(card or 0),
                        "cpf": self.migration_document(cpf, 11),
                        "nome": self.clean_text(name),
                        "rg": self.migration_document(rg),
                        "nascimento": self.migration_date(birth),
                        "endereco": self.clean_text(address),
                        "telefone": re.sub(r"\D", "", str(phone or "")),
                    }
            elif table == "venda":
                for record in records:
                    if len(record) < 6:
                        continue
                    sale_id, _, client_id, total_value, entry_value, date = record[:6]
                    total = float(total_value or 0)
                    entry = float(entry_value or 0)
                    balances[str(client_id)] += total - entry
                    save_event(client_id, (str(date or ""), int(sale_id or 0), 1), {
                        "origem_id": f"VENDA:{sale_id}",
                        "tipo": "COMPRA",
                        "data": str(date or ""),
                        "valor": total,
                        "descricao": f"Venda antiga #{sale_id} — entrada R$ {entry:.2f}",
                    })
            else:
                for record in records:
                    if len(record) < 5:
                        continue
                    receipt_id, client_id, paid_value, date, note = record[:5]
                    value = float(paid_value or 0)
                    clean_note = self.clean_text(note)
                    reversal = "EXTORNO" in clean_note.upper() or "ESTORNO" in clean_note.upper()
                    balances[str(client_id)] += value if reversal else -value
                    event_type = "ESTORNO" if reversal else ("ABATIMENTO" if "DESCONTO" in clean_note.upper() else "PAGAMENTO")
                    save_event(client_id, (str(date or ""), int(receipt_id or 0), 2), {
                        "origem_id": f"RECEBIMENTO:{receipt_id}",
                        "tipo": event_type,
                        "data": str(date or ""),
                        "valor": value,
                        "descricao": clean_note or "Pagamento antigo",
                    })

        events = {code: [item[1] for item in sorted(heap, key=lambda value: value[0])] for code, heap in latest.items()}
        result = {
            "arquivo": os.path.abspath(path),
            "hash": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            "clientes": clients,
            "saldos": dict(balances),
            "eventos": events,
            "contagens": dict(counts),
            "saldo_total": sum(balances.get(code, 0.0) for code in clients),
            "clientes_com_credito": sum(1 for code in clients if balances[code] < -0.005),
            "movimentacoes_selecionadas": sum(len(events.get(code, [])) for code in clients),
        }
        if progress:
            progress(1.0)
        return result


    def execute_summary(
        self,
        data: dict,
        *,
        database_path: str | os.PathLike[str],
        backup_dir: str | os.PathLike[str],
        connect: Callable[[], Any],
        backup_database: Callable[..., object],
        network_mode: bool = False,
        logger: Any = None,
        remove_demo_clients: bool = True,
        import_events: bool = True,
        progress: ProgressCallback | None = None,
    ) -> dict:
        """Importa o resumo preparado preservando IDs, vínculos e idempotência."""
        backup_dir = os.fspath(backup_dir)
        database_path = os.fspath(database_path)
        os.makedirs(backup_dir, exist_ok=True)
        backup = os.path.join(
            backup_dir,
            f"pre_migracao_fase2_{datetime.now():%Y%m%d_%H%M%S}.db",
        )
        backup_database(
            database_path,
            backup,
            timeout=60,
            network_mode=network_mode,
            logger=logger,
        )

        connection = connect()
        cursor = connection.cursor()
        imported = updated = movements = demos_removed = demos_preserved = 0

        def table_exists(name: str) -> bool:
            return bool(cursor.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (name,),
            ).fetchone())

        def remove_demo_client(client_id: int) -> None:
            nonlocal demos_removed, demos_preserved
            cursor.execute("SAVEPOINT remover_demo")
            try:
                if table_exists("documentos_emitidos"):
                    cursor.execute(
                        "DELETE FROM documentos_emitidos WHERE movimentacao_id IN "
                        "(SELECT id FROM movimentacoes WHERE cliente_id=?)",
                        (client_id,),
                    )
                if table_exists("contatos_cobranca"):
                    cursor.execute("DELETE FROM contatos_cobranca WHERE cliente_id=?", (client_id,))
                if table_exists("lembretes_promissorias"):
                    cursor.execute("DELETE FROM lembretes_promissorias WHERE cliente_id=?", (client_id,))
                if table_exists("parcelas"):
                    cursor.execute(
                        "DELETE FROM parcelas WHERE movimentacao_id IN "
                        "(SELECT id FROM movimentacoes WHERE cliente_id=?)",
                        (client_id,),
                    )
                if table_exists("movimentacoes"):
                    cursor.execute("DELETE FROM movimentacoes WHERE cliente_id=?", (client_id,))
                if table_exists("historico_clientes"):
                    cursor.execute("DELETE FROM historico_clientes WHERE cliente_id=?", (client_id,))
                cursor.execute("DELETE FROM clientes WHERE id=?", (client_id,))
                cursor.execute("RELEASE SAVEPOINT remover_demo")
                demos_removed += 1
            except sqlite3.IntegrityError:
                cursor.execute("ROLLBACK TO SAVEPOINT remover_demo")
                cursor.execute("RELEASE SAVEPOINT remover_demo")
                demos_preserved += 1
                if logger is not None:
                    logger.warning(
                        "Cliente de demonstração %s preservado por possuir vínculos.",
                        client_id,
                    )

        try:
            cursor.execute("BEGIN IMMEDIATE")
            if remove_demo_clients:
                demo_ids = [
                    row[0]
                    for row in cursor.execute(
                        "SELECT id FROM clientes WHERE ficticio=1"
                    ).fetchall()
                ]
                for client_id in demo_ids:
                    remove_demo_client(client_id)

            total = max(1, len(data["clientes"]))
            for position, (old_code, client) in enumerate(data["clientes"].items(), 1):
                old_code = str(old_code).strip()
                if not old_code:
                    raise ValueError(f"Cliente na posição {position} está sem código de origem.")
                try:
                    balance = round(float(data["saldos"].get(old_code, 0.0)), 2)
                    existing = cursor.execute(
                        "SELECT id FROM clientes WHERE codigo=?",
                        (old_code,),
                    ).fetchone()
                    if existing:
                        client_id = existing[0]
                        cursor.execute(
                            """UPDATE clientes SET numero_ficha=?,nome=?,cpf=?,rg=?,telefone=?,endereco=?,
                               saldo_devedor=?,data_nascimento=?,origem_migracao='FICHARIO_MYSQL',ficticio=0
                               WHERE id=?""",
                            (
                                client["ficha"], client["nome"], client["cpf"], client["rg"],
                                client["telefone"], client["endereco"], balance,
                                client["nascimento"], client_id,
                            ),
                        )
                        updated += 1
                    else:
                        cursor.execute(
                            """INSERT INTO clientes
                               (codigo,numero_ficha,nome,cpf,rg,telefone,endereco,observacoes,
                                limite,saldo_devedor,ficticio,data_nascimento,origem_migracao)
                               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (
                                old_code, client["ficha"], client["nome"], client["cpf"],
                                client["rg"], client["telefone"], client["endereco"],
                                "Migrado do Fichário MySQL — histórico resumido",
                                0.0, balance, 0, client["nascimento"], "FICHARIO_MYSQL",
                            ),
                        )
                        client_id = cursor.lastrowid
                        imported += 1

                    selected_events = data["eventos"].get(old_code, []) if import_events else ()
                    for event in selected_events:
                        source_id = str(event.get("origem_id") or "").strip()
                        if not source_id:
                            raise ValueError("Movimentação sem identificador de origem.")
                        date_br = self.migration_date(event.get("data")) or str(event.get("data") or "")
                        values = (
                            client_id, event.get("tipo"), event.get("descricao"),
                            float(event.get("valor") or 0), date_br, "", "HISTÓRICO",
                            1, 0, 0.0, "FICHARIO_MYSQL", source_id,
                        )
                        existing_movement = cursor.execute(
                            "SELECT id FROM movimentacoes WHERE origem_sistema=? AND origem_id=?",
                            ("FICHARIO_MYSQL", source_id),
                        ).fetchone()
                        if existing_movement:
                            cursor.execute(
                                """UPDATE movimentacoes SET cliente_id=?,tipo=?,descricao=?,valor=?,data=?,
                                   vencimento=?,status_pagamento=?,total_parcelas=?,parcelas_atrasadas=?,
                                   valor_aberto=? WHERE id=?""",
                                values[:10] + (existing_movement[0],),
                            )
                        else:
                            cursor.execute(
                                """INSERT INTO movimentacoes
                                   (cliente_id,tipo,descricao,valor,data,vencimento,status_pagamento,
                                    total_parcelas,parcelas_atrasadas,valor_aberto,origem_sistema,origem_id)
                                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                                values,
                            )
                        movements += 1

                    details = (
                        f"Cadastro, saldo atual e {len(selected_events)} "
                        "últimas transações importados."
                    )
                    history_exists = cursor.execute(
                        """SELECT 1 FROM historico_clientes
                           WHERE cliente_id=? AND evento='MIGRAÇÃO' AND detalhes=? LIMIT 1""",
                        (client_id, details),
                    ).fetchone()
                    if not history_exists:
                        cursor.execute(
                            "INSERT INTO historico_clientes (cliente_id,evento,detalhes,data) VALUES (?,?,?,?)",
                            (
                                client_id, "MIGRAÇÃO", details,
                                datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                            ),
                        )
                except Exception as exc:
                    raise RuntimeError(
                        f"Falha ao importar cliente código {old_code}, ficha {client.get('ficha', '')}: {exc}"
                    ) from exc

                if progress and (position % 25 == 0 or position == total):
                    progress(position / total)

            violations = cursor.execute("PRAGMA foreign_key_check").fetchall()
            if violations:
                table, rowid, parent_table, foreign_key_id = violations[0]
                raise RuntimeError(
                    f"Integridade inválida após migração: tabela={table}, registro={rowid}, "
                    f"referência={parent_table}, chave={foreign_key_id}."
                )

            details = (
                f"Novos: {imported}; atualizados: {updated}; movimentações: {movements}; "
                f"demos removidos: {demos_removed}; demos preservados: {demos_preserved}; "
                f"backup: {backup}"
            )
            cursor.execute(
                """INSERT INTO migracoes_execucoes
                   (data,arquivo,hash_arquivo,clientes_importados,movimentacoes_importadas,
                    saldo_total,status,detalhes)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    datetime.now().strftime("%d/%m/%Y %H:%M:%S"), data["arquivo"], data["hash"],
                    imported + updated, movements, data["saldo_total"], "SUCESSO", details,
                ),
            )
            connection.commit()
            return {
                "novos": imported,
                "atualizados": updated,
                "movimentacoes": movements,
                "backup": backup,
                "saldo_total": data["saldo_total"],
                "demos_removidos": demos_removed,
                "demos_preservados": demos_preserved,
            }
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
