# Portas comerciais

As portas reais desta fase são `CustomerLookupPort`, `ProductLookupPort`,
`CheckoutPort` e `CommercialEventPort`. Elas atendem ao PDV sem expor SQL,
repositórios ou objetos gráficos.

Leituras que poderão alimentar um futuro `CommercialQueryService`:

- pesquisa e consulta inequívoca de clientes por ID;
- pesquisa e consulta de produtos;
- leitura do estado comercial da sessão.

Ações que deverão passar por autorização antes de um futuro
`CommercialActionService`:

- selecionar cliente e modificar o carrinho;
- preparar pagamento/crediário;
- confirmar ou cancelar uma venda.

Após checkout confirmado poderão surgir eventos como venda concluída, baixa de
estoque e título financeiro criado. Falha em consumidor de evento não desfaz o
commit comercial nem autoriza repetir o checkout.

A direção obrigatória das dependências será:

`UI ou adaptador de IA → API Query/Action → Application Services → Domain → Repositories`

Nenhum adaptador de UI ou IA poderá acessar SQLite diretamente, e o domínio
comercial nunca poderá importar SDKs de IA.

## Fachadas seguras para adaptadores futuros

`CommercialQueryService` concentra leituras e devolve apenas DTOs imutáveis.
`CommercialActionService` concentra mutações, recebe `ActionContext` e exige
confirmação explícita para finalizar ou cancelar venda. Cancelamento é sensível;
checkout é crítico. A consulta de crédito é apenas informativa: o limite continua
sendo revalidado por `PDVTransactionService` dentro da transação.

Direção permitida para uma futura integração:

`IA/provider → AI Tool Adapter → Query/Action Service → Application/Domain → gateways → backend`

O adaptador de IA não poderá importar repositórios, abrir SQLite, alterar saldo
ou estoque, nem chamar `PDVTransactionService` diretamente. Eventos posteriores
ao commit (`SaleCompleted`/`SaleCancelled`) são efeitos secundários: sua falha
deve ser informada sem desfazer o fato persistido ou permitir repetição.

Clientes e recebimentos seguem o mesmo limite: `CustomerApplicationService`
mantém cadastro/ficha por `customer_id`; consultas de extrato, parcelas e
recebimentos passam por `CommercialQueryService`; recebimentos mutáveis passam
por `CommercialActionService` e exigem confirmação. O backend suporta baixa
parcial transacional. O estorno agregado de recebimento não foi exposto porque
o estorno atual trabalha por pagamento de título e não recompõe de forma
inequívoca uma operação distribuída entre várias vendas/parcelas.

O extrato não fabrica saldo histórico por lançamento. Ele fornece débitos,
créditos e efeitos comprováveis, mais o saldo consolidado atual, marcando
`historical_running_balance_available=False`.

## Financeiro e cobranças

`FinancialQueryService` separa títulos `RECEBER`, títulos `PAGAR`, cobranças de
clientes e baixas efetivas. Cobrança é derivada exclusivamente de parcelas de
clientes; contas da empresa não entram nessa projeção. O resumo financeiro é de
caixa/títulos comprováveis e não pretende ser DRE contábil.

`FinancialActionService` exige `ActionContext` e confirmação para criar ou
baixar títulos. Cancelamento e estorno individual são críticos. Títulos
integrados não podem ser cancelados isoladamente: a operação permanece no
módulo de origem. Eventos financeiros são emitidos apenas depois do commit e
sua falha não autoriza repetir a mutação.

Uma futura IA poderá consultar essas fachadas e solicitar ações por elas, mas
não poderá importar `FinanceiroService`, repositórios nem abrir SQLite.

## Produtos e estoque

`ProductApplicationService` oferece cadastro, consulta inequívoca por
`product_id`/código de barras, saldo, estoque mínimo e histórico comprovável.
`StockActionService` atende somente entradas, saídas e ajustes manuais; vendas e
cancelamentos continuam no fluxo transacional do PDV.

Estoque negativo respeita `permite_estoque_negativo` do produto. A autorização
excepcional do PDV continua explícita no checkout e não é oferecida pelas ações
manuais. Entradas e saídas são sensíveis; ajuste absoluto é crítico. Eventos são
posteriores ao commit e falhas neles nunca autorizam repetir a movimentação.

Fluxo mínimo de uma futura interface:

```python
session = application.new_session()
application.search_customers("ficha ou nome")
application.select_customer(session, customer_id)
application.add_product(session, product_id, quantity=1)
# ou application.add_loose_item(...)
application.prepare_payments(session, payments)
# ou application.prepare_store_credit(...)
command = application.prepare_checkout(session)
result = application.checkout(session, user="operador")
```
