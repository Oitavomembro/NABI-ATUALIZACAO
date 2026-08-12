# Sprint 1.19 — Política decimal e migração única

- ProductDecimalMigration é a fonte única e é chamado pelo bootstrap.
- Pedidos e recebimentos possuem colunas TEXT canônicas para custos e totais.
- Leituras priorizam TEXT não vazio e mantêm fallback legado.
- DecimalStorage rejeita valores não finitos e overflow da coluna REAL.
