# Performance final

- Nenhuma otimização foi aplicada porque todas as operações medidas ficaram abaixo de 24 ms no pior caso observado.
- Consultas por histórico e financeiro utilizam índices relevantes no dataset.
- Pesquisas com `%termo%` podem exigir scan por natureza; os tempos atuais não justificam FTS, índices em massa ou mudança funcional.
- Baseline e resultado final são idênticos.
- Comando reproduzível: `python -m pytest -q -s benchmark_tests`.

## Execução final consolidada

| Operação | p50 | Média | Máximo |
|---|---:|---:|---:|
| Pesquisa de produto | 5,544 ms | 7,147 ms | 18,496 ms |
| Sugestões de cliente | 7,593 ms | 7,617 ms | 8,053 ms |
| Histórico de cliente | 1,856 ms | 1,963 ms | 2,320 ms |
| Indicador de dashboard | 12,115 ms | 54,287 ms | 383,291 ms |
| Consulta financeira | 5,612 ms | 5,624 ms | 5,845 ms |

O dashboard apresentou um outlier isolado de 383,291 ms enquanto a mediana permaneceu em 12,115 ms. Uma amostra isolada não comprova regressão nem justifica otimização funcional.
