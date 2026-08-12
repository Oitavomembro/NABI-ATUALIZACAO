# Sprint 1.20 — Pesquisa resiliente e leitura decimal segura

- Placeholders nativos não são tratados como conteúdo.
- Texto digitado branco e placeholder cinza.
- Foco seleciona a pesquisa anterior.
- Enter em cliente/produto é sempre consumido.
- Produto e Compras usam `DecimalStorage.read` com fallback controlado.
- Escrita principal de Produto e histórico usa `DecimalStorage.pair`.
- Totais de pedidos são somados com `Decimal`.
