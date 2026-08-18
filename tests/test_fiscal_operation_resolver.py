import pytest

from services.fiscal_operation_resolver import FiscalOperationResolver


@pytest.mark.parametrize(
    "reference,destination,expected",
    [
        ("5102", 1, "5102"), ("5102", 2, "6102"), ("6102", 3, "7102"),
        ("5401", 2, "6401"), ("5403", 2, "6403"), ("5405", 2, "6404"),
    ],
)
def test_resolve_familias_oficiais_de_venda(reference, destination, expected):
    assert FiscalOperationResolver.resolve_sale(
        reference, destination=destination, crt=1, csosn="102"
    ).cfop == expected


def test_nao_inventa_cfop_6405_ao_converter_st():
    operation = FiscalOperationResolver.resolve_sale(
        "5405", destination=2, crt=1, csosn="500"
    )
    assert operation.cfop == "6404"


def test_bloqueia_exportacao_st_sem_regra_explicita():
    with pytest.raises(ValueError, match="correspondência automática segura"):
        FiscalOperationResolver.resolve_sale("5405", destination=3, crt=1, csosn="500")


def test_mei_restringe_cfop_e_csosn_conforme_regra_oficial():
    assert FiscalOperationResolver.resolve_sale(
        "5102", destination=2, crt=4, csosn="102"
    ).cfop == "6102"
    with pytest.raises(ValueError, match="CSOSN 102, 300 ou 400"):
        FiscalOperationResolver.resolve_sale("5102", destination=1, crt=4, csosn="500")
    with pytest.raises(ValueError, match="somente vendas 5102/6102"):
        FiscalOperationResolver.resolve_sale("5405", destination=1, crt=4, csosn="400")


def test_cfop_fora_da_matriz_nao_e_transformado_por_prefixo():
    with pytest.raises(ValueError, match="não pertence"):
        FiscalOperationResolver.resolve_sale("5949", destination=2, crt=1, csosn="102")
