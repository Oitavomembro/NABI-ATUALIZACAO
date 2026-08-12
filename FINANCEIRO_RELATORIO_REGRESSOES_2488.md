# Financeiro — auditoria e regressões — NabiCode 2.4.88

## Escopo alterado
- `repositories/financeiro_repository.py`
- `services/financeiro_service.py`
- `services/financeiro_calculator.py`
- `services/financeiro_view_data.py`
- testes financeiros desta sprint

`nabicode_legacy.py`, Interface, Documental e PDV não foram alterados.

## Auditoria

### SQL
- removido SQL direto de `FinanceiroService`;
- consultas de título de venda e títulos ativos por origem foram concentradas em `FinanceiroRepository`;
- leitura e persistência das estruturas legadas de crediário foram encapsuladas no Repository;
- inserts repetidos de auditoria foram substituídos por `FinanceiroRepository.registrar_auditoria`.

### Decimal e cálculos
- `FinanceiroCalculator` continua como normalizador monetário central;
- extração dos encargos gravados em observação passou para `FinanceiroCalculator.encargos_observacao`;
- não foi introduzido cálculo monetário com `float` nas camadas modificadas.

### Formatação
- `FinanceiroViewData` deixou de duplicar formatação monetária e agora reutiliza `FinanceiroFormatter` por compatibilidade;
- nenhuma assinatura usada pela interface foi removida.

### Transações / commit / rollback
- nenhuma nova transação foi criada;
- `FinanceiroService` continua usando `DatabaseManager.session(write=True)` como limite transacional;
- nenhum `commit()` ou `rollback()` manual foi adicionado.

### Persistência
- dual-write/canonical Decimal continua delegado a `DecimalStorage` no Repository;
- snapshot de sincronização legada continua persistido em `configuracoes`, sem mudança de chave ou formato.

## Código morto e imports
- removidos helpers `_table_exists` e `_columns` do Service após transferência da responsabilidade ao Repository;
- formatação duplicada removida de `FinanceiroViewData`;
- imports foram reavaliados após as extrações.

## Regressões
Os testes focados financeiros e de crediário devem permanecer verdes antes da entrega. O resultado final da execução e de `python main.py` é registrado na validação da sprint.

## Validação executada

- compilação dos arquivos modificados: aprovada;
- testes financeiros/crediário focados: **66 aprovados**;
- suíte completa: **720 testes + 12 subtestes aprovados** em 15,12 s;
- regressões automatizadas encontradas: **nenhuma**.

## `python main.py`

Executado antes da entrega. A aplicação não abriu neste ambiente por dois bloqueios técnicos externos às alterações financeiras:

```text
_tkinter.TclError: couldn't connect to display ":0"
ModuleNotFoundError: No module named 'customtkinter'
```

A validação visual de abertura está **não concluída**. A sprint não deve ser considerada integralmente validada em runtime gráfico até execução em ambiente com display e dependências instaladas.
