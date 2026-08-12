# Financeiro — Reconciliação e regressões — NabiCode v2.4.90

Base: `NabiCode_v2_4_90_BASE_OFICIAL_INTEGRADA`

## Escopo executado

Alterados exclusivamente componentes financeiros e testes. Não foram alterados Interface, Documental, PDV ou `nabicode_legacy.py`.

## Correção principal

Foi criada uma única rotina transacional de reconciliação financeira no `FinanceiroService`, apoiada por `FinanceiroRepository` e `FinanceiroCalculator`.

A reconciliação usa `movimentacoes.valor_aberto` como saldo da compra e confronta:

- `clientes.saldo_devedor`;
- soma de `movimentacoes.valor_aberto` das compras não canceladas;
- soma de `parcelas.valor_parcela - parcelas.valor_pago`.

Quando parcelas históricas possuem saldo maior que a compra, indicando pagamento anterior não refletido em `parcelas.valor_pago`, a diferença é distribuída nas parcelas em aberto antes do novo recebimento. Quando parcelas comportam menos dívida que `movimentacoes.valor_aberto`, a divergência é considerada não reconciliável automaticamente e o pagamento é bloqueado.

O saldo do cliente é corrigido para a soma reconciliada das compras antes da validação do pagamento.

## Pagamento parcial R$ 220,00 / R$ 20,00

Teste específico criado. Com dívida aberta reconciliada de R$ 220,00, pagamento de R$ 20,00 é aceito e persiste saldo final de R$ 200,00 em cliente, compra e parcelas.

## Transação e rollback

Toda reconciliação e todo recebimento permanecem sob `DatabaseManager.session(write=True)`.

Foi criado teste que injeta falha durante a atualização de parcela, depois do início da operação. A transação reverte integralmente:

- saldo do cliente;
- saldo da compra;
- parcelas;
- título financeiro;
- movimento de pagamento.

## Decimal e persistência

As rotinas de recebimento/reconciliação passaram a respeitar colunas canônicas `*_decimal` quando existentes, com `DecimalStorage.read/pair` e `FinanceiroCalculator`.

Foram eliminadas leituras que ignoravam `saldo_devedor_decimal`, `valor_aberto_decimal`, `valor_parcela_decimal` e `valor_pago_decimal` nesse fluxo.

## Recibo

Nenhum arquivo documental foi alterado. O recibo existente lê o movimento de pagamento e o saldo do cliente após commit. Como esses valores agora são persistidos somente após reconciliação e a operação é revertida em qualquer inconsistência, `Saldo antes` e `Saldo depois` passam a derivar do estado financeiro reconciliado. Teste específico valida R$ 220,00 antes e R$ 200,00 depois.

## Testes

- Regressão financeira ampliada: `73 passed`.
- Suíte completa: `746 passed, 12 subtests passed`.
- Compilação dos arquivos alterados: aprovada.
- Auditoria AST de imports: nenhum import morto encontrado nos arquivos alterados.

## python main.py

Executado antes da entrega.

Bloqueios do ambiente:

- `_tkinter.TclError: couldn't connect to display ":0"`;
- `ModuleNotFoundError: No module named 'customtkinter'`.

A execução gráfica não pôde ser validada neste ambiente. A sprint não é declarada validada em runtime gráfico.

## Patch de legado

Não necessário nesta sprint. `nabicode_legacy.py` não foi alterado. O fluxo de recebimento já delega ao `FinanceiroService`; a correção foi realizada integralmente nas camadas financeiras permitidas.
