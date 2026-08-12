# Testes NabiCode 2.4.92 TESTE

- `pytest -q`: **780 passed, 12 subtests passed, 0 falhas**.
- `python -m compileall -q .`: **aprovado**.
- `python main.py`: tentativa realizada; interface bloqueada neste ambiente por `_tkinter.TclError: couldn't connect to display ":0"` e ausência de `customtkinter`.

## Regressões novas cobertas

- ficha migrada com saldo R$ 90 e nenhuma compra detalhada aceita pagamento parcial;
- saldo consolidado R$ 600 com compras detalhadas de R$ 415 continua permitindo recebimento sobre R$ 600;
- saldo R$ 220 / pagamento R$ 20;
- parcelas históricas incompletas não bloqueiam baixa legítima;
- recibo identifica `Saldo histórico migrado`;
- seleção de compra/parcela específica removida do fluxo operacional.
