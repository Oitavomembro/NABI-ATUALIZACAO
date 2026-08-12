# Checkpoint 9 — Integridade transacional

## Base

- Origem exclusiva: Checkpoint 8 aprovado.
- Baseline: 893 testes e 11 subtests aprovados.

## Auditoria

- Venda, itens, estoque, caixa, parcelas, saldo e financeiro são coordenados por `PDVTransactionService` em uma única transação.
- Recebimentos e operações de caixa executam commit somente quando são proprietários da conexão e rollback em falha.
- NF-e e importação XML usam transações explícitas e testes de falha no meio da operação.
- Cadastros compostos possuem testes que comprovam rollback de entidade e histórico.
- Métodos que recebem conexão externa não executam `commit`, `rollback` ou `close`; essa regra possui verificação automatizada.
- Migração mantém a versão anterior quando uma etapa falha.

## Riscos verificados

- Venda sem itens: protegida pela mesma transação.
- Itens sem venda: protegidos pela mesma transação.
- Estoque, caixa ou saldo divergentes após falha: cobertos por injeção de falha e rollback integral.
- Recebimento parcial: coberto por rollback integral.
- Commit antecipado por participante: bloqueado por teste de propriedade de conexão.
- Registros órfãos: protegidos por chaves estrangeiras, validações e rollback.

## Decisão

- Nenhum defeito transacional crítico ou alto adicional foi comprovado.
- Nenhuma regra comercial ou implementação congelada foi alterada.
- As correções de fechamento de conexões do Checkpoint 8 permanecem preservadas.

## Validação

- Testes focados: 27 aprovados.
- `python -m compileall -q .`: aprovado.
- Suíte completa: 893 testes aprovados e 11 subtests aprovados.
