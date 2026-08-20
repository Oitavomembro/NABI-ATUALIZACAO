from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from database import DatabaseManager
from database.sqlite_introspection import table_exists
from repositories.decimal_storage import DecimalStorage


class NFeImportRepository:
    """Persistência de histórico de NF-e e vínculos produto-fornecedor."""

    def __init__(self, database: DatabaseManager) -> None:
        self.database = database


    _table_exists = staticmethod(table_exists)

    def obter_ou_criar_fornecedor_transacao(self, connection, cnpj: str, nome: str, agora: str) -> int:
        cnpj_limpo = "".join(ch for ch in str(cnpj or "") if ch.isdigit())
        row = None
        if cnpj_limpo:
            row = connection.execute(
                "SELECT id FROM fornecedores WHERE REPLACE(REPLACE(REPLACE(cnpj,'.',''),'/',''),'-','')=? LIMIT 1",
                (cnpj_limpo,),
            ).fetchone()
        if row is None and str(nome or "").strip():
            nome_limpo = " ".join(str(nome).split())
            row = connection.execute(
                "SELECT id FROM fornecedores WHERE nome_fantasia=? COLLATE NOCASE OR razao_social=? COLLATE NOCASE LIMIT 1",
                (nome_limpo, nome_limpo),
            ).fetchone()
        if row:
            return int(row["id"])
        nome_limpo = " ".join(str(nome or f"Fornecedor {cnpj_limpo or 'XML'}").split())
        cursor = connection.execute(
            """INSERT INTO fornecedores
               (razao_social,nome_fantasia,cnpj,telefone,email,ativo,criado_em,atualizado_em)
               VALUES(?,?,?,?,?,1,?,?)""",
            (nome_limpo, nome_limpo, str(cnpj or ""), "", "", agora, agora),
        )
        return int(cursor.lastrowid)

    def obter_ou_criar_unidade_transacao(self, connection, sigla: str, agora: str) -> int:
        sigla = str(sigla or "UN").strip().upper() or "UN"
        row = connection.execute(
            "SELECT id FROM unidades_medida WHERE sigla=? COLLATE NOCASE LIMIT 1", (sigla,)
        ).fetchone()
        if row:
            return int(row["id"])
        cursor = connection.execute(
            """INSERT INTO unidades_medida
               (sigla,descricao,permite_fracionado,ativo,criado_em,atualizado_em)
               VALUES(?,?,0,1,?,?)""",
            (sigla, f"Unidade importada do XML ({sigla})", agora, agora),
        )
        return int(cursor.lastrowid)

    def criar_produto_transacao(
        self, connection, *, item, preparado: dict[str, Any], fornecedor_id: int,
        unidade_id: int, unidade_compra_id: int, agora: str,
    ) -> int:
        codigo = str(preparado.get("codigo") or item.codigo or item.codigo_barras or "").strip()
        if not codigo:
            raise ValueError(f"O item {item.descricao} não possui código para criar o produto.")
        if connection.execute("SELECT 1 FROM produtos WHERE codigo=? COLLATE NOCASE", (codigo,)).fetchone():
            raise ValueError(f"Já existe produto com o código {codigo}.")
        preco_real, preco_decimal = DecimalStorage.pair(preparado["preco"], field="preço de venda")
        custo_real, custo_decimal = DecimalStorage.pair(preparado["custo"], field="preço de custo")
        margem_real, margem_decimal = DecimalStorage.pair(preparado["margem"], field="margem")
        fator_real, fator_decimal = DecimalStorage.pair(preparado["fator"], field="fator de conversão")
        product_name = str(preparado.get("descricao") or item.descricao or "").strip().upper()
        product_barcode = str(
            preparado.get("codigo_barras") or item.codigo_barras or ""
        ).strip()
        product_ncm = str(preparado.get("ncm") or item.ncm or "").strip()
        product_cest = str(preparado.get("cest") or item.cest or "").strip()
        product_columns = {
            str(row[1]) for row in connection.execute("PRAGMA table_info(produtos)").fetchall()
        }
        legacy_description_column = ",descricao" if "descricao" in product_columns else ""
        legacy_description_value = ",?" if legacy_description_column else ""
        cursor = connection.execute(
            f"""INSERT INTO produtos
               (codigo,nome{legacy_description_column},preco_venda,preco_custo,despesas_percentual,margem_lucro,
                preco_venda_decimal,preco_custo_decimal,despesas_percentual_decimal,margem_lucro_decimal,fator_conversao_decimal,
                categoria_id,marca_id,fornecedor_id,unidade_id,unidade_compra_id,fator_conversao,tipo_produto,controla_estoque,
                participa_xml,codigo_barras,ncm,cest,cfop,estoque_atual,estoque_minimo,permite_estoque_negativo,
                ativo,criado_em,atualizado_em)
               VALUES(?,?{legacy_description_value},?,?,?,?,?,?,?,?,?,NULL,NULL,?,?,?,?, 'MERCADORIA',1,1,?,?,?,?,0,0,0,1,?,?)""",
            (codigo, product_name, *((product_name,) if legacy_description_column else ()), preco_real, custo_real, 0.0, margem_real,
             preco_decimal, custo_decimal, "0", margem_decimal, fator_decimal, fornecedor_id, unidade_id,
             unidade_compra_id, fator_real, product_barcode, product_ncm,
             product_cest, "", agora, agora),
        )
        produto_id = int(cursor.lastrowid)
        self._salvar_tributacao_rtc(connection, produto_id=produto_id, item=item, preparado=preparado)
        connection.execute(
            """INSERT INTO historico_precos_produtos
               (produto_id,preco_anterior,preco_novo,custo,margem_percentual,
                preco_anterior_decimal,preco_novo_decimal,custo_decimal,margem_percentual_decimal,motivo,data)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (produto_id, 0.0, preco_real, custo_real, margem_real,
             "0", preco_decimal, custo_decimal, margem_decimal, "NFE_XML_CRIAR", agora),
        )
        return produto_id

    def atualizar_produto_transacao(
        self, connection, *, produto_id: int, item, preparado: dict[str, Any], fornecedor_id: int,
        unidade_id: int, unidade_compra_id: int, agora: str,
    ) -> None:
        atual = connection.execute(
            """SELECT COALESCE(preco_venda_decimal, CAST(preco_venda AS TEXT)) AS preco_venda,
                      COALESCE(preco_custo_decimal, CAST(preco_custo AS TEXT)) AS preco_custo,
                      codigo_barras,ncm,cest,cfop FROM produtos WHERE id=?""",
            (int(produto_id),),
        ).fetchone()
        if not atual:
            raise ValueError("Produto selecionado não localizado.")
        novo_preco = DecimalStorage.to_decimal(preparado["preco"], field="preço de venda")
        novo_custo = DecimalStorage.to_decimal(preparado["custo"], field="preço de custo")
        nova_margem = DecimalStorage.to_decimal(preparado["margem"], field="margem")
        novo_fator = DecimalStorage.to_decimal(preparado["fator"], field="fator de conversão")
        preco_real, preco_decimal = DecimalStorage.pair(novo_preco)
        custo_real, custo_decimal = DecimalStorage.pair(novo_custo)
        margem_real, margem_decimal = DecimalStorage.pair(nova_margem)
        fator_real, fator_decimal = DecimalStorage.pair(novo_fator)
        connection.execute(
            """UPDATE produtos SET fornecedor_id=?,unidade_id=?,unidade_compra_id=?,
               fator_conversao=?,fator_conversao_decimal=?,preco_custo=?,preco_custo_decimal=?,
               margem_lucro=?,margem_lucro_decimal=?,preco_venda=?,preco_venda_decimal=?,
               codigo_barras=CASE WHEN ?<>'' THEN ? ELSE codigo_barras END,
               ncm=CASE WHEN ?<>'' THEN ? ELSE ncm END, cest=CASE WHEN ?<>'' THEN ? ELSE cest END,
               atualizado_em=? WHERE id=?""",
            (fornecedor_id, unidade_id, unidade_compra_id, fator_real, fator_decimal, custo_real, custo_decimal,
             margem_real, margem_decimal, preco_real, preco_decimal,
             str(preparado.get("codigo_barras") or item.codigo_barras or ""), str(preparado.get("codigo_barras") or item.codigo_barras or ""),
             str(preparado.get("ncm") or item.ncm or ""), str(preparado.get("ncm") or item.ncm or ""),
             str(preparado.get("cest") or item.cest or ""), str(preparado.get("cest") or item.cest or ""), agora, int(produto_id)),
        )
        self._salvar_tributacao_rtc(connection, produto_id=int(produto_id), item=item, preparado=preparado)
        preco_anterior = DecimalStorage.to_decimal(atual["preco_venda"], field="preço anterior")
        custo_anterior = DecimalStorage.to_decimal(atual["preco_custo"], field="custo anterior")
        if preco_anterior != novo_preco or custo_anterior != novo_custo:
            connection.execute(
                """INSERT INTO historico_precos_produtos
                   (produto_id,preco_anterior,preco_novo,custo,margem_percentual,
                    preco_anterior_decimal,preco_novo_decimal,custo_decimal,margem_percentual_decimal,motivo,data)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (int(produto_id), DecimalStorage.legacy_real(preco_anterior), preco_real, custo_real, margem_real,
                 DecimalStorage.canonical(preco_anterior), preco_decimal, custo_decimal, margem_decimal,
                 "NFE_XML_ATUALIZAR", agora),
            )

    @staticmethod
    def _salvar_tributacao_rtc(connection, *, produto_id: int, item, preparado: dict[str, Any] | None = None) -> None:
        """Preserva a ficha RTC recebida no XML sem inferir regra tributária."""
        preparado = preparado or {}
        origin = str(preparado.get("origem_mercadoria") or getattr(item, "origem_mercadoria", "") or "").strip()
        if origin and origin not in set("012345678"):
            raise ValueError("O XML possui origem da mercadoria inválida.")
        if origin:
            connection.execute(
                """UPDATE produtos SET fiscal_origin=?,
                          fiscal_profile_source=CASE WHEN fiscal_profile_source='' THEN 'XML_IMPORT' ELSE fiscal_profile_source END
                     WHERE id=?""",
                (origin, int(produto_id)),
            )
        cst = str(getattr(item, "ibs_cbs_cst", "") or "").strip()
        classification = str(getattr(item, "ibs_cbs_class", "") or "").strip()
        if not cst and not classification:
            return
        if len(cst) != 3 or not cst.isdigit() or len(classification) != 6 or not classification.isdigit():
            raise ValueError("O XML possui CST ou classificação IBS/CBS inválida.")
        connection.execute(
            """UPDATE produtos
               SET ibs_cbs_cst=?, ibs_cbs_class=?, ibs_uf_rate=?, ibs_city_rate=?, cbs_rate=?
               WHERE id=?""",
            (
                cst,
                classification,
                str(getattr(item, "ibs_uf_rate", 0) or 0),
                str(getattr(item, "ibs_city_rate", 0) or 0),
                str(getattr(item, "cbs_rate", 0) or 0),
                int(produto_id),
            ),
        )

    def vincular_produto_fornecedor_transacao(
        self, connection, *, produto_id: int, fornecedor_id: int, codigo_fornecedor: str,
        unidade_fornecedor: str, fator_conversao: Decimal | float, ultimo_custo: Decimal | float, agora: str,
    ) -> None:
        fator_real, fator_decimal = DecimalStorage.pair(fator_conversao, field="fator de conversão do fornecedor")
        custo_real, custo_decimal = DecimalStorage.pair(ultimo_custo, field="último custo do fornecedor")
        connection.execute(
            """INSERT INTO produto_fornecedores
               (produto_id,fornecedor_id,codigo_fornecedor,unidade_fornecedor,fator_conversao,ultimo_custo,
                fator_conversao_decimal,ultimo_custo_decimal,ultima_compra,ativo)
               VALUES(?,?,?,?,?,?,?,?,?,1)
               ON CONFLICT(produto_id,fornecedor_id,codigo_fornecedor) DO UPDATE SET
               unidade_fornecedor=excluded.unidade_fornecedor,fator_conversao=excluded.fator_conversao,
               ultimo_custo=excluded.ultimo_custo,fator_conversao_decimal=excluded.fator_conversao_decimal,
               ultimo_custo_decimal=excluded.ultimo_custo_decimal,ultima_compra=excluded.ultima_compra,ativo=1""",
            (int(produto_id), int(fornecedor_id), str(codigo_fornecedor or ""), str(unidade_fornecedor or "UN"),
             fator_real, custo_real, fator_decimal, custo_decimal, agora),
        )

    def registrar_entrada_estoque_transacao(
        self, connection, *, produto_id: int, quantidade: float, origem_id: str, motivo: str, usuario: str, agora: str,
    ) -> int:
        if connection.execute(
            "SELECT 1 FROM estoque_movimentacoes WHERE origem='NFE_XML' AND origem_id=? AND produto_id=?",
            (str(origem_id), int(produto_id)),
        ).fetchone():
            raise ValueError("Este item já possui entrada de estoque para a NF-e.")
        produto = connection.execute(
            "SELECT estoque_atual,controla_estoque,tipo_produto FROM produtos WHERE id=?", (int(produto_id),)
        ).fetchone()
        if not produto:
            raise ValueError("Produto da entrada de estoque não localizado.")
        saldo_anterior = float(produto["estoque_atual"] or 0); saldo_atual = saldo_anterior + float(quantidade)
        connection.execute("UPDATE produtos SET estoque_atual=?,atualizado_em=? WHERE id=?", (saldo_atual, agora, int(produto_id)))
        cursor = connection.execute(
            """INSERT INTO estoque_movimentacoes
               (produto_id,tipo,quantidade,saldo_anterior,saldo_atual,origem,origem_id,motivo,usuario,data)
               VALUES(?,?,?,?,?,'NFE_XML',?,?,?,?)""",
            (int(produto_id), "ENTRADA", float(quantidade), saldo_anterior, saldo_atual, str(origem_id),
             str(motivo), str(usuario or "Sistema"), agora),
        )
        return int(cursor.lastrowid)

    def registrar_importacao_transacao(
        self, connection, *, documento, arquivo_origem: str, itens_criados: int, itens_vinculados: int, agora: str,
    ) -> int:
        cursor = connection.execute(
            """INSERT INTO nfe_importacoes
               (chave,numero,fornecedor_cnpj,fornecedor_nome,arquivo_origem,status,itens_total,itens_criados,itens_vinculados,valor_total,data_importacao)
               VALUES(?,?,?,?,?,'CONCLUIDA',?,?,?,?,?)""",
            (documento.chave, documento.numero, documento.cnpj, documento.fornecedor, arquivo_origem,
             len(documento.itens), int(itens_criados), int(itens_vinculados),
             DecimalStorage.canonical(getattr(documento, "valor_total", 0) or 0, field="valor total da NF-e"), agora),
        )
        return int(cursor.lastrowid)

    def registrar_financeiro_transacao(
        self, connection, *, documento, importacao_id: int, fornecedor_id: int, agora: str,
    ) -> int | None:
        if not self._table_exists(connection, "titulos_financeiros"):
            return None
        colunas = {row["name"] for row in connection.execute("PRAGMA table_info(titulos_financeiros)").fetchall()}
        obrigatorias = {"tipo","origem","origem_id","pessoa_id","pessoa_nome","documento","descricao",
                       "data_emissao","data_vencimento","valor_original","valor_pago","status","observacao",
                       "criado_em","atualizado_em"}
        if not obrigatorias.issubset(colunas):
            return None
        origem_id = str(importacao_id); documento_ref = str(documento.numero or documento.chave or importacao_id)
        existente = connection.execute(
            "SELECT id FROM titulos_financeiros WHERE tipo='PAGAR' AND origem='NFE_XML' AND origem_id=? AND documento=? AND status<>'CANCELADO'",
            (origem_id, documento_ref),
        ).fetchone()
        if existente:
            return int(existente["id"])
        valor = DecimalStorage.to_decimal(getattr(documento, "valor_total", 0) or 0, field="valor total da NF-e")
        if valor <= 0:
            valor = sum((DecimalStorage.to_decimal(item.valor_total or 0, field="valor do item da NF-e") for item in documento.itens), Decimal("0"))
        data_emissao = str(getattr(documento, "data_emissao", "") or agora[:10])[:10]
        legacy, canonical = DecimalStorage.pair(valor, field="valor total da NF-e")
        if {"valor_original_decimal", "valor_pago_decimal"}.issubset(colunas):
            cursor = connection.execute(
                """INSERT INTO titulos_financeiros
                   (tipo,origem,origem_id,pessoa_id,pessoa_nome,documento,descricao,data_emissao,data_vencimento,
                    valor_original,valor_original_decimal,valor_pago,valor_pago_decimal,status,observacao,criado_em,atualizado_em)
                   VALUES('PAGAR','NFE_XML',?,?,?,?,?,?,?, ?,?,0,'0','ABERTO',?,?,?)""",
                (origem_id, int(fornecedor_id), str(documento.fornecedor or ""), documento_ref,
                 f"NF-e de entrada {documento_ref}", data_emissao, data_emissao, legacy, canonical,
                 "Gerado automaticamente pela importação XML", agora, agora),
            )
        else:
            cursor = connection.execute(
                """INSERT INTO titulos_financeiros
                   (tipo,origem,origem_id,pessoa_id,pessoa_nome,documento,descricao,data_emissao,data_vencimento,
                    valor_original,valor_pago,status,observacao,criado_em,atualizado_em)
                   VALUES('PAGAR','NFE_XML',?,?,?,?,?,?,?, ?,0,'ABERTO',?,?,?)""",
                (origem_id, int(fornecedor_id), str(documento.fornecedor or ""), documento_ref,
                 f"NF-e de entrada {documento_ref}", data_emissao, data_emissao, legacy,
                 "Gerado automaticamente pela importação XML", agora, agora),
            )
        return int(cursor.lastrowid)


    def buscar_importacao_por_chave(self, chave: str) -> dict[str, Any] | None:
        chave = str(chave or "").strip()
        if not chave:
            return None
        row = self.database.fetch_one(
            "SELECT * FROM nfe_importacoes WHERE chave=?",
            (chave,),
        )
        return dict(row) if row else None

    def localizar_fornecedor(self, cnpj: str, nome: str = "") -> dict[str, Any] | None:
        cnpj_limpo = "".join(ch for ch in str(cnpj or "") if ch.isdigit())
        if cnpj_limpo:
            row = self.database.fetch_one(
                "SELECT * FROM fornecedores WHERE REPLACE(REPLACE(REPLACE(cnpj,'.',''),'/',''),'-','')=? LIMIT 1",
                (cnpj_limpo,),
            )
            if row:
                return dict(row)
        nome = " ".join(str(nome or "").split())
        if nome:
            row = self.database.fetch_one(
                "SELECT * FROM fornecedores WHERE nome_fantasia=? COLLATE NOCASE OR razao_social=? COLLATE NOCASE LIMIT 1",
                (nome, nome),
            )
            if row:
                return dict(row)
        return None

    def localizar_unidade(self, sigla: str) -> dict[str, Any] | None:
        sigla = str(sigla or "UN").strip().upper() or "UN"
        row = self.database.fetch_one(
            "SELECT * FROM unidades_medida WHERE sigla=? COLLATE NOCASE LIMIT 1",
            (sigla,),
        )
        return dict(row) if row else None

    def listar_produtos_referencia(self) -> list[dict[str, Any]]:
        """Lista campos mínimos usados na comparação inteligente do XML.

        O conjunto reduzido mantém compatibilidade com bancos antigos que ainda
        não possuam todas as colunas opcionais do cadastro atual.
        """
        rows = self.database.fetch_all(
            """SELECT id,codigo,nome,COALESCE(codigo_barras,'') AS codigo_barras
               FROM produtos
               ORDER BY nome,id"""
        )
        return [dict(row) for row in rows]

    def localizar_produto(self, codigo: str, codigo_barras: str = "", descricao: str = "") -> dict[str, Any] | None:
        codigo = str(codigo or "").strip()
        ean = str(codigo_barras or "").strip()
        if ean and ean.upper() not in {"SEM GTIN", "SEMGTIN"}:
            row = self.database.fetch_one(
                "SELECT * FROM produtos WHERE codigo_barras=? COLLATE NOCASE LIMIT 1",
                (ean,),
            )
            if row:
                return dict(row)
        if codigo:
            row = self.database.fetch_one(
                "SELECT * FROM produtos WHERE codigo=? COLLATE NOCASE LIMIT 1",
                (codigo,),
            )
            if row:
                return dict(row)
        descricao = " ".join(str(descricao or "").split())
        if descricao:
            row = self.database.fetch_one(
                "SELECT * FROM produtos WHERE nome=? COLLATE NOCASE LIMIT 1",
                (descricao,),
            )
            if row:
                return dict(row)
        return None

    def atualizar_produto_por_xml(
        self,
        produto_id: int,
        *,
        fornecedor_id: int | None,
        unidade_compra_id: int | None,
        preco_custo: float,
        codigo_barras: str,
        ncm: str,
        cest: str,
        cfop: str,
    ) -> None:
        # CFOP descreve a operação do fornecedor, não a futura venda do destinatário.
        # O parâmetro permanece por compatibilidade, mas nunca altera a ficha de saída.
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.database.execute(
            """UPDATE produtos
               SET fornecedor_id=COALESCE(?, fornecedor_id),
                   unidade_compra_id=COALESCE(?, unidade_compra_id),
                   preco_custo=?, preco_custo_decimal=?,
                   codigo_barras=CASE WHEN ?<>'' THEN ? ELSE codigo_barras END,
                   ncm=CASE WHEN ?<>'' THEN ? ELSE ncm END,
                   cest=CASE WHEN ?<>'' THEN ? ELSE cest END,
                   atualizado_em=?
               WHERE id=?""",
            (
                fornecedor_id,
                unidade_compra_id,
                DecimalStorage.legacy_real(preco_custo, field="preço de custo"),
                DecimalStorage.canonical(preco_custo, field="preço de custo"),
                codigo_barras, codigo_barras,
                ncm, ncm,
                cest, cest,
                agora,
                int(produto_id),
            ),
        )

    def vincular_produto_fornecedor(
        self,
        *,
        produto_id: int,
        fornecedor_id: int,
        codigo_fornecedor: str,
        unidade_fornecedor: str,
        fator_conversao: float,
        ultimo_custo: float,
    ) -> None:
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.database.execute(
            """INSERT INTO produto_fornecedores
               (produto_id,fornecedor_id,codigo_fornecedor,unidade_fornecedor,fator_conversao,ultimo_custo,
                fator_conversao_decimal,ultimo_custo_decimal,ultima_compra,ativo)
               VALUES(?,?,?,?,?,?,?,?,?,1)
               ON CONFLICT(produto_id,fornecedor_id,codigo_fornecedor)
               DO UPDATE SET unidade_fornecedor=excluded.unidade_fornecedor,
                             fator_conversao=excluded.fator_conversao,
                             ultimo_custo=excluded.ultimo_custo,
                             fator_conversao_decimal=excluded.fator_conversao_decimal,
                             ultimo_custo_decimal=excluded.ultimo_custo_decimal,
                             ultima_compra=excluded.ultima_compra,
                             ativo=1""",
            (
                int(produto_id), int(fornecedor_id), str(codigo_fornecedor or ""),
                str(unidade_fornecedor or "UN"),
                DecimalStorage.legacy_real(fator_conversao), DecimalStorage.legacy_real(ultimo_custo),
                DecimalStorage.canonical(fator_conversao), DecimalStorage.canonical(ultimo_custo), agora,
            ),
        )

    def registrar_importacao(
        self,
        *,
        chave: str,
        numero: str,
        fornecedor_cnpj: str,
        fornecedor_nome: str,
        arquivo_origem: str,
        itens_total: int,
        itens_criados: int,
        itens_vinculados: int,
        valor_total: object = 0,
        status: str = "CONCLUIDA",
    ) -> int:
        return self.database.execute(
            """INSERT INTO nfe_importacoes
               (chave,numero,fornecedor_cnpj,fornecedor_nome,arquivo_origem,status,itens_total,itens_criados,itens_vinculados,valor_total,data_importacao)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (
                chave, numero, fornecedor_cnpj, fornecedor_nome, arquivo_origem,
                status, int(itens_total), int(itens_criados), int(itens_vinculados),
                DecimalStorage.canonical(valor_total, field="valor total da NF-e"),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )


    def listar_importacoes(self, data_inicial: str = "", data_final: str = "") -> list[dict[str, Any]]:
        """Lista NF-e importadas, permitindo filtro inclusivo por data ISO (AAAA-MM-DD)."""
        filtros: list[str] = []
        parametros: list[Any] = []
        if str(data_inicial or "").strip():
            filtros.append("date(data_importacao) >= date(?)")
            parametros.append(str(data_inicial).strip())
        if str(data_final or "").strip():
            filtros.append("date(data_importacao) <= date(?)")
            parametros.append(str(data_final).strip())
        where = " WHERE " + " AND ".join(filtros) if filtros else ""
        rows = self.database.fetch_all(
            f"""SELECT id,chave,numero,fornecedor_cnpj,fornecedor_nome,arquivo_origem,
                       status,itens_total,itens_criados,itens_vinculados,valor_total,data_importacao
                FROM nfe_importacoes{where}
                ORDER BY datetime(data_importacao) DESC, id DESC""",
            tuple(parametros),
        )
        return [dict(row) for row in rows]

    def analisar_exclusao(self, importacao_id: int) -> dict[str, Any]:
        """Retorna o impacto da exclusão sem modificar o banco."""
        nota = self.database.fetch_one(
            "SELECT * FROM nfe_importacoes WHERE id=?",
            (int(importacao_id),),
        )
        if not nota:
            raise ValueError("NF-e importada não localizada.")
        nota_dict = dict(nota)
        referencia = str(nota_dict.get("chave") or nota_dict.get("numero") or "").strip()
        prefixo = referencia + ":%"
        movimentos = self.database.fetch_all(
            """SELECT m.id,m.produto_id,m.quantidade,m.saldo_anterior,m.saldo_atual,
                      m.origem,m.origem_id,m.data,p.codigo,p.nome,
                      COALESCE(p.estoque_atual,0) AS estoque_atual
               FROM estoque_movimentacoes m
               JOIN produtos p ON p.id=m.produto_id
               WHERE m.origem='NFE_XML' AND m.origem_id LIKE ?
               ORDER BY m.id""",
            (prefixo,),
        ) if referencia else []
        documento = self.database.fetch_one(
            """SELECT id FROM nfe_documentos_origem
               WHERE (chave<>'' AND chave=?) OR (numero<>'' AND numero=?)
               ORDER BY id DESC LIMIT 1""",
            (str(nota_dict.get("chave") or ""), str(nota_dict.get("numero") or "")),
        )
        devolucoes = 0
        documento_id = None
        if documento:
            documento_id = int(documento["id"])
            row = self.database.fetch_one(
                "SELECT COUNT(*) AS total FROM nfe_devolucoes WHERE documento_origem_id=?",
                (documento_id,),
            )
            devolucoes = int(row["total"] or 0) if row else 0
        agrupados: dict[int, dict[str, Any]] = {}
        bloqueios = []
        for row in movimentos:
            item = dict(row)
            produto_id = int(item["produto_id"])
            agregado = agrupados.setdefault(
                produto_id,
                {
                    "produto_id": produto_id,
                    "codigo": item.get("codigo") or "",
                    "nome": item.get("nome") or "",
                    "estoque_atual": float(item.get("estoque_atual") or 0),
                    "quantidade_reverter": 0.0,
                    "movimentos_ids": [],
                    "origens_ids": [],
                },
            )
            agregado["quantidade_reverter"] += abs(float(item.get("quantidade") or 0))
            agregado["movimentos_ids"].append(int(item["id"]))
            agregado["origens_ids"].append(str(item.get("origem_id") or ""))
        itens = []
        for item in agrupados.values():
            item["estoque_apos_reversao"] = item["estoque_atual"] - item["quantidade_reverter"]
            if item["estoque_apos_reversao"] < -1e-9:
                bloqueios.append(
                    f"{item.get('codigo') or ''} - {item.get('nome') or ''}: "
                    f"estoque atual {item['estoque_atual']:g}, entrada a reverter {item['quantidade_reverter']:g}."
                )
            itens.append(item)
        if devolucoes:
            bloqueios.append(
                f"A nota possui {devolucoes} devolução(ões) registrada(s) e não pode ser apagada."
            )
        return {
            "nota": nota_dict,
            "documento_origem_id": documento_id,
            "devolucoes": devolucoes,
            "movimentos": itens,
            "bloqueios": bloqueios,
            "pode_excluir": not bloqueios,
        }

    def excluir_importacao(self, importacao_id: int) -> dict[str, Any]:
        """Reverte estoque, remove o espelho da NF-e e libera a chave para novo teste."""
        impacto = self.analisar_exclusao(importacao_id)
        if impacto["bloqueios"]:
            raise ValueError("A NF-e não pode ser apagada:\n- " + "\n- ".join(impacto["bloqueios"]))
        nota = impacto["nota"]
        with self.database.session(write=True) as connection:
            # Revalida dentro da transação para impedir corrida entre análise e exclusão.
            atual = connection.execute(
                "SELECT id,chave,numero FROM nfe_importacoes WHERE id=?",
                (int(importacao_id),),
            ).fetchone()
            if not atual:
                raise ValueError("NF-e importada não localizada.")
            referencia = str(atual["chave"] or atual["numero"] or "").strip()
            movimentos = connection.execute(
                """SELECT m.id,m.produto_id,m.quantidade,p.codigo,p.nome
                   FROM estoque_movimentacoes m
                   JOIN produtos p ON p.id=m.produto_id
                   WHERE m.origem='NFE_XML' AND m.origem_id LIKE ?
                   ORDER BY m.id DESC""",
                (referencia + ":%",),
            ).fetchall() if referencia else []
            por_produto: dict[int, dict[str, Any]] = {}
            for movimento in movimentos:
                produto_id = int(movimento["produto_id"])
                agregado = por_produto.setdefault(
                    produto_id,
                    {
                        "quantidade": 0.0,
                        "codigo": movimento["codigo"],
                        "nome": movimento["nome"],
                        "ids": [],
                    },
                )
                agregado["quantidade"] += abs(float(movimento["quantidade"] or 0))
                agregado["ids"].append(int(movimento["id"]))
            revertidos = 0
            for produto_id, agregado in por_produto.items():
                produto = connection.execute(
                    "SELECT estoque_atual FROM produtos WHERE id=?",
                    (produto_id,),
                ).fetchone()
                if not produto:
                    raise ValueError(f"Produto {produto_id} não localizado durante a reversão.")
                estoque_atual = float(produto["estoque_atual"] or 0)
                novo_saldo = estoque_atual - float(agregado["quantidade"])
                if novo_saldo < -1e-9:
                    raise ValueError(
                        f"Estoque insuficiente para reverter {agregado['codigo']} - {agregado['nome']}."
                    )
                connection.execute(
                    "UPDATE produtos SET estoque_atual=?, atualizado_em=? WHERE id=?",
                    (novo_saldo, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), produto_id),
                )
                for movimento_id in agregado["ids"]:
                    connection.execute("DELETE FROM estoque_movimentacoes WHERE id=?", (movimento_id,))
                    revertidos += 1

            documento_id = impacto.get("documento_origem_id")
            if documento_id:
                possui_devolucao = connection.execute(
                    "SELECT 1 FROM nfe_devolucoes WHERE documento_origem_id=? LIMIT 1",
                    (int(documento_id),),
                ).fetchone()
                if possui_devolucao:
                    raise ValueError("A nota possui devolução registrada e não pode ser apagada.")
                connection.execute(
                    "DELETE FROM nfe_documentos_origem_itens WHERE documento_id=?",
                    (int(documento_id),),
                )
                connection.execute("DELETE FROM nfe_documentos_origem WHERE id=?", (int(documento_id),))

            # Títulos de integrações futuras que usem a chave/número como origem também são protegidos.
            origem_ids = {str(nota.get("chave") or "").strip(), str(nota.get("numero") or "").strip()}
            origem_ids.discard("")
            for origem_id in origem_ids:
                pagos = connection.execute(
                    """SELECT COUNT(*) AS total FROM titulos_financeiros
                       WHERE origem IN ('NFE_XML','IMPORTACAO_XML') AND origem_id=?
                         AND COALESCE(valor_pago,0)>0""",
                    (origem_id,),
                ).fetchone()
                if pagos and int(pagos["total"] or 0):
                    raise ValueError("A nota possui título financeiro pago e não pode ser apagada.")
                connection.execute(
                    """DELETE FROM titulos_financeiros
                       WHERE origem IN ('NFE_XML','IMPORTACAO_XML') AND origem_id=?""",
                    (origem_id,),
                )
            connection.execute("DELETE FROM nfe_importacoes WHERE id=?", (int(importacao_id),))
        return {
            "importacao_id": int(importacao_id),
            "numero": str(nota.get("numero") or ""),
            "chave": str(nota.get("chave") or ""),
            "movimentos_revertidos": revertidos,
        }
