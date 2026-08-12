# Relatório de stress automatizado

## Execução

- Comando: `python -m pytest -q -s stress_tests/test_business_stress.py`.
- Banco: SQLite temporário criado e removido pelo teste.
- Duração final consolidada: 21,895 segundos.

## Volume

- 1.000 vendas finalizadas pelo `PDVTransactionService`.
- 2.000 movimentos de estoque.
- 250 vendas a crediário com três parcelas.
- Dinheiro, PIX, crédito, crediário e pagamentos mistos.
- 100 cancelamentos.
- 100 falhas injetadas depois da baixa de estoque.
- Backup validado e restauração comparada com a origem.

## Invariantes

- Quantidade de vendas e parcelas confere com as operações executadas.
- Estoque persistido confere com o cálculo independente.
- Saldo do cliente confere com vendas a prazo ativas.
- Falhas injetadas não deixam venda, estoque, financeiro ou saldo parciais.
- Banco termina com `PRAGMA integrity_check = ok`.
- Restore recupera as 1.000 vendas após alteração destrutiva controlada.

## Bug real encontrado

- Cancelar uma venda paga subtraía o valor total do saldo devedor do cliente, reduzindo dívidas de outras vendas a prazo.
- Causa: cancelamento usava `valor` da venda em vez de `valor_aberto`.
- Correção: saldo agora é reduzido somente pelo valor em aberto da venda cancelada.
- Regressão adicionada à suíte normal.

## Recursos

- Banco final: 552.960 bytes.
- Memória rastreada atual ao final: 46.809 bytes.
- Pico rastreado: 54.760 bytes.
- Esses valores não indicam vazamento; servem como baseline reproduzível desta execução.
