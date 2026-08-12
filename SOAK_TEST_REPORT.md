# Relatório de soak test

## Execução

- 5.000 ciclos consecutivos.
- 1.000 commits.
- 4.000 rollbacks.
- Uma conexão aberta e fechada por ciclo.
- Consulta executada dentro de cada transação.
- Banco exclusivamente temporário.

## Resultado

- Duração final consolidada: 22,916 segundos.
- Banco final: 45.056 bytes.
- `PRAGMA integrity_check`: `ok`.
- Novo `BEGIN IMMEDIATE` obtido ao final, sem lock persistente.
- Artefatos removidos pelo diretório temporário.

## Memória

- Amostras após GC a cada 1.000 ciclos: 6.059, 6.155, 6.187, 6.219 e 6.251 bytes.
- Atual ao final: 7.563 bytes.
- Pico: 12.626 bytes.
- A variação é pequena e não sustenta afirmação de memory leak.

## Reprodução

`python -m pytest -q -s soak_tests`
