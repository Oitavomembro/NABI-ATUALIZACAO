from __future__ import annotations

from .contracts import (
    CapabilityLevel, ParameterDefinition, ParameterType, ToolDefinition,
    ToolKind, ToolSchema,
)


DIAGNOSE_PRODUCT_NCM = ToolDefinition(
    "produtos.diagnosticar_ncm", ToolKind.READ, CapabilityLevel.READ,
    "produtos", "view", ToolSchema((
        ParameterDefinition("product_id", ParameterType.INTEGER, required=True),
    )),
)

PREPARE_PRODUCT_NCM_CORRECTION = ToolDefinition(
    "produtos.preparar_correcao_ncm", ToolKind.DRAFT, CapabilityLevel.DRAFT,
    "produtos", "edit", ToolSchema((
        ParameterDefinition("product_id", ParameterType.INTEGER, required=True),
        ParameterDefinition("proposed_ncm", ParameterType.TEXT, required=True, max_length=8),
        ParameterDefinition(
            "evidence_source", ParameterType.TEXT, required=True,
            allowed_values=("CONTADOR", "DOCUMENTO_FISCAL", "FORNECEDOR", "TABELA_OFICIAL"),
        ),
        ParameterDefinition("evidence_reference", ParameterType.TEXT, required=True, max_length=160),
    )),
)

DIAGNOSE_FISCAL_OUTBOX = ToolDefinition(
    "fiscal.diagnosticar_fila", ToolKind.READ, CapabilityLevel.READ,
    "fiscal", "view", ToolSchema((
        ParameterDefinition("queue_id", ParameterType.TEXT, required=True, max_length=80),
    )),
)

PREPARE_FISCAL_RECOVERY = ToolDefinition(
    "fiscal.preparar_consulta_segura", ToolKind.DRAFT, CapabilityLevel.DRAFT,
    "fiscal", "transmit", ToolSchema((
        ParameterDefinition("queue_id", ParameterType.TEXT, required=True, max_length=80),
    )),
)


class DiagnoseProductNcmTool:
    def __init__(self, service): self._service = service
    def execute(self, request, *, actor):
        value = self._service.diagnose_product_ncm(**request.parameters)
        return {
            "product_id": value.product_id, "product_code": value.product_code,
            "product_description": value.product_description, "current_ncm": value.current_ncm,
            "diagnostic_code": value.diagnostic_code, "message": value.message,
            "suggested_ncm": None, "mutation_performed": False,
        }


class PrepareProductNcmCorrectionTool:
    def __init__(self, service): self._service = service
    def execute(self, request, *, actor):
        value = self._service.prepare_ncm_correction(**request.parameters)
        return {
            "draft_id": value.draft_id, "fingerprint": value.fingerprint,
            "operation_kind": value.operation_kind, "product_id": value.product_id,
            "product_code": value.product_code, "product_description": value.product_description,
            "expected_current_ncm": value.expected_current_ncm,
            "proposed_ncm": value.proposed_ncm, "evidence_source": value.evidence_source,
            "evidence_reference": value.evidence_reference,
            "requires_reinforced_confirmation": True, "persisted": False,
            "ncm_inferred": False,
        }


class DiagnoseFiscalOutboxTool:
    def __init__(self, service): self._service = service
    def execute(self, request, *, actor):
        value = self._service.diagnose_fiscal_outbox(**request.parameters)
        return {
            "queue_id": value.queue_id, "status": value.status,
            "operation": value.operation, "fiscal_outcome": value.fiscal_outcome,
            "safe_action": value.safe_action, "has_receipt": value.has_receipt,
            "has_access_key": value.has_access_key,
            "commercial_sale_preserved": True, "authorization_confirmed": False,
            "mutation_performed": False,
        }


class PrepareFiscalRecoveryTool:
    def __init__(self, service): self._service = service
    def execute(self, request, *, actor):
        value = self._service.prepare_fiscal_recovery(**request.parameters)
        return {
            "draft_id": value.draft_id, "fingerprint": value.fingerprint,
            "queue_id": value.queue_id, "observed_status": value.observed_status,
            "safe_action": value.safe_action, "operation_kind": value.operation_kind,
            "requires_reinforced_confirmation": True, "persisted": False,
            "commercial_sale_preserved": True, "authorization_claimed": False,
            "blind_resend_prepared": False,
        }


def register_safe_error_recovery_tools(registry, service) -> None:
    registry.register(DIAGNOSE_PRODUCT_NCM, DiagnoseProductNcmTool(service))
    registry.register(PREPARE_PRODUCT_NCM_CORRECTION, PrepareProductNcmCorrectionTool(service))
    registry.register(DIAGNOSE_FISCAL_OUTBOX, DiagnoseFiscalOutboxTool(service))
    registry.register(PREPARE_FISCAL_RECOVERY, PrepareFiscalRecoveryTool(service))
