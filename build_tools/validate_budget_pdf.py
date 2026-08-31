"""Gera amostra documental apenas com dados sintéticos e banco descartável."""
from pathlib import Path
from tests.test_pdf_document_service import PDFDocumentServiceTests


def main():
    fixture = PDFDocumentServiceTests()
    fixture.setUp()
    try:
        fixture.config["modelo_recibo"] = "Térmica 80 mm"
        destination = Path("tmp/pdfs/orcamento_condicoes.pdf").resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        path = fixture.service.generate_sale(
            1, [{"qtd": 2, "item": "PRODUTO DEMONSTRATIVO", "preco": 50, "subtotal": 100}],
            100, "ORCAMENTO", destination=destination,
            budget_terms=("CONDIÇÃO ESTIMADA (NÃO É RECEBIMENTO)\n"
                          "Forma: CREDIÁRIO\nEntrada: R$ 10,00\n"
                          "Saldo estimado: R$ 90,00 em 3x"),
        )
        print(path)
    finally:
        fixture.tearDown()


if __name__ == "__main__":
    main()
