# Auditoria 2.4.37 — Atualizador transacional

## Implementado

- validação de versão mínima e versões de origem aceitas;
- validação SHA-256 de todos os arquivos do pacote;
- suporte a remoção declarada de arquivos obsoletos;
- snapshot obrigatório do banco antes da atualização;
- backup dos arquivos que serão substituídos ou removidos;
- estado persistente: PREPARADO, APLICANDO, ARQUIVOS_APLICADOS, CONCLUIDO ou rollback/falha;
- aplicação em processo separado usando o próprio executável;
- validação após reinício dos hashes, versão, integridade do banco, chaves estrangeiras, esquema e tabelas obrigatórias;
- rollback dos arquivos e do banco em falha de validação;
- histórico JSONL de atualizações;
- relatório de diagnóstico após sucesso;
- pacote diagnóstico 2.4.38 para testar atualização sem alterar regras de negócio.

## Validação

- 455 testes: OK.
- developer_tools_cli.py validate: OK.
- compilação Python: OK.
