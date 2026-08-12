# Auditoria de atomicidade do banco

## Conclusão

O NabiCode possui limites transacionais coerentes para as operações críticas auditadas. Conexões externas não são confirmadas, revertidas ou fechadas por services/repositories chamados dentro de uma transação maior. Nenhum banco real foi usado nos testes.

## Propriedade

- `DatabaseManager.session(write=True)`: proprietário de conexão, commit, rollback e close.
- `connection_session(write=True)`: proprietário de conexão, commit, rollback e close.
- Services com connection factory própria: proprietários da operação autônoma completa.
- Métodos com argumento `connection`/`conn`: participantes; não finalizam a transação do chamador.
- `PDVTransactionService`: proprietário da transação composta de venda, parcelas, saldo, financeiro, pagamentos e estoque.

## Fluxos auditados

- Venda/finalização: rollback preserva movimento, parcelas, saldo, financeiro, pagamentos e estoque.
- Recebimento: pagamento excedente e inconsistências revertem movimento e saldo.
- Compras: excesso ou falha preserva pedido e estoque anteriores.
- NF-e/XML: falha final reverte toda importação.
- Cadastros: falha posterior reverte cliente/produto e histórico.
- Migração: falha mantém schema version anterior.
- Restore: origem inválida é rejeitada sem substituir o banco válido.
- Reset/restauração: serviços mantêm backup/rollback e encerramento de conexão.

## Isolamento Produção/Teste

Perfis usam diretórios separados, marcador por banco e lock por arquivo. O ramo Windows verifica PID por API nativa. Testes usam `TemporaryDirectory`/`tmp_path` e `--basetemp` dentro da área isolada.

## Cobertura adicionada

- Falha depois da baixa de estoque reverte venda inteira.
- Falha depois da criação do movimento financeiro reverte saldo e venda.
- Verificação automática impede commit, rollback ou close de conexão externa em services/repositories.

Detalhes complementares estão em `AUDITORIA_ESTABILIDADE_BANCO.md`.
