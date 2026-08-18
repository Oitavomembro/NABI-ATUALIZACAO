from __future__ import annotations

from dataclasses import dataclass, replace
import sqlite3
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any
import unicodedata

from .estoque_service import EstoqueService, ResultadoMovimentacaoEstoque
from .produto_service import ProdutoService
from .pricing_service import PricingService
from .fiscal_product_profile import FiscalProductProfile
from validators import AuxiliaryRegistrationValidator, ProductValidator




class ProductApplicationError(ValueError):
    """Erro estável da camada de aplicação, independente do banco utilizado."""


@dataclass(frozen=True)
class ProductAuxiliaryCreateCommand:
    tipo: str
    nome: str
    descricao: str = ""


@dataclass(frozen=True)
class ProductAuxiliaryCreateResult:
    item_id: int
    tipo: str
    nome: str


@dataclass(frozen=True)
class ProductAuxiliaryOption:
    item_id: int
    nome: str


@dataclass(frozen=True)
class ProductAuxiliaryCatalog:
    categorias: tuple[ProductAuxiliaryOption, ...]
    marcas: tuple[ProductAuxiliaryOption, ...]
    fornecedores: tuple[ProductAuxiliaryOption, ...]
    unidades: tuple[ProductAuxiliaryOption, ...]

    @staticmethod
    def mapa(opcoes: tuple[ProductAuxiliaryOption, ...]) -> dict[str, int]:
        resultado: dict[str, int] = {}
        for item in opcoes:
            chave = item.nome.strip()
            if not chave:
                raise ProductApplicationError("Cadastro auxiliar possui nome vazio.")
            if chave in resultado and resultado[chave] != item.item_id:
                raise ProductApplicationError(f"Existem cadastros auxiliares duplicados com o nome: {chave}.")
            resultado[chave] = item.item_id
        return resultado

    @property
    def mapa_categorias(self) -> dict[str, int]:
        return self.mapa(self.categorias)

    @property
    def mapa_marcas(self) -> dict[str, int]:
        return self.mapa(self.marcas)

    @property
    def mapa_fornecedores(self) -> dict[str, int]:
        return self.mapa(self.fornecedores)

    @property
    def mapa_unidades(self) -> dict[str, int]:
        return self.mapa(self.unidades)


@dataclass(frozen=True)
class ProductFormState:
    codigo: str = ""
    nome: str = ""
    preco_venda: str = "0"
    categoria: str = "Sem categoria"
    tipo_produto: str = "MERCADORIA"
    marca: str = "Sem marca"
    fornecedor: str = "Sem fornecedor"
    unidade: str = "UN"
    unidade_compra: str = "UN"
    fator_conversao: str = "1"
    preco_custo: str = "0"
    despesas_percentual: str = "0"
    margem_lucro: str = "0"
    codigo_barras: str = ""
    estoque_atual: str = "0"
    estoque_minimo: str = "0"
    permite_estoque_negativo: bool = False

@dataclass(frozen=True)
class ProductFormData:
    codigo: str
    nome: str
    preco_venda: str
    categoria_id: int | None
    tipo_produto: str
    marca_id: int | None = None
    fornecedor_id: int | None = None
    unidade_id: int | None = None
    unidade_compra_id: int | None = None
    fator_conversao: str = "1"
    preco_custo: str = "0"
    despesas_percentual: str = "0"
    margem_lucro: str = "0"
    codigo_barras: str = ""
    ncm: str = ""
    cest: str = ""
    cfop: str = ""
    fiscal_origin: str = ""
    fiscal_csosn: str = ""
    fiscal_icms_cst: str = ""
    fiscal_icms_rate: str = "0"
    fiscal_pis_cst: str = ""
    fiscal_pis_rate: str = "0"
    fiscal_cofins_cst: str = ""
    fiscal_cofins_rate: str = "0"
    fiscal_profile_source: str = ""
    ibs_cbs_cst: str = ""
    ibs_cbs_class: str = ""
    ibs_uf_rate: str = "0"
    ibs_city_rate: str = "0"
    cbs_rate: str = "0"
    estoque_atual: str = "0"
    estoque_minimo: str = "0"
    permite_estoque_negativo: bool = False
    produto_id: int | None = None
    usuario: str = "Sistema"


@dataclass(frozen=True)
class ProductSaveCommand:
    codigo: str
    nome: str
    preco_venda: Decimal
    categoria_id: int | None
    tipo_produto: str
    marca_id: int | None = None
    fornecedor_id: int | None = None
    unidade_id: int | None = None
    unidade_compra_id: int | None = None
    fator_conversao: Decimal = Decimal("1")
    preco_custo: Decimal = Decimal("0")
    despesas_percentual: Decimal = Decimal("0")
    margem_lucro: Decimal = Decimal("0")
    codigo_barras: str = ""
    ncm: str = ""
    cest: str = ""
    cfop: str = ""
    fiscal_origin: str = ""
    fiscal_csosn: str = ""
    fiscal_icms_cst: str = ""
    fiscal_icms_rate: str = "0"
    fiscal_pis_cst: str = ""
    fiscal_pis_rate: str = "0"
    fiscal_cofins_cst: str = ""
    fiscal_cofins_rate: str = "0"
    fiscal_profile_source: str = ""
    ibs_cbs_cst: str = ""
    ibs_cbs_class: str = ""
    ibs_uf_rate: str = "0"
    ibs_city_rate: str = "0"
    cbs_rate: str = "0"
    estoque_atual: float = 0.0
    estoque_minimo: float = 0.0
    permite_estoque_negativo: bool = False
    produto_id: int | None = None
    usuario: str = "Sistema"


@dataclass(frozen=True)
class ProductPricingState:
    preco_venda: str
    margem_lucro: str


@dataclass(frozen=True)
class ProductRegistrationPreparation:
    produto_id: int | None
    state: ProductFormState

    @property
    def editing(self) -> bool:
        return self.produto_id is not None

    @property
    def window_title(self) -> str:
        return "Editar produto" if self.editing else "Novo produto"

    @property
    def heading(self) -> str:
        return "Editar produto" if self.editing else "Cadastrar produto"


@dataclass(frozen=True)
class ProductListQuery:
    termo: str = ""
    tipo: str = "TODOS"


@dataclass(frozen=True)
class ProductTableRow:
    produto_id: int
    values: tuple[Any, ...]


@dataclass(frozen=True)
class ProductListResult:
    query: ProductListQuery
    rows: tuple[ProductTableRow, ...]

    @property
    def total(self) -> int:
        return len(self.rows)

    @property
    def total_texto(self) -> str:
        return f"{self.total} produto(s)"


@dataclass(frozen=True)
class ProductHistoryRow:
    values: tuple[str, ...]


@dataclass(frozen=True)
class ProductHistoryResult:
    produto_id: int
    produto_nome: str
    rows: tuple[ProductHistoryRow, ...]

    @property
    def titulo(self) -> str:
        return f"Histórico — {self.produto_nome}"


@dataclass(frozen=True)
class ProductStatusResult:
    produto_id: int
    ativo: bool

    @property
    def status_texto(self) -> str:
        return "Ativo" if self.ativo else "Inativo"


@dataclass(frozen=True)
class ProductDuplicateAssessment:
    similares: tuple[dict[str, Any], ...]

    @property
    def possui_similares(self) -> bool:
        return bool(self.similares)

    def resumo(self) -> str:
        return "\n".join(
            f"• {item['codigo']} — {item['nome']} "
            f"({float(item['similaridade']):.1f}% por {item['criterio_similaridade']})"
            for item in self.similares
        )


@dataclass(frozen=True)
class ProductSaveResult:
    produto_id: int
    nome: str
    criado: bool
    estoque_anterior: float | None = None
    estoque_atual: float | None = None
    movimentacao_estoque: ResultadoMovimentacaoEstoque | None = None

    @property
    def estoque_foi_ajustado(self) -> bool:
        return self.movimentacao_estoque is not None


class ProductApplicationService:
    """Orquestra cadastro de produto e ajuste de estoque fora da camada de UI."""

    def __init__(self, produtos: ProdutoService, estoque: EstoqueService) -> None:
        self.produtos = produtos
        self.estoque = estoque

    @staticmethod
    def _opcoes(registros: list[dict[str, Any]]) -> tuple[ProductAuxiliaryOption, ...]:
        opcoes: list[ProductAuxiliaryOption] = []
        for indice, item in enumerate(registros, start=1):
            try:
                item_id = int(item["id"])
                nome = str(item["nome"] or "").strip()
            except (KeyError, TypeError, ValueError) as exc:
                raise ProductApplicationError(
                    f"Cadastro auxiliar inválido na posição {indice}."
                ) from exc
            if item_id <= 0 or not nome:
                raise ProductApplicationError(
                    f"Cadastro auxiliar inválido na posição {indice}."
                )
            opcoes.append(ProductAuxiliaryOption(item_id, nome))
        return tuple(opcoes)

    def listar_categorias(self) -> tuple[ProductAuxiliaryOption, ...]:
        return self._opcoes(self.produtos.listar_categorias_ativas())

    def listar_auxiliares(self, tipo: str) -> tuple[ProductAuxiliaryOption, ...]:
        tipo_normalizado = AuxiliaryRegistrationValidator.normalize_type(tipo)
        return self._opcoes(self.produtos.listar_auxiliares(tipo_normalizado))

    def carregar_catalogo_auxiliar(self) -> ProductAuxiliaryCatalog:
        return ProductAuxiliaryCatalog(
            categorias=self.listar_categorias(),
            marcas=self.listar_auxiliares("marca"),
            fornecedores=self.listar_auxiliares("fornecedor"),
            unidades=self.listar_auxiliares("unidade"),
        )

    def criar_categoria_resultado(self, nome: str) -> ProductAuxiliaryCreateResult:
        nome_normalizado = ProductValidator.normalize_name(
            nome, message="Informe o nome da categoria.", uppercase=True
        )
        try:
            item_id = int(self.produtos.criar_categoria(nome_normalizado))
        except sqlite3.IntegrityError as exc:
            raise ProductApplicationError("Já existe uma categoria com esse nome.") from exc
        return ProductAuxiliaryCreateResult(item_id=item_id, tipo="categoria", nome=nome_normalizado)

    def criar_categoria(self, nome: str) -> int:
        # Compatibilidade com consumidores anteriores à Sprint 1.15.
        return self.criar_categoria_resultado(nome).item_id

    def criar_auxiliar_comando(
        self, command: ProductAuxiliaryCreateCommand
    ) -> ProductAuxiliaryCreateResult:
        try:
            tipo_normalizado = AuxiliaryRegistrationValidator.normalize_type(command.tipo)
        except ValueError as exc:
            raise ProductApplicationError(str(exc)) from exc
        try:
            nome = AuxiliaryRegistrationValidator.normalize_name(
                command.nome, unit=(tipo_normalizado == "unidade")
            )
        except ValueError as exc:
            raise ProductApplicationError(str(exc)) from exc
        descricao = " ".join(str(command.descricao or "").split())
        extras: dict[str, Any] = {}
        if tipo_normalizado == "fornecedor":
            extras["razao_social"] = descricao or nome
        elif tipo_normalizado == "unidade":
            extras["descricao"] = descricao
        try:
            item_id = int(self.produtos.criar_auxiliar(tipo_normalizado, nome, **extras))
        except sqlite3.IntegrityError as exc:
            raise ProductApplicationError("Já existe um registro com esse nome ou sigla.") from exc
        return ProductAuxiliaryCreateResult(item_id=item_id, tipo=tipo_normalizado, nome=nome.upper() if tipo_normalizado == "unidade" else nome)

    def criar_auxiliar(self, tipo: str, nome: str, **extras: Any) -> int:
        # Compatibilidade temporária; novos consumidores devem usar o comando tipado.
        descricao = str(extras.get("razao_social") or extras.get("descricao") or "")
        return self.criar_auxiliar_comando(
            ProductAuxiliaryCreateCommand(tipo=tipo, nome=nome, descricao=descricao)
        ).item_id

    @staticmethod
    def _tipo_normalizado(tipo: str) -> str:
        texto = unicodedata.normalize("NFKD", str(tipo or ""))
        texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
        return texto.strip().upper()

    @staticmethod
    def converter_decimal(valor: Any, *, padrao: Any = Decimal("0")) -> Decimal:
        if isinstance(valor, Decimal):
            numero = valor
        else:
            texto = str(valor if valor not in (None, "") else padrao).strip()
            if "." in texto and "," in texto:
                texto = texto.replace(".", "")
            texto = texto.replace(",", ".")
            try:
                numero = Decimal(texto)
            except (InvalidOperation, TypeError, ValueError) as exc:
                raise ValueError(f"Valor numérico inválido: {valor}") from exc
        if not numero.is_finite():
            raise ValueError(f"Valor numérico inválido: {valor}")
        return numero

    @classmethod
    def converter_numero(cls, valor: Any, *, padrao: Any = Decimal("0")) -> Decimal:
        """Compatibilidade: desde a Sprint 1.16 retorna Decimal, não float."""
        return cls.converter_decimal(valor, padrao=padrao)

    @classmethod
    def formatar_numero_formulario(cls, valor: Any, *, padrao: Any = Decimal("0")) -> str:
        numero = cls.converter_decimal(valor, padrao=padrao)
        texto = format(numero, "f")
        if "." in texto:
            texto = texto.rstrip("0").rstrip(".")
        return (texto or "0").replace(".", ",")

    @classmethod
    def formatar_moeda(cls, valor: Any) -> str:
        return f"R$ {cls.converter_decimal(valor).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)}"

    @classmethod
    def calcular_preco_formulario(
        cls, custo: Any, despesas_percentual: Any, margem_lucro: Any
    ) -> ProductPricingState:
        resultado = PricingService.calcular(custo, despesas_percentual, margem_lucro)
        return ProductPricingState(
            preco_venda=cls.formatar_numero_formulario(resultado.preco_sugerido),
            margem_lucro=cls.formatar_numero_formulario(resultado.margem_percentual),
        )

    @classmethod
    def calcular_margem_formulario(
        cls, custo: Any, despesas_percentual: Any, preco_venda: Any
    ) -> ProductPricingState:
        calculo_base = PricingService.calcular(custo, despesas_percentual, 0)
        preco = cls.converter_decimal(preco_venda)
        if preco < 0:
            raise ValueError("Preço de venda não pode ser negativo.")
        if calculo_base.custo_total <= 0:
            margem = Decimal("0")
        else:
            margem = ((preco / calculo_base.custo_total) - Decimal("1")) * Decimal("100")
            margem = max(Decimal("0"), margem).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return ProductPricingState(
            preco_venda=cls.formatar_numero_formulario(preco),
            margem_lucro=cls.formatar_numero_formulario(margem),
        )

    @classmethod
    def criar_estado_formulario(
        cls,
        dados: dict[str, Any] | None,
        *,
        categorias: dict[str, int],
        marcas: dict[str, int],
        fornecedores: dict[str, int],
        unidades: dict[str, int],
        codigo_padrao: str = "",
        unidade_padrao: str = "UN",
    ) -> ProductFormState:
        if not dados:
            return ProductFormState(codigo=str(codigo_padrao or ""), unidade=unidade_padrao, unidade_compra=unidade_padrao)

        def nome_por_id(mapa: dict[str, int], identificador: Any, padrao: str) -> str:
            return next((nome for nome, item_id in mapa.items() if item_id == identificador), padrao)

        return ProductFormState(
            codigo=str(dados.get("codigo", "") or ""),
            nome=str(dados.get("nome", "") or ""),
            preco_venda=cls.formatar_numero_formulario(dados.get("preco_venda", 0)),
            categoria=nome_por_id(categorias, dados.get("categoria_id"), "Sem categoria"),
            tipo_produto="SERVIÇO" if cls._tipo_normalizado(dados.get("tipo_produto", "")) == "SERVICO" else "MERCADORIA",
            marca=nome_por_id(marcas, dados.get("marca_id"), "Sem marca"),
            fornecedor=nome_por_id(fornecedores, dados.get("fornecedor_id"), "Sem fornecedor"),
            unidade=nome_por_id(unidades, dados.get("unidade_id"), unidade_padrao),
            unidade_compra=nome_por_id(unidades, dados.get("unidade_compra_id"), unidade_padrao),
            fator_conversao=cls.formatar_numero_formulario(dados.get("fator_conversao", 1), padrao=1),
            preco_custo=cls.formatar_numero_formulario(dados.get("preco_custo", 0)),
            despesas_percentual=cls.formatar_numero_formulario(dados.get("despesas_percentual", 0)),
            margem_lucro=cls.formatar_numero_formulario(dados.get("margem_lucro", 0)),
            codigo_barras=str(dados.get("codigo_barras", "") or ""),
            estoque_atual=cls.formatar_numero_formulario(dados.get("estoque_atual", 0)),
            estoque_minimo=cls.formatar_numero_formulario(dados.get("estoque_minimo", 0)),
            permite_estoque_negativo=bool(dados.get("permite_estoque_negativo", 0)),
        )

    def preparar_cadastro(
        self,
        produto_id: int | None = None,
        dados_precarregados: dict[str, Any] | None = None,
        *,
        categorias: dict[str, int],
        marcas: dict[str, int],
        fornecedores: dict[str, int],
        unidades: dict[str, int],
        unidade_padrao: str = "UN",
    ) -> ProductRegistrationPreparation:
        identificador = int(produto_id) if produto_id is not None else None
        if identificador is not None and identificador <= 0:
            raise ValueError("Identificador de produto inválido.")

        if identificador is not None:
            dados = self.produtos.buscar(identificador)
            if not dados:
                raise ValueError("Produto não encontrado para edição.")
            codigo_padrao = ""
        else:
            dados = dict(dados_precarregados) if dados_precarregados else None
            codigo_padrao = str(self.produtos.proximo_codigo() or "")

        state = self.criar_estado_formulario(
            dados,
            categorias=categorias,
            marcas=marcas,
            fornecedores=fornecedores,
            unidades=unidades,
            codigo_padrao=codigo_padrao,
            unidade_padrao=unidade_padrao,
        )
        return ProductRegistrationPreparation(produto_id=identificador, state=state)

    @staticmethod
    def criar_dados_formulario(
        estado: ProductFormState,
        *,
        categorias: dict[str, int],
        marcas: dict[str, int],
        fornecedores: dict[str, int],
        unidades: dict[str, int],
        produto_id: int | None = None,
        usuario: str = "Sistema",
    ) -> ProductFormData:
        return ProductFormData(
            codigo=estado.codigo, nome=estado.nome, preco_venda=estado.preco_venda,
            categoria_id=categorias.get(estado.categoria), tipo_produto=estado.tipo_produto,
            marca_id=marcas.get(estado.marca), fornecedor_id=fornecedores.get(estado.fornecedor),
            unidade_id=unidades.get(estado.unidade), unidade_compra_id=unidades.get(estado.unidade_compra),
            fator_conversao=estado.fator_conversao, preco_custo=estado.preco_custo,
            despesas_percentual=estado.despesas_percentual, margem_lucro=estado.margem_lucro,
            codigo_barras=estado.codigo_barras, estoque_atual=estado.estoque_atual,
            estoque_minimo=estado.estoque_minimo, permite_estoque_negativo=estado.permite_estoque_negativo,
            produto_id=produto_id, usuario=usuario,
        )

    @classmethod
    def validar_nome_formulario(cls, nome: Any) -> str:
        return ProductValidator.normalize_name(nome)

    @classmethod
    def validar_numero_formulario(
        cls, valor: Any, rotulo: str, *, maior_zero: bool = False
    ) -> float:
        try:
            numero = cls.converter_numero(valor)
        except ValueError as exc:
            raise ValueError(f"{rotulo} inválido.") from exc
        if maior_zero and numero <= 0:
            raise ValueError(f"{rotulo} deve ser maior que zero.")
        return numero

    @classmethod
    def validar_comando(cls, command: ProductSaveCommand) -> ProductSaveCommand:
        ProductValidator.normalize_name(command.nome)
        ProductValidator.validate_values(
            sale_price=command.preco_venda,
            cost_price=command.preco_custo,
            expenses_percent=command.despesas_percentual,
            profit_margin=command.margem_lucro,
            conversion_factor=command.fator_conversao,
            current_stock=command.estoque_atual,
            minimum_stock=command.estoque_minimo,
            allow_negative_stock=command.permite_estoque_negativo,
        )
        return command

    @classmethod
    def criar_comando(cls, dados: ProductFormData) -> ProductSaveCommand:
        command = ProductSaveCommand(
            codigo=str(dados.codigo or "").strip(),
            nome=str(dados.nome or "").strip(),
            preco_venda=cls.converter_numero(dados.preco_venda),
            categoria_id=dados.categoria_id,
            tipo_produto=str(dados.tipo_produto or "").strip(),
            marca_id=dados.marca_id,
            fornecedor_id=dados.fornecedor_id,
            unidade_id=dados.unidade_id,
            unidade_compra_id=dados.unidade_compra_id,
            fator_conversao=cls.converter_numero(dados.fator_conversao, padrao=Decimal("1")),
            preco_custo=cls.converter_numero(dados.preco_custo),
            despesas_percentual=cls.converter_numero(dados.despesas_percentual),
            margem_lucro=cls.converter_numero(dados.margem_lucro),
            codigo_barras=str(dados.codigo_barras or "").strip(),
            ncm=str(dados.ncm or "").strip(), cest=str(dados.cest or "").strip(),
            cfop=str(dados.cfop or "").strip(), fiscal_origin=str(dados.fiscal_origin or "").strip(),
            fiscal_csosn=str(dados.fiscal_csosn or "").strip(),
            fiscal_icms_cst=str(dados.fiscal_icms_cst or "").strip(),
            fiscal_icms_rate=str(dados.fiscal_icms_rate or "0").strip(),
            fiscal_pis_cst=str(dados.fiscal_pis_cst or "").strip(),
            fiscal_pis_rate=str(dados.fiscal_pis_rate or "0").strip(),
            fiscal_cofins_cst=str(dados.fiscal_cofins_cst or "").strip(),
            fiscal_cofins_rate=str(dados.fiscal_cofins_rate or "0").strip(),
            fiscal_profile_source=str(dados.fiscal_profile_source or "").strip(),
            ibs_cbs_cst=str(dados.ibs_cbs_cst or "").strip(),
            ibs_cbs_class=str(dados.ibs_cbs_class or "").strip(),
            ibs_uf_rate=str(dados.ibs_uf_rate or "0").strip(),
            ibs_city_rate=str(dados.ibs_city_rate or "0").strip(),
            cbs_rate=str(dados.cbs_rate or "0").strip(),
            estoque_atual=cls.converter_numero(dados.estoque_atual),
            estoque_minimo=cls.converter_numero(dados.estoque_minimo),
            permite_estoque_negativo=bool(dados.permite_estoque_negativo),
            produto_id=dados.produto_id,
            usuario=str(dados.usuario or "Sistema").strip() or "Sistema",
        )
        command = replace(command, **FiscalProductProfile.normalize(command.__dict__))
        return cls.validar_comando(command)

    def avaliar_duplicidade(
        self, nome: str, *, codigo_barras: str = "", produto_id: int | None = None
    ) -> ProductDuplicateAssessment:
        if produto_id is not None:
            return ProductDuplicateAssessment(())
        similares = self.produtos.localizar_similares(nome, codigo_barras=codigo_barras)
        return ProductDuplicateAssessment(tuple(dict(item) for item in similares))

    def salvar(self, command: ProductSaveCommand) -> ProductSaveResult:
        self.validar_comando(command)
        database = getattr(getattr(self.produtos, "produtos", None), "database", None)
        estoque_database = getattr(self.estoque, "database", None)
        if database is not None and database is estoque_database:
            with database.session(write=True) as connection:
                return self._salvar(command, connection=connection)
        # Mantém compatibilidade com doubles de teste e integrações externas.
        return self._salvar(command, connection=None)

    def _salvar(self, command: ProductSaveCommand, *, connection=None) -> ProductSaveResult:
        buscar = getattr(self.produtos, "buscar")
        try:
            anterior = buscar(int(command.produto_id), connection=connection) if command.produto_id is not None else None
        except TypeError:
            anterior = buscar(int(command.produto_id)) if command.produto_id is not None else None
        if command.produto_id is not None and anterior is None:
            raise ValueError("Produto não encontrado para edição.")

        kwargs = dict(
            codigo=command.codigo, nome=command.nome, preco_venda=command.preco_venda,
            categoria_id=command.categoria_id, tipo_produto=command.tipo_produto,
            marca_id=command.marca_id, fornecedor_id=command.fornecedor_id,
            unidade_id=command.unidade_id, unidade_compra_id=command.unidade_compra_id,
            fator_conversao=command.fator_conversao, preco_custo=command.preco_custo,
            despesas_percentual=command.despesas_percentual, margem_lucro=command.margem_lucro,
            codigo_barras=command.codigo_barras, ncm=command.ncm, cest=command.cest,
            cfop=command.cfop, estoque_atual=command.estoque_atual,
            fiscal_origin=command.fiscal_origin, fiscal_csosn=command.fiscal_csosn,
            fiscal_icms_cst=command.fiscal_icms_cst, fiscal_icms_rate=command.fiscal_icms_rate,
            fiscal_pis_cst=command.fiscal_pis_cst, fiscal_pis_rate=command.fiscal_pis_rate,
            fiscal_cofins_cst=command.fiscal_cofins_cst, fiscal_cofins_rate=command.fiscal_cofins_rate,
            fiscal_profile_source=command.fiscal_profile_source,
            ibs_cbs_cst=command.ibs_cbs_cst, ibs_cbs_class=command.ibs_cbs_class,
            ibs_uf_rate=command.ibs_uf_rate, ibs_city_rate=command.ibs_city_rate,
            cbs_rate=command.cbs_rate,
            estoque_minimo=command.estoque_minimo,
            permite_estoque_negativo=command.permite_estoque_negativo,
            produto_id=command.produto_id,
        )
        if connection is not None:
            kwargs["connection"] = connection
        try:
            produto_id = self.produtos.salvar(**kwargs)
        except TypeError as exc:
            if "connection" not in str(exc):
                raise
            kwargs.pop("connection", None)
            produto_id = self.produtos.salvar(**kwargs)

        movimentacao = None
        estoque_anterior = None
        estoque_atual = None
        if anterior is not None and self._tipo_normalizado(command.tipo_produto) != "SERVICO":
            estoque_anterior = float(anterior.get("estoque_atual", 0) or 0)
            estoque_atual = float(command.estoque_atual)
            if abs(estoque_atual - estoque_anterior) > 0.0001:
                if connection is not None and hasattr(self.estoque, "ajustar_na_transacao"):
                    movimentacao = self.estoque.ajustar_na_transacao(
                        connection, produto_id, estoque_atual,
                        motivo="Ajuste realizado pelo cadastro do produto",
                        usuario=command.usuario,
                    )
                else:
                    movimentacao = self.estoque.ajustar(
                        produto_id, estoque_atual,
                        motivo="Ajuste realizado pelo cadastro do produto",
                        usuario=command.usuario,
                    )

        nome = " ".join(str(command.nome or "").split()).upper()
        return ProductSaveResult(
            produto_id=produto_id, nome=nome, criado=anterior is None,
            estoque_anterior=estoque_anterior, estoque_atual=estoque_atual,
            movimentacao_estoque=movimentacao,
        )

    @classmethod
    def normalizar_consulta_listagem(cls, termo: Any = "", tipo: Any = "TODOS") -> ProductListQuery:
        termo_normalizado = " ".join(str(termo or "").split())
        tipo_normalizado = cls._tipo_normalizado(tipo) or "TODOS"
        if tipo_normalizado not in {"TODOS", "MERCADORIA", "SERVICO"}:
            tipo_normalizado = "TODOS"
        tipo_repositorio = "SERVIÇO" if tipo_normalizado == "SERVICO" else tipo_normalizado
        return ProductListQuery(termo=termo_normalizado, tipo=tipo_repositorio)

    def listar_tabela(self, termo: Any = "", tipo: Any = "TODOS") -> ProductListResult:
        query = self.normalizar_consulta_listagem(termo, tipo)
        linhas: list[ProductTableRow] = []
        for produto in self.produtos.listar(query.termo, query.tipo):
            nome = str(produto["nome"] or "")
            ativo = bool(produto.get("ativo"))
            linhas.append(ProductTableRow(
                produto_id=int(produto["id"]),
                values=(
                    produto.get("codigo") or "",
                    nome if ativo else f"{nome} [INATIVO]",
                    self.formatar_moeda(produto.get('preco_venda', 0) or 0),
                    f"{float(produto.get('estoque_atual', 0) or 0):g}",
                    produto.get("categoria") or "Sem categoria",
                    produto.get("marca") or "Sem marca",
                    produto.get("unidade") or "UN",
                    "Serviço" if self._tipo_normalizado(produto.get("tipo_produto", "")) == "SERVICO" else "Mercadoria",
                ),
            ))
        return ProductListResult(query=query, rows=tuple(linhas))

    def preparar_duplicacao(self, selecao: Any) -> dict[str, Any]:
        produto_id = self.obter_produto_id_selecionado(selecao)
        return dict(self.produtos.preparar_duplicacao(produto_id))

    def obter_historico(self, selecao: Any) -> ProductHistoryResult:
        produto_id = self.obter_produto_id_selecionado(selecao)
        produto = self.produtos.buscar(produto_id)
        if not produto:
            raise ValueError("Produto não encontrado.")
        rows = tuple(
            ProductHistoryRow(values=(
                str(item.get("data", "") or ""),
                str(item.get("motivo", "") or ""),
                self.formatar_moeda(item.get('preco_anterior', 0) or 0),
                self.formatar_moeda(item.get('preco_novo', 0) or 0),
                self.formatar_moeda(item.get('custo', 0) or 0),
                format(self.converter_decimal(item.get('margem_percentual', 0) or 0).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP), 'f'),
            ))
            for item in self.produtos.listar_historico(produto_id)
        )
        return ProductHistoryResult(
            produto_id=produto_id,
            produto_nome=str(produto.get("nome", "") or "Produto"),
            rows=rows,
        )

    def alternar_status(self, selecao: Any) -> ProductStatusResult:
        produto_id = self.obter_produto_id_selecionado(selecao)
        status = self.produtos.alternar_status(produto_id)
        if status is None:
            raise ValueError("Produto não encontrado.")
        return ProductStatusResult(produto_id=produto_id, ativo=bool(status))

    @staticmethod
    def obter_produto_id_selecionado(selecao: Any) -> int:
        itens = tuple(selecao or ())
        if not itens:
            raise ValueError("Selecione um produto.")
        try:
            produto_id = int(itens[0])
        except (TypeError, ValueError) as exc:
            raise ValueError("Seleção de produto inválida.") from exc
        if produto_id <= 0:
            raise ValueError("Seleção de produto inválida.")
        return produto_id

    @staticmethod
    def mensagem_integridade(exc: sqlite3.IntegrityError) -> str:
        detalhe = str(exc)
        detalhe_normalizado = detalhe.casefold()
        if "codigo_barras" in detalhe_normalizado:
            return "Este código de barras já está vinculado a outro produto."
        if "produtos.codigo" in detalhe_normalizado:
            return "Já existe um produto com esse código."
        if "produtos.descricao" in detalhe_normalizado:
            return "Informe o nome/descrição do produto."
        return f"O banco recusou o cadastro por uma restrição de dados:\n{detalhe}"
