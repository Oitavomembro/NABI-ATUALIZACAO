# Sprint 1.16 — Pipeline Decimal de Produtos

## Alterações

- `ProductSaveCommand` usa `Decimal` em preço, custo, despesas, margem e fator de conversão.
- Conversão brasileira usa `Decimal` e rejeita NaN/Infinity.
- `ProdutoService` preserva `Decimal` durante validação, cálculo e histórico.
- `ProdutoRepository` serializa `Decimal` diretamente como texto numérico na fronteira SQLite, sem passagem por `float`.
- Listagem e histórico formatam valores financeiros a partir de `Decimal`.
- Adaptador legado `linhas_tabela()` removido na versão planejada 2.4.57 após confirmação de ausência de consumidores de produção.
- Schema SQLite mantido inalterado.
