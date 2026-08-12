# Auditoria documental — geração e impressão

## Escopo

- PDF
- Cupom 58 mm
- Cupom 80 mm
- Renderização documental
- Impressão

Nenhum arquivo de interface, PDV, pesquisa ou financeiro foi alterado.
`nabicode_legacy.py` não foi alterado.

## Alterações

### `services/pdf_document_service.py`

- Centralizada a leitura de margem, fonte, tamanho e espaçamento em `_render_config`.
- Centralizada a criação de `PDFLineRenderer` em `_line_renderer`.
- Removida repetição de configuração tipográfica nos geradores de venda, movimentação, pagamento e fechamento.
- Mantidas as dimensões, larguras, fontes mínimas, espaçamentos e posições aprovadas.
- Mantido o salvamento único por `_finalize_document`.

### `services/printing_service.py`

- Centralizada a resolução e validação da impressora em `_resolve_printer_name`.
- Removida duplicação entre os backends RAW e A4.
- Cada solicitação continua sendo enviada a somente um backend por `print_text`.

### `tests/test_document_pipeline.py`

- Adicionado teste da configuração tipográfica centralizada.
- Adicionado teste garantindo uma única enumeração na resolução da impressora.

## Auditoria estática

- Código morto encontrado nos blocos alterados: nenhum.
- Imports mortos encontrados: nenhum.
- Compilação com `python -m compileall`: aprovada.
- Arquivos de cache e artefatos de build: excluídos da entrega.

## Testes de regressão

Comando executado:

```text
pytest -q tests/test_document_rendering.py tests/test_document_pipeline.py tests/test_emitted_document_service.py tests/test_pdf_document_service.py tests/test_printing_service.py tests/test_sales_product_selector_and_payment_reprint.py tests/test_sprint1_39_receipt_installment_format.py tests/test_sprint1_40_pdv_print_ui_regression.py tests/test_sprint1_41_unified_print_dialog.py tests/test_sprint1_42_native_print_dialog.py
```

Resultado:

```text
46 passed in 0.71s
```

Regressões automatizadas encontradas: nenhuma.

## Execução de `python main.py`

O comando foi executado antes da entrega, mas a aplicação não abriu neste ambiente.

Bloqueios técnicos:

```text
_tkinter.TclError: couldn't connect to display ":0"
ModuleNotFoundError: No module named 'customtkinter'
```

A sprint não está declarada concluída, pois a abertura visual não pôde ser confirmada.
