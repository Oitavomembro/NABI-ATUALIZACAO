# Checkpoint 24 — Arquitetura de dados instalada

Data: 08/08/2026  
Status: **APROVADO EM TESTES DE RESOLUÇÃO DE CAMINHOS**

## Arquitetura

O programa congelado pode permanecer em `C:\Program Files\NabiCode\`. Dados mutáveis permanecem sob o diretório de perfil já criado por `core/runtime_profile.py`:

```text
%APPDATA%\NabiCode\Producao\
  fichario_moveis.db
  fichario_moveis.db.profile.json
  backups_moveis\
  pdf_cupons_moveis\
  relatorios\
  logs\
  config\
  diagnosticos\
  rollback\
  releases\
  atualizacoes\
  fiscal\
```

O perfil de teste usa a árvore correspondente `Teste`.

## Correções comprovadas

- `BACKUP_DIR` deixou de ser relativo ao diretório de trabalho e passou a usar `APP_DIR`.
- `PDF_DIR` deixou de ser relativo e passou a usar `APP_DIR`.
- relatórios de NF-e de devolução passaram a usar `APP_DIR/relatorios`.
- configuração absoluta escolhida pelo usuário continua sendo respeitada.
- valor relativo legado, como `backups_moveis`, passa a ser resolvido dentro do AppData, não dentro de Program Files.
- `RuntimePaths` centraliza e torna testável a topologia de dados sem mudar o formato ou o conteúdo dos dados.

## Compatibilidade e preservação

- O banco já existente em AppData não é movido nem recriado pelo instalador.
- Configurações, logs, relatórios, backups, fiscal, snapshots e estado de atualização ficam fora de `{app}`.
- Atualização/reinstalação pode substituir apenas arquivos do programa.
- Desinstalação não deve remover AppData automaticamente.
- Caminhos absolutos configurados para backup em pendrive, nuvem ou rede são preservados.

## Validação exigida no Windows

O instalador deverá ser testado com `{app}` sem permissão de escrita para usuário comum. O NabiCode deverá criar/abrir banco e artefatos somente em AppData. Essa validação física permanece para o Checkpoint 29.

## Arquivos alterados

- `core/runtime_profile.py`;
- `nabicode_legacy.py`;
- `services/backup_service.py`;
- `tests/test_runtime_profile_isolation.py`;
- `tests/test_backup_service.py`;
- `CHECKPOINT_24_ARQUITETURA_DADOS.md`.

Nenhuma regra de negócio, financeira, PDV ou impressão foi alterada.
