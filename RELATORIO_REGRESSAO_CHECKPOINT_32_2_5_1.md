# RELATÓRIO DE REGRESSÃO — CHECKPOINT 32 — NABICODE 2.5.1 DEV

## Resultado executivo

**CÓDIGO-FONTE APROVADO NA REGRESSÃO AUTOMATIZADA DESTE AMBIENTE.**

A distribuição Windows autocontida, o instalador offline e o smoke físico em
máquina Windows limpa não foram declarados aprovados: o ambiente disponível é
Linux e não pode produzir nem validar honestamente executáveis Windows.

## Validações finais

| Validação | Resultado |
| --- | --- |
| `python -m compileall -q .` | aprovado, exit code 0 |
| suíte padrão | **912 passed, 11 subtests passed em 17,76 s** |
| stress separado | **1 passed em 4,17 s** |
| benchmark separado | **1 passed em 0,34 s** |
| soak separado | **1 passed em 2,71 s** |

Os 902 testes e 11 subtests informados para a base permanecem cobertos. A suíte
padrão passou de 902 para 912 testes devido a 10 testes novos; nenhum teste
existente foi removido.

Na primeira tentativa de executar a suíte final, o interpretador selecionado
pelo executor não tinha o módulo `pytest`; nenhum teste chegou a iniciar. A
suíte foi então repetida com o mesmo conjunto isolado de ferramentas usado no
baseline, sem instalar pacotes no projeto e sem alterar o código.

## Stress

- 1.000 vendas;
- 2.000 movimentos de estoque;
- 100 cancelamentos;
- 100 rollbacks injetados;
- backup validado e restore validado;
- `PRAGMA integrity_check = ok`;
- duração interna: 3,992 s;
- pico de memória rastreada: 49.508 bytes.

## Benchmark

Dataset: 10.000 clientes, 10.000 produtos, 50.000 movimentos e 20.000 títulos.

| Operação | p50 | máximo |
| --- | ---: | ---: |
| produto/10.000 | 1,199 ms | 3,534 ms |
| cliente/10.000 | 2,251 ms | 2,542 ms |
| histórico/50.000 | 0,199 ms | 0,238 ms |
| dashboard/50.000 | 2,823 ms | 3,663 ms |
| financeiro/20.000 | 1,390 ms | 1,628 ms |

Todos os limites automatizados do benchmark foram atendidos.

## Soak

- 5.000 ciclos;
- 1.000 commits;
- 4.000 rollbacks;
- `PRAGMA integrity_check = ok`;
- lock final adquirido e liberado;
- duração interna: 2,694 s;
- pico de memória rastreada: 7.713 bytes;
- amostras de memória estáveis: 5.146, 5.242, 5.274, 5.306 e 5.338 bytes.

## Startup — antes/depois

Não houve otimização funcional no Checkpoint 31. O baseline parcial identificou
imports pesados, mas a medição completa até a primeira tela utilizável requer
Windows gráfico. Assim, tempo depois e ganho percentual são **não aplicáveis**;
nenhuma melhora especulativa foi mascarada como ganho.

## Distribuição e instalador

A infraestrutura reprodutível para PyInstaller `onedir` e Inno Setup foi criada
e passou nos testes estáticos. Uma tentativa controlada de build neste ambiente
falhou explicitamente, como projetado, por três pré-condições ausentes:

- sistema operacional não Windows;
- Python local 3.12 em vez do Python 3.14 travado para o build;
- dependências Windows de build não instaladas.

Consequentemente, permanecem pendentes:

- distribuição `NabiCode_v2_5_1` para Windows;
- `NabiCode_2.5.1_Setup_Offline.exe`;
- teste do aplicativo empacotado;
- smoke físico Windows 10/11 sem internet;
- impressão/corte físicos do pacote instalado;
- instalação, desinstalação, preservação e reinstalação em máquina limpa.

## Arquivos modificados em relação à base 2.5.0

14 arquivos existentes foram modificados:

- `GERAR_EXE_FINAL.bat`
- `GERAR_INSTALLADOR.bat`
- `NabiCode.iss`
- `VERSAO.txt`
- `core/runtime_profile.py`
- `main.py`
- `nabicode_legacy.py`
- `requirements.txt`
- `services/backup_service.py`
- `tests/test_backup_service.py`
- `tests/test_exe_version_packaging.py`
- `tests/test_requirements_manifest.py`
- `tests/test_runtime_profile_isolation.py`
- `tests/test_startup_smoke_test.py`

22 arquivos foram adicionados:

- `ARQUITETURA_ATUALIZACAO_OFFLINE.md`
- `BUILD_OFFLINE_2_5_1.md`
- `CHECKPOINT_21_BASE_2_5_1.md`
- `CHECKPOINT_24_ARQUITETURA_DADOS.md`
- `CHECKPOINT_27_TESTE_APLICATIVO_EMPACOTADO.md`
- `CHECKPOINT_28_INSTALADOR_OFFLINE.md`
- `CHECKPOINT_31_PERFORMANCE_STARTUP.md`
- `DEPENDENCIAS_RUNTIME_NABICODE_2_5_1.md`
- `RELATORIO_REGRESSAO_CHECKPOINT_32_2_5_1.md`
- `STARTUP_BASELINE_2_5_1.md`
- `TESTE_MAQUINA_LIMPA_OFFLINE_2_5_1.md`
- `build_tools/__init__.py`
- `build_tools/build_offline_windows.ps1`
- `build_tools/build_windows.py`
- `build_tools/inno/NabiCode_Offline.iss`
- `build_tools/prepare_wheelhouse.ps1`
- `build_tools/pyinstaller/nabicode.spec`
- `build_tools/requirements-windows.lock`
- `build_tools/resources/PERFIL_NABICODE.txt`
- `core/startup_metrics.py`
- `tests/test_offline_build_tools.py`
- `tests/test_startup_metrics.py`

Nenhum arquivo da base foi removido.

## Escopo funcional

Não foram alteradas regras comerciais, cálculos financeiros, fluxo do PDV,
impressão/corte, navegação/flash ou splash espacial. As alterações funcionais
limitam-se à separação segura de dados mutáveis em AppData e à instrumentação
opt-in de startup; o restante é infraestrutura de build, instalador,
documentação, versão e testes.

## Estado do fallback

`NabiCode_v2_5_0_RELEASE.zip` permaneceu intocado e conserva o SHA-256
`36f0bc3fdc341623e001cc88ecec711d5b6adbbcd3065397a9a6f3e558f89875`.
