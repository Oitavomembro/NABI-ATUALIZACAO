# Financeiro — Modularização e regressões — NabiCode v2.4.95

Base auditada: `NabiCode_v2_4_95_TESTE_REIMPRESSAO_LAYOUT`.

## Escopo

Alterações restritas ao Financeiro. Nenhum arquivo de Interface, Documental, PDV ou `nabicode_legacy.py` foi alterado.

## Alterações realizadas

- `FinanceiroCalculator` passou a concentrar a classificação de movimentos legados usada por Fluxo de Caixa e DRE.
- Tipos de entrada, tipos de saída, status realizados e origens internas do Financeiro foram centralizados em constantes imutáveis.
- Cálculo de totais de Fluxo de Caixa foi extraído do `FinanceiroService` para `FinanceiroCalculator.fluxo_caixa()`.
- Cálculo de competência/realizado da DRE foi extraído do `FinanceiroService` para `FinanceiroCalculator.dre()`.
- `FinanceiroService.saldo_titulo()` passou a reutilizar `FinanceiroCalculator.saldo()`.
- Persistência de snapshots e conciliações JSON deixou de serializar/deserializar manualmente no Service e passou a usar `FinanceiroRepository.obter_configuracao_json()` / `salvar_configuracao_json()` já existentes.
- Removido o import `json` do `FinanceiroService` após a centralização da persistência JSON.

## Auditoria estrutural

### SQL

- Nenhum SQL direto foi encontrado em `services/financeiro_service.py`, `services/financeiro_calculator.py` ou `services/financeiro_formatter.py` após a alteração.
- SQL financeiro permanece encapsulado em `repositories/financeiro_repository.py`.
- Consultas parametrizadas existentes foram preservadas.

### Transações

- Nenhum `commit()` manual foi encontrado nas camadas financeiras alteradas.
- Nenhum `rollback()` manual foi encontrado nas camadas financeiras alteradas.
- As operações de escrita continuam usando `DatabaseManager.session(write=True)` no Service.
- Métodos do Repository que participam de uma transação reutilizam a conexão recebida, evitando transação de escrita aninhada.

### Decimal

- Nenhum uso de `float()` foi encontrado nos arquivos financeiros auditados.
- Conversões e arredondamentos de valores continuam centralizados em `FinanceiroCalculator` / `DecimalStorage`.
- Os novos cálculos de Fluxo e DRE retornam `Decimal` quantizado em centavos.

### Formatter

- `FinanceiroFormatter` já existia e permanece como ponto único de formatação monetária.
- Nenhuma nova formatação monetária foi adicionada ao Service.

### Repository

- `FinanceiroRepository` já existia na base e permanece como ponto único de SQL/persistência financeira.
- Não foi criada classe paralela ou repositório duplicado.

### Código morto / imports mortos

- Auditoria AST dos arquivos alterados: nenhum import morto encontrado.
- `json` foi removido de `financeiro_service.py` após deixar de ser necessário.
- Nenhum arquivo visual foi modificado.

## Testes adicionados

`tests/test_financeiro_modularizacao_2495.py`

Cobertura:

- classificação centralizada de entradas/saídas;
- exclusão de movimentos internos do Financeiro para evitar duplicação;
- Fluxo de Caixa com valores `Decimal` exatos;
- DRE com competência e realizado em `Decimal`;
- mesma regra de classificação compartilhada entre Fluxo e DRE.

## Regressões

Testes financeiros ampliados:

`72 passed`

Suíte completa:

`795 passed, 12 subtests passed`

Nenhuma regressão automatizada detectada.

## Execução de `python main.py`

Executada antes da entrega.

A aplicação não pôde abrir neste ambiente por bloqueios técnicos externos ao Financeiro:

- `_tkinter.TclError: couldn't connect to display ":0"`
- `ModuleNotFoundError: No module named 'customtkinter'`

A validação gráfica/runtime não é declarada concluída neste ambiente.

## Arquivos realmente modificados

- `services/financeiro_calculator.py`
- `services/financeiro_service.py`
- `tests/test_financeiro_modularizacao_2495.py`
- `FINANCEIRO_RELATORIO_REGRESSOES_2_4_95.md`
