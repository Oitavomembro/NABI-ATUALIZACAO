# NabiCode — Estado Atual

## Checkpoint fiscal — fechamento monetário do documento

- o XML bloqueia soma de pagamentos inferior ao total fiscal;
- códigos e valores de pagamento inválidos são recusados antes da assinatura e transmissão;
- `90 — sem pagamento` exige valor zero e não pode ser combinado com dinheiro, PIX ou cartão;
- devoluções continuam aceitas corretamente como operação única sem pagamento;
- pagamentos acima do total continuam permitidos somente com o troco explícito gerado no XML;
- validação focada: 126 testes e 10 subtestes aprovados;
- suíte completa: 1.170 testes, 1 ignorado e 32 subtestes aprovados;
- `compileall` e `git diff --check` aprovados.

## Checkpoint fiscal — estados determinísticos na Central Fiscal

- documentos cancelados deixam de ser contabilizados como pendentes;
- a Central Fiscal apresenta cartão próprio de canceladas sem ocultar autorizadas, pendentes ou falhas;
- somente estados realmente aguardando transmissão aparecem em `list_pending`;
- documentos em cancelamento local, cancelamento fiscal aceito ou cancelamento concluído não podem voltar à fila;
- a tentativa de reenvio pela interface aplica a mesma proteção do serviço central;
- validação focada: 13 testes aprovados;
- suíte completa: 1.168 testes, 1 ignorado e 32 subtestes aprovados;
- `compileall` e `git diff --check` aprovados.

## Checkpoint fiscal — tributos da nota original e devolução sem pagamento

- o leitor de NF-e passa a extrair efetivamente base, alíquota e valor de ICMS, PIS, COFINS e IPI;
- valores tributários malformados no XML são recusados com indicação do campo, sem virar zero silenciosamente;
- os tributos lidos alimentam o cálculo proporcional já existente da devolução integral ou parcial;
- NF-e de devolução define centralmente pagamento `90 — sem pagamento` e valor `0,00`;
- foi removido o risco de representar devolução como pagamento em dinheiro;
- validação focada: 125 testes e 10 subtestes aprovados;
- suíte completa: 1.168 testes, 1 ignorado e 32 subtestes aprovados;
- `compileall` e `git diff --check` aprovados.

## Checkpoint fiscal — pagamentos completos no XML

- cada forma recebida pelo PDV gera seu próprio grupo `detPag`, sem transformar pagamentos mistos em “Outros”;
- entrada por PIX/dinheiro/cartão e saldo em crediário permanecem discriminados no documento;
- cartão preserva por parcela de pagamento o tipo POS/TEF e a autorização opcional;
- pagamento em dinheiro acima do total gera `vTroco` automaticamente;
- valores ausentes, inválidos ou não positivos são bloqueados antes de reservar definitivamente o documento;
- validação focada: 89 testes e 10 subtestes aprovados;
- suíte completa: 1.168 testes, 1 ignorado e 32 subtestes aprovados;
- `compileall` e `git diff --check` aprovados.

## Checkpoint fiscal — cancelamento consistente da venda

- venda fiscal pendente pode ser cancelada localmente sem deixar fila, numeração, estoque ou financeiro em estado divergente;
- venda já autorizada é bloqueada no cancelamento comum e exige o evento oficial pela Central Fiscal;
- após a autorização do cancelamento pela SEFAZ, a reversão comercial ocorre de forma transacional;
- se a reversão local falhar depois do evento oficial, o estado `CANCELADO_FISCAL` permite recuperação sem reenviar o evento;
- filas canceladas não são transmitidas nem podem ser reativadas por engano;
- a Central Fiscal executa o cancelamento em segundo plano e mantém a senha do A1 apenas em memória;
- foram adicionados testes de regressão para rollback comercial, fila cancelada e cancelamento autorizado;
- suíte completa: 1.166 testes, 1 ignorado e 32 subtestes aprovados;
- `compileall` e `git diff --check` aprovados.

## Checkpoint fiscal — Central Fiscal e cartão POS

- Central Fiscal existente passa a reunir vendas vinculadas, documentos autorizados e eventos sem duplicar persistência;
- cartões mostram autorizadas, pendentes, falhas e total;
- detalhes exibem venda, chave, protocolo, fila, tentativas e última mensagem;
- transmissão e reenvio usam a fila oficial em segundo plano, mantendo a interface responsiva;
- senha do A1 é solicitada somente para a tarefa, não é persistida e a referência em memória é limpa ao terminar;
- a fila não contorna o bloqueio de produção;
- Débito e Crédito mostram no PDV o campo opcional de NSU/autorização da maquininha;
- POS comum é identificado corretamente como não integrado (`tpIntegra=2`) e não exige número do comprovante;
- quando informado, `cAut` é preservado no pagamento e incluído no XML, limitado a 20 caracteres;
- validação focada: 119 testes e 13 subtestes aprovados;
- suíte completa: 1.160 testes, 1 ignorado e 32 subtestes aprovados;
- `compileall` e `git diff --check` aprovados.

## Checkpoint fiscal — destinatário automático da venda

- schema 16 amplia o cadastro oficial do cliente com e-mail, inscrição estadual, indicador de contribuinte e endereço fiscal estruturado;
- não foi criado cadastro paralelo: criação e edição usam a mesma tabela `clientes` e o mesmo serviço oficial;
- NFC-e de consumidor final continua sem exigir identificação desnecessária;
- cliente identificado reutiliza automaticamente nome, CPF/CNPJ, e-mail e inscrição estadual;
- NF-e bloqueia antes da venda quando CPF/CNPJ ou endereço fiscal obrigatório estiver incompleto;
- UF do cliente e do emitente determinam automaticamente operação interna ou interestadual e ajustam o CFOP pelo fluxo já existente;
- XML passa a gerar `enderDest` e e-mail quando disponíveis;
- validação de CPF possui cálculo dos dígitos verificadores e rejeita sequências fictícias;
- validação focada: 105 testes e 10 subtestes aprovados;
- suíte completa: 1.153 testes, 1 ignorado e 32 subtestes aprovados;
- `compileall` e `git diff --check` aprovados.

## Checkpoint fiscal — venda do PDV vinculada ao documento

- schema 15 cria vínculo único entre venda, reserva de numeração, chave de acesso, XML e fila fiscal;
- preparação fiscal ocorre antes da gravação: ficha incompleta, certificado ausente ou XML inválido não deixam venda/estoque/financeiro parcialmente persistidos;
- vínculo fiscal participa da mesma transação SQLite da venda;
- após o commit comercial, o documento é enfileirado de forma idempotente pela chave de acesso;
- reinício ou nova tentativa não cria uma segunda autorização da mesma nota;
- a fila reconhece o rascunho, inclui QR Code da NFC-e, assina com o certificado A1, valida no XSD e monta o lote antes da transmissão;
- sucesso confirma a numeração e sincroniza protocolo/status com a venda; falha preserva a pendência para recuperação;
- validação focada: 100 testes e 10 subtestes aprovados;
- suíte completa: 1.150 testes, 1 ignorado e 32 subtestes aprovados;
- `compileall` aprovado para os arquivos acessíveis; diretórios antigos de build protegidos pelo Windows foram apenas ignorados;
- `git diff --check` aprovado.

## Checkpoint fiscal — preparação nacional das 27 UFs

- catálogo fiscal nacional centralizado em `services/fiscal_state_catalog.py`;
- as 27 UFs possuem código IBGE e autorizador NF-e catalogado (próprio, SVRS ou SVAN);
- seleção de endpoint, QR Code e consulta NFC-e deixou de depender de constantes da Bahia dentro do motor;
- Bahia permanece como perfil validado atualmente; as demais UFs ficam preparadas e bloqueadas com mensagem explícita até homologação, evitando transmissão para destino presumido;
- endpoints personalizados seguros continuam tendo prioridade, preservando integrações existentes;
- validação focada: 83 testes e 10 subtestes aprovados;
- suíte completa: 1.144 testes, 1 ignorado e 32 subtestes aprovados;
- `compileall` e `git diff --check` aprovados.

## Identificação

- **Versão:** 2.5.1 DEV
- **Base:** Checkpoint 41 — Módulo Caixa
- **Branch planejada:** `dev/nabicode-2.5.1`
- **Status:** DESENVOLVIMENTO
- **Instalador:** frente separada — não modificar

## Testes conhecidos

- 990 passed;
- 22 subtests passed;
- suíte focada: 78 passed;
- suíte focada: 3 subtests passed;
- `compileall` aprovado;
- stress aprovado;
- benchmark aprovado;
- soak aprovado.

## Regras críticas preservadas

- A versão 2.5.0 RELEASE permanece aprovada, congelada e não deve ser modificada.
- Esta frente trabalha somente sobre o NabiCode 2.5.1 DEV.
- Não alterar regras comerciais, cálculos financeiros, persistência, licenças, impressão, corte, estoque ou banco sem missão explícita e evidência da causa.
- Antes de corrigir: localizar a implementação real, identificar a causa, registrar evidência e criar teste de regressão quando tecnicamente possível.
- Não remover testes existentes.
- Bancos reais, backups, credenciais, variáveis de ambiente e dados de clientes nunca devem ser versionados.
- Arquivos do instalador pertencem a uma frente separada e não devem ser modificados nesta branch sem missão explícita.

## Pendências externas

- validação física Windows;
- impressão e corte quando aplicável;
- VM e operação offline conforme documentação existente.

## Validação desta preparação Git

- `python -m compileall .`: aprovado.
- `python -m pytest`: não iniciado porque o ambiente atual não possui `pytest`.
- Fallback `python -m unittest discover -s tests`: 803 testes executados em 30,907 s; 796 aprovados, 1 falha e 6 erros de importação.
- Os 6 erros ocorreram pela ausência de `pytest` no ambiente.
- A falha ocorreu no smoke de startup pela ausência de `pygame` no ambiente.
- Nenhum código funcional foi alterado para mascarar essas limitações. O resultado oficial conhecido do Checkpoint 40 permanece `990 passed, 22 subtests passed`.

## Missão concluída — Módulo Caixa

Implementada no NabiCode 2.5.1 DEV sobre a base oficial do Checkpoint 40.

### Arquitetura

- sessões persistidas por terminal em `cash_sessions`;
- sangrias e suprimentos persistidos em `cash_movements`;
- vendas e recebimentos agregados das fontes oficiais em `movimentacoes`, sem duplicação;
- regras e cálculos isolados em `services/cash_service.py`;
- patch de integração e interface mantido mínimo em `nabicode_legacy.py`;
- auditoria de abertura, sangria, suprimento e fechamento na infraestrutura existente.

### Abertura

- Se não houver caixa aberto, perguntar como abrir.
- Oferecer `Informar saldo inicial`.
- Oferecer `Abrir sem informar`.
- Remover `Cancelar`.
- Abrir sem informar significa saldo inicial de R$ 0,00.
- Registrar o usuário.
- Registrar data e hora.
- Registrar o valor.
- Registrar o modo de abertura.
- Não perguntar novamente enquanto existir caixa aberto.

### Caixa

Criar futuramente uma aba própria contendo:

- estado aberto ou fechado;
- saldo inicial;
- vendas em dinheiro;
- PIX;
- cartão;
- recebimentos;
- sangrias;
- suprimentos;
- dinheiro esperado;
- dinheiro contado;
- diferença;
- observação;
- usuário que abriu;
- usuário que fechou;
- data e hora;
- histórico de caixas.

### Regra contábil

PIX e cartão entram no movimento do período, mas **não aumentam o dinheiro físico esperado na gaveta**.

### Múltiplos usuários

Uma sessão de caixa pertence ao terminal ou caixa físico. Cada operação registra o usuário responsável. Não criar automaticamente um caixa independente para cada usuário.

## Validação do Checkpoint 41

- 11 testes automatizados do Caixa cobrindo os 20 cenários obrigatórios, aprovados;
- suíte focada de Caixa, schema, PDV e financeiro: 32 aprovados;
- suíte completa: 999 aprovados e 1 falha preexistente de fidelidade do splash (hash esperado `7057...`, hash atual da própria base e protótipo `6697...`);
- `compileall`: aprovado após a correção de integração;
- GUI física Windows: pendente de validação manual;
- stress, benchmark e soak: não executados nesta missão.

## Checkpoint lógico

**NabiCode 2.5.1 DEV — Checkpoint 41.1 — Caixa UI**

## Checkpoint 41.1 — Caixa UI

- Caixa consolidado como único ponto visual para sangria, suprimento e fechamento;
- removidos do Dashboard os acessos legados `Movimentação de Caixa` e `Finalizar dia`;
- layout reorganizado em cabeçalho, cards, ações, movimentações da sessão e histórico;
- abertura visível somente com caixa fechado; ações operacionais visíveis somente com caixa aberto;
- sangria, suprimento, fechamento e detalhes históricos migrados para modais NabiCode;
- movimentos oficiais de vendas e recebimentos exibidos sem duplicação de persistência;
- fluxos do Caixa deixaram de usar fade por `-alpha` e passaram à revelação estável após o layout;
- regras contábeis, persistência, auditoria e Schema 14 preservados;
- validação física Windows do novo layout e da ausência de glitch permanece pendente.

## Candidato Checkpoint 41.2 — Runtime responsivo

- removida a animação `-alpha` da transição splash → janela principal;
- a abertura obrigatória do Caixa não adquire mais `grab`, eliminando bloqueio invisível da raiz;
- fechar a pergunta obrigatória pelo X encerra normalmente a aplicação, sem permitir operação sem abertura;
- modais operacionais liberam explicitamente qualquer `grab` antes de destruir a janela;
- timeout das conexões do Caixa na thread de interface limitado a 3 segundos;
- logging pontual de startup e Caixa registrado em `startup.log` e `nabicode.log`;
- aprovação do Checkpoint 41.2 permanece condicionada à validação física de 10 ciclos no Windows.

## Correções físicas posteriores — estado e reabertura

- checagem automática do Caixa limitada a uma única execução no startup;
- callbacks pendentes de abertura passam a ser identificados e não se multiplicam;
- cancelar o formulário de saldo não agenda novamente a pergunta de abertura;
- fechamento apenas recarrega o estado persistido e exibe as ações de caixa fechado;
- modal de abertura e modal de fechamento possuem proteção de instância única;
- nova sessão sempre é criada por ação explícita após o fechamento;
- fechamento gera comprovante pelo pipeline oficial `Cupom 80 mm`, fora da thread da GUI;
- ordem real de splash, raiz e diálogo do Caixa instrumentada nos logs de runtime;
- validação física Windows da reabertura, impressão e ausência de piscada permanece pendente.

## Infraestrutura de modais do Caixa — candidato seguinte

- todos os fluxos do Caixa usam `_criar_modal_nabicode`, `_mostrar_modal_nabicode` e `_fechar_modal_caixa`;
- nenhuma janela do Caixa usa `grab_set`, `wait_window`, `wait_variable`, `transient`, `topmost`, `withdraw/deiconify`, `focus_force` ou callback `after` para aparecer;
- probe mínimo `TESTE MODAL` criado sobre o mesmo helper, sem banco, mas não exposto na UI de produção;
- Sangria, Suprimento, Fechamento, escolha de abertura, saldo informado e detalhes compartilham a mesma infraestrutura;
- criação de sessão centralizada com fontes permitidas `OPEN_WITH_VALUE` e `OPEN_WITHOUT_VALUE`;
- origem desconhecida é recusada e registrada; startup e simples abertura da tela não criam sessão;
- sessão aberta encontrada no startup é sempre a fonte persistida do terminal, inclusive uma sessão criada em execução anterior;
- UI visual aprovada preservada sem expansão funcional.

## Checkpoint 41.5 — fechamento seguro do Caixa

- comprovante de fechamento respeita a impressora e o formato próprios da categoria `fechamento`;
- removido o acoplamento indevido com `impressora_recibo`, origem da seleção externa `LIVRARIA NABI`;
- despacho continua limitado a um único trabalho por sessão, inclusive sob chamadas repetidas;
- modal de fechamento é exibido imediatamente e carrega o resumo após a primeira renderização;
- testes usam serviço de impressão simulado e não acionam hardware físico;
- validação focada: 28 testes de interface/runtime aprovados e 19 testes adicionais de Caixa/impressão aprovados;
- validação física Windows permanece pendente.

## Candidato Checkpoint 42 — auditoria de estabilidade

- liberação do lock exclusivo do banco tolera a janela curta de compartilhamento de arquivos do Windows;
- teste de concorrência confirma um único vencedor, sete bloqueios e remoção final do lock;
- dependências de teste restauradas no ambiente local, sem alteração do pacote do aplicativo;
- hash de fidelidade do splash sincronizado com o runtime e o protótipo aprovado, que permanecem byte a byte idênticos e sem alterações desde o Checkpoint 40;
- validação final: `compileall` aprovado; suíte completa com 1034 testes e 22 subtestes aprovados, sem falhas ou avisos.
- stress, benchmark e soak: 3 testes aprovados em 37,44 s;
- dependências instaladas no ambiente de auditoria verificadas sem conflitos;
- integridade do repositório Git aprovada;
- nenhuma interface gráfica ou impressora física foi acionada durante a auditoria.

## Checkpoint 42.2 — impressão segura de relatórios

- relatórios PDF deixaram de usar `os.startfile(..., "print")`, mecanismo capaz de derrubar o runtime em algumas extensões de PDF no Windows;
- envio passou a usar o processo isolado `WindowsPDFPrinter`, já adotado pelo restante do aplicativo;
- impressora padrão do sistema preservada como destino do fluxo de relatórios;
- teste de regressão simula o Windows e confirma o despacho isolado sem acionar impressora;
- 31 testes focados aprovados;
- suíte completa: 1035 testes e 22 subtestes aprovados.

## Checkpoint 42.3 — sincronização entre frentes

- incorporados os commits externos `843a5ff` e `b30ee70` da mesma branch, sem bifurcação ou conflito Git;
- fechamento persistido sem impressão automática e com ação explícita para imprimir ou voltar;
- bloqueio de reentrada impede trabalhos simultâneos e é liberado após sucesso ou falha para permitir nova tentativa;
- movimento total do Caixa representa somente vendas, sem somar recebimentos, sangrias ou suprimentos;
- diálogo obrigatório de abertura solicita primeiro plano momentâneo, sem modalidade ou `topmost` persistente;
- preservado o roteamento exclusivo da categoria `fechamento`, sem reutilizar `impressora_recibo`;
- 47 testes focados aprovados;
- suíte completa: 1041 testes e 22 subtestes aprovados.

## Checkpoint 42.4 — abertura isolada de arquivos e pastas

- removidas do processo principal todas as chamadas funcionais restantes a `os.startfile`;
- arquivos fiscais e documentos de histórico usam o abridor externo já homologado;
- pastas de backup, diagnóstico, PDFs e sistema usam abertura isolada por processo no Windows;
- validação explícita diferencia arquivo ausente de pasta ausente;
- teste de regressão confirma abertura de diretório por processo simulado, sem lançar aplicativo externo;
- 11 testes focados e compilação aprovados;
- suíte completa: 1042 testes e 22 subtestes aprovados.

## Checkpoint 42.5 — resumo do Caixa mais leve

- resumo da sessão deixa de materializar tipos de movimentação que nunca participam do Caixa;
- consulta oficial limita a leitura a vendas (`COMPRA`) e recebimentos (`PAGAMENTO`);
- cálculo, filtro temporal, cancelamentos e fontes persistidas permanecem inalterados;
- nenhuma migração ou novo índice foi introduzido;
- teste de regressão inspeciona a consulta efetivamente enviada ao SQLite;
- 27 testes focados aprovados;
- suíte completa: 1043 testes e 22 subtestes aprovados.

## Checkpoint 42.6 — proteção ampliada dos diagnósticos

- sanitização de logs passa a remover cabeçalhos `Authorization: Bearer`;
- credenciais OAuth `access_token`, `refresh_token` e `client_secret` também são omitidas;
- proteção anterior de senhas, tokens, chaves de API e chaves privadas permanece ativa;
- teste de regressão usa somente segredos fictícios e verifica mensagem persistida;
- 18 testes focados de logs, diagnóstico e segurança aprovados;
- suíte completa: 1044 testes e 22 subtestes aprovados.

## Checkpoint 42.7 — configurações transacionais

- alterações unitárias e atualizações agrupadas de configuração agora são atômicas também na memória;
- falha ao substituir o arquivo restaura imediatamente o estado anterior em execução;
- arquivo persistido e valores ativos não divergem em casos como disco cheio, antivírus ou pasta bloqueada;
- gravação temporária, `fsync` e substituição atômica existentes foram preservados;
- 31 testes focados de núcleo, preferências e rede aprovados;
- suíte completa: 1046 testes e 22 subtestes aprovados.

## Checkpoint 42.8 — concorrência e chaves de configuração

- leitura integral das configurações passa a usar o mesmo bloqueio das demais operações;
- snapshots retornados continuam independentes por cópia profunda;
- chaves pontuadas com segmentos vazios são recusadas antes de qualquer mutação;
- chaves válidas e compatibilidade das preferências existentes permanecem inalteradas;
- 32 testes focados de núcleo, preferências e rede aprovados;
- suíte completa: 1047 testes e 22 subtestes aprovados.

## Checkpoint 42.9 — histórico limitado de tarefas

- gerenciador deixa de manter indefinidamente resultados e `Future` de tarefas antigas;
- histórico padrão preserva os 200 registros mais recentes;
- tarefas pendentes ou em execução nunca são removidas pelo limite;
- somente registros concluídos, falhos ou cancelados mais antigos são descartados ao criar nova tarefa;
- 17 testes focados de tarefas, núcleo e administração aprovados;
- suíte completa: 1049 testes e 22 subtestes aprovados.

## Checkpoint 42.10 — backup diário sem duplicidade concorrente

- execução automática diária passa a serializar verificação, criação e marcação do dia;
- dois disparos simultâneos geram apenas um conjunto de backups;
- o segundo disparo retorna como ignorado depois de observar o marcador atualizado;
- backups manuais e múltiplos destinos permanecem independentes;
- 18 testes focados de backup, snapshot e manutenção aprovados;
- suíte completa: 1050 testes e 22 subtestes aprovados.

## Checkpoint 42.11 — histórico de configurações corrompidas

- recuperações sucessivas deixam de substituir a cópia corrompida anterior;
- primeira ocorrência preserva o nome compatível `.corrompido`;
- ocorrências adicionais recebem sufixo único e mantêm o conteúdo original;
- recriação automática com valores padrão permanece inalterada;
- 28 testes focados de núcleo e preferências aprovados;
- suíte completa: 1051 testes e 22 subtestes aprovados.

## Checkpoint 42.12 — eventos internos consistentes

- assinatura, publicação e limpeza passam a compartilhar a mesma validação de nome;
- espaços externos são normalizados sem alterar os nomes válidos existentes;
- eventos vazios deixam de desaparecer silenciosamente e geram erro explícito;
- isolamento de falhas entre manipuladores permanece inalterado;
- 21 testes focados de núcleo, tarefas e auditoria aprovados;
- suíte completa: 1052 testes e 22 subtestes aprovados.

## Checkpoint 42.13 — recuperação do histórico de relatórios

- histórico persistido com JSON de formato antigo ou tipo incorreto deixa de bloquear relatórios;
- leitura retorna apenas entradas estruturadas como registros;
- próxima geração ou exportação reconstrói automaticamente a lista válida;
- limite de 200 registros e auditoria das operações permanecem inalterados;
- 18 testes focados de relatórios aprovados;
- suíte completa: 1053 testes e 22 subtestes aprovados.

## Checkpoint 42.14 — agendamentos resilientes

- persistência de agendamentos com tipo incorreto deixa de quebrar a listagem;
- registros antigos sem nome, relatório, frequência ou formato válidos são isolados;
- agendamentos íntegros continuam listados e executados mesmo ao lado de entradas incompatíveis;
- regras de frequência, formato, ativação e próxima execução permanecem inalteradas;
- 19 testes focados de relatórios aprovados;
- suíte completa: 1054 testes e 22 subtestes aprovados.

## Checkpoint 42.15 — falhas isoladas nos agendamentos

- falha em um relatório vencido deixa de interromper os agendamentos seguintes;
- cada erro é registrado na auditoria com o nome do agendamento e resultado `ERRO`;
- retorno para a interface continua contendo somente arquivos gerados com sucesso;
- cálculo de vencimento e atualização de execuções bem-sucedidas permanecem inalterados;
- 20 testes focados de relatórios aprovados;
- suíte completa: 1055 testes e 22 subtestes aprovados.

## Checkpoint 42.16 — exportação atômica de relatórios

- CSV, XLSX e PDF são gerados primeiro em arquivo temporário na pasta de destino;
- destino final só é substituído após a geração completa;
- falha remove o arquivo parcial e preserva uma versão anterior existente;
- histórico e auditoria continuam sendo registrados somente após sucesso;
- 21 testes focados de relatórios aprovados;
- suíte completa: 1056 testes e 22 subtestes aprovados.

## Checkpoint 42.17 — nomes exclusivos de backup

- backup reserva atomicamente o arquivo de destino antes de iniciar a cópia SQLite;
- operações com data e microssegundo idênticos recebem sufixos sequenciais;
- dois backups concorrentes não escolhem o mesmo caminho;
- arquivos anteriores nunca são sobrescritos por colisão de relógio;
- 14 testes focados de backup e snapshot aprovados;
- suíte completa: 1058 testes e 22 subtestes aprovados.

## Checkpoint 42.18 — notificações seguras entre threads

- publicação, leitura, limpeza e extensão do histórico compartilham bloqueio reentrante;
- alteração da duração padrão também é sincronizada;
- snapshots do histórico permanecem consistentes sob produtores concorrentes;
- limite configurado e ordem das notificações continuam preservados;
- 14 testes focados de notificações e tarefas aprovados;
- suíte completa: 1059 testes e 22 subtestes aprovados.

## Checkpoint 42.19 — validação de arquivos exportados

- exportação verifica existência e tamanho positivo antes de publicar o destino final;
- retorno silencioso de biblioteca sem conteúdo passa a ser tratado como falha;
- temporário vazio é removido e arquivo anterior permanece intacto;
- histórico e auditoria não registram exportação vazia como sucesso;
- 22 testes focados de relatórios aprovados;
- suíte completa: 1060 testes e 22 subtestes aprovados.

## Checkpoint 42.20 — propriedade nativa dos modais do Caixa

- causa raiz corrigida na fábrica compartilhada: as janelas do Caixa agora pertencem nativamente à janela principal;
- todos os modais usam `transient(self)`, impedindo que sejam ocultados atrás da aplicação;
- removido o contorno anterior baseado em `topmost`; não há temporizador, foco forçado nem bloqueio por `grab`;
- validação manual no Windows aprovada pelo usuário;
- 33 testes focados da infraestrutura de modais aprovados;
- suíte completa: 1060 testes e 22 subtestes aprovados;
- estresse, desempenho e uso prolongado: 3 testes aprovados em ambiente isolado, sem impressora física.

## Checkpoint 42.21 — Caixa diário, contextual e responsivo

- resumo da sessão deixa de varrer todo o histórico e consulta apenas os dias abrangidos pelo Caixa;
- novos índices cobrem movimentos por tipo/data e sessões por terminal/data de abertura;
- cartões do Caixa exibem, sob demanda, somente os movimentos que compõem o valor selecionado;
- resumo já carregado é reutilizado nos cartões, sem nova consulta ao banco a cada clique;
- tabelas permanentes de movimentos e sessões foram substituídas por ações compactas;
- histórico por dia é carregado somente quando solicitado e permite abrir os detalhes da sessão;
- maximização e restauração redesenham a árvore visível e a marca-d'água da tela atual;
- suíte completa: 1068 testes e 22 subtestes aprovados;
- estresse, desempenho, uso prolongado, dependências e empacotamento: 21 testes aprovados;
- nenhuma impressora física foi utilizada.

## Checkpoint 42.22 — fechamento legível e impressão confirmada

- resumo do fechamento foi dividido em cartões de dinheiro físico e meios eletrônicos;
- saldo, vendas, recebimentos, suprimentos, sangrias e valor esperado ganharam leitura individual;
- ação de impressão do fechamento não envia mais trabalho diretamente ao Windows;
- primeiro clique abre a pré-visualização padrão e exige nova ação explícita antes de imprimir;
- configuração própria do fechamento continua usando a impressora de histórico, sem origem externa;
- fechar pelo X a pergunta de abertura mantém a aplicação aberta e o Caixa fechado;
- raiz nasce com superfície escura e o redesenho central ignora mudanças apenas de posição;
- tentativas de pré-renderização que causaram sobreposição foram removidas integralmente;
- glitch visual da transição splash para a interface permanece pendente de diagnóstico futuro;
- suíte completa: 1071 testes e 22 subtestes aprovados;
- nenhuma janela ou impressora física foi acionada na validação final automática.

## Checkpoint 42.23 — carregamento de telas sob demanda

- medição do perfil TESTE confirmou cerca de 10 segundos bloqueados antes da criação da janela principal;
- causa raiz removida do roteador central: clientes, produtos, financeiro, Caixa, compras, relatórios e configurações deixam de ser construídos antecipadamente;
- somente o dashboard inicial é criado no startup; cada outro módulo é criado uma única vez, no primeiro acesso, e depois reutilizado;
- cada criação passa a registrar tela e duração no diagnóstico de startup, permitindo localizar futuros gargalos sem suposições;
- o carregamento ocorre antes da atualização e elevação da tela, preservando o contrato visual de navegação;
- 15 testes focados aprovados;
- suíte completa: 1072 testes e 22 subtestes aprovados;
- perfil TESTE utilizado; nenhuma janela adicional ou impressora física foi acionada.

## Checkpoint 42.24 — base atual integrada ao instalador Windows

- pipeline oficial executado no Windows com Python 3.14.7 e Inno Setup 6.7.3;
- corrigida na fonte a coleta de Tcl/Tk 9 do Python 3.14, distribuído em arquivos zip e antes ausente do onedir;
- ambiente Tcl/Tk é materializado somente durante o build e coletado pelo hook oficial do PyInstaller;
- corrigido conflito de variável que fazia a validação procurar a distribuição em `TK_LIBRARY`;
- smoke do executável aprovado em 1,33 segundo, com perfil PRODUCAO, versão 2.5.1 e splash canônica;
- instalador offline gerado em `build_output/installer/NabiCode_2.5.1_Setup_Offline.exe`;
- SHA-256: `473ff004a2b4fb816195bd8937b124d9a1de0aad353d12be43e59bf632697fd7`;
- suíte completa no ambiente de build: 1074 testes e 22 subtestes aprovados;
- instalador não foi executado e nenhuma impressora física foi utilizada.

## Checkpoint 42.25 / R6 TESTE — navegação superior determinística

- causa raiz removida: cada tela carregada sob demanda criava uma nova barra inicialmente completa, enquanto somente as barras anteriores tinham o perfil de visibilidade aplicado;
- as cópias por tela foram substituídas por uma única barra persistente compartilhada;
- a troca de tela não cria, oculta nem reordena botões;
- `Compras` foi integrado oficialmente a `MODULE_ORDER` e aos perfis compatíveis;
- a barra usa grade determinística de cinco colunas e segunda linha, evitando corte horizontal em 1280×768;
- Financeiro permanece visível ou oculto exclusivamente conforme o perfil salvo (modo, espaço, menu adaptativo ou navegação personalizada);
- preferências por usuário, permissões, atalhos e favoritos foram preservados;
- 69 testes focados e 3 subtestes aprovados, incluindo Caixa e Migração;
- suíte completa definitiva: 1088 testes e 22 subtestes aprovados;
- `compileall`, smoke não visual de `main.py` no perfil TESTE e `git diff --check` aprovados;
- conversor de Migração não foi alterado por esta frente; nenhuma produção foi gerada.

## Checkpoint 42.26 — Fornecedores em Compras e atualizações por revisão

- Compras ganhou acesso direto `Fornecedores`, reutilizando exclusivamente `abrir_cadastros_auxiliares()` no tipo oficial `fornecedor`;
- Produtos preserva o seletor original de marcas, fornecedores e unidades;
- pedido sem fornecedor oferece abrir o cadastro e retoma o pedido com nova consulta ao repositório após fechar;
- acesso direto respeita a permissão de criação em Compras e não cria tabela, formulário ou regra paralela;
- `REVISAO.txt` permite aplicar R7, R8 etc. sobre a mesma versão 2.5.1;
- atualizador existente preserva validação de hashes, snapshot, backup, reinício, diagnóstico e rollback;
- gerador de pacote encontra `build_output/dist` e cria ZIP em `build_output/updates`, sem executar Inno Setup;
- conversor e migração `.nabimig` não foram alterados por esta frente.

## Checkpoint 42.27 — importador `.nabimig` integrado à Migração existente

- a Migração Fase 2 foi preservada integralmente e passou a compartilhar uma área rolável com a nova seção `.nabimig`;
- seleção, validação, contagens, origem, SHA-256, avisos e categorias ficam visíveis antes de qualquer escrita;
- seleção parcial inclui automaticamente Clientes/Produtos/Vendas exigidos pelas dependências;
- backup obrigatório, cancelamento antes da transação, `BEGIN IMMEDIATE`, rollback e `foreign_key_check` permanecem centralizados no serviço oficial;
- clientes demonstrativos são identificados somente por `ficticio=1`; demos sem vínculo podem ser removidos e os vinculados são preservados e relatados;
- relatório técnico final não inclui documentos, telefones ou dados pessoais;
- pacote real R6 validado duas vezes em banco temporário: 87 clientes, 198 produtos, 12 fornecedores, 277 vendas, 317 itens e 32 contas abertas;
- saldo aberto validado em R$ 10.171,00, sem duplicação, com dois backups e zero violações de chave estrangeira;
- 21 testes focados aprovados e 1 teste opcional ignorado sem a variável do pacote real;
- suíte completa: 1.099 testes, 22 subtestes e 1 teste opcional ignorado;
- `compileall`, smoke de `main.py` e `git diff --check` aprovados; nenhum banco real, conversor ou impressora foi acessado.

## Checkpoint 42.28 / R7 TESTE — atualização incremental e instalador

- revisão interna avançada de R6 para R7;
- corrigida a execução direta do comando `build_windows.py update`, que não encontrava os controladores do projeto;
- auditoria de segredos passou a permitir somente o arquivo público `_internal/certifi/cacert.pem`, mantendo chaves, certificados privados e bancos bloqueados;
- 32 testes do atualizador e 23 testes do empacotamento aprovados nas validações focadas;
- pacote incremental: `build_output/updates/NabiCode_ATUALIZACAO_2_5_1_R7.zip`;
- SHA-256 do pacote incremental: `6CEDA9DCC2F7820E2C92706039BEF2E91E3B631BA12962FD94006398F66914B1`;
- instalador alternativo: `build_output/installer/NabiCode_2.5.1_TESTE_R7_Setup.exe`;
- SHA-256 do instalador: `00B9A0003D58760781AC3D7DFD3BA0DF90A12826D8C2444FA70DDFD535E757C1`;
- smoke empacotado e validações do pipeline aprovados; instalador não foi executado.

## Checkpoint 42.29 / R8 TESTE — fluxo único de migração

- a aba Migração usa um único seletor para `.sql` e `.nabimig` e reconhece automaticamente o formato;
- o mesmo fluxo apresenta `1. Analisar`, `2. Preparar` e `3. Migrar` para os dois formatos;
- opções específicas do `.nabimig` aparecem somente depois da preparação, eliminando a seção duplicada permanente;
- Migração Fase 2 antiga permanece disponível quando o arquivo selecionado é `.sql`;
- relatório usa automaticamente a origem correspondente ao formato selecionado;
- pacote financeiro R6 recuperado e restaurado na Área de Trabalho após o original ter sido apagado com a pasta do Conversor;
- pacote restaurado validado duas vezes em banco temporário, com saldo de R$ 10.171,00 e sem duplicação;
- revisão interna avançada para R8.

## Checkpoint 42.30 / R9 TESTE — galeria de cupons térmicos

- criada galeria offline com 20 modelos visuais originais para cupom térmico 80 mm;
- estilos incluem molduras, ticket, blocos, faixas, cantos, linhas, retrô, premium e `Nabi exclusivo`;
- nenhum modelo externo ou arquivo com licença incerta foi incorporado;
- o conteúdo financeiro permanece intocado; somente separadores, títulos, bordas e alinhamento mudam;
- configuração foi simplificada para modelo visual, fonte e tamanho da fonte;
- prévia aplica o modelo escolhido antes de qualquer impressão;
- renderização respeita 42 caracteres e codificação CP850 do pipeline oficial;
- corte automático continua único e nenhuma impressora física foi usada;
- 40 testes focados aprovados;
- revisão interna avançada para R9.

## Checkpoint 42.31 / R10 TESTE — migração responsiva em segundo plano

- causa raiz removida nos dois formatos: análise, preparação e importação `.sql` não executam mais trabalho pesado na thread gráfica;
- validação e importação `.nabimig` informam progresso real para backup, categorias, integridade e confirmação da transação;
- o painel libera o bloqueio modal enquanto uma tarefa longa está ativa, permitindo continuar usando o NabiCode;
- a interface permanece responsável por todos os componentes gráficos; a thread de trabalho não acessa Tk;
- migrações longas exibem etapa e percentual, e a conclusão ou falha é avisada pela interface;
- backup obrigatório, transação única, rollback, cancelamento e verificação de chaves estrangeiras foram preservados;
- 30 testes focados aprovados;
- suíte: 1.087 testes e 22 subtestes aprovados na execução principal; os 19 testes impedidos pela pasta temporária do Windows foram repetidos isoladamente e os 57 testes dos arquivos afetados foram aprovados;
- `compileall` e `git diff --check` aprovados; somente bancos temporários e perfil TESTE foram usados.
- distribuição Windows recompilada com Python 3.14.7 e PyInstaller 6.21.0;
- 49 testes focados aprovados novamente no ambiente canônico de build;
- instalador de teste: `build_output/installer/NabiCode_2.5.1_TESTE_R10_Setup.exe`;
- SHA-256 do instalador R10: `A82567505ED2804099694BFEF7A2588F674E44D63B3BA08BDE38B81004DCF4D3`;
- revisão `10` confirmada dentro da distribuição; instalador não foi executado.

## Checkpoint 42.32 / R11 TESTE — instalador único e desinstalação segura

- o instalador oficial reconhece a identidade legada isolada `NabiCode TESTE R6` e remove seu desinstalador e atalhos conhecidos antes da atualização;
- todas as revisões atuais continuam compartilhando o AppId e a pasta oficiais, impedindo novas instalações paralelas;
- quando o NabiCode já está instalado, o mesmo assistente oferece atualizar/reparar, desinstalar mantendo dados ou desinstalar apagando os dados do usuário;
- apagar tudo exige confirmação adicional e alcança somente `{userappdata}\NabiCode`;
- desinstalações silenciosas, inclusive as usadas por atualização, sempre preservam banco, backups e configurações;
- 22 testes focados do instalador e 29 testes conjuntos de instalador/atualizador aprovados;
- instalador unificado: `build_output/installer/NabiCode_2.5.1_TESTE_R11_Setup.exe`;
- SHA-256 do instalador: `8F6E2B5DE371E97352A6FDE0E51B8C97A7DFC1F0CBA5862789EF2899E40FF577`;
- atualização incremental: `build_output/updates/NabiCode_ATUALIZACAO_2_5_1_R11.zip`;
- SHA-256 da atualização: `D0B025AB56DE65649381DDFCE0C566C75D4694B0BC379238571680522DE6C292`;
- revisão `11` confirmada na distribuição; nenhum instalador ou desinstalador foi executado.

## Checkpoint 42.33 / R12 TESTE — exclusão total protegida e versões antigas

- `Apagar tudo` exige confirmação destrutiva e a mesma senha mestra validada pelo `SecurityService`;
- o instalador armazena somente o SHA-256 já oficial da senha mestra, nunca a credencial em texto aberto;
- a limpeza cobre exclusivamente as raízes NabiCode em AppData Roaming, AppData Local, ProgramData e pastas registradas de instalações oficiais/antigas;
- versões antigas são descobertas pelo cadastro de programas do Windows, exigindo nome NabiCode e publicador NabiCode; não existe varredura destrutiva genérica do disco;
- atualizar/reparar e desinstalar silenciosamente continuam preservando banco, backups, relatórios e configurações;
- 37 testes focados de segurança, autenticação e instalador aprovados;
- instalador R12 compilado com sucesso pelo Inno Setup 6.7.3 após validação real do código Pascal;
- instalador: `build_output/installer/NabiCode_2.5.1_TESTE_R12_Setup.exe`;
- SHA-256: `B853FFF200898EB17EE649ACFCF163550D3223CFE4E3A6BD5B640B371205E264`;
- atualização incremental: `build_output/updates/NabiCode_ATUALIZACAO_2_5_1_R12.zip`;
- SHA-256 da atualização: `8D72872E53542EC386C63191ABEDA2F80125B5431325D52B73D05F107CEAA2F2`;
- revisão `12` confirmada na distribuição; nenhuma exclusão foi executada automaticamente.

## Checkpoint 42.34 / R13 TESTE — aviso de atualização recuperável

- selecionar um pacote da mesma revisão passa a informar `Nenhuma atualização necessária`, sem classificar a situação como falha crítica;
- a caixa nativa bloqueante foi substituída por uma janela NabiCode normal e não modal;
- o aviso oferece `Minimizar`, `Copiar detalhes` e `Fechar`, permanecendo recuperável durante captura de tela ou troca de aplicativo;
- fechar ou minimizar o aviso não oculta nem encerra a janela principal;
- 15 testes focados de atualização aprovados e `compileall` validado;
- revisão interna avançada para R13.
- instalador: `build_output/installer/NabiCode_2.5.1_TESTE_R13_Setup.exe`;
- SHA-256 do instalador: `66B978DF153583D9D0B14386C67DBAC29D64734D232AE13DF60BEBAC6E1AB474`;
- atualização incremental: `build_output/updates/NabiCode_ATUALIZACAO_2_5_1_R13.zip`;
- SHA-256 da atualização: `6AD8BB522F453736DB8EBD888AE95E6BB7FF2C455DC7C0DD10E726A40906DFBC`.

## Checkpoint 42.35 / R14 TESTE — identidade visual 3D oficial

- o conceito aprovado `N Nebulosa` foi reconstruído como ícone 3D de alta definição;
- a fonte visual oficial foi preservada em `build_tools/resources/NabiCode.png`;
- o recurso Windows `NabiCode.ico` contém nove escalas, de 16 a 256 pixels;
- executável, instalador, atalhos e entrada de desinstalação passam a compartilhar a mesma identidade;
- teste de regressão valida as assinaturas PNG/ICO e a presença das nove escalas antes do empacotamento;
- inspeção visual aprovada em 16, 24, 32, 48, 64, 128 e 256 pixels;
- suíte completa: 1.112 testes, 22 subtestes e 1 teste opcional ignorado;
- nenhum programa, banco real ou impressora física foi aberto durante a validação.

## Checkpoint 42.36 / R15 TESTE — ícone 3D sem placa de fundo

- removidos na fonte visual o quadrado escuro, a moldura e o fundo do ícone R14;
- o `N` 3D passou a usar transparência alfa real, como um glifo independente na barra do Windows;
- preservadas as nove escalas do recurso ICO e a identidade azul/ciano aprovada;
- teste de regressão exige PNG RGBA para impedir a reintrodução de uma placa opaca;
- inspeção visual aprovada sobre fundo roxo em 16, 24, 32, 48, 64, 128 e 256 pixels.
- 32 testes focados de empacotamento aprovados; suíte completa da R14, sem alteração funcional posterior, permanece com 1.112 testes e 22 subtestes aprovados.

## Checkpoint 42.37 / R16 TESTE — ícone explícito nos atalhos

- confirmado por extração do recurso PE que o executável R15 já continha o `N` transparente correto;
- causa do atalho divergente removida: os atalhos dependiam da extração automática do executável e do cache de ícones do Windows;
- a distribuição passa a carregar `NabiCode.ico` também como arquivo independente na raiz;
- atalhos do Menu Iniciar e da Área de Trabalho apontam explicitamente para esse recurso;
- a entrada de desinstalação usa o mesmo ícone oficial;
- validação da distribuição reprova pacotes sem o arquivo independente;
- 32 testes focados de build e instalador aprovados.

## Checkpoint 42.38 — perfis fiscais completos para a Bahia

- configuração fiscal passa a oferecer MEI, Simples Nacional, Simples com excesso de sublimite, Lucro Presumido e Lucro Real;
- o CRT correspondente permanece centralizado no serviço fiscal: 1, 2 ou 3 conforme o regime selecionado;
- NF-e modelo 55 e NFC-e modelo 65 podem ser habilitadas juntas ou separadamente;
- o usuário escolhe o documento padrão e o serviço impede selecionar como padrão um modelo desabilitado;
- instalações novas iniciam com UF Bahia, ambos os modelos habilitados e NFC-e 65 como padrão;
- campo livre de regime foi substituído por opções determinísticas, evitando grafias inválidas;
- nenhuma emissão real, certificado ou endpoint de produção foi utilizado;
- 55 testes fiscais focados e 5 subtestes aprovados.

## Checkpoint 42.39 — roteamento oficial SEFAZ-BA e SVRS

- NF-e 55 passa a resolver automaticamente os sete serviços oficiais da SEFAZ-BA em homologação e produção;
- NFC-e 65 passa a usar os sete serviços da SVRS indicados oficialmente pela SEFAZ-BA;
- autorização, retorno de recibo, consulta, eventos, inutilização, status e cadastro ficam separados por modelo e ambiente;
- consulta e eventos identificam o modelo diretamente pela chave de acesso;
- fila de transmissão preserva o modelo de cada documento ao escolher o serviço;
- endpoint manual existente continua tendo prioridade como substituição administrativa explícita;
- modelos desabilitados são recusados antes de qualquer comunicação;
- nenhuma requisição externa, certificado ou emissão real foi utilizada nos testes;
- 58 testes fiscais focados e 5 subtestes aprovados.

## Checkpoint 42.40 — QR Code 3.00 da NFC-e Bahia

- NFC-e online passa a gerar automaticamente o grupo `infNFeSupl` com QR Code versão 3 e URL de consulta da Bahia;
- conforme o Manual DANFE NFC-e/QR Code 6.0, o leiaute v3 não usa CSC, evitando armazenar um segredo fiscal que deixou de ser necessário;
- contingência offline monta os sete parâmetros fiscais e assina sua concatenação em RSA-SHA1 com o mesmo certificado A1 da NFC-e;
- chave, modelo, ambiente, data, total e identificação do destinatário são validados antes da geração;
- autorização da NFC-e atualiza o QR Code imediatamente antes da assinatura XML, preservando a chave privada somente em memória;
- NF-e modelo 55 permanece sem o grupo suplementar exclusivo da NFC-e;
- 57 testes fiscais e 5 subtestes aprovados, incluindo verificação criptográfica da assinatura com certificado temporário;
- `compileall` e `git diff --check` aprovados; nenhuma comunicação com SEFAZ, banco real, certificado real ou impressora foi utilizada.

## Checkpoint 42.41 — documentos fiscais, contabilidade e devolução assistida

- confirmada a estrutura fiscal oficial em `AppData/Roaming/NabiCode/fiscal`, separada por ambiente, modelo e chave de acesso;
- a Central fiscal passou a mostrar a pasta física, buscar por chave, protocolo, status, modelo ou ambiente e abrir os arquivos pelo abridor isolado;
- `Documentos fiscais` tornou-se uma ação direta da pesquisa global, preservando a permissão fiscal de consulta;
- exportação por período gera ZIP atômico para a contabilidade com XML processado autorizado, eventos aceitos e manifesto SHA-256;
- documentos de homologação ficam excluídos por padrão e só entram mediante escolha explícita;
- arquivos e eventos são revalidados contra os hashes persistidos antes de entrar no pacote;
- a devolução reutiliza chave, participantes, produtos, quantidades, valores, NCM, CEST e tributação do XML original;
- CFOP de devolução passa a ser sugerido por item a partir do CFOP e ICMS importados, cobrindo operações internas, interestaduais e substituição tributária;
- removida a pergunta repetitiva de CFOP produto por produto; o usuário escolhe itens/quantidades e confirma um resumo único antes da transmissão;
- arquitetura comparada com os projetos abertos NFePHP/SPED-NFe e PyNFe, sem incorporar código ou dependência licenciada de terceiros;
- 101 testes focados e 5 subtestes aprovados; suíte completa com 1.125 testes e 27 subtestes aprovados, com 1 teste opcional ignorado;
- `compileall` e `git diff --check` aprovados;
- somente bancos, certificados e arquivos temporários de teste foram utilizados.

## Checkpoint 42.42 — cardápio visual do menu técnico

- o seletor textual estreito do Painel Administrativo foi substituído por 12 cartões visuais;
- cada cartão apresenta ícone, área e descrição curta para Licença, Banco, Backup, Atualizações, restauração, diagnóstico, migração, demonstração, ferramentas, sistema, segurança e suporte;
- grade de quatro colunas e três linhas preserva legibilidade em 1280×768;
- cartão ativo recebe destaque sem recriar telas ou duplicar comandos;
- todas as rotinas, permissões técnicas e proteções anteriores foram preservadas;
- 31 testes focados aprovados; `compileall` e `git diff --check` aprovados;
- nenhuma janela do programa foi aberta durante a validação automática.

## Checkpoint 42.43 — CRT 4 oficial do MEI

- corrigido na fonte o enquadramento do MEI de CRT 1 para CRT 4, conforme regra oficial da NF-e;
- validações do perfil e do documento passam a aceitar exclusivamente os CRT 1, 2, 3 e 4;
- teste de regressão impede que o perfil MEI volte a gerar CRT 1;
- 59 testes fiscais aprovados com `NABICODE_PROFILE=TESTE`;
- nenhum banco real, certificado real, endpoint fiscal, interface ou impressora foi utilizado.

## Checkpoint 42.44 — retenção fiscal e modo protegido

- documentos e eventos fiscais deixam de ser descartados silenciosamente dos índices após 1.000 e 2.000 registros;
- a Central Fiscal e a exportação contábil continuam alcançando todo o histórico persistido;
- trocar o modo Comercial/Fiscal exige a senha mestra antes de qualquer configuração ser gravada;
- habilitar ou desabilitar a emissão fiscal oficial também exige a senha mestra e restaura o controle ao valor persistido quando a autenticação é cancelada ou recusada;
- proteção implementada nos pontos únicos de persistência, sem sobreposição visual ou regra duplicada por tela;
- 69 testes focados e `compileall` aprovados com `NABICODE_PROFILE=TESTE`;
- nenhum banco real, certificado real, endpoint fiscal, interface ou impressora foi utilizado.

## Checkpoint 42.45 — transporte fiscal restrito a destinos oficiais

- endpoints fiscais manuais passam a exigir HTTPS, porta 443 e domínio governamental `.gov.br`;
- URLs com usuário/senha, consulta, fragmento, porta alternativa ou domínio externo são recusadas antes da persistência;
- configurações inseguras gravadas por versões anteriores também são bloqueadas quando o endpoint é resolvido, antes do uso do certificado A1;
- domínios reservados `.invalid` permanecem aceitos exclusivamente como destinos inertes dos testes automatizados;
- 62 testes fiscais e `compileall` aprovados com `NABICODE_PROFILE=TESTE`, sem conexão externa.

## Checkpoint 42.46 — instalação guiada do certificado A1

- a configuração fiscal ganhou um cartão único para arquivo, senha, ações e resultado da validação do certificado A1;
- fluxo orientado em duas etapas: selecionar `.pfx/.p12` e verificar imediatamente antes de salvar;
- resultado informa documento identificado e validade, distinguindo senha ausente, arquivo inválido e certificado vencido;
- senha permanece somente em memória e nunca é persistida;
- o cartão reutiliza `FiscalService.inspect_certificate()`, sem criar instalador, cópia ou regra paralela de certificado;
- 72 testes focados e `compileall` aprovados com `NABICODE_PROFILE=TESTE`.

## Checkpoint 42.47 — schemas oficiais e validação obrigatória

- incorporados do Portal Nacional os schemas NF-e/NFC-e `010e v1.02` e eventos/serviços `010d v1.03`, publicados em 10/07/2026;
- origem, URLs e hashes SHA-256 dos ZIP oficiais registrados junto aos recursos, sem alterar os tipos publicados pela Fazenda;
- executável de desenvolvimento e build Windows passam a carregar os mesmos schemas versionados;
- NF-e/NFC-e assinada, consulta, lote de eventos e inutilização são validados localmente antes de qualquer transmissão;
- corrigida na fonte a ausência de `indIEDest`, detectada pelo schema oficial no destinatário;
- eventos deixam de transmitir o elemento isolado e passam a usar o lote oficial `envEvento`;
- validação usa parser sem rede e sem resolução de entidades externas;
- 100 testes fiscais, de devolução e empacotamento aprovados; `compileall` e `git diff --check` aprovados;
- nenhum endpoint, certificado real, banco real, interface ou impressora foi utilizado.

## Checkpoint 42.48 — base para CNPJ alfanumérico

- CNPJ fiscal deixou de passar pelo normalizador exclusivamente numérico e agora preserva as 12 posições alfanuméricas e os dois dígitos verificadores numéricos;
- chave de acesso preserva o CNPJ alfanumérico e calcula o dígito pelo valor oficial `ASCII - 48`, sem alterar os campos que continuam estritamente numéricos;
- configuração, certificado, XML, eventos, consultas, fila e índices usam normalizadores fiscais dedicados, eliminando a remoção silenciosa de letras;
- o exemplo oficial `12.ABC.345/01DE-35` foi coberto por regressão, incluindo persistência e geração de chave com 44 caracteres;
- 65 testes do serviço fiscal aprovados com `NABICODE_PROFILE=TESTE`;
- nenhum endpoint, certificado real, banco real, interface ou impressora foi utilizado.

## Checkpoint 42.49 — dígitos oficiais do CNPJ alfanumérico

- validação do CNPJ passou a calcular os dois dígitos verificadores pelo módulo 11 e pelo valor oficial de cada caractere (`ASCII - 48`);
- o exemplo oficial `12.ABC.345/01DE-35` é aceito e a variante com dígito final incorreto é recusada;
- chave fiscal ganhou validação estrutural compatível com o schema oficial: seis dígitos, doze posições alfanuméricas e vinte e seis dígitos;
- perfil do emitente, geração de chave, XML autorizado e inutilização rejeitam identificadores inconsistentes antes da transmissão;
- 66 testes do serviço fiscal aprovados com `NABICODE_PROFILE=TESTE`.

## Checkpoint 42.50 — homologação técnica da frente fiscal

- suíte completa executada com o executor oficial de testes após instalar `pytest` somente no ambiente local de desenvolvimento;
- resultado final: 1.137 testes e 32 subtestes aprovados, com 1 teste opcional ignorado;
- o único aviso pertence ao cache local do pytest e não afeta runtime, dados, empacotamento ou instalação;
- `pip check` confirmou todas as dependências satisfeitas;
- validações fiscais focadas, devolução, schemas oficiais, certificado A1, documentos, exportação contábil e empacotamento permanecem aprovados;
- nenhum programa foi aberto, nenhuma impressora foi acionada e nenhum banco, certificado ou endpoint real foi utilizado;
- geração de instalador de produção permanece fora deste checkpoint.

## Checkpoint 42.51 — produção fiscal bloqueada até IBS/CBS

- auditoria final confrontou o emissor com as orientações oficiais de 2026 e com as NT 2025.002/2026.002 publicadas pelo Portal NF-e;
- o schema vigente contém os grupos IBS/CBS, mas o NabiCode ainda não possui matriz tributária suficiente para calculá-los legalmente por produto e operação;
- emissão real em `PRODUCAO` passa a falhar de forma explícita antes de certificado ou rede, impedindo documento fiscal incompleto;
- ambiente `HOMOLOGACAO` permanece disponível para demonstração, configuração, certificado A1 e validação técnica;
- a liberação futura de produção depende da implementação da matriz IBS/CBS e de homologação fiscal com os dados tributários da empresa;
- teste de regressão impede remoção acidental deste bloqueio de segurança.

## Checkpoint 42.52 — tributação regular IBS/CBS

- implementado o primeiro grupo RTC completo para tributação regular, CST `000`, com classificação tributária, base, IBS estadual, IBS municipal e CBS por item;
- valores são calculados com `Decimal`, arredondamento monetário explícito e rejeição de bases ou alíquotas fora do intervalo válido;
- totais `IBSCBSTot` e `vNFTot` são derivados dos itens, incluindo os campos zerados obrigatórios de diferimento, devolução e crédito presumido;
- estrutura comparada com o schema `010e v1.02` e com a implementação aberta NFePHP/SPED-NFe, sem incorporar código PHP ao NabiCode;
- XML de regressão foi assinado com certificado temporário e aprovado integralmente pelo schema oficial local;
- nenhuma alíquota ou classificação é inventada: os valores precisam vir da ficha fiscal rastreável do produto ou do XML de origem.

## Checkpoint 42.53 — ficha IBS/CBS reaproveitada do XML

- leitor oficial de NF-e passou a extrair CST, classificação tributária, base e alíquotas de IBS estadual, IBS municipal e CBS;
- o schema de produtos recebeu campos próprios para a ficha RTC, criados automaticamente também em bancos existentes;
- criar ou atualizar produto pela importação preserva a tributação recebida no XML dentro da mesma transação;
- XML sem IBS/CBS não apaga uma ficha fiscal já existente e XML com códigos estruturalmente inválidos é recusado antes do commit;
- a automação elimina o preenchimento imposto a imposto nas vendas seguintes sem tentar deduzir tributação somente pelo CNPJ;
- 25 testes de XML, importação, atomicidade, exclusão e schema aprovados em bancos temporários.

## Checkpoint 42.54 — carrinho convertido automaticamente em itens fiscais

- criado um único preparador fiscal que consulta todos os produtos do carrinho em uma leitura e monta os itens da NF-e/NFC-e;
- NCM, CFOP, CST, classificação e alíquotas IBS/CBS são obtidos da ficha persistida, sem digitação durante a venda;
- o prefixo do CFOP é ajustado de forma determinística para operação interna, interestadual ou exterior, preservando a natureza cadastrada;
- produto inexistente, item avulso ou ficha incompleta interrompe somente a emissão e apresenta uma orientação simples para importar a NF-e ou revisar o cadastro;
- testes confirmam preenchimento automático e bloqueio preventivo sem qualquer gravação parcial.

## Checkpoint 42.55 — Fase 1 da ficha fiscal completa

- produtos passam a ter uma ficha fiscal estruturada com origem, CSOSN, CST ICMS, alíquotas de ICMS, CST e alíquotas de PIS/COFINS, CEST e os campos IBS/CBS já existentes;
- o cadastro oficial de produtos edita e persiste a ficha no mesmo fluxo, sem tabela ou formulário fiscal paralelo;
- a emissão valida a ficha conforme o regime do emitente e gera os grupos suportados de ICMS, PIS e COFINS, incluindo substituição tributária com CEST obrigatório;
- a importação de NF-e preserva NCM, CEST, origem e IBS/CBS, mas não copia o CFOP da operação do fornecedor como se fosse automaticamente o CFOP da futura venda;
- o certificado A1 configurado é reutilizado nas notas seguintes e sua senha permanece somente na memória até o NabiCode ser fechado;
- a troca do arquivo de certificado invalida imediatamente a senha anterior mantida na sessão;
- produção continua bloqueada até a homologação fiscal das regras e classificações aplicáveis ao contribuinte;
- 210 testes focados e 10 subtestes aprovados;
- suíte completa: 1.182 testes e 32 subtestes aprovados, com 1 teste opcional ignorado;
- `compileall` e `git diff --check` aprovados com `NABICODE_PROFILE=TESTE`;
- nenhum programa, banco real, certificado real, endpoint fiscal ou impressora foi utilizado.

## Checkpoint 42.56 — Fase 2 da decisão fiscal de venda

- criado um resolvedor único para a natureza e o CFOP das vendas, sem regras duplicadas no PDV ou no gerador XML;
- a matriz inicial cobre venda de produção própria, revenda e operações com substituição tributária nos destinos oficialmente correspondentes;
- corrigida a conversão indevida de `5405` para o CFOP inexistente `6405`: a correspondência interestadual oficial usada é `6404`;
- exportações e naturezas fora da matriz segura são bloqueadas com orientação para cadastrar regra aprovada pela contabilidade, em vez de trocar o primeiro dígito silenciosamente;
- CRT 4 do MEI passa a gerar o grupo ICMS do Simples Nacional, corrigindo o enquadramento anterior como regime normal;
- para MEI, a automação de venda fica limitada a CFOP `5102/6102` e CSOSN `102`, `300` ou `400`, conforme a restrição oficial vigente;
- a matriz foi confrontada com a tabela oficial de CFOP da Receita Federal e com a orientação oficial específica para MEI;
- validação focada: 115 testes e 10 subtestes aprovados;
- integração fiscal/produtos/schema: 314 testes e 13 subtestes aprovados;
- suíte completa: 1.194 testes e 32 subtestes aprovados, com 1 teste opcional ignorado;
- nenhum programa, banco real, certificado real, endpoint fiscal ou impressora foi utilizado.

## Checkpoint 42.57 — Fase 3 da matriz comercial IBS/CBS

- criado um resolvedor central de IBS/CBS separado do gerador XML e da interface;
- venda nacional regular aceita somente CST `000` com classificação `000001` e alíquotas rastreáveis da ficha do produto;
- exportação de venda passa automaticamente para CST `410`, classificação `410004` e alíquotas zeradas, sem exigir que o operador conheça a classificação;
- o XML de exportação gera o grupo IBS/CBS sem incidência sem `gIBSCBS` e foi aprovado pelo schema oficial local;
- destinatário no exterior passa a exigir e gerar `idEstrangeiro` na ordem prevista pelo leiaute oficial;
- classificações de redução, bonificação, doação, monofasia, crédito presumido e outros regimes especiais continuam bloqueadas até possuírem fluxo e dados próprios;
- a matriz foi confrontada com o Informe Técnico 2025.002 v1.60 e com as tabelas vigentes publicadas no Portal Nacional da NF-e em 23/06/2026;
- validação focada: 121 testes e 10 subtestes aprovados;
- suíte completa: 1.200 testes e 32 subtestes aprovados, com 1 teste opcional ignorado;
- `compileall` e `git diff --check` aprovados com `NABICODE_PROFILE=TESTE`;
- produção permanece bloqueada até homologação contábil e fiscal; nenhum programa, banco real, certificado real, endpoint ou impressora foi utilizado.

## Checkpoint 42.58 — Fase 4 da pré-homologação do catálogo

- criado um serviço único e somente leitura para conferir todas as mercadorias fiscais ativas antes do uso no PDV;
- cada produto é validado pela mesma ficha, matriz de operação e regra IBS/CBS usadas na emissão real;
- a auditoria cobre simultaneamente vendas internas e interestaduais e detecta NCM, CFOP, origem, CEST, ICMS, PIS, COFINS e IBS/CBS incompletos ou incompatíveis;
- serviços, produtos inativos e itens marcados para não participar do XML ficam corretamente fora da conferência;
- a configuração fiscal ganhou a ação `Verificar catálogo fiscal`, que apresenta quantidade pronta e até doze pendências legíveis, sem criar uma tela ou cadastro paralelo;
- nenhum dado fiscal é preenchido, substituído ou corrigido automaticamente pela auditoria;
- MEI e substituição tributária passam pelas mesmas restrições seguras das Fases 1 a 3;
- validação focada: 128 testes e 10 subtestes aprovados;
- suíte completa: 1.205 testes e 32 subtestes aprovados, com 1 teste opcional ignorado;
- `compileall` e `git diff --check` aprovados com `NABICODE_PROFILE=TESTE`;
- nenhum programa, banco real, certificado real, endpoint fiscal ou impressora foi utilizado.

## Checkpoint 42.59 — Fase 5 da correção fiscal assistida

- a lista de pendências da pré-homologação oferece abrir diretamente o primeiro produto bloqueado;
- a correção usa exclusivamente o cadastro oficial de produtos e abre a aba `Fiscal`, sem segundo formulário, tabela ou regra de gravação;
- após salvar o produto, o fluxo retorna à configuração fiscal para permitir nova conferência do catálogo;
- o usuário corrige um produto por vez, preservando decisão humana e rastreabilidade em vez de alterações tributárias em massa;
- o estado de edição do produto passa a incluir NCM, CEST, CFOP, origem, ICMS, PIS, COFINS e IBS/CBS;
- fechar um cadastro com alteração fiscal não salva agora aciona a mesma proteção contra perda de dados dos demais campos;
- validação focada: 63 testes aprovados;
- suíte completa: 1.206 testes e 32 subtestes aprovados, com 1 teste opcional ignorado;
- `compileall` e `git diff --check` aprovados com `NABICODE_PROFILE=TESTE`;
- nenhum programa, banco real, certificado real, endpoint fiscal ou impressora foi utilizado.

## Checkpoint 42.60 — Fase 6 do pré-voo fiscal local

- criada uma verificação única de prontidão que combina configuração, catálogo, certificado, identidade do emitente, geração, assinatura e schema oficial;
- o pré-voo usa uma mercadoria já aprovada pelo catálogo para montar um XML determinístico de homologação sem gravar documento, reservar numeração ou acessar a SEFAZ;
- o CNPJ do certificado é comparado ao emitente configurado e certificados expirados, inválidos ou incompatíveis bloqueiam o resultado;
- o resultado apresenta modelo, quantidade pronta, documento do certificado e impressão digital SHA-256 do XML temporário;
- corrigida na fonte a NFC-e anônima, que não deve criar um grupo `dest` sem CPF, CNPJ ou identificação estrangeira;
- corrigida a ordem estrutural da assinatura quando existe `infNFeSupl`, conforme o schema oficial da NFC-e;
- teste real de integração gera certificado A1 temporário, assina o XML, valida o schema e confirma que a fila de transmissão permanece vazia;
- validação focada: 110 testes e 10 subtestes aprovados;
- suíte completa: 1.210 testes e 32 subtestes aprovados, com 1 teste opcional ignorado;
- nenhum programa, banco real, certificado da Área de Trabalho, endpoint fiscal ou impressora foi utilizado.
