# Sprint 1.41 — Modal de impressão unificado

## Correções

- Importação explícita de `WindowsPDFPrinter` e `WindowsPDFPrintError` no legado.
- Correção do `NameError` ao escolher imprimir em reimpressões e documentos históricos.
- `janela_acoes_pdf()` passou a usar o mesmo contrato visual do pós-venda.
- Todas as ações de PDF apresentam três escolhas explícitas: imprimir, finalizar ou abrir PDF.
- Remoção do diálogo genérico `askyesnocancel` no fluxo de documentos.
- Nenhuma impressão ou abertura acontece automaticamente no modo `PERGUNTAR`.

## Travas

- Teste AST garante a importação do serviço de impressão.
- Teste de contrato garante os três botões e impede o retorno do diálogo genérico.
- Teste de reimpressão garante uso do modal unificado.
