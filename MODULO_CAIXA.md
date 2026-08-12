# Módulo Caixa — NabiCode 2.5.1 DEV

## Fluxo

Cada terminal mantém no máximo uma sessão aberta. A abertura exige `Informar saldo inicial` ou `Abrir sem informar`; a segunda opção registra saldo zero e modo `SEM_VALOR_INFORMADO`. Trocar de usuário não troca a sessão, mas cada operação registra seu responsável.

O fechamento registra um snapshot imutável com esperado, contado, diferença, observação, usuário e horário. Diferenças exigem observação. Uma sessão fechada não aceita movimentos e não é reaberta automaticamente.

## Cálculo

```text
saldo inicial
+ vendas em dinheiro
+ recebimentos em dinheiro
+ suprimentos
- sangrias
- cancelamentos/estornos em dinheiro aplicáveis
= dinheiro físico esperado
```

PIX, cartão e outros meios eletrônicos participam do movimento do período, mas não aumentam o dinheiro físico esperado. Vendas marcadas como `CANCELADO` são desconsideradas.

## Persistência

- `cash_sessions`: terminal, abertura, status e snapshot do fechamento;
- `cash_movements`: sangrias e suprimentos com valor, usuário, data e observação;
- `movimentacoes`: fonte oficial agregada para vendas e recebimentos;
- `auditoria`: eventos `CAIXA_ABERTO`, `SANGRIA`, `SUPRIMENTO` e `CAIXA_FECHADO`.

Os valores próprios do Caixa são persistidos em representação decimal canônica textual para preservar centavos exatamente. Um índice parcial impede duas sessões abertas no mesmo terminal.

## Interface

A aba `Caixa` mostra estado, identificação da sessão, resumo por forma de pagamento, movimento total, dinheiro esperado e histórico. Oferece abertura, sangria, suprimento e fechamento com confirmação. O detalhe histórico preserva o snapshot do fechamento e os movimentos próprios da sessão.
