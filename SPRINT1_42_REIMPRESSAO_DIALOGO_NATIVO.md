# Sprint 1.42 — Reimpressão com diálogo nativo

- Remove o Toplevel customizado da segunda via e demais PDFs.
- Usa `messagebox.askyesnocancel` para evitar janela branca no Windows.
- Sim imprime, Não abre o PDF e Cancelar fecha sem emitir.
- Seleciona apenas uma janela-pai viva e visível.
- Mantém o modal visual do pós-venda, que já foi validado em uso real.
