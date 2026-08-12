# VALIDAÇÃO MANUAL WINDOWS — NABICODE 2.5.1 DEV

## Status

**PENDENTE DE EXECUÇÃO FÍSICA.**

Não marcar nenhum item como aprovado sem observação real na máquina Windows.

## 1. Rebuild oficial

- [ ] usar Windows 10/11 x64 com Python 3.14;
- [ ] confirmar `build_output/wheelhouse/SHA256SUMS.txt`;
- [ ] confirmar perfil raiz `TESTE`;
- [ ] confirmar `build_tools/resources/PERFIL_NABICODE.txt = PRODUCAO`;
- [ ] desconectar a internet para comprovar o build offline, se possível;
- [ ] executar somente:

```powershell
powershell -ExecutionPolicy Bypass -File build_tools\build_offline_windows.ps1
```

- [ ] registrar `918 passed, 11 subtests passed` ou contagem superior;
- [ ] confirmar Analysis, PYZ, PKG, EXE e COLLECT concluídos;
- [ ] confirmar validação do onedir verde;
- [ ] confirmar Inno Setup verde.

## 2. Conteúdo do onedir

- [ ] `NabiCode_v2_5_1.exe` existe;
- [ ] `_internal/VERSAO.txt = 2.5.1`;
- [ ] `_internal/PERFIL_NABICODE.txt = PRODUCAO`;
- [ ] `_internal/certifi/cacert.pem` existe;
- [ ] `matplotlib/tests` e `matplotlib/testing` ausentes;
- [ ] pytest e testes do projeto ausentes;
- [ ] wheelhouse e `.build-venv` ausentes;
- [ ] código-fonte, caches, bytecode, bancos e logs ausentes;
- [ ] manifesto e SHA256SUMS do onedir existem.

## 3. Smoke direto antes do instalador

- [ ] executar `build_output\dist\NabiCode_v2_5_1\NabiCode_v2_5_1.exe`;
- [ ] confirmar que não foi usado `python main.py`;
- [ ] confirmar startup sem console/traceback;
- [ ] confirmar perfil PRODUÇÃO;
- [ ] confirmar criação/uso dos dados em AppData;
- [ ] fechar normalmente;
- [ ] abrir novamente e confirmar persistência;
- [ ] tentar segunda instância e confirmar bloqueio.

## 4. Instalador

- [ ] `build_output\installer\NabiCode_2.5.1_Setup_Offline.exe` existe;
- [ ] `build_output\installer\SHA256SUMS.txt` corresponde ao arquivo;
- [ ] instalar sem internet;
- [ ] confirmar atalhos do Menu Iniciar e Área de Trabalho;
- [ ] iniciar sem Python, pip ou Git instalados;
- [ ] confirmar que nenhum download foi solicitado;
- [ ] confirmar perfil PRODUÇÃO e versão 2.5.1.

## 5. Fluxos funcionais instalados

- [ ] Dashboard;
- [ ] Produtos;
- [ ] Clientes;
- [ ] Histórico;
- [ ] Financeiro;
- [ ] PDV, venda e finalização;
- [ ] PDF e reimpressão;
- [ ] backup e restore;
- [ ] impressão física;
- [ ] corte físico;
- [ ] comportamento real do driver.

## 6. Preservação de dados

- [ ] desinstalar;
- [ ] confirmar preservação de `%APPDATA%\NabiCode`;
- [ ] reinstalar offline;
- [ ] confirmar recuperação do banco, configurações e backups existentes.

## Critério de conclusão

Somente após todos os itens aplicáveis e os testes físicos obrigatórios estarem
aprovados a candidata poderá ser avaliada para promoção. Este checklist não
promove a versão automaticamente.
