# Sprint 1.9 — Produtos: listagem, filtros e seleção fora da UI

## Alterações

- Criados `ProductListQuery`, `ProductTableRow` e `ProductListResult`.
- Normalização do termo e do filtro de tipo centralizada em `ProductApplicationService.normalizar_consulta_listagem`.
- Formação das linhas, valores padrão, tipo exibido e contagem centralizadas em `listar_tabela`.
- Conversão e validação do identificador selecionado centralizadas em `obter_produto_id_selecionado`.
- Fluxos de editar, duplicar, histórico e alteração de status deixaram de converter diretamente o `iid` do Treeview.
- `linhas_tabela` foi mantido como adaptador temporário de compatibilidade.
- Adicionados testes para filtros, resultado tipado, contagem e seleção inválida.

## Validação

- Testes focados do serviço de aplicação: 25 aprovados.
- Suíte completa: 532 testes aprovados.
- Compilação sintática completa aprovada.
- ZIP validado estruturalmente.
