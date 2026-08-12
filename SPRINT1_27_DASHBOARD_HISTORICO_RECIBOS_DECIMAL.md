# Sprint 1.27 — Dashboard, histórico e recibos com Decimal

## Alterações
- Dashboard passa a expor valores monetários como Decimal.
- Histórico consolidado do cliente preserva Decimal em compras e parcelas.
- Pesquisa global formata preços, saldos e títulos sem conversão monetária para float.
- Geração de documentos e recibos formata valores monetários por DecimalStorage.
- Quantidades, medidas de layout e fronteiras gráficas permanecem em float quando apropriado.

## Validação
- 23 testes focados aprovados.
- 594 testes da suíte completa aprovados.
