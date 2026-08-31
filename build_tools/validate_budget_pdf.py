"""Gera amostra documental apenas com dados sintéticos e banco descartável."""
from pathlib import Path
from tests.test_pdf_document_service import PDFDocumentServiceTests
from commercial.application.dto import BudgetDocument
from commercial.domain.cart import CartItem
from commercial.infrastructure.budget_gateway import NabiCodeBudgetGateway


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
            budget_terms=NabiCodeBudgetGateway._terms_text(BudgetDocument(
                budget_id="DEMO", created_at="2026-08-30", customer_id=1,
                customer_name="CLIENTE TESTE", items=(CartItem("PRODUTO", 2, "50"),),
                total="100", entry_amount="10", installments=3,
                payment_method="CREDIÁRIO", first_due_date="2028-01-31",
            )),
        )
        print(path)
    finally:
        fixture.tearDown()


if __name__ == "__main__":
    main()
