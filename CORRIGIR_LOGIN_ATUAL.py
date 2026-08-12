from __future__ import annotations
import os
import sqlite3
from pathlib import Path

APP_DIR = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "NabiCode"
DB = APP_DIR / "fichario_moveis.db"

if not DB.exists():
    raise SystemExit(f"Banco não encontrado: {DB}")

with sqlite3.connect(DB) as conn:
    cols = [row[1] for row in conn.execute("PRAGMA table_info(configuracoes)")]
    if not cols:
        raise SystemExit("Tabela configuracoes não encontrada.")
    key_col = "chave" if "chave" in cols else ("nome" if "nome" in cols else cols[0])
    value_col = "valor" if "valor" in cols else cols[1]
    for key, value in {
        "login_usuarios_habilitado": "0",
        "login_usuarios_configurado": "1",
        "login_inicio_consentido_v2440": "0",
    }.items():
        row = conn.execute(f"SELECT 1 FROM configuracoes WHERE {key_col}=?", (key,)).fetchone()
        if row:
            conn.execute(f"UPDATE configuracoes SET {value_col}=? WHERE {key_col}=?", (value, key))
        else:
            conn.execute(f"INSERT INTO configuracoes ({key_col}, {value_col}) VALUES (?, ?)", (key, value))
    conn.commit()
print("Login inicial desativado com sucesso.")
