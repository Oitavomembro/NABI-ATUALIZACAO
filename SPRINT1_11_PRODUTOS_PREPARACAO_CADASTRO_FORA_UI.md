# Sprint 1.11 — Produtos: preparação do cadastro fora da UI

## Objetivo

Remover do `nabicode_legacy.py` as chamadas diretas restantes de busca do produto para edição e geração do próximo código, consolidando a preparação do formulário no `ProductApplicationService`.

## Alterações

- Criado `ProductRegistrationPreparation`, resultado imutável com estado do formulário, identificador e textos de apresentação.
- Criado `ProductApplicationService.preparar_cadastro(...)`.
- Busca do produto para edição movida para a camada de aplicação.
- Validação de produto inexistente para edição centralizada no serviço.
- Geração do próximo código para novo produto movida para a camada de aplicação.
- Dados pré-carregados de duplicação preservados no fluxo de inclusão.
- Título e cabeçalho do formulário derivados do resultado de preparação.
- Removidas da abertura do cadastro as chamadas diretas a `ProdutoService.buscar(...)` e `ProdutoService.proximo_codigo()`.
- Adicionados três testes unitários específicos.

## Compatibilidade

O método público `abrir_cadastro_produto(produto_id=None, dados_precarregados=None)` foi preservado. O comportamento de inclusão, edição e duplicação permanece compatível.
