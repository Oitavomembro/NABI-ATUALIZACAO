# NabiCode 2.5.1 DEV — Relatório técnico do Checkpoint 37

Data: 8 de agosto de 2026  
Estado: candidata de instalação offline; **não promovida para RELEASE**

## Base e integridade

- Base obrigatória: `NabiCode_v2_5_1_DEV_CHECKPOINT_36_SMOKE_PROFILE_HOTFIX.zip`
- SHA-256 confirmado da base: `36cd989fe883a8bf542ab5b473e986883a318cf9641f18031277586a00226a3d`
- Versão: `2.5.1`
- Perfil da árvore-fonte: `TESTE`
- Perfil do artefato: `PRODUCAO`
- Contrato do smoke empacotado do Checkpoint 36: preservado e coberto por regressão.

## Resultado local

- `python -m compileall -q .`: aprovado.
- Suíte integral final: **949 passed, 18 subtests passed** em 20,16 s.
- Seleção focada final: **64 passed, 10 subtests passed** em 1,22 s.
- Testes removidos: **0**.
- Testes físicos Windows: **pendentes**.

## Causas-raiz confirmadas

### Splash aparentemente congelada

O callback de frame executado por `after()` não protegia toda a renderização. Uma exceção em um único frame encerrava silenciosamente a cadeia de reagendamento no Tk sem console do PyInstaller. A janela continuava viva, mas só era repintada quando o Windows provocava um repaint, comportamento idêntico à evidência física.

Além disso, a implementação anterior operava a 30 FPS, com contagens reduzidas, e encurtava a timeline quando recebia readiness cedo. Isso divergia do protótipo aprovado.

### Processo headless depois do desbloqueio

O bloqueio de licença criava uma segunda raiz `CTk`, executava um segundo `mainloop()` e mantinha a raiz principal retirada. O fluxo de desbloqueio podia não retornar de forma confiável ao loop principal empacotado. Enquanto o contexto modal não concluía, o arquivo `.pause` permanecia presente; o helper ficava vivo e a raiz principal não era restaurada. Isso explica os dois processos respondendo, nenhum `MainWindowHandle`, `.pause` residual e ausência de `.stop`.

### Transições bruscas

A janela principal e as janelas de abertura de caixa podiam ser reveladas antes de o layout e a geometria estarem concluídos. A revelação da raiz também competia com callbacks do construtor. Não existia um gate explícito entre primeiro frame válido, fim canônico da splash e início do fade da aplicação.

## Arquitetura implementada

### Motor visual e scheduler

`splash_screen.py` é um port Tk/Pillow direto da referência canônica `build_tools/references/splash_nabicode_deep_trust_fluid.py` (SHA-256 `7057bd3b41ba0cca3fc05486e07f2556debdb3942cb2304b46ce18a3814ac53f`). Foram preservados:

- 60 FPS, frame nominal de 16 ms;
- duração canônica de 12,2 s;
- aceleração a partir de 2,0 s;
- limpeza/desaceleração do fundo a partir de 4,55 s;
- formação do NABICODE a partir de 4,70 s, concluída por volta de 7,55 s;
- desaceleração entre 6,35 s e 8,70 s;
- início do fade final em 11,0 s e término em 12,2 s;
- 2.050 estrelas de fundo, 1.500 estrelas do nome e apenas 8 estrelas raras;
- NABICODE exclusivamente branco/marfim neon `#FFFCEB`;
- ausência de HUD, barra, nebulosa e segundo NABICODE.

O helper mantém Tk no próprio thread principal. Cada callback agenda o próximo com `after()` e compensação de deriva; não há `sleep` nem busy-loop. A referência `PhotoImage` é retida. Exceções de frame são gravadas em arquivo técnico e o callback é reagendado no `finally`; erros consecutivos não podem deixar uma splash congelada indefinidamente.

O nome da loja é transmitido em JSON temporário atômico, sem acesso do helper ao banco ou ao runtime profile.

### Readiness gate e transições

O fluxo passou a ser:

1. helper anima a sequência canônica;
2. raiz principal é construída retirada;
3. `update_idletasks()` confirma dimensões e primeiro layout válido;
4. `main_window_ready` é registrado;
5. `MAIN_WINDOW_READY` é sinalizado ao helper pelo arquivo `.stop` já existente;
6. readiness antecipado não acelera a timeline mínima;
7. se readiness atrasar, a animação permanece viva em 11,0 s;
8. o helper conclui o fade de 1,2 s e encerra;
9. somente então a raiz é revelada com fade de 340 ms e recebe foco.

Não há intervalo em que a splash desapareça sem existir uma próxima janela pronta. As janelas de abertura de caixa agora são construídas retiradas, têm layout e geometria calculados e usam fade de 300 ms antes de receber foco/grab. Nenhuma regra funcional do caixa foi alterada.

### Modais e licença

O diálogo de licença usa `CTkToplevel(self)`, `transient(self)`, `grab_set`, foco explícito e `wait_window` da mesma raiz. O contexto `startup_modal_scope()` oculta a splash e remove `.pause` em `finally`. Senha incorreta não persiste estado. Senha correta renova por 30 dias, limpa a expiração exata, remove o bloqueio e restaura a mesma instância.

Fechar o bloqueio encerra a raiz pelo fluxo normal do `mainloop`; não é lançada exceção dentro de callback Tk. Durante o startup, a intenção de saída é tratada antes da construção do restante da UI e o `finally` do entrypoint libera lock, sinaliza e reaproveita/encerra o helper.

O monitor periódico passou a avaliar todas as modalidades reais, não apenas a expiração exata de um minuto. Assim, validade diária expirada ou bloqueio manual não ficam operacionalmente liberados até um reinício.

### Ciclo de vida do helper

- final normal: sinal, espera do fade, coleta do processo e remoção de `.stop`, `.pause`, metadata e log temporário;
- exceção/cancelamento: pausa, stop, espera, `terminate`, e `kill/wait` se o helper não obedecer;
- PID pai continua monitorado pelo helper;
- o `DatabaseUsageLock` permanece inalterado e é liberado no `finally`.

## Desempenho local do renderer

Uma medição isolada do desenho Pillow em 1280×720, 2.050 estrelas de fundo e 1.500 estrelas do nome produziu média de 18,26 ms por quadro em 30 quadros (capacidade teórica aproximada de 54,8 FPS). Essa medição não inclui Tk/PhotoImage nem representa aprovação no Windows; a taxa real instalada permanece no checklist físico.

## Escopo preservado

Não houve alteração em PDV, vendas, financeiro, cálculos, schema, persistência operacional, impressão, corte, PDF, recibos, estoque, cadastros ou regras comerciais. Nenhum arquivo de build foi alterado; wheelhouse, PyInstaller onedir, Inno Setup, manifesto e hashes permanecem sob o pipeline existente.

## Pendências

O ambiente desta auditoria não é Windows e não possui display/hardware de impressão. Permanecem obrigatórios: rebuild pelo pipeline oficial, teste instalado em `Program Files`, fluidez/CPU, Alt+Tab, hierarquia de modais, desbloqueio de 1 minuto, árvore de processos, impressão e corte físicos.
