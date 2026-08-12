# NabiCode 2.4.92 — Correção de saldo histórico migrado

- Recebimento passa a operar exclusivamente sobre o saldo total reconciliado do cliente.
- Opção de escolher compra/parcela específica removida da interface de recebimento.
- Saldo consolidado migrado não é zerado quando faltam compras históricas detalhadas.
- Diferença cliente > compras é preservada como `saldo_residual_legado` e pode receber baixa.
- Parcelas históricas incompletas deixam de bloquear pagamentos legítimos.
- Recibo identifica explicitamente valores aplicados em `Saldo histórico migrado`.
- Incluído `AUDITAR_SALDO_CLIENTE.py`, somente leitura, para diagnosticar uma cópia do banco por ficha.
- Nenhum banco de dados é incluído no pacote.
