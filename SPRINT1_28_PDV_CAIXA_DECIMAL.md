# Sprint 1.28 — PDV e Caixa com Decimal

## Alterações

- Totais do carrinho, descontos, acréscimos, pagamentos, falta e troco migrados para `Decimal`.
- Rateio do total final entre itens executado com arredondamento decimal determinístico.
- Preço e subtotal dos itens do PDV preservados como `Decimal` no serviço.
- Pagamentos estruturados serializados em JSON como texto decimal canônico.
- Leitura dos pagamentos estruturados reconstrói valores `Decimal`.
- `PDVTransactionService` valida recebido e troco sem tolerância baseada em `float`.
- Parcelamento do crediário calculado com `Decimal` e ajuste exato da última parcela.
- Escritas em colunas SQLite `REAL` legadas passam por `DecimalStorage.legacy_real()`.
- Descrições e comprovantes do fluxo transacional formatam valores diretamente de `Decimal`.
- Listagem de vendas canceláveis retorna valor monetário como `Decimal`.

## Compatibilidade

- Quantidades físicas continuam aceitando valores numéricos existentes.
- Configurações JSON antigas com números continuam sendo lidas.
- Serviços financeiros recebem texto decimal canônico na fronteira de compatibilidade.
- Schema do banco não foi alterado nesta sprint.

## Testes

- Testes focados de PDV e transação: 29 aprovados.
- Suíte completa: 597 testes aprovados.
