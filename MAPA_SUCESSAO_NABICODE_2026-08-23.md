# MAPA DE SUCESSÃO — NABICODE

Data de referência: 23/08/2026  
Finalidade: permitir que futuras conversas continuem o trabalho sem reiniciar o projeto, perder decisões ou confundir o NabiCode Legacy com a migração Qt.

## Painel de acompanhamento

Legenda:

- `[x]` concluído e com evidência registrada;
- `[~]` em andamento ou aguardando auditoria/homologação;
- `[ ]` pendente;
- `[!]` bloqueado para distribuição/release.

### Base e processo

- [x] migração do desenvolvimento para o checkout Windows local;
- [x] GitHub/push pelo Windows validado;
- [x] fluxo por bundles abandonado;
- [x] estratégia definida: partes pequenas, commit local, homologação, suíte completa e push autorizado;
- [~] versionar este mapa em commit documental separado;

### Estado atual verificado antes do commit documental

- branch: `homologacao/qt-commercial-2026-08-23`;
- HEAD: `83c72af33b99cd2c92322ecc82cb018f8a92faac`;
- quatro commits locais à frente de `origin/homologacao/qt-commercial-2026-08-23`:
  `4cb4932`, `5586a22`, `2c7dccd` e `83c72af`;
- auditoria automatizada da etapa de Pagamentos aprovada;
- suíte informada da etapa: 180 testes e 306 subtestes aprovados;
- homologação manual no Windows ainda pendente;
- nenhum push desses quatro commits está autorizado neste momento.

### Comercial e Qt

- [x] núcleo comercial desacoplado e serviços principais criados;
- [x] primeira interface PySide6 do PDV;
- [x] MoneyEdit Qt corrigido;
- [x] IDs reais para cliente e produto;
- [x] Consumidor Final pela porta comercial;
- [x] estabilização básica do Enter e proteção contra auto-repeat;
- [x] fluxo Item → Cliente → Finalizar → Pagamentos implementado e corrigido nos commits locais até `83c72af`;
- [~] homologação manual da janela de Pagamentos em andamento no Windows;
- [~] achado manual: separar “Revisar” de “Confirmar venda”; revisão não pode persistir, confirmação explícita finaliza e conduz à opção de impressão;
- [x] checkpoint 2 separou `Revisar` de `Confirmar venda` no commit `85f4ae2`: revisão imutável, invalidação após mudanças, confirmação impossível sem revisão e bloqueio de duplicidade; 109 testes Qt/commercial relacionados e 17 testes finais focados aprovados, além de `compileall` e `git diff --check`;
- [~] alinhar as janelas Qt desse fluxo à aparência e à organização das equivalentes do Legacy, sem transportar regras fiscais ou decisões indevidas para a GUI;
- [x] fronteira atual do PDV usa consulta de produtos e não oferece criação/edição de catálogo;
- [x] produto avulso cria somente item de venda, sem `product_id`, cadastro de produto ou movimentação de estoque;
- [x] checkpoint 1 protege a fronteira de produtos por teste arquitetural no commit `88ca3ff`: `ProductLookupPort` expõe somente `search/get`, e item avulso não chama escrita de catálogo/estoque; 16 testes focados, `compileall` e `git diff --check` aprovados;
- [x] checkpoint 3 implementou pós-venda e comprovantes Qt no commit `8685928`: somente resultado confirmado/consumido libera saída, abrir ou cancelar não imprime, cupom/PDF usam serviços oficiais, PDF é registrado e aberto pelo despachante isolado, ajustes reutilizam o rateio comercial e falhas não repetem a venda; 15 testes focados e 135 testes Qt/commercial relacionados aprovados, além de `compileall` e `git diff --check`;
- [~] homologação manual pendente para aparência, foco e impressão/PDF físicos do pós-venda em perfil TESTE;
- [x] checkpoint 4 completou operações do carrinho no commit `c029dc0`: edição atômica de quantidade/preço/desconto, preço cadastrado protegido sem uma permissão comercial real, preço avulso editável, pagamento/revisão invalidados após mutação válida, F4/F10, duplo clique e Delete com bloqueio de auto-repeat; 27 testes focados e 219 testes Qt/commercial/backend relacionados aprovados, além de `compileall` e `git diff --check`;
- [~] homologação manual pendente para edição, remoção, desconto e atalhos físicos do carrinho;
- [x] Orçamento Qt implementado na branch isolada `codex/orcamento-qt`, criada do merge de integração `abff7d4`: checkpoint Commercial `d25c2bd` e interface Qt `a58279a`;
- [x] o fluxo preserva IDs reais, grava/lista/consome pelo `PDVService` existente, não movimenta estoque/Caixa nem registra venda, oferece prévia/PDF/impressão explícitos e converte para venda somente carregando o carrinho antes do checkout oficial;
- [x] validação automatizada do Orçamento: 51 testes focados Commercial/backend, 73 testes Qt e regressão ampliada de 241 testes Qt/Commercial/backend, todos aprovados; `compileall` e `git diff --check` aprovados;
- [~] homologação manual pendente para F5/F9/Enter/Shift+Enter/Esc físicos, aparência Legacy, impressão e abertura de PDF, substituição de carrinho e conversão explícita de orçamento em venda;
- [x] defeito manual de continuidade do teclado corrigido no commit `b995784`: editar, cancelar edição, remover ou clicar no carrinho restaura a próxima etapa operacional; o clique em Salvar respeita o modo Orçamento; o editor e a prévia possuem foco determinístico, Enter único, Shift+Enter, Esc isolado e bloqueio de auto-repeat;
- [x] regressão da correção: 81 testes Qt e 249 testes Qt/Commercial/backend relacionados aprovados, além de `compileall` e `git diff --check`;
- [~] repetir a homologação física do Orçamento Qt a partir de `b995784`, incluindo as sequências intermediárias que originaram o defeito;
- [x] achado manual subsequente de Pagamentos corrigido no commit `fca7bf1`: após cobrir o total, Enter deixa a área de inclusão e segue para ajustes/revisão; nova inclusão é recusada mesmo por clique; pagamento parcial prepara somente o saldo restante; o indicador passou a `TROCO` em fonte grande;
- [x] regressão dessa correção: 85 testes Qt e 253 testes Qt/Commercial/backend relacionados aprovados, além de `compileall` e `git diff --check`;
- [x] homologação física aprovada pelo operador para a não duplicação por Enter e a legibilidade do indicador grande `TROCO`, na versão de código `fca7bf1`;
- [x] Vendas Suspensas Qt implementadas na branch isolada `codex/vendas-suspensas-qt`: fronteira Commercial no commit `33ddd89` e interface Qt no commit `d22e05d`;
- [x] F6 e clique preservam o carrinho pelo `PDVService` oficial sem checkout, pagamento, estoque, Caixa ou Fiscal; a listagem/reabertura só consome após seleção e confirmação de substituição, mantendo cliente somente por ID real;
- [x] validação automatizada: 58 testes focados Commercial/backend, 96 testes Qt e regressão ampliada de 271 testes Qt/Commercial/backend aprovados; `compileall` e `git diff --check` aprovados;
- [~] homologação manual pendente para F6, clique, foco, substituição recusada, reabertura com/sem cliente, persistência após reinício e continuidade pelo checkout oficial;
- [x] Vendas do dia Qt implementadas na branch isolada `codex/vendas-do-dia-qt`: fronteira Commercial `df6e56c`, janela Qt `aa5a281`, identificação real do cliente `e6dc302` e remoção dos últimos marcadores provisórios `6f371ea`;
- [x] F7 e clique listam vendas e orçamentos do dia, filtram dados reais e oferecem prévia, segunda via e PDF pelos serviços documentais existentes; cancelamento local exige confirmação e reverte pelo `PDVTransactionService` oficial;
- [x] a porta Commercial recusa cancelamento local de qualquer venda vinculada a documento fiscal e orienta uso exclusivo da Central Fiscal, sem importar, chamar ou alterar Fiscal/SEFAZ;
- [x] validação relacionada: 235 testes Qt/Commercial/backend e 335 subtestes aprovados; `compileall` e `git diff --check` aprovados;
- [x] todos os botões comerciais visíveis no PDV Qt possuem ação real; o método e o rótulo provisórios foram removidos;
- [~] suíte integral executada: 1693 testes e 385 subtestes aprovados, 1 ignorado e 3 falhas fora deste checkpoint — duas por ausência local de `brazilfiscalreport` em testes de DANFE e uma asserção textual Legacy antiga que ainda procura `entry_valor_venda.insert` após a migração já existente para `MoneyEntryBehavior.set_value`; nenhuma dessas áreas foi alterada por esta missão;
- [x] homologação manual aprovada para F7 e clique, filtros, Enter em transição única, Shift+Enter, Esc, bloqueio de auto-repeat, prévia, PDF, cancelamento local recusado/confirmado, repetição bloqueada, orçamento não cancelável e persistência após reiniciar; impressão física não foi executada por ausência de impressora;
- [~] bloqueio visual de cancelamento fiscal permanece coberto por testes automatizados, mas não pôde ser reproduzido fisicamente porque o perfil TESTE não possuía venda fiscal na lista;
- [~] homologação física Windows avançada: Pagamentos, Orçamento e Vendas do dia foram aprovados pelo operador; o fluxo físico de produto cadastrado permanece impraticável enquanto o perfil TESTE não possuir produto, a impressão física depende de impressora e o bloqueio visual fiscal depende de venda fiscal segura de homologação;
- [x] substituição automatizada das lacunas físicas disponíveis: 11 cenários específicos de produto cadastrado/ID/Enter/carrinho/Consumidor Final/checkout/estoque foram aprovados e a regressão final relacionada repetiu 235 testes e 335 subtestes sem falhas;
- [x] pesquisa ampliada e acessível de produtos implementada na branch isolada `codex/pdv-pesquisa-acessivel`, partindo de `b5bcaa7`, no commit `5246711`: F2 e botão explícito abrem janela grande, mantendo a seta/lista rápida existente;
- [x] a janela ampliada prioriza somente nome, preço e estoque em fonte/linhas grandes, pesquisa também por código/barras, é somente leitura e seleciona exclusivamente `product_id` real;
- [x] teclado da pesquisa ampliada: Enter na busca move uma etapa para a tabela, Enter na tabela seleciona uma vez, Shift+Enter retorna, Esc cancela e auto-repeat é consumido; seleção retorna ao campo Quantidade;
- [x] filtro do PDV ficou seguro durante montagem/destruição da janela no commit `2f17ab0`, sem mudar regra comercial;
- [x] validação: 139 testes e 2 subtestes focados, depois 269 testes e 338 subtestes Qt/Commercial/backend relacionados, todos aprovados; teste de lock afetado pela execução concorrente foi repetido isoladamente e aprovado;
- [~] homologação manual pendente com catálogo real: legibilidade de nome/preço/estoque, F2, botão, seta/lista rápida, busca por nome/código/barras, Enter/Shift+Enter/Esc, mouse e retorno à Quantidade;
- [x] checkpoint isolado de Clientes Qt implementado em `codex/clientes-qt` no commit `94fb107`: lista administrativa, busca, novo cadastro, edição e ficha/extrato usam somente `CustomerApplicationService`, IDs reais e DTOs imutáveis; a GUI não importa banco, repositório ou Fiscal, e preserva Enter/Shift+Enter/Esc, auto-repeat bloqueado, MoneyEdit e estética do Legacy;
- [x] validação de Clientes Qt: 51 testes e 5 subtestes focados, depois 286 testes e 342 subtestes relacionados aprovados, além de `compileall` e `git diff --check`;
- [~] composição do botão/atalho F3 de Clientes no shell Qt permanece pendente porque `main_qt.py` está temporariamente reservado à trilha IA; o diálogo e a fronteira Commercial estão completos e devem ser conectados somente na composição global, sem duplicar serviços;
- [x] checkpoint isolado de Caixa Qt implementado em `codex/caixa-qt` no commit `e000b8c`: porta `CashApplicationService` fixa terminal e usuário fora da GUI e expõe sessão/resumo tipados; a janela Qt cobre abertura com/sem saldo, suprimento, sangria, valores por forma, histórico e fechamento pelo `CashService` transacional, sem SQL ou persistência direta na interface;
- [x] validação de Caixa Qt: 32 testes focados e regressão relacionada com 243 testes e 341 subtestes aprovados, além de `compileall` e `git diff --check`;
- [~] composição do Caixa no shell Qt permanece pendente porque `main_qt.py`, `ui_qt/app.py` e `pdv_window.py` estão temporariamente reservados à trilha IA; conectar depois pela porta pronta, preservando permissões e identidade real do operador;
- [x] checkpoint isolado de Financeiro Qt implementado em `codex/financeiro-qt` no commit `03e80a8`: contas a receber/pagar separadas, resumo, IDs reais, criação e baixa usam exclusivamente `FinancialQueryService`/`FinancialActionService`, `ActionContext` de UI e confirmação humana explícita; nenhuma persistência direta ou importação Fiscal na GUI;
- [x] validação de Financeiro Qt: 51 testes focados e regressão relacionada com 243 testes e 333 subtestes aprovados, além de `compileall` e `git diff --check`;
- [~] composição do Financeiro no shell Qt permanece pendente enquanto os arquivos de composição estão reservados à trilha IA; checkpoint suspenso limpo por prioridade da edição FICHÁRIO;
- [!] PDV Qt não pode ser tratado como pronto antes dos itens acima.

### Fiscal

- [x] contexto e postura de auditor fiscal adversarial preservados;
- [x] outbox transacional, resposta desconhecida, worker e cancelamento seguro preservados no código existente;
- [ ] auditoria fiscal específica após estabilização comercial/Qt;
- [ ] homologação fiscal real acompanhada;
- [!] produção fiscal continua bloqueada até evidência e autorização próprias.

### Proteção comercial e licenciamento

- [x] implementação antiga auditada;
- [x] 37 testes e 8 subtestes do contrato antigo aprovados;
- [x] lacuna crítica confirmada: Qt não usa o mesmo portão do Legacy;
- [x] decisão de reconstrução integral autorizada;
- [x] arquitetura escolhida: licença offline Ed25519 assinada e vinculada à máquina;
- [x] tolerância normativa de dez dias definida;
- [x] pesquisa primária de referências Ed25519/offline concluída e documentada, sem incorporar nova dependência;
- [x] formato canônico `.nabilic`, schema estrito e assinatura Ed25519 implementados em `8cc9990`;
- [x] portão único para Legacy, Qt e auxiliares implementado em `1254a27` e endurecido em `a242f71`;
- [x] verificador fail-closed, monitoramento contínuo e modo restrito de ativação/diagnóstico/backup/exportação implementados;
- [x] Emissor de Licenças separado do runtime e excluído do pacote distribuído;
- [x] ferramenta externa Qt/CLI concluída com revisão imutável antes da assinatura, renovação, revogação, verificação, prevenção de sobrescrita e empacotamento administrativo separado;
- [ ] proteger e fazer backup da chave privada fora do repositório;
- [x] edição AVALIAÇÃO vinculada à máquina e limitada a trinta dias implementada;
- [x] adulteração, expiração, tolerância, retrocesso de relógio, revogação, rollback e máquina divergente cobertos por testes automatizados;
- [ ] testar cópia física para uma segunda máquina;
- [~] avisos de terceiros e documentação operacional atualizados em `a5b6d97`; revisão jurídica permanece obrigatória;
- [!] nenhuma cópia comercial/de avaliação deve ser entregue antes desse portão.

#### Checkpoint automatizável do Licenciamento V2 — branch `codex/licenciamento-v2`

- base preservada: `b5bcaa7842d65430ee49642cc28516e69c2e3827`;
- núcleo criptográfico: `8cc9990`;
- portão e emissor externo: `1254a27`;
- modo restrito, monitoramento contínuo Legacy/Qt e empacotamento sem emissor: `a242f71`;
- operação, cerimônia e avisos de terceiros: `a5b6d97`;
- contrato histórico de empacotamento preservado em `b846c6c`;
- catálogo público real permanece intencionalmente vazio, portanto o runtime falha fechado;
- nenhuma senha mestre fabrica, prolonga ou restaura licença;
- nenhuma chave privada, PEM ou segredo foi versionado, logado ou incluído no pacote;
- o portão externo impede inicialização de banco, runtime Legacy/Qt e workers quando bloqueado, sem alterar regras, XML, outbox, transmissão ou cancelamento Fiscal/SEFAZ;
- validação focada: 94 testes e 8 subtestes aprovados;
- regressão integral inicial: 1.717 testes e 385 subtestes aprovados, com quatro falhas diagnosticadas; o contrato do empacotamento foi corrigido, o teste textual obsoleto do MoneyEdit foi atualizado e a dependência bloqueada já declarada `BrazilFiscalReport==1.0.1` foi restaurada no Python de testes;
- regressão integral final: 1.721 testes e 385 subtestes aprovados, 1 teste previamente marcado como ignorado e zero falhas;
- pendências físicas/materiais: cerimônia da chave real pelo proprietário, duas cópias privadas criptografadas em locais separados, hash do catálogo público, revisão jurídica, teste físico em segunda máquina, reinstalação/atualização e homologação dos estados visuais no Windows;
- nenhum push realizado.

#### Checkpoint do Emissor externo — branch `codex/emissor-licencas-v2`

- base preservada: `07b7f748ca0b8e2a3e2b44f0083d029992c458a1`;
- ferramenta, workflow seguro, CLI, interface Qt, empacotamento e testes: `35b3b80`;
- operação, cerimônia e pesquisa de proveniência: `84c0d49`;
- a revisão é separada da assinatura; qualquer edição posterior invalida a revisão;
- senha é solicitada somente depois da confirmação e nunca passa pela linha de comando;
- a chave privada precisa corresponder ao catálogo público escolhido; catálogo, licença e segredo não entram no executável;
- emissão, renovação e revogação criam novo arquivo e recusam sobrescrita;
- nenhuma chave privada real foi criada, versionada, logada ou empacotada;
- referências Minisign (ISC), exemplo Keygen (MIT) e PyCA `cryptography` foram avaliadas somente por fontes primárias; nenhum código externo foi copiado e nenhuma nova dependência foi incorporada;
- validação: 15 testes próprios do emissor aprovados; regressão relacionada com 104 testes e 11 subtestes aprovada; `compileall` e `git diff --check` aprovados;
- pendências físicas: cerimônia da chave real, cópias criptografadas e teste de restauração, hash do catálogo, build administrativo reproduzível/SBOM, validação em segunda máquina Windows, revisão de versão da `cryptography` e revisão jurídica;
- nenhum push realizado.

#### Checkpoint do Emissor administrativo para pendrive — branch `codex/emissor-facil-fichario`

- implementação e automação portátil: `8353fc8` — `build: finaliza emissor administrativo portatil`;
- o primeiro smoke do EXE revelou `No module named 'services'`: `licensing.machine`
  dependia transitivamente do agregador excluído pelo spec; a coleta dos
  identificadores Windows foi movida para a própria fronteira de licenciamento,
  preservando o mesmo fingerprint e mantendo serviços comerciais/fiscais fora
  do emissor;
- o build oficial com Python `3.14.7` e PyInstaller `6.21.0` gerou e abriu no
  Windows `NabiCode_Emissor_Licencas_V2.exe`; a janela mostrou solicitação da
  máquina, titular, edição `FICHARIO`, prazos, revisão, assinatura e minimizar;
- emissão, adulteração e verificação foram repetidas somente com chaves
  temporárias de teste; não restou `.pem`, `.key` ou `.nabilic` temporário;
- auditoria de 192 entradas internas do executável não encontrou chave, licença,
  catálogo, `NabiCode-Segredos`, IA, Fiscal/SEFAZ ou entradas do cliente;
- SHA-256 do EXE validado: `6084feddcda87596a730be9a78020d87635290155eae4746448d9b3ed39fa998`;
- pasta gerada para cópia contém somente EXE, `LEIA-ME-EMISSOR.txt` e
  `SHA256SUMS.txt`; SBOM separado registra Python, PyInstaller, PySide6,
  shiboken6 e cryptography, sem caminhos ou segredos;
- validação final: `62 passed`, três cenários explícitos de chaves temporárias
  aprovados, `compileall` e `git diff --check` aprovados;
- a chave privada real e o catálogo externo não foram lidos, copiados,
  versionados nem incorporados; o proprietário deve transportá-los de forma
  criptografada e manter a senha separada;
- o emissor de licenças não substitui a chave permanente de assinatura de
  atualizações; essa chave exige cerimônia, senha e guarda próprias e não foi
  criada neste checkpoint;
- pendências físicas: copiar a pasta gerada para pendrive criptografado,
  conferir os hashes após a cópia e repetir abertura/emissão em segunda máquina
  administrativa controlada; nenhum push realizado.

### IA Nabi

- [x] visão do produto registrada;
- [x] decisão: operar por serviços internos, não por cliques livres na GUI;
- [x] texto primeiro e porta de voz futura definidos;
- [x] confirmação humana, ferramentas tipadas, auditoria e níveis de capacidade definidos;
- [x] a fundação e o painel escritos no commit `bd8d126` foram reunidos ao histórico estabilizado do PDV na branch isolada `codex/integracao-nabi-pdv`, sem alterar as branches de origem e sem push;
- [x] Fase 0 implementa ameaça, permissões vinculadas à sessão, auditoria sem parâmetros sensíveis, schemas fechados, consultas, orquestração textual e adaptador `llama.cpp/llama-server` restrito a loopback;
- [~] Fase 1 possui painel Qt escrito, mascote azul aprovada com transparência real, estados visuais acompanhados de texto/acessibilidade, renderização determinística, voz desativada, botão `Parar Nabi` e proteção contra respostas atrasadas; o painel foi conectado ao shell e ao `main_qt.py` como dock opcional em falha fechada, e a ativação autenticada foi implementada, restando homologação manual na janela real;
- [x] Qwen3-1.7B Instruct em GGUF Q4 é o baseline atual; Qwen3-4B em GGUF Q4 permanece somente candidato posterior se memória e velocidade forem aceitáveis;
- [x] peso e runtime locais foram baixados somente no perfil TESTE, verificados por origem, licença, revisão e SHA-256 e submetidos à homologação física inicial; login Qt real, avaliações prolongadas e decisão de empacotamento continuam pendentes;
- [~] Fase 2: núcleo imutável `1d9b092`, exposição tipada `e775982`, confirmação vinculada `0eb076c` e transferência segura ao PDV `76f5634` implementados; homologação manual do fluxo completo e critérios objetivos de sugestão por estoque/valor continuam pendentes;
- [~] Fase 3: recebimento de compra e entrada local de NF-e com vínculo exato possuem execução confirmada e idempotente; expansão para outros módulos permanece pendente;
- [~] cobertura progressiva: cadastro assistido de Clientes implementado; consultas
  de Estoque, Caixa e Financeiro já existem; ações mutáveis restantes e Relatórios
  continuam condicionados a portas oficiais, confirmação e idempotência próprias;
- [~] ferramenta administrativa de testes com catálogo fixo implementada na branch da IA; aceita somente suítes nomeadas, sem terminal/comando livre, e sua primeira execução real da suíte `ia_nabi` passou;
- [x] validação da fundação IA: 31 testes próprios aprovados; validação ampliada posterior com 74 testes Commercial e 88 testes combinados PDV Qt/Nabi aprovados, sem falhas ou ignorados, além de `compileall` e `git diff --check`;
- [x] checkpoint de conexão do painel ao shell Qt: ausência de serviço preserva o shell anterior; ausência de modelo/sessão exibe o painel em preparação com entrada bloqueada sem impedir o PDV; 40 testes IA/painel e 155 testes Qt/Commercial com 311 subtestes aprovados, além de `compileall`, `git diff --check` e ausência de importações Fiscal/SEFAZ na Nabi;
- [x] composição da Nabi somente leitura preparada com fábrica explícita: exige provedor local, fachada Commercial de consultas, `SecurityService`, auditoria administrativa e identificador de sessão; sem sessão o modelo não é chamado, e sem permissão nenhuma consulta é executada; validação ampliada com 200 testes e 326 subtestes aprovada;
- [x] ativação real no `main_qt.py` exige login explícito pelo `SecurityService`, inicia o runtime somente depois da credencial válida e nunca usa `start_session_without_password`; credencial inválida, modelo ausente, runtime adulterado ou falha de composição mantêm a Nabi bloqueada sem impedir o PDV;
- [x] portão local de artefato GGUF implementado: manifesto exige modelo, arquivo, quantização, URL HTTPS sem credenciais, revisão imutável, licença, tamanho e SHA-256; ausência, truncamento ou adulteração falham fechados e nenhum download é realizado; validação ampliada com 204 testes e 336 subtestes aprovada;
- [x] candidato Q4_K_M registrado sem download: `ggml-org/Qwen3-1.7B-GGUF`, revisão imutável `daeb8e2d528a760970442092f6bf1e55c3b659eb`, arquivo de 1.282.439.264 bytes, licença Apache-2.0 e SHA-256 `d2387ca2dbfee2ffabce7120d3770dadca0b293052bc2f0e138fdc940d9bc7b5`;
- [x] artefato e `llama-server` foram homologados no checkpoint `a30449a`, incluindo avisos de terceiros, integridade local, desempenho inicial, ferramenta real de consulta e recusas adversariais;
- [x] download controlado realizado somente na área persistente do perfil TESTE: peso de 1.282.439.264 bytes e SHA-256 local coincidentes; nada foi colocado no Git ou na Produção;
- [x] `llama.cpp` portátil CPU x64 `b10537` verificado pela atestação/hash oficial e por manifesto da árvore extraída com 52 arquivos;
- [x] supervisor local inicia oculto em loopback, sem Web UI, com CORS restrito e chave efêmera somente em memória; acesso sem chave retornou HTTP 401 e o processo é encerrado após uso;
- [x] homologação física inicial: carga entre 1,827 s e 2,210 s; respostas curtas entre 4,609 s e 6,729 s; chamada estruturada de pesquisa aprovada; ataques de SQL e falsa autorização SEFAZ recusados sem ferramenta;
- [~] substituir a pendência anterior por homologação ampliada: login Qt real, sessão/permissões reais, teste prolongado, avaliações de qualidade e decisão de empacotamento continuam pendentes;
- [x] checkpoint visual `32a2e32`: mascote azul integrada ao painel sem substituir o funcionamento textual; PNG RGBA validado, estado nunca depende somente da animação, cabeçalho adaptado ao dock estreito e fallback preservado; 55 testes e 25 subtestes aprovados, além de `compileall` e `git diff --check`;
- [x] checkpoint de ativação autenticada `9646a9d`: botão `Ativar Nabi`, diálogo que não envia senha ao modelo, carregamento assíncrono, sessão aleatória vinculada, runtime local iniciado após autenticação, encerramento pelo botão global e proteção contra ativação tardia após cancelamento; 65 testes e 25 subtestes aprovados, além de `compileall` e `git diff --check`;
- [~] homologação manual pendente: abrir o Qt no perfil TESTE, autenticar usuário real autorizado, confirmar consulta de produto/cliente, expiração de sessão, senha inválida, `Parar Nabi`, fechamento da janela e funcionamento integral do PDV com a Nabi indisponível;
- [x] fundação da Fase 2 `1d9b092`: rascunho usa somente IDs, preço e estoque oficiais, decimais exatos, cliente real no crediário, política de estoque negativo e hash canônico; não cria sessão de PDV, checkout, pagamento ou movimentação; 71 testes e 25 subtestes aprovados, além de `compileall` e `git diff --check`;
- [x] exposição tipada `e775982`: listas fechadas de IDs inteiros e quantidades decimais, registro que aceita leitura/rascunho e recusa mutações, política local atualizada e apresentação explícita de não persistência; 74 testes e 28 subtestes aprovados, além de `compileall` e `git diff --check`;
- [x] confirmação vinculada `0eb076c`: desafio temporário de uso único, usuário/sessão/hash exatos, invalidação por mudança, nova revisão ou `Parar Nabi`; confirmar ainda não executa checkout; 79 testes e 28 subtestes aprovados;
- [x] transferência ao PDV `76f5634`: carrega atomicamente carrinho vazio, revalida produto/preço, seleciona cliente ou Consumidor Final, sugere pagamento e exige finalização pelo fluxo oficial Revisar → Confirmar; não substitui venda em andamento e não persiste antecipadamente; regressão conjunta com 171 testes e 36 subtestes aprovada, além de `compileall` e `git diff --check`;
- [x] planejamento por valor/estoque `aa195e7`: a ferramenta `vendas.sugerir_rascunho_por_estoque` exige valor alvo, tolerância, limite de unidades e pagamento explícitos, consulta produtos ativos/vendáveis pela fachada Commercial, prioriza maior saldo e só produz combinação dentro da tolerância; preço, saldo e disponibilidade são revalidados ao criar o rascunho, nenhuma venda ou movimentação é persistida e a transferência continua sujeita ao fluxo oficial Revisar → Confirmar; 138 testes e 34 subtestes aprovados, além de `compileall` e `git diff --check`;
- [x] correção de integração visual `cdd15be`: o painel reconhece tanto o rascunho explícito quanto a sugestão por valor/estoque, renderiza itens/total/pagamento e libera Revisar → Confirmar; a mensagem de ativação passou a refletir consultas e rascunhos seguros; 19 testes e 3 subtestes focados aprovados, além de `compileall` e `git diff --check`;
- [x] Compras Assistidas `6163bfc`, `209bcaa`, `1086e24` e `e2e2d9b`: rascunho tipado usa IDs reais, saldo pendente, quantidades/custos decimais, total, documento e efeito financeiro explícitos; confirmação reforçada revalida usuário, sessão, permissão e hash; o journal idempotente é gravado na mesma transação de recebimento, estoque, custo, auditoria e financeiro, repetição da mesma chave retorna o commit anterior e conteúdo divergente é recusado; execução ocorre exclusivamente pelo `CompraService` oficial e o painel não possui acesso direto ao banco;
- [x] revisão segura de XML de entrada `3ff2842` e `ee17cbf`: arquivo é escolhido explicitamente pelo operador, limitado em tamanho e rejeita DTD/entidades antes do parser; chave, fornecedor, itens, candidatos e `cStat` são exibidos como dados/evidências, nunca como instrução ou declaração própria de autorização; o checkpoint não importa, não movimenta estoque/financeiro e não acessa SEFAZ;
- [x] entrada assistida de NF-e local `97c5103`: somente revisão previamente preparada, destinatário documentado, evidência local literal `cStat=100`, um único `product_id` real ligado por EAN/código exato e fator explícito por item podem virar rascunho executável; produto novo, nome semelhante, duplicidade exata, XML alterado, fator ausente ou evidência diferente são bloqueados; confirmação reforçada revalida sessão/permissão/hash e o `NFeImportService` grava journal idempotente, nota, vínculo, estoque e financeiro na mesma transação, sem comunicação com SEFAZ;
- [x] validação do checkpoint de entrada: 40 testes focados e regressão relacionada com 304 testes e 37 subtestes aprovados, além de `compileall` e `git diff --check`;
- [x] regressão integral após entrada assistida e integração do emissor: 1.814 testes e 409 subtestes aprovados, 1 teste previamente ignorado e zero falhas; a execução foi particionada alfabeticamente para evitar a interrupção silenciosa observada na execução monolítica, com todos os arquivos `tests/test_*.py` cobertos exatamente uma vez; `compileall` e `git diff --check` aprovados;
- [x] integração conjunta Licenciamento V2 + Qt completo + Nabi: históricos preservados por merge normal; startup mantém portão fail-closed e monitoramento contínuo da licença antes de compor a ativação autenticada, rascunhos de venda, recebimentos idempotentes e revisão XML; validação conjunta pré-merge com 231 testes e 37 subtestes, painel com 16 testes, ativação com 1 teste e licenciamento com 25 testes aprovados;
- [x] emissor externo V2 integrado à trilha conjunta pelo merge normal `780361d`, preservando os commits `35b3b80`, `84c0d49` e `4ee57e9`; nenhuma chave privada real foi criada ou incorporada;
- [x] pesquisa ampla do PDV integrada por merge normal a partir da branch isolada `codex/pdv-pesquisa-acessivel` (`5246711`, `2f17ab0`, `a77a63f`), preservando pesquisa rápida, F2/botão, seleção exclusivamente por `product_id` real e fluxo de teclado; eventual orientação pela Nabi continua condicionada a porta Qt explícita, sem cliques livres, banco direto, produto inventado ou resolução automática de texto ambíguo;
- [ ] experimento visual somente em perfil TESTE: preservar integralmente o splash original e acrescentar, perto do final do carregamento real, a mascote Nabi azul entrando/flutuando e pousando discretamente ao lado do nome; não alterar fundo, logotipo, proporções ou sequência existente, não atrasar artificialmente o startup e não promover para Produção/instalador sem aprovação visual expressa;
- [ ] voz;
- [ ] auditoria específica antes de qualquer integração indireta com fluxo fiscal;
- [!] IA não pode executar ações mutáveis antes das travas de confirmação, permissão e auditoria.

## Instrução para qualquer conversa sucessora

Estamos continuando um trabalho já avançado no NabiCode. Não recomeçar o projeto, não redesenhar toda a arquitetura e não transportar commits de ambientes antigos. Primeiro ler este documento, inspecionar o checkout Windows atual e confirmar o estado real do Git.

A conversa principal atua como **cérebro/arquiteto/auditor**: analisa o sistema completo, define missões pequenas, verifica evidências e audita resultados.

O Work atua como **músculo/engenheiro executor**: implementa missões fechadas no checkout Windows, executa testes, cria commits locais e só faz push quando houver autorização expressa.

## Checkout oficial de desenvolvimento

- Sistema: Windows local.
- Workspace: `C:\Users\famil\Desktop\NabiCode-QT-Homologacao-5b9ff8f\NabiCode-QT-Teste`
- Branch: `homologacao/qt-commercial-2026-08-23`
- Origin: `https://github.com/Oitavomembro/NABI-ATUALIZACAO.git`
- Fluxo abandonado: bundles entre ambientes.
- Fluxo oficial: Work local → testes focados → commit local → homologação manual → testes completos → push autorizado.

## Estado Git na criação deste mapa

- Último commit remoto conhecido: `528275addbf8746b61d5ff76d1d0f4e0f88f7378`.
- Commit local ainda não enviado: `4cb4932a920a1cf9af60e8d1d214c4a6f338cc71`.
- Mensagem: `fix: ajusta fluxo do PDV Qt ate pagamentos`.
- Situação informada: branch local um commit à frente do origin, árvore limpa e nenhum push desse commit.
- Antes de continuar, confirmar tudo novamente com Git; este documento registra um estado histórico, não substitui a verificação real.

## Estratégia de desenvolvimento e validação

Desenvolver por partes normalmente consome menos e reduz retrabalho. Isso não significa testar apenas a parte alterada para sempre.

Fluxo obrigatório:

1. escolher uma pendência pequena e específica;
2. localizar a implementação real e a causa;
3. alterar somente o necessário;
4. executar testes focados;
5. criar commit local recuperável;
6. não fazer push imediatamente;
7. homologar manualmente no Windows quando houver comportamento visual ou operacional;
8. continuar para a próxima parte somente quando a fundação anterior estiver estável;
9. ao fechar um conjunto, executar a suíte completa do NabiCode;
10. fazer push para homologação somente após aprovação;
11. unir/publicar somente depois da homologação final.

Commit local não equivale a publicação. É permitido usá-lo como ponto seguro antes da homologação. Push exige autorização.

## Arquitetura funcional existente

O NabiCode possui duas interfaces coexistentes:

- **Legacy (CustomTkinter/Tk):** referência funcional mais completa do sistema.
- **Qt (PySide6):** migração em andamento; atualmente representa principalmente o PDV comercial e ainda não possui paridade funcional integral.

Não assumir que um botão bonito no Qt está concluído. Conferir sempre o comportamento equivalente no Legacy e, depois, transportar a intenção por meio dos serviços desacoplados, sem copiar acoplamentos antigos.

### Módulos principais do NabiCode

- Início/Dashboard: resumos, atividades e movimentações.
- Vendas/PDV: produto, item avulso, carrinho, cliente, orçamento, vendas suspensas, vendas do dia, descontos, pagamentos e comprovantes.
- Clientes: cadastro, edição, histórico, recebimentos, cobranças, lembretes, retornos e crediário.
- Produtos/Estoque: cadastro, preços, estoque, categorias, marcas, fornecedores, XML, devoluções e histórico.
- Caixa: abertura, saldo inicial, sangria, suprimento, fechamento, conferência e comprovante.
- Financeiro: títulos, baixas, estornos, cancelamentos, recorrências, conciliações e centros de custo.
- Relatórios: filtros, CSV, Excel, PDF, histórico e agendamento.
- Central Fiscal: entradas, saídas, XML, DANFE, SEFAZ, outbox, cancelamento, CC-e, inutilização, contingência e pacotes contábeis.
- Configurações: loja, interface, backup, impressoras, modo comercial/fiscal e segurança.
- Administração: usuários, perfis, auditoria, banco, atualizações, snapshots, migração e diagnóstico.
- Recursos globais: pesquisa, favoritos, notificações, ajuda, suporte, bloqueio e modo pânico.

## Trabalho comercial e Qt já realizado

- autorização local de instalação;
- núcleo comercial desacoplado;
- `PDVApplicationService`;
- Query/Action Services;
- Clientes/Recebimentos;
- Financeiro/Cobranças;
- Produtos/Estoque;
- primeira interface PySide6;
- visual aproximado ao NABI VENDAS Legacy;
- `MoneyEdit` Qt corrigido;
- produto avulso com fluxo por Enter;
- Consumidor Final exposto por porta comercial e gateway existente;
- cliente e produto transportados por IDs reais;
- Enter retirado dos atalhos globais e controlado por filtro de eventos;
- prevenção de múltiplas transições pelo mesmo evento e por auto-repeat;
- edição de texto invalida cliente/produto selecionado anteriormente;
- carrinho e crediário continuam validados pelo backend.

Commits relevantes no histórico recente:

- `dab3f4a` — estabiliza navegação por teclado do PDV Qt;
- `528275a` — invalida seleções editadas no PDV Qt;
- `4cb4932` — ajusta fluxo do PDV Qt até Pagamentos (local na criação deste mapa).

## Fluxo operacional decidido para o PDV Qt

Fluxo esperado:

`Item → Quantidade → Preço → carrinho → Cliente → Finalizar venda → Pagamentos → Confirmação → pós-venda`

Regras:

- inclusão sem cliente deve focar Cliente;
- inclusão com cliente deve focar Finalizar;
- Cliente vazio + Enter seleciona Consumidor Final por ID real;
- cliente selecionado com carrinho deve focar Finalizar;
- cliente selecionado sem carrinho deve focar a entrada ativa do item;
- Enter sobre Finalizar e F9 global abrem a mesma janela de Pagamentos;
- abrir Pagamentos não registra a venda;
- persistência ocorre somente depois de confirmação explícita no diálogo;
- cancelar Pagamentos preserva carrinho, cliente e total;
- carrinho vazio não deve abrir Pagamentos;
- um Enter não pode atravessar várias etapas;
- venda comum não exige cliente identificado;
- crediário continua exigindo cliente válido e nunca pode ser liberado apenas pela interface.

### Homologação manual pendente do conjunto até `83c72af`

Testar no Windows atualizado:

1. produto avulso → quantidade → preço → carrinho;
2. confirmar foco em Cliente;
3. Cliente vazio + Enter → Consumidor Final;
4. confirmar foco em Finalizar;
5. Enter → abrir Pagamentos sem persistir;
6. Cancelar → preservar sessão e retornar a Finalizar;
7. repetir com produto cadastrado;
8. repetir com cliente cadastrado;
9. testar F9;
10. testar carrinho vazio e Enter prolongado.

## Pendências Qt conhecidas após a navegação

### 1. Separar Revisar de Confirmar na janela de Pagamentos

As formas e condições principais de Pagamentos já foram implementadas no conjunto
local até `83c72af`. A pendência manual encontrada é separar duas decisões que
hoje aparecem combinadas:

- `Revisar` valida e apresenta um resumo determinístico, sem persistir;
- `Confirmar venda` somente fica disponível após revisão válida e é a única ação
  que pode solicitar a persistência;
- qualquer alteração posterior deve invalidar a revisão;
- após confirmação bem-sucedida, seguir para as opções de impressão.

O Legacy permanece como referência visual e operacional. Ele possui:

- Dinheiro, PIX, Débito, Crédito, Crediário e Outros;
- valor recebido;
- falta ou troco;
- desconto por valor ou percentual;
- acréscimo por valor ou percentual;
- autorização/NSU opcional da maquininha;
- condições de crediário;
- parcelas e primeiro vencimento;
- Cancelar e Finalizar venda;
- Enter para avançar e Shift+Enter para voltar.

Não copiar regras financeiras para a GUI. O diálogo deve coletar dados e delegar cálculo, validação e persistência ao núcleo comercial/backend.

### 2. Pós-venda e comprovantes

Mapear e implementar sem duplicar persistência:

- confirmação da venda;
- resultado recusado ou efeitos secundários com falha;
- escolha/geração de comprovante;
- impressão térmica e PDF conforme as regras existentes;
- limpeza segura da sessão somente quando o backend indicar consumo;
- prevenção de dupla finalização.

### 3. Botões provisórios no Qt

`Vendas do dia` e `Orçamento` aparecem visualmente, mas ainda precisam ser ligados aos serviços corretos ou permanecer explicitamente indisponíveis. Não criar comportamento fictício.

### 4. Paridade funcional progressiva

Depois do PDV, continuar por módulos comerciais desacoplados. Não migrar o arquivo Legacy inteiro para Qt e não misturar a migração visual com mudanças fiscais.

## Linha fiscal — contexto obrigatório

Durante Fiscal/SEFAZ, a conversa principal assume postura de **auditor fiscal adversarial**, como se estivesse do lado do Governo/Fisco procurando razões legítimas para reprovar, autuar ou impedir homologação.

Princípios:

- conformidade antes de conveniência;
- nenhuma regra fiscal inventada;
- separar regra documentada, interpretação e decisão de produto;
- exigir evidência, rastreabilidade e integridade;
- preservar documentos e evidências de homologação;
- Fiscal não pode depender do comportamento visual da GUI;
- falha de comunicação não pode fabricar autorização ou rejeição;
- testes unitários não equivalem a homologação física/real;
- alterações comerciais/Qt não podem provocar regressão fiscal;
- qualquer mudança Fiscal/SEFAZ exige auditoria específica antes de release.

Já existem trabalhos em:

- outbox fiscal transacional;
- tratamento seguro de resposta desconhecida;
- processamento e worker da outbox;
- cancelamento fiscal seguro;
- autorização SEFAZ para prazo de cancelamento;
- armazenamento persistente fora de `Program Files` para banco, fiscal, logs, backups e demais dados mutáveis.

Não reimplementar ou alterar isso incidentalmente durante a migração Qt.

Regra de ouro fiscal:

> Não perguntar apenas “o NabiCode funciona?”. Perguntar “de quais formas um auditor fiscal poderia provar que ele NÃO está conforme?” e tentar derrubar cada hipótese com evidência.

## Projeto futuro — IA NABI integrada ao sistema inteiro

### Visão

Criar uma assistente chamada **Nabi**, presente do início ao fim do programa, com mascote próprio e uma área de interação. A primeira versão será por texto. A arquitetura deve deixar preparado o caminho para voz no futuro.

A Nabi deve poder auxiliar em todo o sistema, mas não deve possuir acesso irrestrito ao banco, ao sistema operacional, à SEFAZ ou a integrações externas.

Ela deve usar o NabiCode como o operador usa: por comandos e serviços oficiais do próprio programa, respeitando permissões, regras, validações e confirmações.

## Proteção comercial e autorização de cópias

### Objetivo do proprietário

Permitir uma cópia controlada para avaliação/uso pelo chefe ou por um cliente autorizado, sem facilitar que o pacote seja copiado para outros computadores e revendido sem autorização.

Nenhuma proteção local é absolutamente impossível de quebrar, principalmente se o código-fonte completo for entregue. O objetivo realista é combinar barreira técnica, rastreabilidade, contrato e processo de distribuição para tornar cópia casual e revenda indevida difíceis, detectáveis e juridicamente claras.

### Estado encontrado na auditoria de 23/08/2026

O Legacy possui duas travas diferentes:

1. `InstallationAuthorizationService`:
   - exigida em perfis diferentes de `TESTE`;
   - calcula fingerprint com `MachineGuid` do Windows e serial do volume do sistema;
   - persiste somente o hash, não os identificadores brutos;
   - protege o registro com DPAPI em escopo da máquina;
   - detecta arquivo ausente, ilegível, inválido ou copiado para máquina divergente;
   - limita tentativas repetidas de senha por processo;
   - roda antes da licença comum e antes das migrações do banco no startup Legacy.

2. `LicenseService`:
   - controla validade diária, expiração exata e bloqueio manual;
   - reavalia no startup e periodicamente;
   - permite liberação administrativa por período.

### Falhas e lacunas que impedem considerar a proteção pronta

- `main_qt.py` não aplica atualmente a mesma autorização de instalação e a mesma licença do startup Legacy; uma entrega Qt poderia contornar a trava.
- O perfil `TESTE` possui bypass intencional da autorização; não pode ser usado como edição distribuível ao chefe/cliente.
- A autorização atual usa verificação de senha mestre local. Se essa senha ou o verificador forem extraídos, ela pode autorizar novas máquinas.
- A licença comum usa valores locais de configuração; ausência de validade retorna `SEM_VALIDADE` sem bloqueio.
- validade diária inválida e expiração exata inválida possuem comportamentos que podem falhar abertos.
- quem recebe o código-fonte Python completo pode remover chamadas de bloqueio e reconstruir o programa.
- DPAPI impede copiar diretamente o arquivo autorizado para outra máquina, mas não prova que a autorização foi emitida pelo proprietário do NabiCode.
- não existe ainda um arquivo de licença comercial assinado assimetricamente por uma chave privada mantida fora do programa.
- não existe revogação controlada nem cadastro central/offline de quais instalações foram emitidas.
- depender apenas do relógio local permite tentativa de retrocesso de data.
- testes atuais cobrem principalmente o Legacy; a paridade de segurança no Qt precisa de testes próprios.

### Arquitetura recomendada para a trava comercial

Criar uma camada única, usada por todos os pontos de entrada:

`StartupAccessGate → InstallationAuthorization → SignedLicense → RuntimeProfile → abertura do banco/interface`

Nenhuma interface Legacy, Qt, CLI administrativa ou executável auxiliar deve abrir o sistema operacional sem passar pelo mesmo portão quando estiver em edição distribuível.

### Pesquisa de tecnologia aberta — decisão preliminar

Pesquisa realizada em fontes oficiais em 23/08/2026:

- **PyCA cryptography**: já consta no runtime Windows do NabiCode (`cryptography==46.0.0`) e disponibiliza primitivas criptográficas adequadas. O projeto é distribuído sob licenciamento permissivo Apache-2.0/BSD. É a opção preferida para implementar Ed25519 sem adicionar uma segunda pilha criptográfica.
- **Minisign**: projeto aberto sob licença ISC, usa Ed25519 e demonstra corretamente a separação entre chave secreta protegida, chave pública distribuída, assinatura e verificação. Será usado como referência conceitual e operacional, não como código copiado nem dependência obrigatória.
- **Keygen — exemplo de arquivos criptográficos de máquina em Python**: repositório de exemplo sob licença MIT que demonstra assinatura Ed25519, vínculo por fingerprint e arquivo de máquina. Pode orientar testes e ameaças, mas o NabiCode não deve depender do serviço Keygen nem copiar trechos sem preservar atribuição e licença.

Decisão:

- construir implementação própria e pequena sobre `cryptography` já existente;
- formato de licença próprio, canônico, versionado e testado;
- Ed25519 para assinatura/autenticidade;
- não criptografar o payload apenas para esconder dados públicos da licença; assinatura é obrigatória, criptografia só quando houver requisito real de confidencialidade;
- ferramenta emissora separada do runtime;
- manter em `THIRD_PARTY_NOTICES.md` as licenças das dependências efetivamente distribuídas;
- se qualquer código de exemplo for adaptado, registrar origem, commit, licença e alterações; preferir reimplementação independente baseada em documentação e testes;
- evitar GPL/AGPL ou licenças não permissivas em componentes incorporados sem revisão jurídica específica;
- antes da distribuição comercial, executar auditoria de dependências e revisão jurídica dos avisos. Esta análise técnica não substitui aconselhamento jurídico.

#### Licença offline assinada

- gerar a licença em uma ferramenta separada mantida somente pelo proprietário;
- assinar com chave privada que nunca acompanha o NabiCode distribuído;
- o programa contém somente a chave pública para verificar assinatura;
- payload com identificador da licença, cliente, edição, fingerprint autorizado, data de emissão, validade, recursos liberados e quantidade de instalações;
- formato canônico e versão explícita;
- qualquer alteração no arquivo invalida a assinatura;
- arquivo continua protegido localmente por DPAPI depois da validação, quando apropriado;
- não usar uma senha universal como prova de emissão da licença.

#### Edições e perfis

- `DESENVOLVIMENTO/TESTE`: somente para a equipe, nunca distribuído;
- `AVALIACAO`: máquina vinculada, prazo curto, marca visual e dados de teste ou limites explícitos;
- `COMERCIAL`: recursos contratados, validade e máquina(s) autorizada(s);
- `FISCAL`: liberação separada por cliente/CNPJ e somente depois da homologação aplicável;
- `SUPORTE`: ferramentas administrativas sem transformar a credencial em chave universal de ativação.

#### Travas adicionais

- checagem obrigatória no startup Qt e Legacy;
- checagem antes de operações mutáveis críticas, sem consultar licença em cada tecla;
- última data válida assinada/encadeada para detectar retrocesso evidente de relógio;
- tolerância definida para troca legítima de disco ou reinstalação, com processo de reemissão;
- identificador de instalação exibido no painel administrativo e relatórios de suporte;
- registro local auditável de ativação, falha, expiração e reemissão, sem gravar segredos;
- marca d'água discreta na edição de avaliação com cliente/licença, sem poluir documentos oficiais;
- pacote entregue sem repositório `.git`, testes internos, ferramentas de emissão, chave privada ou fonte desnecessária;
- build assinado digitalmente quando houver certificado de assinatura de código;
- manifesto de integridade do pacote e atualizações assinadas;
- exportação e backup dos dados do cliente continuam disponíveis conforme contrato, mesmo que a licença expire;
- bloqueio não pode corromper banco, apagar dados ou impedir backup/exportação necessária.

### Distribuição segura para o chefe

Antes de entregar:

1. não enviar o workspace de desenvolvimento nem o código-fonte completo;
2. criar build de avaliação separado;
3. vincular a licença à máquina dele;
4. definir prazo e recursos liberados;
5. usar banco/perfil de avaliação separado;
6. bloquear Fiscal/SEFAZ de produção;
7. fornecer instalador e atualização oficiais;
8. registrar qual versão, hash, licença e máquina foram entregues;
9. testar expiração, cópia para segunda máquina, backup, reinstalação e recuperação;
10. preencher e revisar juridicamente os Termos de Licença existentes.

### Portão de liberação da proteção comercial

Não entregar a cópia de avaliação enquanto não houver evidência de que:

- `main.py` e `main_qt.py` passam pelo mesmo portão;
- perfil distribuído não aceita bypass `TESTE`;
- licença ausente, inválida, adulterada, expirada ou de outra máquina falha fechada;
- chave privada não está no pacote nem no repositório distribuído;
- cópia do diretório para outra máquina não abre;
- reinstalação autorizada possui procedimento seguro;
- expiração preserva banco e permite procedimento legítimo de suporte/backup;
- atualização não remove ou enfraquece a licença;
- testes automatizados e validação física Windows foram aprovados.

### Decisão do proprietário — reconstrução autorizada

Em 23/08/2026, o proprietário autorizou substituir integralmente a implementação antiga de autorização/licença quando necessário para alcançar segurança adequada. A compatibilidade com as chaves locais antigas não tem prioridade sobre autenticidade, falha fechada, preservação de dados e cobertura uniforme entre Legacy e Qt.

A reconstrução deve ocorrer em missão/branch isolada depois de estabilizar a etapa comercial em andamento. Não misturar a troca de licenciamento com commits de PDV, Pagamentos ou Fiscal.

### Política de vencimento e tolerância de 10 dias

A licença assinada terá estados explícitos:

- `ATIVA`: até 23:59:59 da data de validade;
- `TOLERANCIA`: dez dias civis completos imediatamente posteriores à validade;
- `BLOQUEADA`: a partir de 00:00:00 do décimo primeiro dia posterior à validade;
- `INVALIDA`: assinatura, formato, edição, fingerprint ou chave pública incompatível;
- `RELOGIO_SUSPEITO`: retrocesso relevante do relógio em relação ao último uso confiável;
- `REVOGADA`: somente quando houver evidência de revogação aplicável ao modo de operação.

Exemplo normativo:

- validade: 31/08/2026;
- ativa até: 31/08/2026 23:59:59;
- tolerância: 01/09/2026 00:00:00 até 10/09/2026 23:59:59;
- bloqueio: 11/09/2026 00:00:00.

Durante `TOLERANCIA`:

- operações contratadas continuam disponíveis;
- exibir aviso persistente e não enganoso com dias restantes;
- avisar no startup e no painel, sem modal repetido a cada segundo;
- backup e exportação continuam disponíveis;
- renovar substitui a licença assinada e encerra a tolerância;
- não modificar silenciosamente a data original da licença.

Durante `BLOQUEADA`, `INVALIDA` ou `RELOGIO_SUSPEITO`:

- impedir novas operações comerciais, financeiras, administrativas mutáveis e fiscais;
- permitir somente ativação/importação de nova licença, diagnóstico mínimo, backup e exportação segura dos dados do cliente;
- nunca apagar, criptografar, corromper ou sequestrar os dados;
- não iniciar worker fiscal nem transmissão externa;
- manter mensagem clara com código de suporte e motivo verificável;
- senha mestre local não pode fabricar ou estender licença.

O número de dias de tolerância deve estar no payload assinado ou na política imutável da edição. Configuração local editável não pode ampliar o prazo.

### Evidência da auditoria da implementação antiga

Em 23/08/2026 foram executados os testes focados da licença e autorização em área temporária isolada:

- 37 testes aprovados;
- 8 subtestes aprovados;
- nenhuma falha funcional nesse conjunto.

Esses testes confirmam apenas o contrato antigo. Não resolvem as lacunas já identificadas: ausência do portão no Qt, bypass TESTE, falta de assinatura emitida pelo proprietário, estados locais que falham abertos e inexistência da tolerância de dez dias.

Exemplo de objetivo futuro:

> “Nabi, faça uma venda de aproximadamente R$ 500 usando os produtos com maior estoque e pagamento por PIX.”

Comportamento esperado:

1. interpretar a intenção;
2. consultar estoque pelos serviços oficiais;
3. propor produtos reais e disponíveis;
4. montar um rascunho de venda pela camada comercial;
5. apresentar itens, quantidades, preços, total, cliente e forma de pagamento;
6. perguntar claramente se está pronto para confirmar;
7. somente após confirmação explícita, solicitar ao serviço oficial a finalização;
8. apresentar o resultado real retornado pelo backend;
9. no modo fiscal, apenas o pipeline fiscal existente decide documento, fila e comunicação; a IA não fala diretamente com a SEFAZ e não inventa autorização.

### Princípios arquiteturais da IA

- software gratuito e de código aberto sempre que juridicamente e tecnicamente viável;
- modelo substituível, sem aprisionamento a um único fornecedor;
- execução local/offline como preferência, com adaptadores opcionais no futuro;
- núcleo do NabiCode não deve importar diretamente SDK de um modelo específico;
- separar interface, orquestração, modelo de linguagem e ferramentas do sistema;
- nenhum SQL livre gerado pelo modelo;
- nenhuma chamada direta a repositórios sensíveis quando existir serviço de aplicação;
- cada capacidade exposta como ferramenta tipada, pequena e auditável;
- ferramentas de consulta separadas de ferramentas que alteram estado;
- permissões do usuário atual aplicadas a cada ferramenta;
- confirmação humana obrigatória antes de vendas, pagamentos, cancelamentos, exclusões, alterações financeiras, fiscais ou administrativas;
- mostrar uma prévia determinística antes da confirmação;
- comandos idempotentes e chaves de operação para evitar duplicidade;
- registrar intenção, ferramentas usadas, parâmetros permitidos, confirmação e resultado;
- não gravar raciocínio interno do modelo; registrar somente trilha operacional necessária;
- falha ou indisponibilidade do modelo não pode impedir o uso normal do NabiCode;
- respostas do modelo nunca substituem validações do backend;
- dados sensíveis devem ser minimizados e permanecer locais sempre que possível;
- nenhuma “memória” oculta com dados de clientes sem política explícita de retenção.

### Arquitetura proposta

1. **NabiAssistant UI**
   - painel lateral ou janela própria;
   - mascote e estado visual;
   - histórico de diálogo;
   - entrada por texto na primeira fase;
   - componentes de microfone/voz apenas preparados e desativados até a fase própria;
   - cartões de prévia e botões Confirmar/Cancelar.

2. **AssistantApplicationService**
   - recebe a mensagem do usuário;
   - mantém contexto operacional mínimo da sessão;
   - chama o provedor de modelo por uma porta abstrata;
   - valida planos de ação;
   - executa somente ferramentas registradas e autorizadas;
   - retorna eventos estruturados para a interface.

3. **LanguageModelPort**
   - contrato independente de fornecedor;
   - suporte futuro a diferentes modelos locais ou remotos;
   - saída estruturada e validada;
   - limites de tempo, tamanho e repetição.

4. **Tool Registry**
   - catálogo explícito de capacidades;
   - exemplos de leitura: pesquisar produtos, consultar estoque, localizar cliente, consultar saldo e listar vendas;
   - exemplos de preparação: criar rascunho de venda, simular pagamento e validar disponibilidade;
   - exemplos de alteração: confirmar venda, registrar recebimento ou cancelar operação, sempre com confirmação e autorização adicionais.

5. **Confirmation Gateway**
   - impede que texto do modelo seja tratado como autorização;
   - gera resumo determinístico da ação;
   - exige confirmação do operador;
   - vincula a confirmação ao conteúdo exato e a um prazo curto;
   - invalida confirmação se itens, valores, cliente ou forma de pagamento mudarem.

6. **Audit Trail**
   - registra usuário, horário, ação solicitada, ferramenta, parâmetros permitidos, confirmação e resultado;
   - nunca registra senha, certificado, token ou segredo;
   - permite explicar quem confirmou cada operação.

7. **Future Voice Port**
   - fala para texto e texto para fala como portas independentes;
   - a voz produz a mesma mensagem estruturada da entrada textual;
   - a confirmação de ações sensíveis não deve depender apenas de reconhecimento de voz até existir autenticação apropriada;
   - falha de voz retorna ao modo escrito sem afetar a operação.

### Fases recomendadas da IA

#### Fase 0 — preparação arquitetural

- definir ameaças, permissões, confirmações e auditoria;
- definir portas de modelo, ferramentas e voz;
- nenhuma IA executando operações reais.

#### Fase 1 — assistente escrita somente leitura

- mascote e painel de conversa;
- ajuda contextual;
- pesquisa de clientes e produtos;
- consulta de estoque, preços e informações comerciais;
- nenhuma alteração de estado.

#### Fase 2 — rascunhos comerciais

- montar rascunho de carrinho;
- sugerir produtos com base em critérios objetivos;
- simular total e pagamento;
- operador revisa e transfere o rascunho para o PDV;
- ainda sem confirmação automática de venda.

#### Fase 3 — ações confirmadas

- confirmação vinculada ao rascunho exato;
- finalização somente pelos serviços oficiais;
- trilha de auditoria e proteção contra duplicidade;
- começar por vendas comerciais de teste.

#### Fase 4 — cobertura progressiva do sistema

- Clientes, Estoque, Caixa, Financeiro e Relatórios;
- cada módulo recebe ferramentas próprias e permissões específicas;
- ações destrutivas ou sensíveis continuam exigindo confirmação.

#### Fase 5 — voz

- entrada e saída por voz;
- mesma camada de ferramentas e confirmações;
- texto permanece sempre disponível como alternativa.

#### Fase 6 — integração fiscal indireta e auditada

- a IA prepara e solicita operações pelo fluxo normal do NabiCode;
- o backend fiscal continua sendo a única autoridade para XML, certificado, fila, SEFAZ, autorização, rejeição e cancelamento;
- nenhuma transmissão sem evidência e confirmação apropriadas;
- auditoria fiscal adversarial obrigatória antes de qualquer liberação.

### O que a IA nunca deve fazer

- acessar diretamente a SEFAZ;
- fabricar protocolo, autorização, rejeição, estoque, cliente ou preço;
- executar SQL inventado;
- ignorar permissões do usuário;
- confirmar a própria proposta;
- concluir venda porque o usuário apenas pediu uma simulação;
- reutilizar confirmação antiga depois de mudar o rascunho;
- esconder do operador itens, valores, cliente ou forma de pagamento;
- substituir regras fiscais, comerciais ou financeiras existentes;
- tornar o NabiCode dependente de internet ou de um único modelo.

## Opinião do arquiteto e melhorias indispensáveis

A visão da Nabi é tecnicamente viável e pode se tornar um diferencial real do produto. A decisão mais importante é não transformar o modelo de linguagem em um superusuário invisível.

A expressão “usar o programa como o operador” deve significar **usar as mesmas regras, permissões e serviços oficiais**, e não movimentar o mouse ou clicar livremente na interface. Automação visual é frágil, difícil de auditar e pode acionar o botão errado quando o layout mudar. A interface pode mostrar visualmente cada passo, mas a execução deve ocorrer por comandos estruturados do núcleo.

Também é importante distinguir “código aberto” de “custo zero”. O software pode usar modelos e componentes abertos sem mensalidade obrigatória, mas continuará existindo custo de computador, memória, armazenamento, energia, manutenção e atualização. A arquitetura substituível protege o NabiCode caso um modelo fique pesado, abandone uma licença ou deixe de receber atualizações.

### Separação obrigatória entre planejar e executar

A Nabi deve possuir dois estágios independentes:

1. **Planejamento:** consulta dados permitidos e monta um plano/rascunho sem alterar estado.
2. **Execução:** recebe um comando estruturado já validado, mostra uma prévia e aguarda confirmação humana vinculada ao conteúdo exato.

O texto livre do modelo nunca deve chamar diretamente uma operação de gravação.

### Níveis de capacidade

- **Nível 0 — conversa:** explicar telas e procedimentos, sem consultar dados.
- **Nível 1 — consulta:** pesquisar e resumir dados que o usuário atual já pode visualizar.
- **Nível 2 — rascunho:** preparar carrinhos, filtros, relatórios e formulários sem gravar.
- **Nível 3 — confirmação simples:** operações comerciais reversíveis e de baixo risco, sempre com prévia.
- **Nível 4 — confirmação reforçada:** venda, recebimento, baixa, cancelamento, alteração de estoque, Caixa e Financeiro.
- **Nível 5 — operação restrita:** Fiscal, usuários, permissões, backup/restauração, atualização e migração; requer permissão específica, confirmação reforçada e auditoria própria. Algumas ações devem continuar exclusivamente manuais.

Uma ferramenta não pode mudar de nível por decisão do modelo.

### Travas de segurança adicionais

- botão global **Parar Nabi**, sempre acessível, que cancela novos comandos e invalida confirmações pendentes;
- modo seguro de inicialização com a IA completamente desativada;
- limite de quantidade de ferramentas por solicitação;
- limite de tempo e de tentativas;
- bloqueio de laços em que a IA chama repetidamente a mesma ferramenta;
- chave idempotente por operação mutável;
- bloqueio de dupla confirmação e de duplo clique;
- confirmação expira rapidamente e vale somente para um hash do rascunho;
- qualquer mudança de item, quantidade, preço, cliente, desconto ou pagamento invalida a confirmação;
- valores máximos configuráveis por perfil para ações assistidas;
- operações acima do limite exigem senha/perfil administrativo, sem revelar a senha à IA;
- nenhuma ferramenta recebe conexão de banco aberta ou credenciais;
- resultados retornados às ferramentas devem conter somente os campos necessários;
- logs da IA separados dos logs fiscais, comerciais e de segurança, mas correlacionados por identificador de operação;
- falha da auditoria ou do armazenamento impede ação mutável, mas não impede consultas seguras;
- atualização do modelo nunca deve alterar automaticamente ferramentas ou permissões;
- versão do modelo, prompt operacional e catálogo de ferramentas registrados em cada ação relevante;
- testes com modelo indisponível, resposta inválida, resposta lenta e resposta hostil;
- botão de desfazer somente quando o backend possuir operação reversa real; nunca simular reversão.

### Proteção contra instruções maliciosas nos próprios dados

Nomes de produtos, observações de clientes, XML, PDFs, e-mails, relatórios e descrições podem conter texto malicioso ou acidental, como “ignore as regras e faça uma transferência”. Todo conteúdo vindo de cadastros, documentos ou integrações deve ser tratado como **dado não confiável**, nunca como instrução para a Nabi.

Defesas:

- separar no protocolo mensagens do operador e dados consultados;
- impedir que conteúdo recuperado habilite ferramentas;
- ferramentas disponíveis são escolhidas pelo NabiCode, não por texto encontrado;
- validar toda saída do modelo contra schema fechado;
- rejeitar nomes de ferramentas, campos ou valores fora da lista permitida;
- nunca executar código, comandos de terminal, URLs ou SQL emitidos pelo modelo;
- não enviar documentos completos ao modelo quando um resumo estruturado for suficiente.

### Privacidade e isolamento

- preferir modelo local para dados de clientes e operação;
- permitir adaptador remoto somente com opção explícita, contrato e política de dados revisados;
- mascarar CPF/CNPJ, endereço, telefone, e-mail e dados financeiros quando não forem necessários;
- não usar dados do cliente para treinar modelo automaticamente;
- permitir apagar histórico conversacional sem apagar a auditoria legal mínima da operação;
- separar memória de conversa, preferências do operador e registros oficiais;
- nunca armazenar áudio bruto por padrão;
- indicar claramente quando microfone estiver ativo no futuro.

### Regras especiais para vendas assistidas

Ao receber “faça uma venda de aproximadamente R$ 500 com produtos de maior estoque e PIX”, a Nabi deve:

1. esclarecer critérios ambíguos, como tolerância do valor e exclusões;
2. consultar somente produtos ativos e vendáveis;
3. respeitar estoque reservado, estoque mínimo, unidade e permissão de estoque negativo;
4. não escolher produtos apenas para atingir um valor se isso gerar quantidade absurda ou comercialmente inadequada;
5. informar por que cada produto foi selecionado;
6. usar preço retornado pelo serviço, nunca preço inventado;
7. exibir diferença entre o total e o valor solicitado;
8. identificar claramente Consumidor Final ou cliente escolhido;
9. preparar PIX como forma de pagamento, sem declarar recebimento antes da confirmação operacional;
10. apresentar o rascunho completo e perguntar se pode confirmar;
11. após “sim”, confirmar novamente apenas se o rascunho não mudou e se a sessão ainda for válida;
12. usar uma única chave idempotente para finalizar;
13. mostrar o resultado real da transação;
14. se houver Fiscal, informar apenas o estado real retornado pelo pipeline: preparado, enfileirado, autorizado, rejeitado, desconhecido ou pendente;
15. nunca dizer “enviado à SEFAZ” ou “autorizado” sem evidência do serviço fiscal.

### Mascote e experiência visual

O mascote deve ajudar sem bloquear a operação:

- pode ficar recolhido em um botão flutuante ou painel lateral;
- não deve cobrir preço, total, cliente, mensagens de erro ou botões de confirmação;
- deve possuir estados simples: disponível, pensando, aguardando confirmação, executando, concluído e bloqueado;
- animações precisam ser opcionais e leves;
- acessibilidade deve permitir uso integral por teclado e leitor de tela;
- a conversa escrita deve funcionar mesmo quando animações e voz estiverem desativadas;
- nenhuma animação pode ser usada como única evidência de sucesso.

### Atualizações futuras do modelo

- catálogo de provedores e modelos separado do executável principal;
- verificação de integridade do arquivo do modelo;
- licença e origem registradas;
- atualização manual ou controlada, nunca silenciosa durante uma venda;
- teste de compatibilidade antes de promover novo modelo;
- conjunto fixo de avaliações do NabiCode para comparar versões;
- rollback para o modelo anterior;
- ferramentas e regras permanecem versionadas pelo NabiCode, não pelo modelo.

### Portão de liberação da IA

Nenhuma fase mutável da Nabi deve chegar a cliente antes de existir evidência para:

- permissões;
- confirmação vinculada;
- idempotência;
- proteção contra prompt injection;
- privacidade;
- auditoria;
- falha segura;
- operação sem IA;
- testes adversariais;
- homologação manual no Windows.

## Ordem recomendada de continuidade

1. concluir a homologação manual do commit local `83c72af`;
2. corrigir, em novo commit local e somente após autorização, a separação entre “Revisar” e “Confirmar venda”;
3. usar as janelas equivalentes do Legacy como referência visual e operacional para o fluxo Qt, preservando serviços desacoplados e o backend como autoridade;
4. após confirmação bem-sucedida, completar a etapa de pós-venda e opções de impressão;
5. resolver botões provisórios do PDV Qt;
6. executar validação integral do NabiCode antes do push do conjunto;
7. continuar a migração Qt módulo por módulo;
8. iniciar a Fase 0 da IA Nabi como arquitetura isolada, sem interromper o PDV;
9. implementar primeiro a IA escrita e somente leitura;
10. avançar gradualmente para rascunhos, ações confirmadas e voz;
11. manter Fiscal/SEFAZ congelado durante missões comerciais/Qt/IA, salvo solicitação explícita e auditoria específica.

## Regra final para sucessores

### Checkpoint IA Nabi — integração Qt opcional e inerte

- commit: `cfd994b` — `feat: integra painel Nabi opcional ao Qt`;
- `ui_qt.app` aceita uma fábrica opcional de painel; o padrão permanece
  desligado e não importa nem cria componentes da Nabi;
- quando fornecido explicitamente, o painel entra em dock lateral fechável,
  móvel e flutuante; fábrica inválida falha sem deixar interface parcial;
- `UnavailableLanguageModelAdapter` representa ausência de modelo sem rede,
  arquivo, consulta ou auditoria inventada;
- nenhuma sessão, permissão ou ator é fabricado: sem sessão real, a solicitação
  falha antes de consultar o modelo ou qualquer ferramenta;
- `main_qt.py`, `services/__init__.py`, Fiscal/SEFAZ, licenciamento e banco não
  foram alterados; `.codex-remote-attachments/` foi preservado;
- validação: `42 passed`, `11 subtests passed`, `compileall` e
  `git diff --check` aprovados com o Python 3.14.7/PySide6 do projeto;
- próximo passo: composition root dedicado com sessão e auditoria reais,
  mantendo somente as três ferramentas Commercial de leitura; o modelo GGUF
  continua não baixado e nenhuma mutation está autorizada.

### Checkpoint IA Nabi — composição local somente leitura

- commit: `bf843b4` — `feat: compoe Nabi local somente leitura`;
- o composition root exige SecurityService, auditoria, CommercialQueryService e
  session_id reais fornecidos pelo chamador; nenhuma autoridade substituta é
  criada internamente;
- o provedor local aceita somente endpoint HTTP loopback validado e registra
  exclusivamente `produtos.pesquisar`, `produtos.consultar_estoque` e
  `clientes.pesquisar`, todas READ;
- existe composição indisponível sem rede que mantém os mesmos limites reais e
  falha antes de consulta/auditoria quando não há modelo;
- o composition root não importa banco, repositório, Fiscal, SEFAZ ou SQLite;
  nenhuma mutation, download de pesos ou ligação ao startup foi feita;
- validação: `47 passed`, `14 subtests passed`, `compileall` e
  `git diff --check` aprovados no runtime Qt real;
- próximo passo: fornecer sessão/auditoria reais no shell Qt integrado. Até isso
  existir, a flag permanece OFF e o painel não recebe ferramentas.

Não confundir automação inteligente com autoridade. A Nabi poderá planejar, consultar e operar ferramentas autorizadas, mas o NabiCode continuará sendo a fonte de verdade. Backend, permissões, validações, confirmação humana, transações e auditoria decidem o que realmente pode acontecer.

## Checkpoint FICHÁRIO — chave pública e ativação física

Estado em `2026-08-23`, branch `codex/integracao-nabi-pdv`:

- correção do runtime Tcl/Tk do portátil: `3db90b3`;
- tela restrita de ativação anterior ao banco/serviços comerciais: `33fc095`;
- cópia explícita do código da máquina: `61bb414`;
- teste de segredos distingue certificado público de chave privada: `e4af32c`;
- catálogo público incorporado: `a7d5386`, identificador `nabicode-prod-2026-01`,
  SHA-256 `D6E58A832213E7A0079113AD5B3B3F0FC50D4C411B36FCF6DF315FC599913718`;
- licença externa de homologação verificada para edição `FICHARIO`, máquina real,
  recursos `commercial`, `fichario`, `financial` e `qt`, sem capacidade fiscal,
  validade até `2033-08-01` e tolerância de dez dias;
- regressão conjunta: `183 passed`, `4 subtests passed`; `compileall` e
  `git diff --check` aprovados;
- portátil reconstruído e inspecionado: catálogo público, Tcl/Tk e
  `qwindows.dll` presentes; nenhuma chave privada, segredo ou licença embutida;
- SHA-256 do executável: `1CA9E7417DD021B272F886FD94A99B0BC45F9B283FDB24ABA1B68C7197D02BC6`;
- ativação física retornou código 0 e a reabertura avançou para
  `Entrar no NabiCode Fichario`, comprovando licença ativa;
- decisão posterior do proprietário: a edição FICHÁRIO licenciada não exige
  usuário/senha; `c242b87` reutiliza a sessão local oficial do NabiCode somente
  depois do portão de licença e preserva permissões internas;
- validação dessa mudança: `25 passed`, `compileall` e `git diff --check`;
- portátil reconstruído, SHA-256
  `3131F8A51D97340FFBFA071F801C0EF81BD4DDDD937FE63B432076FB3F228DE9`,
  e homologado fisicamente abrindo direto em `NabiCode Fichario`, sem login;
- chave privada e pasta externa de segredos não foram lidas, copiadas,
  versionadas ou empacotadas; nenhum instalador e nenhum push foram realizados.

## Checkpoint IA — consultas operacionais seguras ampliadas

Estado em `2026-08-23`, branch `codex/integracao-nabi-pdv`:

- implementação: `7929721bc90f619c733d862dcdb8ada2893cf555` — `feat: amplia consultas seguras da Nabi`;
- a Nabi passou a consultar, por ferramentas tipadas, crédito do cliente, estoque baixo, vendas do dia, recebimentos do dia, cobranças vencidas, resumo financeiro e fluxo de caixa;
- todas as consultas usam exclusivamente `CommercialQueryService` ou `FinancialQueryService`, sem SQL, conexão de banco ou serviço mutável entregue ao modelo;
- cada ferramenta exige a permissão `view` do módulo correspondente e a permissão é verificada novamente na execução;
- datas aceitam somente `AAAA-MM-DD`, períodos financeiros são limitados a 366 dias e listas são limitadas antes de entrarem no contexto do modelo;
- saídas foram minimizadas: não transportam CPF/CNPJ, telefone, endereço, e-mail, chave/protocolo fiscal, documento de título, referência financeira ou observações livres;
- o painel Qt ganhou renderização determinística para todas as novas consultas;
- `main_qt.py` injeta a fachada financeira somente quando ela existe; sua ausência mantém as ferramentas financeiras indisponíveis sem impedir a Nabi;
- Fiscal/SEFAZ, licenciamento, emissor, banco real e splash não foram alterados.

Evidências:

- suíte focada: `43 passed`, `15 subtests passed`;
- regressão Nabi/painel: `68 passed`, `15 subtests passed`;
- suíte consolidada IA + fachadas relacionadas: `123 passed`, `35 subtests passed`, zero falhas;
- `compileall` e `git diff --check`: aprovados.

## Checkpoint Fichário — separação assinada entre Nabi e Fiscal

- implementação: `ff672b0` — `feat: separa Nabi e Fiscal por licença`;
- criada a capacidade assinada `assistant`, independente de `fiscal`;
- uma licença com `qt + commercial + financial + assistant`, mas sem `fiscal`, permite PDV/Fichário e Nabi, mantendo workers e escritas fiscais bloqueados;
- sem `assistant`, o Qt não compõe ativação, runtime, painel ou modelo da Nabi;
- com `assistant` e sem `fiscal`, não são construídos `NFeImportRepository`, `NFeImportService`, rascunho XML ou botão de revisão de NF-e;
- revisão local de NF-e só é composta quando `assistant` e `fiscal` estão ambos assinados;
- alteração dos recursos assinados durante a execução encerra a Nabi e força reinício seguro, impedindo reativação acidental por troca de licença;
- código e tabelas fiscais podem permanecer instalados, mas não são inicializados pela composição Fichário;
- validação focada: `21 passed`;
- regressão consolidada de licenciamento + emissor + Nabi + PDV: `267 passed`, `37 subtests passed`, zero falhas;
- `compileall` e `git diff --check`: aprovados.

Trilha paralela autorizada: concluir a edição Fichário com entrada/menu Qt próprios, Clientes, Ficha, crediário, Recebimentos, comprovantes e pacote, sem alterar a implementação da Nabi deste checkpoint.

Próxima etapa coerente da IA: ampliar consultas orientativas somente onde houver fachada oficial e necessidade comprovada; ações de Caixa/Financeiro continuam proibidas até possuírem rascunho, confirmação reforçada, idempotência e auditoria próprios.

### Porta Nabi → pesquisa acessível de produtos

- implementação: `dab5624` — `feat: conecta Nabi a pesquisa segura de produtos`;
- a ferramenta tipada `interface.abrir_pesquisa_produtos` produz somente a intenção `OPEN_PRODUCT_SEARCH` e um termo opcional limitado a 100 caracteres;
- a intenção exige `produtos/view`, não recebe `product_id`, não consulta banco e não seleciona produto;
- o painel Qt, já de volta à thread da GUI, chama uma porta explícita do PDV exatamente uma vez;
- a janela acessível continua sendo a única responsável pela busca e somente uma seleção humana aceita transporta `product_id` real ao fluxo oficial;
- cancelamento não cria identidade; modo Produto avulso recusa a abertura; texto ambíguo nunca é promovido a produto;
- F2, botão manual, lista rápida e fluxo Quantidade → Preço permanecem preservados;
- validação focada: `48 passed`, `7 subtests passed`;
- regressão consolidada Nabi + pesquisa + PDV: `232 passed`, `37 subtests passed`, zero falhas;
- `compileall` e `git diff --check`: aprovados.

## Checkpoint independente — edição NabiCode FICHÁRIO

Estado em `2026-08-23`, worktree
`C:\Users\famil\Desktop\NabiCode-QT-Homologacao-5b9ff8f\NabiCode-QT-Fichario-codex`,
branch `codex/edicao-fichario`, derivada da integração limpa `b3787e2`:

- implementação: `76d83f4` — `feat: adiciona edicao NabiCode Fichario`;
- `LicenseEdition.FICHARIO` e política fail-closed exigem edição assinada
  `FICHARIO`, recursos assinados `fichario`, `qt`, `commercial` e `financial`, e
  recusam capacidade `fiscal`; configuração local não promove a edição;
- composição e entrada próprias em `main_fichario_qt.py` iniciam somente banco,
  serviços Commercial, autenticação e shell FICHÁRIO; não iniciam Nabi,
  FiscalWorker, outbox, SEFAZ, certificado ou importação de NF-e;
- os dados mutáveis ficam isolados em
  `%APPDATA%\NabiCode\Fichario\Producao` ou `Teste`, fora de `Program Files`;
- menu Qt simples entrega PDV comercial/não fiscal, clientes, cadastro/edição,
  ficha/histórico, recebimentos, backup/restauração e informações locais;
- cliente e recebimento usam `customer_id` real e portas oficiais. Recebimento
  exige permissão, revisão humana explícita e uma única chamada a
  `CommercialActionService.receive_customer_payment`;
- Enter, Shift+Enter, Esc e auto-repeat estão cobertos no diálogo de recebimento;
- backup/restauração reutilizam `DatabaseMaintenanceService`: cópia SQLite
  consistente, `integrity_check`, chaves estrangeiras, tabelas obrigatórias e
  schema 20; restauração exige PDV fechado, permissão e digitação de
  `RESTAURAR`, cria cópia anterior e recupera automaticamente em falha;
- o backup inclui o banco operacional (clientes/fichas, produtos, movimentações,
  parcelas, recebimentos, configurações e auditoria). Não inclui build, logs,
  credenciais/certificados, chave privada, `.nabilic` ou estado protegido;
- spec PyInstaller, script de build e Inno Setup próprios reutilizam o pipeline
  offline aprovado, mas produzem artefato/instalação separados e excluem IA,
  emissor e componentes fiscais. Nenhum artefato ou release foi gerado;
- documentação operacional: `docs/FICHARIO_BACKUP_RESTAURACAO.md`.

Evidências automatizadas:

- testes focados da edição, Qt e backup/restauração: `24 passed`;
- regressão relacionada de licenciamento, Commercial, banco e Qt:
  `262 passed`, `343 subtests passed`;
- ida e volta de backup usa somente banco temporário de TESTE e comprova dados,
  corrupção, schema incompatível, caminho ausente, falha intermediária e
  recuperação segura;
- `compileall`, validação do manifesto e `git diff --check`: aprovados.

Build futuro, somente depois da integração final:

1. validar: `python build_tools\build_fichario.py validate`;
2. gerar aplicativo: `python build_tools\build_fichario.py app`;
3. gerar instalador, informando o compilador existente:
   `python build_tools\build_fichario.py installer --iscc "C:\caminho\ISCC.exe"`;
4. para ambos em sequência:
   `python build_tools\build_fichario.py all --iscc "C:\caminho\ISCC.exe"`.

Pendências deliberadas:

- integrar esta branch somente após reconciliar a mudança paralela dos gates
  `assistant`/`fiscal`; não transportar nem sobrescrever `licensing/gate.py` ou
  `main_qt.py` desta trilha;
- executar a suíte global, gerar o artefato local e testar instalação, atualização,
  ativação FICHÁRIO e reinício em máquina Windows de homologação;
- homologar visualmente clientes, ficha, recebimento/comprovante, PDV, backup e
  restauração. Impressão física depende de impressora disponível;
- confirmar no artefato instalado, por inspeção de processos e banco de TESTE,
  que nenhum worker/arquivo/fila fiscal é iniciado ou criado;
- nenhum push foi realizado.

## Checkpoint FICHÁRIO — paridade operacional do projeto raiz

Estado em `2026-08-23`, branch `codex/integracao-nabi-pdv`:

- implementação: `217016d` — `feat: alinha edicao Fichario ao fluxo raiz`;
- tela inicial substituiu a lista simples por cards no padrão visual NabiCode e
  restaurou total de fichas, clientes em dia, clientes devendo, alerta com mais
  de 60 dias e total a receber, usando `DashboardRepository` como autoridade;
- lista de clientes restaurou as cores Legacy: branco sem saldo, amarelo acima
  de R$ 0,005 até R$ 500 e vermelho acima de R$ 500; essas cores são faixas
  visuais de saldo e não inventam atraso;
- número da ficha voltou a ser o primeiro campo, com destaque e preenchimento
  pela configuração canônica `proxima_ficha`; pesquisa inclui ficha, código,
  nome, CPF, RG, telefone e endereço;
- PDV da edição FICHÁRIO ficou exclusivamente em produto avulso: pesquisa,
  catálogo e F2 ficam indisponíveis e uma política própria também recusa
  `product_id` fora da GUI;
- compra do FICHÁRIO exige uma ficha real; Consumidor Final é recusado na
  política da edição antes da persistência;
- botão `IMPORTAR FICHÁRIO ANTIGO` reutiliza `MySQLMigrationService`, separado
  da restauração `.db` produzida pelo próprio NabiCode; fecha o PDV antes da
  operação, analisa o `.sql`, apresenta prévia, exige confirmação e cria backup
  automático antes da escrita;
- decisão expressa do proprietário para a primeira importação externa: importar
  cadastro, número da ficha e saldo atual, sem movimentações históricas antigas;
  compras e recebimentos novos passam a formar o histórico no NabiCode;
- backup real auditado sem alteração:
  `C:\Users\famil\Desktop\bk_fichario_2026_08_01.sql`, SHA-256
  `d236c2ef757d8698cc15ed55ff8454dcacdfb9fcb6a4a07edad9059e0f08aebf`;
  reconhecidos 4.956 clientes, 32.410 vendas e 167.013 recebimentos, sem ficha,
  código ou CPF duplicado;
- prova em banco temporário: primeira execução inseriu 4.956 fichas únicas com
  saldo total R$ 890.654,35, zero movimentos antigos e zero produtos; segunda
  execução inseriu zero e atualizou as mesmas 4.956 fichas, comprovando
  idempotência; nenhum banco real foi usado;
- validação consolidada: `163 passed`, `7 subtests passed`; `compileall` e
  `git diff --check` aprovados;
- nenhum instalador e nenhum push foram realizados.

Próximo passo: abrir o FICHÁRIO pelo código atual para homologação visual dos
cards, clientes, ficha, PDV avulso e prévia do importador. Não executar a
importação no banco de produção antes da aprovação visual e de um backup manual.

### Otimização de Clientes e Recebimentos

- implementação: `fcb455e` — `perf: acelera clientes e recebimentos do Fichario`;
- removido o padrão N+1 que consultava detalhes individualmente para centenas
  de clientes; a projeção agora carrega os IDs ordenados e todos os detalhes em
  lote, preservando a ordem e os IDs reais;
- Clientes abre inicialmente 60 registros e pesquisa até 200 após debounce;
  Receber abre 100 e filtra por ficha ou nome enquanto o operador digita;
- busca mantém ficha exata como prioridade; prefixo de nome completo e início
  de qualquer palavra do nome têm precedência sobre ocorrência interna; dentro
  da mesma faixa de relevância, os nomes permanecem em ordem alfabética;
- tela principal mantém somente Vendas, Clientes/Fichas e Receber como cards;
  importação, backup, restauração e informações ficam no menu `Sistema`;
- card `PDV COMERCIAL / NÃO FISCAL` foi renomeado para `VENDAS`;
- Clientes ganhou escolha persistente de tamanho de letras entre 13 e 21,
  mantendo 15 como padrão legível;
- regressão consolidada: `165 passed`, `7 subtests passed`; validação final da
  busca/telas: `36 passed`; `compileall` e `git diff --check` aprovados;
- estresse temporário com 5.000 clientes: cadastro 0,58 s, tela Clientes com 60
  registros 0,066 s, Receber com 100 registros 0,038 s, ficha exata 0,0095 s e
  nome parcial 0,0125 s;
- 100 vendas avulsas vinculadas concluídas em 4,60 s e 100 recebimentos em
  1,74 s; repetição de checkout não duplicou venda, saldos ficaram exatos e
  `integrity_check` foi aprovado;
- banco fisicamente marcado TESTE, somente leitura: 4.957 clientes, primeiros
  60 em 0,0054 s, nome parcial em 0,0021 s e integridade aprovada;
- banco de Produção não foi acessado e nenhum push foi realizado.

### Central do sistema, backup diário e acessibilidade

- implementação: `8598aa1` — `feat: adiciona central de sistema e backup diario`;
- o card visível `MENU DO SISTEMA` abre uma central com backup imediato,
  restauração, importação do Fichário antigo, preferências e informações; o menu
  nativo superior permanece como acesso alternativo;
- backup diário é opcional, executado uma vez por data e somente grava
  `backup/last_success` depois que `DatabaseMaintenanceService` cria e valida a
  cópia SQLite, schema, tabelas e chaves estrangeiras;
- o proprietário escolhe a pasta de destino por seletor do Windows, inclusive
  pasta sincronizada pelo OneDrive; backup manual, automático e restauração
  passam a usar a mesma pasta configurada;
- falha de escrita ou validação não marca o dia como concluído e apresenta aviso;
- tamanho global de letras configurável entre 13 e 21, persistido também para
  Clientes e Fichas;
- testes concorrentes de cadastro: `6 passed`, `5 subtests passed`; testes Qt,
  Fichário e manutenção separados: `27 passed`; `compileall` e
  `git diff --check` aprovados;
- uma execução monolítica misturando PySide6 e o teste concorrente SQLite
  abortou no runtime Python 3.14, sem asserção funcional; os mesmos grupos foram
  repetidos em processos separados e aprovados;
- nenhum push e nenhum instalador foram realizados.

### Recebimento revisado, confirmado e imprimível

- implementação: `d3248ff` — `fix: separa confirmacao e comprovante do recebimento`;
- `Revisar recebimento` não persiste: cria uma revisão visível com ficha,
  cliente, valor, forma, data, saldo antes e saldo restante;
- `CONFIRMAR RECEBIMENTO` é uma segunda ação explícita e é a única que chama o
  serviço financeiro; alterações posteriores invalidam a revisão e escondem a
  confirmação;
- auto-repeat continua bloqueado, Shift+Enter retorna por campos ativos e duplo
  clique/Enter não pode registrar duas vezes durante a gravação;
- corrigido o erro manual `tuple.index(x): x not in tuple`, causado pela entrada
  dinâmica do botão Confirmar no fluxo de teclado;
- após commit confirmado, o diálogo oficial mostra o recibo e oferece
  `Imprimir recibo`, `Salvar PDF` e `Fechar`, reutilizando `ReceiptService`,
  `PrintingService` e `PDFDocumentService`; essas ações documentais não repetem
  o recebimento;
- opções de fonte ampliadas de 12 a 30; o controle principal permanece na tela
  Clientes e Fichas e destaca especialmente pesquisa, número da ficha e tabela;
- validação final: `31 passed`; `compileall` e `git diff --check` aprovados;
- nenhum push e nenhum instalador foram realizados.

### Cards do Fichário como filtros de clientes

- implementação: `e2c2a49` — `feat: filtra clientes pelos cards do Fichario`;
- os cinco cards do resumo são botões acessíveis e abrem Clientes e Fichas já
  limitado à situação escolhida: todas as fichas, em dia, devendo sem alerta,
  atrasados há mais de 60 dias ou todos com saldo a receber;
- a classificação reutiliza exatamente a mesma regra e a mesma data-limite do
  resumo, evitando divergência entre o número mostrado e a relação aberta;
- a janela identifica visualmente o filtro ativo e mantém pesquisa por ficha,
  código, nome, documento, telefone e endereço dentro daquele grupo;
- apenas `customer_id` real atravessa a fronteira Commercial; a interface não
  consulta o banco diretamente e o carregamento continua paginado em 60/200;
- validação final: `39 passed`; `compileall` e `git diff --check` aprovados;
- nenhum push e nenhum instalador foram realizados.

### Identificação por endereço e escopo visível do backup

- implementação: `df92bd8` — `feat: destaca endereco e escopo do backup no Fichario`;
- Clientes e Fichas passou a exibir, na ordem operacional solicitada: Ficha,
  Nome, Saldo devedor, Endereço e Telefone; nome e endereço também possuem dica
  completa para diferenciar homônimos;
- a ficha aberta por Enter ou duplo clique mostra endereço e telefone no topo;
- as confirmações de backup e restauração enumeram os dados do banco preservados:
  clientes, fichas, endereços, telefones, saldos, vendas, recebimentos, parcelas,
  históricos e configurações do banco;
- pasta de backup e tamanho das letras continuam preferências locais da máquina,
  evitando que uma restauração de outro computador troque silenciosamente o
  destino configurado, inclusive uma pasta do OneDrive;
- teste de ida e volta comprova o escopo operacional completo; validação final:
  `36 passed`, `compileall` e `git diff --check` aprovados;
- nenhum push e nenhum instalador foram realizados.

### Lista ampliada e identificação persistente de homônimos

- implementação: `dc69d39` — `feat: amplia lista e fixa identificacao do cliente`;
- a lista final usa Ficha, Nome, Saldo devedor, CPF e Telefone; o endereço saiu
  da coluna para reduzir ruído e continua disponível na ficha completa;
- selecionar qualquer cliente mantém abaixo da tabela uma faixa fixa com ficha,
  nome, endereço e telefone, sem depender do atraso ou desaparecimento da dica
  temporária do mouse; a dica sobre o nome foi preservada como atalho adicional;
- janela principal passou a 1220x720 e Clientes e Fichas a 1180x720, com mínimos
  maiores e sem obrigar modo de tela cheia;
- validação final: `31 passed`, `compileall` e `git diff --check` aprovados;
- nenhum push e nenhum instalador foram realizados.

### Lista essencial e detalhes adaptáveis do cliente

- implementação: `c19db55` — `feat: simplifica lista e expande dados selecionados`;
- a tabela foi reduzida aos três campos essenciais para leitura rápida: Ficha,
  Nome e Saldo devedor;
- a faixa fixa inferior recebeu fonte maior e apresenta ficha/nome seguidos por
  Endereço, CPF e Telefone; dados vazios são omitidos e o próximo dado ocupa o
  espaço imediatamente, sem colunas ou lacunas artificiais;
- a dica de endereço sobre o nome e a ficha completa por Enter/duplo clique
  permanecem disponíveis;
- validação final: `32 passed`, `compileall` e `git diff --check` aprovados,
  incluindo regressão específica para CPF ou telefone ausente;
- nenhum push e nenhum instalador foram realizados.

### Comportamento de compras na lista de clientes

- implementação: `7d7bb72` — `feat: exibe comportamento de compras dos clientes`;
- cabeçalho `NABICODE FICHARIO` e subtítulo foram centralizados;
- a lista mantém Ficha, Nome e Saldo devedor e usa o espaço restante para
  Compras sem atraso, Compras com atraso e Quantidade de atrasos;
- a regra é a mesma do Legacy: uma compra confiável sem parcela atrasada entra
  em sem atraso; compra com pelo menos uma parcela paga atrasada ou vencida em
  aberto entra em com atraso; quantidade soma essas parcelas atrasadas;
- compras antigas sem datas confiáveis não são inventadas em uma categoria e
  permanecem indicadas por dica explicativa;
- cálculo em lote evita N+1: 60 clientes no banco físico de teste foram
  classificados em aproximadamente `0,013 s`;
- validação final: `45 passed`, `compileall` e `git diff --check` aprovados;
- nenhum push e nenhum instalador foram realizados.

#### Legibilidade dos cabeçalhos

- correção: `2a3c53c` — `fix: torna cabecalhos de atrasos legiveis`;
- títulos longos foram divididos em duas linhas: Compras/sem atraso,
  Compras/com atraso e Parcelas/atrasadas;
- larguras mínimas, alinhamento central e altura do cabeçalho impedem o corte
  observado manualmente; cada título possui dica com a definição da métrica;
- validação: `25 passed`, `compileall` e `git diff --check` aprovados;
- nenhum push e nenhum instalador foram realizados.

### Requisito obrigatório antes do EXE final — atualização segura

- o executável FICHÁRIO deve expor uma porta de atualização assinada e validada,
  reutilizando os serviços de pacote já existentes, sem edição manual de código;
- a atualização deve substituir somente arquivos imutáveis do programa, criar
  backup validado antes da troca e preservar banco, licença, PDFs, logs e backups
  na área persistente fora de `Program Files`;
- falha de assinatura, versão, integridade, backup ou aplicação deve cancelar ou
  reverter a atualização; nenhum atualizador final deve ser publicado antes dos
  testes físicos de reinstalação e atualização no Windows;
- este requisito está planejado, mas ainda não foi declarado concluído nem deve
  ser confundido com a geração atual do EXE de homologação.

### Checkpoint FICHÁRIO — atualização assinada R20 e instalador final

- implementação inicial: `78740e1` — porta de atualização Ed25519, preparação,
  comprovante de estado, aplicação externa e recuperação;
- build visível: `a8d7af2` — revisão `20`, data e hora do build centralizadas no
  rodapé e preservadas também em Informações;
- endurecimento: `4fbeeff` — helper elevado pelo UAC, instalação derivada do
  próprio executável, estado e caminhos confinados, pacote/assinatura/hash
  revalidados, staging verificado e rollback protegido dentro da instalação;
- teste real em cópia: pacote assinado atualizou `2.5.1 R19` para `2.5.1 R20`,
  alterou o build de `23/08/2026 21:09:51` para `23/08/2026 21:46:27`, aplicou
  `1.208` arquivos e preservou o cliente marcador no banco;
- chave privada Ed25519 usada apenas para homologação foi apagada depois da
  assinatura; o artefato contém somente catálogo público, Qt/Tcl/Tk e nenhuma
  chave privada ou banco de cliente;
- validação automatizada do endurecimento: `27 passed`, além dos `33 passed`
  obtidos na auditoria focada; `compileall` e `git diff --check` aprovados;
- suíte completa final após alinhar a revisão: `1.877 passed`, `1 skipped`,
  `409 subtests passed`, zero falhas;
- atualização homologada:
  `build_output/fichario/updates/NabiCode_Fichario_ATUALIZACAO_2_5_1_R20_HOMOLOGACAO.zip`,
  SHA-256 `A784E61BBD6AB88F2BD61CD65CB03978085F4437FBD02E762BCED70158745B2D`;
- instalador final:
  `build_output/fichario/installer/NabiCode_Fichario_2.5.1_Setup_Offline.exe`,
  `120.311.926` bytes, SHA-256
  `0AF44032F21D3BEB2021964D788FE6449206057D46B6A762257C8DC2229ECF5A`;
- pendência física: confirmar a elevação UAC e a atualização dentro de uma
  instalação real em `Program Files`; o motor e o roundtrip em cópia gravável
  estão comprovados. Nenhum push foi realizado.

### Integração final local — FICHÁRIO R20 + checkpoints Nabi

- merge local: `62492f8`, pais `323e601` (FICHÁRIO R20) e `b10928a`
  (IA opcional/composição somente leitura); históricos preservados;
- a composição avançada já existente foi mantida: autenticação real, runtime
  llama.cpp local, rascunhos de venda, recebimento de compras e entrada por XML
  continuam separados do fluxo oficial e das confirmações humanas;
- o novo dock opcional aceita serviço oficial ou fábrica explícita, nunca ambos;
  padrão sem Nabi continua sem painel, rede ou dependência do modelo;
- composition root básico registra exatamente as três consultas READ iniciais,
  com endpoint loopback, sessão e auditoria reais obrigatórias;
- todas as suítes Nabi/painel após a resolução: `118 passed`, `38 subtests`;
- suíte completa integrada: `1.888 passed`, `1 skipped`, `412 subtests passed`,
  zero falhas; `compileall` e `git diff --check` aprovados;
- modelo e runtime permanecem fora do Git/instalador. A homologação técnica em
  TESTE já está documentada, mas a ativação visual com licença/sessão reais e a
  decisão de redistribuição continuam pendentes. Nenhum push foi realizado.

### Auditoria fiscal adversarial — matriz sem desempate silencioso

- auditoria confirmou que produção continua corretamente bloqueada: faltam
  homologação SEFAZ real acompanhada e dossiê físico com autorização, consulta,
  DANFE, rejeição, eventos, contingência, reinício e pacote contábil;
- lacunas declaradas de escopo (matriz tributária parcial, UFs/modelos não
  homologados, NFS-e/IBPT/consultas cadastrais) continuam bloqueadores quando
  aplicáveis; testes automatizados não equivalem a homologação externa;
- correção offline: `364ca7d` — `fix: bloqueia ambiguidade na matriz fiscal`;
- cadastro recusa regras ativas de mesma precedência com CEST sobreposto dentro
  do mesmo emitente/destino/regime/NCM/operação, em transação imediata;
- bancos antigos ambíguos falham fechados na resolução e informam IDs; `id DESC`
  não decide mais qual tributação vence;
- nenhuma alíquota, CST/CSOSN, prazo, certificado, produção ou comunicação SEFAZ
  foi alterada;
- validação fiscal focada: `131 passed`, `10 subtests passed`, zero falhas;
  auditoria ampliada havia aprovado `157 passed`; `compileall` e
  `git diff --check` aprovados;
- próxima pendência auditável: autoria/versionamento imutável das aprovações
  contábeis e enforcement documentado da contingência. Não implementar regra
  jurídica sem fonte oficial e decisão explícita de escopo.

#### Bloqueio adversarial adicional — prazo de contingência NFC-e

- o MOC 7.0, Anexo IV, publicado no Portal Nacional da NF-e, informa que a
  transmissão da NFC-e emitida em contingência offline deve ocorrer depois de
  superado o problema e, no texto vigente consultado em 23/08/2026, até o final
  do primeiro dia útil subsequente à emissão;
- o código atual registra `emissão + 24 horas` e apenas marca atraso. Esse cálculo
  não demonstra o calendário oficial nem garante transmissão imediata após a
  recuperação; portanto não serve como evidência suficiente de conformidade;
- fonte primária:
  `https://www.nfe.fazenda.gov.br/PORTal/exibirArquivo.aspx?conteudo=fMhAfsQfE+M%3D`;
- decisão de segurança: não alterar prazo por aproximação e não liberar
  contingência em produção. Antes, criar política versionada por modelo/UF,
  calendário aplicável, escalonamento auditável e testes com fonte normativa;
- o MOC 7.0, Anexo III, também exige transmissão das NF-e em contingência
  imediatamente após cessar a falha, observando a legislação. Modelo 55 não deve
  reutilizar automaticamente a regra do modelo 65.

### Checkpoint fiscal offline — histórico técnico das regras

- implementação: `b177fdb` — `feat: versiona historico tecnico das regras fiscais`;
- schema `20 → 21` usa o backup pré-migração existente e cria
  `fiscal_tax_rule_revisions` append-only, com revisão única por regra, payload
  canônico, hash encadeado, ator técnico, motivo e data/hora;
- regras antigas recebem backfill idempotente `LEGACY_SEM_TRILHA` e
  `NAO_INFORMADO`, sem inventar autor ou aprovação;
- criação, alteração e desativação gravam a regra e a revisão na mesma
  transação; falha no journal reverte tudo; concorrência não duplica revisão;
- triggers recusam UPDATE/DELETE normal no histórico e a verificação detecta
  adulteração parcial da cadeia;
- IDs e API existentes foram preservados; backup e atualizador Fichário foram
  alinhados ao schema 21, com teste que impede retorno acidental ao schema 20;
- limite probatório explícito: SHA-256 encadeado comprova integridade técnica
  local, não identidade jurídica, assinatura ou não repúdio contra administrador
  com controle total do banco/código;
- validações: `37 passed` no conjunto mínimo schema/Fichário, `148 passed` e
  `10 subtests` na regressão fiscal afetada; suíte completa final:
  `1.898 passed`, `1 skipped`, `412 subtests passed`, zero falhas;
- nenhuma alíquota, CST/CSOSN, certificado, produção ou comunicação SEFAZ foi
  alterada. O próximo passo é ligar `actor` à sessão autenticada real sem
  confundir operador do sistema com responsável contábil declarado.

### Correção de integração — entradas alinhadas ao schema 21

- implementação: `7eadd38` — `fix: alinha entradas ao schema fiscal 21`;
- a auditoria pós-migração encontrou `main_qt.py` e `fichario/runtime.py` ainda
  inicializando o banco com a constante antiga `20`, apesar de o schema oficial
  já estar em `21`;
- ambas as entradas agora exigem schema `21`, e um teste de regressão impede que
  Qt ou FICHÁRIO retornem silenciosamente à versão anterior;
- validação focada: `25 passed`; `compileall` e `git diff --check` aprovados;
- nenhuma regra fiscal, dado real ou comunicação SEFAZ foi alterada.

### Checkpoint IA Nabi — confirmação mutável opaca e de uso único

- implementação: `7b798bb` — `fix: torna confirmacoes da Nabi de uso unico`;
- a auditoria adversarial comprovou que o PDV ignorava o objeto de autorização e
  que Compras/entrada de NF-e aceitavam objetos fabricáveis fora do serviço de
  confirmação;
- o broker agora emite um grant opaco, temporário e de uso único, vinculado ao
  rascunho, fingerprint, operação, usuário, sessão e capacidade exigida;
- PDV, recebimento de compra e entrada local por NF-e recusam ausência, objeto
  manual, objeto falso com método `consume`, operação/sessão divergente e replay;
- todas as dependências e conteúdos verificáveis são revalidados antes de o grant
  ser consumido; as chaves idempotentes oficiais foram preservadas;
- validação consolidada do checkpoint: `132 passed`, `38 subtests passed`;
  `compileall` e `git diff --check` aprovados;
- nenhuma venda é finalizada pela Nabi: venda confirmada apenas carrega o
  rascunho no PDV e continua exigindo Pagamentos e confirmação no fluxo oficial.

### Checkpoint fiscal offline — ator técnico autenticado

- implementação integrada: `18dd14f` (origem `58ca6ad`) — `fix: vincula
  historico fiscal a sessao autenticada`;
- a identidade vem de `SecurityService.session.user.username`, preenchida pelo
  login real e invalidada por logout ou expiração por inatividade;
- `FiscalTaxRuleService` recebe uma porta confiável `actor_provider`; criação,
  alteração e desativação exigem identidade não vazia antes da transação;
- a API de mutação não aceita `actor` livre, e `approved_by` continua separado
  como responsável contábil declarado;
- consultas e resolução permanecem independentes de sessão; backfill histórico
  continua honesto como `LEGACY_SEM_TRILHA`/`NAO_INFORMADO`;
- validação na trilha de origem: `36 passed`; regressão fiscal relacionada:
  `404 passed`, `10 subtests passed`; `compileall` e `git diff --check` aprovados;
- nenhuma regra tributária, XML, outbox, transmissão ou ambiente SEFAZ mudou.

### Documento operacional — dossiê de homologação fiscal Bahia

- documento integrado: `97853f5` (origem `2bde4ce`) —
  `docs/MODELO_DOSSIE_HOMOLOGACAO_FISCAL_BAHIA.md`;
- o modelo separa NF-e/NFC-e, evidências automatizadas e homologação física e
  mantém todos os campos reais como pendentes até coleta acompanhada;
- o documento não afirma aprovação, não fabrica protocolo e não desbloqueia
  produção; deve ser preenchido apenas com evidência verificável da SEFAZ/BA.

### Validação consolidada após os checkpoints de segurança

- suíte completa da branch integrada: `1.909 passed`, `1 skipped`, `2 warnings`,
  `412 subtests passed`, zero falhas;
- os avisos são um `PytestCollectionWarning` de classe auxiliar e uma
  depreciação externa do `BrazilFiscalReport`; nenhum representa falha funcional;
- `compileall` dos módulos existentes e `git diff --check` aprovados;
- produção fiscal continua bloqueada e nenhum push foi realizado.

### FICHÁRIO R21 — relógio do Windows e exclusão cadastral segura

- implementação: `8708891` — `feat: adiciona relogio e exclusao segura ao
  Fichario`; revisão: `082ff3c` — `build: avanca Fichario para revisao 21`;
- o rodapé agora lê `QDateTime.currentDateTime()` e atualiza a cada segundo,
  exibindo somente a data e hora correntes do Windows; a identificação de
  build não é mais mostrada na interface (`f125783`);
- a área Clientes oferece `Excluir cadastro vazio [Del]`, exige permissão de
  edição e confirmação digitada `EXCLUIR` com ficha e nome visíveis;
- Consumidor Final, saldo devedor ou qualquer vínculo comercial impedem a
  exclusão. Somente cadastro sem movimentos pode ser removido, junto de eventos
  puramente cadastrais; dados financeiros e históricos comerciais são preservados;
- validação focada: `67 passed`, `5 subtests passed`; suíte completa final:
  `1.912 passed`, `1 skipped`, `2 warnings`, `412 subtests passed`, zero falhas;
- instalador offline R21 reconstruído em
  `build_output/fichario/installer/NabiCode_Fichario_2.5.1_Setup_Offline.exe`,
  `120.327.275` bytes, SHA-256
  `C06EDE2FD7ACB7F169E839A5709F0FB5519670E013555C1762369AFBF6F5C6D3`;
- a dependência inicial indevida da IA no pacote Fichário foi removida em
  `6bb266a`; o executável reconstruído permaneceu aberto no teste de fumaça;
- auditoria do artefato confirmou revisão `21`, Qt `qwindows.dll`, Tcl/Tk e
  ausência de chave privada/licença de cliente; o único `.pem` incluído é o
  catálogo público de autoridades certificadoras da dependência `certifi`;
- não foi criado ZIP R20→R21: a chave temporária que assinou a R20 foi apagada
  corretamente. A R20 recusaria outra assinatura. O R21 deve receber uma chave
  permanente de atualização por cerimônia segura para permitir R21→R22 sem
  reconstruir instalador. Nenhum bypass de assinatura foi introduzido.

### Checkpoint IA Nabi — cadastro assistido de clientes

- implementação: `88ece83` — `feat: adiciona cadastro assistido de clientes na Nabi`;
- a ferramenta tipada `clientes.preparar_cadastro` apenas cria rascunho em
  memória, com ficha explícita, dados revisáveis e SHA-256 canônico; nenhuma
  gravação ocorre durante a conversa ou preparação;
- execução exige permissão real `clientes/create`, revisão, confirmação
  reforçada temporária vinculada a usuário, sessão, rascunho e fingerprint, e
  autorização opaca de uso único;
- a mutação usa `CustomerApplicationService` e `CustomerRegistrationService`;
  o modelo não recebe repositório, conexão ou acesso direto ao banco;
- `assistant_operation_journal` protege a criação na mesma transação: repetição
  da mesma chave e conteúdo devolve o mesmo cliente, conteúdo divergente é
  recusado e rollback não deixa cliente nem diário pendente;
- ficha concorrente é revalidada antes da gravação; código omitido recebe valor
  determinístico ligado à operação, sem depender do relógio;
- o painel mostra ficha, nome, documentos, contato, endereço e limite para
  revisão e informa o identificador somente depois do commit oficial;
- validação: `138 passed`, `43 subtests passed` na regressão IA/Clientes e `47
  passed`, `5 subtests passed` na composição/painel/idempotência; `compileall` e
  `git diff --check` aprovados; após reunir Produtos/Estoque e o hub, a regressão
  conjunta final aprovou `161 passed` e `43 subtests passed`;
- nenhuma importação Fiscal/SEFAZ foi adicionada; nenhum push foi realizado;
- pendência física: homologar com usuário real autorizado e confirmar visualmente
  revisão, recusa, ficha concorrente e repetição após falha simulada no Windows.

### Checkpoint IA Nabi — recebimento assistido de clientes

- implementação: `52d22dc` — `feat: adiciona recebimento assistido de clientes`;
- `clientes.preparar_recebimento` aceita exclusivamente `customer_id` real,
  valor decimal textual, forma fechada, data ISO e observação limitada;
- a preparação consulta o serviço oficial de Clientes e mostra ficha, nome,
  saldo anterior, valor recebido e saldo restante; não grava pagamento, parcela,
  movimento, caixa ou financeiro;
- valor zero, valor acima do saldo, forma desconhecida, data inválida e cliente
  sem dívida são recusados antes da confirmação;
- a execução exige `financeiro/pay`, usuário e sessão reais, confirmação reforçada
  temporária, fingerprint exato e autorização opaca de uso único;
- imediatamente antes da mutação, o saldo é consultado novamente; qualquer
  mudança invalida o rascunho e exige nova revisão;
- o fluxo usa `CommercialActionService`, `NabiCodeCustomerReceiptGateway` e
  `FinanceiroService`; a IA não recebe banco, repositório nem serviço fiscal;
- `assistant_operation_journal` registra `CUSTOMER_RECEIPT` na mesma transação;
  repetição da mesma chave/conteúdo devolve o movimento original sem nova baixa
  nem novo evento, conteúdo divergente é recusado e falha reverte diário e saldo;
- painel Qt renderiza os valores determinísticos antes da revisão e informa o
  movimento somente depois do commit oficial;
- validação focada: `60 passed`; regressão IA/recebimentos: `143 passed`, `38
  subtests passed`; compatibilidade Commercial/Fichário: `25 passed`;
  regressão conjunta final com Dashboard: `172 passed`, `38 subtests passed`;
  `compileall` e `git diff --check` aprovados;
- nenhuma alteração Fiscal/SEFAZ e nenhum push; homologação manual com usuário e
  dados TESTE permanece necessária para foco, recibo/impressão e falha simulada.

### Checkpoint isolado — Relatórios comerciais Qt

- implementação de origem: `2c6b5b7` — `feat: adiciona relatorios comerciais no Qt`;
- `ReportReadPort`, `ReportApplicationService` e DTOs imutáveis transportam
  consultas, resumos, indicadores e exportações sem expor conexão ou SQL à GUI;
- `NabiCodeReportGateway` reutiliza o `ReportService` oficial para filtros,
  autorização, auditoria, totalização e exportação atômica CSV/XLSX/PDF;
- relatório `nfe` não é exposto pela fachada comercial; Central Fiscal,
  Fiscal/SEFAZ, XML e regras tributárias permanecem fora desse diálogo;
- Enter executa uma etapa, Shift+Enter retorna, auto-repeat é consumido, F5
  atualiza e Esc fecha somente o diálogo;
- validação na origem: `39 passed`; regressão relacionada: `293 passed`,
  `359 subtests passed`; `compileall` e `git diff --check` aprovados;
- pendência: composição global por sessão/permissão e homologação visual e das
  exportações no Windows, sem transportar o agendador Tk para a GUI Qt.

### Checkpoint isolado — Administração de Usuários Qt

- implementação de origem: `042c399` — `feat: adiciona administracao de usuarios no Qt`;
- `UserAdministrationService` é a única porta da GUI e reutiliza o
  `SecurityService`; identidade e autoridade vêm da sessão interna real;
- sessão ausente/expirada e operador sem `technical/users` falham fechados;
  ADMIN continua coberto pelo wildcard oficial;
- criação, edição, senha e ativação preservam PBKDF2, username imutável e a
  proteção que impede remover ou desativar o último administrador;
- a GUI não importa banco, repositório, Legacy, Fiscal ou SEFAZ e controla
  F3/F4/F5/Esc, Enter, Shift+Enter e auto-repeat;
- edição livre de perfis/permissões permanece deliberadamente fora do escopo
  para evitar escalada acidental;
- validação na origem: `19 passed`; regressão relacionada: `182 passed`,
  `2 subtests passed`; `compileall` e `git diff --check` aprovados;
- pendências: composição/menu e homologação manual no Windows; qualquer editor
  visual de capacidades exige decisão explícita posterior.

### Integração isolada — módulos administrativos Qt do projeto principal

- branch/worktree: `codex/principal-modulos-qt`, derivada da integração limpa
  `6bb266a`, sem alterar `codex/integracao-nabi-pdv`;
- Clientes Qt integrado por merge normal `6bdfeeb`, preservando a versão atual
  do FICHÁRIO R21 quando ela já era um superset funcional do checkpoint;
- Caixa Qt integrado por merge normal `8cdf2f1`;
- Financeiro Qt integrado por merge normal `097d267`;
- Relatórios Qt integrado por merge normal `81159d7`;
- Usuários e Permissões Qt integrado por merge normal `f66c66c`;
- nenhum `main_qt.py`, painel Nabi, Fiscal/SEFAZ, instalador, atualizador,
  licenciamento ou banco real foi alterado nesta integração;
- regressão combinada: `107 passed`, `5 subtests passed`; `compileall` de
  administration/commercial/ui_qt e `git diff --check` aprovados;
- pendência deliberada: compor menus/atalhos somente depois de a trilha ativa
  liberar os arquivos de entrada, usando sessão e permissões reais e sem
  reimplementar serviços;
- homologação visual/manual no Windows permanece necessária para todos os cinco
  diálogos; nenhum push realizado.

### Checkpoint isolado — hub administrativo Qt preparado

- implementação local: `763dbdc` — `feat: prepara hub administrativo Qt`;
- novo `AdministrativeModuleHub` reúne Clientes, Caixa, Financeiro, Relatórios e
  Usuários por descritores/fábricas, sem importar banco ou persistência na GUI;
- identidade e autorização são obtidas exclusivamente da sessão do
  `SecurityService`; sessão ausente/expirada e permissão negada falham fechadas,
  e a identidade nunca é aceita como texto da tela filha;
- visual usa os cartões escuros, contraste verde Nabi, dimensões amplas e
  linguagem operacional do Legacy; Enter abre exatamente uma janela,
  Shift+Enter retorna, Esc fecha o hub e auto-repeat é consumido;
- validação focada do hub e dos cinco módulos: `29 passed`; `compileall` e
  `git diff --check` aprovados;
- `main_qt.py` e `ui_qt/app.py` permaneceram intocados porque seguem reservados
  à trilha IA; próximo passo é conectar este hub ao shell somente após liberação
  coordenada desses arquivos e então homologar visualmente no Windows.

### Checkpoint isolado — Produtos e Estoque Qt

- branch/worktree: `codex/produtos-estoque-qt`, derivada da integração limpa
  `c8c7bdf`, sem alterar a branch consolidada;
- fronteira de autoridade em `323e405` — `feat: protege administracao de
  produtos e estoque`: `ProductManagementService` deriva ator exclusivamente da
  sessão real, exige `produtos:view/create/edit`, falha fechado e nunca aceita
  usuário livre da GUI;
- interface em `a8ccbd7` — `feat: adiciona produtos e estoque no Qt`: pesquisa
  ampla por nome/código/barras, cadastro, edição, entrada, saída, ajuste e
  histórico usam somente `ProductApplicationService`/`StockActionService` e
  transportam `product_id` real;
- nome, preço e estoque possuem fonte e colunas prioritárias, seguindo a
  linguagem visual escura e operacional do Legacy; edição de cadastro não muda
  saldo ocultamente — estoque existente só é alterado pela ação explícita de
  movimentação com revisão e confirmação humana;
- Enter executa uma ação, Shift+Enter retorna, Esc fecha a janela corrente e
  auto-repeat é consumido; MoneyEdit e decimais brasileiros permanecem no fluxo;
- validação focada inicial: `66 passed`; regressão ampliada de Produtos,
  Estoque, pesquisa acessível e PDV: `183 passed`, `2 subtests passed`;
  `compileall` e `git diff --check` aprovados;
- pendências: conexão ao hub/shell permanece fora deste checkpoint por
  coordenação com a IA; homologação visual/manual com catálogo real ainda é
  obrigatória. Fiscal/SEFAZ, IA, Fichário, licenciamento e banco real não foram
  alterados.

### Checkpoint isolado — Dashboard / Início Qt

- branch/worktree: `codex/dashboard-inicio-qt`, derivada do consolidado
  `ad51ae4`, sem alterar a integração;
- backend em `5bd7eb6` — `feat: pagina dashboard com permissao real`:
  `DashboardApplicationService` exige sessão válida e `dashboard:view`, e
  `DashboardRepository.day_history_page` limita de 1 a 200 registros, usa
  `LIMIT/OFFSET` e calcula os totais completos do dia no banco;
- interface em `cd4a767` — `feat: adiciona inicio paginado no Qt`: cartões de
  vendas do dia, recebimentos de fichas, cobranças vencidas e produtos ativos,
  além do Histórico de Movimentações do Dia aprovado no Legacy;
- a consulta roda em `QThreadPool`, nunca no construtor/thread da interface;
  gerações atrasadas são descartadas e paginação fica limitada a 100 itens por
  solicitação; teste com 5.000 movimentos materializou somente 50 linhas;
- janela é somente leitura, possui F5/PgUp/PgDown/Esc, foco visível, tabela
  acessível e consome Enter/auto-repeat sem executar mutação;
- testes focados: `33 passed`; regressão ampliada de Dashboard, relatórios,
  segurança, preferências e separação venda/recebimento: `97 passed`;
  `compileall` e `git diff --check` aprovados;
- pendências: conexão ao shell/hub permanece coordenada fora deste checkpoint e
  homologação visual/manual no Windows ainda é necessária. IA, Fiscal/SEFAZ,
  Fichário, licenciamento, instalador e banco real não foram alterados.

### Checkpoint isolado — Fornecedores e Compras Qt

- branch/worktree: `codex/fornecedores-compras-qt`, derivada do consolidado
  `306abfc`, sem alterar a integração;
- fachada em `a164620` — `feat: protege fornecedores e compras no Qt`:
  `PurchaseManagementService` exige sessão e `compras:view/create/receive`,
  deriva o ator internamente e limita consultas a 200 pedidos;
- interface em `e7aead7` — `feat: adiciona fornecedores e compras no Qt`:
  lista por status, fornecedor, novo pedido com itens/IDs reais, detalhes e
  preparação de recebimento parcial com conta a pagar opcional;
- o recebimento chama exatamente uma vez `CompraService.receber`; estoque,
  custo, financeiro, auditoria e idempotência permanecem exclusivamente na
  transação oficial já existente, sem persistência ou journal na GUI;
- visual, colunas, nomes e ações seguem a tela Legacy; Enter executa uma ação,
  Shift+Enter retorna, Esc fecha a janela corrente e auto-repeat é consumido;
- testes focados: `29 passed`; regressão ampliada de Compras, Estoque,
  Financeiro, Produtos e decimais: `85 passed`; `compileall` e
  `git diff --check` aprovados;
- pendências: conexão ao shell/hub permanece fora deste checkpoint; homologação
  manual com fornecedores/produtos de TESTE é necessária. IA, Fiscal/SEFAZ,
  Fichário, licenciamento, instalador e banco real não foram alterados.

### Checkpoint isolado — composição global dos módulos Qt

- branch/worktree: `codex/composicao-modulos-qt`, derivada do consolidado
  `0206209`, sem alterar a integração;
- implementação `a6a9eb3` — `feat: conecta modulos administrativos ao Qt`;
- o shell expõe uma única entrada `Módulos [F1]` e compõe Início, Clientes,
  Produtos/Estoque, Fornecedores/Compras, Caixa, Financeiro, Relatórios e
  Usuários exclusivamente por suas fachadas oficiais;
- login Qt real é obrigatório no startup; usuário/senha passam por
  `SecurityService.authenticate`, senha é limpa imediatamente e cancelamento
  falha fechado. Sessão expirada exige reautenticação ao reabrir o hub;
- módulos opcionais ausentes são omitidos sem impedir PDV ou Nabi; abertura do
  hub possui trava de reentrada, atalhos não repetem automaticamente e cada
  cartão revalida permissão/sessão antes de construir a janela;
- `_create_assistant_activation`, composição licenciada, painel e arquivos
  internos da IA não foram alterados; regressão ampliada anterior: `100 passed`,
  `3 subtests passed`; validação final do wiring: `25 passed`; `compileall` e
  `git diff --check` aprovados;
- pendência: homologação manual do login, F1, oito cartões, expiração e retorno
  ao PDV no Windows. Fiscal/SEFAZ, Fichário, licenciamento, instalador e banco
  real não foram alterados.
### Simplificação operacional do Emissor FICHÁRIO

Checkpoint em `2026-08-23`, branch `codex/emissor-facil-fichario`:

- implementação: `8bccecf` — `feat: simplifica emissao de licencas`;
- o proprietário continua escolhendo a edição, pois ela define o sistema
  licenciado; `FICHARIO` configura automaticamente
  `commercial,fichario,financial,qt`;
- o Emissor descobre no diretório administrativo externo a única chave privada,
  o catálogo público correspondente e seu `key_id`; nenhuma senha é persistida;
- o fluxo principal mostra somente máquina, titular, edição, período de
  1/3/6/9/12 meses, validade calculada e arquivo de saída automático;
- fingerprint bruto, caminhos, recursos, ID e revogação ficam em
  `Opções avançadas`, fechadas por padrão;
- `Usar esta máquina` obtém o fingerprint local; outra máquina continua usando
  solicitação assinável, sem tentar reverter o código visual;
- o nome do `.nabilic` é sugerido automaticamente e nunca sobrescreve arquivo
  existente;
- a edição AVALIAÇÃO fica limitada automaticamente a trinta dias;
- botão `Minimizar` e controle nativo de minimizar foram adicionados;
- regressão focada: `28 passed`; regressão integral de licenciamento/emissor:
  `51 passed`, `8 subtests passed`; `compileall` e `git diff --check` aprovados;
- pendência: integrar o commit na trilha conjunta, refazer o pacote externo do
  Emissor e homologar visualmente no Windows; nenhum push realizado.
### Auditoria fiscal de autoria restante — cancelamento oficial

- implementação: `08d025d` — `fix: autentica autoria do cancelamento fiscal`;
- o inventário separou quatro naturezas que não podem ser unificadas:
  - **identidade técnica autenticada:** operador que solicita mutação, confirma
    condição operacional, reenvia, reconcilia ou cancela uma fila/documento;
  - **responsável contábil declarado:** `approved_by` da matriz tributária, que
    não prova quem operou o NabiCode;
  - **autor fiscal externo:** CNPJ/CPF do emitente ou interessado usado nos XML
    e eventos SEFAZ (`actor_document`), que não é usuário da aplicação;
  - **dado histórico/sistêmico:** autoria já persistida na outbox/documentos,
    backfill `NAO_INFORMADO` e recuperação automática, que não pode receber
    identidade retroativa inventada;
- fronteira única selecionada: `FiscalCancellationService.request`, por criar
  evento oficial de cancelamento, registrar a confirmação de não circulação e
  alterar o documento para `CANCELAMENTO_PENDENTE`;
- o serviço agora exige `actor_provider` confiável, ligado no composition root a
  `SecurityService.session.user.username`; ausência, expiração ou identidade
  vazia falham fechadas antes da mutação;
- a API não aceita mais `actor` livre. Metadados `requested_by`,
  `no_circulation_confirmed_by` e o registro da outbox recebem exatamente a
  identidade autenticada;
- permanecem para checkpoints separados, sem alteração em massa: envio de
  eventos/inutilização, reenvio/cancelamento/reconciliação da outbox, DFe,
  importação/devolução e o fluxo antigo `FiscalSaleService.cancel_authorized`;
- validação focada: `71 passed`; regressão fiscal relacionada: `409 passed`,
  `10 subtests passed`, zero falhas e uma advertência externa de depreciação no
  gerador DANFE; `compileall` e `git diff --check` aprovados;
- regras tributárias, XML, prazos, endpoints, ambiente, transmissão e resposta
  SEFAZ não foram alterados. Produção fiscal continua bloqueada.

### Checkpoint IA Nabi — indicadores agregados de Relatórios

- a ferramenta somente leitura `relatorios.consultar_indicadores` usa
  exclusivamente `ReportApplicationService.indicators` e a sessão real com
  permissão `relatorios/view`;
- aceita somente datas ISO, início não posterior ao fim e período máximo de 366
  dias; devolve apenas vendas, contas a receber, contas a pagar, estoque baixo e
  clientes ativos;
- não expõe linhas, documentos, caminhos, exportação, geração de arquivos,
  relatório NF-e, Fiscal/SEFAZ, banco ou qualquer operação mutável;
- ausência do serviço mantém a ferramenta não registrada sem impedir PDV ou
  painel Nabi;
- validação integrada: `59 passed`, `4 subtests passed`; `compileall` e
  `git diff --check` aprovados; homologação manual do painel permanece pendente.

### Checkpoint IA Nabi — consulta segura do Caixa atual

- a ferramenta somente leitura `caixa.consultar_atual` usa
  `CashApplicationService.current`; o terminal vem da configuração local e o
  usuário vem do ator autenticado da sessão em cada execução;
- o payload contém apenas estado, identificador/abertura e totais monetários
  canônicos; movimentos, observações, documentos e usuários de terceiros não
  são enviados ao modelo;
- a ferramenta não abre ou fecha caixa e não registra suprimento, sangria ou
  qualquer mutação; ausência do serviço mantém a capacidade indisponível;
- validação ampliada Nabi/Caixa: `162 passed`, `38 subtests passed`, zero falhas;
  `compileall` e `git diff --check` aprovados.

### Checkpoint IA Nabi — listas financeiras minimizadas

- `financeiro.listar_receber` e `financeiro.listar_pagar` aceitam somente as
  situações fechadas `ABERTOS` ou `VENCIDOS`, exigem `financeiro/view` e usam
  exclusivamente `FinancialQueryService`;
- cada resposta é ordenada por vencimento e limitada a 50 títulos, contendo
  apenas ID real, parte relacionada, saldo aberto, vencimento, estado e atraso;
- documento, descrição, referência, origem, observações e centro de custo não
  entram no contexto do modelo; nenhuma baixa, criação ou estorno foi exposto;
- o painel renderiza deterministicamente essas listas, os indicadores de
  Relatórios e o Caixa atual, sem recorrer a conteúdo livre ou campos ocultos;
- validação focada integrada: `54 passed`; regressão ampliada e homologação
  manual permanecem obrigatórias antes de distribuição.

### Correção arquitetural — diário idempotente fora do FinanceiroService

- a suíte completa encontrou uma regressão de modularização: o recebimento
  assistido mantinha SQL do `assistant_operation_journal` dentro do serviço;
- a persistência foi extraída para `AssistantOperationJournalRepository`, que
  recebe a mesma conexão da transação e preserva início, replay, confirmação e
  rollback atômicos sem alterar cálculos ou regras financeiras;
- o teste arquitetural voltou a impedir SQL direto no `FinanceiroService`;
  repetição de commit no diário continua recusada;
- validação focada: `15 passed`; a suíte completa anterior registrou `2031
  passed`, `1 skipped`, `444 subtests passed` e somente essa falha, agora
  corrigida;
- repetição integral final: `2034 passed`, `1 skipped`, `2 warnings`, `444
  subtests passed`, zero falhas; os avisos são a classe auxiliar já conhecida e
  uma depreciação externa do `BrazilFiscalReport` no DANFE.

### Auditoria fiscal de autoria — reconciliação da outbox

- implementação: `bcf606c` — `fix: autentica reconciliacao da outbox fiscal`;
- a fronteira selecionada foi exclusivamente `FiscalService.reconcile_unknown`,
  que antes aceitava `actor` livre e persistia esse texto como solicitante ao
  reagendar uma resposta fiscal desconhecida;
- a API não aceita mais ator fornecido pela GUI: identidade e autorização são
  obtidas por portas confiáveis ligadas a `SecurityService.session` e à
  permissão real `fiscal/transmit`;
- ausência, expiração, permissão negada, identidade vazia ou falha do provedor
  encerram a operação antes de ler/alterar a fila; texto forjado não é gravado;
- a reconciliação preserva o contrato anterior: consulta somente recibo ou
  chave existente, nunca retransmite a autorização desconhecida, e mantém
  idempotência, XML, endpoints, ambiente, prazos e respostas desconhecidas;
- testes do serviço fiscal: `125 passed`, `10 subtests passed`; regressão
  outbox/worker/Central/cancelamento/venda/segurança: `100 passed`; regressão
  fiscal ampliada: `324 passed`, `10 subtests passed`, zero falhas e apenas a
  depreciação externa já conhecida do `BrazilFiscalReport` no DANFE;
- `compileall` e `git diff --check` aprovados; nenhum dado real, segredo,
  certificado ou licença foi incluído;
- reenvio manual, cancelamento local da fila e demais fronteiras de autoria
  continuam pendentes para checkpoints separados. Produção fiscal permanece
  bloqueada e este checkpoint não declara conformidade geral.

### Evidência operacional externa — entrada de compra por XML

- vídeo recebido em `2026-08-24`, duração `00:01:31.07`, resolução `1600x900`,
  SHA-256 `A80F9FA593F20653258CE24660153535EF7534C8EF295A7013DAB0A2EB45FCEA`;
- a gravação mostra outro sistema operado por AnyDesk e serve somente como
  referência de fluxo. Ela não prova regra jurídica, conformidade do NabiCode,
  resposta da SEFAZ para o NabiCode nem homologação de produção;
- apesar de ter sido inicialmente descrita como cancelamento, a varredura dos
  `5.462` quadros e das mudanças de cena não encontrou pedido de cancelamento,
  justificativa, protocolo de cancelamento, `cStat` de evento, estorno de
  estoque ou reversão financeira;
- o fluxo efetivamente observado foi: colar chave de acesso de 44 dígitos,
  consultar a NF-e no Portal Nacional, resolver o hCaptcha manualmente, escolher
  certificado do Windows, baixar o XML, revisar emitente/nota/item/tributos,
  decidir movimentação de estoque, unidade e fator de conversão, revisar conta
  a pagar, ajustar custo/preço e confirmar a importação;
- no exemplo de um item, uma embalagem comercial foi convertida por fator `25`
  para `25` unidades de estoque, com custo unitário recalculado a partir do
  total. O valor da nota permaneceu igual no estoque/financeiro; isso é
  evidência de experiência operacional, não uma regra universal de conversão;
- o NabiCode já possui os blocos correspondentes: `FiscalDFeService` para
  Distribuição DF-e/manifestação, `NFeXMLService` para leitura do XML e
  `NFeImportService` para vínculo, fator, estoque e financeiro na mesma
  transação idempotente. Não deve reproduzir navegação automatizada do Portal,
  hCaptcha ou seleção visual de certificado quando existe serviço oficial;
- lacuna de autoria separada: `FiscalDFeService.send_manifestation` ainda aceita
  `actor` livre e a Central Fiscal o fornece externamente. Deve receber ator e
  permissão da sessão autenticada em checkpoint próprio, antes de qualquer
  mutação ou rede, sem alterar tipos/prazos dos eventos;
- lacuna financeira separada: a importação atual cria no máximo um título e usa
  a data de emissão como vencimento. Antes de buscar paridade visual, auditar
  duplicatas/parcelas reais do XML e permitir revisão explícita das condições
  financeiras; não fabricar vencimento, parcelamento ou obrigação ausente;
- o fallback histórico `usuario="Sistema"` na importação também deve ser
  removido de fronteiras manuais: operador técnico vem da sessão; fornecedor,
  emitente e responsável contábil continuam identidades distintas;
- pendência física útil: gravar separadamente um cancelamento fiscal real em
  HOMOLOGAÇÃO, mostrando solicitação, justificativa, envio, retorno, protocolo,
  consulta posterior e reflexos comerciais. O vídeo atual não cobre essa prova;
- nenhum dado visível do certificado, chave completa de acesso, CNPJ ou nome de
  pessoa foi transportado para o repositório. Produção fiscal continua bloqueada.

### Evidência operacional externa — venda e emissão de NFC-e

- vídeo recebido em `2026-08-24`, duração `00:00:56.02`, resolução `1600x900`,
  `3.359` quadros e SHA-256
  `C50D2A3334A2449EE4162C676144FF499C7DE73CCF330B5C2D2C3C99FA8B11CC`;
- a gravação mostra outro emissor em sessão remota AnyDesk e serve apenas como
  referência operacional/visual. Não comprova conformidade do NabiCode, não
  substitui documentação oficial e não autoriza produção fiscal;
- foram observadas duas vendas de um item: a primeira usa um fechamento rápido
  com valor pago já preenchido; a segunda abre a tela completa de pagamento,
  com lista de formas, valor, troco, desconto, acréscimo e restante;
- o fluxo visível é: localizar produto, selecionar item, formar o cupom, revisar
  quantidade/valor/total, escolher o fechamento, informar pagamento, aguardar a
  emissão, abrir a pré-visualização do DANFE NFC-e e somente então retornar ao
  estado `CAIXA LIVRE` para nova venda;
- o DANFE mostrado contém QR Code, chave/consulta, protocolo e data/hora de
  autorização, mas esses valores pertencem ao estabelecimento filmado e não
  foram transcritos para o projeto;
- experiência útil para o NabiCode: fechamento rápido e pagamento detalhado são
  duas apresentações da mesma operação fiscal; nenhuma delas pode criar duas
  vendas, transmitir duas vezes ou marcar sucesso antes de uma resposta fiscal
  terminal comprovada. Impressão/visualização é pós-autorização e não deve ser
  confundida com a autoridade da SEFAZ;
- o vídeo não exibe XML assinado/enviado, ambiente de homologação, `cStat`/
  `xMotivo`, tratamento de rejeição, timeout, resposta desconhecida, consulta de
  recibo/chave, contingência, reinício, reimpressão ou reconciliação. Esses itens
  permanecem PENDENTES e não podem ser inferidos da animação `Aguarde` nem do
  DANFE visível;
- também não há demonstração de múltiplos itens, consumidor identificado,
  desconto/acréscimo efetivo, pagamento misto, cartão/PIX, cancelamento da tela
  de pagamento, falha de impressão ou recuperação após queda. Vídeos adicionais
  podem documentar esses fluxos, mas regras fiscais continuam dependentes de
  fonte oficial e testes próprios;
- nenhum dado pessoal, certificado, chave completa, CNPJ, chave de acesso ou
  protocolo visível foi transportado. Nenhuma chamada à SEFAZ foi executada por
  esta auditoria e produção fiscal continua bloqueada.

### Auditoria fiscal de autoria — manifestação do destinatário DF-e

- implementação: `9957108` — `fix: autentica autoria da manifestacao dfe`;
- causa: `FiscalDFeService.send_manifestation` aceitava `actor` livre do
  chamador e só o repassava ao histórico depois de assinar e transmitir o
  evento, sem validar sessão/permissão na fronteira do serviço;
- a API não aceita mais ator externo. Antes de consultar documentos, assinar ou
  acessar a rede, exige identidade da sessão ativa e permissão real
  `fiscal/transmit`, fornecidas por portas ligadas a `SecurityService`;
- ausência de porta, permissão negada, ator vazio ou falha de obtenção da sessão
  encerram a operação com `PermissionError` antes de qualquer leitura operacional
  ou transmissão; texto `actor` forjado é rejeitado pela assinatura da API;
- a Central Fiscal deixou de obter/passar `_usuario_financeiro()` para essa
  mutação. O serviço registra exclusivamente o usuário autenticado confirmado;
- tipos oficiais de manifestação, justificativa mínima, assinatura, envelope,
  endpoint, idempotência de Ciência/conclusivas e tratamento da resposta não
  foram alterados;
- validação: `14 passed` focados; regressão relacionada em blocos com `150 passed`
  e `10 subtests passed`, `36 passed` e `61 passed`; `compileall` e
  `git diff --check` aprovados. A tentativa de executar todo o conjunto em um
  único processo foi encerrada pelo ambiente sem resumo; os mesmos arquivos
  concluíram separadamente sem falhas;
- nenhum segredo, certificado, dado real ou chamada SEFAZ foi usado. Produção
  fiscal permanece bloqueada e não há declaração de conformidade geral;
- próximas fronteiras independentes ainda pendentes incluem reenvio/consulta
  manual da outbox, cancelamento local da fila e autoria da importação manual de
  XML. Corrigir no máximo uma fronteira por checkpoint, sem fallback `Sistema`.

### Auditoria fiscal de autoria — reenvio manual da outbox

- implementação: `79ae421` — `fix: autentica reenvio manual fiscal`;
- causa: `FiscalService.retry_transmission` aceitava `actor` livre e persistia
  esse texto em `retried_by` ao reabrir uma fila que o worker poderia transmitir;
- a API deixou de aceitar ator externo e chama `_authenticated_outbox_actor`
  antes de listar ou alterar a fila, exigindo identidade ativa e permissão real
  `fiscal/transmit` já ligadas a `SecurityService` no runtime Legacy;
- ausência de sessão/permissão falha fechada antes de ler a fila; texto forjado
  é rejeitado pela assinatura da API e a Central Fiscal não passa mais
  `_usuario_financeiro()` para essa operação;
- permanecem intactas as barreiras que proíbem reabrir documento concluído,
  cancelado, com transmissão iniciada ou `RESPOSTA_DESCONHECIDA`; esta última
  continua obrigatoriamente no fluxo de consulta/reconciliação, nunca reenvio;
- validação diretamente relacionada: `4 passed`, `123 deselected`; regressão de
  outbox/worker/Central/cancelamento/venda/segurança: `103 passed`;
  `compileall` e `git diff --check` aprovados. A execução integral isolada de
  `test_fiscal_service.py` foi encerrada pelo ambiente sem resumo; os testes do
  reenvio e toda a regressão relacionada concluíram separadamente sem falhas;
- nenhuma chamada SEFAZ, dado real, XML fiscal, segredo ou regra tributária foi
  alterada. Produção fiscal permanece bloqueada;
- consulta manual de recibo, cancelamento local de transmissão e autoria da
  importação manual de XML continuam checkpoints independentes pendentes.

### Auditoria fiscal de autoria — consulta manual de recibo

- implementação: `83ccbf5` — `fix: autentica consulta manual de recibo`;
- causa: `FiscalService.force_receipt_check` aceitava `actor` do chamador e
  gravava esse texto ao reagendar uma consulta de recibo na outbox;
- agora identidade e permissão `fiscal/transmit` são verificadas antes de ler a
  fila; a API não aceita ator externo e a Central Fiscal não fornece mais texto
  de usuário para a operação;
- a operação continua sendo exclusivamente consulta de recibo existente: não
  converte autorização sem recibo, não reenvia NFC-e/NF-e e não atua em item
  concluído ou cancelado;
- testes focados: `4 passed`, `125 deselected`; regressão de
  outbox/worker/Central/cancelamento/venda/segurança: `103 passed`;
  `compileall` e `git diff --check` aprovados;
- nenhuma rede SEFAZ, XML, endpoint, prazo, regra tributária ou dado real foi
  alterado. Produção fiscal permanece bloqueada;
- cancelamento local da transmissão e autoria da importação manual de XML
  continuam pendentes para checkpoints separados.

### Auditoria fiscal de autoria — cancelamento local da outbox

- implementação: `ed4d9d7` — `fix: autentica cancelamento local da outbox`;
- causa: `FiscalService.cancel_transmission` aceitava autoria livre mesmo ao
  marcar localmente como cancelada uma fila que ainda poderia ser processada;
- a API não aceita mais ator externo e exige sessão ativa com permissão
  `fiscal/transmit` antes de ler ou alterar a fila. `FiscalSaleService` conserva
  seu ator autenticado somente para a operação distinta de liberar numeração;
- continuam proibidos o cancelamento local de transmissão concluída, iniciada
  ou de resultado desconhecido. Nesses casos a consulta SEFAZ permanece
  obrigatória antes de qualquer decisão comercial;
- testes focados: `3 passed`, `128 deselected`; regressão de venda fiscal,
  cancelamento oficial, outbox/worker, Central e segurança: `100 passed`;
  `compileall` e `git diff --check` aprovados;
- nenhuma chamada SEFAZ, XML, endpoint, prazo, regra tributária ou dado real foi
  alterado. Produção fiscal permanece bloqueada;
- autoria da importação manual de XML e retransmissão em lote de contingência
  permanecem checkpoints independentes pendentes.

### Auditoria fiscal de autoria — retransmissão em lote de contingência

- implementação: `49cb679` — `fix: autentica retransmissao de contingencia`;
- causa: `FiscalService.retry_contingency_batch` aceitava `actor` livre ao
  reagendar várias NFC-e de contingência para processamento posterior;
- a API não aceita mais ator externo e exige sessão ativa com permissão
  `fiscal/transmit` antes de listar ou alterar a fila; a Central Fiscal deixou
  de fornecer `_usuario_financeiro()`;
- a seleção continua restrita a modelo `65`, emissão em contingência e operações
  de autorização/recibo ainda não concluídas, canceladas, iniciadas ou de
  resposta desconhecida. XML, `tpEmis`, prazos e worker não foram alterados;
- testes focados: `3 passed`, `130 deselected`; regressão de
  outbox/worker/Central/venda/segurança: `72 passed`; `compileall` e
  `git diff --check` aprovados;
- nenhuma rede SEFAZ, dado real ou regra fiscal foi usada ou alterada. Produção
  fiscal permanece bloqueada;
- autoria da importação manual de XML permanece como próximo checkpoint
  independente de alto risco.

### Auditoria fiscal de autoria — arquivo de XML autorizado externo

- implementação: `704b542` — `fix: autentica importacao de xml fiscal`;
- escopo deliberadamente separado: esta fronteira é
  `FiscalService.import_authorized_xml`, que valida e arquiva no índice fiscal um
  XML externo já autorizado. Não é a entrada comercial de compra por XML;
- a API deixou de aceitar ator externo e exige sessão ativa com permissão
  `fiscal/transmit` antes de validar o XML, criar diretórios ou gravar índice;
  autoria persistida vem exclusivamente da sessão;
- assinatura, chave, protocolo, ambiente, modelo, hash e validações de
  integridade existentes foram preservados;
- testes focados: `7 passed`, `128 deselected`; regressão de documento fiscal,
  outbox, venda, Central e segurança: `46 passed`; `compileall` e
  `git diff --check` aprovados;
- nenhuma rede SEFAZ, dado real, XML de cliente ou regra tributária foi usada ou
  alterada. Produção fiscal permanece bloqueada;
- bloqueio de composição ainda aberto: `NFeImportService.importar_atomicamente`
  atende tanto o Legacy quanto o gateway confirmado da Nabi. Autenticá-lo exige
  coordenação com `main_qt.py`/gateway para existir uma única porta de sessão;
  esta branch não pode alterar esses arquivos e não deve introduzir autoridade
  paralela ou fallback `Sistema`.

### Auditoria fiscal de autoria — reserva de numeração

- implementação: `281c28c` — `fix: autentica reserva de numeracao fiscal`;
- causa: `FiscalService.reserve_number` aceitava ator livre e o gravava na
  reserva antes de emissão de NF-e/NFC-e;
- a API não aceita mais ator externo e exige sessão ativa com permissão
  `fiscal/transmit` antes de iniciar a transação de numeração. Venda fiscal e
  devolução continuam fornecendo modelo/série/ambiente, mas não identidade;
- sequência monotônica, escopo ambiente/modelo/série, TTL, recuperação de
  reserva expirada, bloqueio de reutilização e vínculo a documento fiscal foram
  preservados;
- testes focados: `15 passed`, `122 deselected`; regressão de venda,
  cancelamento e outbox: `80 passed`; `compileall` e `git diff --check`
  aprovados;
- nenhuma rede SEFAZ, dado real, regra tributária ou numeração de produção foi
  usada. Produção fiscal permanece bloqueada;
- confirmação/liberação de reserva e inicialização manual da numeração ainda
  recebem ator explícito e devem ser auditadas em checkpoints independentes.

### Auditoria fiscal de autoria — inicialização da numeração

- implementação: `f015aea` — `fix: autentica inicializacao da numeracao fiscal`;
- causa: `FiscalService.initialize_numbering` aceitava ator livre numa operação
  humana irreversível para o escopo ambiente/modelo/série;
- a API não aceita mais ator externo e exige sessão ativa com permissão
  específica `fiscal/configure` antes de abrir a transação. A confirmação por
  senha mestra na interface permanece apenas reforço de intenção, nunca fonte de
  identidade ou autorização;
- validações de modelo, série, próximo número, ambiente, inicialização única e
  proibição de reconfigurar sequência existente foram preservadas;
- a autenticação fiscal comum foi generalizada internamente para mensagens
  coerentes por operação; as fronteiras já corrigidas da outbox continuam usando
  a mesma permissão `fiscal/transmit`;
- testes focados de inicialização/reserva: `18 passed`, `121 deselected`;
  regressão de venda/outbox/segurança: `36 passed`; `compileall` e
  `git diff --check` aprovados;
- nenhuma numeração real, rede SEFAZ ou regra tributária foi usada ou alterada.
  Produção fiscal permanece bloqueada;
- confirmação/liberação assíncrona de reserva exige desenho que preserve a
  identidade confiável capturada na origem sem depender de sessão viva do
  worker; não remover seus parâmetros até existir essa capacidade interna.

### Auditoria fiscal de autoria — confirmação assíncrona da numeração

- implementação: `13ba3a8` — `fix: preserva autoria na confirmacao fiscal`;
- arquitetura: a confirmação não exige sessão viva do worker e não aceita um
  novo ator. Ela reutiliza exclusivamente a identidade autenticada capturada em
  `reserve_number`, na mesma reserva vinculada à chave autorizada;
- reservas legadas ainda abertas sem identidade de origem falham fechadas e
  permanecem `RESERVADO`; não é criada identidade retroativa nem fallback
  `Sistema`. Reservas já confirmadas preservam a idempotência anterior;
- correspondência de modelo, série, número e chave, além das barreiras contra
  confirmação de reserva liberada ou chave divergente, foram preservadas;
- o caminho síncrono e o worker removem o parâmetro externo `actor` ao confirmar;
  o histórico `confirmed_by` deriva da reserva confiável;
- testes focados: `4 passed`, `137 deselected`; regressão de
  outbox/worker/venda: `49 passed`; `compileall` e `git diff --check` aprovados;
- nenhuma rede SEFAZ, dado real, XML ou regra tributária foi alterada. Produção
  fiscal permanece bloqueada;
- liberação de reserva continua síncrona e será autenticada pelo operador atual
  em checkpoint separado.

### Auditoria fiscal de autoria — liberação da numeração

- implementação: `285ed3e` — `fix: autentica liberacao da numeracao fiscal`;
- a API `release_number` não aceita mais ator externo e exige sessão ativa com
  permissão `fiscal/transmit` antes de abrir a transação; `released_by` registra
  exclusivamente o operador atual autenticado;
- venda fiscal, cancelamento local e devolução continuam fornecendo apenas o
  motivo técnico da liberação, nunca a identidade;
- motivo obrigatório, idempotência da reserva já liberada e bloqueios contra
  número confirmado, transmissão iniciada ou resposta desconhecida foram
  preservados;
- testes focados: `6 passed`, `138 deselected`; regressão de
  venda/cancelamento/outbox: `57 passed`; `compileall` e `git diff --check`
  aprovados;
- nenhuma rede SEFAZ, dado real, numeração de produção ou regra tributária foi
  usada ou alterada. Produção fiscal permanece bloqueada;
- reserva, confirmação e liberação de numeração deixam de aceitar autoria livre.
  Registros legados permanecem históricos e não recebem identidade inventada.

### Auditoria fiscal de autoria — inutilização de faixa

- implementação: `0e3439c` — `fix: autentica inutilizacao fiscal`;
- `FiscalService.inutilize_numbers` não aceita mais ator externo e exige sessão
  ativa com permissão `fiscal/transmit` antes de validar, assinar ou transmitir;
- a Central Fiscal fornece apenas ano, modelo, série, intervalo, justificativa e
  senha do certificado; autoria do evento vem exclusivamente da sessão;
- validações de faixa/justificativa, XML oficial, assinatura, ambiente, endpoint,
  resposta e histórico do evento foram preservados;
- testes focados: `4 passed`, `142 deselected`; regressão de Central,
  segurança e outbox: `34 passed`; `compileall` e `git diff --check` aprovados;
- nenhuma transmissão real, numeração de produção, dado real ou regra tributária
  foi usada ou alterada. Produção fiscal permanece bloqueada;
- eventos fiscais gerais (`send_event`) ainda recebem ator externo e devem ser
  migrados com cuidado porque são consumidos por cancelamento, CC-e e devolução.

### Auditoria fiscal de autoria — eventos fiscais comuns

- implementação: `8bf9495` — `fix: autentica eventos fiscais`;
- `FiscalService.send_event` deixou de aceitar ator externo e exige sessão ativa
  com permissão `fiscal/transmit` antes de validar, assinar ou transmitir;
- CC-e, cancelamento de venda e cancelamento de devolução fornecem somente os
  dados próprios do evento. O histórico técnico é sempre atribuído ao operador
  confirmado pelo serviço;
- elegibilidade, protocolo, sequência, justificativa/correção, assinatura,
  endpoint, XML e resposta SEFAZ foram preservados. As identidades declaradas do
  documento e responsáveis contábeis não foram confundidas com operador técnico;
- testes focados: `3 passed`, `145 deselected`; regressão de venda,
  cancelamento, devolução e outbox/worker: `115 passed`; `compileall` e
  `git diff --check` aprovados;
- nenhuma transmissão real, dado real ou regra tributária foi usada ou alterada.
  Produção fiscal permanece bloqueada;
- serviços superiores que ainda usam `actor` para efeitos comerciais próprios
  (por exemplo reversão de estoque da devolução) continuam pendentes de auditoria
  separada; não são mais capazes de forjar a autoria do evento fiscal.

### Auditoria fiscal de autoria — autorização síncrona de documento

- implementação: `17e2572` — `fix: autentica autoria da autorizacao fiscal`;
- `FiscalService.authorize_document` deixou de aceitar ator externo e exige
  sessão ativa com permissão `fiscal/transmit` antes de validar prontidão,
  assinar XML, criar arquivos ou transmitir;
- o registro do documento autorizado/rejeitado recebe exclusivamente a
  identidade confirmada pelo serviço. A devolução oficial fornece somente XML,
  chave, certificado, modelo e reserva, nunca a autoria técnica;
- validações de chave, ambiente, modelo e reserva, QR Code NFC-e, assinatura,
  schema, endpoint, protocolo, armazenamento íntegro e confirmação monotônica da
  numeração foram preservadas;
- testes focados: `12 passed`, `138 deselected`; devolução: `35 passed`;
  regressão fiscal ampliada: `285 passed`, `10 subtests passed`; `compileall` e
  `git diff --check` aprovados;
- nenhuma transmissão real, dado real, XML de cliente ou regra tributária foi
  usada ou alterada. Produção fiscal permanece bloqueada;
- a identidade comercial ainda recebida pelo serviço superior de devolução para
  seus efeitos próprios permanece separada da autoria técnica fiscal e requer
  auditoria própria antes de eventual remoção.

### Auditoria fiscal de autoria — reversão de estoque da devolução cancelada

- implementação: `361b412` — `fix: vincula reversao ao ator fiscal autenticado`;
- causa: depois de um cancelamento oficial aceito, o serviço de devolução ainda
  aceitava um segundo `actor` livre para atribuir a reversão local do estoque;
- `cancelar_devolucao_oficial` não aceita mais identidade externa. A reversão
  usa exclusivamente o ator autenticado persistido no evento retornado por
  `FiscalService.send_event`;
- se um adaptador não fornecer essa evidência, o cancelamento fiscal aceito é
  preservado como `CANCELADA_PENDENTE_ESTOQUE`, nenhuma movimentação é criada e
  não há fallback `Sistema`. A recuperação fica explícita para tratamento
  posterior;
- testes focados da devolução: `37 passed`; regressão de devolução, autorização,
  cancelamento, venda e outbox/worker: `267 passed`, `10 subtests passed`;
  `compileall` e `git diff --check` aprovados;
- nenhuma transmissão real, dado real, regra tributária, XML, prazo ou endpoint
  foi usado ou alterado. Produção fiscal permanece bloqueada;
- emissão da devolução e recuperações manuais/em lote ainda possuem identidade
  comercial livre para efeitos de estoque e seguem pendentes de desenho único de
  sessão, sem autoridade paralela.

### Auditoria fiscal de autoria — baixa de estoque da devolução autorizada

- implementação: `9af5618` — `fix: vincula baixa ao ator fiscal autenticado`;
- `NFeDevolucaoService.emitir_devolucao_oficial` não aceita mais ator externo.
  A autoria do histórico e da baixa de estoque vem exclusivamente do registro
  devolvido por `FiscalService.authorize_document`, já autenticado na sessão;
- se a autorização for aceita sem a evidência de autoria, o estado externo é
  preservado como `AUTORIZADA_PENDENTE_ESTOQUE`, nenhuma baixa é feita e não há
  fallback `Sistema`;
- rejeições continuam preservadas sem produzir efeito de estoque; erros antes de
  existir registro fiscal não recebem identidade retroativa inventada;
- testes focados da devolução: `39 passed`; regressão de devolução, autorização,
  venda, cancelamento e outbox/worker: `269 passed`, `10 subtests passed`;
  `compileall` e `git diff --check` aprovados;
- nenhuma transmissão real, dado real, regra tributária, XML, prazo ou endpoint
  foi usado ou alterado. Produção fiscal permanece bloqueada;
- recuperações manuais/em lote dos efeitos pendentes continuam recebendo ator
  livre e são a próxima fronteira isolada. Elas não devem ganhar um segundo
  provedor de segurança; precisam consumir a sessão oficial na composição.

### Auditoria fiscal de autoria — recuperação de estoque pendente

- implementação: `4ca25de` — `fix: autentica recuperacao de estoque fiscal`;
- as recuperações individual e em lote não aceitam mais ator externo nem usam
  `Sistema`. Ambas exigem, antes de consultar ou alterar estoque, a porta de
  sessão/permissão já composta em `FiscalService` com `fiscal/transmit`;
- `FiscalService.require_authenticated_actor` apenas expõe a mesma autoridade
  fail-closed existente para efeitos locais fiscais coordenados; não cria outro
  provedor, fallback ou permissão;
- o lote autentica uma vez e preserva a mesma identidade em todas as tentativas,
  inclusive no histórico de falha. Idempotência, estados pendentes e tratamento
  parcial do lote foram preservados;
- testes focados da devolução: `41 passed`; regressão de devolução, autorização,
  venda, cancelamento, outbox/worker e segurança: `281 passed`, `10 subtests
  passed`; `compileall` e `git diff --check` aprovados;
- nenhuma transmissão real, dado real, regra tributária, XML, prazo ou endpoint
  foi usado ou alterado. Produção fiscal permanece bloqueada;
- o ciclo oficial de devolução deixa de aceitar autoria livre na autorização,
  baixa, cancelamento, reversão e recuperação. A entrada comercial por XML segue
  bloqueada para checkpoint coordenado com a composição Nabi/Legacy.

### Auditoria fiscal de autoria — mutações da venda fiscal

- implementação: `a10a9f4` — `fix: autentica mutacoes da venda fiscal`;
- `FiscalSaleService.prepare` e `cancel_authorized` perderam parâmetros de ator
  que não eram usados; reserva e evento já exigem a sessão oficial no serviço;
- persistência transacional do rascunho/outbox, enfileiramento pendente e
  finalização local do cancelamento não aceitam mais identidade externa. Cada
  fronteira exige `fiscal/transmit` e captura o operador autenticado antes de
  qualquer gravação ou consulta mutável;
- a identidade capturada na transação continua armazenada na outbox para o
  worker assíncrono, sem exigir sessão viva posterior nem criar fallback;
- a venda comercial continua usando seu usuário próprio para estoque/financeiro,
  separado da autoria técnica fiscal. Idempotência do documento/fila,
  contingência, número reservado e bloqueios de resposta desconhecida foram
  preservados;
- testes focados de venda/outbox: `29 passed`; regressão de venda, outbox/worker,
  autorização, cancelamento, Central e segurança: `253 passed`, `10 subtests
  passed`; `compileall` e `git diff --check` aprovados;
- nenhuma transmissão real, dado real, regra tributária, XML, prazo ou endpoint
  foi usado ou alterado. Produção fiscal permanece bloqueada.

### Auditoria fiscal de autoria — enfileiramento técnico legado

- implementação: `114e272` — `fix: autentica enfileiramento fiscal`;
- a API legada `FiscalService.enqueue_transmission`, ainda coberta para
  compatibilidade e testes, deixou de aceitar ator externo e exige sessão ativa
  com `fiscal/transmit` antes de validar XML ou ler/gravar a fila;
- o ator persistido no item é sempre o operador autenticado. O worker continua
  consumindo essa identidade capturada e não depende de sessão viva;
- deduplicação por chave, contingência, resposta desconhecida, tentativas,
  consulta de recibo, reenvio manual e bloqueio de produção foram preservados;
- testes focados de fila/reconciliação/contingência: `30 passed`, `122
  deselected`; regressão fiscal, outbox/worker, venda, Central e segurança: `224
  passed`, `10 subtests passed`; `compileall` e `git diff --check` aprovados;
- nenhuma transmissão real, dado real, regra tributária, XML, prazo ou endpoint
  foi usado ou alterado. Produção fiscal permanece bloqueada;
- `store_document`, `register_event` e `register_rejection` conservam ator como
  primitivas internas porque recebem a identidade já capturada por operação ou
  worker. Torná-las portas públicas de sessão quebraria a autoria assíncrona;
  usos externos futuros devem passar por fachadas autenticadas.

### Encerramento da trilha isolada de autoria fiscal

- auditoria final por assinatura e chamadas confirmou que reserva, inicialização,
  confirmação/liberação de número, autorização, eventos, inutilização, DFe,
  importação de XML autorizado externo, outbox, venda fiscal e ciclo oficial de
  devolução não aceitam mais autoria livre em suas fronteiras mutáveis;
- `FiscalOutboxService.enqueue_in_transaction`, `store_document`,
  `register_event`, `register_rejection` e o histórico de regras tributárias são
  primitivas internas que preservam a identidade confiável capturada antes da
  transação ou pelo worker. Não devem consultar sessão viva no processamento
  assíncrono;
- bloqueio coordenado restante: `NFeImportService.importar_atomicamente`,
  `estornar_importacao`, `excluir_importacao` e
  `revisar_produtos_importados` ainda precisam de uma porta única de sessão e
  permissões. O serviço é composto separadamente no Legacy e em `main_qt.py`, e
  o gateway `assistant_nabi/nfe_entry_gateway.py` atualmente fornece
  `grant.username`. A correção exige checkpoint conjunto na branch consolidada,
  sem aceitar o nome do grant como autoridade final e sem criar provedor
  paralelo nesta branch;
- suíte integral dos arquivos fiscais/NF-e: `444 passed`, `10 subtests passed`;
  `compileall` completo e `git diff --check` aprovados;
- não houve chamada real à SEFAZ, uso de banco real, alteração de regra legal,
  XML, endpoint, prazo ou liberação de produção. Homologação fiscal física e
  produção continuam expressamente bloqueadas;
- próximo passo seguro: integrar esta branch por merge normal na consolidada,
  repetir a suíte completa e somente então executar o checkpoint coordenado da
  entrada de NF-e com SecurityService e broker Nabi compartilhando a mesma
  autoridade de sessão.
