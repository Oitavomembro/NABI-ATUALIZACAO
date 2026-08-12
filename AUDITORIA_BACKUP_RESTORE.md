# Auditoria de backup e restauração

## Arquitetura

- `BackupService`: backup diário/manual em múltiplos destinos configuráveis.
- `backup_database`: cópia consistente pela API de backup do SQLite e fechamento garantido.
- `DatabaseMaintenanceService`: validação, backup de segurança e restauração reversível.
- `SystemSnapshotService`: snapshots versionados com manifesto, SHA-256 e `integrity_check`.

## Garantias verificadas

- O arquivo é aceito somente após abertura SQLite, `integrity_check` e `foreign_key_check`.
- Arquivos ausentes, vazios e corrompidos são rejeitados.
- Falha parcial remove o destino incompleto.
- Cada destino falha isoladamente sem impedir os demais.
- Nomes incluem microssegundos e não colidem em operações no mesmo segundo.
- Restore valida a origem e cria backup de segurança antes de substituir o banco atual.
- Falhas de conexão fecham origem e destino, inclusive quando a segunda abertura falha.

## Riscos deliberadamente não alterados

- Retenção automática não possui política configurada no produto atual. Não foi criada uma regra arbitrária que pudesse excluir backups do usuário.
- Falta de espaço, permissão e arquivo bloqueado dependem do sistema operacional; são propagados e o arquivo parcial é removido quando possível.
- A validação de tamanho usa arquivo não vazio e integridade estrutural; não compara tamanhos entre bancos porque compactação, WAL e conteúdo tornam esse limiar não confiável.
