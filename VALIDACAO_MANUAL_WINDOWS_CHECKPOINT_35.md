# Validação manual Windows — Checkpoint 35

Estado inicial: **PENDENTE DE VALIDAÇÃO FÍSICA**.

Use uma cópia extraída em caminho curto, recomendado `C:\NB\NabiCode`. Não execute o build sobre a RELEASE 2.5.0.

## Preparar e gerar o instalador

1. Extraia `NabiCode_v2_5_1_DEV_CHECKPOINT_35_STARTUP_SPLASH.zip` em `C:\NB\NabiCode`.
2. Confirme `VERSAO.txt = 2.5.1`.
3. Confirme `PERFIL_NABICODE.txt = TESTE` na raiz.
4. Confirme `build_tools\resources\PERFIL_NABICODE.txt = PRODUCAO`.
5. Preserve `build_output\wheelhouse`; não o apague.
6. Em PowerShell, a partir de `C:\NB\NabiCode`, execute exatamente:

```powershell
powershell -ExecutionPolicy Bypass -File build_tools\build_offline_windows.ps1
```

7. Não execute o `.iss` isoladamente e não contorne o pipeline.
8. Confirme que Analysis, PYZ, PKG, EXE, COLLECT, validação onedir e Inno terminam aprovados.
9. Confirme a presença canônica das evidências:
   - `build_output\manifest.json`
   - `build_output\SHA256SUMS.txt`
10. Registre o SHA-256 do instalador; não promova para RELEASE.

## A — Primeira instalação

- [ ] Instalar o novo Setup offline.
- [ ] Clicar em **Executar NabiCode**.
- [ ] A splash Lightspeed aparece.
- [ ] O diálogo de servidor/cliente/local aparece visível acima da splash.
- [ ] A splash não disputa foco e não cobre o diálogo.
- [ ] Confirmar a configuração.
- [ ] A splash retorna somente se o carregamento continuar.
- [ ] A janela principal abre sem flash branco ou janela fantasma.

## B — Cancelar

- [ ] Iniciar sem configuração concluída.
- [ ] Escolher computador cliente.
- [ ] Fechar/cancelar a janela de configuração do cliente.
- [ ] O processo encerra de forma determinística.
- [ ] Não sobra splash, janela invisível ou processo `NabiCode.exe` órfão.
- [ ] Abrir novamente e confirmar que o assistente reaparece corretamente.

## C — Alt+Tab

- [ ] Iniciar o NabiCode e alternar para Chrome/Explorer.
- [ ] Durante carregamento sem modal, confirmar o comportamento topmost definido da splash.
- [ ] Quando surgir um modal do NabiCode, confirmar que ele fica visível e recebe foco.
- [ ] Alternar para outra aplicação e voltar; o modal continua acessível.
- [ ] Não existe alternância repetitiva de foco entre splash e modal.

## D — Segunda instância

- [ ] Manter o NabiCode aberto ou aguardando um modal.
- [ ] Executar o atalho novamente.
- [ ] Confirmar mensagem **NabiCode já está aberto**.
- [ ] Confirmar menção ao banco de PRODUÇÃO.
- [ ] Não aparece traceback.
- [ ] Não aparece `Failed to execute script 'main'`.
- [ ] A primeira instância e o banco permanecem intactos.

## E — Fechamento e lock

- [ ] Fechar o NabiCode normalmente.
- [ ] Confirmar ausência de processo residual.
- [ ] Abrir novamente.
- [ ] Confirmar ausência de falso lock.
- [ ] Forçar uma falha controlada de startup apenas em ambiente de teste e verificar: splash encerra, mensagem aparece à frente e traceback fica somente no log.

## F — Executável instalado

- [ ] Repetir A–E pelo executável em `C:\Program Files\NabiCode`.
- [ ] Confirmar funcionamento sem `python`, `pip`, Git ou internet.
- [ ] Confirmar persistência dos dados em AppData após reinstalação.
- [ ] Confirmar que o wheelhouse e o código-fonte não estão no diretório instalado.

## G — Fidelidade visual

- [ ] Fundo espacial quase preto, sem nebulosas.
- [ ] Muitas estrelas predominantemente brancas.
- [ ] Poucas estrelas raras coloridas.
- [ ] Aceleração progressiva e poucos riscos curtos.
- [ ] NABICODE começa relativamente cedo e nasce de estrelas do espaço profundo.
- [ ] Não há aglomerado central evidente.
- [ ] Nome exclusivamente branco/marfim, sem amarelo e sem estrelas coloridas nas letras.
- [ ] Cor percebida próxima de `#FFFCEB`, com glow quente discreto.
- [ ] Sem HUD, barra, segundo NABICODE ou espera artificial.
- [ ] Se o startup demora, a animação permanece estável; se termina cedo, conclui suavemente.

## H — Hardware físico

- [ ] Impressão física.
- [ ] Corte físico.
- [ ] Driver real da impressora.
- [ ] Reimpressão.

Somente marque o Checkpoint 35 como aprovado no Windows depois de registrar máquina, versão do Windows, hash do instalador, resultado de cada item e eventuais logs.
