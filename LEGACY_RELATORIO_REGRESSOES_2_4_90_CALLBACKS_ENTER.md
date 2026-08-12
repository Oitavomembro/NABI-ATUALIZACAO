# NabiCode v2.4.90 — Redução do Legacy: callbacks e Enter

## Escopo

Base: `NabiCode_v2_4_90_BASE_OFICIAL_INTEGRADA`.

Alterações no `nabicode_legacy.py` são entregues exclusivamente por patch.

## Redução

- Antes: 10.024 linhas.
- Depois: 9.779 linhas.
- Redução líquida: 245 linhas.

## Extrações

### PDVEnterController

Centraliza o tratamento de Enter e KP_Enter do PDV independente para:

1. produto/código de barras;
2. quantidade;
3. preço;
4. adicionar item;
5. carrinho/finalização.

Removidos do fluxo do PDV independente:

- binding global concorrente `win.bind("<Return>", self._enter_contexto_pdv, add="+")`;
- `SearchEntryBehavior.attach(... on_enter=confirmar_sugestao_produto)` no campo principal do PDV independente;
- `install_enter_navigation` concorrente nos campos de quantidade/preço.

`_enter_contexto_pdv(event=None)` foi preservado como adaptador compatível e delega ao controller.

### FinanceiroCallbackController

Movida exclusivamente a orquestração dos callbacks de UI do Financeiro. Nenhuma regra financeira, SQL, cálculo, reconciliação ou transação foi reimplementada.

Assinaturas preservadas no legado:

- `carregar_financeiro`
- `_titulo_financeiro_selecionado`
- `novo_titulo_financeiro`
- `baixar_titulo_financeiro`
- `definir_centro_custo_financeiro`
- `abrir_recorrencias_financeiro`
- `conciliar_pagamento_financeiro`
- `cancelar_titulo_financeiro`
- `abrir_conciliacoes_financeiro`
- `abrir_relatorio_centros_custo`
- `abrir_detalhes_financeiros`
- `estornar_pagamento_financeiro`

Todos agora são adaptadores finos para `FinanceiroCallbackController`.

## Código morto / duplicações

Removida uma definição antiga duplicada de `_selecionar_produto_por_codigo_barras`. A definição posterior, que já era a efetivamente utilizada pelo Python, foi preservada.

Auditoria AST final:

- duplicações top-level em `nabicode_legacy.py`: nenhuma;
- duplicações top-level nos novos controllers: nenhuma;
- duplicações de métodos em `FicharioMoveisApp`: nenhuma.

## Regressões encontradas durante a sprint

Dois testes estruturais antigos falharam inicialmente porque exigiam a arquitetura que esta sprint foi encarregada de eliminar:

1. `test_pdv_independente` exigia literalmente `<Return>` dentro de `abrir_pdv_independente`;
2. `test_search_entry_global_integration` exigia dois `SearchEntryBehavior.attach` para o campo de produto.

Os testes foram atualizados para validar o novo proprietário único do Enter, sem restaurar bindings concorrentes.

Após o ajuste, nenhuma regressão automatizada permaneceu.

## Testes

- Novos/focados: 13 passed.
- Suíte completa: 753 passed, 12 subtests passed, 0 failures.
- `python -m compileall -q .`: aprovado.

## python main.py

Executado.

A aplicação não abriu por bloqueios do ambiente:

- `_tkinter.TclError: couldn't connect to display ":0"` no splash;
- `ModuleNotFoundError: No module named 'customtkinter'` ao carregar o legado.

A validação gráfica não é declarada concluída.
