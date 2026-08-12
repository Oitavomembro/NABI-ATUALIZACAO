# Checkpoint 4 — estabilidade e atomicidade do banco

## Escopo

Auditoria de SQLite, conexões, commit, rollback, close, migrações, runtime profiles, isolamento, concorrência e fluxos críticos de Venda, Finalização, Estoque, Financeiro, Compras, NF-e e Clientes. Todos os testes usaram bancos temporários isolados; nenhum banco real do usuário foi acessado.

## Conexões e configuração

- `open_connection` configura `row_factory`, `busy_timeout` e `foreign_keys=ON`.
- Modo local usa WAL/NORMAL; modo de rede usa DELETE/FULL, evitando WAL em compartilhamento de rede.
- Falha durante configuração fecha a conexão antes de propagar.
- `DatabaseManager.session` e `connection_session` fecham sempre; escrita confirma no sucesso e reverte na exceção.
- Backup fecha origem e destino inclusive em falha.

## Propriedade transacional

- Métodos que recebem `connection`/`conn` externo em repositories e services não chamam `commit`, `rollback` ou `close`.
- Services proprietários de connection factory encerram a transação completa no mesmo método.
- Venda/finalização coordena pagamentos, estoque e financeiro na mesma conexão em `PDVTransactionService`.
- Estoque oferece operações `*_na_transacao` para composição sem commit interno.
- Compras e financeiro recebem conexão externa nas mutações compostas.
- Importação de NF-e aplica persistência atômica e rollback em falha.

## Runtime profile e isolamento

- Produção e Teste usam diretórios distintos.
- Marcador lateral do banco impede abertura cruzada entre perfis.
- Lock por banco impede segunda instância.
- No Windows, verificação de PID usa API nativa; `os.kill(pid, 0)` não é chamado.
- Testes de perfil e lock passaram em ambiente isolado.

## Migrações e integridade

- Migrações são ordenadas por versão e registram `db_schema_version` na mesma transação.
- Migração com falha executa rollback e mantém a versão anterior.
- Auditoria de manutenção verifica `integrity_check` e `foreign_key_check`.
- Inicializador de schema é grande, mas proprietário da conexão; não foi dividido nesta estabilização.

## Concorrência

- `busy_timeout` reduz falhas transitórias de lock.
- Journal é selecionado conforme modo local/rede.
- O lock de uso impede duas instâncias do NabiCode sobre o mesmo banco.
- Não foi introduzido threading para persistência; Tk continua separado das garantias transacionais.

## Testes focados

Executados 127 testes de SQLite, manutenção, runtime profile, PDV, rollback, produto, cadastro, estoque, compras, NF-e, financeiro e clientes.

Resultado: `127 passed in 18.98s`.

## Achados e decisão

- CRÍTICO/ALTO: nenhum defeito reproduzido de perda de atomicidade ou mistura de banco.
- MÉDIO: `schema_initializer.py` permanece extenso e merece manutenção cautelosa, mas alterar agora aumentaria risco.
- BAIXO: boilerplate de propriedade de conexão aparece em alguns services/repositories autônomos, de forma consistente.

Nenhuma mudança funcional foi necessária. Não foram adicionados commits internos, migrações ou alterações de schema.
