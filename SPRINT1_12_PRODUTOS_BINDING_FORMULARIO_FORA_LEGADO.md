# Sprint 1.12 — Produtos: binding do formulário fora do legado

## Objetivo
Remover do `nabicode_legacy.py` a captura campo a campo e o preenchimento manual de `ProductFormState`, estabelecendo uma fronteira reutilizável entre controles visuais e estado de aplicação sem dependência direta de Tkinter.

## Alterações
- Criado `services/product_form_binding.py`.
- Criados `ProductFormControls` e `ProductFormBinding`.
- A leitura completa do formulário foi centralizada em `ProductFormBinding.capture()`.
- A aplicação completa de `ProductFormState` foi centralizada em `ProductFormBinding.apply()`.
- O adaptador trabalha por duck typing e não importa `tkinter` nem `customtkinter`.
- Removida do legado a instanciação manual de `ProductFormState` com todos os widgets.
- Removido do legado o bloco repetitivo de preenchimento dos campos e combos.
- Preservado o bloqueio do código automático na inclusão e sua edição em cadastros existentes.

## Compatibilidade
O fluxo de cadastro, edição e duplicação mantém os mesmos controles e o mesmo `ProductApplicationService`. Nenhuma regra de negócio foi duplicada.

## Testes
- Testes específicos do binding com controles falsos, sem ambiente gráfico.
- Testes focados de Produtos.
- Suíte completa do projeto.
- Compilação sintática de todos os arquivos Python.
