# HANDOFF NABICODE

## ATUALIZAÇÃO — MISSÃO FISCAL 04 / HARDENING DO WORKER

`FiscalService.transmit()` agora rejeita `PRODUCAO` diretamente, antes de
resolver endpoint, certificado ou executar qualquer chamada HTTP. O bloqueio
não depende do pré-voo, do worker ou de outra camada; `HOMOLOGACAO` conserva o
fluxo existente.

O claim da outbox passou a ter heartbeat durante todo processamento. A
renovação atômica exige `status=PROCESSANDO`, o mesmo `worker_id` proprietário
e nunca pode ser feita por outra instância. Persistências intermediárias não
reduzem mais um lease já renovado. Se a renovação falhar ou o claim mudar de
dono, o worker antigo não altera o estado novo. O marcador
`transmission_started_at` continua convertendo lease realmente expirado em
`RESPOSTA_DESCONHECIDA`, exigindo reconciliação e impedindo reenvio cego.

No encerramento, retorno `False` de `worker.stop()` agora é falha explícita. O
runtime não encerra o gerenciador de tarefas nem se declara finalizado, e o
processo principal preserva o lock do banco enquanto uma operação fiscal ainda
pode estar ativa. Não há tentativa de matar thread Python.

Regressões diretas cobrem bloqueio de produção sem `http_post`, homologação,
heartbeat além do lease original, rejeição de renovação por intruso, proteção
contra overwrite tardio e primeiro timeout de shutdown. Nenhum schema, XML,
tributo, DANFE, contingência, cancelamento, DF-e, PIX ou interface foi alterado.
Testes focados: 292 aprovados e 10 subtestes. Suíte completa funcional: 1.379
aprovados, 1 ignorado e 32 subtestes. O único teste DPAPI, repetido isoladamente,
não executa no token restrito do runtime Codex; é a mesma limitação ambiental
já registrada na missão anterior e não envolve código alterado nesta missão.

## ATUALIZAÇÃO — MISSÃO FISCAL 03 / WORKER AUTOMÁTICO

### Arquitetura anterior

A Central Fiscal chamava manualmente `process_transmission_queue()`. O método
lia todos os registros, não reivindicava o item e ao final salvava a lista
inteira. A outbox já possuía claim/lease, mas o processador não os utilizava.
Não existia ciclo automático depois do commit fiscal.

### Worker criado e ciclo de vida

`FiscalOutboxWorker` é uma thread Python interna, sem executável auxiliar. Ela é
construída depois das migrations e dos serviços fiscais, iniciada por
`after_idle`, espera por evento/intervalo controlado e nunca executa rede na
thread da interface. No shutdown central, sua parada ocorre antes do
`TaskManager` e antes da liberação de `DatabaseUsageLock`. Não existe busy-loop.

Cada ciclo reivindica no máximo um pequeno lote. O worker usa claim atômico,
lease e identificação única por host/PID/UUID. O processador manual da Central
Fiscal também passou a reivindicar o item. A persistência final exige que o
mesmo `worker_id` ainda seja proprietário do claim, evitando atualização antiga
sobre estado mais novo.

### Estados automáticos e intervenção

- `PENDENTE` de autorização: prepara, adiciona QR Code existente quando
  aplicável, assina, valida XSD e transmite;
- operação `recibo`: consulta automaticamente sem reenviar a autorização;
- `RESPOSTA_DESCONHECIDA`: é reivindicada exclusivamente para consulta por
  recibo ou chave;
- `CONCLUIDO`, `CANCELADO` e `FALHA`: não são reivindicados novamente;
- rejeição conclusiva fica em `FALHA`, sem retry cego;
- erro local anterior à rede recebe backoff progressivo limitado;
- credencial ausente usa código `AGUARDANDO_CREDENCIAL` e exige ação humana;
- produção usa `PRODUCAO_BLOQUEADA` antes de qualquer comunicação.

### Credencial, concorrência e recuperação

A senha nunca é escrita em log, outbox ou configuração em texto puro. O worker
usa somente a senha de sessão ou o cofre DPAPI já existente. Sem cofre válido,
o documento permanece preservado. Lease vencido antes da transmissão pode ser
recuperado; depois do marcador de início ele vira resposta desconhecida e só
pode ser reconciliado. Duas instâncias/processadores não transmitem o mesmo
item, e a Central Fiscal não contorna claim ativo.

### Isolamentos e limitações

Venda `COMERCIAL` sem outbox nunca é vista pelo worker. Alterar o modo atual
para comercial não apaga nem paralisa obrigação fiscal histórica já criada.
Produção continua bloqueada. Não foram alterados tributos, XMLDSIG, XSD, QR
Code, DANFE, contingência normativa, cancelamento no PDV, devolução, DF-e ou
inutilização. Homologação online real continua dependente de certificado e
credenciamento do contribuinte.

### Arquivos e testes

Arquivos centrais: `services/fiscal_outbox_worker.py`,
`services/fiscal_outbox_service.py`, `services/fiscal_service.py` e
`nabicode_legacy.py`. Regressões: `tests/test_fiscal_outbox_worker.py`, além das
suítes preexistentes de outbox, fiscal, PDV e schema.

Resultado focado: 190 testes aprovados e 10 subtestes. Suíte completa funcional:
1.375 testes aprovados, 1 ignorado e 32 subtestes; o teste DPAPI foi excluído
pelo limite conhecido do runtime isolado do Windows. Compilação e verificação
de diferenças aprovadas. Branch: `dev/nabicode-2.5.1`.

Checkpoint Git: `fix: automatiza processamento seguro da outbox fiscal`.
Push: `origin/dev/nabicode-2.5.1`, executado somente após as validações; o hash
efetivo consta no histórico Git e no relatório final desta missão.

## ATUALIZAÇÃO — MISSÃO FISCAL 02

A proteção posterior à outbox foi implementada. Transmissões que terminam sem
resposta conclusiva passam a `RESPOSTA_DESCONHECIDA` e não são reenviadas.
Reinício e lease vencido preservam esse bloqueio. A Central Fiscal pode agendar
somente consulta por recibo ou chave, reutilizando o XML assinado armazenado.
Numeração vinculada a documento não expira automaticamente, e cancelamento,
liberação ou retransmissão em lote são recusados enquanto houver risco de a
SEFAZ já ter recebido o documento. Não foi criado worker automático e produção
continua bloqueada.

Validação: 153 testes focados e 10 subtestes; suíte completa funcional com
1.357 testes aprovados, 1 ignorado e 32 subtestes. O teste DPAPI permaneceu
excluído pelo limite já documentado do runtime isolado do Windows.

Arquivos centrais desta missão: `services/fiscal_service.py`,
`services/fiscal_outbox_service.py`, `services/fiscal_sale_service.py` e
`nabicode_legacy.py`. Regressões estão em `tests/test_fiscal_service.py` e
`tests/test_fiscal_sale_service.py`/`tests/test_fiscal_outbox_service.py`.

## 1. MISSÃO EXECUTADA

Implementar somente a fundação persistente da fila fiscal do NabiCode, substituindo a separação insegura entre o commit da venda/documento e a gravação posterior da fila JSON por uma outbox SQLite transacional.

Foi autorizado:

- criar tabela própria de outbox fiscal;
- gravar venda, documento fiscal e item inicial da outbox na mesma transação;
- implementar operações atômicas de claim/lease para uso futuro;
- criar estado explícito `RESPOSTA_DESCONHECIDA`;
- migrar de forma idempotente a fila antiga `fiscal.fila_transmissao.v1`, sem apagá-la;
- criar testes de atomicidade, duplicidade, concorrência, migração e isolamento comercial.

Ficou proibido alterar IBS/CBS, cClassTrib, ICMS, IPI, PIS/COFINS, CFOP, NCM/CEST, XML, XSD, QR Code, DANFE, certificado, contingência, endpoints, interface além do mínimo, comportamento comercial e bloqueio de produção. Também foi proibido criar worker automático.

O escopo executado ficou restrito à persistência/outbox fiscal, compatibilidade da Central Fiscal, schema 20, testes e documentação do estado.

## 2. ESTADO ANTES DA ALTERAÇÃO

A venda e `fiscal_sale_documents` já participavam da mesma transação SQLite. Entretanto, depois desse commit, `FiscalSaleService.enqueue_pending()` criava separadamente uma entrada JSON em `fiscal.fila_transmissao.v1`.

Fluxo anterior relevante:

1. venda, estoque, financeiro e documento fiscal eram commitados;
2. somente depois do commit o sistema chamava `enqueue_pending()`;
3. a fila era gravada como um documento JSON inteiro na tabela de configurações;
4. falha, encerramento ou queda entre 1 e 2 deixava venda fiscal persistida sem fila;
5. a fila JSON não possuía claim/lease atômico para duas instâncias;
6. timeout poderia retornar ao mecanismo comum de tentativa sem um estado explícito de resultado desconhecido.

Riscos originais: documento órfão, perda de continuidade, gravação concorrente do JSON, duplicidade de transmissão, ausência de propriedade temporária por worker e retransmissão cega após resposta incerta.

## 3. ALTERAÇÕES REALIZADAS

### `database/schema_initializer.py`

- Função `initialize_database()`.
- Antes: schema 19 possuía `fiscal_sale_documents`, mas não uma outbox relacional.
- Depois: schema 20 cria `fiscal_outbox`, índices, constraints, foreign keys e executa a cópia idempotente da fila legada dentro da transação de atualização.
- Também passa a persistir explicitamente `modo_operacao=COMERCIAL` em instalação nova com `INSERT OR IGNORE`, preservando escolhas existentes.

### `services/fiscal_outbox_service.py` — novo

- Classe `FiscalOutboxService`.
- Centraliza criação transacional, listagem, compatibilidade, migração da fila antiga, claim, lease, recuperação de lease vencido, reagendamento, conclusão e resposta desconhecida.
- Não contém transmissão nem thread automática.

### `services/fiscal_sale_service.py`

- Função `persist_draft()`.
- Antes: inseria somente o documento fiscal na transação da venda.
- Depois: insere o documento e imediatamente insere a outbox usando a mesma conexão/transação SQLite.
- `enqueue_pending()` virou compatibilidade idempotente: retorna a outbox já existente e somente recupera documentos antigos que ainda não possuam item.

### `services/fiscal_service.py`

- Métodos de fila existentes continuam com a mesma interface pública, mas passam a ler/gravar a outbox SQLite.
- A Central Fiscal continua acionando manualmente o processamento.
- Nenhum worker foi criado.

### `nabicode_legacy.py`

- `DB_SCHEMA_VERSION` passou de 19 para 20.
- `finalizar_venda()` passa o ator para a criação transacional da outbox.
- Foi removida a segunda chamada pós-commit a `enqueue_pending()`, eliminando a janela de inconsistência.

### Testes

- Novo `tests/test_fiscal_outbox_service.py` com testes de atomicidade, idempotência, claim/lease, resposta desconhecida e migração.
- `tests/test_fiscal_sale_service.py` foi adaptado para conferir a outbox SQLite real.
- `tests/test_pdv_transaction_service.py` ganhou regressão garantindo que venda comercial não cria outbox/documento fiscal.
- `tests/test_schema_initializer.py` ganhou verificação da nova tabela e do padrão `COMERCIAL`.

### Documentação

- `ESTADO_ATUAL.md` recebeu o checkpoint lógico da Missão Fiscal 01.

## 4. BANCO DE DADOS

Migration: **SIM**, schema 19 para schema 20 por meio do inicializador transacional já existente.

Tabela criada: `fiscal_outbox`.

Colunas:

- `id`;
- `sale_id`;
- `fiscal_document_id`;
- `access_key`;
- `environment`;
- `operation`;
- `status`;
- `attempts`;
- `max_attempts`;
- `retry_minutes`;
- `next_attempt_at`;
- `worker_id`;
- `claimed_at`;
- `lease_until`;
- `receipt`;
- `last_error_code`;
- `last_error_message`;
- `model`;
- `reservation_id`;
- `xml_b64`;
- `original_xml_b64`;
- `actor`;
- `contingency`;
- `contingency_deadline_at`;
- `legacy_id`;
- `metadata_json`;
- `created_at`;
- `updated_at`.

Índices/constraints:

- `uq_fiscal_outbox_document`: um item por documento fiscal;
- `uq_fiscal_outbox_legacy`: impede migrar duas vezes o mesmo registro antigo;
- `uq_fiscal_outbox_authorization_key`: impede autorizações/recibos incompatíveis para a mesma chave;
- `idx_fiscal_outbox_claim`: busca por estado, próxima tentativa e lease;
- `idx_fiscal_outbox_sale`: busca por venda/documento;
- checks de ambiente, status, modelo, tentativas e contingência no schema oficial;
- foreign key de `sale_id` para `movimentacoes(id)`;
- foreign key de `fiscal_document_id` para `fiscal_sale_documents(id)`.

Rollback: no PDV fiscal, venda, pagamentos, estoque, financeiro, documento e outbox usam a mesma conexão e o mesmo commit. Falha na outbox reverte tudo.

Compatibilidade: a fila JSON original não é removida nem alterada. Seus registros são copiados para a outbox de modo idempotente. Registros antigos sem documento relacional correspondente continuam preservados com metadados legados.

## 5. FLUXO ANTES E DEPOIS

ANTES:

`preparar fiscal → reservar número → BEGIN → venda + estoque + financeiro + documento → COMMIT → gravar fila JSON separadamente`

Falha após o commit:

`venda/documento persistidos → fila ausente → recuperação manual/incerta`

DEPOIS:

`preparar fiscal → reservar número → BEGIN → venda + estoque + financeiro + documento + outbox → COMMIT`

Falha antes do commit:

`erro em qualquer etapa → ROLLBACK → nenhuma venda/documento/outbox parcial`

Sucesso:

`commit único → Central Fiscal encontra item persistente na outbox`

## 6. MODO COMERCIAL / NÃO FISCAL

Confirmado como preservado:

- sem certificado;
- sem SEFAZ;
- sem XML fiscal;
- sem numeração fiscal;
- sem outbox/fila fiscal para vendas novas;
- sem dependência de internet.

Pendências fiscais anteriormente criadas permanecem no banco quando o usuário muda posteriormente para `COMERCIAL`.

## 7. MODO FISCAL

### IMPLEMENTADO

- preparação fiscal anterior à persistência da venda;
- venda, documento e item inicial da outbox no mesmo commit;
- outbox SQLite persistente;
- unicidade por documento e autorização/chave;
- migração idempotente da fila antiga;
- claim/lease atômico preparado;
- recuperação de lease vencido;
- reagendamento e conclusão;
- estado `RESPOSTA_DESCONHECIDA` não reivindicável automaticamente;
- Central Fiscal continua processando manualmente pela interface compatível.

### AINDA NÃO IMPLEMENTADO

- worker automático;
- uso de claim/lease pelo futuro worker;
- reconciliação por chave/recibo após timeout ou resposta desconhecida;
- correção definitiva da liberação temporal da numeração após possível transmissão;
- conformidade tributária 2026 restante;
- liberação de produção.

## 8. SEGURANÇA FISCAL

- Duplicidade: reduzida por índices únicos de documento, chave/autorização e registro legado.
- Perda de documento: eliminada a janela entre commit da venda e criação da fila.
- Atomicidade: venda, documento e outbox são atômicos no PDV fiscal.
- Idempotência: criação repetida da outbox e migração legada não duplicam.
- Numeração: não foi refatorada. A reserva continua anterior à transação; falha comercial ainda tenta liberá-la. O risco após início de transmissão fica para a missão seguinte.
- Timeout: comportamento de transmissão não foi alterado.
- Resposta desconhecida: o estado persistente foi criado, mas a classificação/reconciliação automática ainda não foi integrada.
- Concorrência: claim usa `BEGIN IMMEDIATE`; dois workers não reivindicam o mesmo item.
- Duas instâncias: a fundação de claim/lease está pronta, mas o processador manual legado ainda não foi convertido em worker com claim.
- Recuperação após queda: lease vencido pode ser recuperado; itens persistem no SQLite.
- Integridade do XML: XML e regras fiscais não foram modificados; payload e original permanecem armazenados na outbox.

## 9. TESTES

Testes novos:

- 10 testes dedicados em `tests/test_fiscal_outbox_service.py`;
- venda fiscal cria um documento e uma outbox;
- falha da outbox provoca rollback integral;
- duplicidade por documento e chave;
- claim concorrente;
- lease válido e vencido;
- concluído não retorna;
- resposta desconhecida não retorna automaticamente;
- migração repetida é idempotente e preserva o JSON;
- pendência permanece após mudança para comercial.

Testes alterados:

- `tests/test_fiscal_sale_service.py`;
- `tests/test_pdv_transaction_service.py`;
- `tests/test_schema_initializer.py`.

Resultados:

- suíte focada: 158 aprovados e 10 subtestes aprovados;
- primeira suíte completa: 1.316 aprovados, 1 ignorado, 1 falhou e 36 erros de preparação; os 36 erros foram `PermissionError` na pasta temporária global do Windows e a falha foi DPAPI recusada pelo runtime isolado;
- repetição completa com pasta temporária exclusiva no workspace e exclusão somente do teste DPAPI: 1.352 aprovados, 1 ignorado, 1 desmarcado e 32 subtestes aprovados;
- `compileall` dos fontes: aprovado;
- `git diff --check`: aprovado, apenas avisos de futura normalização LF/CRLF;
- lint dedicado: não configurado/não executado.

## 10. TESTES QUE NÃO FORAM POSSÍVEIS

- DPAPI real do usuário Windows no runtime isolado atual;
- certificado A1 real;
- autorização na SEFAZ Bahia;
- rejeição e consulta real de recibo;
- timeout real de rede e resposta desconhecida da SEFAZ;
- homologação fiscal acompanhada;
- impressão física;
- queda forçada durante transmissão real;
- duas instalações reais transmitindo simultaneamente;
- validação manual da interface.

Nenhuma impressora, certificado real, banco real ou endpoint SEFAZ foi utilizado.

## 11. ARQUIVOS ALTERADOS

Arquivos desta missão:

- `ESTADO_ATUAL.md` — modificado;
- `database/schema_initializer.py` — modificado;
- `nabicode_legacy.py` — modificado;
- `services/fiscal_outbox_service.py` — novo;
- `services/fiscal_sale_service.py` — modificado;
- `services/fiscal_service.py` — modificado;
- `tests/test_fiscal_outbox_service.py` — novo;
- `tests/test_fiscal_sale_service.py` — modificado;
- `tests/test_pdv_transaction_service.py` — modificado;
- `tests/test_schema_initializer.py` — modificado;
- `HANDOFF_CHATGPT.md` — novo.

Alteração anterior, preservada e não produzida por esta missão:

- `docs/HOMOLOGACAO_FISCAL_BAHIA.md` — já estava modificado antes do início; diferença observada é apenas remoção da última linha vazia.

Nenhum arquivo foi removido.

## 12. GIT

- Branch: `dev/nabicode-2.5.1`.
- Remoto: `origin`, `https://github.com/peumusicasia-ship-it/NABI-ATUALIZACAO.git`.
- Commit anterior/HEAD: `2c3d433 fix: prepara homologacao fiscal segura na Bahia`.
- Esse commit já existia antes da missão.
- Commit criado nesta missão: **NÃO CRIADO**.
- Hash: **NÃO CRIADO**.
- Mensagem: não aplicável.
- Push: **NÃO**.
- Branch em relação ao remoto: 1 commit à frente, 0 atrás; esse estado já existia no início.
- Existem alterações não commitadas: sim, todos os arquivos listados na seção 11.
- `docs/HOMOLOGACAO_FISCAL_BAHIA.md` é alteração anterior e não deve ser misturada sem revisão.

Status esperado após este handoff:

`dev/nabicode-2.5.1...origin/dev/nabicode-2.5.1 [ahead 1]`, com arquivos modificados e novos ainda não commitados.

## 13. RISCOS RESTANTES

🔴 CRÍTICO

- produção fiscal continua inadequada e deve permanecer bloqueada;
- não existe reconciliação segura após timeout/resposta desconhecida;
- numeração pode exigir proteção adicional quando uma transmissão tiver sido iniciada.

🟠 ALTO

- o processador manual legado ainda não usa claim/lease; a fundação existe, mas duas instâncias não devem processar manualmente a mesma fila;
- a classificação automática de falha de comunicação como `RESPOSTA_DESCONHECIDA` ainda não foi conectada à transmissão;
- worker automático ainda não existe.

🟡 MÉDIO

- registros legados sem vínculo relacional são preservados, mas precisam de auditoria/reconciliação futura;
- DPAPI não pôde ser validada neste runtime;
- homologação real Bahia ainda não foi executada.

🟢 BAIXO

- avisos de LF/CRLF no Git;
- alteração anterior de uma linha vazia em `docs/HOMOLOGACAO_FISCAL_BAHIA.md` precisa ser separada antes de commit.

## 14. PRÓXIMA MISSÃO RECOMENDADA

Missão Fiscal 02: revisar numeração, timeout, resposta desconhecida e reconciliação antes de criar qualquer worker automático.

Recomenda-se primeiro auditar a transação e a migração desta missão. Não iniciar a Missão Fiscal 02 automaticamente.

## 15. REGRA DE TECNOLOGIA

Python permanece a linguagem principal do NabiCode.

Outra linguagem, runtime ou componente nativo somente deve ser considerado diante de necessidade técnica comprovada e após documentar:

- inadequação concreta do Python;
- benefício mensurável;
- compatibilidade Windows;
- compatibilidade PyInstaller;
- build e instalação offline;
- impacto no instalador;
- dependências;
- segurança;
- manutenção;
- testes e atualização.

Nenhum módulo estável deve ser reescrito por preferência tecnológica. Esta missão utilizou somente Python e SQLite já existentes no projeto.

## 16. VEREDITO PARA O AUDITOR

`MISSÃO: CONCLUÍDA`

`TESTES: APROVADOS`

`MODO COMERCIAL: PRESERVADO`

`MODO FISCAL: outbox transacional implementada; processamento ainda manual; reconciliação e worker ainda não implementados`

`PRODUÇÃO: BLOQUEADA`

`PODE SEGUIR PARA PRÓXIMA MISSÃO: REQUER AUDITORIA`

`COMMIT: NÃO CRIADO`

`PUSH: NÃO`

## RESUMO PARA CELULAR

- Missão: criar outbox fiscal transacional.
- Resultado: concluída.
- Venda, documento e outbox agora usam um único commit SQLite.
- Falha na outbox reverte toda a venda fiscal.
- Venda comercial continua totalmente sem fiscal.
- Fila JSON antiga foi preservada e migrada sem duplicar.
- Claim/lease e resposta desconhecida foram preparados.
- Nenhum worker automático foi criado.
- Focados: 158 testes + 10 subtestes aprovados.
- Suíte: 1.352 aprovados, 1 skip, 1 DPAPI não executado.
- Commit: não criado.
- Push: não.
- Produção continua bloqueada.
- Risco principal: reconciliação de timeout e proteção da numeração.
- Próxima etapa: Missão Fiscal 02, somente após auditoria.
