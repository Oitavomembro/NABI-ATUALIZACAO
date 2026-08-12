from services.nfe_matching_service import NFeMatchingService
from services.nfe_xml_service import NFeDocument, NFeItem
from services.update_package_validation_service import UpdatePackageValidationService


class _MatchingRepository:
    def listar_produtos_referencia(self):
        return [{"id": 9, "codigo": "ABC-1", "nome": "Mesa de Jantar", "codigo_barras": "789"}]

    def localizar_produto(self, *_args):
        return None


def test_nfe_matching_service_prefers_exact_ean():
    item = NFeItem("OUTRO", "Mesa", 1, "UN", 10, codigo_barras="789")
    document = NFeDocument("CHAVE", "1", "Fornecedor", "", (item,))
    result = NFeMatchingService(_MatchingRepository()).analyze(document)
    assert result[0].produto_id == 9
    assert result[0].criterio == "EAN"
    assert result[0].status == "VINCULAR"


def test_update_validation_service_preserves_numeric_version_order():
    assert UpdatePackageValidationService.version_tuple("2.10.0") > (2, 9, 9)
