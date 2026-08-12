# RELATÓRIO HOTFIX — CHECKPOINT 34 — PIPELINE DO INSTALADOR WINDOWS

## Estado

**HOTFIX DE INFRAESTRUTURA APROVADO NOS TESTES.**

O estado permanece **NabiCode 2.5.1 DEV / candidata de instalação offline**.
Não houve promoção para RELEASE e nenhum código funcional foi alterado.

O rebuild final do instalador será executado pelo usuário no Windows, em
`C:\NB\NabiCode`. Portanto, este relatório não declara o novo Setup aprovado.

## Evidência Windows recebida

No Checkpoint 33 executado realmente no Windows:

- wheelhouse offline: aprovado;
- suíte: aprovada;
- PyInstaller Analysis/PYZ/PKG/EXE: aprovado;
- COLLECT: aprovado;
- saída: `C:\NB\NabiCode\build_output\dist`;
- reprovação: validação pré/pós-Inno não encontrou `manifest.json` e
  `SHA256SUMS.txt` na localização esperada.

## Causa raiz

`build_windows()` chamava:

```python
write_manifest(distribution, build_manifest(distribution, version=version))
```

Na implementação anterior, `write_manifest()` usava `root.parent`. Como `root`
era `build_output/dist/NabiCode_v2_5_1`, as evidências eram gravadas em:

- `build_output/dist/manifest.json`;
- `build_output/dist/SHA256SUMS.txt`.

Entretanto, `validate_installer()` procurava em:

- `build_output/manifest.json`;
- `build_output/SHA256SUMS.txt`.

O PyInstaller e o COLLECT não falharam. A reprovação foi causada por duas
localizações incompatíveis dentro da própria infraestrutura.

## Localização canônica definida

As evidências pertencem ao processo de build, não ao runtime instalado. A única
localização canônica agora é:

```text
build_output/
    manifest.json
    SHA256SUMS.txt
    dist/
        NabiCode_v2_5_1/
    installer/
        NabiCode_2.5.1_Setup_Offline.exe
        SHA256SUMS.txt
```

Os dois arquivos de evidência onedir não são colocados dentro da aplicação nem
incluídos pelo `[Files]` do Inno Setup.

## Fluxo corrigido

Após o smoke do EXE:

1. `build_manifest()` inventaria todos os arquivos do onedir;
2. `write_manifest(..., evidence_root=BUILD_ROOT)` grava as duas evidências em
   `build_output`;
3. `validate_onedir_evidence()` relê as evidências;
4. compara produto, versão, tipo onedir e lista de arquivos;
5. recalcula tamanho e SHA-256 de cada arquivo da distribuição;
6. confirma que `SHA256SUMS.txt` corresponde exatamente ao manifesto;
7. somente então libera a compilação Inno;
8. após o Inno, a validação do instalador repete a verificação do onedir.

Se a distribuição for alterada depois do manifesto, o pipeline reprova.
Arquivos ausentes, extras, tamanho divergente, hash divergente ou hashes fora de
ordem também reprovam.

## Correções incorporadas no Inno Setup

O arquivo `build_tools/inno/NabiCode_Offline.iss` contém definitivamente:

```ini
OutputDir=..\..\build_output\installer
```

```ini
Source: "..\..\build_output\dist\{#DistName}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
```

O comentário Pascal Script inválido, que continha chaves aninhadas ao mencionar
`{userappdata}`, foi substituído por comentário sem constantes entre chaves:

```pascal
{ Dados operacionais do NabiCode em AppData são deliberadamente preservados. }
```

## Caminho curto no Windows

A compactação profunda do lxml falhou anteriormente em um caminho longo. O
pipeline agora reprova explicitamente raiz de projeto superior a 80 caracteres
e recomenda:

`C:\NB\NabiCode`

A mesma guarda existe no PowerShell e no validador Python. A limitação não é
silenciada nem tratada por truncamento de nomes.

## Testes executados

| Teste | Resultado |
| --- | --- |
| testes focados da infraestrutura | **13 passed** |
| `python -m compileall -q .` | aprovado |
| suíte completa | **920 passed, 11 subtests passed em 19,41 s** |

A suíte anterior do Checkpoint 33 possuía 918 testes. Dois testes foram
adicionados: localização/integridade canônica das evidências e detecção de
adulteração do onedir. Nenhum teste existente foi removido.

## Arquivos alterados contra o Checkpoint 33

Arquivos existentes modificados:

1. `build_tools/build_offline_windows.ps1`
2. `build_tools/build_windows.py`
3. `build_tools/inno/NabiCode_Offline.iss`
4. `tests/test_offline_build_tools.py`

Arquivo adicionado:

1. `RELATORIO_HOTFIX_CHECKPOINT_34_INSTALLER_PIPELINE.md`

Arquivos removidos: nenhum.

## Escopo preservado

Não foram alterados PDV, vendas, financeiro, banco, impressão, corte,
reimpressão, navegação, flash, interface, splash ou regras comerciais.

## Continuação exata no Windows

Na raiz curta `C:\NB\NabiCode`, preservar/recolocar o wheelhouse existente em
`build_output\wheelhouse` e executar exclusivamente:

```powershell
powershell -ExecutionPolicy Bypass -File build_tools\build_offline_windows.ps1
```

O resultado esperado é:

1. suíte verde;
2. PyInstaller e COLLECT verdes;
3. `build_output\manifest.json` presente e validado;
4. `build_output\SHA256SUMS.txt` presente e validado;
5. Inno Setup concluído;
6. `build_output\installer\NabiCode_2.5.1_Setup_Offline.exe`;
7. `build_output\installer\SHA256SUMS.txt`.

O instalador e os testes físicos continuam pendentes até essa execução real.
