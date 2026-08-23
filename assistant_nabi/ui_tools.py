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


class OpenProductSearchIntentTool:
    """Cria somente uma intenção; a GUI decide se pode abrir a janela."""

    def execute(self, request: ToolRequest, *, actor) -> dict:
        return {
            "action": "OPEN_PRODUCT_SEARCH",
            "term": request.parameters.get("term", "").strip(),
        }


def register_ui_intent_tools(registry) -> None:
    registry.register(OPEN_PRODUCT_SEARCH, OpenProductSearchIntentTool())
