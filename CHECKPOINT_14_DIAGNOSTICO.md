# Checkpoint 14 — Diagnóstico e observabilidade

## Implementado

- Handler rotativo centralizado.
- Contexto de versão, perfil e módulo.
- Traceback técnico preservado.
- Sanitização de credenciais em mensagens e exceções.
- Falha do próprio logger contida.

## Testes

- Registro de erro e traceback.
- Omissão de senha e token.
- Falha de escrita não escapa para a aplicação.
- Diagnóstico de sistema e snapshots preservados.

## Validação

- Testes focados: 10 aprovados.
- `python -m compileall -q .`: aprovado.
- Suíte completa: 900 testes aprovados e 11 subtests aprovados.
