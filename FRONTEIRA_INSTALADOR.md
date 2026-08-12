# Fronteira do instalador

Arquivos relacionados ao instalador pertencem à frente separada. A branch `dev/nabicode-2.5.1` não deve modificá-los salvo missão explícita.

## Arquivos protegidos por esta fronteira

Incluem, entre outros:

- `NabiCode.iss`;
- `build_tools/`;
- scripts de geração de executável, pacote, build e instalador;
- especificações PyInstaller e fontes Inno Setup;
- documentação e validações históricas do instalador.

Esses arquivos não foram apagados porque registram a base exata do Checkpoint 40 e alguns também descrevem o empacotamento necessário da aplicação. A presença no repositório de desenvolvimento não autoriza alterações.

Artefatos exclusivamente gerados, como `build/`, `dist/`, `build_output/`, `wheelhouse/`, executáveis e instaladores, ficam excluídos pelo `.gitignore`. Código-fonte e documentação permanecem versionáveis.

Qualquer missão futura que exija alterar essa fronteira deve declarar explicitamente o escopo, comparar com a frente oficial do instalador e impedir mistura acidental de branches ou repositórios.

