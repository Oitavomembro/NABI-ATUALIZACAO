# Mapa de migrações do banco

## Fonte canônica

- Versão atual do schema: `DB_SCHEMA_VERSION = 13` em `nabicode_legacy.py`.
- Versão persistida: `configuracoes.db_schema_version`.
- Histórico: tabela `schema_migrations`, registrada somente após conclusão.
- Inicializador canônico: `database/schema_initializer.py`.

## Fluxo

1. Lê a versão persistida.
2. Rejeita cliente de rede sem banco servidor.
3. Cria backup obrigatório quando a versão existente é inferior à atual.
4. Inicia `BEGIN IMMEDIATE`.
5. Cria tabelas e colunas com operações idempotentes.
6. Executa migração decimal de produtos.
7. Atualiza a versão canônica.
8. Registra histórico apenas após todas as alterações.
9. Confirma uma única vez.

## Garantias

- Instalação vazia chega diretamente à versão atual.
- Reexecução não duplica dados de demonstração nem estruturas.
- Bases antigas preservam produtos e dados existentes.
- Falha interrompida não persiste tabelas, colunas ou versão intermediária.
- Índices são criados somente após as colunas legadas necessárias.
- Chaves estrangeiras permanecem habilitadas na conexão canônica.

## Migrações especializadas

- `ProductDecimalMigration`: normalização decimal idempotente, usada também em testes de compras, NF-e e produtos.
- `DatabaseMaintenanceService.run_migrations`: executor ordenado por versão para migrações administrativas isoladas.
- `MySQLMigrationService`: importação externa com savepoint e transação própria; não define a versão canônica SQLite.
