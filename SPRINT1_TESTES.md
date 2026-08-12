# Validação da Sprint 1 — Produtos

## Testes focados

Executados:

- `tests.test_product_application_service`
- `tests.test_product_layer`
- `tests.test_product_auto_price_regression`
- `tests.test_estoque_service`

Resultado: **32 testes OK**.

## Suíte completa

A suíte completa executou **506 testes**. Foram encontrados **3 testes com falha que já falhavam na base original**, antes desta sprint:

1. `test_customer_payment_coupon_regression.test_source_does_not_generate_pdf_automatically_after_payment`
2. `test_pdv_service.test_crediario_nao_pode_ser_misto`
3. `test_splash_screen_startup.test_splash_is_lightweight_and_startup_only`

Essas falhas não foram introduzidas pela refatoração de Produtos e não foram alteradas nesta sprint para evitar mudanças fora do escopo.
