# Checkpoint 28 — Instalador offline

Data: 08/08/2026  
Status: **PROJETO APROVADO; COMPILAÇÃO WINDOWS PENDENTE**

## Projeto

O instalador oficial é `build_tools/inno/NabiCode_Offline.iss`, compilado por `build_tools/build_windows.py installer` após validação do onedir.

Nome esperado:

```text
NabiCode_2.5.1_Setup_Offline.exe
```

## Propriedades implementadas

- instalação x64 em `{autopf}\NabiCode` com elevação administrativa;
- versão 2.5.1 no executável de setup/desinstalador;
- atalho no Menu Iniciar;
- atalho opcional na Área de Trabalho;
- desinstalador padrão do Inno Setup;
- fechamento coordenado da aplicação;
- nenhuma URL, downloader, pip ou Python instalado;
- cópia integral do onedir já validado;
- AppData não é incluído em `[Files]` nem em remoções de uninstall;
- mensagem de log explícita de preservação dos dados.

## Política de dados

Desinstalar remove somente `{app}`. Banco, configurações, backups, relatórios, logs e estado operacional sob `%APPDATA%\NabiCode` permanecem preservados. Remoção de dados deverá ser uma operação separada e confirmada explicitamente; não faz parte do setup atual.

## Runtime Microsoft

O instalador ainda não inclui `vc_redist.x64.exe`. A decisão depende da inspeção das dependências PE do onedir Windows real. Se necessário, somente um redistributable oficial, assinado e com hash documentado poderá ser incorporado. Não haverá download no cliente.

## Validação

```text
11 passed, 5 subtests passed
```

O Inno Setup não está disponível neste Linux; o Setup EXE não foi fabricado nem declarado aprovado.

## Arquivos alterados

- `build_tools/inno/NabiCode_Offline.iss`;
- `build_tools/build_windows.py`;
- `GERAR_EXE_FINAL.bat`;
- `GERAR_INSTALLADOR.bat`;
- `NabiCode.iss` — bloqueio de uso do pipeline legado;
- `tests/test_offline_build_tools.py`;
- `tests/test_startup_smoke_test.py`;
- `CHECKPOINT_28_INSTALADOR_OFFLINE.md`.
