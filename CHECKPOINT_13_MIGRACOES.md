# Checkpoint 13 — Versionamento e migrações

## Problema corrigido

- O inicializador confirmava uma parte do schema antes de concluir configurações, dados legados, migração decimal e registro de versão.

## Correção

- Toda a inicialização/migração SQLite passa a começar com `BEGIN IMMEDIATE`.
- O commit intermediário foi removido; a confirmação ocorre somente após sucesso integral.

## Regressão adicionada

- Uma falha injetada ao persistir a versão final mantém a versão antiga e não deixa tabela nova publicada.

## Validação

- Testes focados: 19 aprovados.
- `python -m compileall -q .`: aprovado.
- Suíte completa: 897 testes aprovados e 11 subtests aprovados.
