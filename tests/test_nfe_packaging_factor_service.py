from decimal import Decimal

from services import NFePackagingFactorService, normalize_gtin


def test_sem_gtin_e_variantes_sao_ausencia_de_identidade():
    assert normalize_gtin("SEM GTIN") == ""
    assert normalize_gtin(" semgtin ") == ""
    assert normalize_gtin("NO GTIN") == ""
    assert normalize_gtin("7891234567890") == "7891234567890"


def test_nabi_sugere_multipack_sem_aplicar_automaticamente():
    suggestion = NFePackagingFactorService.suggest_from_description(
        "ITALAQUINHO 27X200 ML"
    )
    assert suggestion is not None
    assert suggestion.factor == Decimal("27")
    assert suggestion.content == Decimal("200")
    assert suggestion.content_unit == "ML"
    assert suggestion.confidence == "ALTA"
    assert suggestion.requires_confirmation is True


def test_nabi_reconhece_variacoes_e_recusa_descricao_sem_evidencia():
    assert NFePackagingFactorService.suggest_from_description("REFRIG 6 x 2L").factor == 6
    assert NFePackagingFactorService.suggest_from_description("CAIXA COM 12 UN").factor == 12
    assert NFePackagingFactorService.suggest_from_description("REFRIGERANTE COLA") is None

