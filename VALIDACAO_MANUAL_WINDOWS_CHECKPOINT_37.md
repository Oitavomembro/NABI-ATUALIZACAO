# Validação manual Windows — Checkpoint 37

Status inicial de todos os itens: **PENDENTE DE VALIDAÇÃO FÍSICA**.

## Preparação e build

1. Trabalhar em caminho curto, preferencialmente `C:\NB\NabiCode`.
2. Confirmar `PERFIL_NABICODE.txt = TESTE` na raiz.
3. Confirmar `build_tools\resources\PERFIL_NABICODE.txt = PRODUCAO`.
4. Executar exatamente:

```powershell
cd C:\NB\NabiCode
powershell -ExecutionPolicy Bypass -File build_tools\build_offline_windows.ps1
```

5. Não executar o `.iss` isoladamente e não contornar o pipeline.
6. Instalar o novo `build_output\installer\NabiCode_2.5.1_Setup_Offline.exe`.

## Checklist físico

- [ ] 1. Instalação limpa com internet desconectada e sem Python/pip.
- [ ] 2. Splash evolui continuamente sem minimizar/maximizar.
- [ ] 3. Taxa visual estável e CPU controlada; registrar hardware e uso observado.
- [ ] 4. NABICODE aparece na timeline correta em marfim neon, sem amarelo.
- [ ] 5. Nome da loja configurado aparece corretamente.
- [ ] 6. Sem HUD, barra, nebulosa, excesso de riscos ou segundo nome.
- [ ] 7. Splash conclui com fade; janela principal já está pronta e entra suavemente.
- [ ] 8. Nenhum flash branco ou layout parcialmente montado.
- [ ] 9. Pergunta e formulário de abertura de caixa surgem prontos e suavemente.
- [ ] 10. Modal de servidor/rede aparece acima da splash.
- [ ] 11. Cancelar modal inicial produz saída/continuação determinística, sem processo invisível.
- [ ] 12. Alt+Tab para Chrome/Explorer e retorno preservam splash/modal visível corretamente.
- [ ] 13. Minimizar/restaurar não congela nem reinicia a animação.
- [ ] 14. Ativar licença de teste de 1 minuto.
- [ ] 15. Antes do limite, operação continua disponível.
- [ ] 16. No limite, bloqueio aparece e operação fica protegida.
- [ ] 17. Senha errada mantém bloqueio e não persiste liberação.
- [ ] 18. Senha correta encerra modal e a UI reaparece na mesma instância.
- [ ] 19. Após unlock, `%TEMP%\nabicode_splash_*.pause` não existe.
- [ ] 20. Após unlock/startup, nenhum `--splash-helper` permanece.
- [ ] 21. Processo principal tem `MainWindowHandle` não zero e título visível.
- [ ] 22. Abrir segunda instância durante bloqueio/unlock mostra mensagem amigável, sem traceback.
- [ ] 23. Fechar bloqueado encerra processo, helper e libera lock.
- [ ] 24. Fechar normalmente não deixa processo NabiCode órfão.
- [ ] 25. Nova abertura não apresenta falso lock.
- [ ] 26. Reiniciar após unlock preserva a liberação válida.
- [ ] 27. Impressão física continua aprovada no novo instalador.
- [ ] 28. Corte físico continua aprovado.

## Evidência de processos sugerida

Durante os itens 18–25, registrar:

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -like 'NabiCode*' } |
  Select-Object ProcessId, ParentProcessId, CommandLine

Get-Process NabiCode_v2_5_1 -ErrorAction SilentlyContinue |
  Select-Object Id, Responding, MainWindowHandle, MainWindowTitle

Get-ChildItem $env:TEMP -Filter 'nabicode_splash_*' -ErrorAction SilentlyContinue
```

Critério: após startup/unlock concluído deve restar apenas o processo principal, com janela utilizável; após fechamento não deve restar processo nem `.pause`.

## Registro obrigatório

Anotar versão do Windows, hardware, resolução/DPI, duração percebida, PID pai/filho, resultado de cada item, hash do instalador testado e qualquer log em `%APPDATA%\NabiCode\PRODUCAO\logs`. Não declarar aprovação se qualquer item crítico permanecer pendente.

