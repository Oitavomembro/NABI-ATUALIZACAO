# Relatório de regressões — Navegação por teclado — NabiCode v2.4.90

## Status

**SPRINT NÃO CONCLUÍDA.**

A infraestrutura de Enter foi corrigida e testada, porém a finalização integral do fluxo exclusivamente por Enter não pode ser certificada sem alterar `nabicode_legacy.py`, que está explicitamente proibido nesta sprint.

## Base oficial

`NabiCode_v2_4_90_BASE_OFICIAL_INTEGRADA`

## Arquivos alterados

- `ui/keyboard_navigation.py`
- `core/enter_navigation.py`
- `services/search_entry_behavior.py`
- `tests/test_pdv_keyboard_navigation_2490.py`
- `RELATORIO_REGRESSOES_NAVEGACAO_TECLADO_2_4_90.md`

## Alterações realizadas

### 1. Bindings Enter/KP_Enter unificados

Foi criada a infraestrutura `ui.keyboard_navigation` com:

- `bind_key_once()`;
- `bind_enter_pair()`.

Ela garante que `<Return>` e `<KP_Enter>` usem o mesmo callback e impede reinstalação duplicada do mesmo binding por responsabilidade/widget.

### 2. IntelligentEnterNavigator

`core/enter_navigation.py` passou a usar a infraestrutura única para:

- Enter;
- KP_Enter;
- Shift+Enter;
- Shift+KP_Enter.

O comportamento existente de validação, avanço de foco, retorno e `on_finish` foi preservado.

### 3. SearchEntryBehavior

`services/search_entry_behavior.py` passou a usar a mesma infraestrutura de bindings para:

- `<FocusIn>`;
- `<Return>`;
- `<KP_Enter>`.

Chamadas repetidas a `SearchEntryBehavior.attach()` não instalam novamente o mesmo binding de responsabilidade.

## Testes novos

`tests/test_pdv_keyboard_navigation_2490.py` cobre:

1. paridade Enter/KP_Enter;
2. deduplicação de bindings;
3. idempotência do SearchEntryBehavior;
4. Quantidade -> Preço -> Adicionar -> retorno ao Produto com Enter;
5. o mesmo fluxo com KP_Enter.

## Validações executadas

### Testes focados

`19 passed`

### Suíte completa

`745 passed, 12 subtests passed`

### Compilação

`python -m compileall` sobre todos os arquivos alterados: **APROVADO**.

### Auditoria de imports

Auditoria por AST: nenhum import morto encontrado nos arquivos alterados.

`ruff` não está instalado no ambiente, portanto não foi possível executar esse verificador externo.

### python main.py

Executado.

A abertura foi bloqueada pelo ambiente:

- `_tkinter.TclError: couldn't connect to display ":0"`;
- `ModuleNotFoundError: No module named 'customtkinter'`.

Portanto, a validação gráfica não foi concluída.

## Ponto residual obrigatório

Na base v2.4.90, a etapa de finalização por Enter sobre `tabela_carrinho` continua dentro da função `_enter_contexto_pdv` em `nabicode_legacy.py`. A janela do PDV registra `<Return>` nessa função, mas não existe binding equivalente de `<KP_Enter>` nesse ponto.

Como `nabicode_legacy.py` está proibido nesta sprint, não foi alterado e nenhum patch foi gerado.

Consequência: foi possível corrigir e certificar a infraestrutura compartilhada e o ciclo Produto/Quantidade/Preço/Adicionar/retorno ao Produto, mas não é tecnicamente correto declarar que o fluxo completo até Finalizar foi corrigido sob as restrições atuais.

## Escopo preservado

Não foram alterados:

- Financeiro;
- Documental;
- Cadastros;
- regras do PDV;
- banco de dados;
- `nabicode_legacy.py`.
