# Checkpoint 6 — auditoria da thread da interface

## Resumo

A navegação validada não foi alterada. Clientes já carregam em worker com conexão própria e retornam ao Tk via `after(0)`. Pesquisa global e backgrounds possuem debounce. Há operações potencialmente longas na thread principal, mas nenhuma foi movida sem medição real e contrato seguro de encerramento.

## Operações bloqueantes mapeadas

| Área/callback | Operação | Risco | Estimativa | Separação segura |
|---|---|---:|---|---|
| `_executar_backup_diario_automatico` | backup SQLite e cópia de arquivos | alto em banco grande/rede | dependente do tamanho; não medida no banco real | possível, mas exige política de encerramento/cancelamento e conexão própria |
| Admin backup/restore/reset | backup, validação, restore | alto | dependente de disco/banco | worker possível; exige bloquear ações concorrentes e concluir rollback |
| Importação XML/MySQL | parsing, hashing, SQL e relatório | alto | dependente do arquivo | possível separar parsing; transação deve permanecer no worker com conexão própria |
| PDF/DANFE/relatórios | renderização e filesystem | médio/alto | dependente do documento | worker possível; widgets e diálogos somente no Tk |
| Impressão | subprocess/driver | médio | dependente do spooler | worker possível, preservando diálogo e resultado no Tk |
| Atualização automática em rede | consultas de resumo/histórico | médio | dependente da rede | conexão própria em worker, com descarte de resultado obsoleto |
| Dashboard/produtos/financeiro/compras | SQL e repopulação de tabela | médio | não medida em base real | separar consulta de render após perfilamento |
| Clientes | consulta paginada | baixo após refatoração existente | coberta por paginação | já usa worker e `after(0)` |

## `update` / `update_idletasks`

- Não há `update()` explícito na aplicação auditada.
- `update_idletasks()` na revelação de janelas é necessário para layout antes do mapeamento validado no Windows.
- Usos em cálculo de geometria, Canvas e toasts são necessários e não processam eventos gerais.
- Usos em importação/migração para progresso são potencialmente caros e mantêm trabalho síncrono; não foram removidos porque fazem parte de fluxos transacionais e exigem redesign específico.
- Nenhum uso atual demonstrou reentrância equivalente a `update()`.

## `after` / `after_idle`

- Necessários: revelação de janela, foco, animação do splash e retorno do worker de clientes.
- Debounced: pesquisa global, background, resize, filtro de clientes e fechamento de sugestões cancelam/substituem callback anterior.
- Periódicos deliberados: licença, inatividade, rede, atividades e relatórios.
- Risco: callbacks periódicos não mantêm todos um identificador cancelável no fechamento; não houve thread órfã reproduzida.
- `after_idle` do flash permanece congelado e validado.

## Threads e SQLite

- Worker de clientes não toca widgets; apenas chama repository, que abre conexão própria.
- Resultado e erro retornam com `self.after(0, ...)`.
- ID monotônico descarta resultados antigos.
- Nenhum `check_same_thread=False` foi encontrado.
- `TaskManager` encapsula exceptions, cancelamento e estado, mas publica eventos a partir do worker; subscribers de UI não devem ser adicionados sem marshal para Tk.
- Não foi introduzido threading em backup, restore, importação, impressão ou documental neste checkpoint.

## Testes focados

`74 passed in 5.50s`, cobrindo TaskManager, debounce/background, pesquisa, clientes, navegação/flash e pipeline documental.

## Decisão

Sem congelamento reproduzido ou medição no banco real, mover operações críticas para threads poderia quebrar atomicidade, fechar a aplicação durante backup ou atualizar widgets destruídos. Os candidatos ficam registrados para instrumentação futura, não como correção presumida.
