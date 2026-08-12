# NabiCode 2.4.91 — Pacote integrado para testes no Windows

Base de origem: `NabiCode_v2_4_90_BASE_OFICIAL_INTEGRADA`.

## Ordem de integração aplicada

1. Legacy — patch aplicado em `nabicode_legacy.py`, sem substituição integral.
2. Financeiro — reconciliação entre saldo do cliente, compras abertas e parcelas.
3. Cadastros — saldo reconciliado, refresh e histórico.
4. Documental — recibo/PDF usando saldos reconciliados recebidos do Financeiro.
5. Interface — navegação Enter/KP_Enter e controle de foco do PDV.

## Conflito resolvido durante integração

O teste financeiro originalmente esperava que `ReceiptService` reconstruísse os saldos antes/depois sem recebê-los. Isso contrariava a regra arquitetural documental: o recibo não deve recalcular saldo. A integração manteve o Documental como consumidor de dados reconciliados e ajustou o teste para encaminhar `saldo_anterior` e `novo_saldo` retornados pelo Financeiro.

Também foi aplicado o encaminhamento documental no legado para transportar esses dois valores até o recibo e até o PDF sob demanda.

## Correções integradas

- rotina de reconciliação financeira única;
- pagamento parcial legítimo, incluindo cenário saldo R$ 220,00 / pagamento R$ 20,00;
- rollback em inconsistências de persistência;
- sincronização cliente x movimentações x parcelas;
- atualização de saldo nos cadastros/histórico;
- recibo recebe saldo antes/depois já reconciliados;
- PDF continua sob demanda;
- impressão física continua separada do PDF;
- controlador de Enter do PDV extraído;
- Enter e KP_Enter unificados;
- callbacks financeiros restantes extraídos do legado;
- versão de teste atualizada para 2.4.91.

## Validação executada

`python -m compileall -q .`: APROVADO.

Testes focados da integração: 57 passed.

Suíte completa final: 775 passed, 12 subtests passed, 0 falhas.

Startup smoke sem UI: APROVADO; versão retornada: 2.4.91.

`python main.py`: tentativa executada. A abertura gráfica não pôde ser validada neste ambiente por `_tkinter.TclError: couldn't connect to display ":0"` e `ModuleNotFoundError: No module named 'customtkinter'`.

## Status

Este ZIP é um pacote integrado PARA TESTES NO WINDOWS. Não deve ser promovido a base oficial até os smoke tests manuais dos fluxos críticos serem executados no Windows.
