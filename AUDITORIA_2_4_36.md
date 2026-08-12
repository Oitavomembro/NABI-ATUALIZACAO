# Auditoria NabiCode 2.4.36

- Migração de login opcional executada antes da criação das telas.
- Instalações existentes recebem `login_usuarios_habilitado=0` uma única vez nesta versão.
- Login pode ser reativado manualmente em Segurança.
- Aba `Padrão de fábrica` restaurada no Painel Administrativo.
- Restauração continua disponível também em Configurações.
- Aba Atualizações aceita pacote ZIP com `manifest.json`, valida versão e SHA-256 de todos os arquivos.
- Snapshot validado é obrigatório antes da aplicação.
- Aplicação ocorre após o processo fechar e reinicia o programa.
- Gerador de pacote de atualização incluído para releases Windows compiladas.
- Compilação Python: OK.
- `developer_tools_cli.py validate`: OK.
- Suíte: 450 testes, OK.
