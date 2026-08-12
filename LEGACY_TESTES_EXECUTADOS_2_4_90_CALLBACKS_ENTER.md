# Testes executados

## Focados

```text
python -m pytest -q \
  tests/test_pdv_enter_controller.py \
  tests/test_financeiro_callback_controller.py \
  tests/test_legacy_callbacks_reduction_2490.py
```

Resultado: `13 passed`.

## Suíte completa

```text
pytest -q
```

Resultado final: `753 passed, 12 subtests passed`.

## Compilação

```text
python -m compileall -q .
```

Resultado: aprovado.

## Inicialização

```text
python main.py
```

Resultado: bloqueada pelo ambiente (`display :0` e ausência de `customtkinter`).
