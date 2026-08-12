# RELATÓRIO DO BUILD OFFLINE WINDOWS — NABICODE 2.5.1 DEV

## Status do Checkpoint 33

**INFRAESTRUTURA CORRIGIDA E REGRESSÃO APROVADA.**

**REBUILD WINDOWS, ONEDIR, SMOKE E INSTALADOR: PENDENTES DE EXECUÇÃO EM
WINDOWS.**

O workspace disponível para esta correção é Linux, não contém PowerShell,
`build_output/dist` nem o wheelhouse produzido na máquina Windows. Portanto,
nenhum EXE ou Setup foi declarado como gerado ou aprovado nesta execução.

## Base

- base de trabalho: `NabiCode_v2_5_1_DEV_CHECKPOINT_32`;
- linha: NabiCode 2.5.1 DEV / candidata de instalação offline;
- `VERSAO.txt`: `2.5.1`;
- perfil da árvore-fonte: `TESTE`, preservado;
- perfil exclusivo do artefato: `build_tools/resources/PERFIL_NABICODE.txt = PRODUCAO`;
- NabiCode 2.5.0 RELEASE: não modificado.

## Causas estruturais corrigidas

### Layout onedir

O `.spec` usa explicitamente o layout moderno do PyInstaller com
`contents_directory="_internal"`. Assim, datas cujo destino lógico é `.` ficam
em `_internal`, enquanto o EXE permanece na raiz da distribuição. O validador
agora exige:

- `_internal/VERSAO.txt = 2.5.1`;
- `_internal/PERFIL_NABICODE.txt = PRODUCAO`.

Não houve achatamento do onedir nem cópia manual pós-build.

### Perfil de runtime

Foi adicionado um runtime hook exclusivo do PyInstaller. Ele roda antes de
`main.py`, lê `_MEIPASS/PERFIL_NABICODE.txt`, recusa conteúdo diferente de
`PRODUCAO` e publica o perfil e o caminho de versão no ambiente do processo
empacotado. Isso evita o fallback `TESTE` sem tocar em `core/runtime_profile.py`
ou em qualquer regra funcional.

O smoke do onedir agora só passa se o trace confirmar simultaneamente:

- `runtime_profile_ready` com `profile = PRODUCAO`;
- `startup_smoke_complete`;
- versão gravada igual a `2.5.1`.

### Certifi

`certifi/cacert.pem` é o bundle público de autoridades certificadoras usado para
validar identidades TLS/HTTPS. Ele foi preservado. A exceção do validador é
literal e única: `_internal/certifi/cacert.pem`.

Continuam proibidos:

- qualquer outro `.pem`;
- `.pfx`, `.p12` e `.key`;
- bancos, logs, bytecode e código-fonte;
- caches, ambientes virtuais, wheelhouse e árvores de testes.

Referência técnica: <https://github.com/certifi/python-certifi>.

### Coleta PyInstaller

O laço que executava `collect_all()`, `collect_submodules()` e
`collect_dynamic_libs()` para oito pacotes foi removido. Ele duplicava a coleta
e transformava arquivos de desenvolvimento, como `matplotlib/tests`, em DATA.

O build agora usa a análise normal e os hooks oficiais do PyInstaller e do
`pyinstaller-hooks-contrib`, mantendo apenas hidden imports explícitos dos
módulos realmente usados pelo NabiCode. O hook de CustomTkinter existe no
hooks-contrib desde 2023.4, e o próprio PyInstaller possui suporte integrado ao
Matplotlib. A API oficial também confirma que `collect_all()` coleta todos os
datas, binários e submódulos, justificando sua remoção neste caso.

Referências:

- <https://pyinstaller.org/en/latest/hooks.html>
- <https://github.com/pyinstaller/pyinstaller-hooks-contrib/blob/master/CHANGELOG.rst>
- <https://github.com/pyinstaller/pyinstaller>

## Pipeline oficial

`build_tools/build_offline_windows.ps1` agora executa, em ordem:

1. criação/reutilização da `.build-venv`;
2. instalação exclusivamente pelo wheelhouse com `--no-index`;
3. `python -m compileall -q .`;
4. `python -m pytest -q`;
5. build e validação do onedir;
6. smoke direto do EXE;
7. manifesto e hashes da distribuição;
8. localização robusta do `ISCC.exe`;
9. compilação e validação do instalador;
10. `build_output/installer/SHA256SUMS.txt`.

A limpeza remove somente `dist`, `work`, `installer` e evidências regeneráveis.
`build_output/wheelhouse` e `build_output/.build-venv` são preservados.

## Validações executadas nesta máquina

| Validação | Resultado |
| --- | --- |
| `python -m compileall -q .` | aprovado |
| testes focados da infraestrutura | 11 passed |
| suíte integral | **918 passed, 11 subtests passed em 19,25 s** |
| auditoria estática do build | aprovado; versão 2.5.1 |
| pipeline PowerShell oficial | não iniciado: PowerShell ausente |
| guarda de build fora do Windows | aprovado; falhou explicitamente com exit 2 |

O conjunto anterior tinha 912 testes. Seis testes de infraestrutura foram
adicionados; nenhum teste existente desapareceu.

## Resultado do build, smoke e Inno nesta execução

- Analysis: não executado neste Linux;
- PYZ: não executado;
- PKG: não executado;
- EXE: não executado;
- COLLECT: não executado;
- validação física do conteúdo: pendente;
- smoke direto do onedir: pendente;
- compilação Inno Setup: pendente;
- `NabiCode_2.5.1_Setup_Offline.exe`: não gerado;
- SHA-256 do instalador: pendente.

## Comando obrigatório para retomada no Windows

Executar na raiz do checkpoint, sem contornar o pipeline:

```powershell
powershell -ExecutionPolicy Bypass -File build_tools\build_offline_windows.ps1
```

Somente um resultado verde desse comando permite iniciar a validação manual.

## Promoção

Não promover para RELEASE. O estado permanece **NabiCode 2.5.1 DEV / candidata
de instalação offline**, aguardando rebuild e testes físicos em máquina limpa.
