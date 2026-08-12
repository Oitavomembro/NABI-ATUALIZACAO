# Sprint 1.31 — Inicialização do EXE e versão resiliente

## Problema reproduzido

Executáveis gerados pelos scripts de teste e depuração não incluíam `VERSAO.txt`.
O carregador de versão encerrava a aplicação com `RuntimeError` quando o arquivo
não existia ou tinha conteúdo fora do formato esperado.

## Correções

- Criado `core.app_version` com carregamento testável e independente da UI.
- Suporte a execução por código-fonte, PyInstaller onedir/onefile e `_MEIPASS`.
- Leitura com UTF-8 BOM e prefixo opcional `v`.
- Fallback incorporado `2.4.72`, impedindo falha fatal por ausência do arquivo.
- `NabiCode.spec` passou a usar caminho absoluto para `VERSAO.txt`.
- Builds TESTE e DEBUG passaram a incluir explicitamente `VERSAO.txt`.
- Criado `--startup-smoke-test`, que valida a inicialização sem abrir a UI.
- Todos os scripts de geração executam o binário produzido e conferem a versão.

## Validação

- 15 testes focados aprovados.
- 611 testes na suíte completa aprovados.
- Teste de inicialização por código-fonte aprovado.
- O ambiente de validação não possui Windows/PyInstaller; a geração do EXE não
  foi declarada como executada. Os scripts Windows agora rejeitam automaticamente
  uma build cujo binário não conclua o smoke test.
