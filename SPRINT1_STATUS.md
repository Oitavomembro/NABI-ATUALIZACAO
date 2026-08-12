# Sprint 1 — Produtos

Base modular evoluída da Sprint 1.1 até a Sprint 1.32.

## Concluído

- 1.1: correção e estabilização dos testes legados.
- 1.2: estabilidade e desempenho do módulo de Produtos.
- 1.3: salvamento transacional de produto e estoque.
- 1.4: avaliação de duplicidade fora do legado.
- 1.5: criação de `ProductSaveCommand` fora da UI.
- 1.6: estado do formulário fora do legado.
- 1.7: formação de preço na camada de aplicação.
- 1.8: validações de negócio fora da UI.
- 1.9: listagem, filtros, contagem e seleção fora da UI.
- 1.10: duplicação, histórico e status fora da UI.
- 1.11: preparação de inclusão e edição fora da UI.
- 1.12: binding reutilizável do formulário sem dependência de Tkinter.
- 1.13: controlador reutilizável de formação de preço.
- 1.14: categorias, marcas, fornecedores e unidades fora da UI principal.
- 1.15: segurança do pacote e integridade dos cadastros auxiliares.
- 1.16: pipeline financeiro de Produtos migrado para `Decimal` nas fronteiras de aplicação, serviço, histórico e persistência.
- 1.17 a 1.20: persistência monetária canônica, migração única, sincronização de NF-e/Compras e leitura decimal resiliente.
- 1.21: schema de Produtos fora do construtor do repositório e pesquisas principais padronizadas.
- 1.22: paleta global, Relatórios e Central de Ajuda padronizados.
- 1.23: bindings de pesquisa centralizados, incluindo Enter normal e teclado numérico.
- 1.24 a 1.27: Financeiro, Relatórios, Cobranças, Dashboard, histórico e documentos migrados para `Decimal`.
- 1.28 e 1.29: PDV e Caixa migrados para cálculo e persistência decimal canônica.
- 1.30: cancelamento, baixa e estorno sincronizados nas representações legada e canônica.
- 1.31: inicialização do executável resiliente à ausência ou formato inválido de `VERSAO.txt`, com smoke test automático da build.

## Compatibilidade temporária

- `ProductApplicationService.criar_auxiliar(...)`: manter até a migração integral para `ProductAuxiliaryCreateCommand`.

## Próximo recorte recomendado

Auditar seletores e filtros que não são campos de pesquisa, além de reduzir conversões monetárias residuais fora de Produtos e Compras sem misturar regras de estoque.

## Sprint 1.17 — concluída na versão 2.4.58

Persistência monetária exata adicionada com colunas decimais canônicas em TEXT, migração idempotente, compatibilidade com colunas REAL e teste integrado completo de cadastro.


## Sprint 1.18 concluída
Sincronização monetária integral da NF-e, histórico e produto-fornecedor com serialização decimal centralizada.


## Sprint 1.19 — Política decimal oficial e migração única
- Migração decimal centralizada e integrada ao bootstrap.
- Compras com leitura e persistência canônica em pedidos e recebimentos.
- Fallback seguro para valores canônicos vazios ou inválidos.
- Validação de overflow na representação REAL legada.

## Sprint 1.20 — Pesquisa resiliente e leitura decimal segura — concluída

- Placeholders nativos separados do conteúdo real das pesquisas.
- Texto digitado branco e placeholder cinza nas pesquisas de Cliente e Produto do PDV.
- Foco seleciona o valor anterior para substituição imediata.
- Enter local sempre é consumido, inclusive sem sugestões.
- ProdutoRepository e CompraRepository usam fallback decimal controlado.
- Escrita principal de Produto e histórico usa DecimalStorage.pair().
- Totais de pedidos são somados em Decimal a partir dos itens canônicos.
- Testes completos: 579 aprovados.


## Sprint 1.21 — Pesquisa global e schema fora dos repositórios

- Removidas alterações de schema do construtor de `ProdutoRepository`.
- Índices e compatibilidade de código de barras centralizados no bootstrap.
- Pesquisas principais de Produtos e Clientes padronizadas com `SearchEntryBehavior`.
- Enter nas pesquisas principais é consumido e não propaga para atalhos globais.
- Formatação monetária de auditoria de Compras preserva `Decimal`.


## Sprint 1.22 — Pesquisa restante padronizada
- Paleta global, Relatórios e Central de Ajuda integrados ao `SearchEntryBehavior`.
- Enter consumido nos campos de pesquisa para impedir ações globais indevidas.
- Versão: 2.4.63.


## Sprint 1.23 — Bindings de pesquisa centralizados
- `SearchEntryBehavior.attach(...)` centraliza cores, foco e Enter.
- Enter normal e `<KP_Enter>` são sempre consumidos.
- Produtos, Clientes, PDV, paleta global, Relatórios e Central de Ajuda usam a mesma API.
- Bindings manuais duplicados removidos do código-fonte.
- Versão: 2.4.64.

## Sprint 1.24 — Financeiro Decimal e filtros com Enter
- Repositório financeiro aceita e devolve `Decimal` nas operações monetárias principais.
- Escrita em colunas REAL legadas passa por validação central de overflow.
- Serviço financeiro não converte mais valores para `float` antes das principais chamadas ao repositório.
- Filtros de período do Financeiro usam comportamento centralizado para Enter normal e numérico.
- Versão: 2.4.65.


## Sprint 1.25 — Financeiro com persistência decimal exata

- Títulos e pagamentos possuem representação canônica TEXT.
- Escrita dupla REAL/TEXT centralizada no FinanceiroRepository.
- Leitura monetária resiliente com fallback controlado.
- NF-e compatível com schema novo e schemas legados mínimos.
- 591 testes aprovados.

## Sprint 1.26 — Relatórios e Cobranças com Decimal
- Resumos e mensagens de cobrança sem conversão monetária para float.
- Indicadores financeiros e personalizados agregados com Decimal.
- Atividades financeiras formatadas via DecimalStorage.
- 594 testes aprovados.


## Sprint 1.27 concluída
- Dashboard, histórico de clientes, pesquisa global e documentos/recibos migrados para Decimal nos valores monetários.
- Base oficial: 2.4.68.

## Sprint 1.28 — PDV e Caixa com Decimal
- Totalização, desconto, acréscimo, pagamentos, falta, troco e rateio migrados para Decimal.
- Pagamentos estruturados persistidos como texto decimal canônico em JSON.
- Transação de venda e parcelamento usam Decimal até a fronteira SQLite legada.
- 597 testes aprovados.
- Base oficial: 2.4.69.

## Sprint 1.29 — concluída
- Persistência decimal canônica implementada em PDV, parcelas, saldos e Caixa.
- Compatibilidade com schemas legados preservada.
- Testes SQLite reais adicionados.


## Sprint 1.30 — concluída
- Cancelamento de venda usa valor canônico e restaura saldo canônico do cliente.
- Baixa e estorno sincronizam movimentação, parcelas e cliente.
- Conversões monetárias residuais removidas do FinanceiroService.
- Vazamento de conexão SQLite corrigido.
- Base oficial: 2.4.71.


## Sprint 1.31 — concluída
- Carregamento de versão extraído para `core.app_version`.
- Ausência de `VERSAO.txt` não interrompe mais o executável.
- `NabiCode.spec`, builds TESTE e DEBUG incluem o arquivo de versão.
- Scripts de build executam smoke test do próprio EXE gerado.
- Base oficial: 2.4.72.


## Sprint 1.32 — Estabilidade visual do PDV e parcelas no comprovante

- Splash Matrix otimizada com reutilização de itens do Canvas.
- Janela de Vendas montada oculta e revelada somente após o layout estar pronto.
- Lista de produtos do PDV convertida para tabela com Código, Produto, Preço e Estoque.
- PDF de venda passou a exibir forma de pagamento, parcelas, valores e vencimentos.
- Compatibilidade preservada com bancos antigos sem colunas de parcelamento.
- Versão: 2.4.75.


## Sprint 1.33 concluída

- Modal pós-venda branco corrigido.
- Popup de produtos compactado e com contraste explícito.
- Histórico diário com colunas maiores e rolagem horizontal.
- Splash reduzida para melhorar fluidez.
- Versão: 2.4.75.


## Sprint 1.34 — Correção regressões visuais do PDV

Concluída na versão 2.4.75.

## Sprint 1.35 — PDV lista inline e cupom por perfil

Concluída na versão 2.4.76.

- Lista de produtos incorporada à tela de Vendas.
- Seleção por código de barras restaurada.
- Cupom 80 mm volta a ser o padrão configurável.
- PDF somente no perfil `PDF virtual`.


## Sprint 1.36 — Estabilização conservadora do PDV (2.4.77)

- Removida a lista inline instável introduzida após a 2.4.72.
- Restaurado popup nativo de produtos com consulta direta ao ProdutoService.
- Preservados DecimalStorage, produto avulso, código de barras e impressão por perfil.
- Seleção passou a usar mapa por índice, sem depender do texto formatado.
- Enter e setas funcionam mesmo quando o popup ainda não está aberto.
- Nenhuma funcionalidade nova adicionada.

## Sprint 1.37 — Estabilização runtime do PDV e impressão
- Compatibilidade Tk/CustomTkinter corrigida.
- Importação DecimalStorage validada.
- Emissão pós-venda exige escolha explícita.

## Sprint 1.40 — PDV, impressão segura no Python 3.14 e lista com colunas

- Impressão de PDF isolada em processo PowerShell, sem `os.startfile(..., "print")`.
- Modal pós-venda com ações explícitas e layout estável.
- Lista de produtos com colunas reais e tipografia Segoe UI.
- Travas específicas adicionadas para o crash e regressões visuais.

## Sprint 1.41 — Modal de impressão unificado
- Corrigido NameError do WindowsPDFPrinter.
- Reimpressão e documentos usam o mesmo modal de três ações do pós-venda.
