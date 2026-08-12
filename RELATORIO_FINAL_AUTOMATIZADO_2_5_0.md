# Relatório final automatizado — NabiCode 2.5.0

## Resultado

- Suíte normal: 902 testes aprovados.
- Subtests: 11 aprovados.
- Suítes separadas: 3 testes aprovados — stress, benchmark e soak.
- Total de testes automatizados distintos executados: 905.
- Compileall: aprovado.
- Startup smoke: 2.5.0.

## Operações simuladas

- 1.000 vendas e 2.000 movimentos de estoque.
- 100 cancelamentos e 100 rollbacks por falha injetada.
- Pagamentos em dinheiro, PIX, crédito, crediário e mistos.
- Parcelas e saldo do cliente validados por cálculo independente.
- Backup de base carregada, validação, alteração destrutiva e restore.
- 5.000 ciclos de conexão, consulta, escrita, commit/rollback e fechamento.

## Backup e restore

- Backup normal, corrompido, vazio, parcial e destino indisponível cobertos.
- Restore válido e inválido cobertos.
- Banco anterior protegido por backup de segurança.
- Conexões fechadas mesmo quando a segunda abertura falha.

## Migrações

- Banco vazio, base antiga, repetição, interrupção e dados legados cobertos.
- Migração agora usa uma única transação e publica a versão somente após sucesso.

## Falha real encontrada pelo stress

- Cancelamento de venda paga reduzia saldo de outras compras a prazo.
- Correção usa somente `valor_aberto` da venda cancelada.
- Regressão adicionada e stress repetido com sucesso.

## Performance

- p50: produto 5,544 ms; cliente 7,593 ms; histórico 1,856 ms; dashboard 12,115 ms; financeiro 5,612 ms.
- Nenhuma otimização especulativa foi aplicada.

## Soak e recursos

- 5.000 ciclos em 22,916 segundos.
- Memória rastreada após GC variou de 6.059 a 6.251 bytes nas amostras equivalentes.
- Nenhum lock persistente, corrupção ou arquivo temporário restante.
- Não há evidência suficiente para afirmar memory leak.

## Arquivos funcionais principais modificados

- `services/backup_service.py`
- `database/schema_initializer.py`
- `core/diagnostic_logging.py`
- `nabicode_legacy.py`
- `services/pdv_transaction_service.py`
- `pytest.ini`

## Pendências

- Todos os itens de `VALIDACAO_MANUAL_WINDOWS_PENDENTE.md`.
- A candidata automatizada não é release final.
