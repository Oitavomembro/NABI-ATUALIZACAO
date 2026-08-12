# Auditoria pós-refatoração — Checkpoint 3

## Resultado executivo

A refatoração é funcional e coberta por 883 testes. Controllers chamam services, services usam repositories e repositories usam database na maior parte dos fluxos novos. Não há justificativa para nova reescrita geral. Permanecem ilhas legadas que devem ser tratadas por risco e preservando propriedade transacional.

## Maiores funções restantes

### A — corrigir agora somente por risco concreto

- `abrir_pdv_independente` (291 linhas): risco visual tratado no Checkpoint 2; não extrair o restante agora.
- `abrir_importacao_xml` (527): combina UI, processamento e persistência; qualquer correção deve preservar a transação atômica de importação.
- `abrir_restauracao_fabrica` (217): operação destrutiva e de backup; revisar no checkpoint de banco, sem refatorar UI por estética.
- `receber_pagamento_cliente_selecionado` (109): fluxo financeiro crítico; revisar atomicidade e saldo antes de qualquer extração.

### B — pode ser extraído futuramente

- `abrir_painel_admin` (709), `abrir_historico_devolucoes` (325), `abrir_cadastro_produto` (257), `tela_configs` (233), `abrir_historico_nfe_importadas` (216), `abrir_configuracao_impressoras` (178), `abrir_assistente_devolucao` (168) e `solicitar_pagamentos_pdv` (146).
- A extração deve ocorrer por controlador/componente completo e com testes de comportamento, não por redução mecânica de linhas.

### C — não vale mexer agora

- `__init__`, telas de composição e janelas de recibo/histórico que estão estáveis e cobertas.
- Helpers locais de UI e callbacks pequenos cujo deslocamento aumentaria indireção sem reduzir risco.

## Fronteiras

- UI -> Controller: existe nos fluxos novos, mas `nabicode_legacy.py` ainda chama services, repositories e conexão diretamente.
- Controller -> Service: padrão predominante e adequado.
- Service -> Repository: padrão presente nos domínios produto, cliente, estoque, financeiro, NF-e e documentos.
- Repository -> Database: predominante; repositories usam `DatabaseManager` ou connection factory.
- Exceção de direção: `services/search_entry_behavior.py` importa `ui.keyboard_navigation`. É acoplamento invertido de baixo risco, mas deve ser removido numa evolução futura movendo bindings neutros para core/helper, não durante estabilização.

## SQL fora de repositories

O legado contém cinco chamadas SQL diretas reais: uma consulta de documentos no fluxo de seleção e quatro operações de clientes (carregar edição, ler estado anterior, atualizar e consultar contato/saldo). Há também SQL deliberado em services transacionais e de infraestrutura.

Decisão: não mover agora. Os trechos de cliente devem migrar futuramente para `ClienteRepository` por operação completa. O SQL em services só deve ser movido quando o repository aceitar conexão externa sem adquirir commit/rollback/close.

## Propriedade transacional

- `DatabaseManager.transaction()` é proprietário de conexão, commit, rollback e close.
- Services de PDV, movimento, caixa, fiscal, migração e reset que criam conexão própria também encerram commit/rollback/close no mesmo limite.
- Repositories com parâmetro `connection` atuam dentro de transação externa e não devem fazer commit interno.
- Repositories baseados exclusivamente em connection factory (`SystemRepository`, auditoria e documentos emitidos) são proprietários de suas operações autônomas.
- Métodos como `registrar_pagamentos_transacao`, `estornar_venda_na_transacao` e operações de compra/financeiro com conexão obrigatória preservam composição atômica.

Não foi encontrado motivo seguro para introduzir commits adicionais. Fazer isso quebraria venda, estoque, financeiro e NF-e compostos.

## Riscos classificados

- ALTO: SQL de cliente ainda na UI e fluxos financeiros/importação extensos.
- ALTO: qualquer alteração de propriedade de conexão pode quebrar atomicidade.
- MÉDIO: service importando UI em `search_entry_behavior`.
- MÉDIO: funções administrativas e fiscais muito grandes.
- BAIXO: repositories autônomos repetem boilerplate de commit/rollback/close, mas estão consistentes.

## Alterações deliberadamente não realizadas

- Nenhum SQL movido.
- Nenhum commit, rollback ou close alterado.
- Nenhuma função grande dividida.
- Nenhuma camada renomeada ou reestruturada.

O próximo checkpoint deve validar banco, isolamento e atomicidade dos fluxos críticos com testes existentes e adicionar casos apenas onde houver lacuna demonstrável.
