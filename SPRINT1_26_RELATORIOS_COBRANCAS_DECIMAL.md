# Sprint 1.26 — Relatórios e Cobranças com Decimal

## Alterações
- Resumo de cobranças passou a usar Decimal.
- Mensagens de cobrança e lembrete formatam Decimal sem conversão por float.
- Indicadores financeiros de relatórios retornam Decimal.
- Indicadores personalizados usam agregação Decimal.
- Atividades de vendas e títulos financeiros formatam valores com DecimalStorage.
- Adicionados testes de precisão decimal extensa.

## Escopo preservado
- Quantidades de estoque continuam usando float nesta sprint.
- Séries gráficas continuam convertendo na fronteira de visualização.
