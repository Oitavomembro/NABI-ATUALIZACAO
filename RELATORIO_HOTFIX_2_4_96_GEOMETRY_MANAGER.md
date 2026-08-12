# Hotfix 2.4.96 — conflito pack/grid em Clientes

## Erro reproduzido no Windows

`_tkinter.TclError: cannot use geometry manager grid inside ... which already has slaves managed by pack`

## Causa

`tela_clientes()` criava o cabeçalho através de `criar_cabecalho_e_botoes(frame)`, que usa `pack()` para os filhos diretos de `frame`. A integração visual 2.4.96 passou a inserir `conteudo_cli` no mesmo `frame` usando `grid()`. Tk proíbe misturar `pack` e `grid` entre filhos do mesmo container.

## Correção

`conteudo_cli` agora usa `pack(fill="both", expand=True, padx=20, pady=5)` no mesmo nível do cabeçalho. O conteúdo interno de `conteudo_cli` continua usando `grid`, preservando a responsividade do `LayoutManager`.

Não houve alteração em Financeiro, Documental, PDV, banco ou regras de negócio.

## Testes

- testes focados de layout/BackgroundManager/Pânico: 17 passed
- suíte completa: 826 passed, 11 subtests passed
- `python -m compileall -q .`: aprovado
- `python main.py`: tentativa realizada; ambiente de integração Linux bloqueou GUI por ausência de display e `customtkinter`

## Regressão adicionada

O teste de Clientes agora exige `conteudo_cli.pack(...)` e rejeita `conteudo_cli.grid(...)` nesse nível, impedindo a reintrodução do conflito.
