from decimal import Decimal
import inspect

import pytest

from administration.nfe_purchase_import_service import (
    FactorSuggestionConfidence,
    PurchaseFactorSuggestion,
    suggest_purchase_factor,
)


@pytest.mark.parametrize(
    ("description", "factor", "evidence"),
    (
        ("BISCOITO CAIXA COM 12 UN", Decimal("12"), "CAIXA COM 12 UN"),
        ("SABONETE CX C/ 6", Decimal("6"), "CX C/ 6"),
        ("BEBIDA PACK 24", Decimal("24"), "PACK 24"),
        ("Cafe caixa com 10 unidades", Decimal("10"), "CAIXA COM 10 UNIDADES"),
    ),
)
def test_sugere_fator_somente_com_evidencia_explicita(description, factor, evidence):
    suggestion = suggest_purchase_factor(description)

    assert suggestion == PurchaseFactorSuggestion(
        factor=factor,
        evidence=evidence,
        confidence=FactorSuggestionConfidence.HIGH,
    )


@pytest.mark.parametrize(
    "description",
    (
        "PRODUTO 12 UN",
        "CAIXA PROMOCIONAL",
        "CX COM UNIDADES",
        "PACK FAMILIA",
        "CAIXA COM 1 UN",
        "",
    ),
)
def test_ausencia_ou_evidencia_insuficiente_nao_gera_sugestao(description):
    assert suggest_purchase_factor(description) is None


def test_evidencias_multiplas_sao_ambiguas_mesmo_com_o_mesmo_numero():
    assert suggest_purchase_factor("CAIXA COM 12 UN - PACK 12") is None


def test_evidencias_conflitantes_nao_escolhem_um_fator():
    assert suggest_purchase_factor("CX C/ 6 / PACK 24") is None


def test_analisador_nao_altera_fluxo_de_commit_automaticamente():
    from administration.nfe_purchase_import_service import (
        NFePurchaseImportManagementService,
    )

    assert "suggest_purchase_factor" not in inspect.getsource(
        NFePurchaseImportManagementService.commit
    )
