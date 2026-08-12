# Sprint de Interface — ThemeManager Único

## Status

**BLOQUEADA — NÃO CONCLUÍDA**

A implementação e os testes automatizados foram aprovados, porém a abertura real do programa não pôde ser confirmada no ambiente de validação.

## Escopo respeitado

Alterações restritas a:

- infraestrutura visual em `ui/**`;
- temas, fontes e espaçamentos;
- configuração de botões, entradas, menus, tabelas e scrollbars;
- responsividade;
- testes específicos da interface.

Não foram alterados:

- PDF;
- impressão;
- financeiro;
- pesquisa de produtos;
- PDV;
- banco de dados;
- regras de negócio;
- `main.py`;
- `nabicode_legacy.py`.

## Arquivos realmente modificados

1. `ui/theme.py`
2. `ui/__init__.py`
3. `tests/test_ui_theme.py`
4. `INTERFACE_THEME_MANAGER_AUDITORIA.md`

`PATCH_INTERFACE_LEGADO.md` não foi criado porque `nabicode_legacy.py` não foi alterado.

## Implementação

- Criado `ThemeManager` único.
- Consolidado acesso a tokens imutáveis em `NabiTheme`.
- Centralizados papéis tipográficos: pequeno, corpo, subtítulo e título.
- Centralizadas variantes de botão: primary, secondary, success, danger, info e ghost.
- Centralizada configuração visual de entradas, menus e scrollbars CTk.
- Padronizados `Treeview`, cabeçalhos e scrollbars ttk.
- Mantidos os adaptadores públicos `configure_ctk`, `configure_ttk` e `apply_responsive_geometry` para compatibilidade com o código existente.
- Nenhuma callback ou regra funcional foi movida ou alterada.

## Auditoria do código alterado

- Compilação Python aprovada.
- Análise AST dos imports realizada.
- Nenhum import morto encontrado em `ui/theme.py` ou `tests/test_ui_theme.py`.
- Os imports de `ui/__init__.py` são reexportações públicas declaradas em `__all__`, não código morto.
- Nenhum bloco inalcançável identificado.
- Funções independentes duplicadas foram consolidadas no `ThemeManager`.
- Adaptadores legados permanecem apenas para compatibilidade e delegam ao gerenciador único.
- `ruff` não estava instalado no ambiente; por isso, a análise foi feita por AST, compilação e testes.

## Testes específicos da interface

Comando:

```text
python -m pytest tests/test_ui_theme.py -q
```

Resultado:

```text
10 passed
```

## Testes de regressão protegidos

Foram executados testes de:

- tema e layout;
- preferências de interface;
- inicialização;
- layout do PDV;
- pesquisa;
- impressão.

Resultado:

```text
47 passed, 3 subtests passed
```

## Suíte completa

Comando:

```text
python -m pytest -q
```

Resultado:

```text
671 passed, 12 subtests passed
```

Nenhuma regressão automatizada foi detectada.

## Execução de `python main.py`

O comando foi efetivamente executado.

A aplicação não abriu devido a dois bloqueios do ambiente:

```text
_tkinter.TclError: couldn't connect to display ":0"
ModuleNotFoundError: No module named 'customtkinter'
```

Portanto:

- a abertura real do sistema não foi confirmada;
- a sprint não pode ser declarada concluída;
- o bloqueio não foi mascarado como sucesso;
- nenhuma dependência foi adicionada ao projeto;
- nenhum EXE foi gerado.
