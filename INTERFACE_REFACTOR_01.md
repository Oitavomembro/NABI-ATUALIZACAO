# Interface Refactor 01

## Escopo aplicado

- Tema visual centralizado em `ui/theme.py`.
- Tokens de cores, tipografia, espaçamento, raios e dimensões mínimas.
- Geometria principal adaptativa, preservando 1220x780 como tamanho preferencial.
- Estilo `ttk.Treeview` centralizado e tipografia padronizada em Segoe UI.
- Carregamento tardio do CustomTkinter para permitir testes sem ambiente gráfico.

## Arquivos modificados

- `nabicode_legacy.py`
- `ui/__init__.py`
- `ui/theme.py`
- `tests/test_ui_theme.py`

## Limites preservados

- Nenhuma consulta SQL alterada.
- Nenhum schema ou arquivo de banco alterado.
- Nenhum Service, Repository ou regra de negócio alterado.
- Nenhum callback funcional movido ou reescrito.

## Testes

- Compilação de `core`, `services`, `repositories`, `database`, `ui` e `nabicode_legacy.py`.
- Testes de tema, preferências, layout universal e integração de layout.
