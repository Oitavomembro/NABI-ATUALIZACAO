# Auditoria 2.4.42

- O login inicial usa exclusivamente `login_inicio_ativado_pelo_usuario_v2442`.
- Bancos existentes recebem a política 2.4.42 antes da decisão de abrir a tela de login.
- Chaves antigas de login não autorizam mais a tela inicial.
- A opção só é reativada quando o usuário salva explicitamente em Segurança.
- O relatório técnico mostra o estado efetivo das chaves de login.
- A restauração completa apaga tabelas filhas antes das tabelas pai e valida `foreign_key_check` antes do commit.
- 461 testes executados com resultado OK.
- `developer_tools_cli.py validate`: OK, versão 2.4.42.
