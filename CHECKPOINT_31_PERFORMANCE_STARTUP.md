# CHECKPOINT 31 — PERFORMANCE DE STARTUP

## Status

**CONCLUÍDO SEM ALTERAÇÃO FUNCIONAL DE STARTUP.**

O Checkpoint 23 introduziu instrumentação opt-in e mediu o caminho que pode ser
executado com fidelidade neste ambiente Linux. A medição completa até a primeira
tela utilizável depende de Windows com subsistema gráfico e, por isso, permanece
pendente de validação física.

## Medições disponíveis

### Baseline do Checkpoint 23

Medição isolada do carregamento de `nabicode_legacy.py`, com `-X importtime` e as
dependências de runtime disponíveis:

| Marco | Tempo acumulado |
| --- | ---: |
| ThemeManager/configuração de tema | 138,068 ms |
| importação completa do módulo legado | 144,873 ms |

Imports pesados observados nesse ensaio: `fiscal_service` (80,756 ms),
`requests` (39,901 ms), `urllib3` (24,312 ms), `tkinter` (21,872 ms),
`customtkinter` (18,406 ms), `reportlab.pdfgen.canvas` (18,159 ms) e
`cryptography.x509` (15,733 ms).

### Repetição de controle no encerramento do Checkpoint 31

Sete processos independentes foram executados apenas até a importação do módulo
legado. Resultados: 330,459; 222,777; 223,001; 221,410; 217,987; 222,778 e
233,167 ms.

| Estatística | Tempo |
| --- | ---: |
| mínimo | 217,987 ms |
| mediana | 222,778 ms |
| média | 238,797 ms |
| máximo | 330,459 ms |

Esse segundo conjunto não é comparável diretamente ao ensaio isolado anterior:
o método e o estado do ambiente diferem, e o CustomTkinter também emitiu avisos
de fonte por limitações do ambiente Linux. Portanto, esses números não são
apresentados como regressão nem como ganho.

## Decisão de otimização

Nenhum gargalo foi alterado. A evidência disponível identifica imports pesados,
mas não demonstra que torná-los lazy manteria o comportamento aprovado de
startup, splash, flash, navegação, impressão e PDV. Sem uma medição completa da
janela e da primeira tela utilizável no Windows, qualquer alteração seria
especulativa e violaria o critério deste checkpoint.

| Métrica antes/depois | Resultado |
| --- | --- |
| tempo antes | baseline parcial documentado acima |
| tempo depois | não aplicável; nenhuma otimização funcional realizada |
| ganho percentual | não aplicável |

## Arquivos alterados neste checkpoint

- `CHECKPOINT_31_PERFORMANCE_STARTUP.md` (novo)

Os arquivos de instrumentação já pertencem ao Checkpoint 23 e não foram
alterados neste checkpoint.

## Pendência controlada

Executar em Windows 10/11 a aplicação-fonte e a distribuição `onedir` com
`NABICODE_STARTUP_TRACE` habilitado, coletando todos os marcos até
`first_screen_usable`. Somente depois dessa medição uma otimização de startup
poderá ser proposta com comparação antes/depois válida.
