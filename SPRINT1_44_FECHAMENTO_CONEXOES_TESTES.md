# Sprint 1.44 — Fechamento de conexões SQLite nos testes

## Alterações

- Corrigidas três conexões SQLite não fechadas em `tests/test_customer_registration_service.py`.
- Substituído o uso incorreto de `with sqlite3.connect(...)` por `contextlib.closing(...)`.
- Nenhum arquivo de produção, regra de negócio, schema, interface, PDV ou impressão foi alterado.

## Validação

- Suíte completa executada com `ResourceWarning` habilitado.
- 661 testes aprovados.
- Zero ocorrências de `ResourceWarning`.
