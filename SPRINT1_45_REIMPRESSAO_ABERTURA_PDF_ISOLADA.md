# Sprint 1.45 — Reimpressão com abertura de PDF isolada

- Removido `os.startfile` do fluxo de abertura de PDFs.
- Criado `WindowsFileOpener` para executar `Start-Process` em processo externo.
- Corrigido encerramento fatal do Python 3.14 ao escolher Não na reimpressão.
- Mantido o diálogo nativo: Sim imprime, Não abre PDF, Cancelar não executa ação.
- Adicionados testes de regressão do caminho real.
