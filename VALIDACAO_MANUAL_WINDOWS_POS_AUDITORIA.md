# Validação manual Windows — pós-auditoria noturna

Executar em `C:\NB\NabiCode` com internet desconectada quando aplicável.

1. Rodar `powershell -ExecutionPolicy Bypass -File build_tools\build_offline_windows.ps1`.
2. Confirmar validação SHA-256 do wheelhouse, PyInstaller onedir, smoke PRODUCAO, manifesto, SHA256SUMS e Inno Setup.
3. Instalar o setup gerado em máquina Windows 10/11 limpa, sem Python/pip.
4. Confirmar splash fluida, NABICODE marfim, nenhum texto extra e transição sem flash.
5. Confirmar modal obrigatório acima da splash e comportamento Alt+Tab.
6. Confirmar fim do helper após `MAIN_WINDOW_READY` no Gerenciador de Tarefas.
7. Fechar normalmente e por Alt+F4; verificar ausência de processo, `.pause`, `.stop` residual e falso lock.
8. Repetir erro/cancelamento de configuração inicial; verificar cleanup.
9. Testar licença antes do limite, exatamente no limite e depois do limite; senha errada/correta; confirmar retorno da mesma UI e ausência de instância headless.
10. Com uma instância aberta, iniciar outra; confirmar mensagem amigável e lock preservado.
11. Encerrar abruptamente a primeira instância, abrir novamente e confirmar recuperação do lock antigo.
12. Aplicar atualização offline de teste; confirmar espera pelo processo correto, backup, rollback em falha e reinício.
13. Executar venda, cancelamento, financeiro, backup/restore e persistência após reabrir.
14. Executar impressão, reimpressão e corte físicos.
15. Desinstalar/reinstalar e confirmar preservação dos dados do usuário.

Todos os itens acima permanecem **PENDENTES DE VALIDAÇÃO FÍSICA WINDOWS** nesta entrega.
