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

## Checkpoint 42.61 — Fase 7 da homologação local multimodelo

- o pré-voo fiscal passa a validar todos os modelos habilitados, em vez de conferir somente o documento definido como padrão;
- instalações com NF-e 55 e NFC-e 65 geram, assinam e validam localmente um XML independente para cada modelo;
- instalações com apenas um modelo habilitado continuam respeitando exatamente essa configuração;
- se qualquer modelo reprovar a configuração, o conjunto é interrompido antes da geração e a mensagem identifica explicitamente NF-e ou NFC-e;
- o resultado apresenta os modelos aprovados e uma impressão digital SHA-256 separada para cada XML temporário;
- o teste de integração com certificado A1 temporário comprova os dois modelos no schema oficial e confirma a fila de transmissão vazia;
- validação focada: 107 testes e 10 subtestes aprovados;
- suíte completa: 1.212 testes e 32 subtestes aprovados, com 1 teste opcional ignorado;
- nenhum programa, banco real, certificado da Área de Trabalho, endpoint fiscal ou impressora foi utilizado.

## Checkpoint 42.62 — primeira configuração e ações fiscais oficiais

- a configuração fiscal pode ser preenchida a partir de uma NF-e/NFC-e antiga da própria empresa, desde que o XML possua protocolo autorizado `cStat 100`;
- o leitor oficial reaproveitado extrai CNPJ, razão social, IE, CRT, endereço, município/IBGE, UF, CEP, modelo e série, sem importar produtos ou gravar automaticamente;
- CRT 3 não é convertido silenciosamente em Lucro Presumido ou Real e exige confirmação contábil;
- séries de venda da NF-e 55 e NFC-e 65 passam a ser configuradas e validadas separadamente entre 0 e 999;
- a configuração do emitente ganhou inscrição municipal e aproveita apenas nome/CNPJ gerais como sugestões revisáveis;
- o certificado A1 passa a rejeitar extensão diferente de `.pfx/.p12`, arquivo vazio ou maior que 10 MB e apresenta erro específico para senha/PKCS#12 inválido;
- CNPJ, razão social extraída, validade, dias restantes e alerta nos 30 dias anteriores ao vencimento ficam disponíveis sem expor a senha;
- a Central Fiscal ganhou ações explícitas para baixar o XML autorizado, enviar CC-e e inutilizar uma faixa de numeração usando os serviços fiscais existentes;
- cancelamento, CC-e e inutilização continuam sujeitos a permissão, senha do A1, validação local e retorno efetivo da SEFAZ;
- validação focada: 143 testes e 10 subtestes aprovados;
- suíte completa: 1.219 testes e 32 subtestes aprovados, com 1 teste opcional ignorado;
- nenhum programa, banco real, certificado da Área de Trabalho, endpoint fiscal ou impressora foi utilizado.

## Checkpoint 42.63 — cofre local do A1 e status SEFAZ

- criado um protetor de segredos baseado na DPAPI do Windows, vinculado ao usuário atual e sem chave fixa no código ou no banco;
- a instalação segura valida validade e CNPJ antes de copiar o A1 para a área fiscal gerenciada;
- o `.pfx` permanece criptografado pelo PKCS#12 e a senha é armazenada separadamente em conteúdo protegido pela DPAPI;
- a senha protegida pode ser recuperada automaticamente nas próximas execuções pelo mesmo usuário do Windows;
- remover ou substituir o A1 apaga somente a cópia e a credencial gerenciadas, preservando o arquivo original escolhido pelo cliente;
- a tela oferece visualização restrita a razão social, CNPJ e validade, além da remoção protegida por senha mestra;
- implementada consulta direta de `consStatServ` para NF-e/NFC-e, sem emitir documento, reservar numeração ou gravar retorno fiscal;
- o botão `Testar conexão com a SEFAZ` executa a consulta fora da thread visual e diferencia serviço em operação de resposta indisponível ou erro de comunicação;
- validação focada: 100 testes e 10 subtestes aprovados, incluindo round-trip real da DPAPI com segredo temporário;
- suíte completa: 1.222 testes e 32 subtestes aprovados, com 1 teste opcional ignorado;
- nenhum programa, banco real, certificado da Área de Trabalho, endpoint fiscal ou impressora foi utilizado.

## Checkpoint 42.64 — numeração fiscal inicial auditada

- empresas vindas de outro emissor podem definir o próximo número por ambiente, modelo e série sem gerar documento;
- a operação exige senha mestra e registra usuário, data, escopo e número inicial na própria estrutura transacional de numeração;
- cada escopo só pode ser inicializado uma vez e qualquer tentativa posterior é bloqueada;
- séries ficam limitadas a 0–999 e números ao intervalo oficial de 1–999999999;
- NF-e, NFC-e, homologação e produção mantêm sequências totalmente independentes;
- a primeira reserva após a inicialização usa exatamente o número informado;
- lacunas posteriores não podem ser criadas pela configuração e devem passar pela inutilização oficial;
- validação focada: 101 testes e 10 subtestes aprovados;
- suíte completa: 1.224 testes e 32 subtestes aprovados, com 1 teste opcional ignorado;
- nenhum programa, banco real, certificado real, endpoint fiscal ou impressora foi utilizado.

## Checkpoint 42.65 — relatório fiscal para a contabilidade

- a Central Fiscal passa a exportar relatório CSV por período, ambiente e situação dos documentos;
- os valores bruto, base de ICMS, ICMS, IPI, PIS, COFINS, IBS e CBS são derivados dos XMLs fiscais preservados, sem duplicar dados calculados;
- o relatório inclui chave, modelo, número, série, destinatário, protocolo e documentos cancelados;
- faixas de numeração inutilizadas com aceite fiscal passam a integrar o relatório;
- corrigida na fonte a persistência dos metadados da inutilização, que antes existiam apenas no resultado em memória;
- a gravação do CSV usa arquivo temporário e substituição atômica, com codificação compatível com planilhas brasileiras;
- os comandos de exportação contábil foram distribuídos em uma linha própria para preservar acesso em 1280×768;
- validação focada: 102 testes e 10 subtestes aprovados;
- suíte completa: 1.225 testes e 32 subtestes aprovados, com 1 teste opcional ignorado;
- nenhum programa, banco real, certificado real, endpoint fiscal ou impressora foi utilizado.

## Checkpoint 42.66 — pré-visualização fiscal sem consumir numeração

- o PDV ganhou `PRÉ-VISUALIZAR FISCAL` tanto na janela independente quanto na área integrada de vendas;
- a conferência usa o mesmo cadastro do cliente, destino, produtos, CFOP e perfis tributários da emissão oficial;
- o total exibido é produzido pelo próprio gerador fiscal e inclui os cálculos vigentes do documento;
- a prévia identifica modelo, série, ambiente, cliente e itens e traz marca explícita de documento sem validade fiscal;
- a operação não chama a reserva de numeração, não persiste rascunho, não assina e não transmite à SEFAZ;
- a resolução do cliente atual foi centralizada para evitar divergência entre prévia e finalização da venda;
- validação focada: 114 testes e 10 subtestes aprovados;
- suíte completa: 1.227 testes e 32 subtestes aprovados, com 1 teste opcional ignorado;
- nenhum programa, banco real, certificado real, endpoint fiscal ou impressora foi utilizado.

## Checkpoint 42.67 — recuperação segura de recibos pendentes

- a Central Fiscal ganhou a ação `Consultar recibo` para vendas já recebidas pela SEFAZ e ainda em processamento;
- a consulta manual antecipa somente a próxima tentativa do recibo existente e não reenvia o XML de autorização;
- itens sem recibo, concluídos ou cancelados são bloqueados com mensagem específica;
- usuário e instante da solicitação manual ficam registrados na fila fiscal;
- a consulta continua em segundo plano e mantém o NabiCode utilizável;
- validação focada: 104 testes e 10 subtestes aprovados;
- suíte completa: 1.228 testes e 32 subtestes aprovados, com 1 teste opcional ignorado;
- nenhum programa, banco real, certificado real, endpoint fiscal ou impressora foi utilizado.

## Checkpoint 42.68 — retransmissão em lote das contingências

- a Central Fiscal ganhou `Retransmitir contingências` para não exigir o reenvio nota por nota;
- o lote identifica a contingência pelo `tpEmis` do próprio XML e considera somente NFC-e modelo 65 ainda não concluídas;
- notas normais, documentos autorizados, cancelados e outras operações fiscais não entram no lote;
- documentos que já possuem recibo continuam pela consulta do recibo, sem reenviar a autorização;
- o processador aceita uma seleção explícita de IDs, garantindo que outros itens pendentes não sejam transmitidos pelo botão de contingência;
- usuário e instante da solicitação em lote ficam registrados em cada item selecionado;
- o processamento continua em segundo plano e o botão informa quando não existe contingência pendente;
- validação focada: 106 testes e 10 subtestes aprovados;
- suíte completa: 1.230 testes e 32 subtestes aprovados, com 1 teste opcional ignorado;
- nenhum programa, banco real, certificado real, endpoint fiscal ou impressora foi utilizado.

## Checkpoint 42.69 — auditoria de prontidão comercial fiscal

- realizada auditoria consolidada entre requisitos prometidos, serviços reais, interface e testes;
- criado `AUDITORIA_COMERCIAL_FISCAL.md` com cobertura implementada, bloqueadores de produção e funções ainda ausentes;
- identificado que o PDF simples de conferência era anunciado incorretamente como DANFE;
- o gerador e todos os acessos visuais foram reclassificados para `Espelho fiscal — não é DANFE`, preservando a utilidade sem representar um leiaute oficial inexistente;
- o mesmo ajuste foi aplicado ao fluxo de devoluções, sem alterar XML, autorização, estoque ou regras tributárias;
- DANFE/DANFE NFC-e oficial, contingência completa no PDV, catálogos NCM/CEST/IBPT, consulta cadastral, DF-e, e-mail, NFS-e, cadeia ICP-Brasil e matrizes tributárias especiais permanecem bloqueadores explícitos;
- o bloqueio de produção foi preservado: não houve liberação fiscal artificial ou uso de alíquotas presumidas;
- validação focada: 141 testes e 10 subtestes aprovados;
- suíte completa: 1.230 testes e 32 subtestes aprovados, com 1 teste opcional ignorado;
- `compileall` e `git diff --check` aprovados;
- nenhum programa, banco real, certificado real, endpoint fiscal ou impressora foi utilizado.

## Checkpoint 42.70 — DANFE oficial da NF-e modelo 55

- confirmado no Portal Nacional o MOC 7.0 e o manual técnico vigente do DANFE;
- integrado o BrazilFiscalReport 1.0.1 como dependência separada LGPL-3.0, com aviso de terceiros e versão travada no build Windows;
- o DANFE oficial é gerado somente a partir de NF-e modelo 55 assinada, autorizada e com chave/protocolo coerentes;
- a gravação usa arquivo temporário, valida cabeçalho PDF e substituição atômica;
- a Central Fiscal e as devoluções autorizadas passam a usar o gerador oficial;
- NFC-e modelo 65 é recusada por este gerador e permanece destinada ao leiaute térmico próprio da próxima fase;
- o antigo PDF simples continua disponível apenas internamente como espelho fiscal e não é apresentado como DANFE;
- PyInstaller coleta os módulos do gerador e do código de barras, e o manifesto canônico declara a nova dependência;
- validação focada: 168 testes e 10 subtestes aprovados;
- suíte completa: 1.232 testes e 32 subtestes aprovados, com 1 teste opcional ignorado;
- `compileall` e `git diff --check` aprovados;
- nenhum programa, banco real, certificado real, endpoint fiscal ou impressora foi utilizado.

## Checkpoint 42.71 — DANFE NFC-e térmico de 80 mm

- criado o documento auxiliar próprio da NFC-e modelo 65, separado do DANFE A4 da NF-e;
- o PDF térmico apresenta emitente, itens, totais, pagamentos, consumidor, chave, QR Code e protocolo;
- XML autorizado somente é aceito quando assinatura, chave, protocolo, modelo e situação fiscal são coerentes;
- rascunhos normais sem autorização são recusados, evitando documento auxiliar fiscal indevido;
- a Central Fiscal escolhe automaticamente o gerador correto para os modelos 55 e 65;
- documentos de homologação recebem avisos explícitos de ambiente de testes e ausência de valor fiscal;
- a saída é gravada por arquivo temporário e substituição atômica, sem acionar impressora;
- validação focada: 145 testes e 10 subtestes aprovados;
- suíte completa: 1.234 testes e 32 subtestes aprovados, com 1 teste opcional ignorado;
- `compileall` e `git diff --check` aprovados;
- nenhum programa, banco real, certificado real, endpoint fiscal ou impressora foi utilizado.

## Checkpoint 42.72 — contingência offline completa no PDV

- o PDV ganhou ativação explícita e reversível da contingência, com justificativa mínima e indicação visual enquanto estiver ativa;
- a venda nasce como NFC-e modelo 65 em `tpEmis=9`, antes da persistência comercial, evitando alteração tardia de documento;
- a chave é recalculada, o QR Code offline é assinado com o A1 e o XML recebe assinatura XMLDSig antes de entrar na fila;
- a fila reconhece e valida o XML previamente assinado, sem inserir outro QR Code ou assinar novamente;
- o DANFE NFC-e de contingência é gerado automaticamente em PDF, sem acionar impressora física;
- cada contingência registra prazo operacional de 24 horas e marca atraso sem bloquear uma tentativa posterior de transmissão;
- a contingência é desativada automaticamente após concluir a venda e documentos normais continuam no fluxo anterior;
- produção continua bloqueada e nenhuma indisponibilidade simulada ativa contingência silenciosamente;
- validação focada: 135 testes e 10 subtestes aprovados;
- suíte completa: 1.239 testes e 32 subtestes aprovados, com 1 teste opcional ignorado;
- `compileall` e `git diff --check` aprovados;
- nenhum programa, banco real, certificado real, endpoint fiscal ou impressora foi utilizado.

## Checkpoint 42.73 — catálogo NCM oficial e gratuito

- integrada a fonte pública JSON do Sistema Classif da Receita Federal, sem provedor comercial;
- incluído snapshot oficial vigente em 18/08/2026, Resolução Gecex nº 926/2026, com 10.515 códigos finais;
- a tela fiscal do produto pesquisa por código ou descrição, inclusive sem depender de acentos;
- a atualização ocorre em segundo plano, valida tamanho, JSON, estrutura e quantidade mínima antes de substituir o cache;
- gravação da atualização é atômica e uma resposta incompleta não destrói a última tabela válida;
- cache corrompido recua automaticamente para o snapshot oficial incluído no instalador;
- o instalador passa a transportar o catálogo e sua declaração de origem;
- consulta comercial de CNPJ/IE permanece fora desta fase; a configuração gratuita usa XML autorizado próprio e certificado A1;
- validação focada: 21 testes aprovados;
- suíte completa: 1.243 testes e 32 subtestes aprovados, com 1 teste opcional ignorado;
- um teste antigo de recuperação de lock oscilou sob carga, passou isoladamente e a suíte completa repetida foi aprovada;
- `compileall` e `git diff --check` aprovados;
- nenhum banco real, certificado real, endpoint fiscal de emissão ou impressora foi utilizado.

## Checkpoint 42.74 — referência CEST oficial consolidada

- integrada a publicação consolidada do Convênio ICMS 142/18 diretamente do CONFAZ, sem provedor pago;
- incluído snapshot oficial com 1.049 códigos consolidados a partir de 1.591 ocorrências e redações históricas;
- quando um CEST aparece mais de uma vez, o catálogo preserva a última redação na ordem da publicação oficial;
- pesquisa disponível por CEST, descrição ou compatibilidade textual com o NCM informado;
- selecionar um resultado exige confirmação explícita da descrição e da regra fiscal da empresa;
- coincidência de NCM nunca ativa substituição tributária automaticamente, pois segmento, descrição e legislação da UF também são determinantes;
- atualização roda em segundo plano, valida integralidade e substitui o cache atomicamente;
- cache inválido recua para o snapshot incluído no instalador;
- validação focada: 25 testes aprovados;
- suíte completa: 1.247 testes e 32 subtestes aprovados, com 1 teste opcional ignorado;
- `compileall` e `git diff --check` aprovados;
- nenhum banco real, certificado real, endpoint fiscal de emissão ou impressora foi utilizado.

## Checkpoint 42.75 — cadeia pública de confiança ICP-Brasil

- integrado o pacote público oficial de autoridades certificadoras do ITI, com 180 certificados;
- o arquivo é conferido por SHA-512 em toda leitura, usando o hash publicado no próprio repositório oficial;
- a extração ocorre em memória com limites de tamanho, quantidade e proteção contra caminhos inseguros;
- a cadeia do A1 agora verifica assinaturas, validade, restrições de AC e término em uma AC Raiz oficial;
- abrir corretamente com a senha deixou de ser apresentado como prova suficiente de confiança;
- a tela de configuração informa separadamente validade do A1 e confiança da cadeia ICP-Brasil;
- o pré-voo fiscal reprova certificados cuja cadeia não alcance uma raiz oficial;
- o instalador passa a transportar somente o catálogo público; nenhuma chave privada ou senha é incluída;
- revogação por CRL/OCSP permanece uma etapa online separada e não foi declarada artificialmente como concluída;
- validação focada: 115 testes e 10 subtestes aprovados;
- suíte completa: 1.252 testes e 32 subtestes aprovados, com 1 teste opcional ignorado;
- nenhum banco real, certificado real, endpoint fiscal de emissão ou impressora foi utilizado.

## Checkpoint 42.76 — consulta segura de revogação por CRL

- certificados da cadeia passam a usar os endereços CRL assinados presentes no próprio certificado;
- cada CRL baixada tem tamanho limitado, emissor e assinatura conferidos e janela de validade exigida;
- certificado listado como revogado é bloqueado e uma CRL vencida, ausente ou inválida falha de forma fechada;
- a checagem cobre o A1 e as autoridades intermediárias até a raiz confiável;
- transmissão direta em produção exige tanto cadeia ICP-Brasil válida quanto situação de revogação confirmada;
- a configuração fiscal ganhou consulta manual de revogação em segundo plano, sem congelar a interface;
- homologação e testes locais continuam sem acessar serviços reais automaticamente;
- validação focada: 121 testes e 10 subtestes aprovados;
- suíte completa: 1.256 testes e 32 subtestes aprovados, com 1 teste opcional ignorado;
- nenhum banco real, certificado real, endpoint fiscal de emissão ou impressora foi utilizado.

## Checkpoint 42.77 — envio seguro de documentos fiscais por e-mail

- criada fila persistente para envio do XML autorizado junto ao DANFE correspondente ao modelo 55 ou 65;
- o destinatário é sugerido pelo próprio XML validado e o usuário confirma explicitamente antes do envio;
- credencial SMTP usa DPAPI e nunca é gravada na configuração pública, fila, Git ou anexos;
- configuração e remoção da credencial exigem senha mestra;
- TLS e SSL são suportados, com senha de aplicativo e limite total de 15 MB por mensagem;
- falhas ficam registradas na fila para nova tentativa sem marcar o documento como enviado;
- geração do DANFE e comunicação SMTP rodam fora da interface gráfica;
- a Central Fiscal ganhou configuração e envio direto sem acionar impressora física;
- validação focada: 120 testes e 10 subtestes aprovados;
- suíte completa: 1.262 testes e 32 subtestes aprovados, com 1 teste opcional ignorado;
- nenhum servidor SMTP, e-mail, banco real, certificado real, endpoint fiscal ou impressora foi utilizado.

## Checkpoint 42.78 — guarda e restauração de documentos fiscais

- o backup diário e manual passa a criar, em cada destino configurado, um pacote fiscal ao lado do banco;
- XMLs autorizados e DANFEs são preservados com manifesto, tamanho e SHA-256 individual;
- certificado A1, senha protegida, fila de e-mail e outros segredos são excluídos do pacote;
- o manifesto registra a data mínima de retenção de cinco anos sem apagar automaticamente arquivos antigos;
- a restauração valida integralmente o pacote antes de gravar qualquer documento;
- arquivo existente idêntico é preservado e conflito com conteúdo diferente bloqueia toda a restauração;
- o Menu Técnico ganhou restauração específica de XMLs e DANFEs sem misturar a restauração do banco;
- testes utilizam somente banco e documentos fiscais temporários.
- validação focada: 15 testes aprovados;
- suíte completa: 1.263 testes e 32 subtestes aprovados, com 1 teste opcional ignorado;
- `compileall` e `git diff --check` aprovados.

## Checkpoint 42.79 — Distribuição DF-e e manifestação do destinatário

- implementado o serviço nacional `NFeDistribuicaoDFe` no leiaute 1.01 e pacote oficial v1.04;
- consumo incremental guarda o último NSU e nunca o regride após respostas antigas;
- documentos Base64/GZip têm quantidade e tamanho limitados, XML seguro e schemas conhecidos;
- cada XML recebido é persistido atomicamente e indexado com SHA-256;
- consulta usa o A1 do interessado somente após cadeia ICP-Brasil e CRL válidas;
- Central Fiscal lista os DF-e recebidos e consulta o Ambiente Nacional em segundo plano;
- implementadas Ciência, Confirmação, Desconhecimento e Operação não Realizada;
- Operação não Realizada exige justificativa e manifestações conclusivas duplicadas são bloqueadas;
- a interface informa o prazo conclusivo vigente de 90 dias a partir de 01/06/2026;
- validação focada: 123 testes e 10 subtestes aprovados, incluindo 9 testes próprios de DF-e;
- suíte completa: 1.272 testes e 32 subtestes aprovados, com 1 teste opcional ignorado;
- `compileall` e `git diff --check` aprovados;
- nenhum DF-e, certificado, CNPJ, endpoint ou banco real foi utilizado nos testes.

## Checkpoint 42.80 — duplicação controlada de nota para pré-venda

- documento autorizado pode gerar uma nova pré-venda editável no fluxo oficial do PDV;
- somente código e quantidade são reaproveitados da nota original;
- produto, nome, preço, estoque e perfil fiscal são relidos do cadastro atual;
- número, série, chave, protocolo, pagamentos e tributos antigos nunca são copiados;
- produto removido/inativo bloqueia a duplicação e exige correção consciente;
- cliente é reaproveitado somente quando CPF/CNPJ corresponde ao cadastro atual;
- uma segunda pré-venda aberta para a mesma nota é bloqueada;
- o usuário recebe aviso explícito antes da criação e revisa a pré-venda no PDV.
- validação focada: 116 testes e 10 subtestes aprovados;
- suíte completa: 1.273 testes e 32 subtestes aprovados, com 1 teste opcional ignorado;
- `compileall` e `git diff --check` aprovados.

## Checkpoint 42.81 / R17 TESTE — prévia consolidada do instalador

- revisão interna elevada para 17 e conferida dentro da distribuição reconstruída;
- instalador de teste consolidado com todas as alterações até o Checkpoint 42.80;
- reconstrução completa feita com Python 3.14.7, PyInstaller 6.21.0 e Inno Setup 6.7.3;
- dependências fiscais empacotadas incluem BrazilFiscalReport 1.0.1 e pygame-ce 2.5.7;
- 31 testes focados de build, dependências fiscais e atualização aprovados;
- `compileall` e `git diff --check` aprovados;
- instalador: `build_output/installer/NabiCode_2.5.1_TESTE_R17_Setup.exe`;
- SHA-256: `2C411E936EC2DAFC643D2F4E226E6BA881457E4C781428C4A54CEF2610AAC6C6`;
- o instalador não foi executado e nenhum banco, certificado, endpoint fiscal ou impressora real foi utilizado.

## Checkpoint 42.82 — importação XML e prontidão fiscal determinística

- a importação de NF-e passa a preencher simultaneamente `nome` e a coluna legada obrigatória `descricao`, eliminando a reversão em bancos atualizados de versões antigas;
- código, descrição, código de barras, unidade, fator, custo, margem e preço dos produtos novos podem ser conferidos antes da gravação atômica;
- o preenchimento fiscal por XML identifica se a empresa configurada é emitente ou destinatária e rejeita documentos de terceiros;
- uma NF-e de compra usa os dados do destinatário como dados próprios, evitando copiar silenciosamente o fornecedor para a empresa usuária;
- o modo operacional Fiscal tornou-se a fonte única da obrigatoriedade fiscal no PDV;
- a prontidão fiscal é validada antes de solicitar pagamento, impedindo venda fiscal sem configuração completa;
- a configuração fiscal permanece salva ao alternar temporariamente para o modo comercial;
- Central Fiscal, configuração fiscal e assistente XML passam a abrir preparados e maximizados, com minimizar nativo e sem captura global da interface;
- modo Balcão/Touch foi movido para Configurações, liberando espaço para todas as ações do PDV;
- a busca de clientes mostra somente número e nome, sem o rótulo repetitivo `Ficha` nem identificadores duplicados;
- validação focada: 145 testes e 10 subtestes aprovados;
- suíte completa: 1.277 testes e 32 subtestes aprovados, com 1 teste opcional ignorado;
- nenhum banco real, certificado real, endpoint fiscal de emissão ou impressora foi utilizado.

## Checkpoint 42.83 — dashboard guiada para lançamento de NF-e de compra

- a conferência do XML foi reorganizada como fluxo visual em quatro etapas: identificação, empresa, produtos e revisão;
- cartões mantêm número, emissão, fornecedor, CNPJ, situação cadastral, total e quantidade de itens visíveis;
- a edição de cada produto foi dividida em Vínculo, Cadastro e Estoque e preço, reduzindo a sobrecarga sem esconder dados;
- o sistema abre automaticamente a seção que precisa da atenção do usuário;
- itens pendentes, novos e vinculados recebem estados visuais distintos na lista;
- ações foram renomeadas em linguagem direta e a barra inferior permanece acessível;
- a captura modal residual foi removida, preservando minimizar e alternar janelas;
- o desenho foi baseado no detalhamento por linha usado pelo ERPNext, na conferência em rascunho do Odoo e nas recomendações de formulário responsivo e revelação progressiva da Microsoft;
- validação focada: 20 testes aprovados;
- `compileall` e `git diff --check` aprovados;
- nenhum banco real, certificado real, endpoint fiscal de emissão ou impressora foi utilizado.

## Checkpoint 42.84 — conferência fiscal do produto antes da entrada

- NCM, CEST, origem da mercadoria e código de barras podem ser conferidos e corrigidos na própria ficha do item antes da importação;
- NCM e CEST corrigidos seguem na mesma transação atômica de criação ou atualização do cadastro oficial;
- validações locais exigem 8 dígitos para NCM, 7 para CEST e origem entre 0 e 8;
- o CFOP do fornecedor é exibido como referência da compra, mas nunca é gravado como CFOP da futura venda;
- a origem fiscal recebida ou corrigida continua alimentando a ficha oficial sem criar cadastro paralelo;
- validação focada: 19 testes aprovados;
- `compileall` e `git diff --check` aprovados;
- nenhum banco real, certificado real, endpoint fiscal de emissão ou impressora foi utilizado.

## Checkpoint 42.85 — tributos da compra visíveis por produto

- cada item da NF-e ganhou uma aba compacta de Tributos ao lado de Vínculo, Cadastro e Estoque;
- ICMS, IPI, PIS, COFINS e IBS/CBS lidos do XML ficam visíveis com bases, alíquotas, valores, CST/CSOSN e classificação disponíveis;
- a interface identifica esses números como valores informados pelo fornecedor e não como regra automática da venda;
- os nomes curtos das quatro abas preservam acesso e legibilidade em 1280×768;
- nenhuma alíquota foi inferida, corrigida silenciosamente ou aplicada ao documento de saída;
- validação focada: 19 testes aprovados;
- `compileall` e `git diff --check` aprovados;
- nenhum banco real, certificado real, endpoint fiscal de emissão ou impressora foi utilizado.

## Checkpoint 42.86 — validação integral da frente de lançamento de notas

- toda a frente de importação XML, prontidão fiscal, dashboard guiada e conferência tributária foi validada em conjunto;
- um teste de recuperação de lock revelou prazo frágil de inicialização de subprocesso sob carga no Windows;
- a verificação funcional foi preservada e somente a espera de inicialização passou de 5 para 15 segundos;
- o teste isolado confirmou a recuperação correta após encerramento abrupto;
- suíte completa final: 1.279 testes e 32 subtestes aprovados, com 1 teste opcional ignorado;
- nenhum banco real, certificado real, endpoint fiscal de emissão ou impressora foi utilizado.

## Checkpoint 42.87 / R18 TESTE — atualização incremental da frente fiscal

- revisão interna elevada de 17 para 18;
- distribuição Windows reconstruída com as correções de importação e a nova dashboard de lançamento de notas;
- smoke empacotado, inspeção da árvore e geração do manifesto foram aprovados pelo pipeline oficial;
- pacote incremental criado para atualizar instalações 2.5.1 sem reinstalação completa;
- manifesto interno confirma produto NabiCode, versão 2.5.1, revisão 18 e 1.365 arquivos;
- 48 testes de atualização, empacotamento, integração e versão, além de 2 subtestes, foram aprovados;
- pacote: `build_output/updates/NabiCode_ATUALIZACAO_2_5_1_R18.zip`;
- tamanho: 72.336.026 bytes;
- SHA-256: `0B7EFC573756D302BD998035FA0270EA6B62728893EF31B8F7E06527F7AD421A`;
- o pacote não foi aplicado e nenhum banco, certificado, endpoint fiscal, instalador existente ou impressora real foi utilizado.

## Checkpoint 42.88 / R18 TESTE — instalador consolidado para instalações novas

- instalador completo reconstruído a partir da mesma distribuição validada usada pela atualização R18;
- Inno Setup 6.7.3 concluiu a compilação e o pipeline validou conteúdo, versão, evidências e integridade;
- a pasta de saída contém somente um executável de instalação R18, evitando nomes concorrentes da mesma revisão;
- instalador: `build_output/installer/NabiCode_2.5.1_TESTE_R18_Setup.exe`;
- tamanho: 55.529.665 bytes;
- SHA-256: `04E4264F2C4432B209CA95D63E95F0D12F19B8B0B192B58710D26C3E0D35D251`;
- o instalador não foi executado e nenhum programa instalado, banco, certificado, endpoint fiscal ou impressora real foi utilizado.

## Checkpoint 42.89 / R19 TESTE — instalador substitui revisões anteriores

- revisão interna elevada de 18 para 19;
- a detecção de instalações NabiCode agora cobre registros do Windows de 64 bits, 32 bits e instalações por usuário;
- versões antigas identificadas oficialmente são desinstaladas antes da nova instalação, preservando os dados durante atualização;
- atalhos antigos do NabiCode no menu Iniciar e na Área de Trabalho são removidos e somente o atalho oficial é recriado;
- o instalador não apaga executáveis de instalação guardados pelo usuário em Downloads, Área de Trabalho ou outras pastas pessoais;
- a preparação offline foi corrigida para calcular hashes apenas dos pacotes `.whl`, sem tentar incluir o próprio manifesto;
- suíte completa: 1.287 testes e 32 subtestes aprovados, com 1 teste opcional ignorado;
- instalador: `build_output/installer/NabiCode_2.5.1_TESTE_R19_Setup.exe`;
- tamanho: 55.544.045 bytes;
- SHA-256: `2B744B79D4A580CC74A51D7F0B6EEAF0321F1036483F61568DDAC9E1919A15C5`;
- o instalador não foi executado e nenhum programa instalado, banco, certificado, endpoint fiscal ou impressora real foi utilizado.

## Checkpoint 42.90 — cadastro de produtos por XML acessível no modo comercial

- a causa do desaparecimento foi removida: o acesso à importação estava condicionado ao modo Fiscal;
- Produtos agora exibe sempre o botão `Cadastrar produtos via XML`, inclusive no modo normal;
- o mesmo comando também permanece disponível na pesquisa global fora do modo Fiscal;
- o assistente oficial existente continua conferindo e cadastrando os produtos novos antes da importação atômica da nota, sem cadastro paralelo;
- histórico de notas importadas e NF-e de devolução permanecem exclusivos do modo Fiscal;
- 28 testes focados, `compileall` e `git diff --check` aprovados;
- nenhum programa, banco real, certificado, endpoint fiscal ou impressora foi aberto ou utilizado.

## Checkpoint 42.91 — Modo de Teste Fiscal protegido

- a homologação passou a ser apresentada como `TESTE FISCAL — HOMOLOGAÇÃO (SEM VALOR FISCAL)`;
- produção aparece explicitamente bloqueada nesta versão, sem induzir o usuário a acreditar que já pode emitir documentos reais;
- o PDV identifica permanentemente o ambiente de homologação como `FISCAL TESTE — SEM VALOR FISCAL`;
- trocar entre teste e produção exige senha mestra antes de salvar a configuração;
- cancelar a senha restaura imediatamente a seleção anterior e não altera o ambiente persistido;
- numeração e configuração continuam usando internamente os códigos oficiais `HOMOLOGACAO` e `PRODUCAO`;
- 134 testes focados e 10 subtestes, `compileall` e `git diff --check` aprovados;
- nenhuma UF adicional foi liberada e nenhum programa, banco real, certificado, endpoint fiscal ou impressora foi utilizado.

## Checkpoint 42.92 — IPI de saída configurável e sem presunção

- a ficha oficial do produto ganhou CST de IPI de saída, alíquota e código de enquadramento legal;
- bancos existentes recebem os novos campos pela inicialização idempotente, sem apagar cadastros;
- somente CSTs de saída suportados são aceitos e qualquer IPI configurado exige enquadramento explícito de três dígitos;
- CST tributado gera `IPITrib`, enquanto CST não tributado gera `IPINT`;
- valor do IPI é calculado com `Decimal`, totalizado em `ICMSTot/vIPI` e compõe corretamente o valor da NF-e;
- produto sem IPI configurado preserva exatamente o comportamento anterior;
- consultas toleram esquemas legados durante migração, sem inventar valor fiscal;
- 153 testes focados e 10 subtestes, `compileall` e `git diff --check` aprovados;
- produção e UFs adicionais continuam bloqueadas; nenhum banco real, certificado, endpoint fiscal ou impressora foi utilizado.

## Checkpoint 42.93 — matriz tributária parametrizada da Bahia

- criado cadastro persistente de regras tributárias por regime, prefixo NCM, CEST e UF de destino;
- a matriz guarda ICMS, redução de base, MVA/ST, FCP-ST, DIFAL interno/interestadual, FCP do destino e código de benefício;
- nenhuma alíquota nasce preenchida automaticamente e toda regra exige responsável e data de aprovação contábil;
- regras de ICMS-ST exigem CEST explícito e todas as alíquotas são validadas entre 0 e 100%;
- regras de emitente diferente da Bahia são recusadas nesta fase;
- a resolução prefere a combinação mais específica de NCM e destino, sem tratar apenas o NCM como prova tributária;
- desativação preserva o histórico e impede imediatamente o uso da regra em novas operações;
- banco elevado ao schema 18 para criar a matriz com índice de resolução;
- 143 testes focados e 10 subtestes, `compileall` e `git diff --check` aprovados;
- a matriz ainda não está ligada ao XML de venda; produção permanece bloqueada até essa integração e homologação real.

## Checkpoint 42.94 — regras da Bahia integradas ao documento fiscal

- a matriz tributária aprovada passa a ser resolvida na preparação oficial dos itens por regime, NCM/CEST e UF de destino;
- ICMS-ST do Simples Nacional (CSOSN 201/202/203), MVA, FCP-ST, crédito do Simples e DIFAL passam a compor o XML e os totais nos grupos previstos pelo XSD;
- CST/CSOSN sem gerador homologado é recusado explicitamente, sem conversão silenciosa para uma regra parecida;
- os grupos de DIFAL foram posicionados na ordem exigida pelo esquema oficial, depois de PIS/COFINS;
- 131 testes fiscais e 10 subtestes foram aprovados nesse bloco;
- produção permanece bloqueada e nenhum banco real, certificado, endpoint fiscal ou impressora foi utilizado.

## Checkpoint 42.95 — painel controlado da matriz tributária da Bahia

- a configuração fiscal ganhou o acesso `Regras tributárias da Bahia`;
- inclusão e desativação exigem senha mestra; regras antigas são desativadas sem apagar o histórico;
- cada regra exige responsável e data de aprovação contábil e a tela informa que o sistema não presume alíquotas;
- somente CST/CSOSN que possuem gerador XML validado nesta versão podem ser cadastrados;
- suíte completa: 1.303 testes aprovados, 1 ignorado e 32 subtestes aprovados em `NABICODE_PROFILE=TESTE`;
- fechamento comercial em produção ainda depende de homologação real com credenciais da empresa, validação do contador e autorizações da SEFAZ Bahia; esse bloqueio permanece intencional.
