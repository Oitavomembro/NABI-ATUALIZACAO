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
- [x] Clientes foi conectado ao hub/shell na composição global integrada em `3751c3a`, reutilizando a fronteira Commercial pronta e sem duplicar serviços;
- [x] checkpoint isolado de Caixa Qt implementado em `codex/caixa-qt` no commit `e000b8c`: porta `CashApplicationService` fixa terminal e usuário fora da GUI e expõe sessão/resumo tipados; a janela Qt cobre abertura com/sem saldo, suprimento, sangria, valores por forma, histórico e fechamento pelo `CashService` transacional, sem SQL ou persistência direta na interface;
- [x] validação de Caixa Qt: 32 testes focados e regressão relacionada com 243 testes e 341 subtestes aprovados, além de `compileall` e `git diff --check`;
- [x] Caixa foi conectado ao hub/shell na composição global integrada em `3751c3a`, preservando permissões e identidade real do operador;
- [x] checkpoint isolado de Financeiro Qt implementado em `codex/financeiro-qt` no commit `03e80a8`: contas a receber/pagar separadas, resumo, IDs reais, criação e baixa usam exclusivamente `FinancialQueryService`/`FinancialActionService`, `ActionContext` de UI e confirmação humana explícita; nenhuma persistência direta ou importação Fiscal na GUI;
- [x] validação de Financeiro Qt: 51 testes focados e regressão relacionada com 243 testes e 333 subtestes aprovados, além de `compileall` e `git diff --check`;
- [x] Financeiro foi conectado ao hub/shell na composição global integrada em `3751c3a`, pela porta pronta e sem persistência na GUI;
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
- [x] consultas de Compras adicionadas por fachada autorizada: fornecedores,
  pedidos e detalhes usam sessão/permissão `compras:view`, IDs reais, limites de
  50/100 registros e payload mínimo; CNPJ, observações e usuário interno não são
  enviados ao modelo. Nenhuma criação ou recebimento foi acrescentado por esta
  porta de leitura;
- [x] intenção segura `interface.abrir_modulos` adicionada: a Nabi pode abrir
  somente a Central de Módulos oficial; o schema vazio rejeita módulo, ação,
  senha, caminho ou confirmação inventados. Usuários/permissões, restauração e
  atualização continuam exclusivamente manuais dentro de suas telas autorizadas;
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
- [!] experimento da mascote no splash cancelado expressamente pelo proprietário; preservar o splash original e não retomar essa alteração sem nova autorização explícita;
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

### Checkpoint IA Nabi — fornecedores e novos pedidos assistidos

- branch isolada: `codex/nabi-fornecedores-pedidos`;
- base confirmada: `0a4091075c9478bfa9c7855ffa4b43238fddc122`, contendo
  `40d6f40` e `0a40910`;
- implementação: `926351db1224c45eb3b0604f3e4ef64bfd1f3874`;
- a Nabi prepara cadastros de fornecedor e pedidos de compra como rascunhos
  imutáveis, com IDs reais, valores decimais textuais e prévia determinística;
- cadastro e pedido exigem permissão `compras/create`, sessão real e confirmação
  humana reforçada vinculada ao conteúdo exato;
- a execução usa exclusivamente `PurchaseManagementService`,
  `FornecedorRepository` e `CompraService`; o usuário é derivado da sessão e
  comparado com o operador que confirmou;
- journal idempotente, cadastro/pedido e auditoria são persistidos na mesma
  transação; falha reverte todos os efeitos e repetição devolve o mesmo ID;
- chaves reutilizadas com outro fingerprint e autorizações fabricadas ou já
  consumidas falham fechadas;
- o recebimento de compras já existente não foi alterado, assim como
  `main_qt.py`, `ui_qt/app.py`, painel da Nabi e Fiscal/SEFAZ;
- validação ampliada: 157 testes e 38 subtestes da Nabi/Compras aprovados,
  além de `compileall` e `git diff --check`;
- nenhuma ligação ao painel/shell e nenhum push foram realizados nesta etapa.

### Checkpoint IA Nabi — Produtos e Estoque assistidos

- branch isolada: `codex/ia-produtos-estoque-assistida`;
- base confirmada: `0a4091075c9478bfa9c7855ffa4b43238fddc122`;
- implementação: `5d14497` — `feat: adiciona produtos e estoque assistidos a Nabi`;
- a Nabi prepara cadastro comercial de mercadoria com estoque inicial zero e
  movimentos unitários `STOCK_RECEIVE`, `STOCK_REMOVE` e `STOCK_ADJUST` por ID
  real de produto;
- rascunhos são imutáveis, possuem SHA-256 determinístico e exigem confirmação
  reforçada de uso único, vinculada à sessão e ao usuário reais;
- mutação e `assistant_operation_journal` são confirmados na mesma transação;
  repetição da mesma chave retorna o resultado persistido, fingerprint divergente
  falha fechado e qualquer exceção reverte efeito e diário juntos;
- produto assistido não recebe estoque inicial, saldo negativo ou campos fiscais;
  atualização de produto/preço, exclusão/inativação, inventário em massa e toda
  operação fiscal permanecem manuais;
- nenhuma conexão foi feita em `main_qt.py`, `ui_qt/app.py` ou painel nesta trilha;
- validação: 43 testes focados + 3 subtestes e regressão ampliada de 189 testes +
  38 subtestes, além de `compileall` e `git diff --check`, todos aprovados;
- próximo passo: integrar por merge normal na trilha consolidada e somente depois
  conectar a composição/UI em checkpoint coordenado, preservando os limites acima.

### Integração consolidada — cobertura não fiscal assistida da Nabi

- fornecedores/pedidos (`b73f009`), produtos/estoque (`c848dfe`) e Financeiro
  (`2ef535e`) foram integrados por merges normais, com históricos preservados;
- composição e painel foram conectados nos commits `e39eaf2` e `07f2032`;
- após login real, a Nabi pode preparar e confirmar cadastro de fornecedor,
  pedido, mercadoria comercial com estoque inicial zero, entrada/saída/ajuste
  unitário de estoque, criação de título RECEBER/PAGAR e baixa por ID real;
- todas essas mutações usam rascunho imutável, confirmação reforçada de uso
  único, sessão/permissão real, revalidação, journal durável e transação atômica;
- cancelamento/estorno financeiro, Caixa mutável, edição de produto/preço,
  usuários/permissões, restauração e atualização permanecem manuais; a Nabi
  somente consulta, orienta ou abre a Central oficial nesses limites;
- regressão completa consolidada: `2095 passed`, `1 skipped`, `444 subtests
  passed`, zero falhas e um aviso externo conhecido do BrazilFiscalReport;
  `compileall` e `git diff --check` aprovados.

### Segurança — primeiro acesso oficial e revogação imediata

- branch isolada: `codex/seguranca-primeiro-acesso`, derivada da consolidação
  enviada `112dacd`;
- implementação: `4fc2a95` — `feat: protege primeiro acesso e revogacao de sessao`;
- instalação nova do Qt oficial abre somente o assistente restrito para nome da
  empresa, CNPJ/e-mail opcionais e criação do primeiro administrador;
- o assistente não abre sessão implícita nem libera módulos; após concluir, o
  login real com a senha recém-definida é obrigatório;
- a conclusão é atômica, auditada e consumível uma única vez; atualização de
  instalação existente não reabre o primeiro acesso;
- o FICHÁRIO e sua decisão exclusiva de abertura direta não foram alterados;
- sessões agora recarregam usuário ativo e perfil persistidos antes de autorizar;
  desativação ou troca de perfil em outra instância alcançam o Qt e a Nabi na
  próxima autorização, sem aguardar expiração;
- validação focada: `172 passed`, `38 subtests passed`;
- regressão integral: `2102 passed`, `1 skipped`, `444 subtests passed`, zero
  falhas e um aviso externo conhecido do BrazilFiscalReport;
- `compileall` e `git diff --check`: aprovados;
- pendências separadas: substituir no Legacy oficial a sessão administrativa
  automática por primeiro acesso/login real; remover a senha mestre universal;
  adicionar limitação persistente de tentativas; completar auditoria das
  confirmações da Nabi.

#### Extensão ao Legacy oficial

- implementação: `e95e201` — `feat: exige primeiro acesso seguro no Legacy`;
- ajuste de regressão textual, sem mudança funcional: `ab7e2cc`;
- instalação nova não cria mais o administrador padrão: abre configuração
  restrita, grava empresa/CNPJ/e-mail e primeiro administrador atomicamente e
  exige autenticação real antes de construir/liberar os módulos e iniciar o
  worker fiscal;
- inatividade encerra a sessão configurada e exige nova autenticação; autorização
  sem sessão abre o login e falha fechada quando o operador cancela;
- compatibilidade automática permanece temporariamente somente para bases
  anteriores ao marcador `configuracao_inicial_concluida_v1`, evitando bloquear
  instalações existentes durante uma atualização; sua migração será uma etapa
  assistida separada;
- FICHÁRIO não foi alterado e mantém sua regra exclusiva;
- testes focados finais: `37 passed`; regressão integral repetida:
  `2102 passed`, `1 skipped`, `444 subtests passed`, zero falhas e um aviso
  externo conhecido do BrazilFiscalReport;
- `compileall` e `git diff --check`: aprovados.

#### Endurecimento de autenticação e confirmação da Nabi

- `711d8a6` — `fix: limita tentativas de autenticacao`;
- cinco falhas consecutivas por usuário criam bloqueio persistente de 60
  segundos, compartilhado por reinícios e instâncias; tentativa durante o
  bloqueio é recusada e auditada, e autenticação válida anterior ao limite
  limpa o contador;
- `26b1704` — `fix: audita confirmacoes assistidas da Nabi`;
- revisão do rascunho, confirmação humana e consumo da autorização agora são
  eventos distintos, correlacionados por operação, draft, fingerprint, usuário
  e sessão, sem transportar senha ou conteúdo comercial livre;
- a composição real usa auditoria estrita: falha de persistência impede emitir
  ou consumir autorização e, portanto, bloqueia a mutação assistida;
- validações focadas: `72 passed`, `14 subtests passed` para autenticação e
  `182 passed`, `38 subtests passed` para Nabi/auditoria;
- regressão integral final: `2105 passed`, `1 skipped`, `444 subtests passed`,
  zero falhas e um aviso externo conhecido do BrazilFiscalReport;
- `compileall` e `git diff --check`: aprovados;
- próximo checkpoint crítico: substituir a senha mestre universal sem quebrar
  autorização de instalação, atualização administrativa ou barreiras fiscais.

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

### Candidata integrada — segurança final e inventário de branches

- branch: `codex/integracao-final-seguranca-ia`;
- base: candidata consolidada `3ca8552`; merge de segurança adicional: `fa22b85`;
- as trilhas Nabi Financeiro (`250f8d2`), Fornecedores/Pedidos (`af8e365`) e
  Produtos/Estoque (`bdeb4c4`) já estavam integralmente presentes pelos merges
  `2ef535e`, `b73f009` e `c848dfe`; nenhuma delas foi duplicada;
- inventário de todas as branches locais confirmou que dossiê fiscal, autoria
  fiscal e composição administrativa Qt possuem conteúdo idêntico já integrado;
  duas referências do Fichário contêm somente documentação histórica e o splash
  experimental foi revertido, portanto não devem ser mesclados artificialmente;
- validação completa da candidata: `2161 passed`, `1 skipped`, `444 subtests
  passed`, zero falhas e apenas a depreciação externa conhecida do
  `BrazilFiscalReport`; `compileall` e `git diff --check` aprovados;
- `.codex-remote-attachments/` permanece local, não versionado e fora de todos
  os commits;
- próximo passo: publicar somente esta candidata consolidada e usar seu hash
  como nova base de continuidade; homologações físicas/fiscais continuam
  separadas e não são substituídas pelos testes automatizados.

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
### Checkpoint isolado — Configurações comerciais Qt

- branch/worktree: `codex/configuracoes-qt`, derivada do consolidado
  `3751c3a`, sem alterar a integração;
- implementação `0110ebb` — `feat: adiciona configuracoes comerciais ao Qt`;
- nova `SettingsApplicationService` exige sessão válida e permissões reais de
  `configs`; leitura continua disponível a `configs:view`, enquanto alteração,
  backup e diagnóstico falham fechados sem `edit`, `backup` ou `diagnose`;
- preferências visuais são normalizadas pelo mesmo `UIPreferencesService` do
  Legacy e isoladas pelo nome autenticado do usuário; senha ou identidade livre
  não entram na janela;
- destinos e política diária de backup são gravados atomicamente pelo
  `SystemRepository.set_configs`; o backup Qt reutiliza `BackupService`, não
  inclui diretório fiscal e nunca executa restauração pela interface;
- diagnóstico reutiliza `SystemDiagnostics`, salva relatório na área mutável do
  perfil e não muda dados de negócio;
- a janela Qt preserva a organização escura do Legacy em abas Interface,
  Backup e Diagnóstico; `Ctrl+G` abre o cartão no hub, mantendo F9 exclusivo do
  PDV, Esc fecha a janela e auto-repeat de Enter é consumido;
- validação focada e de infraestrutura: `72 passed`; regressão conjunta Qt,
  Commercial, startup da Nabi e licença: `340 passed`, `367 subtests passed`;
  `compileall` e `git diff --check` aprovados;
- pendências: homologação visual/manual do cartão Configurações, preferências,
  backup em dois destinos e relatório de diagnóstico no perfil TESTE; impressão
  e restauração continuam checkpoints separados. Fiscal/SEFAZ, IA, Fichário,
  licenciamento, instalador e banco real não foram alterados.

### Checkpoint isolado — Impressão comercial Qt

- branch/worktree: `codex/impressao-qt`, derivada do checkpoint de Configurações
  `7ec1a14`, sem alterar a integração;
- implementação `0aec7be` — `feat: adiciona configuracao de impressao ao Qt`;
- a aba Impressão reutiliza `PrintingService` e `ReceiptTemplateService`, lista
  as impressoras instaladas e cobre Recibo/Venda, Entrega, Ficha do cliente,
  Histórico e Fechamento de caixa com os formatos oficiais `Cupom 80 mm`, `A4`
  e `PDF virtual`;
- os 20 modelos visuais do Legacy permanecem disponíveis, com fonte, tamanho,
  corte parcial/total e linhas de avanço normalizados antes da gravação atômica;
- prévia é determinística e não envia trabalho ao spooler; salvar configurações
  também não imprime. A impressão física continua exclusiva dos fluxos
  documentais oficiais já existentes;
- Enter simples mantém uma ação, auto-repeat é consumido e Shift+Enter retorna
  pelo foco sem acionar botões; Esc fecha somente Configurações e F9 continua
  exclusivo para finalizar a venda no PDV;
- testes focados finais: `32 passed`; regressão ampliada Qt, Commercial,
  documental e startup Nabi: `361 passed`, `367 subtests passed`; `compileall`
  e `git diff --check` aprovados;
- pendências: homologação visual no Windows, enumeração com impressora física de
  TESTE e teste manual de cupom/A4 sem venda fiscal. Fiscal/SEFAZ, IA, Fichário,
  licenciamento, instalador e banco real não foram alterados.

### Checkpoint isolado — Central de Ajuda Qt

- branch/worktree: `codex/ajuda-suporte-qt`, derivada do checkpoint de Impressão
  `0f348a9`, sem alterar a integração;
- implementação `6b90bcd` — `feat: adiciona central de ajuda ao Qt`;
- a apresentação Qt reutiliza `ContextHelpRegistry`, é somente leitura e oferece
  assuntos e pesquisa por tecla/ação com a estética escura do Legacy;
- o catálogo passou a cobrir Caixa, Financeiro, Relatórios, Compras, Usuários e
  Impressão além dos tópicos anteriores; orientações não concedem permissões nem
  executam ações de negócio;
- `Ctrl+H` abre a Ajuda no hub sem conflitar com F1 do hub/Início ou F9 do PDV;
  Esc fecha somente a janela e Enter/auto-repeat na tabela são consumidos;
- nenhum navegador, mensageiro, processo externo, banco ou serviço fiscal é
  acessado pela janela; suporte externo permanece indisponível até existir uma
  configuração real e autorizada;
- testes focados: `25 passed`; regressão Qt e startup relacionado: `239 passed`,
  `2 subtests passed`; `compileall` e `git diff --check` aprovados;
- pendência: homologação visual/manual da pesquisa, tópicos e teclado no Windows.
  Fiscal/SEFAZ, IA, Fichário, licenciamento, instalador e banco real não foram
  alterados.

### Integração — Configurações, Impressão, Ajuda e backup completo

- a sequência `codex/configuracoes-qt` → `codex/impressao-qt` →
  `codex/ajuda-suporte-qt` foi reunida ao consolidado por merge normal;
- o backup manual Qt foi corrigido na composição para incluir também a pasta
  fiscal persistente; XMLs e DANFEs entram em arquivo separado com manifesto e
  hash, enquanto certificados, senhas e e-mails continuam excluídos;
- restauração não foi exposta como ação simples: permanece no fluxo técnico
  reforçado existente, com validação e cópia de segurança anterior;
- validação integrada de Configurações, Impressão, Ajuda, backup/restauração e
  composição: `56 passed`; `compileall` e `git diff --check` aprovados.
### Checkpoint isolado — Auditoria Administrativa Qt

- branch/worktree: `codex/auditoria-admin-qt`, derivada da Central de Ajuda
  `f77ba24`, sem alterar a integração;
- implementação `b8385b7` — `feat: adiciona auditoria administrativa ao Qt`;
- `AuditApplicationService` exige sessão válida e `technical:audit`, deriva a
  autorização exclusivamente do `SecurityService` e limita cada consulta aos
  500 eventos de segurança mais recentes;
- a janela Qt é somente leitura, filtra localmente data, usuário, ação,
  resultado e detalhes, e não permite inserir, editar, excluir ou escolher ator;
- a persistência e consulta continuam no `AdminAuditService` e no repositório
  oficial; a GUI não importa banco, SQL, Fiscal/SEFAZ ou Legacy;
- F5 atualiza uma vez, Esc fecha somente a janela e Enter/auto-repeat na tabela
  são consumidos sem disparar ação;
- testes focados: `27 passed`; regressão Qt, segurança, auditoria e startup:
  `254 passed`, `2 subtests passed`; `compileall` e `git diff --check` aprovados;
- pendência: homologação visual/manual com usuário ADMIN e verificação de acesso
  negado para perfis sem `technical:audit`. Nenhum push foi feito porque a etapa
  ainda depende dessa homologação. Fiscal/SEFAZ, IA, Fichário, licenciamento,
  instalador e banco real não foram alterados.

### Checkpoint isolado — Identificação Comercial da Loja Qt

- branch/worktree: `codex/identidade-loja-qt`, derivada da Auditoria
  `6de895c`, sem alterar a integração;
- implementação `fa22971` — `feat: adiciona identidade comercial da loja ao Qt`;
- a aba Loja expõe somente `nome_loja` e `rodape_cupom`, que são as duas chaves
  comerciais realmente consumidas pelos comprovantes e PDFs existentes;
- nome e rodapé são normalizados, possuem limites de 120/500 caracteres,
  rejeitam controles inválidos e são gravados juntos por uma única transação;
- CNPJ, emitente, certificado, ambiente, numeração e qualquer parâmetro fiscal
  permanecem fora dessa interface e não são lidos nem alterados;
- testes focados: `34 passed`; regressão Qt, Commercial, recibos, PDF e startup:
  `357 passed`, `367 subtests passed`; `compileall` e `git diff --check` aprovados;
- pendência: homologação visual/manual no perfil TESTE e geração de comprovante
  não fiscal para confirmar nome/rodapé. Nenhum push foi feito porque a etapa
  ainda depende dessa homologação. Fiscal/SEFAZ, IA, Fichário, licenciamento,
  instalador e banco real não foram alterados.

### Auditoria de prontidão para integração da sequência administrativa Qt

- ponta sequencial auditada: `e702e3a` em `codex/identidade-loja-qt`; ela contém
  Configurações, Impressão, Ajuda, Auditoria e Identificação Comercial, com seus
  respectivos commits documentais preservados;
- comparação somente leitura contra `codex/integracao-nabi-pdv` em `1a3f0f9`
  encontrou ancestral comum `3751c3a`;
- o ajuste dispensável do startup foi removido em `e702e3a` —
  `refactor: evita sobreposicao no startup Qt`; 19 testes de composição/startup
  passaram e `git diff --check` foi aprovado;
- após a correção, nenhum arquivo de código é alterado simultaneamente pelas duas
  trilhas; a única reconciliação prevista no merge normal é este mapa, que deve
  preservar integralmente as evidências Qt e IA;
- integração, merge e promoção continuam reservados à conversa coordenadora.
  Nenhum push foi feito, pois todos os checkpoints desta sequência ainda possuem
  homologação visual/manual pendente.

### Integração consolidada — sequência administrativa Qt

- a sequência Configurações, Impressão, Ajuda, Auditoria Administrativa e
  Identificação Comercial foi integrada por merges normais na branch
  `codex/integracao-nabi-pdv`, preservando os históricos das trilhas;
- conflitos ficaram limitados ao mapa e ao teste de composição e foram
  reconciliados preservando também a versão do aplicativo, a inclusão da pasta
  fiscal no backup e o módulo Auditoria;
- validação focada da integração: `63 passed`;
- regressão completa: `2061 passed`, `1 skipped`, `444 subtests passed`, zero
  falhas; `compileall` e `git diff --check` aprovados;
- merge final: `4a812e7` — `merge: integra identidade da loja e auditoria Qt`;
- permanecem pendentes somente as homologações visuais/manuais já descritas em
  cada checkpoint. A integração não constitui release fiscal.
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

### Integração consolidada — autoria segura da outbox fiscal

- a correção `bcf606c` foi auditada e integrada por merge normal no commit
  `3832dcd`, preservando os históricos fiscal e consolidado;
- a resolução documental preservou integralmente as evidências administrativas,
  da Nabi e fiscais, sem alterar regras tributárias ou comunicação SEFAZ;
- validação fiscal integrada: `214 passed`, `10 subtests passed`, zero falhas;
- regressão completa após o merge: `2064 passed`, `1 skipped`, `444 subtests
  passed`, zero falhas; `compileall` e `git diff --check` aprovados;
- produção fiscal continua bloqueada e as demais fronteiras de autoria seguem
  como checkpoints independentes, sem aprovação implícita de conformidade.

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

### Checkpoint IA Nabi — títulos e baixas financeiras assistidas

- branch isolada: `codex/ia-financeiro-assistido`;
- commit de implementação: `67fa2b087e72a2fb30ed0ed187a4b6d967c99782`;
- a Nabi prepara rascunhos imutáveis para criar contas a receber/pagar e para
  efetuar baixa parcial ou total de título identificado por ID real;
- preparação e revisão não gravam título, pagamento ou journal;
- execução exige sessão real, permissões `financeiro/create` ou
  `financeiro/pay`, confirmação humana reforçada, curta e vinculada ao hash;
- a baixa revalida tipo, estado e saldo aberto imediatamente antes de consumir
  a autorização; saldo alterado exige um novo rascunho;
- criação/baixa e `assistant_operation_journal` são confirmados na mesma
  transação SQLite; falha do journal reverte todos os efeitos;
- replay durável retorna o resultado confirmado sem criar segundo título,
  pagamento ou evento posterior; colisão da chave com outro hash falha fechada;
- cancelamento, estorno, recorrências, conciliação e Caixa mutável não foram
  expostos à Nabi neste checkpoint;
- `main_qt.py`, `ui_qt/app.py`, painel Qt, Fiscal/SEFAZ e banco real não foram
  alterados;
- validação focada: `55 passed`; regressão ampliada de Nabi, Financeiro,
  Commercial e schema: `238 passed, 38 subtests passed`; `compileall` e
  `git diff --check` aprovados;
- pendência de integração: composição no shell/painel deve ocorrer somente em
  checkpoint coordenado, preservando o estado seguro quando o executor não for
  fornecido.

### Segurança — remoção da credencial mestra universal

- branch: `codex/seguranca-primeiro-acesso`; implementação no commit `7738c80`;
- o hash de uma senha universal foi removido de `SecurityService`, do Legacy e
  do instalador; não existe mais login mestre nem confirmação mestre capaz de
  assumir uma identidade administrativa;
- login aceita somente a senha individual do usuário ativo e mantém a limitação
  persistente de tentativas; confirmações sensíveis exigem a senha real de um
  usuário ativo com perfil `ADMIN` ou `GERENTE`;
- a antiga autorização local por senha foi retirada do startup e do painel do
  Legacy. A licença V2 `.nabilic`, assinada e vinculada à máquina, permanece a
  única barreira comercial antes do banco e da interface;
- o instalador não contém segredo compartilhado e não oferece exclusão de dados
  operacionais. Atualização e desinstalação preservam banco, configurações e
  backups; exclusão deliberada continua restrita ao fluxo autenticado dentro do
  aplicativo;
- validação focada final: `59 passed`; regressão completa repetida após atualizar
  a expectativa antiga do desinstalador: `2105 passed`, `1 skipped`, `444
  subtests passed`, zero falhas e apenas a depreciação externa já conhecida do
  `BrazilFiscalReport`;
- `compileall` e `git diff --check` aprovados; Fiscal/SEFAZ não teve regra,
  comunicação, prazo ou persistência alterada; Fichário não foi alterado;
- nenhum push foi realizado neste checkpoint.

### Segurança — migração assistida de instalações antigas

- implementação no commit `e25f527`, branch `codex/seguranca-primeiro-acesso`;
- bases oficiais antigas que possuem usuários, mas não possuem o marcador
  `configuracao_inicial_concluida_v1`, não recebem mais sessão administrativa
  automática;
- antes de qualquer módulo, Qt e Legacy exigem um administrador ativo, validam
  sua credencial persistida e obrigam a substituição por senha de no mínimo oito
  caracteres; cancelar encerra a abertura em modo fail-closed;
- a migração usa transação `BEGIN IMMEDIATE`, grava o novo hash PBKDF2 e o
  marcador juntos, não abre sessão implícita, registra
  `MIGRACAO_CREDENCIAL_LEGADA` e só pode ser consumida uma vez;
- depois da migração, o login normal é obrigatório. Instalações oficiais já
  configuradas também autenticam antes da construção/liberação dos módulos;
- o Fichário permanece explicitamente separado e conserva sua decisão de abrir
  sem login, coberta pelos testes próprios da edição;
- validação focada inicial: `55 passed`; regressão completa: `2108 passed`, `1
  skipped`, `444 subtests passed`, com uma única colisão textual de callback em
  teste antigo; callback renomeado e repetição final das áreas afetadas: `60
  passed`; `compileall` e `git diff --check` aprovados;
- nenhum push foi realizado.

### Segurança — limitação de confirmações gerenciais

- implementação no commit `c91d88c`, branch `codex/seguranca-primeiro-acesso`;
- confirmações por senha de administrador/gerente agora compartilham limitação
  persistente: cinco falhas bloqueiam novas tentativas por 60 segundos, inclusive
  em outra instância ou após reabrir a interface;
- durante o bloqueio, até uma senha correta é recusada; sucesso anterior ao
  limite limpa a contagem; falha e bloqueio ficam registrados na auditoria;
- validação focada: `32 passed`; `compileall` e `git diff --check` aprovados;
- nenhum push foi realizado.

### Segurança — política de senha para usuários

- implementação no commit `7eaa112`, branch `codex/seguranca-primeiro-acesso`;
- criação de usuário e troca explícita de senha exigem no mínimo oito
  caracteres; não é mais possível criar conta oficial com senha vazia;
- a verificação preserva compatibilidade somente para hashes já existentes,
  evitando bloquear credenciais antigas durante a migração assistida;
- ao migrar uma base antiga, contas secundárias com algoritmo legado `none` são
  desativadas na mesma transação; o administrador deverá definir senha segura e
  reativá-las conscientemente;
- a interface Legacy informa a exigência de oito caracteres para novos
  usuários; deixar o campo vazio ao editar continua significando manter a senha
  existente, nunca apagá-la;
- validação focada final: `56 passed`; regressão completa: `2110 passed`, `1
  skipped`, `444 subtests passed`, zero falhas e apenas a depreciação externa
  conhecida do `BrazilFiscalReport`; `compileall` e `git diff --check`
  aprovados; Fichário, Fiscal/SEFAZ e banco real não foram alterados;
- nenhum push foi realizado.
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

### Integração coordenada — autoria da entrada comercial por NF-e

- integração dos históricos: `cf3c236` — merge normal da trilha isolada
  `codex/fiscal-outbox-auth` sobre a consolidada `112dacd`, preservando ambos os
  históricos e reconciliando somente este mapa;
- implementação: `e711ae2` — `fix: autentica entrada de nfe na sessao oficial`;
- `NFeImportService` deixou de aceitar `usuario` livre nas operações mutáveis.
  Importação, revisão, estorno, exclusão técnica e registro de resultado falham
  fechados sem ator e permissões fornecidos pela sessão oficial;
- a importação exige `compras/receive`, `financeiro/create` e as permissões de
  produto coerentes com cada item (`view`, `create` e/ou `edit`). Revisão exige
  `compras/receive` e `produtos/edit`; estorno exige `compras/receive` e
  `financeiro/reconcile`; exclusão técnica exige `technical/delete`;
- o broker da Nabi fornece somente `expected_actor` como trava contra troca de
  sessão entre revisão e confirmação. O nome do grant não é autoridade e nunca
  substitui o ator obtido do `SecurityService` compartilhado pelo shell Qt;
- o Legacy liga seu serviço global à própria sessão oficial depois da criação do
  `SecurityService`. Não há fallback `Sistema` ou `Administrador` nas mutações;
- a composição Qt reutiliza a mesma instância de segurança para shell, Nabi e
  entrada de NF-e. Como essa sessão pertence ao shell, parar ou falhar ao ativar
  a Nabi encerra somente o runtime local e não desloga o operador do sistema;
- testes focados: `43 passed`; regressão integral: `2145 passed`, `1 skipped`,
  `444 subtests passed`; `compileall` completo e `git diff --check` aprovados;
- nenhuma transmissão real, banco real, XML de cliente, regra tributária,
  endpoint, prazo, Fiscal/SEFAZ ou estado de produção foi alterado. Produção
  fiscal e homologação física continuam bloqueadas;
- próximo passo seguro: revisão independente do merge e integração normal desta
  branch na consolidada. Depois, continuar apenas pelas pendências fiscais
  documentais/homologação oficial, sem inventar evidência nem ampliar regras.

### Candidata final — Segurança + autoria fiscal/NF-e

- branch/worktree: `codex/integracao-final-candidata` em
  `NabiCode-QT-Final-codex`, derivada exatamente da consolidada `112dacd`;
- merge `e2e4903`: preserva integralmente os 16 commits do endurecimento de
  primeiro acesso, migração de credenciais antigas, política de senhas,
  limitação de tentativas e remoção da credencial mestra universal;
- merge `31811cb`: preserva a trilha completa de autoria fiscal e integra a
  entrada comercial por NF-e na mesma sessão oficial de Qt, Legacy e Nabi;
- `main_qt.py` e `nabicode_legacy.py` foram combinados automaticamente. O único
  conflito real foi este mapa, reconciliado mantendo todas as evidências de
  Segurança e Fiscal sem apagar pendências;
- a branch antiga `codex/principal-modulos-qt` foi auditada e deliberadamente
  excluída: sua composição já foi substituída pelos módulos administrativos
  mais completos existentes na consolidada;
- validação cruzada de Segurança, startup, Nabi, importação NFe, DFe, outbox,
  venda e devolução: `319 passed`, `10 subtests passed`;
- regressão integral: `2160 passed`, `1 skipped`, `444 subtests passed`, zero
  falhas; único aviso é a depreciação externa já conhecida do
  `BrazilFiscalReport`; `compileall` completo e `git diff --check` aprovados;
- nenhum banco, licença de cliente, chave privada, certificado, XML real ou
  segredo foi incluído. Nenhuma chamada real à SEFAZ foi executada;
- pendências restantes: homologações físicas/visuais já listadas, cerimônia das
  chaves permanentes, revisão jurídica e dossiê/homologação oficial SEFAZ Bahia.
  Não há outro checkpoint automatizável de alto valor identificado sem invadir
  as trilhas reservadas de IA/Fichário ou inventar evidência fiscal.

### Recuperação e modernização visual do shell Qt

- a trilha `codex/qt-shell-paridade-legacy` foi integrada por avanço direto
  sobre `7147c32`, sem conflito e preservando o inicializador Legacy oficial;
- o Qt volta a abrir no Início, e não diretamente no PDV. A navegação mantém a
  ordem operacional Início, Vendas, Clientes, Produtos, Financeiro, Caixa,
  Central Fiscal, Relatórios e Configurações;
- Central Fiscal permanece desabilitada no shell Qt e identifica explicitamente
  que a operação fiscal continua no Legacy oficial até migração homologada;
- cartões foram reorganizados em grade 3 x 3, ampliados e receberam linguagem
  visual tecnológica de metal escuro com trilhas luminosas azul/ciano e
  vermelho, inspirada apenas como direção estética e sem copiar ativos de
  terceiros;
- cartões do Início e resumos laterais seguem o padrão funcional aprovado no
  Fichário, mas nenhuma regra ou dependência exclusiva da edição FICHÁRIO foi
  transportada ao produto oficial;
- valores monetários dos resumos usam formatação brasileira pelo `MoneyCodec`;
- commit visual adicional: `548189f` — `style: moderniza cartoes do shell Qt`;
- inspeção visual isolada no Windows aprovada tecnicamente, sem banco real e sem
  contornar o portão de licença. Testes focados finais: `35 passed`;
  `compileall` e `git diff --check` aprovados;
- a apresentação flutuante da Nabi foi implementada no commit `3f455fd`: a
  mascote azul permanece recolhida sobre o shell, sem dock ou moldura de janela,
  e revela o painel escrito existente somente em balão tecnológico recolhível;
- motor, ferramentas, permissões, confirmações, falha fechada e botão de parada
  permaneceram intactos. A apresentação não copia personagem, relógio, voz ou
  arte de terceiros; 63 testes de Nabi/painel/shell foram aprovados, além de
  `compileall` e `git diff --check`.

### Cadeia de fornecimento Windows fechada V2

- branch/worktree isolados: `codex/supply-chain-fechada-v2` em
  `NabiCode-QT-SupplyChainV2-codex`, derivados exatamente de `1cfdfa4`;
- implementação: `0c2b4a2` — `build: fecha cadeia de dependencias Windows`;
- cerimônia autorizada em 24/08/2026 preservou as 18 versões diretas já
  homologadas e fixou `cyclonedx-bom==7.3.1`; uma resolução única em TEMP para
  Python 3.14.7/Windows x64 produziu baseline transitiva de 68 wheels;
- cada entrada do lock registra versão exata, único nome de artefato aprovado e
  SHA-256 previamente capturado; atualizações futuras exigem novo checkpoint;
- download e instalação usam `--no-deps`, `--require-hashes` e
  `--only-binary=:all:`; o build permanece `--no-index` e offline;
- validador fail-closed rejeita lock incompleto/duplicado, wheel ausente, extra,
  duplicado, renomeado ou adulterado antes da criação do ambiente de build;
- revisão de licenças cobre exatamente o lock e gera o inventário versionado em
  `THIRD_PARTY_NOTICES.md`; pacote sem decisão de licença, ausente ou divergente
  reprova, sem inferência automática;
- `cyclonedx-bom` gera e valida SBOM CycloneDX 1.6 reproduzível; simulação real
  produziu 68 componentes e passou na validação do schema;
- testes focados finais: `33 passed`; instalação integral do lock em ambiente
  temporário com hashes/no-deps aprovada; `compileall` e `git diff --check`
  aprovados;
- não houve alteração de runtime, Fiscal/SEFAZ, Nabi, Qt, banco ou instalador
  final real; nenhuma versão direta foi atualizada incidentalmente e nenhum
  segredo foi lido ou incluído;
- o wheelhouse e o SBOM continuam artefatos gerados fora do Git. Build físico do
  onedir/instalador não foi executado neste checkpoint e permanece sujeito ao
  roteiro Windows já documentado;
- próximo passo seguro: revisão independente e integração normal na consolidada,
  seguida de novo build físico offline. Não integrar automaticamente.

### Auditoria crítica fail-closed

- implementação: `07932a6` — `fix: exige auditoria nas mutacoes criticas`;
- o inventário confirmou que `record_event` era usado diretamente apenas pela
  consulta informativa da Nabi e pela fachada genérica do Legacy. O primeiro
  permanece best-effort; a fachada agora encaminha automaticamente os eventos
  catalogados como críticos à persistência estrita;
- o catálogo central cobre as ações existentes de usuários, perfis e senhas,
  fechamento/sangria/suprimento, cancelamento e estorno financeiro, ajuste e
  saída de estoque, recebimento de compras, operações administrativas de
  restauração/reset/atualização/licenciamento e mutações fiscais conhecidas;
- usuários/perfis/senhas, Caixa e Estoque passaram a gravar a auditoria na mesma
  transação da mutação. Compras e Financeiro já possuíam esse comportamento e
  receberam provas adicionais de rollback;
- ausência da tabela, recusa SQL ou retorno de persistência falso bloqueiam a
  operação. A confirmação da Nabi não possui mais fallback para auditoria
  best-effort;
- fault injection comprovou zero mutação após falha em criação de usuário,
  sangria, fechamento de Caixa, ajuste/saída de estoque, recebimento de compra e
  cancelamento financeiro. Testes arquiteturais protegem o catálogo e o contrato
  estrito da Nabi;
- regressão focada: `118 passed`; regressão ampliada de Administração,
  Segurança, Caixa, Estoque, Compras, Financeiro, Nabi e Fiscal relacionado:
  `650 passed`, `13 subtests passed`; único aviso é a depreciação externa já
  conhecida do `BrazilFiscalReport`; `compileall` e `git diff --check`
  aprovados;
- backup/restauração física, reset, atualização, licenciamento criptográfico e
  rede Fiscal/SEFAZ não foram modificados neste checkpoint. O catálogo impede
  que chamadas futuras pela fachada sejam silenciosas, mas a atomicidade desses
  fluxos externos exige checkpoint próprio, pois não pode ser simulada dentro
  de uma transação SQLite.

### Backup diário Qt confiável e restauração comprovável

- branch isolada `codex/backup-diario-qt-confiavel`, derivada de `1cfdfa4`;
- núcleo `2bce948` — `fix: torna backup diario confiavel por destino`;
- startup/UI `f019630` — `feat: executa backup diario no startup Qt`;
- o backup configurado inicia em worker somente depois de licença, perfil,
  banco, migração/primeiro acesso e login estarem prontos e depois de o shell
  ser exibido; a interface não espera a cópia SQLite;
- principal e pasta sincronizada possuem estado diário independente por caminho
  normalizado. Sucesso local não marca o secundário com falha; nova tentativa no
  mesmo dia executa somente destinos pendentes;
- o lock único do serviço e a marca por destino impedem duplicação concorrente.
  SQLite Backup API, nomes exclusivos, `integrity_check`, `foreign_key_check`,
  documentos fiscais permitidos e retenção existente foram preservados;
- resultado visível distingue concluído, parcial, falha, desativado e já
  concluído. Backup manual parcial também deixou de alegar sucesso integral;
- a verificação operacional restaura exclusivamente para diretório TEMP,
  revalida integridade/FK e compara schema com o banco ativo sem modificá-lo.
  A restauração real continua manual, reforçada e com snapshot de segurança no
  serviço oficial de manutenção; nenhum botão perigoso foi criado;
- corrigido o mojibake `Backup invÃ¡lido`; Configurações avisa que os backups
  contêm dados pessoais e não recebem criptografia neste checkpoint;
- validação final relacionada: `99 passed`, `3 subtests passed`; bloco focado:
  `38 passed`; `compileall` completo e `git diff --check` aprovados;
- não houve alteração em Fiscal/SEFAZ, Nabi, PDV, Caixa, licenciamento,
  usuários, banco real, instalador, retenção ou regras de negócio;
- próximo passo: revisão independente e integração normal na consolidada. O
  pacote mensal do contador permanece fora deste checkpoint até contrato
  oficial delimitado pela trilha arquiteta.

### Backup criptografado autenticado opcional

- branch isolada `codex/backup-criptografado-v2`, derivada de
  `codex/backup-diario-qt-confiavel@ac9b69f`;
- implementação `8a5cb8a` — `feat: adiciona backup criptografado autenticado`;
- novo envelope `.nabibackup` versão 1 usa AES-256-GCM em fluxo por blocos e
  scrypt com parâmetros fixos da implementação; a dependência `cryptography`
  permanece na versão `46.0.0` já bloqueada pelo build oficial;
- cabeçalho canônico, versão, cifra, KDF, salt, nonce e tamanho declarado são
  validados antes da derivação/descriptografia e autenticados como AAD;
- senha possui mínimo de 12 caracteres, nunca é persistida ou registrada e não
  existe senha mestra nem recuperação. Perder a senha torna o envelope
  irrecuperável;
- criação usa cópia SQLite consistente em TEMP, `integrity_check`,
  `foreign_key_check`, arquivo temporário exclusivo, validação completa e troca
  atômica. Falha remove envelope parcial e texto temporário;
- verificação/restauração de prova autentica e descriptografa somente em TEMP,
  valida integridade/FK/schema e nunca toca no banco ativo. A restauração real
  permanece no fluxo oficial reforçado;
- backups `.db` existentes continuam aceitos e são identificados explicitamente
  como `SQLITE_LEGACY_UNENCRYPTED`; não há renomeação, conversão ou criptografia
  silenciosa;
- o envelope protege somente o banco operacional. O ZIP fiscal separado não foi
  alterado neste checkpoint e segue sua política própria;
- testes cobrem roundtrip, senha errada, adulteração, truncamento, cabeçalho
  malicioso, tamanho declarado abusivo, colisão, atomicidade, limpeza e
  compatibilidade legado. Regressão Backup/Configurações/Fichário: `74 passed`;
  supply chain/empacotamento/backup: `34 passed`; `compileall` e
  `git diff --check` aprovados;
- nenhum Fiscal/SEFAZ, Nabi, Qt visual, licenciamento, banco real ou instalador
  foi alterado. Próximo passo: integrar por merge normal e expor a opção de
  senha somente em fluxo humano explícito, sem persistência.

### Configuração Qt do backup criptografado

- branch isolada `codex/backup-criptografado-qt`, derivada do checkpoint V2
  `4630832`; implementação `5ce1362` — `feat: adiciona backup criptografado ao Qt`;
- a aba Backup mantém o diário legado compatível e oferece uma entrada separada
  `Backup protegido`; o diálogo novo seleciona destino e apresenta o envelope
  criptografado como opção recomendada;
- escolher `.db` legado exige opção explícita visualmente marcada como insegura
  e sem criptografia. Nenhum backup existente é convertido ou renomeado;
- senha e confirmação usam campos protegidos, nunca entram em configuração ou
  log e são limpas antes de iniciar o worker, ao concluir, falhar ou cancelar;
- geração e restauração de prova rodam em `QThreadPool`; reentrada fica
  bloqueada e o diálogo não fecha fingindo cancelamento enquanto a operação
  atômica está em andamento;
- sucesso mostra somente nome do arquivo, proteção real, schema e SHA-256.
  Falha não exibe senha, caminho interno nem texto livre da exceção;
- Enter avança uma etapa, Shift+Enter retorna, Esc fecha quando seguro e
  auto-repeat é consumido. A GUI usa apenas a porta
  `SettingsApplicationService`, sem banco, Fiscal, IA ou licenciamento;
- `create_backup_package` exige permissão real `configs/backup`, gera pelo
  `BackupService`, verifica em TEMP e remove o novo arquivo se a prova final
  falhar. `verify_backup_package` apenas prepara futura seleção de arquivo e
  também nunca restaura o banco ativo;
- validação focada UI/serviço/criptografia: `51 passed`; regressão ampliada de
  Backup, Configurações e Fichário: `84 passed`; `compileall` e
  `git diff --check` aprovados;
- `main_qt.py`, shell, Fiscal/SEFAZ, Nabi, licenciamento, banco real e instalador
  não foram alterados. Integração e homologação visual no Windows permanecem
  checkpoints separados.
### Pacote contábil V2 — checkpoint 1 de integridade

- branch isolada: `codex/pacote-contabil-integridade-v2`, derivada de
  `1cfdfa4`, sem integração com a candidata principal;
- implementação: `e4816fb` — `fix: endurece integridade do pacote contabil`;
- o manifesto passou ao layout explícito `nabicode.accounting-package.v2` e
  cataloga individualmente, com SHA-256, todos os XMLs de saídas, DF-e
  recebidos, envios e retornos de eventos e o arquivo de instruções;
- o validador exige correspondência exata entre catálogo e ZIP e rejeita bytes
  alterados, arquivo ausente ou extra, caminhos duplicados/ambíguos, travessia
  de diretório, vínculos/hash repetidos e manifesto estruturalmente
  inconsistente;
- XMLs são reabertos sem rede ou entidades externas para confrontar, quando o
  contrato disponível contém o dado, chave de acesso, protocolo, CNPJ do
  emitente, período de emissão, modelo e status de documento/evento;
- manifesto V1 é classificado explicitamente como `LEGADO` e insuficiente; ele
  nunca é apresentado como íntegro no padrão V2;
- o manifesto não é assinado neste checkpoint. O resultado e o LEIA-ME
  declaram `non_repudiation=false`: SHA-256 detecta corrupção/divergência, mas
  não prova autoria nem oferece não-repúdio;
- testes focados: `17 passed`; regressão de todos os arquivos `test_fiscal*` e
  adversariais do pacote: `364 passed`, `10 subtests passed`; `compileall` e
  `git diff --check` aprovados;
- nenhum conteúdo EFD/PGDAS/SPED foi criado e nenhuma transmissão, outbox,
  retenção, backup, Qt, Nabi, banco real, certificado, segredo ou regra
  Fiscal/SEFAZ operacional foi alterada;
- próximo passo: ampliar conteúdo contábil somente em checkpoint separado,
  preservando este contrato V2 e sem confundir integridade por hash com
  assinatura ou prova de autoria.

### Pacote contábil — checkpoint 2 de fontes e reconciliação

- branch isolada: `codex/contabil-fontes-reconciliacao`, derivada de
  `9af32ef`, sem integração com a principal;
- correção de fonte: `7db7d8e` — `fix: usa titulos financeiros nos relatorios`;
  `ReportService` passou a consultar exclusivamente a tabela canônica
  `titulos_financeiros` em indicadores e relatório. Não existe fallback
  silencioso para a tabela antiga `financeiro_titulos`; 25 testes de relatório
  provam títulos reais a pagar/receber e preservam precisão decimal;
- implementação: `3519be6` — `feat: cria reconciliacao contabil somente leitura`;
- `AccountingReconciliationService` abre a conexão em modo `query_only`, não
  cria tabela ou lançamento e produz DTO imutável e CSV versionado
  `nabicode.accounting-reconciliation.v1`, com resumo por classificação e
  totais separados por relação para não somar o mesmo fato repetidamente;
- relações diagnosticadas por IDs/chaves/origens existentes: venda↔documento
  fiscal, venda↔JSON de pagamentos, venda↔título/parcelas,
  compra↔recebimento parcial↔estoque↔título, pagamentos↔títulos, documento
  fiscal órfão, origem financeira/estoque inválida, cancelamento↔estorno e
  DF-e↔compra;
- classificações: `CONCILIADO`, `PENDENTE_DADO_EXTERNO`, `DIVERGENTE`,
  `LEGADO_NAO_PROVAVEL` e `NAO_APLICAVEL`. Correspondência textual ambígua não
  é criada;
- competência e caixa permanecem explicitamente separados. O relatório avisa
  que pagamento de venda está em JSON, vendas/recebimentos não possuem
  `cash_session_id`, itens antigos podem ser somente texto e NF-e importada não
  possui vínculo inequívoco com pedido/recebimento;
- testes focados de reconciliação/relatório: `33 passed`; regressão combinada de
  Report, Financeiro, PDV, Compras e Fiscal: `366 passed`, `13 subtests passed`;
  `compileall` e `git diff --check` aprovados;
- teste de 1.001 vendas prova ausência de truncamento silencioso. Casos
  adversariais cobrem JSON inválido, duplicidade, origem inválida, venda fiscal
  sem documento, documento sem venda, crediário, compra parcial, pagamento
  órfão, cancelamento, competência/caixa e DF-e sem vínculo canônico;
- nenhuma tabela contábil, lançamento, DRE oficial, EFD/SPED ou regra de negócio
  foi criada. Fiscal operacional, transmissão, Qt, Nabi, backup, despesas de
  Caixa, licenciamento e banco real permaneceram intocados.

### Pacote do contador — checkpoint 3 em camadas

- branch isolada: `codex/pacote-contador-em-camadas`, derivada de `2076a49`,
  sem integração com a principal;
- implementação: `7dd382d` — `feat: exporta pacote mensal para contador`;
- endurecimento de escala/identidade: `dc11995` — `fix: filtra fontes
  contabeis na competencia`;
- `AccountantMonthlyPackageService` exporta por CNPJ e competência, em modo
  SQLite `query_only`, as camadas `00` a `11` e `99`: resumo/pendências,
  empresa, vendas/recebimentos, XMLs de saída/entrada, caixa, contas,
  compras/fornecedores, estoque/inventário, limitações tributárias, externos,
  intercâmbio universal e evidências;
- perfis `ESSENCIAL`, `COMPLETO` e `AUDITORIA` preservam os mesmos totais e toda
  movimentação real no resumo, manifesto e CSVs canônicos. O Completo adiciona
  JSON/XLSX auxiliares; Auditoria adiciona a trilha existente; Essencial mantém
  a entrega curta;
- `LEIA-ME_CONTADOR.txt` na raiz orienta início, semáforo, perfis, CNPJ,
  competência, totais e pendências externas. Toda seção sem registro recebe
  declaração explícita; isso nunca é apresentado como prova automática de
  ausência econômica;
- cadastro da empresa exporta apenas campos contábeis/fiscais permitidos e
  transforma ausência de razão/nome, CNPJ, IE, IM, UF/município/endereço,
  regime/CRT ou CNAE em pendência. Certificado, senha, endpoints e demais
  segredos não entram no pacote;
- XMLs originais vêm exclusivamente do pacote fiscal V2 validado. Saídas,
  entradas e eventos ficam separados, e o manifesto fiscal preserva a marcação
  `RESUMO` versus `XML_COMPLETO`;
- a pasta `11_INTERCAMBIO_UNIVERSAL` contém CSV UTF-8-BOM, `layout.json`
  versionado e, nos perfis completos, XLSX de conveniência. Lote e linhas têm
  identidades SHA-256 separadas: `source_key` permanece estável por
  CNPJ/fonte/ID; `row_hash` detecta mudança de conteúdo; `row_id` identifica a
  versão exata para evitar reimportação duplicada. Não são gerados
  débito, crédito, plano de contas, centro de custo ou lançamento inferido;
- o pacote externo possui ZIP determinístico, catálogo individual de tamanho e
  SHA-256 e validador estrito contra adulteração, arquivo extra, duplicidade,
  caminho inseguro e manifesto inconsistente. Hash não é assinatura e
  `non_repudiation=false` permanece explícito;
- bancos, adquirentes/cartões, folha, contratos e despesas estruturadas sem
  fonte canônica são pendências externas ou
  `CAPACIDADE_PENDENTE_INTEGRACAO`, com impacto, responsável e prazo quando
  disponível. Competência e caixa permanecem separados;
- CNPJ é validado com dígitos verificadores pelo utilitário fiscal existente.
  Fontes periódicas usam consultas SQL parametrizadas: datas ISO seguem ramo
  apto a índice e datas DD/MM/AAAA usam compatibilidade separada, sem carregar
  todo o histórico em memória;
- testes focados pacote/reconciliação: `21 passed`; regressão combinada de
  pacote V2, Report, Financeiro, PDV, Compras e Fiscal: `379 passed`, `13
  subtests passed`; `compileall` e `git diff --check` aprovados;
- testes cobrem todos os perfis, CNPJ/competência, pacote vazio, cadastro
  ausente, divergência, 1.002 movimentações sem truncamento, determinismo byte a
  byte, privacidade, intercâmbio idempotente, XML original e rejeição de
  adulteração/arquivo extra. Teste adicional com 5.000 linhas fora da
  competência comprova, pelo SQL observado, que o histórico não é materializado;
- o material é chamado de pacote de fontes, nunca de EFD, PGDAS, SPED ou DRE
  contábil, e não apura imposto. Nenhum schema, regra de negócio, Fiscal
  operacional/SEFAZ, Qt, Nabi, backup, Caixa, licença ou banco real foi alterado.

### Central do Contador Qt — preparação e exportação segura

- branch/worktree isolados: `codex/central-contador-qt` em
  `NabiCode-QT-CentralContador-codex`, derivados exatamente do pacote em camadas
  `885cd75` e sem conexão ao shell ou `main_qt.py`;
- implementação: `74f3539` — `feat: adiciona Central do Contador Qt`;
- a tela apresenta competência, CNPJ confirmado e destino, com Essencial e
  Completo como caminhos principais e Auditoria somente em opção avançada;
- os três perfis usam exclusivamente `AccountantMonthlyPackageService` e não
  oferecem filtros para omitir movimentos. A interface explica conteúdos,
  pendências externas, separação entre competência/caixa e que o pacote não é
  EFD, PGDAS, SPED, DRE contábil nem apuração tributária;
- revisão e geração são ações separadas. A revisão produz plano imutável com
  SHA-256 vinculado a CNPJ, competência, perfil, destino e operador; qualquer
  alteração invalida a geração. Sessão e `relatorios/generate` são revalidadas
  nas duas ações, e troca de operador falha fechada;
- exportação roda por `QThreadPool`, bloqueia reentrada, descarta resultado
  atrasado e preserva Enter, Shift+Enter, Esc e consumo de auto-repeat;
- o semáforo mostra somente estados reais `CONCILIADO`, `PENDENTE` ou
  `DIVERGENTE`, além de quantidade de arquivos, movimentos e pendências. Nunca
  antecipa sucesso nem substitui a revisão do contador;
- defeito histórico de determinismo corrigido: o `openpyxl` atualizava o campo
  interno `modified` do XLSX durante `save()`, alterando ZIP/hash conforme o
  segundo do relógio. O metadado agora é normalizado e o teste atravessa um
  segundo entre duas exportações idênticas;
- validação focada da Central/pacote/reconciliação: `35 passed`; regressão
  ampliada de pacote, relatórios, segurança e Qt: `86 passed`; `compileall` e
  `git diff --check` aprovados;
- não foram alterados Fiscal/SEFAZ operacional, IA, banco real, shell,
  `main_qt.py` ou regras contábeis/tributárias;
- próximo passo: revisão cruzada, merge normal na consolidada e somente depois
  composição explícita no menu autorizado. Homologação visual Windows e geração
  em banco TESTE continuam obrigatórias antes de promoção.
### Perfil empresarial unificado — serviço versionado

- branch isolada: `codex/perfil-empresarial-unificado`, derivada exatamente de
  `1cfdfa4`, sem UI e sem integração com a principal;
- implementação: `2b21aa7` — `feat: versiona perfil empresarial confirmado`;
- `CompanyProfileService` e seus DTOs imutáveis registram CNPJ validado, razão
  social, regime (`MEI`, Simples, Presumido, Real ou Outro), enquadramento
  (`MEI`, `ME`, `EPP` ou Outro), CNAEs/atividades, UF, município, IE/IM, tipos
  declarados de operação/documento, fonte, data da fonte, ator, confirmação e
  vigência;
- licença, perfil empresarial e permissões são fronteiras independentes. A
  leitura exige sessão oficial com `configs/view`; confirmação e rollback
  exigem `configs/edit`. Permissão `fiscal/configure` não concede alteração do
  perfil, e nenhuma chave/licença participa da autorização;
- toda alteração cria nova versão e auditoria na mesma transação. Vigências são
  fechadas sem apagar versões; mudança MEI→ME/EPP e rollback preservam a linha
  histórica. Concorrência otimista impede sobrescrita de revisão antiga;
- versões formam cadeia SHA-256 de conteúdo para detectar adulteração
  estrutural. Essa cadeia não é assinatura/não-repúdio e não substitui o log de
  auditoria; ausência ou falha da auditoria reverte toda alteração;
- `prepare_legacy_migration` transforma configuração fiscal/básica antiga em
  rascunho não confirmado e não persistido. CNAEs, operações ou obrigações
  ausentes nunca são inferidos;
- readiness é determinístico e exclusivamente informativo: distingue
  `INCOMPLETO`, `AGENDADO` e `PRONTO_INFORMATIVO`, lista campos ausentes e
  mantém `enables_fiscal=false`. Vigência futura não ativa antecipadamente;
- o serviço não consulta internet, não decide obrigação pelo CNPJ, não habilita
  Fiscal/SEFAZ e não altera regras tributárias ou endpoints;
- testes focados: `17 passed`; regressão de Segurança, onboarding/configuração
  fiscal e FiscalService: `195 passed`, `10 subtests passed`; `compileall` e
  `git diff --check` aprovados;
- testes cobrem sessão ausente, permissão insuficiente, confirmação explícita,
  CNPJ/CNAE inválidos, fonte futura, campos ausentes, vigência futura, mudança
  MEI→EPP, concorrência, rollback, auditoria ausente, JSON corrompido, cadeia
  adulterada, migração legada sem persistência e separação de licença/Fiscal;
- nenhum schema, UI, banco real, certificado, segredo, transmissão, outbox,
  regra Fiscal/SEFAZ, licença ou permissão persistida foi alterado.

### Onboarding Qt do perfil empresarial unificado

- branch/worktree isolados: `codex/onboarding-perfil-empresarial-qt` em
  `NabiCode-QT-OnboardingPerfil-codex`, derivados exatamente de `3d875d5`;
- implementação: `aa9891f` — `feat: cria onboarding Qt do perfil empresarial`;
- `CompanyProfileDialog` guia criação ou revisão de CNPJ, razão social, regime,
  enquadramento, CNAEs, UF/município, IE/IM, operações, documentos, fonte e
  vigência. A tela não foi conectada ao shell neste checkpoint;
- licença, permissões e perfil empresarial são explicados como controles
  independentes. O readiness permanece informativo, exibe explicitamente
  `enables_fiscal=false` e não habilita Fiscal/SEFAZ;
- a configuração antiga pode ser carregada somente como rascunho. Ela nunca se
  autoconfirma ou persiste; campos e obrigações ausentes continuam sem inferência;
- revisão validada e normalizada é obrigatória e não grava dados. Uma segunda
  confirmação consciente é exigida antes de chamar a transação oficial; qualquer
  edição invalida a revisão e uma trava impede reentrada/dupla confirmação;
- leitura/revisão exige sessão real com `configs/view`; confirmação exige
  `configs/edit` e registra o ator da sessão. Concorrência otimista bloqueia uma
  revisão antiga e preserva a versão confirmada por outra sessão;
- Enter avança uma etapa, Shift+Enter retorna, Esc cancela e auto-repeat é
  consumido sem ação; cancelamento e falhas de permissão não persistem dados;
- testes focados finais: `28 passed`; regressão ampliada de perfil, Segurança,
  Configurações e Fiscal: `220 passed`, `10 subtests passed`; `compileall` e
  `git diff --check` aprovados;
- nenhum `main_qt.py`, `ui_qt/app.py`, shell, licença, banco real, certificado,
  regra Fiscal/SEFAZ, transmissão ou endpoint foi alterado. Próximo passo seguro:
  revisão independente e integração normal; conexão ao shell deve ser checkpoint
  posterior, separado e explicitamente autorizado.
### Redação central de dados sensíveis

- branch/worktree isolados: `codex/redacao-dados-sensiveis` em
  `NabiCode-QT-RedacaoDados-codex`, derivados exatamente de `1cfdfa4`;
- implementação: `ec290bf` — `security: centraliza redacao de dados sensiveis`;
- `core.sensitive_data` concentra sanitização de texto e estruturas aninhadas
  para senha, tokens/Authorization, certificado/chave privada, XML fiscal
  reproduzido, CPF/CNPJ, e-mail, telefone e raiz de caminho pessoal;
- falha de conversão ou sanitização retorna somente marcador técnico fixo; o
  conteúdo original nunca é usado como fallback;
- formatter diagnóstico, auditoria administrativa (log, evento, persistência e
  consulta) e relatório JSON de diagnóstico usam a mesma política antes da
  saída; IDs técnicos, estados, contagens e hashes continuam disponíveis;
- documentos XML fiscais canônicos e suas áreas próprias de armazenamento não
  foram alterados: somente eventual reprodução em log/diagnóstico é omitida;
- testes adversariais e regressão central: `18 passed`; `compileall` e
  `git diff --check` aprovados;
- não houve mudança em Fiscal/SEFAZ operacional, IA, pacote contábil, Qt, schema
  ou banco real; nenhum dado real ou segredo foi usado;
- próximo passo seguro: revisão independente e integração normal na consolidada,
  seguida de expansão gradual somente nos emissores periféricos comprovadamente
  necessários, sem reescrever regras de negócio.
### Portão obrigatório de prontidão Fiscal/SEFAZ

- implementação isolada: `cbc1e3d` — `fix: exige prontidao antes de operar fiscal`;
- o runtime Legacy liga um único `FiscalReadinessGate` ao serviço fiscal e ao
  auditor oficial do catálogo; instâncias auxiliares sem essa composição não
  representam uma entrada operacional do produto;
- antes de rede ou mutação, o portão exige sessão/permissão oficial, módulo e
  modelo habilitados, homologação, CNPJ, UF/perfil estadual, regime, endpoint,
  A1 válido e correspondente ao emitente, cadeia ICP-Brasil e situação de
  revogação confirmadas pelos mecanismos já existentes;
- autorização e preparação da venda também exigem catálogo sem pendências e
  numeração explicitamente inicializada para ambiente/modelo/série antes de
  qualquer reserva; produção continua bloqueada;
- distribuição DF-e, manifestação, consulta de status, consulta de documento,
  eventos e inutilização passam pelo mesmo portão antes de abrir rede;
- quando faltam requisitos básicos, a Central Fiscal não apresenta operações:
  informa as pendências e abre somente a configuração/diagnóstico;
- testes negativos comprovam que recusa do portão não reserva número e não
  inicia rede DF-e; regressão ampliada: `279 passed`, `10 subtests passed`;
  `compileall` e `git diff --check` aprovados;
- nenhum certificado, XML, banco real ou endpoint real foi usado; nenhuma
  chamada à SEFAZ foi executada e nenhum push foi realizado;
- pendências continuam físicas/documentais: homologação oficial acompanhada,
  evidências com certificado e empresa de homologação, revisão jurídica e
  autorização expressa antes de qualquer futura liberação de produção.

### Correção fail-closed do portão de prontidão Fiscal/SEFAZ

- branch isolada `codex/fiscal-readiness-fail-closed`, derivada exatamente de
  `codex/fiscal-readiness-gate` em `76fc54c`;
- removido o fallback de `_readiness_enforced == False` que autorizava leitura,
  ator coordenado sintético ou autenticação sem executar o portão;
- `FiscalService` nasce sem gate operacional; ausência de composição, flag
  desligada ou tentativa de ligar apenas a flag falha com `PermissionError`
  antes de autenticação, reserva, arquivo, assinatura ou rede;
- o gate composto continua revalidando configuração, CNPJ, certificado,
  confiança/revogação, catálogo e numeração conforme a operação; nenhuma regra
  tributária, XML, endpoint ou modo de produção foi alterado;
- testes novos cobrem inicialização limpa, configuração/CNPJ/A1 ausentes e
  tentativa de bypass; testes DFe comprovam bloqueio antes de rede/reserva;
- regressão focada de prontidão/DFe/Central/venda: `52 passed`; `compileall` e
  `git diff --check` aprovados. A regressão fiscal ampliada foi iniciada, mas
  excedeu a janela curta desta execução e deve ser repetida antes da integração;
- nenhum certificado real, banco real ou chamada SEFAZ foi usado. Comercial e
  módulos não fiscais não passam por esta API e permanecem operacionais;
- próximo passo: revisão independente, regressão fiscal integral e integração
  normal na consolidada; produção fiscal continua bloqueada.
## Radar regulatório — MEI e Simples Nacional em 2027 (pesquisa de 24/08/2026)

Registro preventivo; não representa homologação fiscal nem autorização para alterar leiautes sem nova auditoria.

- fonte oficial: Ministério da Fazenda, notícia de 11/08/2026 sobre as Resoluções CGSN nº 190 e nº 191/2026;
- regra divulgada: as alterações da Resolução CGSN nº 190 produzem efeitos, em regra, a partir de 01/01/2027 e ampliam a emissão de documento fiscal pelo MEI para vendas de mercadorias e prestações de serviços;
- serviços: permanece prevista a NFS-e de padrão nacional, gratuita;
- mercadorias e determinadas prestações de transporte: a regulamentação prevê uso preferencial e gratuito da Nota Fiscal Fácil (NFF);
- Simples Nacional: documentos fiscais passam a observar também as regras de CBS/IBS aplicáveis a partir de 01/01/2027, conforme hipóteses e leiautes oficiais;
- cronograma oficial dos documentos fiscais da Reforma Tributária indica 01/01/2027 para documentos de contribuintes do Simples Nacional, com leiautes previstos para publicação/adequação anterior;
- não existe, nas fontes consultadas, obrigação de o MEI comprar ou usar um programa privado específico. O NabiCode pode integrar os emissores/APIs oficiais quando houver contrato técnico publicado, mas não pode substituir, contornar ou presumir autorização governamental;
- a regra atual anterior à vigência de 2027 não deve ser apagada: a dispensa e as hipóteses de emissão do MEI continuam dependentes da data, operação, destinatário, atividade e ente federado.

Fontes oficiais registradas:

- `https://www.gov.br/fazenda/pt-br/assuntos/noticias/2026/agosto/cgsn-atualiza-regras-do-simples-nacional-para-adequacao-a-reforma-tributaria-do-consumo`;
- `https://www.gov.br/receitafederal/pt-br/assuntos/noticias/2026/julho/receita-federal-e-comite-gestor-do-ibs-publicam-o-cronograma-de-implementacao-dos-documentos-fiscais-eletronicos-da-reforma-tributaria-do-consumo`;
- `https://www.gov.br/receitafederal/pt-br/assuntos/noticias/2026/agosto/simples-nacional-nfs-e-nacional-sera-obrigatoria-para-me-e-epp-a-partir-de-1o-de-novembro-de-2026`;
- `https://normas.receita.fazenda.gov.br/sijut2consulta/link.action?idAto=92278` (Resolução CGSN nº 140/2018 consolidada; conferir novamente antes da implementação).

Checkpoint futuro obrigatório antes de release fiscal 2027:

1. reler Resoluções CGSN nº 190/191 e atos posteriores na fonte normativa consolidada;
2. identificar o enquadramento real do contribuinte (MEI, ME/EPP, atividade, UF e município);
3. homologar leiautes 2027 de NF-e/NFC-e/NFS-e/NFF e campos CBS/IBS sem inventar regra;
4. implementar por adaptadores versionados, mantendo Comercial/NÃO FISCAL isolado;
5. testar nos ambientes oficiais de homologação e preservar evidências físicas;
6. somente então liberar qualquer operação fiscal correspondente.

Estratégia de produto para aproveitar a transição sem reduzir conformidade:

- manter um único NabiCode oficial completo e atualizável, sem binários diferentes por regime tributário; o perfil confirmado da empresa controla módulos, obrigações, campos, assistentes e conectores aplicáveis;
- não inferir enquadramento somente pelo número do CNPJ: onboarding deve confirmar dados oficiais, regime, atividade, UF, município, inscrições e documentos, com rastreabilidade da fonte e da confirmação humana;
- separar três conceitos: licença comercial define o direito de uso; perfil empresarial define o que se aplica; permissões do usuário definem quem pode executar. Nenhum deles pode contornar os outros;
- permitir mudança futura de MEI para ME/EPP ou outro regime por migração de configuração versionada, preservando histórico, documentos e evidências sem reinstalar ou trocar de banco;
- oferecer entrada simples para MEI, sem exigir conhecimento contábil: cadastro guiado, importação de clientes/produtos, vendas, recebimentos, despesas documentadas e pacote mensal Essencial;
- permitir evolução para o pacote Completo/Auditoria e para contador sem nova digitação ou troca de banco;
- usar a Nabi como orientadora e preparadora de rascunhos, nunca como autoridade fiscal ou fonte de regra;
- manter conectores independentes e versionados para NFS-e Nacional, NFF, NF-e/NFC-e e futuros campos CBS/IBS, ativados somente conforme atividade e enquadramento;
- criar um assistente de prontidão 2027 que mostre cadastro incompleto, documentos necessários, ambiente de homologação, data de vigência e evidências pendentes;
- manter o produto utilizável em Comercial/NÃO FISCAL enquanto a configuração fiscal não estiver aprovada, sem permitir emissão fiscal por fallback;
- planejar migração e onboarding rápidos para escritórios contábeis e carteiras de MEIs, com pacotes Essencial/Completo padronizados e sem dependência de fornecedor contábil específico;
- não anunciar “conforme 2027” antes da auditoria jurídica, técnica e de homologação real de cada documento aplicável.

## Regra permanente de evolução do produto

Critério de entrada: uma capacidade entra no NabiCode oficial somente quando reduz trabalho, preserva as regras existentes, possui fronteira autorizada, falha fechada, testes proporcionais ao risco e caminho de atualização/migração sem perda de dados.

Prioridades aprovadas para entrada progressiva:

- perfil empresarial único e onboarding guiado;
- Central do Contador em camadas, conciliação e intercâmbio universal;
- Central de Socorro com diagnóstico determinístico e autorreparo apenas reversível;
- backup autenticado/criptografado e restauração comprovada;
- conectores fiscais versionados conforme documentos e vigências oficiais;
- Nabi global por portas tipadas, com confirmação, idempotência e auditoria;
- acessibilidade, paginação, desempenho e mensagens humanas.

Critério de retirada/proibição:

- edições diferentes do NabiCode oficial por regime, telas duplicadas, botões provisórios ou sem ação;
- carregamento integral desnecessário, acesso direto da GUI/IA ao banco e identidade fornecida livremente pelo chamador;
- senha mestra universal, permissão implícita, função escondida que contorne autorização ou fallback fiscal;
- autorreparo de venda, Caixa, estoque, Fiscal, licenciamento, usuários, backup/restore ou atualização sem o nível de confirmação exigido;
- logs/pacotes de suporte com segredo ou dado pessoal cru;
- lançamento contábil, regra tributária ou alegação de conformidade inventados.

O Fichário permanece uma finalidade/produto especial e isolado. Melhorias compartilháveis podem ser reaproveitadas após auditoria; regras exclusivas do Fichário não entram incidentalmente no NabiCode oficial.

### Homologação reproduzível do primeiro uso Qt

- branch/worktree isolados: `codex/homologacao-primeiro-uso` em
  `NabiCode-QT-PrimeiroUso-codex`, derivados exatamente da integração resiliente
  `739ad558033ba6621f25272ac4347d156acf7044`;
- implementação: `af57e6d` — `test: homologa primeiro uso Qt em ambiente isolado`;
- `build_tools/homologate_first_use.py` reproduz em diretório vazio e descartável
  a sequência licença ausente/restrita → licença Ed25519 efêmera de teste → banco
  novo/schema atual → primeiro administrador → login obrigatório → shell Qt →
  Vendas → fechamento seguro;
- o ensaio substitui `APPDATA` somente no subprocesso, força o perfil `TESTE`,
  recusa o diretório ativo do NabiCode e qualquer destino não vazio, bloqueia
  conexões de rede e nunca abre certificado, XML, CSC, banco ou licença reais;
- a chave privada temporária existe somente em memória. O arquivo temporário de
  licença é removido após a ativação do ensaio e não existe `.pem` ou `.pfx` no
  resultado;
- licença ausente foi comprovada antes da criação do banco: Qt e mutações ficam
  bloqueados, enquanto ativação e diagnóstico permanecem disponíveis;
- o primeiro acesso cria somente um administrador e não cria sessão implícita;
  senha incorreta é recusada e o login correto é necessário para abrir o shell;
- dependências de fonte/build verificadas: catálogo público de licença, spec
  oficial, plugins Qt de plataforma e runtimes Tcl/Tk (inclusive Python 3.14 em
  `zipfs`);
- nenhum caminho absoluto da máquina de desenvolvimento foi incorporado ao
  runner ou à configuração; a documentação usa marcador explícito para o Python;
- validação própria: `3 passed`; regressão ampliada de startup, licença, banco,
  primeiro acesso, login, shell, PDV, composição e empacotamento: `212 passed`,
  `5 subtests passed`; `compileall` e `git diff --check` aprovados;
- nenhum defeito operacional de primeiro uso foi confirmado na base, portanto
  não houve alteração do produto para esconder falha. O único ajuste durante o
  ensaio alinhou a ordem de imports do runner ao entrypoint real e reconheceu o
  runtime Tcl 9 distribuído por `zipfs`;
- `docs/HOMOLOGACAO_PRIMEIRO_USO_QT.md` contém o roteiro humano curto: instalar,
  ativar com licença emitida externamente, configurar empresa, criar o primeiro
  administrador, entrar e abrir Vendas;
- o roteiro foi separado em três portões: Fase A comercial TESTE; Fase B de
  prontidão Fiscal exclusivamente local/offline, sem senha persistida; e Fase C
  manual posterior com proprietário presente e somente SEFAZ HOMOLOGAÇÃO;
- qualquer falha da Fase A impede iniciar Fiscal; cadastro, A1, cadeia, vigência,
  CNPJ, ambiente, série/numeração ou preflight pendentes bloqueiam a Fase C;
  PRODUÇÃO permanece proibida e nenhuma fase a libera implicitamente;
- pendências: o instalador final não foi gerado; instalação/desinstalação física,
  ativação com licença TESTE real, DPI/tela, atalhos e abertura em uma segunda
  máquina Windows continuam exigindo homologação humana antes de release.

#### Correção confirmada na homologação visual de primeiro uso

- `6f08e33` — `fix: mantem ativacao aberta no primeiro uso`;
- a execução real sem licença revelou que o Qt oficial apenas mostrava o bloqueio
  e encerrava. Agora permanece em diálogo restrito, mostra e copia o código da
  máquina e permite selecionar uma `.nabilic`, sempre antes de rede, banco e
  serviços;
- somente uma licença assinada que libere a capacidade Qt permite continuar;
  falha, cancelamento ou edição incompatível permanecem bloqueados;
- o ensaio descartável passou a fechar explicitamente a conexão SQLite de
  verificação, eliminando o arquivo temporário preso no Windows;
- validação focada: `26 passed`; ensaio completo novamente aprovado com licença
  temporária em memória, banco novo, administrador, login, shell e Vendas, sem
  rede fiscal; `compileall` e `git diff --check` aprovados;
- ativação manual TESTE, criação do administrador e login foram confirmados pelo
  proprietário. A rodada visual seguinte encontrou lacunas de UX/integração que
  seguem em checkpoints isolados e não devem ser confundidas com Fiscal.
- `0e95e6d` adiciona a Nabi como guia determinístico já no primeiro acesso após
  a licença: orienta empresa, CNPJ, e-mail, usuário e senha, inclusive no modo
  não fiscal e sem depender de modelo GGUF. Antes da licença a IA permanece
  desligada; nenhuma orientação inicia banco, rede ou comunicação fiscal.
- validação do guia: `14 passed` na composição Qt e `3 passed` no ensaio de
  primeiro uso; `compileall` e `git diff --check` aprovados.
## Integração resiliente/contábil — validação de abertura e regressão

- branch: `codex/integracao-resiliencia-contabil`;
- foram preservados por merges normais os históricos de supply chain fechada V2, auditoria crítica fail-closed, backup criptografado Qt, Central do Contador Qt, onboarding do perfil empresarial, redação de dados sensíveis, portão fiscal fail-closed e radar MEI 2027;
- o caminho mínimo licença → banco → primeiro acesso/login → shell Qt → módulos principais foi validado com `105 passed` e `3 subtests passed`;
- a primeira regressão integral encontrou seis testes antigos cujos fakes/schemas não declaravam a auditoria estrita agora obrigatória; somente as estruturas de teste foram alinhadas, sem reintroduzir fallback no produto;
- validação focada após o alinhamento: `12 passed`, `3 subtests passed`;
- regressão integral final: `2313 passed`, `1 skipped`, `460 subtests passed`, zero falhas e dois avisos externos/conhecidos;
- `git diff --check` aprovado; nenhum banco, certificado, XML real, chave ou segredo foi usado;
- novas interfaces permanecem desacopladas do shell até checkpoint próprio de composição e homologação visual.

### Trilhos seguros da Nabi para erros e onboarding técnico

- branch/worktree isolados: `codex/nabi-erros-seguros` em
  `NabiCode-QT-NabiErrosSeguros-codex`, derivados do commit confirmado
  `52bbfe2a361629471cc8e0dfa5a9694f56e0c0f0` de
  `codex/homologacao-primeiro-uso`; o checkout de origem tinha alterações locais
  e foi preservado sem sobrescrita;
- implementação: `0a828a8` — `feat: adiciona trilhos seguros da Nabi para erros`;
- a auditoria confirmou que o broker opaco de confirmação e o outbox fiscal já
  existiam. A implementação reutiliza ambos e cobre somente as lacunas Nabi:
  diagnóstico/rascunho de NCM, consulta/reconciliação fiscal segura e roteiro
  técnico pós-licença independente de GGUF;
- `produtos.diagnosticar_ncm` nunca sugere classificação. O rascunho exige NCM
  explícito com exatamente oito dígitos não genéricos, fonte humana/documental
  permitida (`CONTADOR`, `DOCUMENTO_FISCAL`, `FORNECEDOR` ou `TABELA_OFICIAL`)
  e referência verificável; nada é persistido antes de confirmação reforçada;
- a execução deriva o ator da sessão oficial, consome autorização opaca de uso
  único, detecta NCM alterado desde a revisão e grava atomicamente somente a
  coluna `ncm` e o diário idempotente. Preço, descrição, estoque e demais dados
  comerciais permanecem intactos; nenhuma autorização fiscal é alegada;
- `fiscal.diagnosticar_fila` lê o estado real do outbox existente e devolve
  resultado sanitizado. `RESPOSTA_DESCONHECIDA` só admite rascunho de
  reconciliação por recibo/chave; recibo pendente só admite consulta. Estado sem
  referência, erro comum, estado terminal ou desconhecido falha fechado;
- nenhuma ferramenta Nabi chama `retry_transmission`, `transmit` ou
  `authorize_document`. O gateway delega exclusivamente a
  `reconcile_unknown` e `force_receipt_check`, que mantêm autenticação e regras
  do `FiscalService`; venda comercial fica preservada e o retorno fixa
  `authorization_claimed=false` e `blind_resend_performed=false`;
- `NabiTechnicalOnboardingService` é uma porta somente leitura, determinística e
  sem dependência de modelo/GGUF. Antes de licença operacional com recurso Nabi,
  falha antes até de consultar a prontidão; depois, ordena empresa/CNPJ, regime,
  usuários/acessos, caixa, impressão e backup. Fiscal aparece somente se o perfil
  estiver habilitado e permanece checklist/readiness informativo, sempre com
  `fiscal_release_authorized=false`;
- o guia visual de primeiro acesso publicado posteriormente na branch de origem
  não foi alterado nem regravado. A futura integração visual deve apenas chamar
  a porta determinística deste checkpoint;
- testes adversariais cobrem NCM ausente/inválido/genérico, fonte de IA recusada,
  ausência de evidência, confirmação reforçada/uso único, usuário forjado,
  concorrência/stale, rollback, idempotência, preservação comercial, estados do
  outbox, mudança de estado, ausência de recibo/chave, consulta de recibo sem
  reenvio, socket bloqueado, licença ausente/recurso Nabi ausente, regime não
  inferido e Fiscal habilitado/desabilitado sem liberação;
- regressão Nabi/outbox/licença: `200 passed`, `38 subtests passed`; regressão de
  FiscalService, produtos, perfil empresarial e composição licenciada:
  `185 passed`, `10 subtests passed`; `compileall` e `git diff --check`
  aprovados;
- as provas usam adapters fake determinísticos e SQLite exclusivamente em
  memória para atomicidade. Nenhum socket, certificado, XML, senha, banco real
  ou chamada SEFAZ foi usado;
- não foram alterados `main_qt.py`, licenciamento, UI/UX, PDV, regras
  tributárias, schema, endpoint, certificado ou worker fiscal. A composição no
  shell/guia visual permanece checkpoint posterior; isto não é homologação
  fiscal real e não libera PRODUÇÃO.
## UX global segura sobre a homologação de primeiro uso — 25/08/2026

- branch/worktree isolados: `codex/ux-global-primeiro-uso` em
  `NabiCode-QT-UXPrimeiroUso-codex`, derivados exatamente de
  `codex/homologacao-primeiro-uso` em
  `52bbfe2a361629471cc8e0dfa5a9694f56e0c0f0`;
- o checkout de origem permaneceu intocado com as quatro alterações locais de
  ativação já existentes; `main_qt.py`, `licensing/`, IA, Fiscal e banco real
  não foram alterados;
- `8c7241d` padroniza setas e Enter no hub administrativo, preservando
  auto-repeat bloqueado, Shift+Enter regressivo e autorização individual de
  cada módulo;
- `bd14ed7` transforma os resumos laterais em cards de clientes acessíveis e
  clicáveis, ligados aos segmentos existentes `all/current/owing/alert` do
  `DashboardRepository`; a janela filtrada continua exigindo `clientes/view` e
  não consulta o banco pela GUI;
- Clientes e Produtos deixam de ser comprimidos dentro da área central do
  shell e abrem como janelas Qt amplas/maximizadas, reutilizadas por módulo e
  fechadas junto com o shell;
- os botões inferiores passam a herdar o tema metálico principal do shell; as
  setas percorrem cards e grades sem executar ações, enquanto Enter executa uma
  única vez;
- o gatilho Legacy de dez cliques em até cinco segundos foi restaurado no logo.
  Ele falha fechado antes de mostrar senha sem `technical/view`, usa somente
  `SecurityService.confirm_manager_password` e abre apenas módulos já marcados
  como `technical`; cada entrada mantém sua permissão própria. Nenhuma senha,
  licença ou operação administrativa paralela foi criada;
- validação focada: `92 passed` em grupos isolados de shell/hub, Clientes,
  Produtos, composição, segmentos do dashboard e segurança; casos adversariais
  cobrem auto-repeat, janela temporal reiniciada, permissão negada, senha errada,
  troca de segmento e reuso de janela;
- `python -m compileall -q ui_qt` e `git diff --check` aprovados. A coleta direta
  isolada de alguns testes no Python 3.14 ainda depende da ordem histórica de
  imports entre `repositories` e `services`; o mesmo comportamento foi
  reproduzido sem este diff na base de primeiro uso e não foi alterado neste
  escopo;
- próximo passo: homologação visual humana em DPI/telas suportadas e integração
  por merge normal após revisão dos commits. O push desta branch foi autorizado.
## Correção isolada do PDV Qt após homologação do primeiro uso

- branch: `codex/pdv-qt-correcao-homologacao`, derivada de
  `codex/homologacao-primeiro-uso` em `2929d19`;
- `76015dc` — `fix: isola servico do modulo de produtos`;
- causa comprovada da mensagem
  `PurchaseManagementService object has no attribute search`: as fábricas Qt de
  Produtos e Compras capturavam a mesma variável local `service`; a composição
  posterior de Compras substituía a referência usada pela fábrica de Produtos;
- cada fábrica agora captura explicitamente sua fachada tipada, e uma regressão
  adversarial abre Produtos com Compras também presente para impedir retorno do
  defeito;
- `b26af3b` — `fix: estabiliza catalogo e pagamentos do pdv`;
- seta para baixo no campo vazio de produto passa a consultar e abrir a lista
  rápida; catálogo vazio é informado no próprio PDV, e auto-repeat é consumido
  sem repetir consultas;
- Pagamentos foi organizado em três seções visuais — formas, ajustes e condições
  do crediário — sem mover cálculos para a GUI; desconto e acréscimo identificam
  explicitamente `R$` ou `%` conforme o tipo selecionado;
- a auditoria confirmou que desconto em valor e percentual continuam calculados
  pelo `PDVApplicationService`; testes cobrem os dois tipos, pagamentos mistos,
  revisão/confirmação separadas, navegação por Enter/Shift+Enter e bloqueio de
  auto-repeat;
- `d5cfee0` — `fix: sincroniza ajustes e parcelas no pagamento`;
- digitação e troca de tipo de desconto ou acréscimo agora recalculam de imediato
  total final, sugestão editável de pagamento e falta/troco; a regressão inclui o
  caso explícito de `R$ 21,00` passando a `R$ 19,95`, sem conservar a sugestão
  anterior;
- pagamentos já adicionados nunca são reescritos pela mudança de ajuste: a
  revisão é invalidada, o saldo é atualizado e a GUI orienta revisar, completar
  ou remover os pagamentos antes de confirmar;
- para crediário, quantidade, distribuição e total financiado das parcelas são
  exibidos a partir do `preview_checkout` do núcleo comercial; também foi
  corrigida a comparação do valor Qt da forma de pagamento que impedia exibir as
  condições antes de adicionar o crediário;
- recusa do checkout retorna ao PDV com carrinho, cliente e total preservados,
  uma única tentativa registrada e foco em Finalizar, agora coberto por teste de
  interface;
- validação focada final: `206 passed`, `2 subtests passed`; regressão integral
  final: `2331 passed`, `1 skipped`, `460 subtests passed`; `compileall` e
  `git diff --check` aprovados;
- nenhum arquivo de IA, Fiscal/SEFAZ, licença ou `main_qt.py` foi alterado; não
  houve mudança de regra fiscal nem de reenvio SEFAZ;
- próximo passo: homologar visualmente no Windows a abertura de Produtos com
  Compras habilitado, catálogo por seta para baixo, seções de Pagamentos e retorno
  após uma recusa comercial controlada.

### Sessão operacional durante o expediente e integração visual

- `f402220` remove a expiração automática padrão por inatividade: a sessão
  autenticada permanece válida até logout/troca de usuário, fechamento do
  processo, revogação da conta ou licença. Confirmações próprias de operações
  sensíveis permanecem obrigatórias;
- o timeout continua disponível para contextos que o instanciem explicitamente,
  com regressão própria; o padrão comercial não interrompe vendas ou cadastros;
- `073da8b` integra por merge normal a UX global (cards filtráveis, janelas
  amplas, teclado, tema inferior e menu técnico com dupla barreira);
- `a10919f` integra por merge normal Produtos/catálogo/Pagamentos e preserva os
  testes das duas trilhas durante a resolução exclusivamente aditiva;
- regressão consolidada depois dos merges: `2355 passed`, `1 skipped`,
  `460 subtests passed`, zero falhas e dois avisos externos conhecidos;
  ensaio de primeiro uso completo também aprovado, sem rede Fiscal/SEFAZ.

#### Consolidação após stress e correção da ordem de imports

- `110d018` integra por merge normal o checkpoint de consultas comerciais sob
  carga, preservando todas as trilhas anteriores;
- coleta fresca antes bloqueada pelo ciclo `repositories`/`services` passou em
  conjunto (`46 passed`), sem depender da ordem de imports;
- ensaio descartável licença → banco → administrador → login → shell → Vendas
  foi repetido e aprovado, ainda sem rede Fiscal/SEFAZ;
- regressão integral consolidada final: `2362 passed`, `1 skipped`,
  `460 subtests passed`, zero falhas e somente dois avisos externos conhecidos.
## Consultas comerciais sob carga — checkpoint isolado

- branch/worktree: `codex/stress-consultas-servicos` em
  `NabiCode-QT-StressConsultas-codex`, derivados de
  `origin/codex/homologacao-primeiro-uso@80a70f4`;
- implementação: `c22ec0f` e normalização de teste `28a2dbe`;
- o gargalo comprovado da pesquisa de produtos materializava todo o catálogo e
  só depois aplicava o limite no gateway. Com 20.000 produtos, consumia cerca de
  2.091 ms e 49,4 MB para exibir 30 linhas; após paginação/limite no SQL, mediu
  cerca de 7,7 ms e 81 KB. Em 100.000 produtos, manteve 30 linhas, cerca de
  8,9 ms e 81 KB;
- busca de produto por nome, código e barras agora é limitada na origem; o
  fallback sem acentos percorre o cursor em lotes e para ao completar a página;
  catálogo vazio e detecção de código de barras duplicado preservam os contratos;
- sugestão de cliente deixou de cortar 200 linhas antes da ordenação: ficha
  exata, código/nome exatos, início/parte do nome e desempates por nome, ficha e
  ID são resolvidos deterministicamente. A ficha exata inserida após centenas
  de parciais permaneceu na primeira posição;
- segmentos Em dia, Devendo, Atrasados e Dívida possuem página limitada e total
  completo no mesmo snapshot de leitura. Índices idempotentes foram adicionados
  para ordenação de clientes, catálogo ativo e pendências por cliente/vencimento;
- com 100.000 registros: página de 50 clientes mediu cerca de 20,5 ms/22 KB,
  sugestão limitada a 30 cerca de 65,9 ms/17 KB e resumo completo cerca de
  251,8 ms/3 KB. Os planos SQL confirmaram uso dos três índices novos;
- o ciclo de imports `repositories → estoque_repository → services →
  estoque_service → repositories` foi reproduzido em intérprete novo e removido
  por import local estrito da política de auditoria. As ordens `repositories →
  services` e `services → repositories` passam isoladamente;
- concorrência já oficial de criação de clientes e vendas comerciais foi
  revalidada em banco TEMP: uma criação vence/uma duplicada é recusada e vendas
  concorrentes respeitam limite/transação, sem banco real, rede ou SEFAZ;
- validação ampliada: `131 passed`, `5 subtests passed`; regressão específica
  final: `3 passed`; `compileall` e `git diff --check` aprovados;
- risco residual honesto: pesquisa textual por substring continua linear no
  SQLite (sem FTS) e o resumo completo cresce com o número de pendências. Aos
  100.000 registros permaneceu abaixo de 300 ms no ensaio local; somente migrar
  para FTS/cache se telemetria real futura comprovar necessidade, preservando a
  busca oficial e sem materializar o catálogo.

## Regressão fiscal e dossiê OFFLINE — 25/08/2026

- branch/worktree isolados: `codex/fiscal-regressao-offline` em
  `NabiCode-QT-FiscalRegressaoOffline-codex`, derivados exatamente de
  `origin/codex/homologacao-primeiro-uso@a179e791a82bc0a58c4ccccc1bccf357b6008fa8`;
- as duas falhas herdadas do dossiê em
  `FiscalAuthorizationNumberingIntegrationTests` foram reproduzidas na história
  e auditadas. Na base integrada já estavam corrigidas por `65f0500` e os dois
  testes passam sem alteração; a causa era fixture anterior que não compunha o
  portão de prontidão fail-closed;
- a fixture foi reforçada para verificar os parâmetros reais do portão:
  autorização, modelo 55, série 1, catálogo, numeração e revogação. A auditoria
  então revelou a lacuna funcional residual: `authorize_document` aceitava
  resposta síncrona de sucesso sem uma reserva de numeração correspondente;
- `8fbe536` exige reserva `RESERVADO` no mesmo ambiente, modelo, série e número
  antes de ler XML, assinar ou transmitir. Gate ausente/recusado continua
  bloqueando primeiro; rejeição preserva a reserva e somente sucesso sintético
  confirma o número uma única vez. A matriz adversarial bloqueia socket e cobre
  ausência de gate/reserva, recusa de numeração e reservas terminais ou
  divergentes;
- `342879c` e `eaf10cc` trazem o dossiê determinístico OFFLINE preservado, com
  hashes estáveis entre finais de linha. `852a1b1` eleva o harness a `1.1.0` e
  acrescenta `PRONTIDAO-NUMERACAO-AUSENTE`, que prova bloqueio antes até do
  transporte fake e store em memória;
- dossiê final: `17/17` cenários aprovados; JSON SHA-256
  `578f61213164a998c9879bd92b514213c0c28ad215a42aad951e8af07dc28af3` e
  resumo humano SHA-256
  `40d3c4c5c79f882983944af5f35b1fe91909ae3b8130ab202e337360305311c0`;
- regressão fiscal ampliada sobre 26 módulos: `421 passed`, `10 subtests passed`,
  sem falhas e com um único aviso externo conhecido do
  `brazilfiscalreport`; matriz focada final: `23 passed`; `compileall` de
  `services`/`tests` e `git diff --check` aprovados;
- os adapters e dados são integralmente fake/sintéticos. Guards de runtime
  provaram `0` tentativas/chamadas de rede, `0` conexões de banco e `0` leituras
  de certificado/chave; nenhum XML, certificado, senha, banco, socket, endpoint
  ou SEFAZ real foi usado;
- não foram alterados UI, IA/Nabi, licenciamento, `main_qt.py`, PDV, regra
  tributária, endpoint ou schema. Isto é somente TESTE OFFLINE: não é
  homologação física/real, não comprova autorização SEFAZ e mantém PRODUÇÃO
  fiscal bloqueada;
- próximo passo: revisão dos commits e integração por merge normal. Homologação
  física, credenciamento, A1/CSC, impressão e SEFAZ permanecem pendentes e fora
  deste checkpoint.
### Central de Socorro — diagnóstico somente leitura

- branch isolada `codex/central-socorro-diagnostico`, base `d7769b0`;
- catálogo fechado por enums, `HelpEntry` e `DiagnosticResult` imutáveis, estados
  `SAUDAVEL`, `ALERTA`, `FALHA` e `INCONCLUSIVO`;
- checks iniciais: disco, diretórios persistentes sem escrita, banco por porta
  read-only, backup diário, impressora e runtime Nabi opcional;
- serviço não contém SQL, shell, credencial ou autorreparo; portas ausentes e
  exceções viram resultado seguro sem impedir os demais checks;
- auditoria recebe apenas estados sanitizados; XML/PII/segredos não são emitidos;
- testes focados: `6 passed`; `compileall` e `git diff --check` aprovados;
- nenhuma UI, Fiscal/SEFAZ, Caixa, estoque, venda, Qt, licença ou banco real foi alterado.

### Central de Socorro — interface Qt somente diagnóstica

- branch/worktree isolados: `codex/central-socorro-qt` em
  `NabiCode-QT-CentralSocorroQt-codex`, derivados exatamente de `4a84d90`;
- implementação: `f4ddd94` — `feat: cria Central de Socorro Qt somente diagnostica`;
- a janela apresenta os seis checks do catálogo fechado em cartões com estados
  `SAUDAVEL`, `ALERTA`, `FALHA` e `INCONCLUSIVO`; detalhes e identificadores
  técnicos são sanitizados novamente antes da exibição;
- execução ocorre em `QThreadPool`, fora da thread gráfica. Reentrada é bloqueada,
  respostas de geração anterior são descartadas e os workers permanecem vivos
  até a conclusão;
- a tela explica separadamente o que foi protegido/testado e o que permanece
  inconclusivo ou dependente de homologação física. Nenhum estado é apresentado
  como reparo, autorização ou prova fiscal;
- o relatório JSON `nabicode.help-center-report.v1` cobre exatamente um resultado
  por check, repete os limites do diagnóstico, sanitiza todo texto e é gravado por
  arquivo temporário + `fsync` + substituição atômica. Falha preserva o destino
  anterior e remove o temporário;
- Enter avança ou executa uma única ação, Shift+Enter retorna, Esc fecha e invalida
  resultado tardio, e auto-repeat é consumido sem ação;
- testes focados finais: `12 passed`; regressão administrativa/Qt e redação:
  `51 passed`; `compileall` e `git diff --check` aprovados;
- não há autorreparo, SQL, shell, credencial, gravação operacional ou conexão a
  `main_qt.py`/shell. Fiscal/SEFAZ, Caixa, estoque, vendas, licença e banco real
  permaneceram intocados; conexão ao shell exige checkpoint posterior separado.
### Conexão mínima da Central de Socorro ao hub

- a Central de Socorro diagnóstica passou a aparecer no hub administrativo sob `configs/view`, sem criar atalho oculto ou contornar sessão/permissões;
- banco usa `quick_check` em conexão SQLite `mode=ro` e `query_only`; pastas e backups são apenas inspecionados; impressoras são consultadas e a Nabi ausente permanece inconclusiva;
- nenhum diretório, backup, banco ou configuração é criado/alterado pelo novo módulo;
- validação focada de composição, serviço e Qt: `25 passed`; `compileall` e `git diff --check` aprovados.

### Central de Socorro — catálogo de autorreparo VERDE

- branch/worktree isolados: `codex/central-socorro-autorreparo-verde` em
  `NabiCode-QT-SocorroAutorreparoVerde-codex`, derivados exatamente de
  `ea1ffd3`;
- implementação: `3bd4b46` — `feat: adiciona autorreparo verde tipado ao
  socorro`;
- catálogo fechado e imutável aceita somente quatro operações VERDE:
  normalizar preferências visuais inválidas, limpar cache/temporário registrado,
  reiniciar o runtime local da Nabi e regenerar cache de relatórios;
- `RepairRequest` exige enum e chave opaca; texto livre, nome de ferramenta ou
  comando produzido pela IA não atravessa a fronteira. Repetição da mesma chave
  devolve o mesmo resultado e colisão com outro reparo falha fechada;
- resultados tipados são exclusivamente `PROVADO`, `FALHOU`, `REVERTIDO` ou
  `INCONCLUSIVO`, com precheck, postcheck, snapshot e rollback verificável;
- preferências visuais preservam cópia integral em memória, aplicam somente a
  normalização fornecida pela porta e restauram exatamente o snapshot quando a
  pós-checagem ou a auditoria estrita falha;
- limpeza aceita apenas tupla registrada de raiz absoluta explícita + caminho
  relativo. Raiz de volume, escape `..`, ADS, alvo duplicado/sobreposto,
  symlink, junction/reparse point e tipo especial são recusados antes da
  alteração; alvos passam por quarentena confinada e o rollback compara SHA-256
  de nomes/conteúdo sem registrar os dados;
- reinício da Nabi usa exclusivamente callbacks tipados de snapshot, restart e
  rollback; não recebe PID, processo, operação em andamento, shell ou comando;
- cache de relatórios é regenerado exclusivamente por porta tipada, com geração
  anterior, validade posterior e restauração da geração original quando não há
  prova de sucesso;
- toda mutação exige auditoria estrita antes de começar. A auditoria recebe
  apenas enum, fase, resultado, indicador de mudança, ID técnico fechado e hash
  da chave; falha de persistência bloqueia a ação ou força a restauração;
- 13 testes adversariais novos cobrem catálogo fechado, imutabilidade, replay,
  colisão de escopo, normalização, rollback, containment, raiz ampla, ADS,
  duplicidade, sobreposição, reparse, quarentena, callbacks e falha da auditoria;
- regressão relacionada final: `73 passed`; suíte integral anterior ao último
  endurecimento de caminho: `2208 passed`, `1 skipped`, `444 subtests passed`,
  com somente a depreciação externa já conhecida do `BrazilFiscalReport`;
  `compileall` completo e `git diff --check` aprovados após o endurecimento;
- não houve ligação à interface/composição e `main_qt.py` permaneceu intocado.
  Banco, backup/restauração, atualização, licença, usuários, vendas, Caixa,
  estoque, Financeiro, Fiscal/SEFAZ e reparos de sistema operacional ficaram
  fora do catálogo e não foram acessados ou alterados;
- próximo passo seguro: revisão independente do contrato e, somente em
  checkpoint coordenado posterior, composição explícita das quatro portas e da
  auditoria oficial; não promover texto da Nabi a comando nem ampliar o catálogo
  sem novo desenho, testes e autorização.

### Integração isolada da Central de Socorro e do catálogo VERDE

- branch/worktree: `codex/integracao-socorro-verde-homologacao` em
  `NabiCode-QT-IntegracaoSocorroVerde-codex`, derivados exatamente de
  `origin/codex/homologacao-primeiro-uso@a179e79`; a branch estável não recebeu
  merge nem alteração;
- a ancestralidade foi conferida antes da integração. `5a70477` e `7cde9f7`
  são trilhas irmãs e não ancestrais entre si; seus merge-bases com a base
  estável são, respectivamente, `739ad558` e `d7769b0`, e o merge-base entre
  as duas trilhas é `ea1ffd3`;
- os históricos publicados foram preservados por merges normais, na ordem da
  dependência: `fc1626f` integra a Central Qt e `2926083` integra o catálogo
  VERDE. Os conflitos limitaram-se ao mapa e foram resolvidos aditivamente,
  mantendo as evidências das duas origens e da base estável;
- `afa925e` conecta a tela ao catálogo fechado e imutável, exibindo exatamente
  as quatro operações tipadas publicadas. Diagnóstico nunca dispara reparo,
  não existe campo de comando/texto livre, toda execução exige confirmação
  explícita e auto-repeat não produz nova ação;
- a composição dispõe hoje de porta segura real apenas para preferências
  visuais: snapshot integral sem normalização silenciosa, normalização tipada,
  pós-checagem e restauração exata. A ação exige `configs/edit` e auditoria
  estrita antes da mutação; falha de auditoria bloqueia ou reverte a mudança;
- limpeza de cache/temporário registrado, reinício local da Nabi e regeneração
  do cache de relatórios permanecem visíveis no catálogo publicado, mas retornam
  `INCONCLUSIVO` porque a base estável não oferece portas seguras correspondentes.
  Nenhuma pasta, processo, PID, comando, operação em andamento ou gerador de
  cache foi inventado para simular suporte;
- os únicos resultados aceitos continuam sendo `PROVADO`, `FALHOU`, `REVERTIDO`
  e `INCONCLUSIVO`; o diálogo valida o catálogo e o resultado retornado antes de
  exibi-lo e mantém chaves opacas por execução;
- `8ae2cdf` torna determinística a prova de nova coleta diagnóstica: o teste
  verifica que o resultado não foi reutilizado sem comparar literalmente o
  espaço livre em disco, valor ambiental que oscila durante a suíte;
- validação focada final: `91 passed`; a prova de repetição passou cinco vezes
  consecutivas. Regressão integral final: `2397 passed`, `1 skipped`, `460
  subtests passed`, zero falhas e somente os dois avisos externos já conhecidos;
  `compileall`, `git diff --check` e conferência de escopo aprovados;
- não houve acesso a banco real nem alteração de Fiscal/SEFAZ, IA operacional,
  licença, `main_qt.py`, regras de negócio ou reparos amarelos/vermelhos. O
  próximo passo é homologação visual do fluxo explícito de preferências e dos
  três retornos inconclusivos, ainda sem promover esta branch na estável.

## Candidata integrada de primeiro uso — 25/08/2026

- branch: `codex/integracao-primeiro-uso-completa`, criada da base estável
  `a179e791a82bc0a58c4ccccc1bccf357b6008fa8`;
- merges normais preservam Fiscal OFFLINE estrito (`283069e`), entrega contábil
  confiável (`212c726`) e Central de Socorro/reparos VERDES (`d012a13`);
- conflitos limitaram-se a documentação e expectativa aditiva da composição;
  Central do Contador e Central de Socorro permanecem simultaneamente presentes,
  cada uma com sessão, permissão e ação humana próprias;
- validação combinada focada: `81 passed`; regressão integral final:
  `2456 passed`, `1 skipped`, `492 subtests passed`, zero falhas e apenas dois
  avisos externos conhecidos;
- `compileall` e `git diff --check` aprovados; ensaio descartável completo de
  primeiro uso repetido com licença temporária, banco novo, administrador,
  login, shell e Vendas, sem comunicação Fiscal/SEFAZ;
- isto não representa homologação física ou autorização SEFAZ. Produção fiscal,
  certificado real e rede permanecem bloqueados até a cerimônia manual.

### Importação local de dados empresariais por XML — checkpoint isolado

- branch/worktree: `codex/empresa-importar-xml` em
  `.worktrees/NabiCode-QT-EmpresaImportarXML-codex`, derivados exatamente de
  `codex/integracao-fiscal-dashboard-final@4bf9ed3`;
- a configuração inicial exibe `Importar dados de XML`; após o primeiro uso,
  Configurações abre o perfil empresarial, que oferece o mesmo botão;
- o importador aceita somente arquivo local XML de NF-e/NFC-e processada,
  modelos 55/65, protocolo literal `cStat=100` e chave de 44 dígitos. DTD,
  entidades, XML inválido/adulterado, modelo diferente e ausência de protocolo
  falham fechados, sem download ou consulta SEFAZ;
- emitente e destinatário são exibidos separadamente. Documento já afirmado no
  cadastro/perfil/configuração fiscal seleciona somente uma correspondência;
  caso contrário o operador precisa escolher. CNPJ/CPF incompatível com os
  documentos já configurados é recusado;
- a prévia mostra campo atual, valor comprovado, origem e ação
  manter/preencher/substituir. Somente após `Aplicar` os dados entram no
  rascunho; cancelamento não altera campos e nenhuma importação persiste o
  perfil sem a revisão e confirmação oficiais já existentes;
- razão social, fantasia, CNPJ/CPF, IE, endereço, município/código IBGE, UF,
  CEP, telefone e e-mail são copiados somente quando presentes. CRT/regime,
  enquadramento, CSC, certificado/senha, séries, numeração e credenciamento não
  são inferidos nem alterados;
- o modelo empresarial versionado passou a preservar os novos campos de forma
  retrocompatível; o arquivo original permanece intacto e nenhum XML real foi
  adicionado ao repositório;
- testes sintéticos cobrem XML válido, empresa emitente/destinatária,
  participante ambíguo, ausências, adulteração, confirmação de sobrescrita,
  cancelamento, incompatibilidade e preservação do original. Validação focada:
  `63 passed`; `compileall` e `git diff --check` aprovados;
- nenhum dado real, senha, certificado, banco real, endpoint, socket, Fiscal
  operacional, emissão, catálogo, Nabi ou SEFAZ foi acessado ou alterado.
  Homologação visual do seletor e da prévia no Windows permanece pendente.

## Caixa e Financeiro — janelas amplas e detalhamento reconciliável

- branch/worktree isolados: `codex/caixa-financeiro-janelas-detalhes` em
  `NabiCode-QT-CaixaFinanceiroDetalhes-codex`, derivados exatamente de
  `52ae726a446d7b85a7b88516e524a645e6947d08`;
- Caixa e Financeiro passaram a abrir como janelas próprias amplas, maximizadas
  e reutilizadas pelo shell, com controles nativos de minimizar, maximizar e
  fechar. Diálogos de confirmação permanecem modais e sem minimização;
- os seis cards do Caixa são botões acessíveis e abrem fotografia imutável do
  resumo oficial. O detalhe é somente leitura, paginado, limitado a 100 linhas
  por página e informa sessão/período, origem, tipo, valor, responsável,
  documento e observação quando existentes;
- cada fotografia compara explicitamente o total do card com a soma das linhas.
  Dinheiro esperado inclui saldo inicial, vendas/recebimentos em dinheiro,
  suprimentos e sangrias com sinal; divergência nunca é apresentada como
  reconciliada;
- origem e documento foram enriquecidos na consulta oficial do Caixa sem alterar
  fechamento, persistência ou regra transacional. Colunas legadas ausentes
  continuam aceitas por detecção de schema;
- sessão e ator são revalidados em toda consulta e ação. Caixa distingue
  `view`, `create` e `reconcile`; Financeiro distingue `view`, `create` e `pay`.
  Sessão expirada ou permissão ausente bloqueia antes da operação;
- Enter abre cada card uma única vez, Shift+Enter e setas retornam/avançam de
  modo determinístico, PgUp/PgDown paginam, Esc fecha e auto-repeat é consumido;
- validação focada final: `80 passed`; regressão `unittest`: `1555 passed`;
  regressão integral final: `2469 passed`, `1 skipped`, `492 subtests passed`,
  zero falhas e apenas dois avisos externos conhecidos; `compileall` e
  `git diff --check` aprovados;
- Fiscal/SEFAZ, IA/Nabi, licenciamento e `main_qt.py` não foram alterados. Não
  houve merge em outra branch nem acesso a banco real; próximo passo é revisão
  dos commits e homologação visual/teclado no Windows antes da integração.

## Auditoria adversarial dos botões da Central Fiscal Qt — 25/08/2026

- branch/worktree auditados: `codex/integracao-fiscal-dashboard-final` em
  `NabiCode-QT-IntegracaoFinal-codex`, iniciando exatamente em `f34f1c4` e com
  árvore limpa;
- a auditoria OFFSCREEN, sem certificado/senha reais, banco operacional, rede ou
  SEFAZ, confirmou cliques de Configurar Fiscal, Atualizar leitura, Fechar,
  Selecionar A1, Revisar e salvar e Cancelar; também cobriu Enter, Shift+Enter,
  Esc e auto-repeat;
- defeito reproduzido: Shift+Enter e Enter auto-repeat nos botões da configuração
  executavam Selecionar A1/Revisar e salvar. O filtro passou a consumir repetição,
  usar Shift+Enter somente para retorno de foco e manter Enter simples como ação
  única; Esc também ficou explicitamente sem auto-repeat;
- o primeiro endurecimento revelou em regressão ampliada um evento tardio durante
  destruição parcial do diálogo; o filtro agora tolera a ausência dos controles e
  o ciclo de abertura/fechamento não deixa exceção residual;
- seleção de arquivo cancelada preserva o caminho anterior; revisão cancelada e
  Cancelar não gravam; erro sintético de certificado limpa a senha, preserva os
  demais dados e mantém a tela aberta; salvamento confirmado limpa a senha;
- validação final: `39 passed` no ciclo focado de diálogo/shell e `525 passed`,
  `18 subtests passed` na regressão ampliada Fiscal/licenciamento/composição/Qt,
  com somente a depreciação externa já conhecida do `brazilfiscalreport`;
  `compileall` e `git diff --check` aprovados;
- nenhuma transmissão, autorização, consulta, XML, certificado, senha ou endpoint
  real foi usado. Produção fiscal e homologação SEFAZ continuam bloqueadas.
