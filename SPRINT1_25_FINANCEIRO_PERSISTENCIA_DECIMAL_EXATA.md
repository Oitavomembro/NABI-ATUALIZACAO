# Sprint 1.25 — Financeiro com persistência decimal exata

## Alterações

- Colunas canônicas TEXT adicionadas aos títulos e pagamentos financeiros.
- Migração idempotente integrada ao migrador decimal existente.
- FinanceiroRepository grava REAL legado e TEXT canônico na mesma transação.
- Leituras priorizam o valor canônico e usam fallback controlado para o legado.
- Saldo aberto é calculado com Decimal após a leitura dos valores monetários.
- NF-e grava o título financeiro nas duas representações quando o schema migrado está disponível.
- Compatibilidade mantida para bancos mínimos e integrações antigas sem colunas canônicas.

## Testes

- Persistência SQLite real com precisão decimal extensa.
- Validação do tipo SQLite TEXT.
- Fallback para valor canônico vazio ou inválido.
- Suíte completa: 591 testes aprovados.
