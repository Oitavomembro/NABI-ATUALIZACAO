# Auditoria do instalador — Checkpoint 40

## Causa do resíduo observado

O script possuía `CloseApplications=yes`, mas não declarava um identificador de processo compartilhado com o aplicativo. A desinstalação podia iniciar com binários ainda mapeados pelo processo, e o Windows/Inno deixava arquivos que não podiam ser removidos.

## Contrato corrigido

- O processo real do NabiCode cria o mutex Windows `NabiCodeApplicationMutex` depois do smoke/update-helper e antes do runtime operacional.
- Smoke e splash-helper não criam o mutex.
- O mutex não substitui nem enfraquece o `DatabaseUsageLock`.
- A liberação ocorre no fim do `finally`, depois de tarefas, DatabaseLock, splash-helper e sinais temporários.
- O Inno declara `AppMutex=NabiCodeApplicationMutex`; instalação, atualização e desinstalação não devem prosseguir enquanto a instância real estiver aberta.
- Não existe `taskkill` nem encerramento forçado. O usuário fecha o aplicativo normalmente, protegendo transações em andamento.

Também foram preservados `CloseApplications=yes`, `RestartApplications=no`, `AppId` estável e adicionada a política `UninstallLogMode=append` para atualização sobre a instalação existente.

## Programa versus dados

- Binários: `{autopf}\NabiCode`, normalmente `C:\Program Files\NabiCode`.
- Dados: `%APPDATA%\NabiCode` e caminhos de runtime profile existentes.
- O `.iss` não instala, sobrescreve nem apaga `{userappdata}\NabiCode`.
- Não foi adicionada regra ampla de exclusão em `{app}` que pudesse remover arquivo não pertencente ao instalador.

## Conteúdo offline

O pipeline continua produzindo um único `NabiCode_2.5.1_Setup_Offline.exe`. A validação da distribuição proíbe `.py`, `.pyc`, testes, `build_tools`, wheelhouse, `.venv`, caches, bancos e logs. Python/SDL e dependências ficam no onedir `_internal`; não há pip, download ou compilação no cliente.

O wheelhouse não faz parte do ZIP DEV nem do setup. Ele é somente insumo de build e deve ser preparado/reutilizado em `build_output\wheelhouse` no Windows.

## Atualização existente

O `AppId` não mudou, evitando instalação paralela. O Inno atualiza a mesma instalação, conserva AppData e mantém log cumulativo dos arquivos instalados. Binários antigos registrados são administrados pelo mesmo desinstalador. Migrations e backup continuam sob o fluxo já existente do NabiCode; não foram modificados.

## Ícone futuro

PyInstaller e Inno aceitam opcionalmente `build_tools/resources/NabiCode.ico`. Se o arquivo não existir, o pipeline continua válido. Nenhum ícone foi inventado, convertido ou incluído neste checkpoint.

## Validação disponível

Auditoria de fonte aprovada para 2.5.1, distribuição `NabiCode_v2_5_1`, fonte TESTE e artefato PRODUCAO. O Inno/PyInstaller não foram executados neste Linux. O bloqueio real de desinstalação, limpeza de Program Files e setup final permanecem pendentes de validação Windows.
