# Sprint 1.35 — Lista de produtos inline e emissão por perfil

## Alterações

- Lista de produtos removida de janela externa e incorporada à própria tela do PDV.
- A seta de produtos e a digitação alimentam a mesma lista estável.
- Restaurada a seleção exata por código interno ou código de barras.
- Finalização de venda deixou de gerar e abrir PDF automaticamente.
- A saída agora respeita `formato_impressao_recibo`:
  - Cupom 58 mm;
  - Cupom 80 mm;
  - A4;
  - PDF virtual.
- PDF é criado somente quando `PDF virtual` está selecionado.
