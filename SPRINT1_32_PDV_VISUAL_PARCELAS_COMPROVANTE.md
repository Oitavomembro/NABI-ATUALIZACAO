# Sprint 1.32 — PDV visual e parcelas no comprovante

## Correções

- A animação Matrix deixou de apagar e recriar todos os caracteres a cada quadro. Os objetos gráficos são criados uma vez e reutilizados.
- A janela de Vendas permanece oculta enquanto os widgets são montados, eliminando o quadro branco durante a abertura.
- A lista suspensa de produtos agora possui colunas reais para código, descrição, preço e estoque.
- O comprovante PDF da venda consulta a movimentação e as parcelas persistidas, exibindo quantidade, valor, vencimento e status.
- Bancos legados sem as colunas novas continuam gerando comprovantes normalmente.

## Versão

2.4.73
