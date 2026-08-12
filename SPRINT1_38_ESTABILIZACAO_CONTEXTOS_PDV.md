# Sprint 1.38 — Estabilização definitiva dos contextos do PDV

## Causa raiz
A aplicação cria dois conjuntos de campos de venda: a janela independente do PDV e a aba Vendas. Ambos reutilizavam os mesmos atributos (`entry_item_venda`, `entry_qtd_venda`, `entry_valor_venda`). O último conjunto criado sobrescrevia o anterior. A pesquisa então consultava ou atualizava um campo invisível, produzindo o sintoma de lista vazia mesmo com produtos cadastrados.

## Correção
- Restaurado o registro explícito de cada contexto de venda.
- Cada ação de pesquisa sincroniza o contexto pelo foco ou pela visibilidade.
- Removido definitivamente o seletor embutido duplicado.
- Mantido um único popup Tk nativo, ancorado ao campo ativo.
- Preservados DecimalStorage, produto avulso, código de barras e decisão explícita entre cupom e PDF.

## Travas de regressão
- Os dois contextos devem ser registrados.
- Mostrar, filtrar e navegar devem sincronizar o contexto.
- `_criar_lista_produtos_inline` e `_produto_sugestao_por_iid` não podem reaparecer.
- O popup não pode exigir `winfo_ismapped()` antes de ser criado.
