# Auditoria 2.4.41

## Correções

- Migração corretiva única `login_inicio_migrado_v2441` desativa o login inicial em bancos existentes antes da decisão de abrir a tela de login.
- O login só volta quando o proprietário o habilita explicitamente em Segurança.
- Restauração completa desliga temporariamente as chaves estrangeiras dentro da conexão de manutenção, apaga as tabelas operacionais, executa `foreign_key_check` antes do commit e preserva metadados do esquema.
- Em caso de falha, a transação é revertida e o backup validado permanece disponível.

## Validação

- 461 testes executados com sucesso.
- `developer_tools_cli.py validate`: `ok: true`, versão `2.4.41`, sem arquivos ausentes e sem erros.
