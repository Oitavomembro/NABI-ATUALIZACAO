from __future__ import annotations


class ProductSchemaMigration:
    """Manutenção explícita dos índices de Produtos durante o bootstrap."""

    @staticmethod
    def migrate_connection(connection) -> None:
        if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='produtos'").fetchone() is None:
            return
        cursor = connection.cursor()
        for indice in cursor.execute("PRAGMA index_list(produtos)").fetchall():
            unique = bool(indice[2])
            if not unique:
                continue
            nome_indice = str(indice[1])
            nome_escapado = nome_indice.replace('"', '""')
            colunas = cursor.execute(f'PRAGMA index_info("{nome_escapado}")').fetchall()
            nomes = [str(coluna[2] or "").casefold() for coluna in colunas]
            if nomes == ["codigo_barras"] and not nome_indice.startswith("sqlite_autoindex_"):
                cursor.execute(f'DROP INDEX IF EXISTS "{nome_escapado}"')
        duplicado = cursor.execute("""
            SELECT 1 FROM produtos
            WHERE TRIM(COALESCE(codigo_barras,''))<>''
            GROUP BY codigo_barras COLLATE NOCASE HAVING COUNT(*)>1 LIMIT 1
        """).fetchone()
        if duplicado is None:
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_produtos_codigo_barras_unico
                ON produtos(codigo_barras COLLATE NOCASE)
                WHERE TRIM(codigo_barras)<>''
            """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_produtos_codigo_barras ON produtos(codigo_barras COLLATE NOCASE)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_produtos_nome_nocase ON produtos(nome COLLATE NOCASE)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_produtos_tipo_ativo ON produtos(tipo_produto, ativo)")
