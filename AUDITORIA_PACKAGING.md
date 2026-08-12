# Auditoria de preparação para empacotamento

## Aprovado automaticamente

- `NabiCode.spec` resolve a raiz pelo `SPECPATH`.
- `VERSAO.txt` é incluído por caminho absoluto e carregado também por `_MEIPASS`.
- Assets, config e docs são incluídos quando existentes.
- Dependências fiscais indiretas possuem hidden imports explícitos.
- APPDATA e `NABICODE_APP_DIR` separam dados graváveis dos recursos empacotados.
- Perfis Produção/Teste usam diretórios, marcadores e locks separados.
- Banco, backups, logs, diagnósticos e PDFs usam áreas graváveis.
- Scripts de build executam smoke test do binário e conferem a versão.
- `developer_tools_cli.py validate`: aprovado para versão 2.5.0.
- Startup smoke em código-fonte: aprovado com 2.5.0.
- Testes focados: 21 aprovados e 5 subtests aprovados.

## Não executado nesta etapa

- Build EXE definitivo.
- Instalação em máquina Windows limpa.
- Assinatura, SmartScreen e antivírus.
- Impressora e diálogos físicos.

Esses itens permanecem na validação manual final.
