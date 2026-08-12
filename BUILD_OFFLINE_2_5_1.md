# Build offline — NabiCode 2.5.1 DEV

Checkpoints 25 e 26  
Data: 08/08/2026  
Status: **INFRAESTRUTURA APROVADA; ARTEFATO WINDOWS PENDENTE**

## Estratégia escolhida

Formato inicial: **PyInstaller onedir x64**.

Motivos:

- não exige Python, pip ou bibliotecas no cliente;
- não extrai todo o runtime a cada abertura como um onefile;
- facilita inspeção de DLLs e diagnóstico de imports tardios;
- oferece startup mais previsível;
- permite que o Inno Setup instale a árvore pronta integralmente offline.

PyInstaller não é cross-compiler. O build Windows deve ser produzido e validado no Windows 10/11 x64 com Python 3.14.x. O cliente final não recebe esse Python de build: recebe apenas o runtime coletado no onedir.

## Estrutura criada

```text
build_tools/
  build_windows.py
  build_offline_windows.ps1
  prepare_wheelhouse.ps1
  requirements-windows.lock
  pyinstaller/
    nabicode.spec
  resources/
    PERFIL_NABICODE.txt  # PRODUCAO
```

Saídas são criadas somente em `build_output/`.

## Ambiente fixado

O lock de build usa Python 3.14.x e fixa as dependências diretas, inclusive:

- CustomTkinter 5.2.2;
- Pillow 12.2.0;
- Requests 2.34.2;
- Cryptography 46.0.0;
- lxml 6.0.2;
- ReportLab 4.4.9;
- OpenPyXL 3.1.5;
- Matplotlib 3.10.8;
- pywin32 312;
- PyInstaller 6.21.0;
- pyinstaller-hooks-contrib 2026.6;
- pytest 9.1.1.

`Pillow` também foi declarado diretamente em `requirements.txt`, corrigindo a lacuna do Checkpoint 22.

## Wheelhouse e build sem rede

Em uma máquina de preparação conectada, `prepare_wheelhouse.ps1` baixa wheels binárias e gera `SHA256SUMS.txt`. O wheelhouse pode ser levado à máquina de build.

Em uma máquina de build Windows desconectada, `build_offline_windows.ps1`:

1. exige wheelhouse com hashes;
2. cria ambiente temporário somente de build;
3. instala com `--no-index --find-links`;
4. executa a suíte;
5. executa o build onedir;
6. não distribui o ambiente de build.

O uso de pip ocorre somente na máquina de build. O cliente não executa pip.

## Comportamento de `build_windows.py`

- valida versão e arquivos obrigatórios;
- exige Windows e Python 3.14.x para build real;
- valida todas as distribuições necessárias;
- limpa somente saídas anteriores conhecidas;
- usa spec onedir, sem UPX;
- inclui perfil `PRODUCAO` no artefato sem alterar o perfil de teste da árvore DEV;
- coleta dados, submódulos e DLLs de dependências;
- inclui hidden imports fiscais, Pillow, Matplotlib/TkAgg e pywin32;
- exclui testes e suítes da distribuição;
- reprova `.venv`, caches, bancos e segredos;
- executa o EXE gerado com `--startup-smoke-test`;
- valida versão retornada;
- gera `manifest.json` com tamanho e SHA-256 de cada arquivo;
- gera `SHA256SUMS.txt`.

## Dados não incluídos

O onedir não inclui:

- banco real ou de teste;
- backups;
- certificados/chaves;
- `.venv`;
- `__pycache__`, `*.pyc`, `.pytest_cache`;
- testes normais, benchmark, stress ou soak;
- splash Lightspeed.

## Validação realizada

Auditoria estática:

```text
{"ok": true, "version": "2.5.1", "distribution": "NabiCode_v2_5_1"}
```

Testes focados:

```text
13 passed, 2 subtests passed
```

A tentativa de build neste Linux foi corretamente recusada com código 2 e mensagens explícitas de sistema/versão/dependências. Nenhum artefato Windows falso foi gerado.

## Validações obrigatórias no Windows

1. preparar ou copiar wheelhouse íntegro;
2. executar build offline;
3. revisar warnings do PyInstaller;
4. confirmar módulos e DLLs de pywin32;
5. executar smoke do EXE;
6. executar aplicação completa a partir do onedir;
7. validar impressão RAW, corte, A4 e PDF;
8. inspecionar dependência do VC Runtime;
9. gerar e validar instalador Inno Setup.

## Arquivos alterados

- `build_tools/__init__.py`;
- `build_tools/build_windows.py`;
- `build_tools/build_offline_windows.ps1`;
- `build_tools/prepare_wheelhouse.ps1`;
- `build_tools/requirements-windows.lock`;
- `build_tools/pyinstaller/nabicode.spec`;
- `build_tools/resources/PERFIL_NABICODE.txt`;
- `requirements.txt`;
- `VERSAO.txt`;
- `nabicode_legacy.py` — somente fallback de versão 2.5.1, além dos marcos/caminhos já registrados;
- `tests/test_requirements_manifest.py`;
- `tests/test_exe_version_packaging.py`;
- `tests/test_offline_build_tools.py`;
- `BUILD_OFFLINE_2_5_1.md`.

Nenhuma regra funcional foi alterada.
