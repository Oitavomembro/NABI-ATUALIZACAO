# Sprint 1.18 — Sincronização monetária integral da NF-e

- Corrige criação e atualização de produtos por NF-e para gravar colunas legadas e canônicas na mesma transação.
- Corrige histórico de preços da NF-e.
- Adiciona persistência decimal canônica em vínculos produto-fornecedor.
- Centraliza conversão em `DecimalStorage`.
- Remove migração decimal do construtor de `ProdutoRepository`; schema é responsabilidade do inicializador.
- Adiciona testes de regressão para criação e atualização por NF-e.
