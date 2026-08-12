# NabiCode 2.5.1 DEV — Relatório técnico do Checkpoint 35

Data: 8 de agosto de 2026  
Estado: candidata de instalação offline; **não promovida para RELEASE**  
Base obrigatória: `NabiCode_v2_5_1_DEV_CHECKPOINT_34_INSTALLER_PIPELINE.zip`  
SHA-256 da base: `100d072bd0e80a755cb7e0dad4189cece23a767618066ddd5cf53ece2edf5b57`

## Resultado

O fluxo de startup foi corrigido no código-fonte e o splash Lightspeed definitivo foi integrado. A validação automatizada local terminou com:

- `python -m compileall -q .`: aprovado;
- suíte completa: **931 passed, 11 subtests passed** (execução final: 17,25 s);
- testes focados de startup/splash: **31 passed**;
- testes focados de build/PyInstaller/smoke: **17 passed, 3 subtests passed**;
- smoke do framebuffer Lightspeed: `RGBA 960x540`, 920 estrelas de fundo e 720 estrelas do nome, aprovado;
- testes físicos Windows: **pendentes**.

Os 920 testes existentes no Checkpoint 34 foram preservados. Foram adicionados 11 testes: os 10 cenários obrigatórios do Checkpoint 35 e uma verificação adicional do canal de pausa/liveness do processo pai.

## Causa raiz

O assistente de primeira instalação é executado durante o import de `nabicode_legacy.py`, antes da criação da janela principal. A splash anterior rodava em processo separado com `-topmost` permanente e não possuía canal para saber que o processo principal estava aguardando um modal. O diálogo tinha um parent Tk local, porém o processo da splash continuava acima dele. O resultado era um processo vivo aguardando uma janela escondida.

O conflito de segunda instância era corretamente detectado por `DatabaseUsageLock`, mas exposto como `RuntimeError` genérico. No executável PyInstaller, essa exceção chegava ao bootloader e produzia `Failed to execute script 'main' due to unhandled exception`.

## Arquitetura adotada

### Separação de processos

- a aplicação Tk principal permanece no processo principal e no thread principal;
- a splash Tk/Pillow permanece em processo auxiliar;
- nenhum objeto Tk atravessa processos ou threads;
- não há `sleep`, busy loop ou segundo loop de UI no mesmo processo;
- pygame/SDL não foi acrescentado às dependências ou ao wheelhouse.

### Coordenação modal/splash

`core/startup_window_coordinator.py` mantém um arquivo-sinal temporário cujo caminho é transmitido pela variável `NABICODE_SPLASH_PAUSE_FILE`.

Fluxo:

1. splash visível e `topmost` durante carregamento normal;
2. um modal obrigatório entra em `startup_modal_scope()`;
3. o arquivo de pausa é criado;
4. o processo da splash chama `withdraw()` e deixa de disputar `topmost`;
5. o modal recebe parent, `transient`, `grab_set`, `lift` e foco explícitos;
6. ao fechar o modal, o sinal é removido;
7. a splash só retorna se o startup ainda precisar dela;
8. cancelamento, retorno antecipado e exceção limpam o sinal pelo `finally` do context manager.

O mecanismo suporta modais aninhados por contador de profundidade.

### Segunda instância

`DatabaseInUseError` é uma subclasse de `RuntimeError`, preservando compatibilidade com o contrato anterior. O lock e sua semântica não mudaram. O entrypoint captura somente esse conflito esperado, registra o diagnóstico em `%APPDATA%\NabiCode\<perfil>\logs\startup.log`, encerra a splash e exibe uma mensagem amigável. O fluxo retorna código 0, sem traceback e sem `Failed to execute script`.

### Erros no startup

Falhas inesperadas são registradas com traceback técnico no log de startup. Antes da mensagem ao usuário, o entrypoint pede a ocultação e o encerramento da splash. O bloco `finally` libera o lock, aguarda/termina o auxiliar se necessário e remove os arquivos-sinal.

### Motor visual Lightspeed

Referência canônica preservada byte a byte em `build_tools/references/splash_nabicode_deep_trust_fluid.py`.

SHA-256 da referência: `7057bd3b41ba0cca3fc05486e07f2556debdb3942cb2304b46ce18a3814ac53f`.

A adaptação mantém:

- espaço profundo `RGB 0,1,5`;
- estrelas predominantemente brancas e apenas 18 raras coloridas;
- aceleração a partir de 2 s, redução perto de 4,55 s e formação a partir de 4,70 s;
- riscos curtos e limitados;
- estrelas do nome originadas do espaço profundo;
- desaceleração durante a formação;
- nome formado exclusivamente por estrelas brancas/marfim;
- marfim neon `#FFFCEB`, com glow quente discreto;
- ausência de HUD, barra, nebulosas e segundo nome.

O tempo visual é desacoplado do carregamento real. Se o aplicativo ficar pronto cedo, a formação e o fade são concluídos em aproximadamente 620 ms. Se o startup durar mais, a timeline é mantida em estado estável até o sinal real de conclusão. Durante um modal, o relógio visual é pausado. O PID do processo pai é monitorado para impedir splash órfã.

## Compatibilidade do build offline

- nenhuma nova dependência externa;
- `requirements.txt`, lock Windows e wheelhouse não foram alterados;
- o `.spec` recebeu apenas os hidden imports explícitos `PIL.ImageDraw` e `PIL.ImageFont`;
- perfil da raiz permanece `TESTE`;
- perfil do artefato permanece `PRODUCAO`;
- versão permanece `2.5.1`;
- pipeline onedir/Inno, manifesto e `SHA256SUMS.txt` não foram modificados.

## Escopo funcional

Não houve alteração em PDV, vendas, financeiro, regras comerciais, banco, schema, impressão, corte, reimpressão, navegação de módulos ou cálculo financeiro. As alterações em `nabicode_legacy.py` estão limitadas à propriedade/visibilidade dos modais executados durante o startup.

## Pendências obrigatórias

Este ambiente não é Windows e não possui display físico nem impressora. Portanto, permanecem pendentes:

- hierarquia real das janelas no executável instalado;
- Alt+Tab e foco no Windows 10/11;
- validação do segundo processo PyInstaller sem traceback;
- fluidez e consumo de CPU/GPU do splash em hardware real;
- instalação em `C:\Program Files\NabiCode`;
- impressão, driver e corte físicos;
- geração e validação do novo instalador offline.

Consulte `VALIDACAO_MANUAL_WINDOWS_CHECKPOINT_35.md` antes de qualquer promoção.
