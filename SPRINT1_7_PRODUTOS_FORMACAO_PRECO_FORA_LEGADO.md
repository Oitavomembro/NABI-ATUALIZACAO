# Sprint 1.7 — Produtos: formação de preço fora do legado

## Objetivo
Remover dos callbacks Tkinter a regra de formação automática do preço de venda e da margem de lucro.

## Alterações
- Adicionado `ProductPricingState` ao serviço de aplicação de Produtos.
- Adicionado `ProductApplicationService.calcular_preco_formulario`.
- Adicionado `ProductApplicationService.calcular_margem_formulario`.
- Unificado o cálculo sobre custo total com `PricingService` e `Decimal`.
- Removida do callback Tkinter a fórmula manual de margem com `float`.
- Mantidos os callbacks apenas como leitura/escrita dos widgets e tratamento visual.
- Adicionados testes para preço, margem inversa, arredondamento, margem mínima e entrada inválida.

## Compatibilidade
A regra comercial permanece: despesas são incorporadas ao custo e a margem é aplicada sobre o custo total. Margens negativas informadas indiretamente por preço abaixo do custo continuam limitadas a zero na tela.
