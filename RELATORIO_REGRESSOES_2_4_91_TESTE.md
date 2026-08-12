# Regressões — NabiCode 2.4.91 teste integrado

## Coberturas automatizadas aprovadas

- reconciliação financeira;
- pagamento parcial;
- múltiplas compras/parcelas;
- divergências históricas;
- rollback financeiro;
- saldo reconciliado em cadastros;
- recibo e pipeline documental;
- navegação por Enter/KP_Enter;
- controlador do PDV;
- callbacks financeiros extraídos;
- startup smoke e versionamento.

Resultado final: `775 passed, 12 subtests passed`.

## Smoke test Windows ainda obrigatório

- abertura sem senha inesperada;
- Dashboard;
- Pesquisa e lista de sugestões;
- fluxo Enter completo do PDV;
- Venda e Finalização;
- produto sem estoque com autorização;
- pagamento cliente: saldo 220 -> pagar 20 -> saldo 200;
- atualização imediata do saldo em Clientes/Histórico;
- Impressão 80 mm;
- PDF somente quando solicitado;
- botão "Não" abrindo PDF quando o diálogo assim indicar;
- Reimpressão;
- Financeiro;
- Cadastros;
- verificação visual de glitches/redraw/scroll/foco.
