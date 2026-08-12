# Testes — v2.4.16

Resultado: **44 testes automatizados aprovados**.

Cobertura nova:

- detecção de produto por EAN;
- bloqueio de NF-e duplicada;
- localização de fornecedor por CNPJ formatado;
- atualização de custo e vínculo produto-fornecedor;
- regressão das camadas existentes.

## v2.4.17 — Assistente de NF-e de devolução

- localização por número e chave;
- devolução parcial;
- devolução integral do saldo;
- bloqueio de quantidade acima do disponível;
- rejeição de item de outra nota;
- cancelamento de rascunho e liberação do saldo;
- validação fiscal do rascunho;
- proteção contra sobrescrita da nota após devolução;
- regressão completa dos módulos anteriores.

Resultado automatizado: 52 testes aprovados.

## Estoque — v2.4.19

- Entrada e saída com histórico.
- Bloqueio por saldo insuficiente.
- Agregação de produto repetido na venda.
- Idempotência da baixa e do estorno.
- Ajuste com motivo obrigatório.
- Serviços sem controle de estoque.
- Produtos abaixo do estoque mínimo.
- Regressão completa: 63 testes aprovados.

## 2.4.20

- Criação de pedido e consolidação de itens repetidos.
- Recebimento parcial e total.
- Conversão de embalagem na entrada de estoque.
- Atualização do custo unitário de estoque.
- Rollback em quantidade superior ao saldo pendente.
- Bloqueio de serviços em pedidos de estoque.

## Pesquisa global (v2.4.32)

- Comandos sem termo de pesquisa.
- Pesquisa de produto por nome sem acento e por código de barras.
- Pesquisa de cliente, fornecedor, NF-e e título financeiro.
- Pesquisa de comandos por palavras-chave.
- Normalização de acentos e caixa.
