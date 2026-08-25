from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta
from typing import Callable, Any


def initialize_database(
    *,
    db_name: str,
    backup_dir: str,
    pdf_dir: str,
    schema_version: int,
    last_database_update: dict[str, object],
    network_mode: bool,
    network_role: str,
    connect: Callable[[], Any],
    read_existing_version: Callable[[], int],
    backup_before_update: Callable[[int, int], str],
) -> None:
    """Cria/atualiza o schema mantendo compatibilidade com a inicialização legada."""
    DB_NAME = db_name
    BACKUP_DIR = backup_dir
    PDF_DIR = pdf_dir
    DB_SCHEMA_VERSION = schema_version
    ULTIMA_ATUALIZACAO_BANCO = last_database_update
    MODO_REDE = network_mode
    PAPEL_REDE = network_role
    conectar_banco = connect
    _ler_versao_schema_existente = read_existing_version
    _backup_antes_atualizacao = backup_before_update
    primeira_instalacao = not os.path.exists(DB_NAME)
    versao_anterior = 0 if primeira_instalacao else _ler_versao_schema_existente()
    if MODO_REDE and primeira_instalacao and PAPEL_REDE != "servidor":
        raise FileNotFoundError(f"O banco compartilhado não foi encontrado:\n{DB_NAME}")

    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    if not os.path.exists(PDF_DIR):
        os.makedirs(PDF_DIR)

    if not primeira_instalacao and versao_anterior < DB_SCHEMA_VERSION:
        try:
            backup_criado = _backup_antes_atualizacao(versao_anterior, DB_SCHEMA_VERSION)
            ULTIMA_ATUALIZACAO_BANCO.update(executada=True, de=versao_anterior, para=DB_SCHEMA_VERSION, backup=backup_criado)
        except Exception as exc:
            raise RuntimeError(
                "A atualização foi cancelada porque o backup de segurança não pôde ser criado.\n"
                f"Nenhum dado foi alterado.\n\nDetalhes: {exc}"
            ) from exc

    conn = conectar_banco()
    cursor = conn.cursor()
    cursor.execute("BEGIN IMMEDIATE")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT UNIQUE,
            numero_ficha INTEGER,
            nome TEXT,
            cpf TEXT,
            rg TEXT,
            telefone TEXT,
            favorito INTEGER DEFAULT 0,
            endereco TEXT,
            referencia TEXT,
            limite REAL DEFAULT 0.0,
            saldo_devedor REAL DEFAULT 0.0
        )
    """)

    cursor.execute("PRAGMA table_info(clientes)")
    colunas=[c[1] for c in cursor.fetchall()]
    for coluna,tipo in {
        "numero_ficha":"INTEGER", "cpf":"TEXT", "rg":"TEXT", "telefone":"TEXT",
        "favorito":"INTEGER DEFAULT 0", "observacoes":"TEXT DEFAULT ''",
        "ficticio":"INTEGER DEFAULT 0", "data_nascimento":"TEXT DEFAULT ''",
        "origem_migracao":"TEXT DEFAULT ''", "email":"TEXT DEFAULT ''",
        "inscricao_estadual":"TEXT DEFAULT ''", "contribuinte_icms":"INTEGER DEFAULT 0",
        "fiscal_logradouro":"TEXT DEFAULT ''", "fiscal_numero":"TEXT DEFAULT ''",
        "fiscal_bairro":"TEXT DEFAULT ''", "fiscal_codigo_municipio":"TEXT DEFAULT ''",
        "fiscal_municipio":"TEXT DEFAULT ''", "fiscal_uf":"TEXT DEFAULT ''",
        "fiscal_cep":"TEXT DEFAULT ''",
    }.items():
        if coluna not in colunas:
            cursor.execute(f"ALTER TABLE clientes ADD COLUMN {coluna} {tipo}")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historico_clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER NOT NULL,
            evento TEXT NOT NULL,
            detalhes TEXT,
            data TEXT NOT NULL,
            FOREIGN KEY (cliente_id) REFERENCES clientes (id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movimentacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER,
            tipo TEXT,
            descricao TEXT,
            valor REAL,
            data TEXT,
            vencimento TEXT,
            status_pagamento TEXT DEFAULT 'PENDENTE',
            total_parcelas INTEGER DEFAULT 1,
            parcelas_atrasadas INTEGER DEFAULT 0,
            FOREIGN KEY (cliente_id) REFERENCES clientes (id)
        )
    """)

    cursor.execute("PRAGMA table_info(movimentacoes)")
    colunas_mov = [c[1] for c in cursor.fetchall()]
    if "valor_aberto" not in colunas_mov:
        cursor.execute("ALTER TABLE movimentacoes ADD COLUMN valor_aberto REAL")
    if "origem_sistema" not in colunas_mov:
        cursor.execute("ALTER TABLE movimentacoes ADD COLUMN origem_sistema TEXT DEFAULT ''")
    if "origem_id" not in colunas_mov:
        cursor.execute("ALTER TABLE movimentacoes ADD COLUMN origem_id TEXT DEFAULT ''")
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_mov_origem ON movimentacoes(origem_sistema, origem_id) WHERE origem_sistema <> '' AND origem_id <> ''")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_mov_tipo_data ON movimentacoes(tipo, data)")
    cursor.execute("""
        UPDATE movimentacoes
        SET valor_aberto = CASE
            WHEN tipo = 'COMPRA' AND status_pagamento = 'PAGO' THEN 0
            WHEN tipo = 'COMPRA' THEN COALESCE(valor, 0)
            ELSE 0
        END
        WHERE valor_aberto IS NULL
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS parcelas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            movimentacao_id INTEGER,
            numero_parcela INTEGER,
            valor_parcela REAL,
            vencimento TEXT,
            status TEXT DEFAULT 'PENDENTE',
            valor_pago REAL DEFAULT 0,
            data_pagamento TEXT DEFAULT '',
            atraso_registrado INTEGER DEFAULT 0,
            dados_confiaveis INTEGER DEFAULT 1,
            FOREIGN KEY (movimentacao_id) REFERENCES movimentacoes (id)
        )
    """)
    cursor.execute("PRAGMA table_info(parcelas)")
    colunas_parcelas = [c[1] for c in cursor.fetchall()]
    for coluna, tipo in {
        "valor_pago": "REAL DEFAULT 0",
        "data_pagamento": "TEXT DEFAULT ''",
        "atraso_registrado": "INTEGER DEFAULT 0",
        "dados_confiaveis": "INTEGER DEFAULT 1"
    }.items():
        if coluna not in colunas_parcelas:
            cursor.execute(f"ALTER TABLE parcelas ADD COLUMN {coluna} {tipo}")

    # Compras antigas sem detalhamento de parcelas recebem um registro legado.
    # Elas continuam preservadas, mas não são classificadas como pontuais/atrasadas
    # sem evidência suficiente para evitar um resultado financeiro enganoso.
    cursor.execute("""
        INSERT INTO parcelas
            (movimentacao_id, numero_parcela, valor_parcela, vencimento, status,
             valor_pago, data_pagamento, atraso_registrado, dados_confiaveis)
        SELECT m.id, 1, COALESCE(m.valor, 0), COALESCE(m.vencimento, ''),
               CASE WHEN m.status_pagamento='PAGO' THEN 'PAGO'
                    WHEN m.status_pagamento='PARCIAL' THEN 'PARCIAL' ELSE 'PENDENTE' END,
               CASE WHEN m.status_pagamento='PAGO' THEN COALESCE(m.valor, 0)
                    ELSE MAX(0, COALESCE(m.valor, 0)-COALESCE(m.valor_aberto, m.valor, 0)) END,
               '', 0, 0
        FROM movimentacoes m
        WHERE m.tipo='COMPRA'
          AND NOT EXISTS (SELECT 1 FROM parcelas p WHERE p.movimentacao_id=m.id)
    """)

    # Cobranças e lembretes de promissórias (schema 5).
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lembretes_promissorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER NOT NULL,
            parcela_id INTEGER NOT NULL,
            dias_antecedencia INTEGER NOT NULL DEFAULT 1,
            observacao TEXT DEFAULT '',
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL,
            ultimo_aviso_em TEXT DEFAULT '',
            UNIQUE(parcela_id),
            FOREIGN KEY (cliente_id) REFERENCES clientes(id),
            FOREIGN KEY (parcela_id) REFERENCES parcelas(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contatos_cobranca (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER NOT NULL,
            parcela_id INTEGER,
            tipo TEXT NOT NULL DEFAULT 'COBRANCA',
            resultado TEXT DEFAULT '',
            observacao TEXT DEFAULT '',
            proximo_contato TEXT DEFAULT '',
            data TEXT NOT NULL,
            FOREIGN KEY (cliente_id) REFERENCES clientes(id),
            FOREIGN KEY (parcela_id) REFERENCES parcelas(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_lembretes_ativos ON lembretes_promissorias(ativo, parcela_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_contatos_cliente_data ON contatos_cobranca(cliente_id, data)")

    # Etapa 3.2.1 — Catálogo de produtos, categorias e tipo do produto.
    # A migração é aditiva para preservar integralmente os bancos existentes.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categorias_produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL COLLATE NOCASE UNIQUE,
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL,
            atualizado_em TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS marcas_produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL COLLATE NOCASE UNIQUE,
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL,
            atualizado_em TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fornecedores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            razao_social TEXT NOT NULL DEFAULT '',
            nome_fantasia TEXT NOT NULL COLLATE NOCASE UNIQUE,
            cnpj TEXT NOT NULL DEFAULT '',
            telefone TEXT NOT NULL DEFAULT '',
            email TEXT NOT NULL DEFAULT '',
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL,
            atualizado_em TEXT NOT NULL
        )
    """)
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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT NOT NULL COLLATE NOCASE UNIQUE,
            nome TEXT NOT NULL,
            preco_venda REAL NOT NULL DEFAULT 0,
            categoria_id INTEGER,
            marca_id INTEGER,
            fornecedor_id INTEGER,
            unidade_id INTEGER,
            tipo_produto TEXT NOT NULL DEFAULT 'MERCADORIA'
                CHECK (tipo_produto IN ('MERCADORIA', 'SERVICO')),
            controla_estoque INTEGER NOT NULL DEFAULT 1,
            participa_xml INTEGER NOT NULL DEFAULT 1,
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL,
            atualizado_em TEXT NOT NULL,
            FOREIGN KEY (categoria_id) REFERENCES categorias_produtos(id),
            FOREIGN KEY (marca_id) REFERENCES marcas_produtos(id),
            FOREIGN KEY (fornecedor_id) REFERENCES fornecedores(id),
            FOREIGN KEY (unidade_id) REFERENCES unidades_medida(id)
        )
    """)
    cursor.execute("PRAGMA table_info(produtos)")
    colunas_produtos = {linha[1] for linha in cursor.fetchall()}

    # Compatibilidade com bancos antigos: algumas versões possuíam uma tabela
    # produtos reduzida e, em certos casos, usavam ``descricao`` no lugar de
    # ``nome``. As colunas usadas por índices e telas precisam existir antes
    # da criação dos índices abaixo.
    colunas_base_produtos = {
        "codigo": "TEXT NOT NULL DEFAULT ''",
        "nome": "TEXT NOT NULL DEFAULT ''",
        "preco_venda": "REAL NOT NULL DEFAULT 0",
        "categoria_id": "INTEGER REFERENCES categorias_produtos(id)",
        "tipo_produto": "TEXT NOT NULL DEFAULT 'MERCADORIA'",
        "controla_estoque": "INTEGER NOT NULL DEFAULT 1",
        "participa_xml": "INTEGER NOT NULL DEFAULT 1",
        "ativo": "INTEGER NOT NULL DEFAULT 1",
        "criado_em": "TEXT NOT NULL DEFAULT ''",
        "atualizado_em": "TEXT NOT NULL DEFAULT ''",
    }
    for coluna, definicao in colunas_base_produtos.items():
        if coluna not in colunas_produtos:
            cursor.execute(f"ALTER TABLE produtos ADD COLUMN {coluna} {definicao}")
            colunas_produtos.add(coluna)

    if "descricao" in colunas_produtos:
        cursor.execute(
            "UPDATE produtos SET nome=descricao "
            "WHERE TRIM(COALESCE(nome,''))='' AND TRIM(COALESCE(descricao,''))<>''"
        )

    for coluna, definicao in {
        "marca_id": "INTEGER REFERENCES marcas_produtos(id)",
        "fornecedor_id": "INTEGER REFERENCES fornecedores(id)",
        "unidade_id": "INTEGER REFERENCES unidades_medida(id)",
        "unidade_compra_id": "INTEGER REFERENCES unidades_medida(id)",
        "fator_conversao": "REAL NOT NULL DEFAULT 1",
        "preco_custo": "REAL NOT NULL DEFAULT 0",
        "despesas_percentual": "REAL NOT NULL DEFAULT 0",
        "margem_lucro": "REAL NOT NULL DEFAULT 0",
        "codigo_barras": "TEXT NOT NULL DEFAULT ''",
        "ncm": "TEXT NOT NULL DEFAULT ''",
        "cest": "TEXT NOT NULL DEFAULT ''",
        "cfop": "TEXT NOT NULL DEFAULT ''",
        "fiscal_origin": "TEXT NOT NULL DEFAULT ''",
        "fiscal_csosn": "TEXT NOT NULL DEFAULT ''",
        "fiscal_icms_cst": "TEXT NOT NULL DEFAULT ''",
        "fiscal_icms_rate": "TEXT NOT NULL DEFAULT '0'",
        "fiscal_pis_cst": "TEXT NOT NULL DEFAULT ''",
        "fiscal_pis_rate": "TEXT NOT NULL DEFAULT '0'",
        "fiscal_cofins_cst": "TEXT NOT NULL DEFAULT ''",
        "fiscal_cofins_rate": "TEXT NOT NULL DEFAULT '0'",
        "fiscal_ipi_cst": "TEXT NOT NULL DEFAULT ''",
        "fiscal_ipi_rate": "TEXT NOT NULL DEFAULT '0'",
        "fiscal_ipi_enq": "TEXT NOT NULL DEFAULT ''",
        "fiscal_profile_source": "TEXT NOT NULL DEFAULT ''",
        "ibs_cbs_cst": "TEXT NOT NULL DEFAULT ''",
        "ibs_cbs_class": "TEXT NOT NULL DEFAULT ''",
        "ibs_uf_rate": "TEXT NOT NULL DEFAULT '0'",
        "ibs_city_rate": "TEXT NOT NULL DEFAULT '0'",
        "cbs_rate": "TEXT NOT NULL DEFAULT '0'",
        "estoque_atual": "REAL NOT NULL DEFAULT 0",
        "estoque_minimo": "REAL NOT NULL DEFAULT 0",
        "permite_estoque_negativo": "INTEGER NOT NULL DEFAULT 0",
    }.items():
        if coluna not in colunas_produtos:
            cursor.execute(f"ALTER TABLE produtos ADD COLUMN {coluna} {definicao}")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historico_precos_produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id INTEGER NOT NULL,
            preco_anterior REAL NOT NULL DEFAULT 0,
            preco_novo REAL NOT NULL DEFAULT 0,
            custo REAL NOT NULL DEFAULT 0,
            margem_percentual REAL NOT NULL DEFAULT 0,
            motivo TEXT NOT NULL DEFAULT '',
            data TEXT NOT NULL,
            FOREIGN KEY (produto_id) REFERENCES produtos(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_historico_precos_produto_data ON historico_precos_produtos(produto_id, data)")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS estoque_movimentacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id INTEGER NOT NULL,
            tipo TEXT NOT NULL CHECK(tipo IN ('ENTRADA','SAIDA','AJUSTE')),
            quantidade REAL NOT NULL,
            saldo_anterior REAL NOT NULL,
            saldo_atual REAL NOT NULL,
            origem TEXT NOT NULL DEFAULT '',
            origem_id TEXT NOT NULL DEFAULT '',
            motivo TEXT NOT NULL DEFAULT '',
            usuario TEXT NOT NULL DEFAULT 'Sistema',
            data TEXT NOT NULL,
            FOREIGN KEY(produto_id) REFERENCES produtos(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_estoque_mov_produto_data ON estoque_movimentacoes(produto_id, data)")
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_estoque_mov_origem_produto ON estoque_movimentacoes(origem, origem_id, produto_id) WHERE origem<>'' AND origem_id<>''")
    agora_catalogo = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""INSERT OR IGNORE INTO unidades_medida
        (sigla,descricao,permite_fracionado,ativo,criado_em,atualizado_em)
        VALUES('UN','Unidade',0,1,?,?)""", (agora_catalogo, agora_catalogo))
    cursor.execute("UPDATE produtos SET unidade_id=(SELECT id FROM unidades_medida WHERE sigla='UN') WHERE unidade_id IS NULL")
    cursor.execute("UPDATE produtos SET unidade_compra_id=unidade_id WHERE unidade_compra_id IS NULL")
    cursor.execute("UPDATE produtos SET fator_conversao=1 WHERE fator_conversao IS NULL OR fator_conversao<=0")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_produtos_nome ON produtos(nome COLLATE NOCASE)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_produtos_ativo_nome ON produtos(ativo DESC, nome COLLATE NOCASE, id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_produtos_categoria ON produtos(categoria_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_produtos_marca ON produtos(marca_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_produtos_fornecedor ON produtos(fornecedor_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_produtos_unidade ON produtos(unidade_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_produtos_unidade_compra ON produtos(unidade_compra_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_clientes_ficha_ordem ON clientes((numero_ficha IS NULL), numero_ficha, nome COLLATE NOCASE, id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_mov_pendente_cliente_vencimento ON movimentacoes(status_pagamento, cliente_id, vencimento)")
    from database.product_schema_migration import ProductSchemaMigration
    ProductSchemaMigration.migrate_connection(conn)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS produto_fornecedores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id INTEGER NOT NULL,
            fornecedor_id INTEGER NOT NULL,
            codigo_fornecedor TEXT NOT NULL DEFAULT '',
            unidade_fornecedor TEXT NOT NULL DEFAULT 'UN',
            fator_conversao REAL NOT NULL DEFAULT 1,
            ultimo_custo REAL NOT NULL DEFAULT 0,
            ultima_compra TEXT NOT NULL DEFAULT '',
            ativo INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (produto_id) REFERENCES produtos(id),
            FOREIGN KEY (fornecedor_id) REFERENCES fornecedores(id),
            UNIQUE(produto_id, fornecedor_id, codigo_fornecedor)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_produto_fornecedores_fornecedor ON produto_fornecedores(fornecedor_id)")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS nfe_importacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chave TEXT NOT NULL UNIQUE,
            numero TEXT NOT NULL DEFAULT '',
            fornecedor_cnpj TEXT NOT NULL DEFAULT '',
            fornecedor_nome TEXT NOT NULL DEFAULT '',
            arquivo_origem TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'CONCLUIDA',
            itens_total INTEGER NOT NULL DEFAULT 0,
            itens_criados INTEGER NOT NULL DEFAULT 0,
            itens_vinculados INTEGER NOT NULL DEFAULT 0,
            valor_total TEXT NOT NULL DEFAULT '0',
            data_importacao TEXT NOT NULL
        )
    """)
    colunas_nfe_importacoes = {
        str(row[1]).casefold() for row in cursor.execute("PRAGMA table_info(nfe_importacoes)").fetchall()
    }
    if "valor_total" not in colunas_nfe_importacoes:
        cursor.execute("ALTER TABLE nfe_importacoes ADD COLUMN valor_total TEXT NOT NULL DEFAULT '0'")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_nfe_importacoes_numero ON nfe_importacoes(numero)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_nfe_importacoes_cnpj ON nfe_importacoes(fornecedor_cnpj)")

    # Pedidos e recebimentos de compra (schema 12).
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pedidos_compra (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fornecedor_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'ABERTO'
                CHECK(status IN ('ABERTO','PARCIAL','RECEBIDO','CANCELADO')),
            observacao TEXT NOT NULL DEFAULT '',
            usuario TEXT NOT NULL DEFAULT 'Sistema',
            criado_em TEXT NOT NULL,
            atualizado_em TEXT NOT NULL,
            FOREIGN KEY(fornecedor_id) REFERENCES fornecedores(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pedidos_compra_fornecedor_status ON pedidos_compra(fornecedor_id,status)")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pedido_compra_itens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pedido_id INTEGER NOT NULL,
            produto_id INTEGER NOT NULL,
            quantidade_pedida REAL NOT NULL,
            quantidade_recebida REAL NOT NULL DEFAULT 0,
            custo_unitario REAL NOT NULL DEFAULT 0,
            valor_total REAL NOT NULL DEFAULT 0,
            observacao TEXT NOT NULL DEFAULT '',
            FOREIGN KEY(pedido_id) REFERENCES pedidos_compra(id) ON DELETE CASCADE,
            FOREIGN KEY(produto_id) REFERENCES produtos(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pedido_compra_itens_pedido ON pedido_compra_itens(pedido_id)")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recebimentos_compra (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pedido_id INTEGER NOT NULL,
            documento TEXT NOT NULL DEFAULT '',
            observacao TEXT NOT NULL DEFAULT '',
            usuario TEXT NOT NULL DEFAULT 'Sistema',
            data_recebimento TEXT NOT NULL,
            FOREIGN KEY(pedido_id) REFERENCES pedidos_compra(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_recebimentos_compra_pedido ON recebimentos_compra(pedido_id)")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recebimento_compra_itens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recebimento_id INTEGER NOT NULL,
            pedido_item_id INTEGER NOT NULL,
            produto_id INTEGER NOT NULL,
            quantidade REAL NOT NULL,
            custo_unitario REAL NOT NULL DEFAULT 0,
            valor_total REAL NOT NULL DEFAULT 0,
            FOREIGN KEY(recebimento_id) REFERENCES recebimentos_compra(id) ON DELETE CASCADE,
            FOREIGN KEY(pedido_item_id) REFERENCES pedido_compra_itens(id),
            FOREIGN KEY(produto_id) REFERENCES produtos(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_recebimento_itens_recebimento ON recebimento_compra_itens(recebimento_id)")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS assistant_operation_journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            idempotency_key TEXT NOT NULL UNIQUE,
            operation_kind TEXT NOT NULL,
            fingerprint TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('PENDING','COMMITTED')),
            result_json TEXT NOT NULL DEFAULT '',
            username TEXT NOT NULL,
            created_at TEXT NOT NULL,
            committed_at TEXT NOT NULL DEFAULT ''
        )
    """)
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_assistant_operation_kind_status "
        "ON assistant_operation_journal(operation_kind,status)"
    )

    # Financeiro essencial integrado (schema 13).
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS titulos_financeiros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL CHECK(tipo IN ('PAGAR','RECEBER')),
            origem TEXT NOT NULL DEFAULT 'MANUAL',
            origem_id TEXT NOT NULL DEFAULT '',
            pessoa_id INTEGER,
            pessoa_nome TEXT NOT NULL DEFAULT '',
            documento TEXT NOT NULL DEFAULT '',
            descricao TEXT NOT NULL DEFAULT '',
            data_emissao TEXT NOT NULL,
            data_vencimento TEXT NOT NULL,
            valor_original REAL NOT NULL DEFAULT 0,
            valor_original_decimal TEXT,
            valor_pago REAL NOT NULL DEFAULT 0,
            valor_pago_decimal TEXT,
            status TEXT NOT NULL DEFAULT 'ABERTO'
                CHECK(status IN ('ABERTO','PARCIAL','PAGO','CANCELADO')),
            observacao TEXT NOT NULL DEFAULT '',
            criado_em TEXT NOT NULL,
            atualizado_em TEXT NOT NULL
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_titulos_tipo_status_vencimento ON titulos_financeiros(tipo,status,data_vencimento)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_titulos_origem ON titulos_financeiros(origem,origem_id)")
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_titulos_origem_unica
        ON titulos_financeiros(tipo,origem,origem_id,documento)
        WHERE origem_id<>'' AND status<>'CANCELADO'
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pagamentos_titulos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo_id INTEGER NOT NULL,
            valor REAL NOT NULL,
            valor_decimal TEXT,
            forma_pagamento TEXT NOT NULL DEFAULT '',
            observacao TEXT NOT NULL DEFAULT '',
            usuario TEXT NOT NULL DEFAULT 'Sistema',
            data_pagamento TEXT NOT NULL,
            FOREIGN KEY(titulo_id) REFERENCES titulos_financeiros(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pagamentos_titulo ON pagamentos_titulos(titulo_id)")

    # Assistente de NF-e de devolução (schema 9).
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS nfe_documentos_origem (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chave TEXT NOT NULL DEFAULT '',
            numero TEXT NOT NULL DEFAULT '',
            emitente_nome TEXT NOT NULL DEFAULT '',
            emitente_documento TEXT NOT NULL DEFAULT '',
            destinatario_nome TEXT NOT NULL DEFAULT '',
            destinatario_documento TEXT NOT NULL DEFAULT '',
            data_emissao TEXT NOT NULL DEFAULT '',
            serie TEXT NOT NULL DEFAULT '',
            modelo TEXT NOT NULL DEFAULT '',
            valor_total REAL NOT NULL DEFAULT 0,
            arquivo_origem TEXT NOT NULL DEFAULT '',
            criado_em TEXT NOT NULL,
            atualizado_em TEXT NOT NULL
        )
    """)
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_nfe_documentos_origem_chave ON nfe_documentos_origem(chave) WHERE chave<>''")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_nfe_documentos_origem_numero ON nfe_documentos_origem(numero)")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS nfe_documentos_origem_itens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            documento_id INTEGER NOT NULL,
            item_numero INTEGER NOT NULL,
            codigo TEXT NOT NULL DEFAULT '',
            descricao TEXT NOT NULL DEFAULT '',
            quantidade REAL NOT NULL DEFAULT 0,
            unidade TEXT NOT NULL DEFAULT 'UN',
            valor_unitario REAL NOT NULL DEFAULT 0,
            valor_total REAL NOT NULL DEFAULT 0,
            ncm TEXT NOT NULL DEFAULT '',
            cfop TEXT NOT NULL DEFAULT '',
            cest TEXT NOT NULL DEFAULT '',
            codigo_barras TEXT NOT NULL DEFAULT '',
            origem_mercadoria TEXT NOT NULL DEFAULT '',
            cst_icms TEXT NOT NULL DEFAULT '',
            csosn TEXT NOT NULL DEFAULT '',
            cst_pis TEXT NOT NULL DEFAULT '',
            cst_cofins TEXT NOT NULL DEFAULT '',
            FOREIGN KEY(documento_id) REFERENCES nfe_documentos_origem(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_nfe_origem_itens_documento ON nfe_documentos_origem_itens(documento_id)")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS nfe_devolucoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            documento_origem_id INTEGER NOT NULL,
            tipo TEXT NOT NULL CHECK(tipo IN ('INTEGRAL','PARCIAL')),
            motivo TEXT NOT NULL DEFAULT '',
            observacoes TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'RASCUNHO',
            valor_total REAL NOT NULL DEFAULT 0,
            numero_devolucao TEXT NOT NULL DEFAULT '',
            xml_rascunho TEXT NOT NULL DEFAULT '',
            hash_xml TEXT NOT NULL DEFAULT '',
            finalizado_em TEXT NOT NULL DEFAULT '',
            criado_em TEXT NOT NULL,
            atualizado_em TEXT NOT NULL,
            FOREIGN KEY(documento_origem_id) REFERENCES nfe_documentos_origem(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_nfe_devolucoes_origem ON nfe_devolucoes(documento_origem_id)")
    # Exportação e finalização de rascunhos de devolução (schema 10).
    colunas_devolucao = {row[1] for row in cursor.execute("PRAGMA table_info(nfe_devolucoes)").fetchall()}
    for coluna, definicao in (
        ("numero_devolucao", "TEXT NOT NULL DEFAULT ''"),
        ("xml_rascunho", "TEXT NOT NULL DEFAULT ''"),
        ("hash_xml", "TEXT NOT NULL DEFAULT ''"),
        ("finalizado_em", "TEXT NOT NULL DEFAULT ''"),
    ):
        if coluna not in colunas_devolucao:
            cursor.execute(f"ALTER TABLE nfe_devolucoes ADD COLUMN {coluna} {definicao}")
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_nfe_devolucoes_numero ON nfe_devolucoes(numero_devolucao) WHERE numero_devolucao<>''")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS nfe_devolucao_itens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            devolucao_id INTEGER NOT NULL,
            item_origem_id INTEGER NOT NULL,
            quantidade REAL NOT NULL,
            valor_unitario REAL NOT NULL DEFAULT 0,
            valor_total REAL NOT NULL DEFAULT 0,
            FOREIGN KEY(devolucao_id) REFERENCES nfe_devolucoes(id) ON DELETE CASCADE,
            FOREIGN KEY(item_origem_id) REFERENCES nfe_documentos_origem_itens(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_nfe_devolucao_itens_devolucao ON nfe_devolucao_itens(devolucao_id)")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS configuracoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chave TEXT UNIQUE,
            valor TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            versao_origem INTEGER NOT NULL,
            versao_destino INTEGER NOT NULL,
            data TEXT NOT NULL,
            backup_path TEXT DEFAULT '',
            status TEXT NOT NULL,
            detalhes TEXT DEFAULT ''
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS log_acesso_admin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            sucesso INTEGER NOT NULL,
            detalhes TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS log_migracao (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            arquivo TEXT NOT NULL,
            etapa TEXT NOT NULL,
            status TEXT NOT NULL,
            detalhes TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS migracoes_execucoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            arquivo TEXT NOT NULL,
            hash_arquivo TEXT NOT NULL,
            clientes_importados INTEGER DEFAULT 0,
            movimentacoes_importadas INTEGER DEFAULT 0,
            saldo_total REAL DEFAULT 0,
            status TEXT NOT NULL,
            detalhes TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS migracao_nabimig_ids (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_system TEXT NOT NULL,
            entity TEXT NOT NULL,
            source_id TEXT NOT NULL,
            target_table TEXT NOT NULL,
            target_id INTEGER NOT NULL,
            UNIQUE(source_system, entity, source_id),
            UNIQUE(target_table, target_id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS migracao_nabimig_itens_venda (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_system TEXT NOT NULL,
            source_id TEXT NOT NULL,
            sale_source_id TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            quantidade REAL NOT NULL,
            valor_unitario REAL NOT NULL,
            valor_total REAL NOT NULL,
            UNIQUE(source_system, source_id),
            FOREIGN KEY(product_id) REFERENCES produtos(id)
        )
    """)
    # Controle financeiro opcional e documentos emitidos
    cursor.execute("PRAGMA table_info(movimentacoes)")
    colunas_mov = [c[1] for c in cursor.fetchall()]
    for coluna, tipo in {
        "forma_pagamento": "TEXT DEFAULT ''",
        "responsavel": "TEXT DEFAULT ''",
        "documento_numero": "TEXT DEFAULT ''"
    }.items():
        if coluna not in colunas_mov:
            cursor.execute(f"ALTER TABLE movimentacoes ADD COLUMN {coluna} {tipo}")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS caixa_aberturas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_caixa TEXT NOT NULL UNIQUE,
            valor_inicial REAL DEFAULT 0,
            responsavel TEXT DEFAULT '',
            observacao TEXT DEFAULT '',
            criado_em TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fechamentos_caixa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_caixa TEXT NOT NULL,
            valor_esperado REAL DEFAULT 0,
            valor_contado REAL,
            diferenca REAL,
            responsavel TEXT DEFAULT '',
            observacao TEXT DEFAULT '',
            pdf_path TEXT DEFAULT '',
            criado_em TEXT NOT NULL
        )
    """)
    # Checkpoint 41: sessões de caixa pertencem ao terminal físico. As vendas e
    # recebimentos continuam sendo agregados de ``movimentacoes``; somente
    # operações próprias (sangria/suprimento) são gravadas separadamente.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cash_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            terminal TEXT NOT NULL,
            opened_by TEXT NOT NULL,
            opened_at TEXT NOT NULL,
            opening_balance TEXT NOT NULL DEFAULT '0.00',
            opening_mode TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'ABERTO'
                CHECK(status IN ('ABERTO','FECHADO')),
            closed_by TEXT DEFAULT '',
            closed_at TEXT DEFAULT '',
            expected_cash TEXT,
            counted_cash TEXT,
            difference TEXT,
            closing_note TEXT DEFAULT ''
        )
    """)
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_cash_session_terminal_open
        ON cash_sessions(terminal) WHERE status='ABERTO'
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cash_sessions_terminal_opened ON cash_sessions(terminal, opened_at)")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cash_movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cash_session_id INTEGER NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('SANGRIA','SUPRIMENTO')),
            amount TEXT NOT NULL,
            payment_method TEXT NOT NULL DEFAULT 'DINHEIRO',
            source TEXT NOT NULL DEFAULT 'CAIXA',
            source_id TEXT NOT NULL DEFAULT '',
            user_id TEXT NOT NULL,
            note TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY(cash_session_id) REFERENCES cash_sessions(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cash_movements_session ON cash_movements(cash_session_id,created_at)")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fiscal_sale_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER NOT NULL UNIQUE,
            reservation_id TEXT NOT NULL UNIQUE,
            access_key TEXT NOT NULL UNIQUE,
            model TEXT NOT NULL CHECK(model IN ('55','65')),
            environment TEXT NOT NULL CHECK(environment IN ('HOMOLOGACAO','PRODUCAO')),
            status TEXT NOT NULL DEFAULT 'RASCUNHO',
            xml_b64 TEXT NOT NULL,
            queue_id TEXT NOT NULL DEFAULT '',
            protocol TEXT NOT NULL DEFAULT '',
            last_error TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(sale_id) REFERENCES movimentacoes(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_fiscal_sale_status ON fiscal_sale_documents(status,created_at)")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fiscal_outbox (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER,
            fiscal_document_id INTEGER,
            access_key TEXT NOT NULL DEFAULT '',
            environment TEXT NOT NULL CHECK(environment IN ('HOMOLOGACAO','PRODUCAO')),
            operation TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDENTE'
                CHECK(status IN ('PENDENTE','PROCESSANDO','ERRO','RESPOSTA_DESCONHECIDA','CONCLUIDO','CANCELADO','FALHA')),
            attempts INTEGER NOT NULL DEFAULT 0 CHECK(attempts >= 0),
            max_attempts INTEGER NOT NULL DEFAULT 5 CHECK(max_attempts > 0),
            retry_minutes INTEGER NOT NULL DEFAULT 5 CHECK(retry_minutes > 0),
            next_attempt_at TEXT,
            worker_id TEXT NOT NULL DEFAULT '',
            claimed_at TEXT,
            lease_until TEXT,
            receipt TEXT NOT NULL DEFAULT '',
            last_error_code TEXT NOT NULL DEFAULT '',
            last_error_message TEXT NOT NULL DEFAULT '',
            model TEXT NOT NULL DEFAULT '55' CHECK(model IN ('55','65')),
            reservation_id TEXT NOT NULL DEFAULT '',
            xml_b64 TEXT NOT NULL DEFAULT '',
            original_xml_b64 TEXT NOT NULL DEFAULT '',
            actor TEXT NOT NULL DEFAULT '',
            contingency INTEGER NOT NULL DEFAULT 0 CHECK(contingency IN (0,1)),
            contingency_deadline_at TEXT NOT NULL DEFAULT '',
            legacy_id TEXT NOT NULL DEFAULT '',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(sale_id) REFERENCES movimentacoes(id),
            FOREIGN KEY(fiscal_document_id) REFERENCES fiscal_sale_documents(id)
        )
    """)
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_fiscal_outbox_document ON fiscal_outbox(fiscal_document_id) WHERE fiscal_document_id IS NOT NULL")
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_fiscal_outbox_legacy ON fiscal_outbox(legacy_id) WHERE legacy_id != ''")
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_fiscal_outbox_authorization_key ON fiscal_outbox(access_key) WHERE access_key != '' AND operation IN ('autorizacao','recibo')")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_fiscal_outbox_claim ON fiscal_outbox(status,next_attempt_at,lease_until,created_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_fiscal_outbox_sale ON fiscal_outbox(sale_id,fiscal_document_id)")
    # A fila JSON antiga permanece intacta. A cópia para a outbox é idempotente
    # e ocorre dentro da mesma transação da atualização do schema.
    from services.fiscal_outbox_service import FiscalOutboxService
    FiscalOutboxService.migrate_legacy_in_transaction(conn)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fiscal_tax_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
            issuer_state TEXT NOT NULL DEFAULT 'BA',
            destination_state TEXT NOT NULL DEFAULT '*',
            tax_regime TEXT NOT NULL,
            ncm_prefix TEXT NOT NULL DEFAULT '',
            cest TEXT NOT NULL DEFAULT '',
            operation_kind TEXT NOT NULL DEFAULT 'VENDA',
            icms_code TEXT NOT NULL,
            icms_rate TEXT NOT NULL DEFAULT '0',
            icms_base_reduction TEXT NOT NULL DEFAULT '0',
            sn_credit_rate TEXT NOT NULL DEFAULT '0',
            st_mva TEXT NOT NULL DEFAULT '0',
            st_rate TEXT NOT NULL DEFAULT '0',
            fcp_st_rate TEXT NOT NULL DEFAULT '0',
            difal_internal_rate TEXT NOT NULL DEFAULT '0',
            difal_interstate_rate TEXT NOT NULL DEFAULT '0',
            difal_fcp_rate TEXT NOT NULL DEFAULT '0',
            benefit_code TEXT NOT NULL DEFAULT '',
            approved_by TEXT NOT NULL,
            approved_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_fiscal_tax_rules_match
        ON fiscal_tax_rules(active,issuer_state,destination_state,tax_regime,ncm_prefix,cest)
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fiscal_tax_rule_revisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id INTEGER NOT NULL,
            revision_number INTEGER NOT NULL,
            event_kind TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            previous_hash TEXT NOT NULL DEFAULT '',
            current_hash TEXT NOT NULL,
            actor TEXT NOT NULL DEFAULT 'NAO_INFORMADO',
            change_reason TEXT NOT NULL DEFAULT '',
            recorded_at TEXT NOT NULL,
            UNIQUE(rule_id,revision_number),
            FOREIGN KEY(rule_id) REFERENCES fiscal_tax_rules(id)
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_fiscal_tax_rule_revisions_rule
        ON fiscal_tax_rule_revisions(rule_id,revision_number)
    """)
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_fiscal_tax_rule_revisions_no_update
        BEFORE UPDATE ON fiscal_tax_rule_revisions
        BEGIN
            SELECT RAISE(ABORT, 'historico fiscal append-only nao pode ser alterado');
        END
    """)
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_fiscal_tax_rule_revisions_no_delete
        BEFORE DELETE ON fiscal_tax_rule_revisions
        BEGIN
            SELECT RAISE(ABORT, 'historico fiscal append-only nao pode ser excluido');
        END
    """)
    # Backfill técnico idempotente. Ele preserva o estado encontrado, mas não
    # autentica juridicamente autoria, aprovação contábil ou não repúdio.
    from services.fiscal_tax_rule_service import FiscalTaxRuleService
    revision_columns = FiscalTaxRuleService.REVISION_PAYLOAD_COLUMNS
    legacy_rules = cursor.execute(
        f"SELECT {','.join(revision_columns)} FROM fiscal_tax_rules r "
        "WHERE NOT EXISTS (SELECT 1 FROM fiscal_tax_rule_revisions h WHERE h.rule_id=r.id)"
    ).fetchall()
    for legacy_row in legacy_rules:
        payload = dict(zip(revision_columns, legacy_row))
        payload["active"] = bool(payload["active"])
        payload_json = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        recorded_at = str(payload.get("updated_at") or payload.get("created_at") or datetime.now().astimezone().isoformat())
        current_hash = FiscalTaxRuleService.revision_hash(
            rule_id=int(payload["id"]), revision_number=1,
            event_kind="LEGACY_SEM_TRILHA", payload_json=payload_json,
            previous_hash="", actor="NAO_INFORMADO", change_reason="",
            recorded_at=recorded_at,
        )
        cursor.execute(
            "INSERT INTO fiscal_tax_rule_revisions "
            "(rule_id,revision_number,event_kind,payload_json,previous_hash,current_hash,actor,change_reason,recorded_at) "
            "VALUES (?,1,'LEGACY_SEM_TRILHA',?,'',?,'NAO_INFORMADO','',?)",
            (int(payload["id"]), payload_json, current_hash, recorded_at),
        )
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documentos_emitidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            movimentacao_id INTEGER,
            categoria TEXT NOT NULL,
            caminho_pdf TEXT NOT NULL,
            numero_documento TEXT DEFAULT '',
            data_emissao TEXT NOT NULL,
            FOREIGN KEY (movimentacao_id) REFERENCES movimentacoes(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS auditoria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            usuario TEXT DEFAULT 'Sistema',
            modulo TEXT NOT NULL,
            acao TEXT NOT NULL,
            objeto TEXT DEFAULT '',
            detalhes TEXT DEFAULT '',
            resultado TEXT NOT NULL DEFAULT 'SUCESSO'
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_auditoria_data ON auditoria(data)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_auditoria_modulo ON auditoria(modulo)")

    configs_padrao = [
        ("nome_loja", "NabiCode — Gerenciador de Crediário"),
        ("db_schema_version", str(DB_SCHEMA_VERSION)),
        ("modo_operacao", "COMERCIAL"),
        ("proxima_ficha", "5500"),
        ("cnpj", "00.000.000/0001-00"),
        ("telefone", "(74) 99805-5735"),
        ("email", "gustavoiglbalt@gmail.com"),
        ("endereco", "Rua Principal, Centro"),
        ("tipo_impressora", "Termica"),
        ("impressora_nome", "Padrão do Sistema"),
        ("impressora_recibo", "Padrão do Sistema"),
        ("formato_impressao_recibo", "Cupom 80 mm"),
        ("impressora_entrega", "Padrão do Sistema"),
        ("formato_impressao_entrega", "Cupom 80 mm"),
        ("impressora_ficha", "Padrão do Sistema"),
        ("formato_impressao_ficha", "A4"),
        ("impressora_historico", "Padrão do Sistema"),
        ("formato_impressao_historico", "A4"),
        ("formato_impressao_fechamento", "A4"),
        ("impressao_corte_automatico", "1"),
        ("impressao_tipo_corte", "PARCIAL"),
        ("impressao_linhas_antes_corte", "4"),
        ("pasta_pendrive", BACKUP_DIR),
        ("pasta_backup_local", BACKUP_DIR),
        ("pasta_backup_nuvem", ""),
        ("backup_diario_ativo", "1"),
        ("ultimo_backup_diario", ""),
        ("aparencia_sistema", "Dark"),
        ("cor_destaque", "Verde Nabi"),
        ("rodape_cupom", "Guarde este comprovante.\nObrigado pela preferência!"),
        ("licenca_validade", (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")),
        ("licenca_bloqueada", "0"),
        ("admin_senha_hash", "c6e9ec8af02a450b41405d7f905d7ce4061bd7559d576d5dd56efd3071b399ef"),
        ("login_usuarios_habilitado", "0"),
        ("licenca_expira_em", ""),
        ("modelo_recibo", "Térmica 80 mm"),
        ("modelo_entrega", "A4"),
        ("modelo_ficha", "A4"),
        ("modelo_historico", "A4"),
        ("modelo_fechamento", "A4"),
        ("impressao_fonte", "Helvetica"),
        ("modelo_cupom_visual", "Clássico"),
        ("impressao_fonte_tamanho", "10"),
        ("impressao_titulo_tamanho", "15"),
        ("impressao_espacamento", "1.25"),
        ("impressao_margem_mm", "7"),
        ("impressao_vias", "1"),
        ("impressao_mostrar_logo", "0"),
        ("impressao_logo_path", ""),
        ("impressao_mostrar_endereco", "1"),
        ("impressao_mostrar_telefone", "1"),
        ("impressao_mostrar_cnpj", "1"),
        ("impressao_mostrar_email", "0"),
        ("impressao_mostrar_assinatura", "1"),
        ("impressao_qrcode", "1"),
        ("impressao_avanco_linhas", "3"),
        ("impressao_acao_pos_pdf", "PERGUNTAR"),
        ("impressao_salvar_pdf_automatico", "1")
    ]
    for chave, valor in configs_padrao:
        cursor.execute("INSERT OR IGNORE INTO configuracoes (chave, valor) VALUES (?, ?)", (chave, valor))

    # 2.4.94: bases migradas podiam carregar o corte térmico desligado por um
    # default duplicado antigo. Habilita uma única vez; depois disso a escolha
    # do usuário volta a ser soberana e pode ser desligada nas configurações.
    corte_marker = cursor.execute(
        "SELECT valor FROM configuracoes WHERE chave='migracao_corte_automatico_2494'"
    ).fetchone()
    if not corte_marker:
        cursor.execute(
            "UPDATE configuracoes SET valor='1' WHERE chave='impressao_corte_automatico'"
        )
        cursor.execute(
            "INSERT OR REPLACE INTO configuracoes (chave, valor) VALUES ('migracao_corte_automatico_2494', '1')"
        )
    # Migra apenas a senha padrão antiga; senhas personalizadas permanecem intactas.
    senha_antiga = hashlib.sha256("NabiCode@123".encode("utf-8")).hexdigest()
    senha_nova = "c6e9ec8af02a450b41405d7f905d7ce4061bd7559d576d5dd56efd3071b399ef"
    cursor.execute("UPDATE configuracoes SET valor=? WHERE chave='admin_senha_hash' AND valor=?", (senha_nova, senha_antiga))

    cursor.execute("SELECT COUNT(*) FROM clientes")
    if cursor.fetchone()[0] == 0:
        demos = [
            ("CLI001", 1, "Ana Souza", "111.111.111-11", "11.111.111-1", "(11) 98888-1111", "Rua das Flores, 10", "Cliente fictício para testes", 1200.0, 0.0, 1),
            ("CLI002", 2, "Bruno Lima", "222.222.222-22", "22.222.222-2", "(11) 97777-2222", "Av. Central, 250", "Recebe no dia 5", 800.0, 185.0, 1),
            ("CLI003", 3, "Carla Mendes", "333.333.333-33", "33.333.333-3", "(11) 96666-3333", "Rua do Comércio, 75", "Prefere contato por telefone", 1500.0, 640.0, 1),
        ]
        cursor.executemany("""INSERT INTO clientes
            (codigo, numero_ficha, nome, cpf, rg, telefone, endereco, observacoes, limite, saldo_devedor, ficticio)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", demos)
        agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        cursor.execute("SELECT id FROM clientes WHERE ficticio = 1")
        for (cid,) in cursor.fetchall():
            cursor.execute("INSERT INTO historico_clientes (cliente_id, evento, detalhes, data) VALUES (?, ?, ?, ?)",
                           (cid, "CADASTRO", "Cadastro fictício criado automaticamente para demonstração.", agora))

    from database.product_decimal_migration import ProductDecimalMigration
    ProductDecimalMigration.migrate_connection(conn)

    cursor.execute("INSERT OR REPLACE INTO configuracoes (chave, valor) VALUES ('db_schema_version', ?)", (str(DB_SCHEMA_VERSION),))
    if ULTIMA_ATUALIZACAO_BANCO["executada"]:
        cursor.execute("""INSERT INTO schema_migrations
            (versao_origem, versao_destino, data, backup_path, status, detalhes)
            VALUES (?, ?, ?, ?, 'SUCESSO', ?)""",
            (versao_anterior, DB_SCHEMA_VERSION, datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
             ULTIMA_ATUALIZACAO_BANCO["backup"], "Estrutura verificada e atualizada automaticamente."))
    conn.commit()
    conn.close()
    return primeira_instalacao
