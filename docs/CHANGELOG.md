# 2.5.2 R22 — candidata consolidada

- Unifica as trilhas Qt comercial, fiscal e administrativa já homologadas em uma única candidata.
- Completa o cadastro fiscal do cliente e preserva as travas fail-closed da emissão fiscal.
- Mantém produção fiscal bloqueada até a homologação manual com credenciamento, contador e A1 reais.
- Gera um artefato com identidade própria para impedir confusão com a instalação antiga 2.5.1.

# 2.4.47 — Sprint 1.6 Produtos

- Estado de preenchimento e leitura do formulário extraído do `nabicode_legacy.py`.
- Resolução de seleções para IDs centralizada no `ProductApplicationService`.
- Adicionado `ProductFormState` e testes de regressão.
- 521 testes aprovados.

# 2.4.46 — Sprint 1.5 Produtos

- Montagem de `ProductSaveCommand` removida da UI legada.
- Criado `ProductFormData` para transportar valores brutos do formulário.
- Conversão numérica centralizada no `ProductApplicationService`.
- Adicionados testes de conversão, padrões e rejeição de valores inválidos.


## Etapa 13 — decisão explícita e similaridade na conferência XML
- Itens do XML agora recebem candidatos de produtos com percentual de similaridade.
- Correspondências aproximadas ficam pendentes até o usuário escolher Vincular, Atualizar ou Criar.
- A conferência mostra lado a lado a descrição do XML e o produto candidato com critério e percentual.
- A importação bloqueia decisões incoerentes, impedindo atualização automática de produto apenas semelhante.

- Atalho `F4` agora altera a quantidade do item selecionado no carrinho e recalcula o subtotal; sem seleção, mantém o foco no campo de quantidade do próximo item.
## Etapa 20 — Complementos finais do PDV
- Cliente rápido acessível por `Shift+F3`, selecionando automaticamente o cadastro criado.
- Desconto percentual por item acessível por `F10`, preservando o preço original para reaplicação ou remoção do desconto.
- `Enter` finaliza a venda quando o foco está na tabela do carrinho e adiciona o item quando os campos do produto estão completos.
# Changelog

## 2.4.31 — Ajuda contextual (Etapa 6)

- F1 identifica a janela ou módulo ativo e abre ajuda específica.
- Tópicos para Dashboard, Produtos, Cadastro de Produto, Clientes, PDV, XML, NF-e de devolução e Configurações.
- Ajuda pesquisável com filtro por tecla ou ação.
- Atalhos gerais disponíveis a partir de qualquer tópico.
- Contexto da tela principal passa a ser atualizado ao navegar.

# NabiCode v2.4.29

- Ctrl+S, Del e Esc centralizados pelo WindowActionController.
- Confirmação ao fechar formulários com alterações não salvas.
- Exclusão padronizada com confirmação e descrição do impacto.
- Cadastro de produtos, importação XML e PDV integrados ao controlador universal.
- Ctrl+N e Ctrl+E conectados às telas principais de Produtos e Clientes.


## 2.4.24 — Exclusão segura de NF-e importada

- Botão **Notas importadas** na tela de Produtos.
- Filtro de notas por período.
- Seleção múltipla e prévia do impacto no estoque.
- Senha administrativa e snapshot obrigatório antes da exclusão.
- Reversão transacional das entradas de estoque.
- Remoção do espelho usado pelo Assistente de Devolução.
- Liberação da chave de acesso para nova importação em testes.
- Bloqueio quando há devolução registrada, título pago ou estoque insuficiente.

## 2.4.22 — Menu inicial personalizável

- Seleção manual dos botões exibidos na navegação principal.
- Atalhos F1 a F5 continuam ativos mesmo quando os botões estão ocultos.
- F4 abre Produtos independentemente da configuração visual.
- Aplicação imediata da visibilidade ao salvar as configurações.
- Compatibilidade preservada com modos, espaços de trabalho e menu adaptativo.
- Schema permanece na versão 13.

# 2.4.18 — Rascunho fiscal de devolução

- Geração de número interno sequencial para devoluções.
- Exportação atômica do rascunho em XML.
- Hash SHA-256 e rastreabilidade do arquivo gerado.
- Status `PRONTO` após validação fiscal.
- Bloqueio de finalização com chave, destinatário ou itens inconsistentes.
- Migração aditiva do schema 9 para 10.

# Changelog

## 2.4.17 — Assistente de NF-e de devolução

- Criados `NFeDevolucaoService` e `NFeDevolucaoRepository`.
- Nota original localizada por número ou chave de acesso.
- XML original pode ser importado para registrar os dados da nota.
- Devolução integral usa todo o saldo ainda disponível.
- Devolução parcial permite selecionar itens e quantidades.
- Quantidades superiores ao saldo disponível são bloqueadas.
- Rascunhos cancelados liberam novamente o saldo dos itens.
- Dados do emitente, destinatário, série, modelo, data e total são preservados.
- Dados fiscais dos itens são armazenados para conferência.
- Nota que já possui devoluções não pode ser sobrescrita.
- Schema atualizado para 9.
- 52 testes automatizados aprovados.

## 2.4.16 — XML inteligente e histórico de importações

- Criado `NFeImportService` e `NFeImportRepository`.
- NF-e já importada passa a ser bloqueada pela chave de acesso.
- Produtos são localizados por EAN, código ou nome exato.
- Fornecedor e unidade podem ser criados durante a importação.
- Produtos existentes recebem vínculo com fornecedor, custo e dados fiscais.
- Criadas as tabelas `nfe_importacoes` e `produto_fornecedores`.
- Adicionados os campos `codigo_barras`, `ncm`, `cest` e `cfop` em Produtos.
- Schema atualizado para 8.
- 44 testes automatizados aprovados.

# NabiCode v2.4.13 — Dashboard personalizável

- Seleção dos painéis exibidos na tela inicial.
- Resumo de cobranças vencidas.
- Resumo de produtos ativos.
- Histórico opcional de movimentações.
- Compatibilidade com preferências antigas.

# NabiCode v2.4.12 — Interface adaptativa

- Modos de uso Simples, Intermediário e Avançado.
- Espaços de trabalho Geral, Caixa, Estoque, Financeiro, Atendimento e Gerência.
- Menu superior adaptado ao modo e espaço selecionados.
- Densidade configurável das tabelas.
- Temas oficiais registrados para evolução visual.
- Preferências persistidas com validação e recuperação segura.
- Sem alteração no schema do banco de dados.

# Changelog

## 2.4.9 — Assistente XML aprimorado

- Seleção real dos itens da NF-e antes do cadastro.
- Cálculo do preço de venda por margem configurável.
- Leitura de NCM, CFOP, CEST e código de barras.
- Relatório JSON atômico de cada importação.
- Proteção contra recadastro de códigos existentes.
- Schema do banco mantido na versão 4.

## 2.4.5

- Criado `DatabaseManager` com conexão centralizada e sessões transacionais.
- Criados `ProdutoRepository` e `CategoriaRepository`.
- Criado `ProdutoService` para validações e regras de negócio.
- Tela de Produtos integrada à nova camada sem mudança visual intencional.
- Cadastro, edição, listagem, filtros e alteração de status passaram a usar o serviço.
- Mantidas as regras: Serviço não controla estoque e não participa do XML.
- Adicionados testes de CRUD, validação e rollback transacional.
- Schema do banco mantido na versão 4, pois não houve alteração estrutural.

## 2.4.4

- Ponto de entrada modular.
- ConfigManager com JSON e gravação atômica.
- EventBus interno com isolamento de falhas.

## 2.4.6 — Diagnóstico técnico modular

- Extraído o diagnóstico técnico para `services/system_diagnostics.py`.
- Adicionadas verificações de integridade, quick check, chaves estrangeiras, tabelas, schema, índices, disco, permissões e backups.
- Relatórios JSON passam a ser gravados atomicamente.
- A interface antiga permanece compatível por funções adaptadoras.
- Adicionados testes automatizados específicos do diagnóstico.

## 2.4.7 — Tarefas em segundo plano

- Adicionado `TaskManager` com pool controlado de workers.
- Adicionados estados de tarefa, progresso e cancelamento cooperativo.
- Eventos de início, progresso, conclusão, falha e cancelamento.
- Snapshot e diagnóstico executados sem bloquear a interface.
- Nenhuma alteração no schema do banco.

## 2.4.10 — Cobranças e lembretes
- Central de promissórias atrasadas com valor aberto e dias de atraso.
- Cobrança por WhatsApp com mensagem pronta para conferência.
- Registro de resultado, observação e próximo contato.
- Lembretes configuráveis antes do vencimento.
- Histórico de contatos de cobrança.
- Migração aditiva para schema 5.

## 2.4.11
- Filtros operacionais de cobrança.
- Retornos agendados e vencidos.
- Bloqueio de lembrete duplicado no mesmo dia.
- Camada `CobrancaService` separada da interface.

## 2.4.14 — Marcas, fornecedores e unidades
- Criadas as tabelas `marcas_produtos`, `fornecedores` e `unidades_medida`.
- Adicionados vínculos opcionais de marca, fornecedor principal e unidade ao produto.
- Unidade padrão `UN` criada automaticamente para bancos novos e existentes.
- Pesquisa de produtos ampliada para marca e fornecedor.
- Tela de cadastros auxiliares integrada ao módulo Produtos.
- Migração aditiva do schema 5 para 6, preservando dados existentes.


## 2.4.15 — Preços e conversão de unidades
- Adicionados custo, despesas percentuais e margem ao cadastro de produtos.
- Criado motor de precificação determinístico com `Decimal`.
- Adicionadas unidade de compra e unidade de estoque/venda.
- Adicionado fator de conversão da embalagem de compra para o estoque.
- Criado histórico de preços por produto.
- Importação XML passa a registrar custo e margem usados no cadastro.
- Migração aditiva do schema 6 para 7.

## 2.4.19 — Estoque integrado às vendas

- Adicionados saldo atual, estoque mínimo e permissão de estoque negativo por produto.
- Criado histórico imutável de movimentações de estoque.
- Implementadas entradas, saídas, ajustes e estornos idempotentes.
- A venda baixa estoque na mesma transação do financeiro; falhas revertem toda a operação.
- Itens repetidos no carrinho são agregados antes da baixa.
- Serviços e itens digitados manualmente não movimentam estoque.
- A grade de produtos passa a exibir o saldo atual.
- Migração do schema 10 para 11.

## 2.4.20 — Pedidos e recebimentos de compra

- Pedidos de compra por fornecedor.
- Itens consolidados por produto.
- Recebimento parcial e total.
- Entrada automática no estoque na mesma transação.
- Conversão da unidade de compra para a unidade de estoque.
- Atualização do último custo e do vínculo produto-fornecedor.
- Bloqueio de recebimentos acima do saldo pendente.
- Auditoria dos recebimentos.
- Schema 12.

## 2.4.21 — Financeiro essencial integrado

- Criadas as tabelas `titulos_financeiros` e `pagamentos_titulos`.
- Implementados títulos a pagar/receber, pagamentos parciais e totais e cancelamento seguro.
- Recebimentos de compra podem gerar conta a pagar na mesma transação.
- Falhas financeiras revertem estoque e recebimento.
- Schema atualizado para 13.

## 2.4.23 — Conferência XML e rolagem percentual

- Cadastro de produto reorganizado em layout horizontal de três colunas.
- Todos os campos principais receberam rótulos visíveis.
- Rodapé fixo com Cancelar, Calcular preço e Salvar produto.
- Atalhos Ctrl+S e Esc no cadastro de produto.
- Componente bidirecional de rolagem limitado entre 0% e 100%.
- Roda do mouse avança 5% na vertical; Shift+roda avança 5% na horizontal.
- PageUp/PageDown avançam 20%; Home/End movem para 0%/100%.
- Dashboard migrado para o componente de rolagem sem dependência de scrollbar interna do CustomTkinter.
- Conferência XML com edição por item de quantidade recebida, fator, unidade de estoque, custo e preço de venda.
- Entrada no estoque calculada por quantidade recebida × fator de conversão.
- Entrada de XML idempotente por chave/item/produto para impedir duplicidade.
- Tabela da conferência XML com rolagem vertical e horizontal.

## 2.4.25 — Conferência inteligente de XML e padrão de fábrica

- Conferência obrigatória de todos os itens da NF-e antes da gravação.
- Bloqueio da importação quando quantidade, fator, unidade, custo ou preço estiverem inválidos.
- Preço e margem sincronizados nos dois sentidos durante a conferência.
- Lucro unitário, markup, entrada no estoque e progresso exibidos em tempo real.
- Aplicação de margem em lote.
- Produtos novos e existentes tratados automaticamente; nenhuma NF-e é gravada sem processar todos os itens.
- Snapshot automático e restauração integral em falha durante a importação.
- Nomes de produtos normalizados em caixa alta.
- Restauração de personalização, configurações gerais ou padrão de fábrica completo.
- Scripts separados para EXE DEBUG, TESTE e FINAL, com versão centralizada em VERSAO.txt.

## 2.4.27 — Atalhos globais padronizados
- Gerenciador central de atalhos.
- Ctrl+S/N/E/F/P, F1, F11, Ctrl+M, Esc e Delete.
- Delete preservado dentro de campos de texto.
- Pesquisa contextual em Produtos, Clientes e Vendas.
- Fechamento seguro da janela principal.

## 2.4.29 — Enter inteligente

- Navegação reutilizável por Enter e Shift+Enter.
- Enter avança entre campos disponíveis e ignora campos desabilitados.
- Enter no último campo executa a ação principal do formulário.
- Validação impede avanço e mantém foco no primeiro campo inválido.
- Cadastro de produtos finaliza com Enter no último campo.
- PDV adiciona o item ao concluir quantidade e preço.
- Conferência XML confirma o item, avança para o próximo e, no último, inicia a validação final.

## 2.4.31 — Menu de contexto e área de transferência

- Menu de contexto universal com botão direito e Shift+F10.
- Copiar, colar, recortar, excluir, selecionar tudo, desfazer e refazer.
- Suporte a Entry, Text e Treeview, incluindo widgets internos do CustomTkinter.
- Ctrl+C/Ctrl+V/Ctrl+X/Ctrl+A/Ctrl+Z/Ctrl+Y padronizados.
- Cópia de múltiplas linhas de tabelas em formato tabulado, compatível com Excel.
- Evento `<<NabiPaste>>` publicado após colagem para telas que executam pesquisa automática.
- Normalização opcional de moeda e percentuais em campos marcados como numéricos.
- Correção preventiva contra colagem duplicada causada pela ordem de bindings do Tk.

## 2.4.32 — Pesquisa global Ctrl+K

- Paleta de comandos acessível por `Ctrl+K`.
- Pesquisa integrada de produtos, clientes, fornecedores, NF-e e títulos financeiros.
- Busca tolerante a maiúsculas, minúsculas e acentos.
- Abertura direta de telas, cadastros e registros encontrados.
- Navegação por teclado com Enter, setas e Esc.
- Oito testes unitários do motor de pesquisa adicionados.

## Etapa 10 — Scroll global
- Corrigido o cálculo percentual para representar o percurso rolável real entre 0% e 100%.
- Adicionados PageUp, PageDown, Home e End à área rolável e ao conteúdo interno.
- Adicionada rolagem horizontal por Shift + roda também em ambientes Linux.
- Normalizado o delta de roda e touchpad.
- Adicionado scroll horizontal independente ao painel de atividades.

## Etapa 11 — Layout universal (parcial aplicada)
- Política responsiva centralizada.
- Formulários de Produto e Cliente com dimensões seguras.
- Cadastro de Cliente convertido para cabeçalho, corpo rolável com rótulos e rodapé fixo.
- Atalhos Ctrl+S e Esc adicionados ao cadastro de Cliente.

## Etapa 12 — Notificações não bloqueantes
- Adicionado centro de notificações com duração configurável e histórico limitado.
- Sucessos de produto, venda, importação XML e backup passaram a usar toast não bloqueante.
- Erros críticos e validações continuam usando diálogos modais.
- Adicionado acesso ao histórico pelo cabeçalho das telas.

## Etapa 13 — XML inteligente (incremento)
- Adicionada colagem tabular de valores copiados do Excel na conferência da NF-e.
- Colunas aceitas: quantidade, fator, unidade, custo, margem e preço.
- Cabeçalho opcional, separação por tabulação ou ponto e vírgula e validação integral antes da aplicação.
- A colagem começa no item selecionado e não altera o banco até a confirmação final da importação.

## Etapa 14 — Estoque inteligente (núcleo transacional)
- Inventário em lote com validação integral antes de qualquer alteração.
- Snapshot JSON atômico dos saldos antes das correções.
- Ajustes de inventário registrados no histórico com usuário, motivo e origem.
- Diagnóstico de produtos sem histórico e de saldos divergentes do último movimento.
- Reversão idempotente de ajustes não vinculados.
- Bloqueio de reversão manual para vendas, compras e NF-e, exigindo cancelamento pelo documento de origem.
- Nenhuma alteração de schema ou migração de banco.

## Etapa 15 — Produtos
- Pesquisa de produtos sem distinção de acentos ou caixa, incluindo código, nome, EAN, marca e fornecedor.
- Detecção de possíveis duplicidades por EAN e similaridade de nome antes de novo cadastro.
- Duplicação inteligente com código único, EAN limpo e estoque inicial zerado.
- Histórico de preço e custo acessível pela tela de produtos.
- Alterações apenas de custo também passam a gerar histórico.

## Etapa 16 — Banco de dados
- Centralizada a manutenção SQLite em um serviço independente da interface.
- Backups manuais passam a usar a API de backup do SQLite e só são aceitos após verificação de integridade, chaves estrangeiras, schema e tabelas obrigatórias.
- Restauração valida o arquivo de origem, cria backup de segurança do banco atual e executa rollback automático se a validação final falhar.
- Reindexação, compactação e diagnóstico retornam relatório estruturado.
- Exportação atômica de relatório de integridade em JSON.
- Adicionado executor de migrações versionadas com uma transação por versão e rollback em caso de falha.
- Nenhuma alteração de schema foi realizada nesta etapa.

## Etapa 17 — Padrão de fábrica
- Criado serviço transacional para planejar e executar restaurações.
- Adicionadas seis opções: aparência, personalizações, configurações, dados de teste, dados operacionais e restauração completa.
- Prévia exibe tabelas e quantidade de registros afetados antes da confirmação.
- Todo modo cria backup validado obrigatório.
- Modos destrutivos exigem senha administrativa e a confirmação literal `APAGAR TUDO`.
- Falhas de integridade após a operação acionam restauração do backup.

## Etapa 18 — Ferramentas do desenvolvedor

- Adicionados `EXECUTAR_TESTES.bat`, `ATUALIZAR_DEPENDENCIAS.bat`, `BACKUP_BANCO.bat` e `GERAR_INSTALLADOR.bat`.
- Adicionado instalador Inno Setup versionado por `VERSAO.txt`.
- Adicionado serviço técnico para testes, limpeza de build, versões, diagnóstico compactado e verificação de versão.
- Painel administrativo ampliado com acesso a logs, backups, banco, diagnóstico, testes, limpeza e versões.
- Build final continua condicionado à aprovação da suíte de testes.

## Etapa 19 — Segurança
- Adicionado serviço de autenticação com PBKDF2-SHA256 e compatibilidade com a senha administrativa legada.
- Usuários, perfis e permissões persistidos em `configuracoes`, sem migração de schema.
- Login obrigatório na inicialização, bloqueio por inatividade e auditoria de acessos.
- Permissões aplicadas à navegação, pesquisa global e painel técnico.
- Confirmação de gerente disponível para operações críticas.

## Etapa 20 — PDV profissional (avanço real)
- Adicionado serviço independente para totalização e validação de pagamentos mistos.
- Adicionada persistência de vendas suspensas na configuração existente, sem migração.
- Adicionados comandos F6 para suspender e F7 para reabrir vendas no PDV.
- Reabertura restaura cliente e itens e remove a venda da fila de suspensas.

## Etapa 20 — PDV profissional (conclusão)
- Modos Balcão, Touch e Rápido persistidos.
- Orçamentos e pré-vendas podem ser salvos e convertidos em carrinho.
- Pagamento misto com validação de saldo e cálculo de troco integrado ao fechamento.
- Vendas pagas não geram saldo devedor; crediário mantém financeiro em aberto.
- Cancelamento de venda reverte estoque, parcelas e saldo do cliente.
- Cliente rápido integrado ao PDV por Shift+F3, com seleção automática após o cadastro.
- F4 altera a quantidade do item selecionado e recalcula o subtotal.
- F10 aplica ou remove desconto percentual sem acumular reduções sobre o preço já descontado.
- Enter atua conforme o contexto: adiciona produto ou finaliza quando o carrinho está em foco.
- F11 alterna tela cheia; Del remove item; Esc fecha com confirmação e preserva o carrinho em memória.
- Auditoria final da Etapa 20 coberta por testes de serviço e testes estruturais dos atalhos.

## Etapa 21 — Financeiro
- Fluxo de caixa por período com entradas, saídas e saldo realizado.
- DRE por competência e por valores realizados.
- Baixa parcial e total centralizada pelo serviço financeiro.
- Cálculo de juros e multa por atraso.
- Contas recorrentes idempotentes por competência.
- Centro de custos e conciliação persistidos em `configuracoes`, sem migração de schema.

## Etapa 21 — Integração da interface financeira
- Adicionada tela Financeiro com títulos, filtros, fluxo de caixa e DRE.
- Baixas parciais/totais exibem cálculo de juros e multa antes da confirmação.
- Recorrências, centro de custos e conciliação ficaram acessíveis pela interface.
- Navegação e ações financeiras respeitam as permissões do usuário.

## Etapa 21 — Financeiro (correções finais)
- DRE realizada corrigida para considerar a data efetiva dos pagamentos.
- Juros e multa passam a integrar o valor do título antes da baixa total.
- Estorno de pagamento reabre o título e remove conciliação vinculada.
- Recorrências podem ser listadas, ativadas, desativadas, excluídas e geradas por competência.
- Conciliações podem ser listadas e desfeitas.
- Relatório consolidado por centro de custo adicionado.
- Nenhuma migração de banco foi realizada.

## Etapa 21 — correções finais de auditoria
- Estorno de baixa com juros e multa também reverte o acréscimo no valor original do título.
- Recorrências podem ser editadas preservando o estado ativo/inativo.
- Interface financeira ganhou cancelamento de título, consulta/desfazer conciliações, relatório por centro de custo e detalhamento de fluxo/DRE.
- Nenhuma migração de banco foi realizada.

## Etapa 17 — Padrão de fábrica (auditoria e correções)
- Restaurações de aparência, personalizações e configurações agora restauram o backup se o callback falhar.
- Limpeza de dados de teste calcula prévia apenas para registros explicitamente TESTE e remove vínculos diretos antes das entidades.
- Restauração completa preserva metadados de migração do schema.
- Validação final ocorre também após a reaplicação das configurações padrão.

## Etapa 18 — auditoria final das ferramentas do desenvolvedor

- versão exibida pelo aplicativo passou a ser carregada de `VERSAO.txt`;
- `VERSAO.txt` passou a ser incluído no pacote PyInstaller;
- builds validam a estrutura obrigatória antes de executar testes ou empacotar;
- serviço técnico ganhou relatório de validação de scripts, testes, spec e instalador;
- painel interno ganhou ação **Validar ferramentas**;
- diretório do projeto deixou de depender do diretório de trabalho atual;
- diagnóstico técnico passou a incluir o estado das ferramentas de build.

## Etapa 23 — Fiscal oficial (continuação)
- Geração de rascunho XML NF-e/NFC-e e chave de acesso com dígito verificador.
- Contingência registrada no XML com tipo de emissão, data e justificativa.
- Consulta de situação, cancelamento, CC-e e inutilização com XML próprio e assinatura A1.
- Orquestração de autorização, consulta e eventos com armazenamento dos arquivos enviados e retornados.
- XML processado combina NF-e autorizada e protocolo para preservação fiscal.
- DANFE em PDF permitido somente para documento com protocolo autorizado.
- Central fiscal na interface para listar documentos/eventos, abrir arquivos e gerar DANFE.
- Recursos fiscais permanecem opcionais; uso comum não exige CNPJ nem certificado.

## Etapa 24 — Fechamento e recuperação de devoluções
- Recuperação idempotente de devoluções autorizadas com baixa de estoque pendente.
- Recuperação idempotente de cancelamentos fiscais com reversão de estoque pendente.
- Processamento em lote de pendências sem interromper as demais devoluções em caso de erro.
- Histórico de tentativas de recuperação local com usuário, data, resultado e mensagem.
- Bloqueio de reemissão para documentos já autorizados, inclusive com efeito local pendente.
- Cancelamento oficial permitido para NF-e autorizada cuja baixa local ainda esteja pendente.
- DANFE permitido para documento fiscal autorizado mesmo quando o efeito local aguarda recuperação.
- Central de devoluções recebeu ações de recuperação individual e em lote.

## Refatoração do inicializador de banco
- Extraído `inicializar_banco` para `database/schema_initializer.py`.
- Mantido wrapper compatível em `nabicode_legacy.py`.
- Adicionados testes de instalação inicial, idempotência e atualização com backup.

## Correção de inicialização e dependências
- Adicionado `requirements.txt` com todas as dependências utilizadas pelo projeto.
- O módulo fiscal deixou de derrubar o programa quando `requests` não está instalado e o fiscal não é usado.
- A transmissão fiscal apresenta uma mensagem controlada quando `requests` está ausente.
- O PyInstaller passou a coletar explicitamente `requests`, `cryptography`, `lxml`, `reportlab`, `openpyxl` e `matplotlib`.
- Scripts de build instalam e validam as dependências antes de gerar o executável.

- Corrigido crash na abertura causado por `tk.Canvas` receber a cor inválida `transparent`; a cor concreta agora é herdada da hierarquia CustomTkinter.

### Correção de empacotamento fiscal
- O PyInstaller agora coleta explicitamente submódulos e bibliotecas dinâmicas de `cryptography`, `lxml`, `requests` e demais dependências.
- Imports fiscais pesados tornaram-se opcionais na inicialização; a ausência de uma dependência não derruba o uso não fiscal do sistema.
- Operações fiscais exibem erro controlado orientando a reinstalação das dependências.

## Correção de compatibilidade de banco e rolagem

- Migração automática de tabelas antigas de produtos sem a coluna `nome`.
- Preservação do texto legado armazenado em `descricao`.
- Criação de índices somente após garantir as colunas necessárias.
- Roda do mouse permanece ativa sobre os widgets filhos das telas roláveis.
- Scroll horizontal por Shift + roda preservado.
- Testes de regressão adicionados para banco legado e rolagem.

## 2.4.33 — Etapa 2: finalização moderna da venda

- Substituída a entrada textual de pagamento por janela modal com Dinheiro, PIX, Débito, Crédito, Crediário e Outros.
- Desconto e acréscimo por valor ou percentual, com cálculo instantâneo.
- Total final, troco e valor restante atualizados em tempo real.
- Fluxo completo por teclado com F9, Tab, Enter e Esc.
- Estrutura de retorno da janela preparada para evolução posterior para pagamento misto.
- Total final rateado entre os itens antes da persistência, preservando consistência entre venda, financeiro, estoque e impressão.
- Corrigido o crash do CustomTkinter causado por uso direto de `bind_all` em frame rolável.
- Eliminada a dependência inexistente de `PagamentoService`; a finalização usa `PDVService` e `PDVTransactionService` existentes.
- Adicionados testes de desconto, acréscimo, troco, falta de pagamento, rateio e novas formas de pagamento.

## 2.4.45 — Sprint 1.4 Produtos

- Avaliação de duplicidade de produtos movida da UI legada para `ProductApplicationService`.
- Adicionado `ProductDuplicateAssessment` com resumo padronizado.
- Adicionados testes de duplicidade para criação e edição.
- Corrigida a versão interna para 2.4.45.
