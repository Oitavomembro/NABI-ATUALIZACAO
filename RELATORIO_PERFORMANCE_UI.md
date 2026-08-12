# Relatório de performance da UI

## Metodologia

Auditoria estática dos callbacks e execução de testes reproduzíveis com bancos/arquivos temporários. O banco real do usuário não foi usado. Não foi realizada cronometragem visual subjetiva nem foram inventados tempos de telas reais.

| Operação | Antes | Depois | Método | Impacto |
|---|---:|---:|---|---|
| Render de backgrounds em sete resoluções | limite automatizado < 1,5 s | inalterado | `perf_counter`, teste existente | debounce/cache permanecem aprovados |
| Pesquisa, debounce e worker de clientes | contratos aprovados | inalterado | testes unitários/integrados | sem chamadas duplicadas reproduzidas |
| Grupo UI/thread/documental | 74 testes em 5,50 s | inalterado | pytest isolado | nenhuma regressão |
| Backup/restore/importação/PDF | não medido em base real | não alterado | auditoria estática | sem alegação de ganho |

Nenhuma otimização foi implementada; portanto não existe ganho antes/depois a declarar.
