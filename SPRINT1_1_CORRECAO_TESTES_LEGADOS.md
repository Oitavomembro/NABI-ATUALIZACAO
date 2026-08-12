# Sprint 1.1 — Correção dos três testes legados

Base: `NabiCode_v2_4_44_SPRINT1_PRODUTOS.zip`.

## Correções

1. O teste do recibo de pagamento agora valida o botão real `Salvar PDF (opcional)`, mantendo a regra de não gerar PDF automaticamente.
2. Os testes do PDV foram alinhados ao fluxo atual de crediário, que aceita entrada + valor financiado, e agora também cobrem soma incorreta e duas parcelas de crediário.
3. O teste da splash foi alinhado à configuração atual de 45 ms por quadro e até 110 colunas, preservando a splash apenas no startup.

Nenhuma funcionalidade foi revertida para satisfazer testes antigos; os testes foram atualizados para refletir os requisitos atuais aprovados.
