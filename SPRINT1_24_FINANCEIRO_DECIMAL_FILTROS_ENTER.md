# Sprint 1.24 — Financeiro Decimal e Filtros com Enter

## Alterações

- `FinanceiroRepository` passa a aceitar `Decimal` nas gravações monetárias.
- Conversões para SQLite REAL são centralizadas em `DecimalStorage.legacy_real()` com validação de overflow.
- Leituras de títulos e pagamentos retornam `Decimal` para valores financeiros.
- `FinanceiroService` deixa de converter para `float` antes das chamadas principais ao repositório.
- `ResultadoPagamento` passa a transportar `Decimal` em valor pago e saldo aberto.
- Filtros de período da tela Financeiro usam `SearchEntryBehavior.attach()`.
- Enter normal e Enter do teclado numérico atualizam a tela sem propagar para atalhos globais.

## Escopo preservado

- O schema financeiro legado continua usando colunas REAL nesta sprint.
- Quantidades de estoque não foram alteradas.
- Relatórios e documentos externos permanecem para sprint específica de persistência financeira canônica.

## Testes

- Testes focados: 36 aprovados.
- Suíte completa: 589 aprovados.
