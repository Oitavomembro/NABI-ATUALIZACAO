# Checkpoint 17 — Soak test

- 1 teste separado de longa duração controlada.
- 5.000 ciclos, com 1.000 commits e 4.000 rollbacks.
- Nenhuma corrupção, lock persistente ou arquivo temporário restante.
- Soak aprovado em 22,81 segundos.
- `python -m compileall -q .`: aprovado.
- Suíte normal: 901 testes aprovados e 11 subtests aprovados.
