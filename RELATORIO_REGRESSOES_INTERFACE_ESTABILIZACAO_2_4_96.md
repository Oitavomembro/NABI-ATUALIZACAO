# Interface — Estabilização e regressões — NabiCode v2.4.96

## Base obrigatória

`NabiCode_v2_4_96_TESTE_INTEGRADO_HOTFIX_CLIENTES`

Os hotfixes posteriores relacionados a logo, marca d'água, BackgroundManager de logo, CanvasBackgroundHost e layers de imagem foram ignorados conforme a diretriz da sprint.

## Escopo auditado

- responsividade existente;
- gerenciamento de geometria `pack`/`grid`;
- maximizar/restaurar por políticas de geometria já existentes;
- resoluções 1024x768, 1280x720, 1366x768, 1600x900 e 1920x1080;
- navegação por teclado protegida por testes existentes;
- Enter/KP_Enter do PDV;
- setas;
- Ctrl+Shift+P / Pânico;
- regressões visuais relacionadas a Clientes e ao hotfix de geometry manager.

## Decisão de implementação

Nenhum arquivo de produção foi alterado nesta sprint.

A base já contém o hotfix de Clientes que evita a mistura de `pack` e `grid` no mesmo parent. Reabrir layouts já validados no Windows sem uma falha reproduzível violaria a regra de estabilidade desta sprint.

`nabicode_legacy.py` não foi alterado e nenhum patch de legado foi necessário.

`ui/background_manager.py`, `ui/theme.py`, fontes, botões e configurações de logo permaneceram congelados.

## Nova regressão automática

Criado `tests/test_interface_layout_safety_2496.py`.

O teste percorre os arquivos Python de produção, analisa cada função isoladamente e relaciona widgets criados ao respectivo parent. A regressão falha se um mesmo parent possuir filhos gerenciados simultaneamente por `pack` e `grid` no mesmo escopo funcional.

Também foram adicionadas validações para as resoluções obrigatórias:

- 1024x768;
- 1280x720;
- 1366x768;
- 1600x900;
- 1920x1080.

As geometrias retornadas por `LayoutManager.window_geometry()` devem permanecer positivas, contidas na resolução da tela e respeitar a área útil calculada.

## Auditoria de código morto, imports e duplicações

- nenhum arquivo funcional foi modificado;
- não foi introduzido código morto;
- imports do novo teste foram revisados e estão todos em uso;
- o detector inicial de geometry manager foi corrigido antes da entrega para não agregar funções distintas e gerar falsos positivos;
- não foi introduzida nova abstração visual nem duplicação de `ThemeManager`/`BackgroundManager`.

## Testes focados

Comando:

`python -m pytest -q tests/test_interface_layout_safety_2496.py tests/test_layout_manager.py tests/test_panic_and_clients_layout_2493.py tests/test_v2494_keyboard_layout_cutter.py tests/test_pdv_keyboard_navigation_2490.py`

Resultado:

`26 passed`

## Compilação

Comando:

`python -m compileall -q .`

Resultado:

APROVADO.

## Suíte completa

Comando:

`python -m pytest -q`

Resultado:

`833 passed, 11 subtests passed`

Nenhuma regressão automatizada foi detectada em Financeiro, Documental, Cadastros ou regras do PDV.

## Execução do programa

Comando executado:

`python main.py`

A validação gráfica ficou BLOQUEADA pelo ambiente Linux:

- `_tkinter.TclError: couldn't connect to display ":0"`;
- `ModuleNotFoundError: No module named 'customtkinter'`.

A sprint não pode ser considerada validada graficamente neste ambiente. A abertura, maximizar/restaurar, corte de botões, scrollbars e redraw final devem ser confirmados no Windows antes de promoção definitiva.

## Arquivos realmente modificados

- `tests/test_interface_layout_safety_2496.py`
- `RELATORIO_REGRESSOES_INTERFACE_ESTABILIZACAO_2_4_96.md`

Nenhum projeto inteiro, EXE, cache, log temporário ou `nabicode_legacy.py` completo faz parte da entrega.
