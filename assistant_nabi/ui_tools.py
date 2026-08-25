from __future__ import annotations

from .contracts import (
    CapabilityLevel,
    ParameterDefinition,
    ParameterType,
    ToolDefinition,
    ToolKind,
    ToolRequest,
    ToolSchema,
)


OPEN_PRODUCT_SEARCH = ToolDefinition(
    "interface.abrir_pesquisa_produtos",
    ToolKind.DRAFT,
    CapabilityLevel.DRAFT,
    "produtos",
    "view",
    ToolSchema((ParameterDefinition("term", ParameterType.TEXT, max_length=100),)),
)
OPEN_MODULE_HUB = ToolDefinition(
    "interface.abrir_modulos",
    ToolKind.DRAFT,
    CapabilityLevel.DRAFT,
    "dashboard",
    "view",
    ToolSchema(),
)
EXPLAIN_CONFIGURATION = ToolDefinition(
    "contexto.explicar_configuracao",
    ToolKind.READ,
    CapabilityLevel.READ,
    "configs",
    "view",
    ToolSchema((ParameterDefinition(
        "area", ParameterType.TEXT, required=True,
        allowed_values=("EMPRESA", "FISCAL", "XML_PRODUTOS"),
    ),)),
)
OPEN_FISCAL_CONFIGURATION = ToolDefinition(
    "interface.abrir_configuracao_fiscal",
    ToolKind.DRAFT,
    CapabilityLevel.DRAFT,
    "configs",
    "view",
    ToolSchema(),
)
OPEN_COMPANY_XML_IMPORT = ToolDefinition(
    "interface.abrir_importacao_xml_empresa",
    ToolKind.DRAFT,
    CapabilityLevel.DRAFT,
    "configs",
    "edit",
    ToolSchema(),
)
OPEN_PRODUCT_XML_IMPORT = ToolDefinition(
    "interface.abrir_importacao_xml_produtos",
    ToolKind.DRAFT,
    CapabilityLevel.DRAFT,
    "produtos",
    "create",
    ToolSchema(),
)


_CONFIGURATION_GUIDANCE = {
    "EMPRESA": {
        "title": "Identidade da empresa",
        "guidance": (
            "Confira os dados comprovados da empresa antes de salvar. "
            "No modo fiscal, o CNPJ do cadastro deve corresponder ao certificado A1."
        ),
        "limits": (
            "A Nabi não escolhe a empresa, não inventa campos e não confirma pelo operador."
        ),
    },
    "FISCAL": {
        "title": "Configuração e prontidão fiscal",
        "guidance": (
            "Revise empresa, ambiente, certificado e numeração pelas telas oficiais. "
            "A prontidão local não equivale a autorização da SEFAZ."
        ),
        "limits": (
            "A Nabi não recebe senha, não instala certificado, não transmite e não libera portões fiscais."
        ),
    },
    "XML_PRODUTOS": {
        "title": "Entrada de produtos por XML",
        "guidance": (
            "Selecione o XML local na tela oficial e confirme vínculos, unidades, fatores, custos e preços."
        ),
        "limits": (
            "A Nabi não inventa produto, fator ou unidade e não confirma a importação pelo operador."
        ),
    },
}


class OpenProductSearchIntentTool:
    """Cria somente uma intenção; a GUI decide se pode abrir a janela."""

    def execute(self, request: ToolRequest, *, actor) -> dict:
        return {
            "action": "OPEN_PRODUCT_SEARCH",
            "term": request.parameters.get("term", "").strip(),
        }


class OpenModuleHubIntentTool:
    """Solicita apenas a Central; ações internas continuam manuais e autorizadas."""

    def execute(self, request: ToolRequest, *, actor) -> dict:
        return {"action": "OPEN_MODULE_HUB"}


class ExplainConfigurationTool:
    """Explica limites conhecidos sem consultar dados operacionais ou segredos."""

    def execute(self, request: ToolRequest, *, actor) -> dict:
        area = request.parameters["area"]
        return {"area": area, **_CONFIGURATION_GUIDANCE[area]}


class _ClosedInterfaceIntentTool:
    def __init__(self, action: str) -> None:
        self._action = action

    def execute(self, request: ToolRequest, *, actor) -> dict:
        return {"action": self._action}


def register_ui_intent_tools(registry) -> None:
    registry.register(EXPLAIN_CONFIGURATION, ExplainConfigurationTool())
    registry.register(OPEN_PRODUCT_SEARCH, OpenProductSearchIntentTool())
    registry.register(OPEN_MODULE_HUB, OpenModuleHubIntentTool())
    registry.register(
        OPEN_FISCAL_CONFIGURATION,
        _ClosedInterfaceIntentTool("OPEN_FISCAL_CONFIGURATION"),
    )
    registry.register(
        OPEN_COMPANY_XML_IMPORT,
        _ClosedInterfaceIntentTool("OPEN_COMPANY_XML_IMPORT"),
    )
    registry.register(
        OPEN_PRODUCT_XML_IMPORT,
        _ClosedInterfaceIntentTool("OPEN_PRODUCT_XML_IMPORT"),
    )
