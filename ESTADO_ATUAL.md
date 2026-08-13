# NabiCode — Estado Atual

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
