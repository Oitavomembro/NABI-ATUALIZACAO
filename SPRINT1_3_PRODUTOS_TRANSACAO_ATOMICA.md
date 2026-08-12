# NabiCode v2.4.44 — Sprint 1.3

## Objetivo

Garantir que a edição de produto, o histórico de preço e o ajuste de estoque sejam persistidos como uma única operação atômica.

## Alterações

- `ProductApplicationService` agora abre uma transação compartilhada quando Produto e Estoque usam o mesmo `DatabaseManager`.
- Alteração cadastral, histórico de preço, saldo e movimentação de estoque são confirmados juntos.
- Se o ajuste de estoque falhar, nome, preço, custo e histórico também são revertidos.
- `ProdutoRepository` passou a aceitar uma conexão transacional opcional em consultas e gravações usadas pelo fluxo de salvamento.
- `ProdutoService.salvar` passou a propagar a conexão transacional para validações, persistência e histórico.
- `EstoqueService` ganhou `ajustar_na_transacao`, reutilizando a transação externa sem abrir uma segunda conexão.
- Mantida compatibilidade com os testes e integrações que usam doubles sem `DatabaseManager`.

## Testes adicionados

- sucesso grava cadastro, histórico e estoque no mesmo commit;
- falha simulada no estoque reverte cadastro, preço, histórico e movimentação.

## Validação

- 35 testes focados em Produto/Estoque: OK.
- 513 testes da suíte completa: OK.
