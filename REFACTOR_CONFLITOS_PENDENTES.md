# Conflitos pendentes da refatoração

## Arquivos e áreas protegidas

Não modificar nesta missão:

- `main.py` nas rotinas de splash, revelação e transições.
- `splash_screen.py`.
- `ui/theme.py` e qualquer uso de `ThemeManager`.
- `ui/background_manager.py` e qualquer uso de `BackgroundManager`.
- `ui/screen_navigation.py` e qualquer implementação de `ScreenNavigation`.
- `core/enter_navigation.py`, navegação por teclado e bindings associados.
- `core/window_actions.py`, troca de telas e ações de janela.
- widgets, geometria, layout e transições visuais no legacy ou em `ui/`.

## Achados deliberadamente não corrigidos

- `core/global_search.py:331`: import local de `tkinter` marcado como não utilizado por Ruff. Mantido porque o arquivo participa da navegação/paleta global.
- `core/text_interactions.py:12`: import de `tkinter.ttk` marcado como não utilizado. Mantido por pertencer à camada de widgets/interações.
- `core/text_interactions.py:13`: `typing.Iterable` marcado como não utilizado. Mantido para evitar alteração concorrente no mesmo arquivo protegido.
- `nabicode_legacy.py`, método `editar_cliente_selecionado`: ainda contém SQL e controle manual de transação dentro de um fluxo de widgets. A extração foi adiada porque exigiria modificar uma rotina visual protegida nesta missão.

## Regra de integração

Esses itens só devem ser tratados depois da integração da branch dedicada ao flash branco e após repetição integral dos testes de navegação, troca de telas, splash, tema e background.
