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

A aba `Caixa` é o ponto oficial de todas as operações. Ela mantém a navegação principal acessível e mostra estado, identificação, cards por forma de pagamento, movimento total, dinheiro esperado, ações, movimentações da sessão e histórico.

Com caixa aberto aparecem somente sangria, suprimento e fechamento. Com caixa fechado aparecem somente as duas opções de abertura. Sangria, suprimento, fechamento e detalhes usam modais visuais NabiCode, construídos ocultos e revelados somente depois do layout, sem fade por transparência.

Os antigos acessos `Movimentação de Caixa` e `Finalizar dia` não são mais exibidos no Dashboard. As funções internas legadas permanecem apenas para compatibilidade do código histórico, sem concorrer com o fluxo oficial.

Após o fechamento, nenhuma abertura é disparada automaticamente. A tela consulta novamente o banco, mostra `CAIXA FECHADO` e aguarda uma escolha explícita. O comprovante do fechamento é enviado ao pipeline oficial de impressão térmica 80 mm em segundo plano; falhas de impressora não desfazem o fechamento nem bloqueiam a interface.

Todos os Toplevels do Caixa compartilham uma infraestrutura não bloqueante. Nesta fase de estabilização não usam modalidade, espera, transient, topmost ou alternância de visibilidade. A criação de sessão também possui uma única fronteira: somente confirmação de saldo informado ou clique explícito em abrir sem informar são aceitos.
