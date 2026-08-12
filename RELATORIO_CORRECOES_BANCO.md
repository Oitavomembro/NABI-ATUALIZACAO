# Relatório de correções do banco — Checkpoint 4

## Alterações

Nenhuma implementação de banco precisou ser alterada. A auditoria e os testes existentes confirmaram o contrato transacional. Foram adicionadas somente regressões para lacunas de falha injetada e propriedade de conexão externa.

## Arquivos de teste

- `tests/test_pdv_transaction_service.py`: dois cenários de rollback após efeitos intermediários.
- `tests/test_external_connection_ownership.py`: guarda arquitetural contra commit/rollback/close em conexão recebida.

## Cenários já cobertos e preservados

- rollback integral de recebimento, compra, NF-e, cadastro e migração;
- restore inválido;
- isolamento Produção/Teste;
- fechamento de conexão e rollback em context managers;
- saldo reconciliado, parcelas, histórico migrado e documental sem recálculo na UI.

## Validação focada

- Auditoria ampla inicial: `127 passed`.
- Grupo após testes novos: `29 passed`.
- Nenhuma navegação, tema, layout ou implementação do flash foi modificada.

## Validação completa

- `python -m compileall -q .`: aprovado.
- `python -m pytest -q`: `886 passed, 11 subtests passed in 75.89s`.
- Aumento de 883 para 886 explicado pelos três testes novos.

## Riscos restantes

- `schema_initializer.py` é extenso e deve ser alterado somente com migração segura.
- SQL legado em callbacks de cliente continua pendência de manutenção, sem defeito transacional reproduzido.
- Validação de concorrência real em compartilhamento de rede depende do ambiente operacional.
