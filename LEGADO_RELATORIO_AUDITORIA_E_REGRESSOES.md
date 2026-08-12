# Relatório de auditoria e regressões

## Escopo aplicado

- Função alterada no legado: `executar_migracao_resumida`.
- A implementação transacional duplicada foi removida do legado.
- O ponto de entrada público foi preservado como fachada para `MySQLMigrationService.execute_summary`.
- Interface, financeiro e impressão não foram alterados.

## Redução

- Base integrada antes do patch: 10.357 linhas.
- Legado após o patch: 10.175 linhas.
- Redução líquida: 182 linhas.

## Auditoria do código alterado

- Não há regra SQL duplicada na função do legado.
- A função mantém todas as dependências de runtime: banco, backup, conexão, modo de rede, logger, remoção de demonstração e progresso.
- Nenhuma definição de função ou classe de nível superior está duplicada no `nabicode_legacy.py` resultante.
- Nenhum import novo foi introduzido.
- Nenhum import foi removido: os módulos usados pela implementação antiga continuam referenciados em outras áreas do legado; removê-los sem ampliar o escopo seria inseguro.
- Nenhum código morto foi encontrado dentro da nova fachada.

## Regressões encontradas

### Suíte completa

A suíte apresentou 1 falha preexistente e não relacionada ao patch:

- `tests/test_exe_version_packaging.py::ExeVersionPackagingTests::test_legacy_uses_compiled_fallback`
- O teste exige `COMPILED_APP_VERSION = "2.4.85"`.
- A base integrada contém `COMPILED_APP_VERSION = "2.4.86"`.
- A versão não foi alterada porque está fora do escopo desta redução.

Resultado restante: 690 testes aprovados e 12 subtestes aprovados.

### Inicialização

`python main.py` foi executado, mas o sistema não abriu no ambiente de validação.

Bloqueios técnicos:

- `ModuleNotFoundError: No module named 'customtkinter'`.
- `_tkinter.TclError: couldn't connect to display ":0"` durante o splash.

## Status

Sprint não concluída, porque não foi possível confirmar a abertura da interface no ambiente disponível.
