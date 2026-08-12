# Baseline de performance

Dataset temporário: 10.000 clientes, 10.000 produtos, 50.000 movimentações e 20.000 títulos financeiros. Nove repetições por operação.

| Operação | p50 | Média | Máximo |
|---|---:|---:|---:|
| Pesquisa de produto | 5,160 ms | 8,856 ms | 23,252 ms |
| Sugestões de cliente | 7,560 ms | 7,654 ms | 8,222 ms |
| Histórico de cliente | 1,903 ms | 1,973 ms | 2,161 ms |
| Indicador de dashboard | 10,699 ms | 10,679 ms | 11,009 ms |
| Consulta financeira | 5,618 ms | 5,922 ms | 7,663 ms |

Ambiente: banco SQLite temporário local, execução sem GUI.
