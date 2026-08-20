from __future__ import annotations

from collections.abc import Callable
from difflib import SequenceMatcher
from typing import Any
from decimal import Decimal
import re
import unicodedata

from repositories import CadastroAuxiliarRepository, CategoriaRepository, ProdutoRepository
from .pricing_service import PricingService
from .unit_conversion_service import UnitConversionService
from validators import AuxiliaryRegistrationValidator, ProductValidator

AuditCallback = Callable[..., None]


class ProdutoService:
    """Valida dados e coordena os repositórios de Produtos e Categorias."""

    def __init__(
        self,
        produtos: ProdutoRepository,
        categorias: CategoriaRepository,
        auxiliares: CadastroAuxiliarRepository | None = None,
        auditoria: AuditCallback | None = None,
    ) -> None:
        self.produtos = produtos
        self.categorias = categorias
        self.auxiliares = auxiliares
        self.auditoria = auditoria

    def listar(self, termo: str = "", tipo: str = "TODOS") -> list[dict[str, Any]]:
        tipo_normalizado = ProductValidator.normalize_filter_type(tipo)
        return self.produtos.listar(termo.strip(), tipo_normalizado)

    def listar_categorias_ativas(self) -> list[dict]:
        return self.categorias.listar_ativas()

    def criar_categoria(self, nome: str) -> int:
        nome = ProductValidator.normalize_name(nome, message="Informe o nome da categoria.", uppercase=True)
        categoria_id = self.categorias.criar(nome)
        self._auditar("Categorias", "CRIAR", categoria_id, f"nome={nome}")
        return categoria_id


    def listar_auxiliares(self, tipo: str) -> list[dict[str, Any]]:
        if not self.auxiliares:
            return []
        return self.auxiliares.listar_ativos(tipo)

    def criar_auxiliar(self, tipo: str, nome: str, **extras: Any) -> int:
        if not self.auxiliares:
            raise RuntimeError("Repositório de cadastros auxiliares não configurado.")
        tipo = AuxiliaryRegistrationValidator.normalize_type(tipo)
        nome = AuxiliaryRegistrationValidator.normalize_name(nome, unit=(tipo == "unidade"))
        registro_id = self.auxiliares.criar(tipo, nome, **extras)
        self._auditar("Produtos", f"CRIAR_{tipo.upper()}", registro_id, f"nome={nome}")
        return registro_id

    @staticmethod
    def calcular_preco_sugerido(preco_custo: float, despesas_percentual: float, margem_lucro: float) -> dict[str, float]:
        return PricingService.calcular(preco_custo, despesas_percentual, margem_lucro).as_dict()

    @staticmethod
    def converter_quantidade_compra(quantidade: float, fator_conversao: float) -> float:
        return UnitConversionService.para_estoque(quantidade, fator_conversao)

    def buscar(self, produto_id: int, connection=None) -> dict[str, Any] | None:
        return self.produtos.buscar_por_id(int(produto_id), connection)

    def proximo_codigo(self) -> str:
        return self.produtos.proximo_codigo()

    def salvar(
        self,
        *,
        codigo: str,
        nome: str,
        preco_venda: Decimal | float,
        categoria_id: int | None,
        tipo_produto: str,
        marca_id: int | None = None,
        fornecedor_id: int | None = None,
        unidade_id: int | None = None,
        unidade_compra_id: int | None = None,
        fator_conversao: Decimal | float = Decimal("1"),
        preco_custo: Decimal | float = Decimal("0"),
        despesas_percentual: Decimal | float = Decimal("0"),
        margem_lucro: Decimal | float = Decimal("0"),
        codigo_barras: str = "",
        ncm: str = "",
        cest: str = "",
        cfop: str = "",
        fiscal_origin: str = "", fiscal_csosn: str = "", fiscal_icms_cst: str = "",
        fiscal_icms_rate: str = "0", fiscal_pis_cst: str = "", fiscal_pis_rate: str = "0",
        fiscal_cofins_cst: str = "", fiscal_cofins_rate: str = "0",
        fiscal_ipi_cst: str = "", fiscal_ipi_rate: str = "0", fiscal_ipi_enq: str = "",
        fiscal_profile_source: str = "", ibs_cbs_cst: str = "", ibs_cbs_class: str = "",
        ibs_uf_rate: str = "0", ibs_city_rate: str = "0", cbs_rate: str = "0",
        estoque_atual: float = 0,
        estoque_minimo: float = 0,
        permite_estoque_negativo: bool = False,
        produto_id: int | None = None,
        connection=None,
    ) -> int:
        dados_salvamento = {
            "codigo": codigo, "nome": nome, "preco_venda": preco_venda,
            "categoria_id": categoria_id, "tipo_produto": tipo_produto, "marca_id": marca_id,
            "fornecedor_id": fornecedor_id, "unidade_id": unidade_id,
            "unidade_compra_id": unidade_compra_id, "fator_conversao": fator_conversao,
            "preco_custo": preco_custo, "despesas_percentual": despesas_percentual,
            "margem_lucro": margem_lucro, "codigo_barras": codigo_barras, "ncm": ncm,
            "cest": cest, "cfop": cfop, "estoque_atual": estoque_atual,
            "fiscal_origin": fiscal_origin, "fiscal_csosn": fiscal_csosn,
            "fiscal_icms_cst": fiscal_icms_cst, "fiscal_icms_rate": fiscal_icms_rate,
            "fiscal_pis_cst": fiscal_pis_cst, "fiscal_pis_rate": fiscal_pis_rate,
            "fiscal_cofins_cst": fiscal_cofins_cst, "fiscal_cofins_rate": fiscal_cofins_rate,
            "fiscal_ipi_cst": fiscal_ipi_cst, "fiscal_ipi_rate": fiscal_ipi_rate,
            "fiscal_ipi_enq": fiscal_ipi_enq,
            "fiscal_profile_source": fiscal_profile_source, "ibs_cbs_cst": ibs_cbs_cst,
            "ibs_cbs_class": ibs_cbs_class, "ibs_uf_rate": ibs_uf_rate,
            "ibs_city_rate": ibs_city_rate, "cbs_rate": cbs_rate,
            "estoque_minimo": estoque_minimo,
            "permite_estoque_negativo": permite_estoque_negativo, "produto_id": produto_id,
        }
        if connection is not None:
            return self._salvar_em_transacao(connection=connection, **dados_salvamento)
        with self.produtos.transaction() as active_connection:
            return self._salvar_em_transacao(connection=active_connection, **dados_salvamento)

    def _salvar_em_transacao(
        self, *, connection, codigo: str, nome: str, preco_venda: Decimal | float,
        categoria_id: int | None, tipo_produto: str, marca_id: int | None,
        fornecedor_id: int | None, unidade_id: int | None, unidade_compra_id: int | None,
        fator_conversao: Decimal | float, preco_custo: Decimal | float,
        despesas_percentual: Decimal | float, margem_lucro: Decimal | float,
        codigo_barras: str, ncm: str, cest: str, cfop: str, estoque_atual: float,
        fiscal_origin: str, fiscal_csosn: str, fiscal_icms_cst: str, fiscal_icms_rate: str,
        fiscal_pis_cst: str, fiscal_pis_rate: str, fiscal_cofins_cst: str,
        fiscal_cofins_rate: str, fiscal_profile_source: str, ibs_cbs_cst: str,
        fiscal_ipi_cst: str, fiscal_ipi_rate: str, fiscal_ipi_enq: str,
        ibs_cbs_class: str, ibs_uf_rate: str, ibs_city_rate: str, cbs_rate: str,
        estoque_minimo: float, permite_estoque_negativo: bool, produto_id: int | None,
    ) -> int:
        codigo = codigo.strip() or (self.produtos.proximo_codigo() if produto_id is None else "")
        nome = ProductValidator.normalize_name(nome, message="Nome é obrigatório e o código automático não pôde ser gerado.", uppercase=True)
        if not codigo:
            raise ValueError("Nome é obrigatório e o código automático não pôde ser gerado.")
        ProductValidator.validate_values(
            sale_price=preco_venda, cost_price=preco_custo,
            expenses_percent=despesas_percentual, profit_margin=margem_lucro,
            conversion_factor=fator_conversao, current_stock=estoque_atual,
            minimum_stock=estoque_minimo, allow_negative_stock=permite_estoque_negativo,
        )
        tipo = ProductValidator.normalize_type(tipo_produto)
        fator_validado = UnitConversionService.validar_fator(fator_conversao)
        codigo_barras_limpo = str(codigo_barras or "").strip()
        conflitos = self.produtos.localizar_conflitos_identificadores(
            codigo, codigo_barras_limpo, produto_id, connection
        )
        if "codigo" in conflitos:
            raise ValueError("Já existe um produto com esse código.")
        if "codigo_barras" in conflitos:
            raise ValueError("Este código de barras já está vinculado a outro produto.")
        calculo = PricingService.calcular(preco_custo, despesas_percentual, margem_lucro)
        preco_anterior = Decimal("0")
        custo_anterior = Decimal("0")
        if produto_id is not None:
            atual = self.produtos.buscar_por_id(int(produto_id), connection)
            preco_anterior = Decimal(str(atual.get("preco_venda", 0) or 0)) if atual else Decimal("0")
            custo_anterior = Decimal(str(atual.get("preco_custo", 0) or 0)) if atual else Decimal("0")
        dados = {
            "codigo": codigo,
            "nome": nome,
            "preco_venda": Decimal(str(preco_venda)),
            "preco_custo": calculo.custo_base,
            "despesas_percentual": Decimal(str(despesas_percentual)),
            "margem_lucro": Decimal(str(margem_lucro)),
            "categoria_id": categoria_id,
            "tipo_produto": tipo,
            "controla_estoque": 0 if tipo == "SERVICO" else 1,
            "participa_xml": 0 if tipo == "SERVICO" else 1,
            "marca_id": marca_id,
            "fornecedor_id": fornecedor_id,
            "unidade_id": unidade_id,
            "unidade_compra_id": unidade_compra_id or unidade_id,
            "fator_conversao": fator_validado,
            "codigo_barras": codigo_barras_limpo,
            "ncm": str(ncm or "").strip(),
            "cest": str(cest or "").strip(),
            "cfop": str(cfop or "").strip(),
            "fiscal_origin": fiscal_origin, "fiscal_csosn": fiscal_csosn,
            "fiscal_icms_cst": fiscal_icms_cst, "fiscal_icms_rate": fiscal_icms_rate,
            "fiscal_pis_cst": fiscal_pis_cst, "fiscal_pis_rate": fiscal_pis_rate,
            "fiscal_cofins_cst": fiscal_cofins_cst, "fiscal_cofins_rate": fiscal_cofins_rate,
            "fiscal_ipi_cst": fiscal_ipi_cst, "fiscal_ipi_rate": fiscal_ipi_rate,
            "fiscal_ipi_enq": fiscal_ipi_enq,
            "fiscal_profile_source": fiscal_profile_source, "ibs_cbs_cst": ibs_cbs_cst,
            "ibs_cbs_class": ibs_cbs_class, "ibs_uf_rate": ibs_uf_rate,
            "ibs_city_rate": ibs_city_rate, "cbs_rate": cbs_rate,
            "estoque_atual": 0 if tipo == "SERVICO" else float(estoque_atual),
            "estoque_minimo": 0 if tipo == "SERVICO" else float(estoque_minimo),
            "permite_estoque_negativo": False if tipo == "SERVICO" else bool(permite_estoque_negativo),
        }
        if produto_id is None:
            produto_id = self.produtos.criar(dados, connection)
            acao = "CRIAR"
        else:
            self.produtos.atualizar(int(produto_id), dados, connection)
            produto_id = int(produto_id)
            acao = "ATUALIZAR"
        novo_preco = Decimal(str(preco_venda))
        tolerancia = Decimal("0.00001")
        if (abs(preco_anterior - novo_preco) > tolerancia
                or abs(custo_anterior - calculo.custo_base) > tolerancia):
            self.produtos.registrar_historico_preco(
                produto_id, preco_anterior, novo_preco, calculo.custo_base,
                Decimal(str(margem_lucro)), acao, connection
            )
        self._auditar("Produtos", acao, produto_id, f"codigo={codigo}; tipo={tipo}; fator={fator_validado}")
        return produto_id

    @staticmethod
    def _normalizar_similaridade(valor: str) -> str:
        texto = unicodedata.normalize("NFKD", str(valor or ""))
        texto = "".join(ch for ch in texto if not unicodedata.combining(ch)).upper()
        return " ".join(re.findall(r"[A-Z0-9]+", texto))

    def localizar_similares(
        self, nome: str, *, codigo_barras: str = "", ignorar_produto_id: int | None = None, limite: int = 5
    ) -> list[dict[str, Any]]:
        nome_normalizado = self._normalizar_similaridade(nome)
        ean = str(codigo_barras or "").strip()
        if not nome_normalizado and not ean:
            return []
        candidatos = self.produtos.listar("", "TODOS")
        encontrados: list[dict[str, Any]] = []
        for candidato in candidatos:
            if ignorar_produto_id is not None and int(candidato["id"]) == int(ignorar_produto_id):
                continue
            ean_candidato = str(candidato.get("codigo_barras") or "").strip()
            nome_candidato = self._normalizar_similaridade(candidato.get("nome", ""))
            percentual = 0.0
            criterio = "NOME"
            if ean and ean_candidato and ean == ean_candidato:
                percentual = 100.0
                criterio = "EAN"
            elif nome_normalizado and nome_candidato:
                percentual = SequenceMatcher(None, nome_normalizado, nome_candidato).ratio() * 100
                if nome_normalizado in nome_candidato or nome_candidato in nome_normalizado:
                    percentual = max(percentual, 90.0)
            if percentual >= 72.0:
                item = dict(candidato)
                item["similaridade"] = round(percentual, 1)
                item["criterio_similaridade"] = criterio
                encontrados.append(item)
        encontrados.sort(key=lambda item: (-float(item["similaridade"]), str(item["nome"])))
        return encontrados[:max(1, int(limite))]

    def listar_historico(self, produto_id: int, limite: int = 200) -> list[dict[str, Any]]:
        if not self.buscar(produto_id):
            raise ValueError("Produto não encontrado.")
        return self.produtos.listar_historico(int(produto_id), limite)

    def preparar_duplicacao(self, produto_id: int) -> dict[str, Any]:
        origem = self.buscar(produto_id)
        if not origem:
            raise ValueError("Produto não encontrado.")
        base = f"{origem['codigo']}-COPIA"
        codigo = base
        sequencia = 2
        while self.produtos.codigo_existe(codigo):
            codigo = f"{base}-{sequencia}"
            sequencia += 1
        duplicado = dict(origem)
        duplicado.pop("id", None)
        duplicado["codigo"] = codigo
        duplicado["nome"] = f"{origem['nome']} CÓPIA"
        duplicado["codigo_barras"] = ""
        duplicado["estoque_atual"] = 0.0
        duplicado["ativo"] = 1
        return duplicado

    def alternar_status(self, produto_id: int) -> bool | None:
        status = self.produtos.alternar_status(int(produto_id))
        if status is not None:
            self._auditar("Produtos", "ALTERAR_STATUS", produto_id, f"ativo={int(status)}")
        return status

    def _auditar(self, modulo: str, acao: str, objeto: Any, detalhes: str) -> None:
        if self.auditoria:
            self.auditoria(modulo, acao, objeto=str(objeto), detalhes=detalhes)
