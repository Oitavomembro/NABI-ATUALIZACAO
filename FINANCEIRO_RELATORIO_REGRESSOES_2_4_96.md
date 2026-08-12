# Financeiro — fortalecimento e simplificação v2.4.96

Base obrigatória: `NabiCode_v2_4_96_TESTE_INTEGRADO_HOTFIX_CLIENTES`.
Hotfixes posteriores de logo/marca d'água foram ignorados.

## Escopo alterado

- `repositories/financeiro_repository.py`
- `services/financeiro_calculator.py`
- `tests/test_financeiro_fortalecimento_2496.py`

Nenhum arquivo de Interface, PDV, Documental, Cadastros ou `nabicode_legacy.py` foi alterado.

## Consolidações

1. `atualizar_saldo_compra_reconciliado()` deixou de manter SQL próprio e reutiliza `atualizar_compra_aberta()`.
2. Atualizações de `parcelas.valor_pago/status/data_pagamento/atraso_registrado` passaram por uma única rotina interna de persistência, eliminando SQL duplicado entre reconciliação e baixa normal.
3. `FinanceiroCalculator.saldo_parcelas()` centraliza o cálculo Decimal do saldo agregado das parcelas e é reutilizado pela reconciliação.
4. Não existem caches de saldo nas camadas financeiras auditadas; o estado é relido da persistência dentro da transação.
5. A reconciliação permaneceu sem alteração de resultado e ganhou prova explícita de idempotência após reinicialização do Service.

## Decimal e persistência

- cálculos monetários auditados continuam em `Decimal`;
- não foi encontrado `float()` nas camadas financeiras auditadas;
- persistência dual legado/canônica continua centralizada em `DecimalStorage`;
- nenhuma transação duplicada foi criada;
- nenhum `commit()` ou `rollback()` manual novo foi introduzido;
- rollback continua delegado a `DatabaseManager.session(write=True)`.

## Índices / consultas

Os índices financeiros existentes para `titulos_financeiros` e `pagamentos_titulos` foram preservados. As consultas de reconciliação usam principalmente `movimentacoes.cliente_id/tipo` e `parcelas.movimentacao_id`. Não foi alterado o schema nesta sprint: adicionar índices sem evidência de volume/`EXPLAIN QUERY PLAN` no banco real seria mudança especulativa e desnecessária.

## Testes novos

- saldo R$ 90,00 / pagamento R$ 20,00 => R$ 70,00;
- saldo R$ 220,00 / pagamento R$ 20,00 => R$ 200,00;
- saldo histórico sem compras detalhadas;
- múltiplas dívidas/compras;
- reconciliação idempotente;
- consistência após recriar `FinanceiroService`;
- uma operação não gera dupla baixa;
- soma de parcelas com Decimal exato.

O rollback e estorno continuam cobertos pelos testes financeiros existentes e foram executados novamente na suíte focada.

## Resultados

- `python -m compileall`: aprovado nos arquivos financeiros alterados/teste novo.
- suíte financeira ampliada: **78 passed**.
- suíte completa: **832 passed, 11 subtests passed**; o runner externo reportou timeout depois de imprimir o resumo completo, mas o próprio pytest chegou a 100% e informou zero falhas.
- imports mortos nos três arquivos entregues: nenhum encontrado por análise AST.

## Runtime

`python main.py` foi executado e não abriu neste ambiente por bloqueios externos:

- `_tkinter.TclError: couldn't connect to display ":0"`;
- `ModuleNotFoundError: No module named 'customtkinter'`.

A validação gráfica/runtime não é declarada concluída neste ambiente.
