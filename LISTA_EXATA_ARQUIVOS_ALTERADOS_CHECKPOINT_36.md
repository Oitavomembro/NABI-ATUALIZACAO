# Lista exata de arquivos alterados — Checkpoint 36

Comparação contra `NabiCode_v2_5_1_DEV_CHECKPOINT_35_STARTUP_SPLASH.zip`.

## Código de infraestrutura

1. `main.py` — resolução física e somente leitura do perfil dentro do smoke; novo evento `packaged_profile_resolved`.
2. `core/runtime_profile.py` — nova função `resolve_profile_marker()`; nenhuma alteração em `DatabaseUsageLock`, `DatabaseInUseError` ou configuração normal do runtime.
3. `build_tools/build_windows.py` — validação do novo evento e rejeição explícita de eventos com efeitos colaterais.

## Testes

4. `tests/test_offline_build_tools.py` — reprodução do contrato impossível do Checkpoint 35, aprovação do contrato novo e rejeição de runtime indevido.
5. `tests/test_runtime_profile_isolation.py` — comprovação de leitura física independente da variável de ambiente e ausência de escrita.
6. `tests/test_startup_smoke_test.py` — trace exato do smoke e comprovação de que AppData não é criado.

## Documentação

7. `RELATORIO_CHECKPOINT_36_SMOKE_PROFILE.md`
8. `LISTA_EXATA_ARQUIVOS_ALTERADOS_CHECKPOINT_36.md`
9. `RESULTADO_TESTES_CHECKPOINT_36.txt`

Nenhum outro arquivo foi alterado. Em particular, não houve alteração no splash visual, banco, lock, PDV, vendas, financeiro, impressão, corte, reimpressão, regras comerciais, wheelhouse, spec do PyInstaller ou instalador Inno Setup.
