from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import Any
from decimal import Decimal
from repositories.decimal_storage import DecimalStorage
import unicodedata

from database import DatabaseManager


class ProdutoRepository:
    @staticmethod
    def _sqlite_decimal(value: Any) -> Any:
        """Serializa Decimal canônico para colunas TEXT; outros tipos são preservados."""
        return DecimalStorage.canonical(value) if isinstance(value, Decimal) else value

    @classmethod
    def _sqlite_values(cls, values: list[Any]) -> list[Any]:
        return [cls._sqlite_decimal(value) for value in values]

    def __init__(self, database: DatabaseManager) -> None:
        self.database = database

    @contextmanager
    def transaction(self):
        """Mantém validação, persistência e histórico na mesma transação."""
        with self.database.session(write=True) as connection:
            yield connection

    @staticmethod
    def _decimalizar_registro(registro: dict[str, Any], campos: tuple[str, ...]) -> dict[str, Any]:
        for campo in campos:
            canonico = registro.pop(f"{campo}_canonico", registro.get(campo))
            legado = registro.pop(f"{campo}_legado", registro.get(campo, 0))
            registro[campo] = DecimalStorage.read(canonico, legado, field=campo)
        return registro

    @classmethod
    def _decimalizar_produto(cls, registro: dict[str, Any]) -> dict[str, Any]:
        return cls._decimalizar_registro(registro, ("preco_venda", "preco_custo", "despesas_percentual", "margem_lucro", "fator_conversao"))

    @staticmethod
    def _normalizar_busca(valor: Any) -> str:
        texto = unicodedata.normalize("NFKD", str(valor or ""))
        return "".join(ch for ch in texto if not unicodedata.combining(ch)).casefold()

    def listar(self, termo: str = "", tipo: str = "TODOS") -> list[dict[str, Any]]:
        base_sql = """SELECT p.id, p.codigo, p.nome, p.preco_venda_decimal AS preco_venda_canonico, p.preco_venda AS preco_venda_legado,
                        COALESCE(c.nome, 'Sem categoria') AS categoria,
                        COALESCE(m.nome, 'Sem marca') AS marca,
                        COALESCE(f.nome_fantasia, 'Sem fornecedor') AS fornecedor,
                        COALESCE(u.sigla, 'UN') AS unidade,
                        COALESCE(uc.sigla, COALESCE(u.sigla, 'UN')) AS unidade_compra,
                        p.preco_custo_decimal AS preco_custo_canonico, p.preco_custo AS preco_custo_legado, p.despesas_percentual_decimal AS despesas_percentual_canonico, p.despesas_percentual AS despesas_percentual_legado, p.margem_lucro_decimal AS margem_lucro_canonico, p.margem_lucro AS margem_lucro_legado, p.fator_conversao_decimal AS fator_conversao_canonico, p.fator_conversao AS fator_conversao_legado,
                        p.codigo_barras, p.ncm, p.cest, p.cfop,
                        COALESCE(p.estoque_atual,0) AS estoque_atual,
                        COALESCE(p.estoque_minimo,0) AS estoque_minimo,
                        COALESCE(p.permite_estoque_negativo,0) AS permite_estoque_negativo,
                        p.controla_estoque, p.tipo_produto, p.ativo
                 FROM produtos p
                 LEFT JOIN categorias_produtos c ON c.id=p.categoria_id
                 LEFT JOIN marcas_produtos m ON m.id=p.marca_id
                 LEFT JOIN fornecedores f ON f.id=p.fornecedor_id
                 LEFT JOIN unidades_medida u ON u.id=p.unidade_id
                 LEFT JOIN unidades_medida uc ON uc.id=p.unidade_compra_id
                 WHERE 1=1"""
        params: list[Any] = []
        if tipo != "TODOS":
            base_sql += " AND p.tipo_produto=?"
            params.append(tipo)

        termo_limpo = str(termo or "").strip()
        order_sql = " ORDER BY p.ativo DESC, p.nome COLLATE NOCASE"
        if not termo_limpo:
            return [self._decimalizar_produto(dict(row)) for row in self.database.fetch_all(base_sql + order_sql, params)]

        # Caminho rápido para as pesquisas comuns. Evita carregar todo o catálogo
        # em memória a cada tecla digitada no PDV e no cadastro de produtos.
        like = f"%{termo_limpo}%"
        searchable_sql = base_sql + """ AND (
            p.codigo LIKE ? COLLATE NOCASE OR
            p.nome LIKE ? COLLATE NOCASE OR
            p.codigo_barras LIKE ? COLLATE NOCASE OR
            c.nome LIKE ? COLLATE NOCASE OR
            m.nome LIKE ? COLLATE NOCASE OR
            f.nome_fantasia LIKE ? COLLATE NOCASE
        )"""
        fast_params = params + [like] * 6
        rows = [self._decimalizar_produto(dict(row)) for row in self.database.fetch_all(searchable_sql + order_sql, fast_params)]
        if rows:
            return rows

        # SQLite NOCASE não remove acentos. O fallback preserva a pesquisa por
        # "cafe" encontrando "CAFÉ", mas só é executado quando o SQL não acha nada.
        all_rows = [self._decimalizar_produto(dict(row)) for row in self.database.fetch_all(base_sql + order_sql, params)]
        termo_normalizado = self._normalizar_busca(termo_limpo)
        campos = ("codigo", "nome", "codigo_barras", "categoria", "marca", "fornecedor")
        return [
            row for row in all_rows
            if any(termo_normalizado in self._normalizar_busca(row.get(campo)) for campo in campos)
        ]

    def buscar_por_id(self, produto_id: int, connection=None) -> dict[str, Any] | None:
        sql = """SELECT *,
                 preco_venda_decimal AS preco_venda_canonico, preco_venda AS preco_venda_legado,
                 preco_custo_decimal AS preco_custo_canonico, preco_custo AS preco_custo_legado,
                 despesas_percentual_decimal AS despesas_percentual_canonico, despesas_percentual AS despesas_percentual_legado,
                 margem_lucro_decimal AS margem_lucro_canonico, margem_lucro AS margem_lucro_legado,
                 fator_conversao_decimal AS fator_conversao_canonico, fator_conversao AS fator_conversao_legado
                 FROM produtos WHERE id=?"""
        row = (connection.execute(sql, (int(produto_id),)).fetchone()
               if connection is not None else self.database.fetch_one(sql, (int(produto_id),)))
        return self._decimalizar_produto(dict(row)) if row else None

    def proximo_codigo(self) -> str:
        """Gera o menor código numérico livre; a UNIQUE do banco é a garantia final."""
        rows = self.database.fetch_all("SELECT codigo FROM produtos WHERE codigo GLOB '[0-9]*'")
        usados = {int(str(row[0])) for row in rows if str(row[0]).isdigit()}
        candidato = 1
        while candidato in usados:
            candidato += 1
        return str(candidato)

    def _produto_tem_coluna(self, nome: str, connection=None) -> bool:
        try:
            rows = (connection.execute("PRAGMA table_info(produtos)").fetchall()
                    if connection is not None else self.database.fetch_all("PRAGMA table_info(produtos)"))
            return any(str(row["name"]).casefold() == str(nome).casefold() for row in rows)
        except Exception:
            return False

    def _montar_persistencia(self, dados: dict[str, Any], connection=None) -> tuple[list[str], list[Any]]:
        """Monta uma única vez os campos e valores compartilhados por INSERT e UPDATE."""
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        pv_r, pv_c = DecimalStorage.pair(dados["preco_venda"], field="preço de venda")
        pc_r, pc_c = DecimalStorage.pair(dados.get("preco_custo", 0), field="preço de custo")
        dp_r, dp_c = DecimalStorage.pair(dados.get("despesas_percentual", 0), field="despesas")
        ml_r, ml_c = DecimalStorage.pair(dados.get("margem_lucro", 0), field="margem")
        fc_r, fc_c = DecimalStorage.pair(dados.get("fator_conversao", 1), field="fator de conversão")

        campos = [
            "codigo", "nome", "preco_venda", "preco_custo", "despesas_percentual",
            "margem_lucro", "preco_venda_decimal", "preco_custo_decimal",
            "despesas_percentual_decimal", "margem_lucro_decimal",
            "fator_conversao_decimal", "categoria_id", "marca_id", "fornecedor_id",
            "unidade_id", "unidade_compra_id", "fator_conversao", "tipo_produto",
            "controla_estoque", "participa_xml", "codigo_barras", "ncm", "cest",
            "cfop", "estoque_minimo", "permite_estoque_negativo", "atualizado_em",
        ]
        valores = [
            dados["codigo"], dados["nome"], pv_r, pc_r, dp_r, ml_r, pv_c, pc_c, dp_c,
            ml_c, fc_c, dados.get("categoria_id"), dados.get("marca_id"),
            dados.get("fornecedor_id"), dados.get("unidade_id"),
            dados.get("unidade_compra_id"), fc_r, dados["tipo_produto"],
            dados["controla_estoque"], dados["participa_xml"],
            dados.get("codigo_barras", ""), dados.get("ncm", ""),
            dados.get("cest", ""), dados.get("cfop", ""),
            dados.get("estoque_minimo", 0),
            int(bool(dados.get("permite_estoque_negativo", False))), agora,
        ]
        if self._produto_tem_coluna("descricao", connection):
            campos.insert(2, "descricao")
            valores.insert(2,dados["nome"])
        for fiscal_field in (
            "fiscal_origin", "fiscal_csosn", "fiscal_icms_cst", "fiscal_icms_rate",
            "fiscal_pis_cst", "fiscal_pis_rate", "fiscal_cofins_cst", "fiscal_cofins_rate",
            "fiscal_ipi_cst", "fiscal_ipi_rate", "fiscal_ipi_enq",
            "fiscal_profile_source", "ibs_cbs_cst", "ibs_cbs_class", "ibs_uf_rate",
            "ibs_city_rate", "cbs_rate",
        ):
            if self._produto_tem_coluna(fiscal_field, connection):
                campos.append(fiscal_field)
                valores.append(dados.get(fiscal_field, "0" if fiscal_field.endswith("_rate") else ""))
        return campos, valores

    def criar(self, dados: dict[str, Any], connection=None) -> int:
        campos, valores = self._montar_persistencia(dados, connection)
        criado_em = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        campos.extend(("estoque_atual", "ativo", "criado_em"))
        valores.extend((dados.get("estoque_atual", 0), 1, criado_em))
        sql = f"INSERT INTO produtos ({','.join(campos)}) VALUES ({','.join('?' for _ in campos)})"
        if connection is not None:
            return int(connection.execute(sql, tuple(valores)).lastrowid)
        return self.database.execute(sql, tuple(valores))

    def atualizar(self, produto_id: int, dados: dict[str, Any], connection=None) -> None:
        campos, valores = self._montar_persistencia(dados, connection)
        sql = f"UPDATE produtos SET {','.join(f'{campo}=?' for campo in campos)} WHERE id=?"
        params = tuple(valores) + (int(produto_id),)
        if connection is not None:
            connection.execute(sql, params)
        else:
            self.database.execute(sql, params)

    def registrar_historico_preco(self, produto_id: int, preco_anterior: Decimal, preco_novo: Decimal, custo: Decimal, margem: Decimal, motivo: str = "CADASTRO", connection=None) -> None:
        pa_r,pa_c=DecimalStorage.pair(preco_anterior, field="preço anterior")
        pn_r,pn_c=DecimalStorage.pair(preco_novo, field="preço novo")
        cu_r,cu_c=DecimalStorage.pair(custo, field="custo")
        ma_r,ma_c=DecimalStorage.pair(margem, field="margem")
        sql="""INSERT INTO historico_precos_produtos
                 (produto_id,preco_anterior,preco_novo,custo,margem_percentual,preco_anterior_decimal,preco_novo_decimal,custo_decimal,margem_percentual_decimal,motivo,data)
                 VALUES(?,?,?,?,?,?,?,?,?,?,?)"""
        params=(produto_id,pa_r,pn_r,cu_r,ma_r,pa_c,pn_c,cu_c,ma_c,motivo,datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        if connection is not None: connection.execute(sql,params)
        else: self.database.execute(sql,params)

    def listar_historico(self, produto_id: int, limite: int = 200) -> list[dict[str, Any]]:
        rows=self.database.fetch_all("""SELECT id,produto_id,
            preco_anterior_decimal AS preco_anterior_canonico,preco_anterior AS preco_anterior_legado,
            preco_novo_decimal AS preco_novo_canonico,preco_novo AS preco_novo_legado,
            custo_decimal AS custo_canonico,custo AS custo_legado,
            margem_percentual_decimal AS margem_percentual_canonico,margem_percentual AS margem_percentual_legado,
            motivo,data FROM historico_precos_produtos WHERE produto_id=? ORDER BY id DESC LIMIT ?""",
            (int(produto_id),max(1,int(limite))))
        return [self._decimalizar_registro(dict(row),("preco_anterior","preco_novo","custo","margem_percentual")) for row in rows]

    def localizar_conflitos_identificadores(
        self,
        codigo: str,
        codigo_barras: str = "",
        ignorar_produto_id: int | None = None,
        connection=None,
    ) -> set[str]:
        """Retorna conflitos de código/EAN com uma única consulta ao catálogo."""
        codigo_limpo = str(codigo or "").strip()
        barras_limpo = str(codigo_barras or "").strip()
        if not codigo_limpo and not barras_limpo:
            return set()

        filtros: list[str] = []
        params: list[Any] = []
        if codigo_limpo:
            filtros.append("codigo = ? COLLATE NOCASE")
            params.append(codigo_limpo)
        if barras_limpo:
            filtros.append("codigo_barras = ? COLLATE NOCASE")
            params.append(barras_limpo)

        sql = (
            "SELECT codigo, codigo_barras FROM produtos WHERE ("
            + " OR ".join(filtros)
            + ")"
        )
        if ignorar_produto_id is not None:
            sql += " AND id <> ?"
            params.append(int(ignorar_produto_id))

        rows = (
            connection.execute(sql, tuple(params)).fetchall()
            if connection is not None
            else self.database.fetch_all(sql, params)
        )
        conflitos: set[str] = set()
        for row in rows:
            if codigo_limpo and str(row["codigo"] or "").casefold() == codigo_limpo.casefold():
                conflitos.add("codigo")
            if barras_limpo and str(row["codigo_barras"] or "").casefold() == barras_limpo.casefold():
                conflitos.add("codigo_barras")
        return conflitos

    def codigo_existe(self, codigo: str, ignorar_produto_id: int | None = None, connection=None) -> bool:
        sql = "SELECT id FROM produtos WHERE codigo=? COLLATE NOCASE"
        params: list[Any] = [str(codigo).strip()]
        if ignorar_produto_id is not None:
            sql += " AND id<>?"
            params.append(int(ignorar_produto_id))
        row = (connection.execute(sql + " LIMIT 1", tuple(params)).fetchone()
               if connection is not None else self.database.fetch_one(sql + " LIMIT 1", params))
        return row is not None

    def codigo_barras_existe(self, codigo_barras: str, ignorar_produto_id: int | None = None, connection=None) -> bool:
        codigo_barras = str(codigo_barras or "").strip()
        if not codigo_barras:
            return False
        sql = "SELECT id FROM produtos WHERE codigo_barras=? COLLATE NOCASE"
        params: list[Any] = [codigo_barras]
        if ignorar_produto_id is not None:
            sql += " AND id<>?"
            params.append(int(ignorar_produto_id))
        row = (connection.execute(sql + " LIMIT 1", tuple(params)).fetchone()
               if connection is not None else self.database.fetch_one(sql + " LIMIT 1", params))
        return row is not None

    def alternar_status(self, produto_id: int) -> bool | None:
        atual = self.database.fetch_one("SELECT ativo FROM produtos WHERE id=?", (produto_id,))
        if not atual:
            return None
        novo_status = not bool(atual["ativo"])
        self.database.execute(
            "UPDATE produtos SET ativo=?, atualizado_em=? WHERE id=?",
            (int(novo_status), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), produto_id),
        )
        return novo_status
