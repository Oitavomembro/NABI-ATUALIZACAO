# Sprint 1.10 — Produtos: ações fora da UI

## Objetivo
Remover dos callbacks Tkinter as chamadas diretas ao `ProdutoService` nos fluxos de duplicação, histórico de preços e ativação/desativação.

## Alterações
- `ProductApplicationService.preparar_duplicacao(...)` passou a validar a seleção e orquestrar a preparação da cópia.
- `ProductApplicationService.obter_historico(...)` passou a buscar o produto, carregar o histórico e formar linhas prontas para apresentação.
- `ProductApplicationService.alternar_status(...)` passou a validar a seleção, alterar o status e retornar um resultado tipado.
- Criados `ProductHistoryRow`, `ProductHistoryResult` e `ProductStatusResult`.
- O `nabicode_legacy.py` deixou de chamar diretamente `ProdutoService.preparar_duplicacao`, `listar_historico` e `alternar_status` nesses fluxos.
- Tratamento de produto inexistente centralizado na camada de aplicação.

## Compatibilidade
As regras existentes de duplicação, auditoria e persistência continuam delegadas ao `ProdutoService`; não houve duplicação de repositórios ou regras de domínio.

## Testes
- 28 testes focados do `ProductApplicationService` aprovados.
- 535 testes da suíte completa aprovados.
- Compilação sintática completa aprovada.
