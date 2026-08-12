# Sprint 1.30 — Cancelamento e estorno decimalmente consistentes

## Alterações

- Cancelamento do PDV passou a ler `valor_decimal` com fallback para `valor`.
- Saldo do cliente é restaurado nas colunas `saldo_devedor` e `saldo_devedor_decimal`.
- Pagamentos legados sincronizam valores canônicos de movimentação, parcelas e cliente.
- Estorno restaura simultaneamente representações legada e canônica.
- `FinanceiroService` deixou de devolver valores monetários como `float` nos fluxos de juros, caixa, DRE, recorrências e centros de custo.
- Recorrências são armazenadas como texto decimal canônico e expostas como `Decimal`.
- Corrigido vazamento de conexão SQLite em teste de persistência financeira.

## Testes

- Cenário de cancelamento com divergência entre coluna REAL e canônica.
- Pagamento parcial e estorno com sincronização integral de movimento, parcela e cliente.
- Suíte completa: 601 testes aprovados.
- ResourceWarnings: 0.
