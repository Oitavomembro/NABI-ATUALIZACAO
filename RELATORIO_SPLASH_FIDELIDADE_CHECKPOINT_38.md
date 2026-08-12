# NabiCode 2.5.1 DEV — Fidelidade do splash — Checkpoint 38

Data: 8 de agosto de 2026  
Estado: candidata DEV; **não promovida para RELEASE**

## Base

- `NabiCode_v2_5_1_DEV_CHECKPOINT_37_STARTUP_SPLASH_LICENSE_FIX.zip`
- SHA-256: `0dbd062b69e26403b58e119594fd3f545590b98bcfb84f1dfe27b94dcb3df88a`
- Protótipo canônico: `build_tools/references/splash_nabicode_deep_trust_fluid.py`
- SHA-256 do protótipo: `7057bd3b41ba0cca3fc05486e07f2556debdb3942cb2304b46ce18a3814ac53f`

## Causa da reprovação visual do Checkpoint 37

O port mantinha parte das constantes, mas divergia na composição final:

- a janela era limitada a 68% da tela, reduzindo tamanho, densidade aparente e deslocamento em pixels;
- a máscara do NABICODE era escalada junto com a janela em vez de permanecer no espaço lógico 1280×720;
- no Windows era selecionada Segoe UI Semibold, enquanto o protótipo solicita Segoe UI em negrito;
- o relógio de sweep/twinkle recebia `perf_counter()` absoluto, e não o tempo da animação;
- glows eram desenhados como discos RGB opacos, causando sujeira, cor e contorno inadequados;
- o fator aleatório de profundidade continuava escurecendo estrelas já encaixadas;
- o nome da loja era desenhado abaixo de NABICODE, elemento inexistente no protótipo.

## Correção

- framebuffer lógico fixo em 1280×720;
- exibição 16:9 em escala 1:1 sempre que a tela comportar, com redução proporcional apenas em telas menores;
- DPI awareness ativado no helper antes da criação do Tk;
- fonte 96 px, Segoe UI Bold (`segoeuib.ttf`) e amostragem da máscara em passo 3;
- 2.050 estrelas de fundo, 1.500 do nome e 8 raras;
- timeline e fórmulas extraídas diretamente do protótipo;
- `speed = 40 + 540*(warp**2.60)` preservada;
- baixa probabilidade de rastros e fator de comprimento preservados;
- origem das estrelas do nome em raio 2–42 próximo ao ponto de fuga;
- arco, delay, travel, reveal e rastro curto preservados;
- nome formado exclusivamente em paleta branco/marfim, convergindo para `#FFFCEB`;
- glow com composição alpha, sem discos escuros opacos;
- todo texto adicional removido: o único texto visual é `NABICODE`;
- scheduler `after()` e proteção contra callback interrompido preservados;
- readiness gate, pausa de modal, liveness do pai e encerramento do helper preservados.

## FPS e escala

Medição local isolada do renderer Pillow em 1280×720, percorrendo os 732 frames da timeline:

- média: 12,53 ms por quadro;
- percentil 95: 21,93 ms;
- pior quadro: 29,13 ms;
- capacidade teórica média do desenho: 79,8 FPS.

Essa medição não inclui `PhotoImage`, compositor do Windows ou hardware do cliente. O helper agora grava telemetria real ao encerrar (`measured_fps`, render médio, pior render, frames e display); o processo principal a registra no log de startup antes de apagar o arquivo temporário. A aprovação física continua pendente.

## Testes

- focados: **66 passed, 3 subtests passed** em 0,77 s;
- `python -m compileall -q .`: aprovado;
- suíte integral: **959 passed, 18 subtests passed** em 19,22 s;
- testes removidos: 0;
- testes novos: 10.

## Escopo preservado

Não houve alteração em licenciamento, `DatabaseLock`, unlock, perfil, contrato do smoke, build, instalador, banco, PDV, financeiro, impressão, caixa ou regras de negócio.

## Status

O código e a regressão automatizada estão aprovados. A fidelidade visual final depende exclusivamente do teste físico Windows descrito em `VALIDACAO_MANUAL_WINDOWS_CHECKPOINT_38.md`.

