# Testes executados

- `python -m py_compile nabicode_legacy.py managers/system_infrastructure_manager.py managers/__init__.py helpers/value_parsing.py helpers/__init__.py tests/test_system_infrastructure_manager.py tests/test_value_parsing_helpers.py` — aprovado.
- `python -m pytest -q tests/test_system_infrastructure_manager.py tests/test_value_parsing_helpers.py` — 5 passed.
- `python -m pytest -q` — 721 passed, 12 subtests passed.
- Auditoria AST de assinaturas e duplicações — nenhuma assinatura alterada; nenhuma definição duplicada.
- `python main.py` — executado; bloqueado por ausência de `customtkinter` e display gráfico `:0`.
