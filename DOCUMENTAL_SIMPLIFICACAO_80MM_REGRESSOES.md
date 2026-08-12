# DOCUMENTAL — Simplificação 80 mm / Regressões

Base oficial auditada: `NabiCode_v2_4_88_BASE_OFICIAL_INTEGRADA`.

## Arquivos realmente modificados

- `services/printing_service.py`
- `services/pdf_document_service.py`
- `tests/test_document_pipeline.py`
- `DOCUMENTAL_SIMPLIFICACAO_80MM_REGRESSOES.md`

Nenhum outro arquivo foi alterado.

## Política documental validada

- `Cupom 80 mm` permanece o único formato térmico oficial.
- `Cupom 58 mm` não foi reintroduzido em `VALID_FORMATS` e continua rejeitado pelo dispatcher físico.
- Configurações antigas persistidas como `Cupom 58 mm` continuam migradas em memória para `Cupom 80 mm`.
- Configuração antiga de PDF `Térmica 58 mm econômica` agora é normalizada para `Térmica 80 mm` ao selecionar o modelo de novos recibos.
- O suporte interno de canvas/renderização 58 mm foi preservado em `_create_canvas()` para compatibilidade histórica temporária.
- Imprimir cupom 80 mm continua despachando exclusivamente para `print_raw_text`; o fluxo físico não cria PDF automaticamente.

## Simplificações aplicadas

### `services/printing_service.py`

A compatibilidade antiga de impressão térmica usava um `frozenset` com apenas um valor (`Cupom 58 mm`). Foi simplificada para um único valor legado interno (`LEGACY_THERMAL_FORMAT`) e comparação direta. O comportamento permanece idêntico: 58 mm persistido é convertido para 80 mm, mas 58 mm não é aceito como formato físico oficial.

### `services/pdf_document_service.py`

`document_model()` passa a normalizar a configuração histórica `Térmica 58 mm econômica` para `Térmica 80 mm` para novos documentos. O ramo interno de `_create_canvas()` que entende 58 mm não foi removido.

### `tests/test_document_pipeline.py`

- O teste de impressão 80 mm foi corrigido para verificar o dispatcher real: apenas backend RAW é chamado e backend A4 não é acionado.
- Adicionado teste que garante a migração do modelo PDF 58 mm para 80 mm em novos documentos.
- Adicionado teste que garante que a compatibilidade interna de canvas 58 mm continua disponível.

## Auditoria de código

- Arquivos Python modificados compilados com `python -m py_compile` sem erros.
- Auditoria AST não encontrou imports mortos nos três arquivos Python modificados.
- Nenhum código de Financeiro, Interface, PDV, Cadastros ou `nabicode_legacy.py` foi alterado.
- Nenhum EXE foi gerado.

## Testes de regressão

Executado:

`pytest -q tests/test_document_pipeline.py tests/test_pdf_document_service.py tests/test_printing_service.py tests/test_emitted_document_service.py tests/test_sprint1_45_reprint_open_isolated.py tests/test_customer_payment_receipt_regression.py tests/test_customer_payment_coupon_regression.py tests/test_sprint1_41_unified_print_dialog.py tests/test_sales_product_selector_and_payment_reprint.py`

Resultado: **43 passed**.

Cobertura funcional da regressão: impressão térmica 80 mm, PDF, documentos emitidos, recibos de cliente, cupom de pagamento, diálogo unificado e reimpressão.

## `python main.py`

Executado antes da entrega.

A aplicação não abriu por bloqueios técnicos do ambiente:

- `_tkinter.TclError: couldn't connect to display ":0"`
- `ModuleNotFoundError: No module named 'customtkinter'`

A sprint não pode ser declarada totalmente validada em execução gráfica neste ambiente. Os testes automatizados documentais passaram, mas a abertura da aplicação deve ser confirmada em ambiente Windows com Tk/customtkinter disponíveis.

## Regressões encontradas

Nenhuma regressão automatizada foi encontrada nos 43 testes executados.
