# Sprint 1 — Extração da orquestração de Produtos

- criada `ProductApplicationService`;
- cadastro/edição de produto coordena Produto e Estoque fora da UI;
- cadastro inicial não cria ajuste duplicado de estoque;
- edição ajusta estoque somente quando o saldo muda;
- produto do tipo serviço não gera movimentação de estoque;
- formatação da tabela saiu da interface;
- mensagens de integridade foram centralizadas;
- corrigida condição duplicada na validação do fator de conversão;
- adicionados testes unitários da nova camada.
