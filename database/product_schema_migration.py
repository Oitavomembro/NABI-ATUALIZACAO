from __future__ import annotations

from datetime import datetime


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

        # Catálogo de unidades é aberto à configuração, mas nasce com um conjunto
        # operacional canônico. A política pode ser alterada conscientemente sem
        # transformar a sigla recebida do fornecedor em texto livre no produto.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS unidades_medida (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sigla TEXT NOT NULL COLLATE NOCASE UNIQUE,
                descricao TEXT NOT NULL DEFAULT '',
                permite_fracionado INTEGER NOT NULL DEFAULT 0,
                ativo INTEGER NOT NULL DEFAULT 1,
                criado_em TEXT NOT NULL,
                atualizado_em TEXT NOT NULL
            )
        """)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for sigla, descricao, fracionada in (
            ("UN", "Unidade", 0), ("CX", "Caixa", 0),
            ("KG", "Quilograma", 1), ("L", "Litro", 1), ("M", "Metro", 1),
        ):
            cursor.execute(
                """INSERT OR IGNORE INTO unidades_medida
                   (sigla,descricao,permite_fracionado,ativo,criado_em,atualizado_em)
                   VALUES(?,?,?,1,?,?)""",
                (sigla, descricao, fracionada, now, now),
            )
        product_columns = {
            str(row[1]) for row in cursor.execute("PRAGMA table_info(produtos)").fetchall()
        }
        if "permite_fracionado" not in product_columns:
            cursor.execute("ALTER TABLE produtos ADD COLUMN permite_fracionado INTEGER")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS unidade_fornecedor_aliases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alias TEXT NOT NULL COLLATE NOCASE UNIQUE,
                unidade_id INTEGER NOT NULL,
                criado_em TEXT NOT NULL,
                FOREIGN KEY (unidade_id) REFERENCES unidades_medida(id)
            )
        """)
        for alias, sigla in (
            ("UND", "UN"), ("UNID", "UN"), ("UNIDADE", "UN"),
            ("PC", "UN"), ("PÇ", "UN"), ("PCA", "UN"),
            ("CAIXA", "CX"), ("BOX", "CX"),
            ("KILO", "KG"), ("QUILO", "KG"),
            ("LT", "L"), ("LITRO", "L"), ("MT", "M"), ("METRO", "M"),
        ):
            cursor.execute(
                """INSERT OR IGNORE INTO unidade_fornecedor_aliases(alias,unidade_id,criado_em)
                   SELECT ?,id,? FROM unidades_medida WHERE sigla=? COLLATE NOCASE""",
                (alias, now, sigla),
            )

        # Um código alternativo identifica exatamente um produto. Códigos
        # principais legados duplicados não são inventivamente conciliados:
        # permanecem fora desta tabela e continuam resultando em ambiguidade.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS produto_codigos_barras (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                produto_id INTEGER NOT NULL,
                codigo TEXT NOT NULL COLLATE NOCASE UNIQUE,
                tipo TEXT NOT NULL DEFAULT 'UNIDADE'
                    CHECK(tipo IN ('UNIDADE','CAIXA','FORNECEDOR','OUTRO')),
                principal INTEGER NOT NULL DEFAULT 0,
                ativo INTEGER NOT NULL DEFAULT 1,
                criado_em TEXT NOT NULL,
                FOREIGN KEY (produto_id) REFERENCES produtos(id),
                UNIQUE(produto_id,codigo)
            )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_produto_barras_produto ON produto_codigos_barras(produto_id,ativo)"
        )
        cursor.execute("""
            INSERT OR IGNORE INTO produto_codigos_barras
                (produto_id,codigo,tipo,principal,ativo,criado_em)
            SELECT p.id,TRIM(p.codigo_barras),'UNIDADE',1,1,?
              FROM produtos p
             WHERE TRIM(COALESCE(p.codigo_barras,''))<>''
               AND (SELECT COUNT(*) FROM produtos x
                    WHERE TRIM(x.codigo_barras)=TRIM(p.codigo_barras) COLLATE NOCASE)=1
        """, (now,))
