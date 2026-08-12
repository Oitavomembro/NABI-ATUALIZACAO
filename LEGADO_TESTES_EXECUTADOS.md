# Testes executados

## Compilação

```text
python -m py_compile nabicode_legacy.py services/mysql_migration_service.py
Resultado: aprovado
```

## Testes focados

```text
python -m pytest -q tests/test_migration_phase2_fk.py tests/test_mysql_migration_service.py
Resultado: 9 passed in 0.35s
```

## Suíte completa

```text
python -m pytest -q
Resultado: 1 failed, 690 passed, 12 subtests passed in 14.27s
```

Falha única: teste de versão espera `2.4.85`, enquanto a base integrada declara `2.4.86`.

## Inicialização

```text
python main.py
```

Resultado: bloqueado por ausência de `customtkinter` e indisponibilidade de display gráfico `:0`.
