# Sprint 1.37 — Estabilização real do PDV e escolha de comprovante

## Correções
- `SearchEntryBehavior` diferencia CTkEntry, tk.Entry e widgets compatíveis.
- Opções exclusivas de CustomTkinter não são enviadas a widgets Tk nativos.
- `DecimalStorage` e `DecimalStorageError` são importados explicitamente no legado.
- A lista de produtos mantém consulta direta, filtro de ativos, seleção por índice e precisão decimal.
- Finalização da venda não imprime nem gera PDF automaticamente.
- Diálogo nativo de três opções: imprimir cupom 80 mm, gerar PDF ou finalizar sem emissão.
- Testes de regressão bloqueiam retorno dos erros `unknown option -text_color`, `NameError: DecimalStorage` e emissão automática.
