# Sprint 1.36 — Estabilização conservadora do PDV

Base: 2.4.76
Versão: 2.4.77

## Objetivo
Restaurar o comportamento comprovado da pesquisa de produtos sem desfazer correções financeiras e de impressão recentes.

## Alterações
- Popup Tk nativo ancorado ao campo de produto.
- Consulta direta por `PRODUTO_SERVICE.listar(termo, "TODOS")`.
- Filtro robusto de produtos ativos.
- Mapa de seleção por índice.
- Suporte a produto avulso e código de barras preservado.
- Lista limitada a dez itens visíveis e até cem resultados.
- Removida dependência do layout inline do CustomTkinter.

## Restrições
Nenhum redesign, nova funcionalidade ou alteração de schema.
